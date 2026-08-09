# -*- coding: utf-8 -*-
"""
plot_cp.py

Genera gráficas Cp estilo XFOIL a partir de:
- airfoil_v4.dat
- cp_alpha_*.txt
- polar_v4_auto.txt

MODOS DE USO

1) Modo individual:
python plot_cp.py airfoil_v4.dat cp_alpha_m4.txt cp_alpha_m4_black.png -4 --show

2) Modo individual detectando alpha automáticamente:
python plot_cp.py airfoil_v4.dat cp_alpha_m4.txt cp_alpha_m4_black.png --show

3) Modo automático para todos los cp_alpha_*.txt:
python plot_cp.py --all

4) Modo automático mostrando cada figura:
python plot_cp.py --all --show

5) Modo presentation:
python plot_cp.py --all --presentation
"""

import sys
import os
import re
import glob
import numpy as np
import matplotlib.pyplot as plt


# =========================================================
# CONFIG
# =========================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

DEFAULT_DAT = os.path.join(SCRIPT_DIR, "airfoil_v4.dat")
DEFAULT_POLAR = os.path.join(SCRIPT_DIR, "polar_v4_auto.txt")

DEFAULT_RE = 1.0e6
DEFAULT_NCRIT = 9.0

AIRFOIL_NAME = "AIRFOIL_LE_TE_V4"


# =========================================================
# UTILIDADES BÁSICAS
# =========================================================
def try_float(x):
    try:
        return float(x)
    except Exception:
        return None


def remove_non_finite(points):
    pts = np.array(points, dtype=float)

    if pts.ndim != 2:
        return pts

    mask = np.all(np.isfinite(pts), axis=1)
    return pts[mask]


def remove_non_finite_or_allow_nan_y(points):
    """
    Permite y=NaN cuando el archivo Cp solo trae x Cp.
    Exige x y Cp finitos donde corresponde.
    """
    pts = np.array(points, dtype=float)

    if pts.ndim != 2 or pts.shape[1] != 3:
        return pts

    mask = np.isfinite(pts[:, 0]) & np.isfinite(pts[:, 2])
    return pts[mask]


def sort_by_x(points):
    if len(points) == 0:
        return points

    return points[np.argsort(points[:, 0])]


def remove_consecutive_duplicates(points, tol=1e-8):
    pts = np.array(points, dtype=float)

    if len(pts) == 0:
        return pts

    cleaned = [pts[0]]

    for p in pts[1:]:
        last = cleaned[-1]
        if np.linalg.norm(p - last) > tol:
            cleaned.append(p)

    return np.array(cleaned, dtype=float)


def filter_reasonable_x(points, x_min=-0.10, x_max=1.15):
    if len(points) == 0:
        return points

    mask = (points[:, 0] >= x_min) & (points[:, 0] <= x_max)
    return points[mask]




def alpha_from_cp_filename(cp_path):
    """
    Detecta alpha desde nombres tipo:
    cp_alpha_m4.txt  -> -4
    cp_alpha_p4.txt  -> +4
    cp_alpha_p0.txt  -> 0
    cp_alpha_m2p5.txt -> -2.5 si alguna vez lo usas
    """
    name = os.path.basename(cp_path)

    m = re.search(r"cp_alpha_([mp])([0-9]+(?:p[0-9]+)?)", name, re.IGNORECASE)

    if not m:
        return None

    sign = m.group(1).lower()
    value_txt = m.group(2).replace("p", ".")

    try:
        value = float(value_txt)
    except Exception:
        return None

    if sign == "m":
        return -value

    return value


def output_name_from_cp(cp_path, suffix="_black.png"):
    base = os.path.splitext(os.path.basename(cp_path))[0]
    return os.path.join(os.path.dirname(cp_path), base + suffix)


def find_cp_files(work_dir):
    pattern = os.path.join(work_dir, "cp_alpha_*.txt")
    files = sorted(glob.glob(pattern))

    def sort_key(path):
        alpha = alpha_from_cp_filename(path)
        if alpha is None:
            return 9999
        return alpha

    return sorted(files, key=sort_key)


