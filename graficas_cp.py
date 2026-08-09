"""
Project graph 4: PRESSURE DISTRIBUTION (Cp). Port of cp_on_demand.py to Plotly.
Uses the arc-order surface split (NOT plot_cp.py's median-of-y, which has the zigzag
bug). Aeronautical convention: Cp axis inverted (negative up). Runs XFOIL on the
TE-real geometry (regenerated from .asc, no CATIA) at the profile's optimal condition.

Reusable:  from graficas_cp import fig_cp ; fig = fig_cp(run_id, vel, alpha)
Direct:    python graficas_cp.py -> graficas/cp_0014.{html,png}
"""
import os, subprocess, shutil
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from estilo_graficas import PALETA, aplica_estilo

BASE = os.path.dirname(os.path.abspath(__file__))
OUTDIR = os.path.join(BASE, "graficas")
from rutas import XFOIL_EXE as XFOIL   # fuente unica de la ruta a XFOIL (ver rutas.py)
RHO, MU, ITER = 1.225, 1.81e-5, 200
RUN_ID_DEFAULT, VEL_DEFAULT, ALPHA_DEFAULT = "0014_20260711_193032", 290, -8

C_SUC, C_PRE = PALETA["k2"], PALETA["k0"]   # suction azul / pressure naranja


def _reynolds(c, v): return RHO * (v / 3.6) * (c / 1000.0) / MU


