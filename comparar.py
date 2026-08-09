"""
COMPARACION de disenos guardados (NIVEL 2). Portable e INSTANTANEO:
- curvas superpuestas |CL| / CD / |L/D| vs |alpha| de 2-3 perfiles a una velocidad
  de referencia (surrogate; NO se reejecuta la inversa).
- siluetas superpuestas (contornos normalizados x/c) desde los 7 params, con el
  generador arreglado (geometria pura, milisegundos).

Reutiliza: curvas_optimo (modelos ya cargados + features), airfoil_geom_fixed,
estilo_graficas (paleta COMPARE_COLORS). NO toca produccion.
"""
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import airfoil_geom_fixed as FIX
from curvas_optimo import _CL, _CD, _LD, _features, VEL_ALPHAS, _reynolds, _alphas_de
from feature_utils import SHAPE
from estilo_graficas import PALETA, COMPARE_COLORS, FONT_FAMILY

PANELS = [("CL", "|CL|", True), ("CD", "CD", False), ("LD", "|L/D|", True)]

# Velocidad de los guardados ANTERIORES a la feature C5. No es una suposicion: era la
# constante cableada (inversa_service.V_KMH), asi que un guardado sin velocidad se hizo
# necesariamente a 180. Se marca igualmente en la UI para no dar por sabido lo que el
# fichero guardado no dice.
VEL_LEGACY = 180.0


def _shape_vec(sp):
    return np.array([float(sp[k]) for k in SHAPE])


def _vel_de(d):
    """Velocidad de diseno del guardado. Devuelve (velocidad, es_asumida)."""
    v = d.get("velocidad_kmh")
    if v is None:
        return VEL_LEGACY, True
    return float(v), False


def _etiqueta(d):
    """Nombre para leyenda: incluye SIEMPRE la velocidad, porque desde C5 cada curva
    se dibuja a la suya y comparar sin verla induciria a error."""
    v, asumida = _vel_de(d)
    return f"{d['name']} · {v:g} km/h" + (" †" if asumida else "")


def _subtitulo_vel(disenos, mismo_angulo=True, breve=False):
    """Subtitulo honesto: si todos comparten velocidad se dice y ya; si no, se avisa de
    que parte de la diferencia entre curvas es la velocidad, no la forma.
    mismo_angulo=False para el Cp, donde cada perfil va en SU angulo recomendado.
    breve=True para el Cp, cuyo titulo ya arrastra la leyenda de suction/pressure y se
    salia del lienzo con la version larga (el aviso completo lo da la nota de la vista)."""
    vs = [_vel_de(d)[0] for d in disenos]
    if len(set(vs)) == 1:
        return f"all at {vs[0]:g} km/h" + (", same angle" if mismo_angulo else "")
    lista = ", ".join(f"{v:g}" for v in vs) + " km/h"
    if breve:
        return f"each at ITS OWN design speed ({lista})"
    return (f"each at ITS OWN design speed ({lista}) — part of the gap between "
            + ("curves" if mismo_angulo else "them") + " is the speed, not the shape")


def _rangos_comunes(disenos, margen=0.08):
    """Rango Y por panel cubriendo todos los disenos, CADA UNO A SU VELOCIDAD.

    Se calcula sobre lo que realmente se dibuja (no sobre las 3 velocidades): al
    comparar perfiles de cuerdas muy distintas, el envolvente de 3 velocidades
    disparaba el techo del CD y dejaba una de las curvas aplastada contra el eje
    (ocupaba ~14% del panel = 'no aparece')."""
    acc = {c: [] for c, _, _ in PANELS}
    for d in disenos:
        v, _ = _vel_de(d)
        al = _alphas_de(v)
        X = _features(_shape_vec(d["shape_params"]), al, v)
        for col, _, absval in PANELS:
            p = {"CL": _CL, "CD": _CD, "LD": _LD}[col].predict(X)
            acc[col].append(np.abs(p) if absval else p)
    out = {}
    for col, vals in acc.items():
        a = np.concatenate(vals)
        lo, hi = float(a.min()), float(a.max())
        # CD puede abarcar un factor grande entre perfiles de cuerdas distintas:
        # en ese caso, escala LOG para que ambas curvas se lean (si no, una se aplasta).
        if col == "CD" and lo > 0 and hi / lo > 3.0:
            out[col] = {"log": True,
                        "range": [float(np.log10(lo * 0.9)), float(np.log10(hi * 1.1))]}
        else:
            pad = (hi - lo) * margen or 0.05
            out[col] = {"log": False, "range": [lo - pad, hi + pad]}
    return out


