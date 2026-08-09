"""
CURVAS PREDICHAS del perfil OPTIMO (perfil nuevo, NO en el dataset).
Predice CL/CD/|L-D| a lo largo de los angulos, en las 3 velocidades (110/180/290),
con los modelos de produccion + feature_utils. Banda +-sigma (ensemble LD) en |L/D|.

Reutiliza el ESTILO de graficas_polares (paleta, VEL_COLOR, layout) pero alimentado
por PREDICCIONES, no por el CSV. NO toca produccion.

  from curvas_optimo import fig_curvas_optimo
  fig = fig_curvas_optimo(shape_params_dict)   # -> go.Figure
"""
import os
import numpy as np
import joblib
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from feature_utils import SHAPE, FEATURES, f_alpha_over_sqrtre, f_te_rel
from estilo_graficas import PALETA, VEL_COLOR, FONT_FAMILY

BASE = os.path.dirname(os.path.abspath(__file__))
RHO, MU = 1.225, 1.81e-5
# Barrido escalonado por velocidad: los LIMITES son los del dataset real
# (-10/-12/-14 segun velocidad), pero el PASO es de 1 grado, no de 2.
# Por que paso 1: el angulo recomendado se decide sobre una rejilla de 1 grado
# (metricas_banda) y casi siempre cae impar, asi que con muestreo par el punto naranja
# no tenia vertice donde apoyarse y Plotly interpolaba recto por debajo del valor real
# (la curva es convexa ahi) -> el punto parecia flotar sobre la linea. Es solo densidad
# de dibujo: NO cambia ningun calculo, ni el angulo, ni los KPIs.
V_MARCA = 180        # DEFAULT de la velocidad de decision (= inversa_service.V_KMH)
VEL_REF = (110, 180, 290)                       # las 3 con datos reales
VEL_ALPHA_MIN = {110: -10, 180: -12, 290: -14}
VEL_ALPHAS = {v: [-a for a in range(0, abs(amin) + 1)] for v, amin in VEL_ALPHA_MIN.items()}


def _alphas_de(v):
    """Rejilla de angulos (paso 1) para una velocidad cualquiera. Las 3 de referencia
    usan su limite medido; para una velocidad de usuario intermedia se interpola con
    guardas_velocidad.alpha_max_soportado (misma fuente que el aviso de angulo, para
    que la curva no llegue mas lejos de donde el sistema dice que hay datos)."""
    vi = int(round(v))
    if vi in VEL_ALPHAS:
        return VEL_ALPHAS[vi]
    from guardas_velocidad import alpha_max_soportado
    amax = int(round(alpha_max_soportado(v)))
    return [-a for a in range(0, amax + 1)]
PANELS = [("CL", "|CL|", True), ("CD", "CD", False), ("LD", "|L/D|", True)]

_CL = joblib.load(os.path.join(BASE, "modelo_CL_xgb.joblib"))["model"]
_CD = joblib.load(os.path.join(BASE, "modelo_CD_xgb.joblib"))["model"]
_LD = joblib.load(os.path.join(BASE, "modelo_LD_inversa_xgb.joblib"))["model"]
_ENS = joblib.load(os.path.join(BASE, "ensemble_ld_sigma.joblib"))


def _reynolds(chord_mm, v_kmh):
    return RHO * (v_kmh / 3.6) * (chord_mm / 1000.0) / MU


def _features(shape, alphas, v):
    """(n,11) para un vector de alphas a velocidad v, via feature_utils."""
    n = len(alphas)
    chord = shape[0]; te = shape[4]
    a = np.array(alphas, float)
    re = np.full(n, _reynolds(chord, v))
    full = np.tile(shape, (n, 1))
    trel = np.full(n, f_te_rel(te, chord))          # te y chord escalares -> array
    return np.column_stack([full, a, re, f_alpha_over_sqrtre(a, re), trel])


