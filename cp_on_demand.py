"""
Cp A DEMANDA para UNA condicion real del dataset (velocidad + angulo).
- Usa el .dat YA archivado en dataset_runs/{run_id}/ (no reconstruye en CATIA).
- Corre XFOIL con el Reynolds REAL de esa velocidad (Re = rho*V*L/mu).
- Dibuja el Cp con recuadro que muestra el Re/velocidad/angulo reales.

SEPARACION DE CARAS POR ORDEN DE ARCO (como XFOIL):
  El contorno de XFOIL (CPWR: x,y,Cp) viene en orden de arco TE->LE->TE. Se
  separa extrados/intrados cortando en el LE (argmin(x)), EXACTAMENTE como hace
  XFOIL. Esto elimina de raiz el zigzag cerca del TE (que lo causaba separar por
  mediana de y + orden por x, que en perfiles invertidos mezcla las dos caras
  donde y~0 cerca del TE). Ya NO hace falta suavizado cosmetico.

Etiquetas succion/presion: la cara de succion se identifica por Cp medio mas
negativo; en perfiles invertidos de downforce debe ser la cara INFERIOR (menor y),
cosa que se verifica y se anota.

Diagnostico opcional --hardcopy: hace que XFOIL vuelque SU PROPIA grafica de Cp a
PostScript nativo (comando HARD -> plot.ps) y la rasteriza, para contrastar con la
fuente.

NO toca el pipeline de generacion; reutiliza lectores de plot_cp por import.

Uso:
  python cp_on_demand.py                                   # perfil/condicion por defecto
  python cp_on_demand.py --run-id X --vel 290 --alpha -14
  python cp_on_demand.py --run-id X --vel 180 --alpha -6 --hardcopy
"""
import os
import sys
import shutil
import argparse
import subprocess
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import plot_cp as pc           # solo lectores (.dat, cp, polar); no se edita
import generate_batch as gb    # compute_reynolds
import run_xfoil as rx         # XFOIL_EXE

BASE = os.path.dirname(os.path.abspath(__file__))
OUTDIR = os.path.join(BASE, "eda_outputs")
os.makedirs(OUTDIR, exist_ok=True)
DF = pd.read_csv(os.path.join(BASE, "airfoil_dataset.csv"))

NCRIT = 9.0
ITER = 200


# =========================================================
# SEPARACION DE CARAS POR ORDEN DE ARCO (como XFOIL)
# =========================================================
def split_arc_order(arr):
    """
    Separa un contorno (Nx2 geometria o Nx3 x,y,Cp) que viene en orden de arco
    TE->LE->TE, cortando en el LE = argmin(x). Devuelve (rama1, rama2) SIN
    reordenar por x (el orden de arco ya es monotono en x en cada cara).
    """
    ile = int(np.argmin(arr[:, 0]))
    return arr[:ile + 1].copy(), arr[ile:].copy()


# =========================================================
# SUAVIZADO COSMETICO DEL TE  ---  DEPRECADO / NO USADO
# =========================================================
# Se conserva por si acaso, pero YA NO se usa: la separacion por orden de arco
# elimina el zigzag de raiz (era un artefacto de separar por mediana de y, no
# del solver). El flag --suavizar-te se retiro. Para reactivarlo habria que
# volver a llamar a suavizar_te() sobre las ramas antes de dibujar.
#
# def _median_filter(y, k=5):
#     n = len(y); h = k // 2; out = y.copy()
#     for i in range(n):
#         seg = y[max(0, i-h):min(n, i+h+1)]
#         seg = seg[np.isfinite(seg)]
#         if len(seg): out[i] = np.median(seg)
#     return out
#
# def suavizar_te(branch, x_te=0.65, kernel=5):
#     ...  # (mediana local gated por zona TE + alta frecuencia)


# =========================================================
# XFOIL + LECTURA
# =========================================================
def run_xfoil_single(dat_src, Re, alpha, workdir, hardcopy=False):
    os.makedirs(workdir, exist_ok=True)
    shutil.copy2(dat_src, os.path.join(workdir, "geom.dat"))
    for f in ("cp.txt", "polar.txt", "plot.ps"):
        p = os.path.join(workdir, f)
        if os.path.exists(p):
            os.remove(p)
    # Marchar desde 0 hasta alpha (paso -2) para que XFOIL converja; solo se
    # escribe el Cp del angulo objetivo. Rutas CORTAS (cwd=workdir).
    seq = list(range(0, alpha - 1, -2)) if alpha < 0 else list(range(0, alpha + 1, 2))
    if alpha not in seq:
        seq.append(alpha)
    cmds = ["LOAD geom.dat", "", "PANE", "OPER",
            f"VISC {int(round(Re))}", f"ITER {ITER}", "PACC", "polar.txt", ""]
    cmds += [f"ALFA {a}" for a in seq]
    if hardcopy:                      # volcado nativo de XFOIL (Xplot11 -> plot.ps)
        cmds.append("HARD")
    cmds += ["CPWR cp.txt", "PACC", "", "QUIT"]
    subprocess.run([rx.XFOIL_EXE], input="\n".join(cmds) + "\n", text=True,
                   capture_output=True, cwd=workdir, timeout=120)
    cp = os.path.join(workdir, "cp.txt")
    return (cp if os.path.isfile(cp) else None), os.path.join(workdir, "polar.txt")