def fig_comparar_curvas(disenos, vel=None):
    """disenos: [{name, shape_params, banda_lo, banda_hi, velocidad_kmh}].

    Cada diseno se dibuja A SU VELOCIDAD DE GUARDADO, no a una comun. Antes se forzaban
    todos a 180: un perfil disenado para 250 se comparaba donde no es optimo, y la vista
    contradecia a la fila 'Design speed' de la tabla. El precio es que parte de la
    diferencia entre curvas viene de la velocidad y no de la forma; se avisa en el
    titulo y en la nota de la vista. `vel` se ignora (se acepta por compatibilidad)."""
    fig = make_subplots(rows=1, cols=3, horizontal_spacing=0.07,
                        subplot_titles=[p[1] for p in PANELS])

    for ci, (col, ytit, absval) in enumerate(PANELS, start=1):
        for i, d in enumerate(disenos):
            c = COMPARE_COLORS[i % len(COMPARE_COLORS)]
            v, _asum = _vel_de(d)
            alphas = _alphas_de(v)
            xabs = np.abs(alphas)
            shape = _shape_vec(d["shape_params"])
            X = _features(shape, alphas, v)
            pred = {"CL": _CL, "CD": _CD, "LD": _LD}[col].predict(X)
            y = np.abs(pred) if absval else pred
            nombre = _etiqueta(d)
            fig.add_trace(go.Scatter(
                x=xabs, y=y, mode="lines+markers", name=nombre,
                legendgroup=nombre, showlegend=(ci == 1),
                line=dict(color=c, width=2.2),
                marker=dict(color=c, size=5, line=dict(color=PALETA["fondo"], width=1)),
                hovertemplate=(f"<b>{d['name']}</b> ({v:g} km/h)<br>|α|: %{{x}}&deg;<br>"
                               f"{ytit}: %{{y:.3f}}<extra></extra>")),
                row=1, col=ci)
        # bandas objetivo de cada diseno (solo en el panel |L/D|, sutiles)
        if col == "LD":
            for i, d in enumerate(disenos):
                lo, hi = d.get("banda_lo"), d.get("banda_hi")
                if lo is None or hi is None or lo == hi:
                    continue
                r, g, b = _hex_rgb(COMPARE_COLORS[i % len(COMPARE_COLORS)])
                fig.add_vrect(x0=lo, x1=hi, row=1, col=ci, layer="below",
                              fillcolor=f"rgba({r},{g},{b},0.10)", line_width=0)

    fig.update_xaxes(title_text="Angle of attack |α| (°)", color=PALETA["eje"],
                     gridcolor=PALETA["rejilla"], zeroline=False, linecolor=PALETA["eje"],
                     ticks="outside", tickcolor=PALETA["eje"],
                     title_font=dict(color=PALETA["texto"], size=12))
    rangos = _rangos_comunes(disenos)
    for ci, (col, ytit, _) in enumerate(PANELS, start=1):
        rg = rangos[col]
        fig.update_yaxes(title_text=(ytit + " (log)" if rg["log"] else ytit),
                         type=("log" if rg["log"] else "linear"), range=rg["range"],
                         color=PALETA["eje"], gridcolor=PALETA["rejilla"],
                         zeroline=False, linecolor=PALETA["eje"], ticks="outside",
                         tickcolor=PALETA["eje"], title_font=dict(color=PALETA["texto"], size=12),
                         row=1, col=ci)
    fig.update_layout(
        title=dict(text=("<b>Overlaid polars</b> <span style='font-size:12px;color:"
                         + PALETA["eje"] + "'>— " + _subtitulo_vel(disenos)
                         + " · shaded = each design's target band</span>"),
                   x=0.5, xanchor="center", font=dict(size=15, color=PALETA["texto"]),
                   y=0.97, yanchor="top"),
        legend=dict(orientation="h", x=0.5, xanchor="center", y=1.13, yanchor="bottom",
                    bgcolor="rgba(0,0,0,0)", font=dict(color=PALETA["texto"], size=12)),
        plot_bgcolor=PALETA["fondo"], paper_bgcolor=PALETA["fondo_papel"],
        width=1080, height=455, font=dict(family=FONT_FAMILY, color=PALETA["texto"], size=12),
        margin=dict(l=55, r=25, t=140, b=52))
    for ann in fig.layout.annotations:
        ann.font.color = PALETA["texto"]; ann.font.size = 13
    return fig


