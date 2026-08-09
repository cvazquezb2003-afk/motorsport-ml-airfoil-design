"""
VALIDACION EN LA FUENTE (solo lectura, no toca el pipeline):
Corre XFOIL sobre el .dat archivado con el Reynolds real y el escalonado de
angulos, y hace que XFOIL:
  1) vuelque SU PROPIA grafica de Cp a PostScript nativo con el comando HARD
     (-> plot.ps). Es la representacion nativa de XFOIL, no un redibujado.
  2) escriba el fichero crudo de Cp con CPWR (-> cp.txt).
Luego inspecciona plot.ps y la zona del TE del fichero crudo.
"""
import os
import sys
import shutil
import subprocess

import run_xfoil as rx
import generate_batch as gb
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
DF = pd.read_csv(os.path.join(BASE, "airfoil_dataset.csv"))
WORK = os.path.join(os.environ.get("TEMP", BASE), "xfoil_native")
os.makedirs(WORK, exist_ok=True)

RUN_ID = "0048_20260701_202312"
VEL = 180
ALPHA = -6

chord = float(DF[DF.run_id == RUN_ID].chord_length_mm.iloc[0])
Re = gb.compute_reynolds(chord, VEL)
dat_src = os.path.join(BASE, "dataset_runs", RUN_ID, "airfoil_v4.dat")
shutil.copy2(dat_src, os.path.join(WORK, "geom.dat"))

for f in ("plot.ps", "cp.txt", "polar.txt"):
    p = os.path.join(WORK, f)
    if os.path.exists(p):
        os.remove(p)

seq = list(range(0, ALPHA - 1, -2))   # 0,-2,-4,-6
# HARD justo despues del ALFA objetivo -> vuelca el Cp de ESE angulo a plot.ps
cmds = ["LOAD geom.dat", "", "PANE", "OPER",
        f"VISC {int(round(Re))}", "ITER 200", "PACC", "polar.txt", ""]
cmds += [f"ALFA {a}" for a in seq]
cmds += ["HARD", "CPWR cp.txt", "PACC", "", "QUIT"]

print(f"[INFO] perfil {RUN_ID[:4]} | v={VEL} | alpha={ALPHA} | Re real={Re:,.0f}")
print("[INFO] comandos XFOIL:")
print("   " + " / ".join(cmds))

r = subprocess.run([rx.XFOIL_EXE], input="\n".join(cmds) + "\n", text=True,
                   capture_output=True, cwd=WORK, timeout=120)

ps = os.path.join(WORK, "plot.ps")
cp = os.path.join(WORK, "cp.txt")
print(f"\n[RESULT] plot.ps creado: {os.path.isfile(ps)}"
      + (f" ({os.path.getsize(ps)} bytes)" if os.path.isfile(ps) else ""))
print(f"[RESULT] cp.txt creado : {os.path.isfile(cp)}"
      + (f" ({os.path.getsize(cp)} bytes)" if os.path.isfile(cp) else ""))
print(f"[RESULT] WORK dir: {WORK}")

# Menciones de HARD / plot.ps en la salida de XFOIL
for line in (r.stdout or "").splitlines():
    if any(k in line for k in ("plot.ps", "Hardcopy", "hardcopy", "HARD", "PostScript", "sav")):
        print("   [xfoil] " + line.strip())

# Cabeceras del cp.txt (para ver columnas: x Cp  o  x y Cp)
if os.path.isfile(cp):
    print("\n[cp.txt] primeras 6 lineas:")
    with open(cp, encoding="utf-8", errors="ignore") as f:
        for _ in range(6):
            ln = f.readline()
            if not ln:
                break
            print("   " + ln.rstrip())
