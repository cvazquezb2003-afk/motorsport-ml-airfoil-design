import os
import sys
import json
import subprocess
import time


# =========================================================
# CONFIG
# =========================================================

from rutas import XFOIL_EXE   # fuente unica de la ruta a XFOIL (ver rutas.py)

from rutas import BASE as WORK_DIR   # carpeta del proyecto

AIRFOIL_DAT = os.path.join(WORK_DIR, "airfoil_v4.dat")
POLAR_FILE = os.path.join(WORK_DIR, "polar_v4_auto.txt")
XFOIL_LOG = os.path.join(WORK_DIR, "xfoil_log.txt")

REYNOLDS = 1_000_000
ITERATIONS = 100

ALPHAS = [-8,-6,-4,-2, 0, 2, 4]


# =========================================================
# PARSEO DE ALPHAS POR ARGUMENTO (OPCIONAL)
# =========================================================

def parse_alphas_arg(argv):
    """
    Permite sobreescribir ALPHAS pasando un JSON como primer argumento:

        python run_xfoil.py "[0]"
        python run_xfoil.py "[-4, 0, 4]"

    Si no se pasa argumento (o el JSON es inválido / no es una lista
    numérica), se devuelve None y se mantiene la lista ALPHAS por defecto,
    para no romper el comportamiento actual.
    """
    if len(argv) < 2:
        return None

    raw = argv[1]

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"[WARN] Argumento alphas no es JSON válido ({e}). Se usa la lista por defecto.")
        return None

    if not isinstance(parsed, list) or len(parsed) == 0:
        print("[WARN] El argumento alphas debe ser una lista no vacía. Se usa la lista por defecto.")
        return None

    if not all(isinstance(a, (int, float)) for a in parsed):
        print("[WARN] Todos los alphas deben ser numéricos. Se usa la lista por defecto.")
        return None

    return parsed


def parse_reynolds_arg(argv):
    """
    Permite sobreescribir REYNOLDS pasando un numero como SEGUNDO argumento:

        python run_xfoil.py "[-6]" "1235992"

    Si no se pasa (o no es un numero > 0) se devuelve None y se mantiene el
    REYNOLDS actual, para no romper el comportamiento standalone.
    """
    if len(argv) < 3:
        return None

    try:
        re = float(argv[2])
    except ValueError:
        print(f"[WARN] Reynolds por argumento no numérico ({argv[2]!r}). Se ignora.")
        return None

    if re <= 0:
        print("[WARN] Reynolds por argumento debe ser > 0. Se ignora.")
        return None

    return int(round(re))


# =========================================================
# UTILIDADES
# =========================================================

def check_files():
    if not os.path.isfile(XFOIL_EXE):
        raise FileNotFoundError(f"No se encuentra xfoil.exe en:\n{XFOIL_EXE}")

    if not os.path.isfile(AIRFOIL_DAT):
        raise FileNotFoundError(f"No se encuentra el .dat en:\n{AIRFOIL_DAT}")

    if not os.path.isdir(WORK_DIR):
        raise FileNotFoundError(f"No existe la carpeta de trabajo:\n{WORK_DIR}")


def delete_old_outputs():
    # Borrar polar y log antiguos
    for file_path in [POLAR_FILE, XFOIL_LOG]:
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"[INFO] Archivo antiguo borrado: {file_path}")

    # Borrar archivos Cp antiguos
    for filename in os.listdir(WORK_DIR):
        if filename.startswith("cp_alpha_") and filename.endswith(".txt"):
            path = os.path.join(WORK_DIR, filename)
            os.remove(path)
            print(f"[INFO] Cp antiguo borrado: {path}")


def build_xfoil_commands():
    """
    Construye los comandos que normalmente escribiríamos a mano dentro de XFOIL.
    """

    commands = []

    # Cargar perfil
    commands.append(f'LOAD {AIRFOIL_DAT}')

    # Aceptar nombre por defecto si XFOIL lo pide
    commands.append("")

    # Repanelar
    commands.append("PANE")

    # Entrar en modo operación
    commands.append("OPER")

    # Activar viscosidad
    commands.append(f"VISC {REYNOLDS}")

    # Iteraciones
    commands.append(f"ITER {ITERATIONS}")

    # Activar acumulación de polar
    commands.append("PACC")
    commands.append(POLAR_FILE)

    # Segundo archivo dump: vacío
    commands.append("")

    # Ejecutar alphas
    for alpha in ALPHAS:
     commands.append(f"ALFA {alpha}")

    if alpha < 0:
        alpha_tag = f"m{abs(int(alpha))}"
    else:
        alpha_tag = f"p{int(alpha)}"

    cp_file = os.path.join(WORK_DIR, f"cp_alpha_{alpha_tag}.txt")
    commands.append(f"CPWR {cp_file}")

    # Cerrar acumulación de polar
    commands.append("PACC")

    # Salir de OPER y XFOIL
    commands.append("")
    commands.append("QUIT")

    return "\n".join(commands) + "\n"


