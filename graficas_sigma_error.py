"""
Project graph 3: SIGMA vs REAL ERROR — does the ensemble sigma predict where the
model fails? Scatter: x = predicted sigma (ensemble), y = real |L/D| error of the
k=2 proposal, one point per battery case. Trend line + correlation if present.

Reusable:  from graficas_sigma_error import fig_sigma_error ; fig = fig_sigma_error()
Direct:    python graficas_sigma_error.py -> graficas/sigma_error.{html,png}
"""
import os, json
import numpy as np
from scipy import stats
import plotly.graph_objects as go
from estilo_graficas import PALETA, aplica_estilo, caja_bg

BASE = os.path.dirname(os.path.abspath(__file__))
OUTDIR = os.path.join(BASE, "graficas")


BATERIAS = {"julio": "bateria_tereal", "densif": "bateria_densif"}


def _datos(tag_bat="densif"):
    pref = BATERIAS[tag_bat]
    k2 = json.load(open(os.path.join(BASE, f"{pref}_k2_resultados.json"), encoding="utf-8"))
    xs, ys, cd = [], [], []
    for c in k2:
        if not c.get("LD_real") or c.get("sigma") is None:
            continue
        err = abs(c["LD_real"] - c["LD_pred"]) / abs(c["LD_real"]) * 100
        xs.append(c["sigma"]); ys.append(err)
        cd.append((c["caso"], c["cuerda"], c["vel"], c["alpha"], c["sigma"], err))
    return np.array(xs), np.array(ys), cd


def fig_sigma_error():
    """σ vs error real, con las DOS baterías.

    Honestidad obligada: con los datos densif la correlación cae y deja de ser
    significativa (ρ≈0.2, p>0.05). No es que σ se haya roto — es que ya casi no hay
    errores grandes que señalar: σ se movía en 0.11-2.52 y ahora en 0.11-1.30, y los
    errores que ordenaba han desaparecido. Ocultarlo mostrando solo julio sería
    vender una capacidad que los datos vigentes ya no respaldan.
    """
    x, y, cd = _datos("densif")
    xj, yj, _ = _datos("julio")          # solo para la caja de contraste, no se dibuja
    rho, p_rho = stats.spearmanr(x, y)
    rho_j, p_j = stats.spearmanr(xj, yj)
    a, b = np.polyfit(x, y, 1)

    fig = go.Figure()
    xl = np.array([x.min(), x.max()])
    fig.add_trace(go.Scatter(
        x=xl, y=a * xl + b, mode="lines", name="Linear trend",
        line=dict(color=PALETA["eje"], width=1.6, dash="dash"), hoverinfo="skip"))
    fig.add_trace(go.Scatter(
        x=x, y=y, mode="markers", name="Battery case",
        marker=dict(color=PALETA["k2"], size=10, opacity=0.9,
                    line=dict(color="white", width=1)),
        customdata=cd,
        hovertemplate=("<b>Case %{customdata[0]}</b><br>chord %{customdata[1]} mm · "
                       "%{customdata[2]} km/h · %{customdata[3]}°<br>"
                       "σ (ensemble): %{customdata[4]:.2f}<br>"
                       "Real |L/D| error: %{customdata[5]:.1f}%<extra></extra>")))

    sig = "significant" if p_rho < 0.05 else "not significant"
    fig.add_annotation(
        # arriba a la IZQUIERDA: ahi el scatter esta vacio (sigma baja con error alto
        # no se da). Arriba a la derecha tapaba el caso de sigma 1.01 / error 12.2%.
        xref="x domain", yref="y domain", x=0.03, y=0.97, xanchor="left",
        yanchor="top", align="left", showarrow=False, bordercolor=PALETA["rejilla"],
        borderwidth=1, borderpad=9, bgcolor=caja_bg(0.9),
        font=dict(size=12.5, color=PALETA["texto"]),
        text=(f"Spearman ρ = <b>{rho:.2f}</b> (p = {p_rho:.2f}, {sig})<br>"
              f"n = {len(x)} cases · σ spans {x.min():.2f}–{x.max():.2f}<br>"
              f"<span style='color:{PALETA['eje']}'>before densification: "
              f"ρ = {rho_j:.2f}, σ spanned {xj.min():.2f}–{xj.max():.2f}</span>"))

    aplica_estilo(
        fig,
        title="σ flagged the big failures — and now there are barely any",
        subtitle="Predicted uncertainty vs real k=2 error, after densification",
        xaxis_title="Predicted σ (LD ensemble)", yaxis_title="Real |L/D| error of k=2 (%)",
        width=860, height=620, legend_top=True)
    fig.update_layout(margin=dict(l=70, r=40, t=140, b=115))
    fig.add_annotation(
        xref="paper", yref="paper", x=0.5, y=-0.165, xanchor="center", yanchor="top",
        showarrow=False, font=dict(size=12, color=PALETA["eje"]),
        text=("σ has less to rank now: both its range and the errors it used to sort "
              "collapsed. It stays as a guard, not as a fine-grained predictor."))
    fig.update_xaxes(range=[0, x.max() * 1.10])
    fig.update_yaxes(range=[0, y.max() * 1.12])
    return fig


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    fig = fig_sigma_error()
    fig.write_html(os.path.join(OUTDIR, "sigma_error.html"), include_plotlyjs="cdn")
    print("[OK] HTML -> graficas/sigma_error.html")
    try:
        fig.write_image(os.path.join(OUTDIR, "sigma_error.png"), scale=2)
        print("[OK] PNG  -> graficas/sigma_error.png")
    except Exception as e:
        print(f"[AVISO] PNG: {e}")


if __name__ == "__main__":
    main()
