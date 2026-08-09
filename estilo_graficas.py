"""
Estilo compartido de TODAS las graficas del proyecto (Plotly).
IDENTIDAD VISUAL: tema oscuro tipo telemetria motorsport.
Paleta fija + layout base, para que dashboard Flask y PNGs sean identicos.

Uso:
    import plotly.graph_objects as go
    from estilo_graficas import PALETA, VEL_COLOR, aplica_estilo
    fig = go.Figure(...)
    aplica_estilo(fig, title="...", xaxis_title="...", yaxis_title="...")
"""

# ---- PALETA FIJA DEL PROYECTO (tema oscuro) ----
PALETA = {
    "k0": "#e8a13a",         # ambar  - optimizacion ingenua (naive)
    "k2": "#1b9e8a",         # teal   - penalizada por incertidumbre (penalised)
    "texto": "#f0f3f6",      # texto principal (claro sobre oscuro)
    "eje": "#7d8896",        # ejes / ticks
    "rejilla": "#232a33",    # gridlines (sutil, poco contraste)
    "acento": "#1b9e8a",     # acento UI (teal)
    "fondo": "#0d1117",      # fondo del PLOT (gris muy oscuro, no negro)
    "fondo_papel": "#161b22",# fondo del PAPEL / pagina
}

# Velocidades: rampa aqua->teal->verde profundo (graficas polares / barridos).
# Direccion conservada (mas velocidad = mas oscuro) pero con el TRIPLE de separacion
# perceptual que la rampa original (#7fd4c4/#3aa892/#1b7a68), donde 180 y 290 eran casi
# indistinguibles. Los tres pasos separan ~21-28 puntos de L* (antes ~17) y mantienen
# >=3:1 de contraste contra el fondo #0d1117, asi que ninguno se pierde en el oscuro.
# Se mueve hue y luminosidad a la vez (aqua -> teal -> verde) para que se distingan
# tambien en escala de grises y para no invadir el ambar de PALETA["k0"].
VEL_COLOR = {
    110: "#a9f2e6",          # aqua claro
    180: "#2ec4a6",          # teal del proyecto (familia de k2/acento), el mas vivo
    290: "#0d7550",          # verde-teal profundo
}

# COMPARACION de disenos guardados: hasta 3 series bien diferenciadas entre si
# (teal / ambar / violeta), legibles sobre el fondo oscuro.
COMPARE_COLORS = ["#1b9e8a", "#e8a13a", "#a06cd5"]

FONT_FAMILY = "Segoe UI, Helvetica, Arial, sans-serif"


def caja_bg(alpha=0.85):
    """Fondo semi-transparente para cajas de anotacion sobre el tema oscuro."""
    return f"rgba(22,27,34,{alpha})"   # = fondo_papel translucido


def aplica_estilo(fig, title=None, subtitle=None, xaxis_title=None, yaxis_title=None,
                  width=820, height=760, legend_top=True):
    """Aplica el layout base OSCURO del proyecto a una figura Plotly (in-place).

    - Fondo oscuro (plot #0d1117 / papel #161b22), sin gradientes ni sombras.
    - Fuente, colores de texto/ejes/rejilla de la paleta.
    - legend_top=True: leyenda horizontal ARRIBA, fuera del area de plot.
    """
    p = PALETA
    title_html = None
    if title:
        title_html = f"<b>{title}</b>"
        if subtitle:
            title_html += (f"<br><span style='font-size:13px;color:{p['eje']}'>"
                           f"{subtitle}</span>")

    axis_common = dict(
        color=p["eje"], gridcolor=p["rejilla"], zeroline=False,
        linecolor=p["eje"], ticks="outside", tickcolor=p["eje"],
        title_font=dict(color=p["texto"], size=14),
    )

    fig.update_layout(
        title=dict(text=title_html, x=0.5, xanchor="center",
                   font=dict(size=19, color=p["texto"]), y=0.95, yanchor="top") if title_html else None,
        xaxis=dict(title=xaxis_title, **axis_common),
        yaxis=dict(title=yaxis_title, **axis_common),
        plot_bgcolor=p["fondo"], paper_bgcolor=p["fondo_papel"],
        width=width, height=height,
        font=dict(family=FONT_FAMILY, color=p["texto"], size=13),
        margin=dict(l=80, r=40, t=135 if legend_top else 95, b=70),
    )

    if legend_top:
        fig.update_layout(legend=dict(
            orientation="h", x=0.5, xanchor="center", y=1.0, yanchor="bottom",
            bgcolor="rgba(0,0,0,0)", borderwidth=0,
            font=dict(color=p["texto"], size=12.5)))
    return fig
