"""
DIAGNOSTICO (solo lectura): aisla Reynolds de cuerda. UN mismo perfil (misma
geometria) a las 3 velocidades, mismo angulo (-6). Si el zigzag del Cp cerca del
TE depende del Reynolds, debe aparecer a 290 km/h (Re alto) y atenuarse/desaparecer
a 110 km/h (Re bajo). NO toca el pipeline.
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
OUTDIR = os.path.join(BASE, "eda_outputs", "zigzag_vel")
os.makedirs(OUTDIR, exist_ok=True)
TMP = os.path.join(os.environ.get("TEMP", BASE), "cp_diag_vel")

RUN_ID = "0048_20260701_202312"
ALPHA = -6
VELS = [110, 180, 290]

df = pd.read_csv(os.path.join(BASE, "airfoil_dataset.csv"))
CHORD = float(df[df.run_id == RUN_ID].chord_length_mm.iloc[0])
print(f"[INFO] perfil {RUN_ID[:4]} | cuerda FIJA = {CHORD:.1f} mm | alpha = {ALPHA}")


def run_xfoil(v, workdir):
    os.makedirs(workdir, exist_ok=True)
    shutil.copy2(os.path.join(BASE, "dataset_runs", RUN_ID, "airfoil_v4.dat"),
                 os.path.join(workdir, "geom.dat"))
    Re = gb.compute_reynolds(CHORD, v)
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
    return up if np.nanmean(up[:, 1]) <= np.nanmean(lo[:, 1]) else lo


def zigzag_score(branch, x0=0.60, x1=1.0, amp=0.10):
    b = branch[np.all(np.isfinite(branch), axis=1)]
    b = b[(b[:, 0] >= x0) & (b[:, 0] <= x1)]
    b = b[np.argsort(b[:, 0])]
    if len(b) < 4:
        return 0
    d = np.diff(b[:, 1]); sign = 0; rev = 0
    for delta in d:
        if abs(delta) < amp:
            continue
        s = 1 if delta > 0 else -1
        if sign != 0 and s != sign:
            rev += 1
        sign = s
    return rev


def plot_cp(v, cp_path, Re, rev, out_png):
    airfoil = pc.read_airfoil_dat(os.path.join(BASE, "dataset_runs", RUN_ID, "airfoil_v4.dat"))
    cp_pts = pc.read_cp_file(cp_path)
    ug, lg = pc.split_airfoil_by_le(airfoil)
    uc, lc = pc.split_cp_branches(cp_pts)
    uc = pc.smooth_te_visual_noise(pc.remove_large_x_jumps_for_plot(uc))
    lc = pc.smooth_te_visual_noise(pc.remove_large_x_jumps_for_plot(lc))
    fig = plt.figure(figsize=(11, 6.2), facecolor="black")
    ax1 = fig.add_axes([0.08, 0.40, 0.88, 0.50], facecolor="black")
    ax1.plot(uc[:, 0], uc[:, 1], color="#00E5FF", lw=1.2)
    ax1.plot(lc[:, 0], lc[:, 1], color="#E5C800", lw=1.2)
    ax1.set_xlim(-0.04, 1.10)
    vu = uc[np.all(np.isfinite(uc), axis=1)]; vl = lc[np.all(np.isfinite(lc), axis=1)]
    ax1.set_ylim(*pc.get_cp_ylim(vu, vl))
    ax1.axvspan(0.60, 1.0, color="#552222", alpha=0.35)
    ax1.set_ylabel("Cp", color="#D8D8D8", fontsize=16)
    ax1.tick_params(colors="#D8D8D8"); ax1.set_xticks(np.linspace(0, 1, 6)); ax1.set_xticklabels([])
    ax1.axhline(0, color="#B0B0B0", lw=0.7)
    ax1.set_title(f"{RUN_ID[:4]} (cuerda {CHORD:.0f}mm FIJA) | {v} km/h | a=-6 | "
                  f"Re={Re:,.0f} | reversiones={rev}", color="#D8D8D8", fontsize=11)
    ax2 = fig.add_axes([0.08, 0.12, 0.88, 0.18], facecolor="black")
    ax2.plot(ug[:, 0], ug[:, 1], color="#00E5FF", lw=1.2)
    ax2.plot(lg[:, 0], lg[:, 1], color="#E5C800", lw=1.2)
    ax2.set_xlim(-0.04, 1.10); ax2.set_xticks([]); ax2.set_yticks([])
    for sp in ax2.spines.values(): sp.set_visible(False)
    plt.savefig(out_png, dpi=150, facecolor="black", bbox_inches="tight"); plt.close(fig)


print(f"\n{'v (km/h)':>9} {'Reynolds':>11} {'reversiones':>12}  zigzag?")
for i, v in enumerate(VELS):
    cp_path, Re = run_xfoil(v, os.path.join(TMP, str(v)))
    if cp_path is None:
        print(f"{v:>9} {Re:>11,.0f}   XFOIL no convergio a -6"); continue
    rev = zigzag_score(suction_branch(pc.read_cp_file(cp_path)))
    out = os.path.join(OUTDIR, f"cp_0048_v{v}.png")
    plot_cp(v, cp_path, Re, rev, out)
    print(f"{v:>9} {Re:>11,.0f} {rev:>12}  {'SI' if rev >= 3 else 'no'}   -> {out}")
