"""
Dibuja la FORMA de un perfil alar. Base de la capa visual.

Fuentes admitidas:
  --dat  ruta.dat            un .dat de XFOIL (normalizado x/c)
  --run-id RUN_ID            un perfil del dataset (lee dataset_runs/{run_id}/airfoil_v4.dat
                             y saca la cuerda del CSV automaticamente)

El .dat esta NORMALIZADO por la cuerda. Si se conoce la cuerda (via --run-id o
--chord), se dibuja en mm reales; si no, en unidades de cuerda (x/c).
Ejes a escala 1:1 SIEMPRE (axis equal) para que el perfil no salga deformado.

Ejemplos:
    python plot_perfil.py --run-id 0001_20260625_182322
    python plot_perfil.py --dat airfoil_v4.dat --chord 450 --titulo "Inversa caso 4"
    python plot_perfil.py --run-id XXXX --out mi_perfil.png --dpi 300
"""
import os
import sys
import argparse
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BASE = os.path.dirname(os.path.abspath(__file__))
DATASET_CSV = os.path.join(BASE, "airfoil_dataset.csv")
DATASET_RUNS = os.path.join(BASE, "dataset_runs")


def leer_dat(path):
    """Lee un .dat de XFOIL: 1a linea = nombre, resto = pares x y."""
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        lineas = f.readlines()
    nombre = lineas[0].strip()
    pts = []
    for ln in lineas[1:]:
        p = ln.split()
        if len(p) < 2:
            continue
        try:
            pts.append((float(p[0]), float(p[1])))
        except ValueError:
            continue
    if not pts:
        raise ValueError(f"No hay puntos validos en {path}")
    xy = np.array(pts)
    return nombre, xy[:, 0], xy[:, 1]


def cuerda_de_run_id(run_id):
    """Saca chord_length_mm del dataset para un run_id."""
    if not os.path.exists(DATASET_CSV):
        return None
    df = pd.read_csv(DATASET_CSV)
    fila = df[df.run_id == run_id]
    if fila.empty:
        return None
    return float(fila.iloc[0]["chord_length_mm"])


def dibujar(x, y, titulo, cuerda_mm=None, out=None, dpi=200):
    """Contorno con proporciones reales, estilo limpio."""
    en_mm = cuerda_mm is not None
    if en_mm:
        x, y = x * cuerda_mm, y * cuerda_mm
        unidad = "mm"
    else:
        unidad = "x/c"

    fig, ax = plt.subplots(figsize=(11, 4.2))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    # contorno cerrado (repetimos el primer punto para cerrar el trazo)
    xs, ys = np.append(x, x[0]), np.append(y, y[0])
    ax.plot(xs, ys, color="#1a1a1a", linewidth=1.6, solid_joinstyle="round")
    ax.fill(xs, ys, color="#1a1a1a", alpha=0.055, zorder=0)

    # 1:1 REAL: misma escala en ambos ejes -> el perfil no se deforma
    ax.set_aspect("equal", adjustable="box")

    # estilo limpio
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    for lado in ("left", "bottom"):
        ax.spines[lado].set_color("#999999")
        ax.spines[lado].set_linewidth(0.8)
    ax.grid(True, linewidth=0.4, alpha=0.25, color="#888888")
    ax.set_axisbelow(True)
    ax.tick_params(colors="#444444", labelsize=9)

    if en_mm:
        ax.set_xlabel("x  [mm]", fontsize=10, color="#333333")
        ax.set_ylabel("y  [mm]", fontsize=10, color="#333333")
    else:
        ax.set_xlabel("x / c  [adimensional]", fontsize=10, color="#333333")
        ax.set_ylabel("y / c  [adimensional]", fontsize=10, color="#333333")

    ax.set_title(titulo, fontsize=12, color="#111111", pad=12)

    # anotacion de la cuerda
    if en_mm:
        nota = f"cuerda = {cuerda_mm:.2f} mm"
    else:
        nota = "geometria normalizada (cuerda desconocida)"
    ax.annotate(nota, xy=(0.995, 0.04), xycoords="axes fraction",
                ha="right", va="bottom", fontsize=9, color="#555555")

    fig.tight_layout()
    out = out or os.path.join(BASE, "perfil.png")
    fig.savefig(out, dpi=dpi, facecolor="white")
    plt.close(fig)
    return out


def main():
    ap = argparse.ArgumentParser(description="Dibuja la forma de un perfil alar.")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--dat", type=str, help="Ruta a un .dat de XFOIL.")
    src.add_argument("--run-id", type=str, help="run_id del dataset (usa dataset_runs/).")
    ap.add_argument("--chord", type=float, default=None,
                    help="Cuerda en mm (para escalar un .dat suelto). Con --run-id se "
                         "obtiene sola del CSV.")
    ap.add_argument("--titulo", type=str, default=None, help="Titulo del grafico.")
    ap.add_argument("--out", type=str, default=None, help="PNG de salida.")
    ap.add_argument("--dpi", type=int, default=200, help="DPI (por defecto 200).")
    args = ap.parse_args()

    if args.run_id:
        path = os.path.join(DATASET_RUNS, args.run_id, "airfoil_v4.dat")
        if not os.path.exists(path):
            print(f"[ERROR] No existe {path}")
            return 1
        cuerda = args.chord or cuerda_de_run_id(args.run_id)
        titulo = args.titulo or f"Perfil {args.run_id}"
        out = args.out or os.path.join(BASE, f"perfil_{args.run_id}.png")
    else:
        path = args.dat
        if not os.path.exists(path):
            print(f"[ERROR] No existe {path}")
            return 1
        cuerda = args.chord
        titulo = args.titulo or f"Perfil  ({os.path.basename(path)})"
        out = args.out or os.path.join(BASE, "perfil.png")

    nombre, x, y = leer_dat(path)
    print(f"[INFO] {path}  |  {len(x)} puntos  |  cabecera: {nombre}")
    if cuerda:
        print(f"[INFO] cuerda = {cuerda:.2f} mm -> se dibuja en mm reales")
    else:
        print("[INFO] sin cuerda conocida -> se dibuja normalizado (x/c)")

    png = dibujar(x, y, titulo, cuerda_mm=cuerda, out=out, dpi=args.dpi)
    print(f"[OK] guardado: {png}  (dpi={args.dpi})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