# =========================================================
# LECTURA .DAT
# =========================================================
def read_airfoil_dat(dat_path):
    pts = []

    with open(dat_path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    for line in lines[1:]:
        s = line.strip()

        if not s:
            continue

        parts = s.replace(",", " ").split()

        if len(parts) < 2:
            continue

        x = try_float(parts[0])
        y = try_float(parts[1])

        if x is None or y is None:
            continue

        pts.append([x, y])

    pts = remove_non_finite(pts)
    pts = filter_reasonable_x(pts)

    if len(pts) < 10:
        raise ValueError("No se han podido leer suficientes puntos del .dat")

    return pts


# =========================================================
# LECTURA CP
# =========================================================
def read_cp_file(cp_path):
    """
    Lee archivo Cp de XFOIL.

    Acepta:
    - x Cp
    - x y Cp

    Devuelve array Nx3:
    x, y, Cp
    """
    rows = []

    with open(cp_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            s = line.strip()

            if not s:
                continue

            parts = s.replace(",", " ").split()

            nums = []

            for p in parts:
                v = try_float(p)
                if v is not None:
                    nums.append(v)

            if len(nums) >= 2:
                rows.append(nums)

    if len(rows) < 10:
        raise ValueError(f"No se han podido leer suficientes datos Cp en: {cp_path}")

    cp_points = []

    for r in rows:
        if len(r) == 2:
            x = r[0]
            y = np.nan
            cp = r[1]
        else:
            x = r[0]
            y = r[1]
            cp = r[2]

        cp_points.append([x, y, cp])

    cp_points = remove_non_finite_or_allow_nan_y(cp_points)
    cp_points = filter_reasonable_x(cp_points)

    if len(cp_points) < 10:
        raise ValueError("El archivo Cp queda con muy pocos puntos tras filtrar")

    return cp_points


# =========================================================
# LECTURA POLAR
# =========================================================
def read_polar_file(polar_path):
    rows = []

    if not os.path.isfile(polar_path):
        return rows

    with open(polar_path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    for line in lines:
        s = line.strip()

        if not s:
            continue

        if not re.match(r"^[\+\-]?\d", s):
            continue

        parts = s.split()

        if len(parts) < 7:
            continue

        vals = []
        ok = True

        for p in parts[:7]:
            v = try_float(p)
            if v is None:
                ok = False
                break
            vals.append(v)

        if ok:
            rows.append({
                "alpha": vals[0],
                "CL": vals[1],
                "CD": vals[2],
                "CDp": vals[3],
                "CM": vals[4],
                "Top_Xtr": vals[5],
                "Bot_Xtr": vals[6],
            })

    return rows


def find_polar_row_for_alpha(rows, alpha_target):
    if not rows:
        return None

    best = None
    best_err = 1e99

    for row in rows:
        err = abs(row["alpha"] - alpha_target)
        if err < best_err:
            best_err = err
            best = row

    return best


# =========================================================
# SEPARACIÓN GEOMETRÍA
# =========================================================
def split_airfoil_by_le(airfoil):
    """
    El .dat suele venir:
    TE upper -> LE -> TE lower
    """
    idx_le = int(np.argmin(airfoil[:, 0]))

    upper = airfoil[:idx_le + 1].copy()
    lower = airfoil[idx_le:].copy()

    upper = remove_consecutive_duplicates(upper)
    lower = remove_consecutive_duplicates(lower)

    upper_plot = sort_by_x(upper)
    lower_plot = sort_by_x(lower)

    # Asegurar upper visual arriba
    if np.nanmean(upper_plot[:, 1]) < np.nanmean(lower_plot[:, 1]):
        upper_plot, lower_plot = lower_plot, upper_plot

    return upper_plot, lower_plot


# =========================================================
# SEPARACIÓN CP
# =========================================================
def split_cp_branches(cp_pts):
    """
    Separa Cp en dos ramas.

    Preferencia:
    1) Si hay coordenada y, separar por y.
    2) Si no hay y, cortar por LE en el orden del archivo.
    """
    x = cp_pts[:, 0]
    y = cp_pts[:, 1]

    has_y = np.any(np.isfinite(y))

    if has_y:
        finite_y = np.isfinite(y)
        pts_with_y = cp_pts[finite_y].copy()

        if len(pts_with_y) >= 10:
            y_median = np.nanmedian(pts_with_y[:, 1])

            branch_a = pts_with_y[pts_with_y[:, 1] >= y_median]
            branch_b = pts_with_y[pts_with_y[:, 1] < y_median]

            if len(branch_a) >= 3 and len(branch_b) >= 3:
                upper = branch_a[:, [0, 2]]
                lower = branch_b[:, [0, 2]]

                upper = sort_by_x(upper)
                lower = sort_by_x(lower)

                return upper, lower

    # Fallback por LE
    idx_le = int(np.argmin(x))

    branch_1 = cp_pts[:idx_le + 1, :].copy()
    branch_2 = cp_pts[idx_le:, :].copy()

    branch_1 = branch_1[:, [0, 2]]
    branch_2 = branch_2[:, [0, 2]]

    branch_1 = sort_by_x(branch_1)
    branch_2 = sort_by_x(branch_2)

    # La rama con Cp medio más negativo se pinta como succión.
    if np.nanmean(branch_1[:, 1]) <= np.nanmean(branch_2[:, 1]):
        upper = branch_1
        lower = branch_2
    else:
        upper = branch_2
        lower = branch_1

    return upper, lower


def remove_large_x_jumps_for_plot(points, jump_tol=0.20):
    """
    Inserta NaN si hay saltos grandes en x.
    Así matplotlib no une puntos lejanos con una línea rara.
    """
    if len(points) < 2:
        return points

    out = [points[0]]

    for i in range(1, len(points)):
        dx = abs(points[i, 0] - points[i - 1, 0])

        if dx > jump_tol:
            out.append([np.nan, np.nan])

        out.append(points[i])

    return np.array(out, dtype=float)


def smooth_te_visual_noise(points, x_start=0.975, max_abs_cp_jump=0.35):
    """
    Limpieza visual ligera cerca del TE.

    No modifica archivos fuente ni resultados XFOIL.
    Solo evita pequeños picos visuales muy bruscos cerca de x ~ 1.
    """
    pts = np.array(points, dtype=float)

    if len(pts) < 5:
        return pts

    cleaned = [pts[0]]

    for i in range(1, len(pts)):
        p_prev = cleaned[-1]
        p = pts[i]

        if np.any(~np.isfinite(p)) or np.any(~np.isfinite(p_prev)):
            cleaned.append(p)
            continue

        near_te = p[0] >= x_start and p_prev[0] >= x_start
        cp_jump = abs(p[1] - p_prev[1])

        if near_te and cp_jump > max_abs_cp_jump:
            # metemos NaN para no unir visualmente ese pico
            cleaned.append([np.nan, np.nan])

        cleaned.append(p)

    return np.array(cleaned, dtype=float)


# =========================================================
# ESCALAS
# =========================================================
def get_cp_ylim(upper_cp, lower_cp):
    cp_all = np.concatenate([upper_cp[:, 1], lower_cp[:, 1]])
    cp_all = cp_all[np.isfinite(cp_all)]

    cp_min = float(np.min(cp_all))
    cp_max = float(np.max(cp_all))

    cp_range = cp_max - cp_min
    cp_margin = max(0.15, 0.12 * (cp_range + 1e-6))

    # Cp invertido estilo XFOIL:
    # arriba = más negativo
    # abajo = más positivo
    return cp_max + cp_margin, cp_min - cp_margin


def get_geo_ylim(upper_geo, lower_geo):
    y_all = np.concatenate([upper_geo[:, 1], lower_geo[:, 1]])
    y_all = y_all[np.isfinite(y_all)]

    y_min = float(np.min(y_all))
    y_max = float(np.max(y_all))

    y_range = y_max - y_min
    y_margin = max(0.015, 0.20 * (y_range + 1e-6))

    return y_min - y_margin, y_max + y_margin


# =========================================================
# PLOT
# =========================================================
def make_plot(
    dat_path,
    cp_path,
    output_png,
    alpha_deg=None,
    polar_path=DEFAULT_POLAR,
    show=False,
    presentation=False
):
    if alpha_deg is None:
        alpha_deg = alpha_from_cp_filename(cp_path)

    if alpha_deg is None:
        raise ValueError("No se pudo detectar alpha. Pásalo como argumento o usa cp_alpha_m4.txt / cp_alpha_p4.txt.")

    airfoil = read_airfoil_dat(dat_path)
    cp_pts = read_cp_file(cp_path)
    polar_rows = read_polar_file(polar_path)

    upper_geo, lower_geo = split_airfoil_by_le(airfoil)
    upper_cp, lower_cp = split_cp_branches(cp_pts)

    upper_cp = remove_large_x_jumps_for_plot(upper_cp)
    lower_cp = remove_large_x_jumps_for_plot(lower_cp)

    # Limpieza visual ligera en TE
    upper_cp = smooth_te_visual_noise(upper_cp)
    lower_cp = smooth_te_visual_noise(lower_cp)

    polar_row = find_polar_row_for_alpha(polar_rows, alpha_deg)

    if polar_row is not None:
        cl = polar_row["CL"]
        cd = polar_row["CD"]
        cm = polar_row["CM"]
        ld = cl / cd if abs(cd) > 1e-12 else None
    else:
        cl = None
        cd = None
        cm = None
        ld = None

    # =========================
    # FIGURA
    # =========================
    if presentation:
        fig = plt.figure(figsize=(14, 7.5), facecolor="black")
        lw_main = 1.7
        text_size = 13
        title_size = 15
    else:
        fig = plt.figure(figsize=(12.8, 7.2), facecolor="black")
        lw_main = 1.25
        text_size = 12
        title_size = 12

    # Colores estilo XFOIL
    c_upper = "#00E5FF"
    c_lower = "#E5C800"
    c_text = "#D8D8D8"
    c_axis = "#B0B0B0"

    # -------------------------
    # AXIS CP
    # -------------------------
    ax1 = fig.add_axes([0.07, 0.40, 0.88, 0.52], facecolor="black")

    ax1.plot(upper_cp[:, 0], upper_cp[:, 1], color=c_upper, lw=lw_main)
    ax1.plot(lower_cp[:, 0], lower_cp[:, 1], color=c_lower, lw=lw_main)

    ax1.set_xlim(-0.04, 1.10)

    valid_upper = upper_cp[np.all(np.isfinite(upper_cp), axis=1)]
    valid_lower = lower_cp[np.all(np.isfinite(lower_cp), axis=1)]
    ax1.set_ylim(*get_cp_ylim(valid_upper, valid_lower))

    ax1.set_ylabel("Cp", color=c_text, fontsize=20)
    ax1.tick_params(colors=c_text, labelsize=12)

    for sp in ax1.spines.values():
        sp.set_color(c_axis)
        sp.set_linewidth(0.8)

    ax1.grid(False)
    ax1.axhline(0.0, color=c_axis, lw=0.8, alpha=0.85)

    ax1.set_xticks(np.linspace(0, 1, 6))
    ax1.set_xticklabels([])

    if not presentation:
        ax1.text(
            0.015, 0.94,
            "XFOIL\nv 6.99",
            transform=ax1.transAxes,
            color=c_text,
            fontsize=10,
            ha="left",
            va="top",
            family="monospace"
        )

    # Bloque de resultados
    info_lines = [AIRFOIL_NAME, ""]
    info_lines.append(f"Re = {DEFAULT_RE / 1e6:.3f}*10$^6$")
    info_lines.append(f"α  = {alpha_deg: .4f}°")

    if cl is not None:
        info_lines.append(f"C$_L$ = {cl: .4f}")
    if cm is not None:
        info_lines.append(f"C$_M$ = {cm: .4f}")
    if cd is not None:
        info_lines.append(f"C$_D$ = {cd: .5f}")
    if ld is not None:
        info_lines.append(f"L/D = {ld: .2f}")

    info_lines.append(f"N$_{{cr}}$ = {DEFAULT_NCRIT: .2f}")

    ax1.text(
        0.66, 0.95,
        "\n".join(info_lines),
        transform=ax1.transAxes,
        color=c_text,
        fontsize=text_size,
        ha="left",
        va="top",
        family="monospace"
    )

    if presentation:
        ax1.set_title(
            f"Pressure coefficient distribution | alpha = {alpha_deg:g} deg",
            color=c_text,
            fontsize=title_size,
            pad=10
        )

    # -------------------------
    # AXIS GEOMETRÍA
    # -------------------------
    ax2 = fig.add_axes([0.07, 0.10, 0.88, 0.18], facecolor="black")

    ax2.plot(upper_geo[:, 0], upper_geo[:, 1], color=c_upper, lw=lw_main)
    ax2.plot(lower_geo[:, 0], lower_geo[:, 1], color=c_lower, lw=lw_main)

    ax2.set_xlim(-0.04, 1.10)
    ax2.set_ylim(*get_geo_ylim(upper_geo, lower_geo))

    ax2.set_xticks([])
    ax2.set_yticks([])

    for sp in ax2.spines.values():
        sp.set_visible(False)

    ax2.grid(False)

    # Guardar
    plt.savefig(output_png, dpi=220 if presentation else 180, facecolor="black", bbox_inches="tight")
    print(f"[OK] Imagen guardada: {output_png}")

    if show:
        plt.show()
    else:
        plt.close(fig)


# =========================================================
# MODOS DE EJECUCIÓN
# =========================================================
def run_single(args):
    """
    Modo individual.

    Posibles:
    python plot_cp.py airfoil_v4.dat cp_alpha_m4.txt out.png -4
    python plot_cp.py airfoil_v4.dat cp_alpha_m4.txt out.png
    """
    clean_args = [
        a for a in args
        if a not in ["--show", "--presentation"]
    ]

    show = "--show" in args
    presentation = "--presentation" in args

    if len(clean_args) < 4:
        raise ValueError(
            "Uso individual:\n"
            "python plot_cp.py airfoil_v4.dat cp_alpha_m4.txt cp_alpha_m4_black.png -4\n"
            "o:\n"
            "python plot_cp.py airfoil_v4.dat cp_alpha_m4.txt cp_alpha_m4_black.png"
        )

    dat_path = clean_args[1]
    cp_path = clean_args[2]
    output_png = clean_args[3]

    if len(clean_args) >= 5:
        alpha_deg = float(clean_args[4])
    else:
        alpha_deg = alpha_from_cp_filename(cp_path)

    print("\n[PLOT CP - SINGLE]")
    print(f"[INFO] DAT   : {dat_path}")
    print(f"[INFO] CP    : {cp_path}")
    print(f"[INFO] OUT   : {output_png}")
    print(f"[INFO] alpha : {alpha_deg}")

    make_plot(
        dat_path=dat_path,
        cp_path=cp_path,
        output_png=output_png,
        alpha_deg=alpha_deg,
        polar_path=DEFAULT_POLAR,
        show=show,
        presentation=presentation
    )


def run_all(args):
    """
    Modo automático:
    python plot_cp.py --all
    """
    show = "--show" in args
    presentation = "--presentation" in args

    dat_path = DEFAULT_DAT
    polar_path = DEFAULT_POLAR
    work_dir = SCRIPT_DIR

    cp_files = find_cp_files(work_dir)

    print("\n[PLOT CP - ALL]")
    print(f"[INFO] Work dir: {work_dir}")
    print(f"[INFO] DAT     : {dat_path}")
    print(f"[INFO] POLAR   : {polar_path}")
    print(f"[INFO] CP files encontrados: {len(cp_files)}")

    if not os.path.isfile(dat_path):
        raise FileNotFoundError(f"No existe el .dat: {dat_path}")

    if len(cp_files) == 0:
        raise FileNotFoundError("No se encontraron archivos cp_alpha_*.txt")

    created = []

    for cp_path in cp_files:
        alpha_deg = alpha_from_cp_filename(cp_path)

        if alpha_deg is None:
            print(f"[WARN] No se pudo detectar alpha en: {cp_path}. Se salta.")
            continue

        output_png = output_name_from_cp(cp_path, suffix="_presentation.png" if presentation else "_black.png")

        print("\n---------------------------------------------")
        print(f"[INFO] Procesando alpha = {alpha_deg:g}")
        print(f"[INFO] CP  : {cp_path}")
        print(f"[INFO] OUT : {output_png}")

        try:
            make_plot(
                dat_path=dat_path,
                cp_path=cp_path,
                output_png=output_png,
                alpha_deg=alpha_deg,
                polar_path=polar_path,
                show=show,
                presentation=presentation
            )
            created.append(output_png)

        except Exception as e:
            print(f"[ERROR] Falló alpha {alpha_deg:g}: {e}")

    print("\n[RESUMEN CP PLOTS]")
    for path in created:
        print(f"[OK] {path}")

    print(f"\n[OK] Total gráficas Cp generadas: {len(created)}")


def print_usage():
    print("""
Uso:

1) Generar todos los Cp automáticamente:
   python plot_cp.py --all

2) Generar todos y abrir ventanas:
   python plot_cp.py --all --show

3) Generar todos en modo presentación:
   python plot_cp.py --all --presentation

4) Modo individual:
   python plot_cp.py airfoil_v4.dat cp_alpha_m4.txt cp_alpha_m4_black.png -4 --show

5) Modo individual detectando alpha:
   python plot_cp.py airfoil_v4.dat cp_alpha_m4.txt cp_alpha_m4_black.png --show
""")


def main():
    args = sys.argv

    if len(args) == 1:
        print_usage()
        return 0

    try:
        if "--all" in args:
            run_all(args)
        else:
            run_single(args)

        return 0

    except Exception as e:
        print("\n[ERROR plot_cp.py]")
        print(str(e))
        print_usage()
        return 1


if __name__ == "__main__":
    sys.exit(main())