"""
Project graph 1: WINNER'S CURSE — y como la DENSIFICACION lo encogio.

Dos paneles, porque el mensaje son dos cosas distintas:
  IZQUIERDA (el titular): flechas julio -> densif sobre el error medio. Una flecha
    larguisima (k=0: 21.5% -> 6.9%) y otra que no se mueve (k=2: 3.8% -> 3.7%).
    De un vistazo se ve QUE cambio y QUE no.
  DERECHA (la evidencia): predicho vs real caso a caso con los modelos densif, y
    detras, en gris, la nube de k=0 de julio. Se ve la nube COLAPSAR sobre la
    diagonal, que es el mismo hecho contado por caso en vez de por media.

Por que no basta con sustituir los numeros viejos por los nuevos: el hallazgo NO es
"6.9% y 3.7%". Es que la maldicion se ENCOGIO. Sin el termino de comparacion, un
lector ve 6.9 vs 3.7 y concluye que la penalizacion casi no aporta — justo lo
contrario de lo que pasa (aporta lo mismo; es que hay mucho menos que corregir).

TODOS LOS NUMEROS SE CALCULAN DE LOS DATOS (`stats_bateria`). Antes ERR_MEDIO estaba
hardcodeado a 21.5/3.8 y caduco en silencio con la promocion: la grafica habria seguido
dibujando los valores de julio aunque se le cambiara el fichero de entrada.

Uso:
    from graficas_winner_curse import fig_winner_curse, _carga
    k0, k2 = _carga()                 # densif (produccion)
    fig = fig_winner_curse(k0, k2)

Directo:  python graficas_winner_curse.py  -> graficas/winner_curse.{html,png}
"""
import os, json
import numpy as np
import plotly.graph_objects as go
from estilo_graficas import PALETA, FONT_FAMILY, aplica_estilo, caja_bg

BASE = os.path.dirname(os.path.abspath(__file__))
OUTDIR = os.path.join(BASE, "graficas")

# Las DOS baterias. Julio no es un dato caducado: es el termino de comparacion.
BATERIAS = {"julio": "bateria_tereal", "densif": "bateria_densif"}
ETIQUETA_BAT = {"julio": "before densification", "densif": "after densification"}
COLOR = {"k0": PALETA["k0"], "k2": PALETA["k2"]}
NOMBRE = {"k0": "k = 0 (naive)", "k2": "k = 2 (penalised)"}
GRIS = PALETA["eje"]


def _carga(tag="densif"):
    """Casos (k0, k2) de una bateria. Por defecto la DENSIF, que es la vigente."""
    pref = BATERIAS[tag]
    k0 = json.load(open(os.path.join(BASE, f"{pref}_k0_resultados.json"), encoding="utf-8"))
    k2 = json.load(open(os.path.join(BASE, f"{pref}_k2_resultados.json"), encoding="utf-8"))
    return k0, k2


def _err(c):
    """Error relativo |L/D| en %, o None si el caso no convergio en XFOIL."""
    if not c.get("LD_real"):
        return None
    return abs(c["LD_real"] - c["LD_pred"]) / abs(c["LD_real"]) * 100


def stats_bateria(k0, k2):
    """TODO lo que el texto necesita, DERIVADO de los casos. Nada hardcodeado."""
    e0 = [e for e in (_err(c) for c in k0) if e is not None]
    e2 = [e for e in (_err(c) for c in k2) if e is not None]
    signos = sum(1 for c in k0
                 if c.get("LD_real") and abs(c["LD_real"]) < abs(c["LD_pred"]))
    m0, m2 = float(np.mean(e0)), float(np.mean(e2))
    return {
        "k0": m0, "k2": m2,
        "mediana_k0": float(np.median(e0)), "mediana_k2": float(np.median(e2)),
        "n_k0": len(e0), "n_k2": len(e2), "n_casos": len(k0),
        "factor": m0 / m2 if m2 else float("nan"),
        "signos": signos, "n_signos": len(e0),
    }


def _serie(casos):
    """Casos convergidos -> (x=|pred|, y=|real|, hover payload)."""
    xs, ys, cd = [], [], []
    for c in casos:
        e = _err(c)
        if e is None:
            continue
        xs.append(abs(c["LD_pred"])); ys.append(abs(c["LD_real"]))
        cd.append((c["caso"], c["cuerda"], c["vel"], c["alpha"],
                   abs(c["LD_pred"]), abs(c["LD_real"]), e))
    return xs, ys, cd


