"""
Project graph 2: POLAR CARD of a profile — |CL|, CD and |L/D| vs angle of attack,
with the 3 speeds (110/180/290 km/h) overlaid. Plotly (interactive for Flask) + PNG.

Data: current TE-real dataset, filtered by run_id (NOT by "18 conditions" — that
legacy selection in eda_velocidad.py is stale; profiles now have 21). status == "ok".

|CL| and |L/D| are shown in absolute value (higher = more downforce / efficiency),
consistent with the winner's-curse graph; CD is naturally positive.

Reusable:  from graficas_polares import fig_polares ; fig = fig_polares(run_id)
Direct:    python graficas_polares.py  -> graficas/polar_0014.{html,png}
"""
import os
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from estilo_graficas import PALETA, VEL_COLOR, FONT_FAMILY

BASE = os.path.dirname(os.path.abspath(__file__))
OUTDIR = os.path.join(BASE, "graficas")
RUN_ID_DEFAULT = "0014_20260711_193032"

# (columna, titulo eje, usar valor absoluto)
PANELS = [("CL", "|CL|", True), ("CD", "CD", False), ("LD", "|L/D|", True)]


def fig_polares(run_id, df=None):
    """Return a 1x3 go.Figure (|CL|, CD, |L/D| vs alpha) for the given run_id."""
    if df is None:
        df = pd.read_csv(os.path.join(BASE, "airfoil_dataset.csv"))
    g = df[(df.run_id == run_id) & (df.status == "ok")].copy()
    if g.empty:
        raise ValueError(f"Sin filas 'ok' para run_id={run_id}")
    chord = float(g.chord_length_mm.iloc[0])

    fig = make_subplots(rows=1, cols=3, shared_xaxes=False, horizontal_spacing=0.07,
                        subplot_titles=[p[1] for p in PANELS])

    speeds = sorted(g.velocidad_kmh.unique())
    for ci, (col, ytit, absval) in enumerate(PANELS, start=1):
        for v in speeds:
            s = g[g.velocidad_kmh == v].sort_values("alpha_deg")
            re = int(s.reynolds.iloc[0])
            y = s[col].abs() if absval else s[col]
            xabs = s.alpha_deg.abs()   # |alpha|: eje 0->15 creciente
            fig.add_trace(go.Scatter(
                x=xabs, y=y, mode="lines+markers",
                name=f"{int(v)} km/h",
                legendgroup=f"{int(v)}", showlegend=(ci == 1),
                line=dict(color=VEL_COLOR[int(v)], width=2),
                marker=dict(color=VEL_COLOR[int(v)], size=7,
                            line=dict(color="white", width=1)),
                customdata=[(int(v), re, aa, yy) for aa, yy in zip(xabs, y)],
                hovertemplate=(f"<b>{ytit}</b><br>"
                               "Speed: %{customdata[0]} km/h<br>"
                               "Reynolds: %{customdata[1]:,}<br>"
                               "|α|: %{customdata[2]}&deg;<br>"
                               f"{ytit}: " "%{customdata[3]:.3f}<extra></extra>")),
                row=1, col=ci)

    # estilo compartido (paleta del proyecto), replicado para los 3 ejes del subplot
    fig.update_xaxes(title_text="Angle of attack |α| (°)", color=PALETA["eje"],
                     gridcolor=PALETA["rejilla"], zeroline=False, linecolor=PALETA["eje"],
                     ticks="outside", tickcolor=PALETA["eje"],
                     title_font=dict(color=PALETA["texto"], size=13))
    for ci, (_, ytit, _) in enumerate(PANELS, start=1):
        fig.update_yaxes(title_text=ytit, color=PALETA["eje"], gridcolor=PALETA["rejilla"],
                         zeroline=False, linecolor=PALETA["eje"], ticks="outside",
                         tickcolor=PALETA["eje"], title_font=dict(color=PALETA["texto"], size=13),
                         row=1, col=ci)

    short = run_id.split("_")[0]
    fig.update_layout(
        title=dict(
            text=(f"<b>Polar card — profile {short}</b>"
                  f"<br><span style='font-size:13px;color:{PALETA['eje']}'>"
                  f"chord {chord:.0f} mm &nbsp;·&nbsp; run_id {run_id} &nbsp;·&nbsp; "
                  f"3 speeds overlaid &nbsp;·&nbsp; negative incidence (downforce)</span>"),
            x=0.5, xanchor="center", font=dict(size=19, color=PALETA["texto"]),
            y=0.96, yanchor="top"),
        legend=dict(orientation="h", x=0.5, xanchor="center", y=1.14, yanchor="bottom",
                    title_text="Speed  ", bgcolor="rgba(0,0,0,0)",
                    font=dict(color=PALETA["texto"], size=12.5)),
        plot_bgcolor=PALETA["fondo"], paper_bgcolor=PALETA["fondo_papel"],
        width=1180, height=480,
        font=dict(family=FONT_FAMILY, color=PALETA["texto"], size=12.5),
        margin=dict(l=65, r=30, t=140, b=60))
    # color de los titulos de subplot (make_subplots los coloca en el top del dominio)
    for ann in fig.layout.annotations:
        ann.font.color = PALETA["texto"]; ann.font.size = 14
    return fig


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    fig = fig_polares(RUN_ID_DEFAULT)
    short = RUN_ID_DEFAULT.split("_")[0]
    html_path = os.path.join(OUTDIR, f"polar_{short}.html")
    png_path = os.path.join(OUTDIR, f"polar_{short}.png")
    fig.write_html(html_path, include_plotlyjs="cdn")
    print(f"[OK] HTML -> {html_path}")
    try:
        fig.write_image(png_path, scale=2)
        print(f"[OK] PNG  -> {png_path}")
    except Exception as e:
        print(f"[AVISO] PNG no exportado: {e}")


if __name__ == "__main__":
    main()
