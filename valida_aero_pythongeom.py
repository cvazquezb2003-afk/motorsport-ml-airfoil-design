"""
PASO B — Validacion AERODINAMICA del generador Python (airfoil_geom_python.py).
Para 15-20 perfiles: genera el .dat en Python, lo pasa por XFOIL en las MISMAS
condiciones (Re, alpha, velocidad) del CSV, y compara CL/CD/LD contra los valores
REALES (que salieron del .dat de CATIA). No toca el pipeline: usa ficheros temporales.
"""
import os, subprocess, tempfile
import numpy as np
import pandas as pd
import airfoil_geom_python as G

BASE = os.path.dirname(os.path.abspath(__file__))
from rutas import XFOIL_EXE as XFOIL   # fuente unica de la ruta a XFOIL (ver rutas.py)
SCRATCH = os.path.join(BASE, "_paso_b_tmp")
os.makedirs(SCRATCH, exist_ok=True)
SHAPE = ["chord_length_mm", "leading_edge_angle_deg", "leading_edge_thickness_level",
         "trailing_edge_angle_deg", "trailing_edge_thickness_mm",
         "te_upr_angle_deg", "te_lwr_angle_deg"]


def escribe_dat(contour, path, nombre="PY_GEOM"):
    with open(path, "w") as f:
        f.write(nombre + "\n")
        for x, y in contour:
            f.write(f"{x:.6f} {y:.6f}\n")


def xfoil_polar(dat_path, reynolds, alphas, polar_path):
    if os.path.exists(polar_path):
        os.remove(polar_path)
    cmds = [f"LOAD {dat_path}", "", "PANE", "OPER", f"VISC {int(reynolds)}",
            "ITER 100", "PACC", polar_path, ""]
    for a in alphas:
        cmds.append(f"ALFA {a}")
    cmds += ["PACC", "", "QUIT"]
    try:
        subprocess.run([XFOIL], input="\n".join(cmds) + "\n", text=True,
                       capture_output=True, cwd=SCRATCH, timeout=90)
    except Exception:
        pass
    # parsear polar
    out = {}
    if os.path.exists(polar_path):
        for ln in open(polar_path, encoding="utf-8", errors="ignore"):
            p = ln.split()
            if len(p) >= 5:
                try:
                    a = float(p[0]); cl = float(p[1]); cd = float(p[2])
                    out[round(a)] = (cl, cd)
                except ValueError:
                    pass
    return out


def elige_perfiles(df, n_por_zona=6):
    ok = df[df.status == "ok"]
    # perfiles con .dat y con las 3 velocidades ok
    cand = []
    for rid, g in ok.groupby("run_id"):
        if g.velocidad_kmh.nunique() < 3:
            continue
        if not os.path.exists(os.path.join(BASE, "dataset_runs", rid, "airfoil_v4.dat")):
            continue
        cand.append((rid, g.chord_length_mm.iloc[0]))
    cand = pd.DataFrame(cand, columns=["run_id", "chord"])
    sel = []
    for lo, hi in [(150, 200), (200, 400), (400, 500)]:
        z = cand[(cand.chord >= lo) & (cand.chord < hi)]
        sel += z.head(n_por_zona).run_id.tolist()
    return sel


if __name__ == "__main__":
    df = pd.read_csv(os.path.join(BASE, "airfoil_dataset.csv"))
    perfiles = elige_perfiles(df, n_por_zona=6)
    print(f"[INFO] {len(perfiles)} perfiles seleccionados\n")
    filas = []
    for k, rid in enumerate(perfiles, 1):
        g = df[(df.run_id == rid) & (df.status == "ok")]
        p = {c: g.iloc[0][c] for c in SHAPE}
        contour, _ = G.generate_contour(p)
        dat = os.path.join(SCRATCH, "py.dat")
        escribe_dat(contour, dat)
        chord = p["chord_length_mm"]
        print(f"  [{k}/{len(perfiles)}] {rid}  cuerda={chord:.0f}mm")
        for v in [110, 180, 290]:
            gv = g[g.velocidad_kmh == v]
            if gv.empty:
                continue
            Re = int(gv.reynolds.iloc[0])
            alphas = sorted(gv.alpha_deg.tolist())
            pol = xfoil_polar(dat, Re, alphas, os.path.join(SCRATCH, "pol.txt"))
            for _, r in gv.iterrows():
                a = int(r.alpha_deg)
                if a in pol:
                    clp, cdp = pol[a]
                    ldp = clp/cdp if cdp else np.nan
                    filas.append(dict(run_id=rid, chord=chord, v=v, alpha=a, Re=Re,
                                      CL_real=r.CL, CL_py=clp, CD_real=r.CD, CD_py=cdp,
                                      LD_real=r.LD, LD_py=ldp))
    R = pd.DataFrame(filas)
    R.to_csv(os.path.join(BASE, "valida_aero_resultados.csv"), index=False)
    print(f"\n[OK] {len(R)} condiciones comparadas (Python convergio y existia en CSV)")

    # errores relativos
    for col in ["CL", "CD", "LD"]:
        R[f"err_{col}"] = 100*np.abs(R[f"{col}_py"]-R[f"{col}_real"])/np.abs(R[f"{col}_real"])
    print("\n=== RESUMEN ERROR RELATIVO (%) Python vs real(CATIA) ===")
    print(f"{'metrica':8s}{'media':>9s}{'p95':>9s}{'max':>9s}")
    for col in ["CL", "CD", "LD"]:
        e = R[f"err_{col}"].replace([np.inf, -np.inf], np.nan).dropna()
        print(f"{col:8s}{e.mean():>8.1f}%{e.quantile(.95):>8.1f}%{e.max():>8.1f}%")

    print("\n=== POR ZONA DE CUERDA (error medio %) ===")
    R["zona"] = pd.cut(R.chord, [150, 200, 400, 500], labels=["150-200", "200-400", "400-500"])
    print(R.groupby("zona", observed=True)[["err_CL", "err_CD", "err_LD"]].mean().round(1).to_string())

    print("\n=== MUESTRA (primeras 18 condiciones) ===")
    cols = ["run_id", "chord", "v", "alpha", "CL_real", "CL_py", "CD_real", "CD_py", "err_CL", "err_CD"]
    print(R[cols].head(18).to_string(index=False))