def fig_winner_curse(k0=None, k2=None):
    """GRAFICA 1, SIMPLE: predicho vs real con los datos densif. UNA sola idea.

    Se probo meter aqui el contraste julio->densif (nube fantasma + panel de flechas) y
    hubo que deshacerlo: doblaba los elementos visuales para transmitir un dato que cabe
    en una linea de texto, y la figura dejaba de leerse de un vistazo. El antes/despues
    vive ahora en `fig_evolucion`, solo y a tamano completo, que es donde gana."""
    if k0 is None or k2 is None:
        k0, k2 = _carga("densif")
    S = stats_bateria(k0, k2)
    series = {"k0": _serie(k0), "k2": _serie(k2)}

    todos = [v for s in series.values() for v in (s[0] + s[1])]
    lo, hi = min(todos), max(todos)
    pad = (hi - lo) * 0.06
    lo, hi = lo - pad, hi + pad

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=[lo, hi], y=[lo, hi], mode="lines", name="Perfect prediction",
        line=dict(color=GRIS, width=1.6, dash="dash"), hoverinfo="skip"))

    hover = ("<b>Case %{customdata[0]}</b><br>Chord: %{customdata[1]} mm<br>"
             "Speed: %{customdata[2]} km/h<br>Angle: %{customdata[3]}&deg;<br>"
             "Predicted |L/D|: %{customdata[4]:.1f}<br>"
             "Actual |L/D|: %{customdata[5]:.1f}<br>"
             "Error: %{customdata[6]:.1f}%<extra></extra>")
    for tag in ("k0", "k2"):
        xs, ys, cd = series[tag]
        fig.add_trace(go.Scatter(
            x=xs, y=ys, mode="markers", name=NOMBRE[tag],
            marker=dict(color=COLOR[tag], size=10, opacity=0.85,
                        line=dict(color="white", width=1.0)),
            customdata=cd, hovertemplate=hover))

    # error medio, DERIVADO (antes ERR_MEDIO estaba hardcodeado a 21.5/3.8)
    fig.add_annotation(
        xref="x domain", yref="y domain", x=0.035, y=0.965,
        xanchor="left", yanchor="top", align="left", showarrow=False,
        bordercolor=PALETA["rejilla"], borderwidth=1, borderpad=9,
        bgcolor=caja_bg(0.9), font=dict(size=13.5, color=PALETA["texto"]),
        text=(f"<b>Mean error</b><br>"
              f"<span style='color:{COLOR['k0']}'>●</span> k = 0: {S['k0']:.1f}%<br>"
              f"<span style='color:{COLOR['k2']}'>●</span> k = 2: {S['k2']:.1f}%"))
    # test de signos: esquina inferior derecha, vacia por construccion (mucho predicho
    # con poco real seria un error enorme, que no se da)
    fig.add_annotation(
        xref="x domain", yref="y domain", x=0.97, y=0.035,
        xanchor="right", yanchor="bottom", align="right", showarrow=False,
        font=dict(size=12, color=GRIS),
        text=(f"Naive optimisation overpredicts in "
              f"{S['signos']}/{S['n_signos']} converged cases"))

    aplica_estilo(
        fig,
        title="Winner's curse: naive vs uncertainty-penalised optimisation",
        subtitle=(f"{S['n_casos']}-case validation battery, after densification — "
                  f"every point verified in XFOIL"),
        xaxis_title="Predicted |L/D|", yaxis_title="Actual |L/D| (XFOIL)",
        width=860, height=780, legend_top=True)
    fig.update_xaxes(range=[lo, hi], constrain="domain")
    fig.update_yaxes(range=[lo, hi], scaleanchor="x", scaleratio=1)
    return fig