def cl_medio_banda(disenos, vel=None):
    """|CL| medio en la banda objetivo de cada diseno, A SU PROPIA VELOCIDAD — misma
    convencion que el L/D, el CD y la sigma que ya vienen guardados (media sobre el
    rango, a la velocidad de diseno).

    Antes se calculaba a 180 fija para todas las columnas, asi que la tabla mezclaba
    dos marcos: L/D, CD y sigma a la velocidad de cada diseno y el CL a 180. Alineado
    para que TODA la vista Compare siga el mismo criterio: cada perfil a su velocidad.
    `vel` se ignora (se acepta por compatibilidad)."""
    out = []
    for d in disenos:
        lo, hi = d.get("banda_lo"), d.get("banda_hi")
        if lo is None or hi is None:
            out.append(None); continue
        v, _asum = _vel_de(d)
        a = -np.arange(float(lo), float(hi) + 1e-6, 1.0)
        if len(a) == 0:
            a = np.array([-float(lo)])
        X = _features(_shape_vec(d["shape_params"]), a, v)
        out.append(float(np.mean(np.abs(_CL.predict(X)))))
    return out


def fig_comparar_siluetas(disenos):
    """Contornos superpuestos a ESCALA REAL (mm), alineados por el borde de ataque
    (x=0) y con aspecto 1:1: asi una cuerda de 450 mm se VE mayor que una de 250 mm
    (normalizar por cuerda las igualaba y ocultaba la diferencia de tamano)."""
    fig = go.Figure()
    for i, d in enumerate(disenos):
        c = COMPARE_COLORS[i % len(COMPARE_COLORS)]
        C, _ = FIX.generate_contour({k: float(d["shape_params"][k]) for k in SHAPE})
        ch = float(d["shape_params"]["chord_length_mm"])
        xs = np.append(C[:, 0], C[0, 0]) * ch          # normalizado -> mm reales
        ys = np.append(C[:, 1], C[0, 1]) * ch
        r, g, b = _hex_rgb(c)
        fig.add_trace(go.Scatter(
            x=xs, y=ys, mode="lines", name=f"{d['name']} · chord {ch:.0f} mm",
            line=dict(color=c, width=2), fill="toself",
            fillcolor=f"rgba({r},{g},{b},0.07)",
            hovertemplate=(f"<b>{d['name']}</b><br>x: %{{x:.1f}} mm<br>"
                           "y: %{y:.1f} mm<extra></extra>")))
    fig.update_layout(
        title=dict(text=("<b>Overlaid shapes — real scale (mm)</b> "
                         "<span style='font-size:12px;color:" + PALETA["eje"]
                         + "'>— aligned at the leading edge, 1:1 aspect</span>"),
                   x=0.5, xanchor="center", font=dict(size=15, color=PALETA["texto"]),
                   y=0.95, yanchor="top"),
        xaxis=dict(title="x (mm)", color=PALETA["eje"], gridcolor=PALETA["rejilla"],
                   zeroline=False, linecolor=PALETA["eje"], ticks="outside",
                   tickcolor=PALETA["eje"], title_font=dict(color=PALETA["texto"], size=12),
                   constrain="domain"),
        yaxis=dict(title="y (mm)", color=PALETA["eje"], gridcolor=PALETA["rejilla"],
                   zeroline=False, linecolor=PALETA["eje"], ticks="outside",
                   tickcolor=PALETA["eje"], title_font=dict(color=PALETA["texto"], size=12),
                   scaleanchor="x", scaleratio=1),
        legend=dict(orientation="h", x=0.5, xanchor="center", y=1.0, yanchor="bottom",
                    bgcolor="rgba(0,0,0,0)", font=dict(color=PALETA["texto"], size=12)),
        plot_bgcolor=PALETA["fondo"], paper_bgcolor=PALETA["fondo_papel"],
        width=1080, height=380, font=dict(family=FONT_FAMILY, color=PALETA["texto"], size=12),
        margin=dict(l=55, r=25, t=95, b=50))
    return fig


def _hex_rgb(h):
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


# =========================================================
# Cp SUPERPUESTO (cada perfil en SU angulo recomendado)
# =========================================================
_CP_CMP_CACHE = {}          # (hash_perfil, vel, alpha) -> Nx3 (x,y,Cp)  |  None si no converge


def _cp_de_diseno(sp, alpha, vel=290):
    """Corre XFOIL sobre el .dat del perfil (reutiliza la MISMA ruta que Results:
    optimo_geom.gen_dat_optimo + graficas_cp._xfoil_cp) y cachea por (perfil, vel, alpha)."""
    import os, tempfile
    from optimo_geom import gen_dat_optimo, hash_params
    from graficas_cp import _xfoil_cp, _reynolds
    h = hash_params(sp)
    # _xfoil_cp marcha con range() en pasos de -2 -> necesita alpha ENTERO. El angulo
    # recomendado siempre es entero (la banda se recorre en pasos de 1 grado), asi que
    # int() no pierde nada: se respeta el angulo recomendado, sin redondear a par.
    alpha = int(round(float(alpha)))
    key = (h, int(vel), alpha)
    if key in _CP_CMP_CACHE:
        return _CP_CMP_CACHE[key]
    dat, _ = gen_dat_optimo(sp)                       # .dat con TE fabricable (cacheado)
    chord = float(sp["chord_length_mm"])
    work = os.path.join(tempfile.gettempdir(), "cp_cmp", h)
    cp3, _clcd = _xfoil_cp(dat, _reynolds(chord, vel), alpha, work)
    out = cp3 if (cp3 is not None and len(cp3) >= 20) else None
    _CP_CMP_CACHE[key] = out
    return out


