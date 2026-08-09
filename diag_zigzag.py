"""
DIAGNOSTICO (solo lectura): comprueba si el zigzag cerca del TE en la curva de
Cp aparece en todos los perfiles o solo en algunos. Para una condicion comun
(180 km/h, -6 deg) genera el Cp a demanda (Re real, .dat archivado) y mide un
'score de zigzag' en la rama de succion cerca del TE (x en [0.80, 1.0]).
NO toca el pipeline.
"""
import os
import shutil
import subprocess
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import plot_cp as pc
import generate_batch as gb
import run_xfoil as rx
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
OUTDIR = os.path.join(BASE, "eda_outputs", "zigzag")
os.makedirs(OUTDIR, exist_ok=True)
TMP = os.path.join(os.environ.get("TEMP", BASE), "cp_diag")

VEL = 180
ALPHA = -6
PROFILES = [
    "0031_20260628_223705", "0002_20260701_194537", "0005_20260628_221820",
    "0006_20260701_194939", "0038_20260701_201514", "0001_20260701_194448",
    "0040_20260628_224318", "0048_20260701_202312",
]

df = pd.read_csv(os.path.join(BASE, "airfoil_dataset.csv"))


def run_xfoil(run_id, chord, workdir):
    os.makedirs(workdir, exist_ok=True)
    dat_src = os.path.join(BASE, "dataset_runs", run_id, "airfoil_v4.dat")
    shutil.copy2(dat_src, os.path.join(workdir, "geom.dat"))
    Re = gb.compute_reynolds(chord, VEL)
    seq = list(range(0, ALPHA - 1, -2))
    cmds = ["LOAD geom.dat", "", "PANE", "OPER",
            f"VISC {int(round(Re))}", "ITER 200", "PACC", "polar.txt", ""]
    cmds += [f"ALFA {a}" for a in seq]
    cmds += ["CPWR cp.txt", "PACC", "", "QUIT"]
    subprocess.run([rx.XFOIL_EXE], input="\n".join(cmds) + "\n", text=True,
                   capture_output=True, cwd=workdir, timeout=120)
    cp = os.path.join(workdir, "cp.txt")
    return (cp if os.path.isfile(cp) else None), Re


def suction_branch(cp_pts):
    up, lo = pc.split_cp_branches(cp_pts)
    # rama de succion = la de Cp medio mas negativo
    return up if np.nanmean(up[:, 1]) <= np.nanmean(lo[:, 1]) else lo


def zigzag_score(branch, x0=0.60, x1=1.0, amp=0.10):
    """Nº de reversiones de direccion del Cp (con amplitud > amp) en [x0,x1]."""
    b = branch[np.all(np.isfinite(branch), axis=1)]
    b = b[(b[:, 0] >= x0) & (b[:, 0] <= x1)]
    b = b[np.argsort(b[:, 0])]
    if len(b) < 4:
        return 0, len(b)
    d = np.diff(b[:, 1])
    sign = 0
    rev = 0
    for delta in d:
        if abs(delta) < amp:
            continue
        s = 1 if delta > 0 else -1
        if sign != 0 and s != sign:
            rev += 1
        sign = s
    return rev, len(b)


def plot_cp(run_id, cp_path, Re, out_png):
    airfoil = pc.read_airfoil_dat(os.path.join(BASE, "dataset_runs", run_id, "airfoil_v4.dat"))
    cp_pts = pc.read_cp_file(cp_path)
    ug, lg = pc.split_airfoil_by_le(airfoil)
    uc, lc = pc.split_cp_branches(cp_pts)
    uc = pc.smooth_te_visual_noise(pc.remove_large_x_jumps_for_plot(uc))
    lc = pc.smooth_te_visual_noise(pc.remove_large_x_jumps_for_plot(lc))
    fig = plt.figure(figsize=(11, 6.2), facecolor="black")
    ax1 = fig.add_axes([0.08, 0.40, 0.88, 0.52], facecolor="black")
    ax1.plot(uc[:, 0], uc[:, 1], color="#00E5FF", lw=1.2)
    ax1.plot(lc[:, 0], lc[:, 1], color="#E5C800", lw=1.2)
    ax1.set_xlim(-0.04, 1.10)
    vu = uc[np.all(np.isfinite(uc), axis=1)]; vl = lc[np.all(np.isfinite(lc), axis=1)]
    ax1.set_ylim(*pc.get_cp_ylim(vu, vl))
    ax1.axvspan(0.60, 1.0, color="#552222", alpha=0.35)  # zona TE inspeccionada
    ax1.set_ylabel("Cp", color="#D8D8D8", fontsize=16)
    ax1.tick_params(colors="#D8D8D8"); ax1.set_xticks(np.linspace(0, 1, 6)); ax1.set_xticklabels([])
    ax1.axhline(0, color="#B0B0B0", lw=0.7)
    ax1.set_title(f"{run_id[:4]} | 180 km/h | a=-6 | Re={Re:,.0f}", color="#D8D8D8", fontsize=11)
    ax2 = fig.add_axes([0.08, 0.12, 0.88, 0.18], facecolor="black")
    ax2.plot(ug[:, 0], ug[:, 1], color="#00E5FF", lw=1.2)
    ax2.plot(lg[:, 0], lg[:, 1], color="#E5C800", lw=1.2)
    ax2.set_xlim(-0.04, 1.10); ax2.set_xticks([]); ax2.set_yticks([])
    for sp in ax2.spines.values(): sp.set_visible(False)
    plt.savefig(out_png, dpi=150, facecolor="black", bbox_inches="tight"); plt.close(fig)


print(f"{'run_id':24} {'Re':>10} {'pts_TE':>7} {'reversiones':>11}  zigzag?")
results = []
for i, rid in enumerate(PROFILES):
    chord = df[df.run_id == rid].chord_length_mm.iloc[0]
    cp_path, Re = run_xfoil(rid, chord, os.path.join(TMP, str(i)))
    if cp_path is None:
        print(f"{rid:24} {'-':>10}  XFOIL no convergio"); continue
    cp_pts = pc.read_cp_file(cp_path)
    sb = suction_branch(cp_pts)
    rev, npts = zigzag_score(sb)
    zig = rev >= 3
    out = os.path.join(OUTDIR, f"cp_{rid[:4]}.png")
    plot_cp(rid, cp_path, Re, out)
    results.append((rid, rev, zig, out))
    print(f"{rid:24} {Re:>10,.0f} {npts:>7} {rev:>11}  {'SI' if zig else 'no'}")

n_zig = sum(1 for _, _, z, _ in results if z)
print(f"\nCON zigzag: {n_zig} | SIN zigzag: {len(results)-n_zig}  (de {len(results)})")
if results:
    worst = max(results, key=lambda r: r[1]); best = min(results, key=lambda r: r[1])
    print(f"ejemplo CON mas zigzag: {worst[0][:4]} (rev={worst[1]}) -> {worst[3]}")
    print(f"ejemplo SIN/menos zigzag: {best[0][:4]} (rev={best[1]}) -> {best[3]}")