def polar_cl_cd_cm(polar_path, alpha):
    rows = pc.read_polar_file(polar_path)
    row = pc.find_polar_row_for_alpha(rows, alpha)
    if row is None:
        return None, None, None
    return row["CL"], row["CD"], row["CM"]


# =========================================================
# RENDER del plot.ps NATIVO de XFOIL (diagnostico --hardcopy)
# =========================================================
def render_native_ps(ps_path, out_png):
    with open(ps_path, encoding="latin-1") as f:
        txt = f.read()
    body = txt.split("setrgbcolor pop pop pop } bind def", 1)[-1]
    polys, pending, cur, color = [], [], [], (0, 0, 0)

    def flush():
        nonlocal cur
        if len(cur) >= 2:
            polys.append((color, np.array(cur, float)))
        cur = []

    for t in body.replace("\n", " ").split():
        try:
            pending.append(float(t)); continue
        except ValueError:
            pass
        if t == "M":
            flush()
            if len(pending) >= 2:
                cur = [(pending[-2] / 10.0, pending[-1] / 10.0)]
        elif t == "L":
            if len(pending) >= 2:
                cur.append((pending[-2] / 10.0, pending[-1] / 10.0))
        elif t == "CO":
            flush()
            if len(pending) >= 3:
                color = tuple(v / 255.0 for v in pending[-3:])
        elif t == "SG":
            flush()
            if pending:
                g = pending[-1]; color = (g, g, g)
        elif t in ("stroke", "CPSM", "CFS", "NP"):
            flush()
        pending = []
    flush()
    fig, ax = plt.subplots(figsize=(11, 8), facecolor="white")
    for c, p in polys:
        ax.plot(p[:, 0], p[:, 1], color=c, lw=0.7)
    ax.set_aspect("equal"); ax.axis("off")
    ax.set_title("XFOIL NATIVO (plot.ps: sus propios trazos vectoriales)", fontsize=11)
    fig.savefig(out_png, dpi=130, facecolor="white", bbox_inches="tight")
    plt.close(fig)


