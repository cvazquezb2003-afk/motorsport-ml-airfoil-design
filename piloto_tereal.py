"""
PILOTO TE-REAL sobre 100 perfiles (Pasos 1 y 2).
Selecciona 100 perfiles estratificados por cuerda, regenera su geometria con el
conversor TE-real (perfil hasta esquinas reales, TE romo por hueco 1er/ultimo,
sin listar la cara ni cerrar), y corre XFOIL en EXACTAMENTE las condiciones del
CSV actual (mismas velocidades, angulos, Re). Guarda airfoil_dataset_TEreal_piloto.csv.

NO toca airfoil_dataset.csv, ni asc_to_dat.py, ni el pipeline. Solo lectura de esos.
Escritura incremental + tally por perfil (para vigilar convergencia y cortar si es mala).
"""
import os, sys, csv, subprocess, shutil
import numpy as np
import pandas as pd
from asc_to_dat import (read_asc_points, project_to_chord_system,
                        remove_consecutive_duplicates, PLANE_MODE, N_LE, N_TE)

BASE = os.path.dirname(os.path.abspath(__file__))
from rutas import XFOIL_EXE as XFOIL   # fuente unica de la ruta a XFOIL (ver rutas.py)
SCRATCH = os.path.join(BASE, "_piloto_tmp"); os.makedirs(SCRATCH, exist_ok=True)
OUT_CSV = os.path.join(BASE, "airfoil_dataset_TEreal_piloto.csv")
SHAPE = ["chord_length_mm", "leading_edge_angle_deg", "leading_edge_thickness_level",
         "trailing_edge_angle_deg", "trailing_edge_thickness_mm",
         "te_upr_angle_deg", "te_lwr_angle_deg"]
COLS = ["run_id", "timestamp", "source"] + SHAPE + \
       ["alpha_deg", "velocidad_kmh", "reynolds", "CL", "CD", "CM", "LD", "status", "error_detail"]


def genera_tereal(asc_path, out_dat):
    """TE-real: perfil hasta esquinas reales, TE romo por hueco (estandar XFOIL)."""
    pts = read_asc_points(asc_path, plane_mode=PLANE_MODE)
    le_raw = pts[:N_LE]; te_raw = pts[N_LE:N_LE + N_TE]
    if len(te_raw) > 0:
        te_raw = te_raw[::-1]
    le_norm, te_norm, chord = project_to_chord_system(le_raw, te_raw)
    ch = remove_consecutive_duplicates(le_norm)
    if ch[0, 1] < ch[-1, 1]:
        ch = ch[::-1]
    ch[:, 0] = np.clip(ch[:, 0], 0.0, 1.0)
    with open(out_dat, "w") as f:
        f.write("TE_REAL\n")
        for x, y in ch:
            f.write(f"{x:.6f} {y:.6f}\n")
    return float(np.linalg.norm(ch[0] - ch[-1]))


def xfoil_sweep(dat, Re, alphas):
    """Corre un barrido de alphas (orden del dataset: 0,-2,...) con ITER 100 (como el pipeline).
    Devuelve {alpha_int: (CL,CD,CM)} para los que convergieron."""
    geom = os.path.join(SCRATCH, "geom.dat"); shutil.copy2(dat, geom)
    pol = "pol.txt"
    polp = os.path.join(SCRATCH, pol)
    if os.path.exists(polp):
        os.remove(polp)
    cmds = ["LOAD geom.dat", "", "PANE", "OPER", f"VISC {int(Re)}", "ITER 100", "PACC", pol, ""]
    for a in alphas:
        cmds.append(f"ALFA {a}")
    cmds += ["PACC", "", "QUIT"]
    try:
        subprocess.run([XFOIL], input="\n".join(cmds) + "\n", text=True,
                       capture_output=True, cwd=SCRATCH, timeout=150)
    except Exception:
        pass
    out = {}
    if os.path.exists(polp):
        for ln in open(polp, encoding="utf-8", errors="ignore"):
            p = ln.split()
            if len(p) >= 5:
                try:
                    a = float(p[0]); cl = float(p[1]); cd = float(p[2]); cm = float(p[4])
                    out[int(round(a))] = (cl, cd, cm)
                except ValueError:
                    pass
    return out