def fig_curvas_optimo(shape_params, alpha_rec=None, v_marca=V_MARCA, franja=None,
                      ld_banda=None):
    """Polares predichas. `v_marca` es la velocidad a la que se decidio el angulo
    recomendado (la del usuario). Si no es una de las 3 de referencia se dibuja ADEMAS
    su curva, en ambar: si no, el punto naranja volveria a flotar entre dos curvas,
    que es justo el fallo de coherencia que se corrigio.

    `ld_banda`: |L/D| MEDIO de la banda (= el KPI de Results, metricas_banda['LD']).
    Se usa solo en el hover del punto: el punto vale el |L/D| PUNTUAL del argmax (un
    pico) y el KPI es la MEDIA de la banda, asi que por definicion no coinciden. Sin
    decirlo parecia un descuadre, de modo que el hover muestra los dos y los nombra."""
    shape = np.array([float(shape_params[k]) for k in SHAPE])
    fig = make_subplots(rows=1, cols=3, horizontal_spacing=0.07,
                        subplot_titles=[p[1] for p in PANELS])

    vm = float(v_marca)
    es_ref = int(round(vm)) in VEL_ALPHAS
    velocidades = list(VEL_REF) if es_ref else sorted(list(VEL_REF) + [vm])

    for ci, (col, ytit, absval) in enumerate(PANELS, start=1):
        for v in velocidades:
            propia = (not es_ref) and abs(v - vm) < 1e-9      # la curva del usuario
            color = PALETA["k0"] if propia else VEL_COLOR[int(v)]
            nombre = f"{v:g} km/h" + (" (yours)" if propia else "")
            alphas = _alphas_de(v)
            X = _features(shape, alphas, v)
            re = int(round(_reynolds(shape[0], v)))
            pred = {"CL": _CL.predict(X), "CD": _CD.predict(X), "LD": _LD.predict(X)}[col]
            y = np.abs(pred) if absval else pred
            xabs = np.abs(alphas)

            # banda +-sigma (solo |L/D|, ensemble LD)
            if col == "LD":
                P = np.stack([m.predict(X) for m in _ENS])
                sd = P.std(axis=0)
                up, lo = np.abs(pred) + sd, np.abs(pred) - sd
                r, g, b = _hex_rgb(color)
                fig.add_trace(go.Scatter(
                    x=np.concatenate([xabs, xabs[::-1]]),
                    y=np.concatenate([up, lo[::-1]]), mode="lines", fill="toself",
                    fillcolor=f"rgba({r},{g},{b},0.13)", line=dict(width=0),
                    hoverinfo="skip", showlegend=False), row=1, col=ci)

            fig.add_trace(go.Scatter(
                x=xabs, y=y, mode="lines+markers", name=nombre,
                legendgroup=f"{v:g}", showlegend=(ci == 1),
                line=dict(color=color, width=2.8 if propia else 2.2),
                # marcador mas pequeno que antes: con paso 1 grado hay ~2x puntos y con
                # size=6 se solapaban hasta empastar la linea
                marker=dict(color=color, size=4, line=dict(color=PALETA["fondo"], width=0.8)),
                customdata=[(v, re, aa, yy) for aa, yy in zip(xabs, y)],
                hovertemplate=(f"<b>{ytit} (predicted)</b><br>Speed: %{{customdata[0]:g}} km/h<br>"
                               "Reynolds: %{customdata[1]:,}<br>|α|: %{customdata[2]}&deg;<br>"
                               f"{ytit}: " "%{customdata[3]:.3f}<extra></extra>")),
                row=1, col=ci)

    # marca del ANGULO RECOMENDADO: franja sombreada + punto en el panel |L/D|
    r0, g0, b0 = _hex_rgb(PALETA["k0"])

    # FRANJA: la zona de angulos que el modelo no distingue del mejor (ver
    # optimo_geom.franja_angulo). Es lo que comunica la incertidumbre; el punto del
    # argmax se queda solo como marca central, no como promesa de precision de 1 grado.
    if franja is not None:
        f_lo, f_hi = float(franja[0]), float(franja[1])
        if f_hi > f_lo:
            fig.add_vrect(x0=f_lo, x1=f_hi, row=1, col=3,
                          fillcolor=f"rgba({r0},{g0},{b0},0.13)", line_width=0, layer="below")
            for xb in (f_lo, f_hi):
                fig.add_vline(x=xb, row=1, col=3,
                              line=dict(color=f"rgba({r0},{g0},{b0},0.35)", width=1, dash="dot"))

    if alpha_rec is not None:
        ar = abs(float(alpha_rec))
        # solo en el panel |L/D| (donde importa) y sutil: no debe dominar la grafica
        if franja is None or float(franja[1]) <= float(franja[0]):
            fig.add_vline(x=ar, row=1, col=3,
                          line=dict(color=f"rgba({r0},{g0},{b0},0.45)", width=1, dash="dot"))
        # El punto va SIEMPRE a vm = la misma velocidad a la que se decidio el angulo.
        # Antes se dibujaba a 290 fija: el punto flotaba sobre la curva equivocada y,
        # como el optimo se desplaza con el Reynolds, aparentaba no caer en el pico.
        # Ver CLAUDE.md (efecto Reynolds).
        Xr = _features(shape, [-ar], vm)
        ldr = abs(float(_LD.predict(Xr)[0]))
        hay_franja = franja is not None and float(franja[1]) > float(franja[0])
        etiqueta = (f"recommended |α| {float(franja[0]):g}–{float(franja[1]):g}° @{vm:g} km/h"
                    if hay_franja else f"recommended |α| ~{ar:g}° @{vm:g} km/h")
        extra = (f"<br>Within {float(franja[0]):g}–{float(franja[1]):g}&deg; the model cannot "
                 "tell these apart" if hay_franja else "")
        # PICO vs MEDIA: el punto es el |L/D| puntual del argmax; el KPI de arriba es la
        # media sobre la banda. Se nombran los dos para que el usuario no lea un
        # descuadre donde solo hay dos magnitudes distintas.
        media = ("" if ld_banda is None else
                 f"<br>Band mean (the KPI above): {abs(float(ld_banda)):.1f}")
        fig.add_trace(go.Scatter(
            x=[ar], y=[ldr], mode="markers", name=etiqueta,
            marker=dict(color=PALETA["k0"], size=12, symbol="circle",
                        line=dict(color=PALETA["fondo"], width=1.5)),
            hovertemplate=(f"<b>Recommended angle</b> (decided at {vm:g} km/h)"
                           f"<br>|L/D| at {ar:g}&deg;: " "%{y:.1f}"
                           + (" (peak of the band)" if media else "")
                           + media + extra + "<extra></extra>")),
            row=1, col=3)

    fig.update_xaxes(title_text="Angle of attack |α| (°)", color=PALETA["eje"],
                     gridcolor=PALETA["rejilla"], zeroline=False, linecolor=PALETA["eje"],
                     ticks="outside", tickcolor=PALETA["eje"],
                     title_font=dict(color=PALETA["texto"], size=12))
    for ci, (_, ytit, _) in enumerate(PANELS, start=1):
        fig.update_yaxes(title_text=ytit, color=PALETA["eje"], gridcolor=PALETA["rejilla"],
                         zeroline=False, linecolor=PALETA["eje"], ticks="outside",
                         tickcolor=PALETA["eje"], title_font=dict(color=PALETA["texto"], size=12),
                         row=1, col=ci)

    fig.update_layout(
        title=dict(text="<b>Predicted polars of the optimum</b> "
                        "<span style='font-size:12px;color:" + PALETA["eje"] + "'>— surrogate "
                        + ("prediction across 3 speeds" if es_ref else
                           f"prediction at your {vm:g} km/h (amber) plus the 3 reference speeds")
                        + "</span>",
                   x=0.5, xanchor="center", font=dict(size=15, color=PALETA["texto"]),
                   y=0.97, yanchor="top"),
        legend=dict(orientation="h", x=0.5, xanchor="center", y=1.14, yanchor="bottom",
                    title_text="Speed  ", bgcolor="rgba(0,0,0,0)",
                    font=dict(color=PALETA["texto"], size=12)),
        plot_bgcolor=PALETA["fondo"], paper_bgcolor=PALETA["fondo_papel"],
        width=1080, height=460, font=dict(family=FONT_FAMILY, color=PALETA["texto"], size=12),
        margin=dict(l=55, r=25, t=145, b=52))
    for ann in fig.layout.annotations:
        ann.font.color = PALETA["texto"]; ann.font.size = 13
    return fig


