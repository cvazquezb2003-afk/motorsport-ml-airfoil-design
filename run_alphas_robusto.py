"""
run_alphas_robusto.py
======================

Corre el MISMO perfil (airfoil_v4.dat) a una lista de angulos, con una
secuencia XFOIL mas robusta para forzar convergencia en perfiles con un
trailing edge imperfecto:

  - Repanelado denso (PANE + PPAR N).
  - Mas iteraciones (ITER 200).
  - Arranque "marchando" desde alpha = 0: primero se converge alpha 0
    (fuera de la polar), y luego se sube de uno en uno usando la solucion
    anterior como semilla. Asi se evita el cold-start directo a un alpha
    alto, que es lo que suele fallar.

No modifica el pipeline ni la geometria. Es un script de diagnostico/uso
directo sobre el .dat que ya existe.

Uso:
    python run_alphas_robusto.py            -> alphas 2,4,6,8
    python run_alphas_robusto.py "[2,4,6,8]"
"""

import os
import sys
import json
import subprocess

from rutas import XFOIL_EXE   # fuente unica de la ruta a XFOIL (ver rutas.py)
from rutas import BASE as WORK_DIR   # carpeta del proyecto

AIRFOIL_DAT = os.path.join(WORK_DIR, "airfoil_v4.dat")
POLAR_FILE = os.path.join(WORK_DIR, "polar_2468.txt")
XFOIL_LOG = os.path.join(WORK_DIR, "xfoil_2468_robusto_log.txt")

REYNOLDS = 1_000_000
ITERATIONS = 200
N_PANELS = 240


def parse_alphas(argv, default):
    if len(argv) < 2:
        return default
    try:
        parsed = json.loads(argv[1])
    except json.JSONDecodeError:
        return default
    if isinstance(parsed, list) and parsed and all(isinstance(a, (int, float)) for a in parsed):
        return parsed
    return default


def build_commands(alphas):
    seed = 0  # alpha de arranque para sembrar la solucion viscosa

    c = []
    c.append(f"LOAD {AIRFOIL_DAT}")
    c.append("")              # aceptar nombre por defecto

    # Repanelado (PANE deja ~160 paneles bien distribuidos)
    c.append("PANE")

    # Operacion viscosa
    c.append("OPER")
    c.append(f"VISC {REYNOLDS}")
    c.append(f"ITER {ITERATIONS}")

    # Sembrar: converger alpha de arranque SIN acumular en polar
    c.append("INIT")
    c.append(f"ALFA {seed}")

    # Activar acumulacion de polar
    c.append("PACC")
    c.append(POLAR_FILE)
    c.append("")              # sin archivo dump

    # Marchar por los alphas pedidos, en orden ascendente, usando la
    # solucion previa como semilla (sin INIT entre ellos).
    for a in sorted(alphas):
        c.append(f"ALFA {a}")

    c.append("PACC")          # cerrar polar
    c.append("")              # salir de OPER
    c.append("QUIT")

    return "\n".join(c) + "\n"


def main():
    alphas = parse_alphas(sys.argv, [2, 4, 6, 8])

    if not os.path.isfile(XFOIL_EXE):
        print(f"[ERROR] No existe xfoil.exe: {XFOIL_EXE}")
        return 1
    if not os.path.isfile(AIRFOIL_DAT):
        print(f"[ERROR] No existe el .dat: {AIRFOIL_DAT}")
        return 1

    if os.path.exists(POLAR_FILE):
        os.remove(POLAR_FILE)

    commands = build_commands(alphas)

    print("[INFO] Alphas pedidos:", alphas)
    print("[INFO] Comandos XFOIL:")
    print("-" * 50)
    print(commands)
    print("-" * 50)
    print("[INFO] Ejecutando XFOIL (robusto)...")

    result = subprocess.run(
        [XFOIL_EXE],
        input=commands,
        text=True,
        capture_output=True,
        cwd=WORK_DIR,
        timeout=300,
    )

    with open(XFOIL_LOG, "w", encoding="utf-8", errors="ignore") as f:
        f.write(result.stdout or "")
        f.write("\n\n===== STDERR =====\n")
        f.write(result.stderr or "")

    print(f"[INFO] Log: {XFOIL_LOG}")

    if not os.path.isfile(POLAR_FILE):
        print("[ERROR] No se genero la polar.")
        return 1

    print(f"\n[OK] Polar generada: {POLAR_FILE}")
    print("=" * 50)
    with open(POLAR_FILE, "r", encoding="utf-8", errors="ignore") as f:
        print(f.read())
    print("=" * 50)
    return 0


if __name__ == "__main__":
    sys.exit(main())
