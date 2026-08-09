import sys
import os
import re
import math
import matplotlib.pyplot as plt


# =========================================================
# CONFIG
# =========================================================

from rutas import BASE as DEFAULT_WORK_DIR   # carpeta del proyecto
DEFAULT_POLAR_FILE = os.path.join(DEFAULT_WORK_DIR, "polar_v4_auto.txt")


# =========================================================
# LECTURA DE POLAR XFOIL
# =========================================================

def read_xfoil_polar(polar_file):
    if not os.path.isfile(polar_file):
        raise FileNotFoundError(f"No existe el archivo polar: {polar_file}")

    rows = []

    with open(polar_file, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    for line in lines:
        s = line.strip()

        if not s:
            continue

        # Solo líneas que empiezan por número, + o -
        if not re.match(r"^[\+\-]?\d", s):
            continue

        parts = s.split()

        # Formato esperado:
        # alpha CL CD CDp CM Top_Xtr Bot_Xtr
        if len(parts) < 7:
            continue

        try:
            row = {
                "alpha": float(parts[0]),
                "CL": float(parts[1]),
                "CD": float(parts[2]),
                "CDp": float(parts[3]),
                "CM": float(parts[4]),
                "Top_Xtr": float(parts[5]),
                "Bot_Xtr": float(parts[6]),
            }
            rows.append(row)
        except ValueError:
            continue

    if not rows:
        raise ValueError("No se han encontrado datos numéricos válidos en la polar.")

    return rows


def get_column(rows, key):
    return [row[key] for row in rows]


# =========================================================
# PLOTS
# =========================================================

def save_plot(x, y, xlabel, ylabel, title, output_path):
    plt.figure(figsize=(8, 5))
    plt.plot(x, y, marker="o")
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.title(title)
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()

    print(f"[OK] Grafica guardada: {output_path}")


def generate_plots(rows, output_dir):
    alpha = get_column(rows, "alpha")
    cl = get_column(rows, "CL")
    cd = get_column(rows, "CD")
    cm = get_column(rows, "CM")

    # CL/CD seguro, con el mismo número de puntos que alpha
    ld = []
    for row in rows:
        if abs(row["CD"]) < 1e-12:
            ld.append(0.0)
        else:
            ld.append(row["CL"] / row["CD"])

    out_cl_alpha = os.path.join(output_dir, "polar_cl_alpha.png")
    out_cd_alpha = os.path.join(output_dir, "polar_cd_alpha.png")
    out_cl_cd = os.path.join(output_dir, "polar_cl_cd.png")
    out_ld_alpha = os.path.join(output_dir, "polar_ld_alpha.png")
    out_cm_alpha = os.path.join(output_dir, "polar_cm_alpha.png")

    save_plot(
        alpha,
        cl,
        "Alpha (deg)",
        "CL",
        "CL vs Alpha",
        out_cl_alpha
    )

    save_plot(
        alpha,
        cd,
        "Alpha (deg)",
        "CD",
        "CD vs Alpha",
        out_cd_alpha
    )

    save_plot(
        cd,
        cl,
        "CD",
        "CL",
        "Polar aerodinamica: CL vs CD",
        out_cl_cd
    )

    save_plot(
        alpha,
        ld,
        "Alpha (deg)",
        "CL/CD",
        "CL/CD vs Alpha",
        out_ld_alpha
    )

    save_plot(
        alpha,
        cm,
        "Alpha (deg)",
        "CM",
        "CM vs Alpha",
        out_cm_alpha
    )


# =========================================================
# MAIN
# =========================================================

def main():
    if len(sys.argv) > 1:
        polar_file = sys.argv[1]
    else:
        polar_file = DEFAULT_POLAR_FILE

    polar_file = os.path.abspath(polar_file)
    output_dir = os.path.dirname(polar_file)

    print(f"[INFO] Leyendo polar: {polar_file}")

    rows = read_xfoil_polar(polar_file)

    print(f"[OK] Datos de polar leidos: {len(rows)} puntos")

    generate_plots(rows, output_dir)

    print("[OK] Graficas de polar generadas correctamente.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"[ERROR] No se pudieron generar las graficas de polar: {e}")
        sys.exit(1)