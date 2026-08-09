"""
Project graph 2: WINNER'S CURSE BY CHORD ZONE — grouped bars.
Mean |L/D| error of k=0 vs k=2 in the three chord zones, from the 40-case battery.

Reusable:  from graficas_winner_zona import fig_winner_zona ; fig = fig_winner_zona()
Direct:    python graficas_winner_zona.py -> graficas/winner_zona.{html,png}
"""
import os, json
import numpy as np
import plotly.graph_objects as go
from estilo_graficas import PALETA, aplica_estilo

BASE = os.path.dirname(os.path.abspath(__file__))
OUTDIR = os.path.join(BASE, "graficas")
ZONAS = [("150-200", 150, 200), ("200-400", 200, 400), ("400-500", 400, 500)]
COLOR = {"k0": PALETA["k0"], "k2": PALETA["k2"]}
NOMBRE = {"k0": "k = 0 (naive)", "k2": "k = 2 (penalised)"}


# Las dos baterias: la densif es la vigente, julio es el termino de comparacion.
BATERIAS = {"julio": "bateria_tereal", "densif": "bateria_densif"}


def _stats(tag_bat="densif"):
    """Error medio por zona de cuerda. TODO derivado de los casos."""
    pref = BATERIAS[tag_bat]
    k0 = {c["caso"]: c for c in json.load(
        open(os.path.join(BASE, f"{pref}_k0_resultados.json"), encoding="utf-8"))}
    k2 = {c["caso"]: c for c in json.load(
        open(os.path.join(BASE, f"{pref}_k2_resultados.json"), encoding="utf-8"))}
    def err(c): return abs(c["LD_real"] - c["LD_pred"]) / abs(c["LD_real"]) * 100 if c.get("LD_real") else None
    out = {}
    for zname, lo, hi in ZONAS:
        e0 = [err(c) for c in k0.values() if lo <= c["cuerda"] < hi and err(c) is not None]
        e2 = [err(k2[cid]) for cid, c in k0.items() if lo <= c["cuerda"] < hi and err(k2[cid]) is not None]
        out[zname] = {"k0": float(np.mean(e0)), "k2": float(np.mean(e2)),
                      "n0": len(e0), "n2": len(e2)}
    return out


def fig_winner_zona():
    """GRAFICA 2, SIMPLE: dos barras por zona, solo densif. UNA idea.

    Se probo superponer las barras de julio en gris y hubo que quitarlas: con cuatro
    barras el ojo empareja lo ADYACENTE (k2-julio con k2-densif) y concluye "no ha
    cambiado nada", cuando el mensaje es que k=0 se desplomo. La grafica trabajaba
    contra su propio texto. El antes/despues lo lleva el bloque de evolucion; aqui
    solo queda una nota al pie con la cifra de referencia."""
    st = _stats("densif")
    sj = _stats("julio")            # solo para la nota al pie
    znames = [z[0] for z in ZONAS]
    fig = go.Figure()

    for tag in ("k0", "k2"):
        vals = [st[z][tag] for z in znames]
        ns = [st[z][f"n{tag[-1]}"] for z in znames]
        fig.add_trace(go.Bar(
            x=znames, y=vals, name=NOMBRE[tag], marker_color=COLOR[tag],
            text=[f"{v:.1f}%" for v in vals], textposition="outside",
            textfont=dict(color=PALETA["texto"], size=12),
            customdata=list(zip(ns, vals)),
            hovertemplate=(f"<b>{NOMBRE[tag]}</b><br>Zone: %{{x}} mm<br>"
                           "Mean |L/D| error: %{customdata[1]:.1f}%<br>"
                           "n = %{customdata[0]} cases<extra></extra>")))

    peor_j = max(sj[z]["k0"] for z in znames)
    peor_d = max(st[z]["k0"] for z in znames)
    aplica_estilo(
        fig,
        title="Winner's curse by chord zone",
        subtitle=(f"Mean |L/D| error vs XFOIL — {sum(st[z]['n0'] for z in znames)} "
                  f"converged cases, after densification"),
        xaxis_title="Chord zone (mm)", yaxis_title="Mean |L/D| error (%)",
        width=860, height=620, legend_top=True)
    fig.update_layout(barmode="group", bargap=0.35, bargroupgap=0.12,
                      margin=dict(l=70, r=40, t=140, b=110))
    fig.update_yaxes(range=[0, peor_d * 1.25])
    fig.update_xaxes(scaleanchor=None)  # barras: no forzar 1:1
    fig.add_annotation(
        xref="paper", yref="paper", x=0.5, y=-0.155, xanchor="center", yanchor="top",
        showarrow=False, font=dict(size=12, color=PALETA["eje"]),
        text=(f"Before densification the worst zone was {peor_j:.1f}%. No zone is an "
              f"outlier any more: naive error now spans "
              f"{min(st[z]['k0'] for z in znames):.1f}–{peor_d:.1f}% across all three."))
    return fig


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    fig = fig_winner_zona()
    fig.write_html(os.path.join(OUTDIR, "winner_zona.html"), include_plotlyjs="cdn")
    print("[OK] HTML -> graficas/winner_zona.html")
    try:
        fig.write_image(os.path.join(OUTDIR, "winner_zona.png"), scale=2)
        print("[OK] PNG  -> graficas/winner_zona.png")
    except Exception as e:
        print(f"[AVISO] PNG: {e}")


if __name__ == "__main__":
    main()
