"""
Project graph 1: AIRFOIL SHAPE (real 1:1). Port of plot_perfil.py to Plotly.

IMPORTANT: the archived dataset_runs/{run_id}/airfoil_v4.dat is the OLD amputated
geometry (pre TE-real). To show the clean TE-real shape (no kink), this regenerates
the .dat from the archived .asc via genera_tereal (portable, no CATIA, no production
touch), caches it in graficas/_dats/, and plots that.

Reusable:  from graficas_forma import fig_forma ; fig = fig_forma(run_id)
Direct:    python graficas_forma.py -> graficas/forma_0014.{html,png}
"""
import os
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from estilo_graficas import PALETA, FONT_FAMILY

BASE = os.path.dirname(os.path.abspath(__file__))
OUTDIR = os.path.join(BASE, "graficas")
DATCACHE = os.path.join(OUTDIR, "_dats")
RUN_ID_DEFAULT = "0014_20260711_193032"


def _dat_tereal(run_id):
    """Regenera el .dat TE-real desde el .asc archivado (cacheado). Devuelve ruta."""
    os.makedirs(DATCACHE, exist_ok=True)
    out = os.path.join(DATCACHE, f"{run_id}_tereal.dat")
    if not os.path.exists(out):
        from piloto_tereal import genera_tereal
        asc = os.path.join(BASE, "dataset_runs", run_id, "auto_export.asc")
        if not os.path.exists(asc):
            raise FileNotFoundError(f"Sin .asc archivado para {run_id}")
        genera_tereal(asc, out)
    return out


def _leer_dat(path):
    xs, ys = [], []
    with open(path, encoding="utf-8", errors="ignore") as f:
        for i, ln in enumerate(f):
            p = ln.split()
            if len(p) < 2:
                continue
            try:
                xs.append(float(p[0])); ys.append(float(p[1]))
            except ValueError:
                continue
    return np.array(xs), np.array(ys)


def fig_forma(run_id=RUN_ID_DEFAULT, df=None):
    if df is None:
        df = pd.read_csv(os.path.join(BASE, "airfoil_dataset.csv"))
    row = df[df.run_id == run_id]
    chord = float(row.chord_length_mm.iloc[0]) if not row.empty else 1.0

    x, y = _leer_dat(_dat_tereal(run_id))
    xm, ym = x * chord, y * chord                      # mm reales
    # TE romo: hueco entre primer y ultimo punto (= espesor de TE en mm)
    te_mm = float(np.hypot(xm[0] - xm[-1], ym[0] - ym[-1]))

    xs = np.append(xm, xm[0]); ys = np.append(ym, ym[0])   # cerrar contorno

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=xs, y=ys, mode="lines", name="Airfoil",
        line=dict(color=PALETA["texto"], width=1.8),
        fill="toself", fillcolor="rgba(240,243,246,0.06)",
        customdata=np.stack([xs, ys], axis=1),
        hovertemplate="x: %{customdata[0]:.2f} mm<br>y: %{customdata[1]:.2f} mm<extra></extra>"))

    short = run_id.split("_")[0]
    fig.update_layout(
        title=dict(
            text=(f"<b>Airfoil shape — profile {short}</b>"
                  f"<br><span style='font-size:13px;color:{PALETA['eje']}'>"
                  f"chord {chord:.1f} mm &nbsp;·&nbsp; TE thickness {te_mm:.2f} mm "
                  f"&nbsp;·&nbsp; TE-real geometry (blunt TE, no kink)</span>"),
            x=0.5, xanchor="center", font=dict(size=19, color=PALETA["texto"]),
            y=0.9, yanchor="top"),
        xaxis=dict(title="x (mm)", color=PALETA["eje"], gridcolor=PALETA["rejilla"],
                   zeroline=False, linecolor=PALETA["eje"], ticks="outside",
                   tickcolor=PALETA["eje"], title_font=dict(color=PALETA["texto"], size=13),
                   constrain="domain"),
        yaxis=dict(title="y (mm)", color=PALETA["eje"], gridcolor=PALETA["rejilla"],
                   zeroline=False, linecolor=PALETA["eje"], ticks="outside",
                   tickcolor=PALETA["eje"], title_font=dict(color=PALETA["texto"], size=13),
                   scaleanchor="x", scaleratio=1),      # 1:1 REAL
        plot_bgcolor=PALETA["fondo"], paper_bgcolor=PALETA["fondo_papel"], showlegend=False,
        width=1180, height=430,
        font=dict(family=FONT_FAMILY, color=PALETA["texto"], size=12.5),
        margin=dict(l=60, r=30, t=90, b=55))
    return fig


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    fig = fig_forma()
    short = RUN_ID_DEFAULT.split("_")[0]
    fig.write_html(os.path.join(OUTDIR, f"forma_{short}.html"), include_plotlyjs="cdn")
    print(f"[OK] HTML -> graficas/forma_{short}.html")
    try:
        fig.write_image(os.path.join(OUTDIR, f"forma_{short}.png"), scale=2)
        print(f"[OK] PNG  -> graficas/forma_{short}.png")
    except Exception as e:
        print(f"[AVISO] PNG: {e}")


if __name__ == "__main__":
    main()