def _xfoil_cp(dat, Re, alpha, workdir):
    """Corre XFOIL, vuelca Cp (CPWR). Devuelve Nx3 (x,y,Cp) en orden de arco + (cl,cd)."""
    os.makedirs(workdir, exist_ok=True)
    shutil.copy2(dat, os.path.join(workdir, "geom.dat"))
    for f in ("cp.txt", "polar.txt"):
        p = os.path.join(workdir, f)
        if os.path.exists(p): os.remove(p)
    seq = list(range(0, alpha - 1, -2))
    if alpha not in seq: seq.append(alpha)
    cmds = ["LOAD geom.dat", "", "PANE", "OPER", f"VISC {int(round(Re))}", f"ITER {ITER}",
            "PACC", "polar.txt", ""] + [f"ALFA {a}" for a in seq] + \
           ["CPWR cp.txt", "PACC", "", "QUIT"]
    # Semaforo + timeout corto: en la web esto lo dispara un boton publico.
    # Ver el bloque de limites en rutas.py para el porque de cada numero.
    from rutas import semaforo_xfoil, XFOIL_TIMEOUT_S
    with semaforo_xfoil():
        try:
            subprocess.run([XFOIL], input="\n".join(cmds) + "\n", text=True,
                           capture_output=True, cwd=workdir,
                           timeout=XFOIL_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            # se trata como "no convergio": el llamador ya sabe degradar
            return None, None
    cpp = os.path.join(workdir, "cp.txt")
    if not os.path.isfile(cpp):
        return None, None
    rows = []
    for ln in open(cpp, encoding="utf-8", errors="ignore"):
        p = ln.split()
        if len(p) >= 3:
            try: rows.append((float(p[0]), float(p[1]), float(p[2])))
            except ValueError: pass
    arr = np.array(rows)
    # CL/CD de la polar
    clcd = None
    pol = os.path.join(workdir, "polar.txt")
    if os.path.isfile(pol):
        for ln in open(pol, encoding="utf-8", errors="ignore"):
            q = ln.split()
            if len(q) >= 3:
                try:
                    if int(round(float(q[0]))) == alpha:
                        clcd = (float(q[1]), float(q[2]))
                except ValueError: pass
    return arr, clcd


def _split_arc(arr):
    ile = int(np.argmin(arr[:, 0]))
    return arr[:ile + 1].copy(), arr[ile:].copy()


def condicion_optima(run_id, df=None):
    """Detecta la condicion de MAXIMO |L/D| del perfil en el dataset.
    Devuelve (velocidad_kmh, alpha_deg) del pico. Base para el Cp 'optimo' generico."""
    if df is None:
        df = pd.read_csv(os.path.join(BASE, "airfoil_dataset.csv"))
    g = df[(df.run_id == run_id) & (df.status == "ok")].copy()
    if g.empty:
        raise ValueError(f"Sin filas ok para {run_id}")
    best = g.loc[g["LD"].abs().idxmax()]
    return int(best["velocidad_kmh"]), int(best["alpha_deg"])


def _build_cp_fig(cp3, clcd, title, subtitle):
    """Figura Cp (tema oscuro, invertido) desde un cp3 (N,3 x,y,Cp), con la SILUETA
    del perfil como inset (misma codificacion de color que las curvas)."""
    A, B = _split_arc(cp3)
    suc, pre = (A, B) if np.nanmean(A[:, 2]) <= np.nanmean(B[:, 2]) else (B, A)
    fig = go.Figure()
    for arr, nm, col in [(suc, "Suction side", C_SUC), (pre, "Pressure side", C_PRE)]:
        order = np.argsort(arr[:, 0])
        fig.add_trace(go.Scatter(
            x=arr[order, 0], y=arr[order, 2], mode="lines", name=nm,
            line=dict(color=col, width=2),
            hovertemplate=(f"<b>{nm}</b><br>x/c: %{{x:.3f}}<br>Cp: %{{y:.3f}}<extra></extra>")))
    fig.add_hline(y=0, line=dict(color=PALETA["eje"], width=1, dash="dot"))

    # --- INSET: silueta del perfil (columnas x,y del propio cp3), 1:1 ---
    for arr, col in [(suc, C_SUC), (pre, C_PRE)]:
        order = np.argsort(arr[:, 0])
        fig.add_trace(go.Scatter(
            x=arr[order, 0], y=arr[order, 1], mode="lines",
            line=dict(color=col, width=1.6), xaxis="x2", yaxis="y2",
            showlegend=False, hoverinfo="skip"))

    aplica_estilo(fig, title=title, subtitle=subtitle, xaxis_title="x / c",
                  yaxis_title="Cp", width=820, height=620, legend_top=True)
    fig.update_yaxes(autorange="reversed")   # convenio aeronautico: Cp negativo arriba
    # ejes del inset: arriba a la derecha, sin decoracion, escala 1:1
    fig.update_layout(
        xaxis2=dict(domain=[0.60, 0.97], anchor="y2", showgrid=False, zeroline=False,
                    showticklabels=False, showline=False, ticks=""),
        yaxis2=dict(domain=[0.72, 0.93], anchor="x2", showgrid=False, zeroline=False,
                    showticklabels=False, showline=False, ticks="",
                    autorange=True,          # NO heredar el reversed del eje Cp
                    scaleanchor="x2", scaleratio=1),
        annotations=list(fig.layout.annotations or []) + [dict(
            xref="paper", yref="paper", x=0.785, y=0.955, showarrow=False,
            text="profile shape", font=dict(size=10.5, color=PALETA["eje"]))])
    return fig


def fig_cp_from_dat(dat_path, chord, vel, alpha, title, subtitle, workdir=None):
    """Corre XFOIL sobre un .dat CUALQUIERA (no solo del dataset) y devuelve
    (figura, (L/D, Re)). Lanza si XFOIL no converge. Reutilizable para el optimo."""
    Re = _reynolds(chord, vel)
    workdir = workdir or os.path.join(os.environ.get("TEMP", BASE), "cp_dat")
    cp3, clcd = _xfoil_cp(dat_path, Re, alpha, workdir)
    if cp3 is None or len(cp3) < 20:
        raise RuntimeError("XFOIL no convergio sobre el .dat")
    ld = (clcd[0] / clcd[1]) if clcd and clcd[1] else None
    sub = subtitle + f" &nbsp;·&nbsp; Re = {Re:,.0f}" + (
        f" &nbsp;·&nbsp; L/D = {abs(ld):.1f}" if ld else "")
    return _build_cp_fig(cp3, clcd, title, sub), (ld, Re)


def fig_cp(run_id=RUN_ID_DEFAULT, vel=None, alpha=None, df=None):
    from graficas_forma import _dat_tereal
    if df is None:
        df = pd.read_csv(os.path.join(BASE, "airfoil_dataset.csv"))
    if vel is None or alpha is None:      # auto: condicion de maximo |L/D| del perfil
        vel, alpha = condicion_optima(run_id, df)
    chord = float(df[df.run_id == run_id].chord_length_mm.iloc[0])
    dat = _dat_tereal(run_id)
    short = run_id.split("_")[0]
    fig, _ = fig_cp_from_dat(
        dat, chord, vel, alpha,
        "Pressure distribution (Cp) — optimal condition",
        (f"profile {short} &nbsp;·&nbsp; chord {chord:.0f} mm &nbsp;·&nbsp; "
         f"{vel} km/h &nbsp;·&nbsp; |α| = {abs(alpha)}°"),
        workdir=os.path.join(os.environ.get("TEMP", BASE), "cp_plotly", run_id[:4]))
    return fig


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    fig = fig_cp()
    short = RUN_ID_DEFAULT.split("_")[0]
    fig.write_html(os.path.join(OUTDIR, f"cp_{short}.html"), include_plotlyjs="cdn")
    print(f"[OK] HTML -> graficas/cp_{short}.html")
    try:
        fig.write_image(os.path.join(OUTDIR, f"cp_{short}.png"), scale=2)
        print(f"[OK] PNG  -> graficas/cp_{short}.png")
    except Exception as e:
        print(f"[AVISO] PNG: {e}")


if __name__ == "__main__":
    main()