def selecciona(df, n_por_zona):
    """Perfiles con .asc archivado, estratificados por cuerda, variados (espaciado)."""
    ok = df.groupby("run_id").first().reset_index()
    ok = ok[[os.path.exists(os.path.join(BASE, "dataset_runs", r, "auto_export.asc"))
             for r in ok.run_id]]
    sel = []
    for (lo, hi), n in n_por_zona.items():
        z = ok[(ok.chord_length_mm >= lo) & (ok.chord_length_mm < hi)].sort_values("chord_length_mm")
        if len(z) <= n:
            sel += z.run_id.tolist()
        else:
            idx = np.linspace(0, len(z) - 1, n).round().astype(int)  # espaciado por cuerda
            sel += z.iloc[idx].run_id.tolist()
    return sel


if __name__ == "__main__":
    df = pd.read_csv(os.path.join(BASE, "airfoil_dataset.csv"))
    perfiles = selecciona(df, {(150, 200): 18, (200, 400): 55, (400, 500): 27})
    print(f"[SELECCION] {len(perfiles)} perfiles")
    for (lo, hi) in [(150, 200), (200, 400), (400, 500)]:
        chs = [df[df.run_id == r].chord_length_mm.iloc[0] for r in perfiles]
        z = [c for c in chs if lo <= c < hi]
        print(f"   {lo}-{hi} mm: {len(z)} perfiles  (cuerdas {min(z):.0f}-{max(z):.0f})")
    sys.stdout.flush()

    with open(OUT_CSV, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS); w.writeheader()
        tot_ok = tot = 0
        for k, rid in enumerate(perfiles, 1):
            g = df[df.run_id == rid]
            base = g.iloc[0]
            asc = os.path.join(BASE, "dataset_runs", rid, "auto_export.asc")
            dat = os.path.join(SCRATCH, "tr.dat")
            try:
                gap = genera_tereal(asc, dat)
            except Exception as e:
                print(f"  [{k}/100] {rid} FALLO genera: {e}"); sys.stdout.flush(); continue
            p_ok = p_tot = 0
            for v in sorted(g.velocidad_kmh.unique()):
                gv = g[g.velocidad_kmh == v]
                alphas = sorted(gv.alpha_deg.tolist(), reverse=True)  # 0,-2,-4,... como el dataset
                Re = int(gv.reynolds.iloc[0])
                pol = xfoil_sweep(dat, Re, alphas)
                for a in alphas:
                    p_tot += 1; tot += 1
                    row = {c: base[c] for c in ["run_id", "timestamp", "source"] + SHAPE}
                    row.update({"alpha_deg": a, "velocidad_kmh": v, "reynolds": Re})
                    if a in pol:
                        cl, cd, cm = pol[a]
                        ld = cl / cd if cd else ""
                        row.update({"CL": cl, "CD": cd, "CM": cm, "LD": ld,
                                    "status": "ok", "error_detail": ""})
                        p_ok += 1; tot_ok += 1
                    else:
                        row.update({"CL": "", "CD": "", "CM": "", "LD": "",
                                    "status": "error_xfoil_no_converge",
                                    "error_detail": f"TE-real no converge a{a} v{v}"})
                    w.writerow(row)
            fh.flush()
            print(f"  [{k}/100] {rid} c={base['chord_length_mm']:.0f} | conv {p_ok}/{p_tot} "
                  f"| acumulado {tot_ok}/{tot} ({100*tot_ok/tot:.0f}%)")
            sys.stdout.flush()
    print(f"\n[OK] guardado {OUT_CSV}  ({tot_ok}/{tot} ok, {100*tot_ok/tot:.0f}%)")