# =========================================================
# MAIN
# =========================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", default="0048_20260701_202312")
    ap.add_argument("--vel", type=int, default=180)
    ap.add_argument("--alpha", type=int, default=-6)
    ap.add_argument("--hardcopy", action="store_true",
                    help="ademas, vuelca y rasteriza la grafica NATIVA de XFOIL (.ps)")
    args = ap.parse_args()
    run_id, vel, alpha = args.run_id, args.vel, args.alpha

    sub = DF[DF["run_id"] == run_id]
    if sub.empty:
        print(f"[ERROR] run_id no encontrado: {run_id}"); return 1
    chord = float(sub["chord_length_mm"].iloc[0])
    Re = gb.compute_reynolds(chord, vel)
    dat_src = os.path.join(BASE, "dataset_runs", run_id, "airfoil_v4.dat")
    if not os.path.isfile(dat_src):
        print(f"[ERROR] no existe el .dat archivado: {dat_src}"); return 1

    print(f"[INFO] perfil={run_id[:4]}  v={vel} km/h  alpha={alpha}")
    print(f"[INFO] cuerda={chord:.1f} mm -> Reynolds REAL = {Re:,.0f}")

    workdir = os.path.join(os.environ.get("TEMP", BASE), "cp_ondemand", run_id[:4])
    cp_txt, polar = run_xfoil_single(dat_src, Re, alpha, workdir, hardcopy=args.hardcopy)
    if cp_txt is None:
        print("[ERROR] XFOIL no genero el Cp (no convergio?)"); return 1

    # --- lectura en ORDEN DE ARCO (sin reordenar) ---
    airfoil = pc.read_airfoil_dat(dat_src)          # Nx2 (x,y), orden de arco
    cp3 = pc.read_cp_file(cp_txt)                    # Nx3 (x,y,Cp), orden de arco

    geoA, geoB = split_arc_order(airfoil)
    cpA, cpB = split_arc_order(cp3)

    # cpA<->geoA y cpB<->geoB (misma cara: ambos recorren TE->LE->TE igual).
    # Succion = cara con Cp medio mas negativo.
    if np.nanmean(cpA[:, 2]) <= np.nanmean(cpB[:, 2]):
        cp_suc, cp_pre, geo_suc, geo_pre = cpA, cpB, geoA, geoB
    else:
        cp_suc, cp_pre, geo_suc, geo_pre = cpB, cpA, geoB, geoA

    # Verificacion: en downforce invertido, la succion debe ser la cara INFERIOR
    suc_es_inferior = np.nanmean(geo_suc[:, 1]) < np.nanmean(geo_pre[:, 1])
    lado_suc = "inferior" if suc_es_inferior else "superior"
    print(f"[INFO] separacion por ORDEN DE ARCO | succion = cara {lado_suc} "
          f"(mean_y_suc={np.nanmean(geo_suc[:,1]):+.4f} vs "
          f"mean_y_pre={np.nanmean(geo_pre[:,1]):+.4f})")

    cl, cd, cm = polar_cl_cd_cm(polar, alpha)
    ld = cl / cd if (cl is not None and cd not in (None, 0)) else None

    # ---- figura estilo XFOIL (Cp arriba invertido, geometria abajo) ----
    C_SUC, C_PRE, c_txt, c_ax = "#00E5FF", "#E5C800", "#D8D8D8", "#B0B0B0"
    fig = plt.figure(figsize=(12.8, 7.2), facecolor="black")

    ax1 = fig.add_axes([0.07, 0.40, 0.88, 0.50], facecolor="black")
    ax1.plot(cp_suc[:, 0], cp_suc[:, 2], color=C_SUC, lw=1.25, label="succión")
    ax1.plot(cp_pre[:, 0], cp_pre[:, 2], color=C_PRE, lw=1.25, label="presión")
    ax1.set_xlim(-0.04, 1.10)
    cp_all = np.concatenate([cp_suc[:, 2], cp_pre[:, 2]])
    cp_all = cp_all[np.isfinite(cp_all)]
    m = max(0.15, 0.12 * (cp_all.max() - cp_all.min() + 1e-6))
    ax1.set_ylim(cp_all.max() + m, cp_all.min() - m)   # Cp invertido
    ax1.set_ylabel("Cp", color=c_txt, fontsize=20)
    ax1.tick_params(colors=c_txt, labelsize=12)
    for sp in ax1.spines.values():
        sp.set_color(c_ax); sp.set_linewidth(0.8)
    ax1.axhline(0.0, color=c_ax, lw=0.8, alpha=0.85)
    ax1.set_xticks(np.linspace(0, 1, 6)); ax1.set_xticklabels([])
    ax1.legend(loc="lower right", facecolor="black", edgecolor=c_ax,
               labelcolor=c_txt, fontsize=10)

    info = [f"perfil {run_id[:4]}", "",
            f"V   = {vel} km/h",
            f"Re  = {Re/1e6:.3f}*10$^6$   (REAL)",
            f"a   = {alpha: .1f} deg"]
    if cl is not None: info.append(f"C$_L$ = {cl: .4f}")
    if cm is not None: info.append(f"C$_M$ = {cm: .4f}")
    if cd is not None: info.append(f"C$_D$ = {cd: .5f}")
    if ld is not None: info.append(f"L/D = {ld: .2f}")
    info.append(f"N$_{{cr}}$ = {NCRIT: .2f}")
    info.append("")
    info.append(f"succion: cara {lado_suc}")
    ax1.text(0.66, 0.97, "\n".join(info), transform=ax1.transAxes,
             color=c_txt, fontsize=12, ha="left", va="top", family="monospace")
    ax1.set_title(f"Cp REAL (orden de arco) | {run_id[:4]} | {vel} km/h | "
                  f"alpha {alpha} deg | Re={Re:,.0f}", color=c_txt, fontsize=12, pad=10)

    ax2 = fig.add_axes([0.07, 0.10, 0.88, 0.18], facecolor="black")
    ax2.plot(geo_suc[:, 0], geo_suc[:, 1], color=C_SUC, lw=1.25)
    ax2.plot(geo_pre[:, 0], geo_pre[:, 1], color=C_PRE, lw=1.25)
    ax2.set_xlim(-0.04, 1.10)
    yall = np.concatenate([geo_suc[:, 1], geo_pre[:, 1]])
    ym = max(0.015, 0.20 * (yall.max() - yall.min() + 1e-6))
    ax2.set_ylim(yall.min() - ym, yall.max() + ym)
    ax2.set_xticks([]); ax2.set_yticks([])
    for sp in ax2.spines.values():
        sp.set_visible(False)

    out_png = os.path.join(OUTDIR, f"cp_{run_id[:4]}_v{vel}_a{alpha}_arcorder.png")
    plt.savefig(out_png, dpi=180, facecolor="black", bbox_inches="tight")
    plt.close(fig)
    print(f"[OK] PNG guardado: {out_png}")
    print(f"[DATOS crudos] CL={cl} CD={cd} CM={cm} LD={ld}")

    # --- diagnostico opcional: grafica nativa de XFOIL ---
    if args.hardcopy:
        ps = os.path.join(workdir, "plot.ps")
        if os.path.isfile(ps):
            ps_keep = os.path.join(OUTDIR, f"cp_{run_id[:4]}_v{vel}_a{alpha}_XFOILnative.ps")
            shutil.copy2(ps, ps_keep)
            native_png = os.path.join(OUTDIR, f"cp_{run_id[:4]}_v{vel}_a{alpha}_XFOILnative.png")
            render_native_ps(ps, native_png)
            print(f"[OK] XFOIL nativo: {ps_keep}")
            print(f"[OK] XFOIL nativo rasterizado: {native_png}")
        else:
            print("[AVISO] --hardcopy pedido pero XFOIL no genero plot.ps")
    return 0


if __name__ == "__main__":
    sys.exit(main())