def fig_ld_vs_velocidad(shape_params, alpha_abs, v_min=100, v_max=300, paso=5,
                        v_marca=None):
    """|L/D| y CD del OPTIMO a su angulo recomendado, barriendo la velocidad de forma
    continua (Reynolds recalculado en cada punto). Banda +-sigma del ensemble y los 3
    puntos ancla (110/180/290) donde el dataset tiene referencia."""
    shape = np.array([float(shape_params[k]) for k in SHAPE])
    a = -abs(float(alpha_abs))
    if v_marca is not None:            # el barrido debe CONTENER la velocidad del usuario
        v_min = min(v_min, int(np.floor(float(v_marca) / paso) * paso))
        v_max = max(v_max, int(np.ceil(float(v_marca) / paso) * paso))
    vs = np.arange(v_min, v_max + 1e-9, paso, dtype=float)

    ld, cd, sd = [], [], []
    for v in vs:
        X = _features(shape, [a], v)
        ld.append(abs(float(_LD.predict(X)[0])))
        cd.append(float(_CD.predict(X)[0]))
        sd.append(float(np.stack([m.predict(X) for m in _ENS]).std(axis=0)[0]))
    ld, cd, sd = np.array(ld), np.array(cd), np.array(sd)

    fig = make_subplots(rows=1, cols=2, horizontal_spacing=0.10,
                        subplot_titles=["|L/D|", "CD"])
    r, g, b = _hex_rgb(PALETA["k2"])
    # banda +-sigma en |L/D|
    fig.add_trace(go.Scatter(
        x=np.concatenate([vs, vs[::-1]]), y=np.concatenate([ld + sd, (ld - sd)[::-1]]),
        mode="lines", fill="toself", fillcolor=f"rgba({r},{g},{b},0.15)",
        line=dict(width=0), hoverinfo="skip", showlegend=False), row=1, col=1)

    for ci, (y, nm) in enumerate([(ld, "|L/D|"), (cd, "CD")], start=1):
        fig.add_trace(go.Scatter(
            x=vs, y=y, mode="lines", name="Surrogate prediction",
            legendgroup="pred", showlegend=(ci == 1),
            line=dict(color=PALETA["k2"], width=2.4),
            customdata=[(v, int(round(_reynolds(shape[0], v)))) for v in vs],
            hovertemplate=(f"<b>{nm}</b><br>Speed: %{{customdata[0]:.0f}} km/h<br>"
                           "Reynolds: %{customdata[1]:,}<br>"
                           f"{nm}: %{{y:.4f}}<extra></extra>")),
            row=1, col=ci)
        # anclas: las 3 velocidades con datos de referencia
        anc = [110, 180, 290]
        ya = [float(np.interp(v, vs, y)) for v in anc]
        fig.add_trace(go.Scatter(
            x=anc, y=ya, mode="markers", name="Reference speeds (dataset)",
            legendgroup="anc", showlegend=(ci == 1),
            marker=dict(color=PALETA["eje"], size=9, line=dict(color=PALETA["fondo"], width=1.5)),
            hovertemplate=f"<b>{nm} @ %{{x}} km/h</b><br>{nm}: %{{y:.4f}}<extra></extra>"),
            row=1, col=ci)
        # la velocidad del USUARIO, destacada en ambar (coherente con el punto naranja
        # de las polares: el ambar significa siempre "tu punto de diseno")
        if v_marca is not None:
            vm = float(v_marca)
            fig.add_trace(go.Scatter(
                x=[vm], y=[float(np.interp(vm, vs, y))], mode="markers",
                name=f"your speed ({vm:g} km/h)", legendgroup="yours", showlegend=(ci == 1),
                marker=dict(color=PALETA["k0"], size=13, symbol="circle",
                            line=dict(color=PALETA["fondo"], width=1.5)),
                hovertemplate=(f"<b>Your speed</b><br>{nm} @ {vm:g} km/h: "
                               "%{y:.4f}<extra></extra>")),
                row=1, col=ci)

    fig.update_xaxes(title_text="Speed (km/h)", range=[v_min, v_max], color=PALETA["eje"],
                     gridcolor=PALETA["rejilla"], zeroline=False, linecolor=PALETA["eje"],
                     ticks="outside", tickcolor=PALETA["eje"],
                     title_font=dict(color=PALETA["texto"], size=12))
    for ci, t in enumerate(["|L/D|", "CD"], start=1):
        fig.update_yaxes(title_text=t, color=PALETA["eje"], gridcolor=PALETA["rejilla"],
                         zeroline=False, linecolor=PALETA["eje"], ticks="outside",
                         tickcolor=PALETA["eje"], title_font=dict(color=PALETA["texto"], size=12),
                         row=1, col=ci)
    fig.update_layout(
        title=dict(text=("<b>Performance vs speed</b> <span style='font-size:12px;color:"
                         + PALETA["eje"] + "'>— your optimum at |α| ~"
                         + f"{abs(float(alpha_abs)):g}°, Reynolds recomputed at every point</span>"),
                   x=0.5, xanchor="center", font=dict(size=15, color=PALETA["texto"]),
                   y=0.97, yanchor="top"),
        legend=dict(orientation="h", x=0.5, xanchor="center", y=1.10, yanchor="bottom",
                    bgcolor="rgba(0,0,0,0)", font=dict(color=PALETA["texto"], size=12)),
        plot_bgcolor=PALETA["fondo"], paper_bgcolor=PALETA["fondo_papel"],
        width=1080, height=380, font=dict(family=FONT_FAMILY, color=PALETA["texto"], size=12),
        margin=dict(l=60, r=25, t=120, b=50))
    for ann in fig.layout.annotations:
        ann.font.color = PALETA["texto"]; ann.font.size = 13
    return fig


def _hex_rgb(h):
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


if __name__ == "__main__":
    import json
    d = json.load(open(os.path.join(BASE, "inversa_v2_propuesta_top1.json"), encoding="utf-8"))
    fig = fig_curvas_optimo(d["shape_params"])
    os.makedirs(os.path.join(BASE, "graficas"), exist_ok=True)
    fig.write_image(os.path.join(BASE, "graficas", "_curvas_optimo.png"), scale=2)
    print("[OK] graficas/_curvas_optimo.png")