def run_xfoil():
    check_files()
    delete_old_outputs()

    commands = build_xfoil_commands()

    print("\n[INFO] Comandos enviados a XFOIL:")
    print("--------------------------------")
    print(commands)
    print("--------------------------------")

    print("[INFO] Ejecutando XFOIL...")

    result = subprocess.run(
        [XFOIL_EXE],
        input=commands,
        text=True,
        capture_output=True,
        cwd=WORK_DIR,
        timeout=60
    )

    with open(XFOIL_LOG, "w", encoding="utf-8", errors="ignore") as f:
        f.write("===== STDOUT =====\n")
        f.write(result.stdout or "")
        f.write("\n\n===== STDERR =====\n")
        f.write(result.stderr or "")

    print(f"[INFO] Log guardado en: {XFOIL_LOG}")

    if result.returncode != 0:
        print("[ERROR] XFOIL terminó con error.")
        print(result.stderr)
        return False

    # Dar un pequeño margen a Windows para escribir el archivo
    time.sleep(0.5)

    if not os.path.isfile(POLAR_FILE):
        print("[ERROR] No se ha creado el archivo polar.")
        print(f"Esperado en: {POLAR_FILE}")
        return False

    print(f"[OK] Polar creada correctamente: {POLAR_FILE}")
    return True


def read_polar_file():
    if not os.path.isfile(POLAR_FILE):
        print("[ERROR] No existe la polar para leer.")
        return

    print("\n[POLAR RESULT]")
    print("--------------------------------")

    with open(POLAR_FILE, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    for line in lines:
        print(line.rstrip())

    print("--------------------------------")

def alpha_to_tag(alpha):
    """
    Convierte alpha a nombre seguro de archivo.
    -4  -> m4
     0  -> p0
     4  -> p4
    """
    alpha_int = int(alpha)

    if alpha_int < 0:
        return f"m{abs(alpha_int)}"
    else:
        return f"p{alpha_int}"


def run_xfoil_cp_for_each_alpha():
    """
    Ejecuta XFOIL una vez por cada alpha para guardar Cp individual.
    Esto es más robusto que intentar sacar todos los CPWR en una sola sesión.
    """

    print("\n[INFO] Generando archivos Cp individuales...")

    for alpha in ALPHAS:
        alpha_tag = alpha_to_tag(alpha)
        cp_file = os.path.join(WORK_DIR, f"cp_alpha_{alpha_tag}.txt")

        # Borrar el Cp anterior de ese alpha si existe
        if os.path.exists(cp_file):
            os.remove(cp_file)
            print(f"[INFO] Cp antiguo borrado: {cp_file}")

        commands = []

        commands.append(f"LOAD {AIRFOIL_DAT}")
        commands.append("")
        commands.append("PANE")
        commands.append("OPER")
        commands.append(f"VISC {REYNOLDS}")
        commands.append(f"ITER {ITERATIONS}")
        commands.append(f"ALFA {alpha}")
        commands.append(f"CPWR {cp_file}")
        commands.append("")
        commands.append("QUIT")

        commands_text = "\n".join(commands) + "\n"

        print(f"[INFO] Ejecutando Cp para alpha = {alpha} deg")
        print(f"[INFO] Archivo esperado: {cp_file}")

        result = subprocess.run(
            [XFOIL_EXE],
            input=commands_text,
            text=True,
            capture_output=True,
            cwd=WORK_DIR,
            timeout=60
        )

        if result.returncode != 0:
            print(f"[AVISO] XFOIL devolvió error en alpha = {alpha}")
            print(result.stderr)

        if os.path.isfile(cp_file):
            print(f"[OK] Cp creado: {cp_file}")
        else:
            print(f"[ERROR] No se creó Cp para alpha = {alpha}")

# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":
    alphas_override = parse_alphas_arg(sys.argv)
    if alphas_override is not None:
        ALPHAS = alphas_override
        print(f"[INFO] ALPHAS sobreescrito por argumento: {ALPHAS}")
    else:
        print(f"[INFO] ALPHAS por defecto: {ALPHAS}")

    reynolds_override = parse_reynolds_arg(sys.argv)
    if reynolds_override is not None:
        REYNOLDS = reynolds_override
    print(f"[INFO] REYNOLDS usado: {REYNOLDS}")

    ok = run_xfoil()

    if ok:
        read_polar_file()

        # Nuevo paso: generar Cp individual para cada alpha
        run_xfoil_cp_for_each_alpha()

        print("\n[OK] XFOIL automatizado correctamente.")
    else:
        print("\n[ERROR] No se pudo completar la automatización de XFOIL.")