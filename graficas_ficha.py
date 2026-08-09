"""
Project graph 5: PROFILE CARD COMPOSER — one deliverable per run_id joining
shape + polars + Cp. Reuses fig_forma / fig_polares / fig_cp.

  HTML: the three interactive figures stacked in a styled page.
  PNG:  the three figures rendered at a common width and stacked vertically,
        with a title band (via Pillow).

Reusable:  from graficas_ficha import ficha ; ficha(run_id, vel, alpha)
Direct:    python graficas_ficha.py -> graficas/ficha_0014.{html,png}
"""
import os
import pandas as pd
from PIL import Image, ImageDraw, ImageFont
from estilo_graficas import PALETA
from graficas_forma import fig_forma
from graficas_polares import fig_polares
from graficas_cp import fig_cp, condicion_optima

BASE = os.path.dirname(os.path.abspath(__file__))
OUTDIR = os.path.join(BASE, "graficas")
RUN_ID_DEFAULT = "0014_20260711_193032"
W = 1180  # ancho comun de la lamina


def _figs(run_id, vel, alpha):
    df = pd.read_csv(os.path.join(BASE, "airfoil_dataset.csv"))
    chord = float(df[df.run_id == run_id].chord_length_mm.iloc[0])
    return {
        "shape": fig_forma(run_id, df=df),
        "polars": fig_polares(run_id, df=df),
        "cp": fig_cp(run_id, vel, alpha, df=df),
    }, chord


def _html(figs, run_id, chord, vel, alpha):
    short = run_id.split("_")[0]
    p = PALETA
    parts = [f"""<div style="max-width:1200px;margin:0 auto;font-family:Segoe UI,Arial,sans-serif;
        color:{p['texto']};background:{p['fondo_papel']};padding:18px">
      <div style="border-bottom:2px solid {p['rejilla']};padding-bottom:10px;margin-bottom:6px">
        <div style="font-size:24px;font-weight:700">Profile card — {short}</div>
        <div style="font-size:14px;color:{p['eje']}">run_id {run_id} &nbsp;·&nbsp; chord {chord:.0f} mm
        &nbsp;·&nbsp; optimal Cp at {vel} km/h, |α| = {abs(alpha)}°</div>
      </div>"""]
    for i, key in enumerate(("shape", "polars", "cp")):
        inc = "cdn" if i == 0 else False
        parts.append(figs[key].to_html(full_html=False, include_plotlyjs=inc,
                                       config={"displayModeBar": False}))
    parts.append("</div>")
    return "\n".join(parts)


def _png(figs, run_id, chord, vel, alpha, out):
    tmp = []
    for key in ("shape", "polars", "cp"):
        f = figs[key]
        f.update_layout(width=W)
        pth = os.path.join(OUTDIR, f"_tmp_{key}.png")
        f.write_image(pth, scale=2)
        tmp.append(pth)
    imgs = [Image.open(t).convert("RGB") for t in tmp]
    band = 150
    total_h = band + sum(im.height for im in imgs)
    width = max(im.width for im in imgs)
    canvas = Image.new("RGB", (width, total_h), PALETA["fondo_papel"])
    d = ImageDraw.Draw(canvas)
    try:
        f_big = ImageFont.truetype("segoeui.ttf", 46)
        f_sm = ImageFont.truetype("segoeui.ttf", 30)
    except Exception:
        f_big = ImageFont.load_default(); f_sm = ImageFont.load_default()
    short = run_id.split("_")[0]
    d.text((40, 34), f"Profile card — {short}", fill=PALETA["texto"], font=f_big)
    d.text((40, 92), f"run_id {run_id}  ·  chord {chord:.0f} mm  ·  "
                     f"optimal Cp at {vel} km/h, |a| = {abs(alpha)} deg",
           fill=PALETA["eje"], font=f_sm)
    y = band
    for im in imgs:
        canvas.paste(im, ((width - im.width) // 2, y)); y += im.height
    canvas.save(out)
    for t in tmp:
        os.remove(t)


def ficha(run_id=RUN_ID_DEFAULT, vel=None, alpha=None):
    os.makedirs(OUTDIR, exist_ok=True)
    if vel is None or alpha is None:      # auto: condicion de maximo |L/D| del perfil
        vel, alpha = condicion_optima(run_id)
    figs, chord = _figs(run_id, vel, alpha)
    short = run_id.split("_")[0]
    html_path = os.path.join(OUTDIR, f"ficha_{short}.html")
    png_path = os.path.join(OUTDIR, f"ficha_{short}.png")
    open(html_path, "w", encoding="utf-8").write(_html(figs, run_id, chord, vel, alpha))
    print(f"[OK] HTML -> graficas/ficha_{short}.html")
    try:
        _png(figs, run_id, chord, vel, alpha, png_path)
        print(f"[OK] PNG  -> graficas/ficha_{short}.png")
    except Exception as e:
        print(f"[AVISO] PNG: {e}")


if __name__ == "__main__":
    ficha()