def fig_comparar_cp(disenos, vel=None):
    """Cp superpuesto de 2-3 perfiles, cada uno en SU angulo recomendado Y A SU
    VELOCIDAD DE GUARDADO (antes: 290 km/h comun para todos).
    Eje X en x/c (adimensional, a proposito: el Cp se compara en cuerda normalizada,
    al contrario que las siluetas). Eje Cp INVERTIDO (convencion aeronautica).
    El cache de _cp_de_diseno ya lleva la velocidad en la clave, asi que no hay que
    tocarlo: cada (perfil, velocidad, angulo) se calcula una sola vez.
    `vel` se ignora (se acepta por compatibilidad). Devuelve (figura, lista_de_fallos)."""
    from graficas_cp import _split_arc
    fig = go.Figure()
    fallos, dibujados = [], 0

    for i, d in enumerate(disenos):
        c = COMPARE_COLORS[i % len(COMPARE_COLORS)]
        a_rec = abs(float(d.get("alpha_rec") or 0.0))
        v, asumida = _vel_de(d)
        cp3 = _cp_de_diseno(d["shape_params"], -a_rec, v)
        if cp3 is None:
            fallos.append({"name": d["name"], "alpha": a_rec, "vel": v})
            continue
        A, B = _split_arc(cp3)
        suc, pre = (A, B) if np.nanmean(A[:, 2]) <= np.nanmean(B[:, 2]) else (B, A)
        etiqueta = f"{d['name']} · α {a_rec:g}° · {v:g} km/h" + (" †" if asumida else "")
        for j, arr in enumerate((suc, pre)):
            o = np.argsort(arr[:, 0])
            fig.add_trace(go.Scatter(
                x=arr[o, 0], y=arr[o, 2], mode="lines",
                name=etiqueta, legendgroup=etiqueta, showlegend=(j == 0),
                line=dict(color=c, width=2, dash=("solid" if j == 0 else "dot")),
                hovertemplate=(f"<b>{etiqueta}</b><br>"
                               + ("suction" if j == 0 else "pressure")
                               + "<br>x/c: %{x:.3f}<br>Cp: %{y:.3f}<extra></extra>")))
        dibujados += 1

    fig.add_hline(y=0, line=dict(color=PALETA["eje"], width=1, dash="dot"))
    if fallos:
        aviso = " · ".join(f"Cp unavailable for {f['name']} — did not converge at "
                           f"α {f['alpha']:g}° / {f['vel']:g} km/h" for f in fallos)
        fig.add_annotation(xref="paper", yref="paper", x=0.5, y=-0.20, xanchor="center",
                           showarrow=False, font=dict(size=12, color=PALETA["k0"]),
                           text=aviso)

    fig.update_layout(
        title=dict(text=("<b>Overlaid pressure distributions (Cp)</b> "
                         "<span style='font-size:12px;color:" + PALETA["eje"]
                         + "'>— each at its recommended angle · "
                         + _subtitulo_vel(disenos, mismo_angulo=False, breve=True)
                         + "<br>solid = suction, dotted = pressure</span>"),
                   x=0.5, xanchor="center", font=dict(size=15, color=PALETA["texto"]),
                   y=0.97, yanchor="top"),
        xaxis=dict(title="x / c", range=[0, 1], color=PALETA["eje"],
                   gridcolor=PALETA["rejilla"], zeroline=False, linecolor=PALETA["eje"],
                   ticks="outside", tickcolor=PALETA["eje"],
                   title_font=dict(color=PALETA["texto"], size=12)),
        yaxis=dict(title="Cp", autorange="reversed", color=PALETA["eje"],
                   gridcolor=PALETA["rejilla"], zeroline=False, linecolor=PALETA["eje"],
                   ticks="outside", tickcolor=PALETA["eje"],
                   title_font=dict(color=PALETA["texto"], size=12)),
        legend=dict(orientation="h", x=0.5, xanchor="center", y=1.06, yanchor="bottom",
                    bgcolor="rgba(0,0,0,0)", font=dict(color=PALETA["texto"], size=12)),
        plot_bgcolor=PALETA["fondo"], paper_bgcolor=PALETA["fondo_papel"],
        width=1080, height=520, font=dict(family=FONT_FAMILY, color=PALETA["texto"], size=12),
        margin=dict(l=60, r=25, t=120, b=(90 if fallos else 55)))
    return fig, fallos