def fig_evolucion():
    """BLOQUE DE EVOLUCION: el antes/despues, SOLO y a tamano completo.

    Dos filas (naive y penalizada) sobre el mismo eje de error medio, con el tramo
    recorrido de julio a densif. Una linea larguisima y otra que no se mueve: el
    mensaje esta en la LONGITUD, no en los numeros. Se descarto meterlo dentro de la
    grafica 1 (competia con el scatter) y como barras agrupadas (cuatro barras invitan
    a comparar k2-julio con k2-densif, que es la lectura equivocada)."""
    S = {"julio": stats_bateria(*_carga("julio")),
         "densif": stats_bateria(*_carga("densif"))}
    fig = go.Figure()
    FILA = {"k0": 1.0, "k2": 0.0}
    xmax = S["julio"]["k0"]
    for tag in ("k0", "k2"):
        y = FILA[tag]
        xa, xb = S["julio"][tag], S["densif"][tag]
        fig.add_trace(go.Scatter(
            x=[xa, xb], y=[y, y], mode="lines", showlegend=False, hoverinfo="skip",
            line=dict(color=COLOR[tag], width=5)))
        fig.add_trace(go.Scatter(
            x=[xa], y=[y], mode="markers", showlegend=False,
            marker=dict(color=PALETA["fondo"], size=20,
                        line=dict(color=COLOR[tag], width=3)),
            hovertemplate=(f"<b>{NOMBRE[tag]} — {ETIQUETA_BAT['julio']}</b><br>"
                           f"mean error {xa:.1f}%<extra></extra>")))
        fig.add_trace(go.Scatter(
            x=[xb], y=[y], mode="markers", showlegend=False,
            marker=dict(color=COLOR[tag], size=20,
                        line=dict(color=PALETA["fondo"], width=2)),
            hovertemplate=(f"<b>{NOMBRE[tag]} — {ETIQUETA_BAT['densif']}</b><br>"
                           f"mean error {xb:.1f}%<extra></extra>")))
        junto = abs(xa - xb) < xmax * 0.10
        if junto:
            fig.add_annotation(x=max(xa, xb), y=y + 0.22, xanchor="left",
                               showarrow=False, text=f"   {xa:.1f}% → <b>{xb:.1f}%</b>",
                               font=dict(size=16, color=COLOR[tag]))
        else:
            fig.add_annotation(x=xa, y=y + 0.22, showarrow=False, text=f"{xa:.1f}%",
                               font=dict(size=16, color=GRIS))
            fig.add_annotation(x=xb, y=y + 0.22, showarrow=False,
                               text=f"<b>{xb:.1f}%</b>",
                               font=dict(size=18, color=COLOR[tag]))
        fig.add_annotation(x=-0.4, y=y, xanchor="right", showarrow=False,
                           text=f"<b>{NOMBRE[tag]}</b>",
                           font=dict(size=15, color=COLOR[tag]))
        d = xa - xb
        fig.add_annotation(x=(xa + xb) / 2, y=y - 0.24, showarrow=False,
                           text=(f"−{d:.1f} points" if d > 0.5 else "unchanged"),
                           font=dict(size=13.5,
                                     color=PALETA["texto"] if d > 0.5 else GRIS))

    sj, sd = S["julio"], S["densif"]
    aplica_estilo(
        fig,
        title="What densification changed",
        subtitle=("Mean |L/D| error against XFOIL, before → after adding three speeds "
                  "and every intermediate angle"),
        xaxis_title="Mean |L/D| error vs XFOIL (%)", yaxis_title=None,
        width=1080, height=420, legend_top=False)
    fig.update_xaxes(range=[-6.5, xmax * 1.12], tickvals=[0, 5, 10, 15, 20],
                     ticktext=["0%", "5%", "10%", "15%", "20%"])
    # el eje Y no codifica nada (solo separa las dos filas): fuera etiquetas, rejilla,
    # linea Y TICKS. Con ticks="outside" heredado del estilo quedaban unas rayitas
    # sueltas a la izquierda que parecian un eje a medio dibujar.
    fig.update_yaxes(range=[-0.75, 1.75], showgrid=False, showticklabels=False,
                     zeroline=False, ticks="", linecolor="rgba(0,0,0,0)")
    fig.update_layout(showlegend=False, margin=dict(l=40, r=40, t=120, b=110))
    fig.add_annotation(
        xref="paper", yref="paper", x=0.5, y=-0.30, xanchor="center", yanchor="top",
        align="center", showarrow=False, bordercolor=PALETA["rejilla"], borderwidth=1,
        borderpad=10, bgcolor=caja_bg(0.9), font=dict(size=13, color=PALETA["texto"]),
        text=(f"The gap between naive and penalised narrowed from "
              f"<b>{sj['factor']:.1f}×</b> to <b>{sd['factor']:.1f}×</b> — not because "
              f"the penalty stopped working,<br>but because there is far less left to "
              f"correct."))
    return fig


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    k0, k2 = _carga("densif")
    s = stats_bateria(k0, k2)
    print(f"     densif: k0 {s['k0']:.1f}%  k2 {s['k2']:.1f}%  factor {s['factor']:.1f}x  "
          f"signos {s['signos']}/{s['n_signos']}  (TODO calculado de los datos)")
    for nombre, fig in (("winner_curse", fig_winner_curse(k0, k2)),
                        ("evolucion_densif", fig_evolucion())):
        fig.write_html(os.path.join(OUTDIR, nombre + ".html"), include_plotlyjs="cdn")
        try:
            fig.write_image(os.path.join(OUTDIR, nombre + ".png"), scale=2)
            print(f"[OK] {nombre}.html + .png")
        except Exception as e:
            print(f"[AVISO] {nombre}: PNG no exportado: {e}")


if __name__ == "__main__":
    main()
