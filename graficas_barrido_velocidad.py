"""
Project graph 3: SPEED SWEEP — surrogate prediction vs XFOIL measurements.
For a fixed profile and fixed angle, sweep speed continuously (every 5 km/h),
recomputing Reynolds per speed, and predict |CL|, CD, |L/D| with the surrogate.
XFOIL measured points (the 3 dataset speeds) are overlaid.

Features are built via feature_utils (single source of truth) — never by hand.
An uncertainty band (±σ) from the LD ensemble is shown on the |L/D| panel
(the ensemble models LD only).

Reusable:  from graficas_barrido_velocidad import fig_barrido ; fig = fig_barrido(run_id, alpha)
Direct:    python graficas_barrido_velocidad.py -> graficas/barrido_0014.{html,png}
"""
import os
import numpy as np
import pandas as pd
import joblib
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from sklearn.linear_model import LinearRegression
from xgboost import XGBRegressor
from feature_utils import SHAPE, FEATURES, add_derived
from estilo_graficas import PALETA, FONT_FAMILY

BASE = os.path.dirname(os.path.abspath(__file__))
OUTDIR = os.path.join(BASE, "graficas")
RUN_ID_DEFAULT = "0014_20260711_193032"
ALPHA_DEFAULT = -6

RHO, MU = 1.225, 1.81e-5
def reynolds(chord_mm, v_kmh):
    return RHO * (v_kmh / 3.6) * (chord_mm / 1000.0) / MU

C_LINE = PALETA["k2"]      # surrogate (azul)
C_PTS = PALETA["k0"]       # XFOIL medido (naranja)
PANELS = [("CL", "|CL|", True), ("CD", "CD", False), ("LD", "|L/D|", True)]


def _modelos():
    """CL, CD y LD de produccion, todos cargados de disco (+ ensemble).

    El CSV es el DENSIFICADO: es el que tiene las 6 velocidades medidas, y es ademas
    con el que se entrenaron estos modelos, asi que curva y puntos vienen del mismo
    universo. Con airfoil_dataset.csv (sin promocionar, 3 velocidades) la grafica
    mezclaba modelo nuevo con mediciones viejas y solo se veian 3 puntos."""
    df = pd.read_csv(os.path.join(BASE, "airfoil_dataset_densif_merged.csv"))
    cl = joblib.load(os.path.join(BASE, "modelo_CL_xgb.joblib"))["model"]
    cd = joblib.load(os.path.join(BASE, "modelo_CD_xgb.joblib"))["model"]  # antes inline
    ld = joblib.load(os.path.join(BASE, "modelo_LD_inversa_xgb.joblib"))["model"]
    ens = None
    p = os.path.join(BASE, "ensemble_ld_sigma.joblib")
    if os.path.exists(p):
        ens = joblib.load(p)
    return {"CL": cl, "CD": cd, "LD": ld}, ens, df


def _features_barrido(shape_row, alpha, vels):
    """DataFrame de features (11) para el barrido, via feature_utils (add_derived)."""
    rows = []
    for v in vels:
        r = {k: shape_row[k] for k in SHAPE}
        r["alpha_deg"] = alpha
        r["reynolds"] = reynolds(shape_row["chord_length_mm"], v)
        rows.append(r)
    d = add_derived(pd.DataFrame(rows))
    return d[FEATURES].values


