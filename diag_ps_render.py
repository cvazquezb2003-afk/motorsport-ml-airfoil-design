"""
(1) Renderiza el plot.ps NATIVO de XFOIL dibujando SUS PROPIOS trazos vectoriales
    (macros M/L del PostScript). No reconstruye desde el Cp: rasteriza el vector
    que emitio XFOIL.
(2) Compara, a partir del MISMO cp.txt crudo (x,y,Cp), dos formas de separar
    caras: por ORDEN DE ARCO (correcto, como XFOIL) vs por MEDIANA DE Y + orden
    por x (lo que hace plot_cp.split_cp_branches) -> muestra de donde sale el
    zigzag.
Solo lectura, no toca el pipeline.
"""
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import plot_cp as pc

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "eda_outputs")
WORK = os.path.join(os.environ.get("TEMP", BASE), "xfoil_native")
PS = os.path.join(WORK, "plot.ps")
CP = os.path.join(WORK, "cp.txt")


# ---------- (1) render del PostScript nativo ----------
def parse_ps_polylines(ps_path):
    with open(ps_path, encoding="latin-1") as f:
        txt = f.read()
    body = txt.split("setrgbcolor pop pop pop } bind def", 1)[-1]
    tokens = body.replace("\n", " ").split()
    polys = []            # lista de (color, np.array Nx2)
    pending = []
    cur = []
    color = (0, 0, 0)

    def flush():
        nonlocal cur
        if len(cur) >= 2:
            polys.append((color, np.array(cur, float)))
        cur = []

    for t in tokens:
        try:
            pending.append(float(t))
            continue
        except ValueError:
            pass
        if t == "M":
            flush()
            if len(pending) >= 2:
                cur = [(pending[-2] / 10.0, pending[-1] / 10.0)]
        elif t == "L":
            if len(pending) >= 2:
                cur.append((pending[-2] / 10.0, pending[-1] / 10.0))
        elif t == "CO":
            flush()
            if len(pending) >= 3:
                r, g, b = pending[-3], pending[-2], pending[-1]
                color = (r / 255.0, g / 255.0, b / 255.0)
        elif t == "SG":
            flush()
            if pending:
                ggg = pending[-1]
                color = (ggg, ggg, ggg)
        elif t in ("stroke", "CPSM", "CFS", "NP"):
            flush()
        pending = []
    flush()
    return polys


def render_ps():
    polys = parse_ps_polylines(PS)
    fig, ax = plt.subplots(figsize=(12, 8.5), facecolor="white")
    for color, pts in polys:
        ax.plot(pts[:, 0], pts[:, 1], color=color, lw=0.7)
    ax.set_aspect("equal"); ax.axis("off")
    ax.set_title("XFOIL NATIVO (plot.ps rasterizado: sus propios trazos vectoriales)",
                 fontsize=11)
    out = os.path.join(OUT, "xfoil_native_plotps.png")
    fig.savefig(out, dpi=130, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    print(f"[OK] render PS nativo: {out}  ({len(polys)} polilineas)")


# ---------- (2) arc-order vs y-median desde el cp.txt crudo ----------
def load_cp():
    rows = []
    with open(CP, encoding="utf-8", errors="ignore") as f:
        for ln in f:
            p = ln.replace(",", " ").split()
            if len(p) >= 3:
                try:
                    rows.append([float(p[0]), float(p[1]), float(p[2])])
                except ValueError:
                    pass
    return np.array(rows)


def compare_splits():
    a = load_cp()                      # x, y, Cp en orden de fichero
    # ARC-ORDER: cortar en el LE (min x) segun el orden del archivo (como XFOIL)
    ile = int(np.argmin(a[:, 0]))
    s1 = a[:ile + 1]
    s2 = a[ile:]
    # Y-MEDIAN: replicar plot_cp.split_cp_branches sobre el array [x,y,Cp]
    up, lo = pc.split_cp_branches(a.copy())

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6), facecolor="white")
    for s, c in ((s1, "#1f77b4"), (s2, "#d62728")):
        ax1.plot(s[:, 0], s[:, 2], "-", color=c, lw=1.2)      # Cp vs x, ORDEN de arco
    ax1.axvspan(0.65, 1.0, color="#ffd9d9")
    ax1.set_title("Correcto: caras separadas por ORDEN DE ARCO (como XFOIL)\n-> SUAVE")
    ax1.invert_yaxis(); ax1.set_xlabel("x/c"); ax1.set_ylabel("Cp"); ax1.grid(alpha=0.3)

    ax2.plot(up[:, 0], up[:, 1], "-", color="#1f77b4", lw=1.2)
    ax2.plot(lo[:, 0], lo[:, 1], "-", color="#d62728", lw=1.2)
    ax2.axvspan(0.65, 1.0, color="#ffd9d9")
    ax2.set_title("plot_cp: separacion por MEDIANA DE Y + orden por x\n-> ZIGZAG (artefacto)")
    ax2.invert_yaxis(); ax2.set_xlabel("x/c"); ax2.set_ylabel("Cp"); ax2.grid(alpha=0.3)

    out = os.path.join(OUT, "cp_arcorder_vs_ymedian.png")
    fig.tight_layout(); fig.savefig(out, dpi=130, facecolor="white"); plt.close(fig)
    print(f"[OK] comparacion arc-order vs y-median: {out}")


render_ps()
compare_splits()