def fig_barrido(run_id=RUN_ID_DEFAULT, alpha=ALPHA_DEFAULT):
    modelos, ens, df = _modelos()
    g = df[(df.run_id == run_id) & (df.status == "ok")]
    if g.empty:
        raise ValueError(f"Sin filas ok para {run_id}")
    shape_row = {k: float(g[k].iloc[0]) for k in SHAPE}
    chord = shape_row["chord_length_mm"]

    vsweep = np.arange(100, 301, 5)
    Xs = _features_barrido(shape_row, alpha, vsweep)
    pred = {c: modelos[c].predict(Xs) for c, _, _ in PANELS}
    # sigma del ensemble (solo LD)
    sd = None
    if ens is not None:
        P = np.stack([m.predict(Xs) for m in ens])
        sd = P.std(axis=0)

    # puntos XFOIL medidos a este alpha
    meas = g[g.alpha_deg == alpha].sort_values("velocidad_kmh")

    fig = make_subplots(rows=1, cols=3, horizontal_spacing=0.07,
                        subplot_titles=[p[1] for p in PANELS])

    for ci, (col, ytit, absval) in enumerate(PANELS, start=1):
        yp = np.abs(pred[col]) if absval else pred[col]

        # banda +-sigma (solo LD, donde hay ensemble)
        if col == "LD" and sd is not None:
            up, lo = np.abs(pred[col]) + sd, np.abs(pred[col]) - sd
            fig.add_trace(go.Scatter(
                x=np.concatenate([vsweep, vsweep[::-1]]),
                y=np.concatenate([up, lo[::-1]]), fill="toself",
                fillcolor="rgba(27,158,138,0.20)", line=dict(width=0),
                hoverinfo="skip", showlegend=(ci == 3), name="Surrogate ±σ"),
                row=1, col=ci)

        # linea del surrogate
        fig.add_trace(go.Scatter(
            x=vsweep, y=yp, mode="lines", name="Surrogate prediction",
            legendgroup="sur", showlegend=(ci == 1),
            line=dict(color=C_LINE, width=2.4),
            customdata=[(v, int(round(reynolds(chord, v))), yy) for v, yy in zip(vsweep, yp)],
            hovertemplate=(f"<b>{ytit} — surrogate</b><br>Speed: %{{customdata[0]}} km/h<br>"
                           "Reynolds: %{customdata[1]:,}<br>"
                           f"{ytit}: %{{customdata[2]:.3f}}<extra></extra>")),
            row=1, col=ci)

        # puntos XFOIL
        ym = meas[col].abs() if absval else meas[col]
        fig.add_trace(go.Scatter(
            x=meas.velocidad_kmh, y=ym, mode="markers", name="XFOIL measurements",
            legendgroup="xf", showlegend=(ci == 1),
            marker=dict(color=C_PTS, size=11, symbol="circle",
                        line=dict(color="white", width=1.5)),
            customdata=[(int(v), int(r), yy) for v, r, yy in
                        zip(meas.velocidad_kmh, meas.reynolds, ym)],
            hovertemplate=(f"<b>{ytit} — XFOIL</b><br>Speed: %{{customdata[0]}} km/h<br>"
                           "Reynolds: %{customdata[1]:,}<br>"
                           f"{ytit}: %{{customdata[2]:.3f}}<extra></extra>")),
            row=1, col=ci)

    fig.update_xaxes(title_text="Speed (km/h)", range=[100, 300], color=PALETA["eje"],
                     gridcolor=PALETA["rejilla"], zeroline=False, linecolor=PALETA["eje"],
                     ticks="outside", tickcolor=PALETA["eje"],
                     title_font=dict(color=PALETA["texto"], size=13))
    for ci, (col, ytit, _) in enumerate(PANELS, start=1):
        # |CL| con rango fijo: el auto-zoom (~3 centesimas) magnifica un error del ~1%.
        # CD y |L/D| en auto (ahi la variacion con la velocidad si es significativa).
        yrange = [0.8, 1.3] if col == "CL" else None
        fig.update_yaxes(title_text=ytit, range=yrange, color=PALETA["eje"],
                         gridcolor=PALETA["rejilla"], zeroline=False, linecolor=PALETA["eje"],
                         ticks="outside", tickcolor=PALETA["eje"],
                         title_font=dict(color=PALETA["texto"], size=13), row=1, col=ci)

    short = run_id.split("_")[0]
    fig.update_layout(
        title=dict(
            text=(f"<b>Speed sweep — surrogate prediction vs XFOIL</b>"
                  f"<br><span style='font-size:13px;color:{PALETA['eje']}'>"
                  f"profile {short} &nbsp;·&nbsp; chord {chord:.0f} mm &nbsp;·&nbsp; "
                  f"|α| = {abs(alpha)}° (downforce) &nbsp;·&nbsp; "
                  f"{len(meas)} measured speeds</span>"),
            x=0.5, xanchor="center", font=dict(size=19, color=PALETA["texto"]),
            y=0.96, yanchor="top"),
        legend=dict(orientation="h", x=0.5, xanchor="center", y=1.14, yanchor="bottom",
                    bgcolor="rgba(0,0,0,0)", font=dict(color=PALETA["texto"], size=12.5)),
        plot_bgcolor=PALETA["fondo"], paper_bgcolor=PALETA["fondo_papel"],
        width=1180, height=480,
        font=dict(family=FONT_FAMILY, color=PALETA["texto"], size=12.5),
        margin=dict(l=65, r=30, t=140, b=60))
    for ann in fig.layout.annotations:
        ann.font.color = PALETA["texto"]; ann.font.size = 14
    return fig


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    fig = fig_barrido()
    short = RUN_ID_DEFAULT.split("_")[0]
    html_path = os.path.join(OUTDIR, f"barrido_{short}.html")
    png_path = os.path.join(OUTDIR, f"barrido_{short}.png")
    fig.write_html(html_path, include_plotlyjs="cdn")
    print(f"[OK] HTML -> {html_path}")
    try:
        fig.write_image(png_path, scale=2)
        print(f"[OK] PNG  -> {png_path}")
    except Exception as e:
        print(f"[AVISO] PNG no exportado: {e}")


if __name__ == "__main__":
    main()
