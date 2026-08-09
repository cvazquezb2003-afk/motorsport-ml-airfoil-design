import json
import os
import subprocess
import sys
import time
import glob
import shutil
from pathlib import Path

# Forzar UTF-8 en stdout para que print() nunca falle con
# caracteres no-cp1252 que vengan del subprocess (ej: �).
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


# =========================================================
# CONFIG GENERAL
# =========================================================

BASE_DIR = Path(__file__).resolve().parent
WORK_DIR = BASE_DIR
PYTHON_EXE = sys.executable

SCRIPT_1_GENERATOR = BASE_DIR / "airfoil_generator.py"
SCRIPT_2_POINTS = BASE_DIR / "airfoil_points.py"
SCRIPT_3_EXPORT_ASC = BASE_DIR / "export_cloud_ascii.py"
SCRIPT_4_ASC_TO_DAT = BASE_DIR / "asc_to_dat.py"
SCRIPT_5_RUN_XFOIL = BASE_DIR / "run_xfoil.py"
SCRIPT_6_PLOT_POLAR = BASE_DIR / "plot_polar.py"
SCRIPT_7_PLOT_CP = BASE_DIR / "plot_cp.py"

OUTPUT_CSV = BASE_DIR / "airfoil_points_xyz.csv"
OUTPUT_ASC = BASE_DIR / "auto_export.asc"
OUTPUT_DAT = BASE_DIR / "airfoil_v4.dat"
OUTPUT_POLAR = BASE_DIR / "polar_v4_auto.txt"
OUTPUT_XFOIL_LOG = BASE_DIR / "xfoil_log.txt"

OUTPUT_POLAR_CL_ALPHA = BASE_DIR / "polar_cl_alpha.png"
OUTPUT_POLAR_CD_ALPHA = BASE_DIR / "polar_cd_alpha.png"
OUTPUT_POLAR_CL_CD = BASE_DIR / "polar_cl_cd.png"
OUTPUT_POLAR_LD_ALPHA = BASE_DIR / "polar_ld_alpha.png"
OUTPUT_POLAR_CM_ALPHA = BASE_DIR / "polar_cm_alpha.png"


# =========================================================
# PARAMETROS POR DEFECTO
# Estos son los valores base del MVP actual
# =========================================================

DEFAULT_USER_PARAMS = {
    "chord_length_mm": 200.0,
    "chord_angle_deg": 350.0,

    "leading_edge_angle_deg": 3.5,
    "leading_edge_thickness_level": 0.5,

    "trailing_edge_angle_deg": 168.0,
    "trailing_edge_thickness_mm": 2.288,

    "te_upr_angle_deg": 10.0,
    "te_lwr_angle_deg": -2.0,
}


DEFAULT_CONFIG = {
    "user_params": DEFAULT_USER_PARAMS,

    # El usuario indica VELOCIDAD(es) en km/h; el Reynolds es una cantidad
    # DERIVADA que el sistema calcula de la cuerda y la velocidad (misma funcion
    # que generate_batch.py). NUNCA se especifica el Reynolds a mano.
    "velocidad_kmh": None,
    "alphas": [-8, -6, -4, -2, 0, 2, 4],
}


# =========================================================
# UTILIDADES
# =========================================================

def print_header(title: str) -> None:
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def remove_if_exists(path: Path) -> None:
    if path.exists():
        try:
            path.unlink()
            print(f"[INFO] Eliminado archivo previo: {path.name}")
        except Exception as e:
            print(f"[AVISO] No se pudo eliminar {path.name}: {e}")


def validate_environment() -> None:
    missing = []

    required_scripts = [
        SCRIPT_1_GENERATOR,
        SCRIPT_2_POINTS,
        SCRIPT_3_EXPORT_ASC,
        SCRIPT_4_ASC_TO_DAT,
        SCRIPT_5_RUN_XFOIL,
        SCRIPT_6_PLOT_POLAR,
        SCRIPT_7_PLOT_CP,
    ]

    for script in required_scripts:
        if not script.exists():
            missing.append(script.name)

    if missing:
        raise FileNotFoundError(
            "Faltan scripts necesarios en la carpeta:\n"
            + "\n".join(f" - {name}" for name in missing)
        )

    print("[OK] Scripts encontrados correctamente.")


def run_step(step_name: str, cmd: list[str], timeout: int | None = None) -> None:
    print_header(f"[STEP] {step_name}")
    print("[CMD]")
    print(" ".join(f'\"{x}\"' if " " in str(x) else str(x) for x in cmd))

    result = subprocess.run(
        cmd,
        cwd=str(BASE_DIR),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )

    if result.stdout:
        print("\n[STDOUT]")
        print(result.stdout)

    if result.stderr:
        print("\n[STDERR]")
        print(result.stderr)

    if result.returncode != 0:
        raise RuntimeError(f"Fallo el paso: {step_name}")


def check_output_exists(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"No se ha generado {label}: {path}")
    print(f"[OK] {label}: {path}")


def clean_previous_outputs() -> None:
    print_header("[CLEAN] Limpiando archivos previos")

    files_to_clean = [
        OUTPUT_CSV,
        OUTPUT_ASC,
        OUTPUT_DAT,
        OUTPUT_POLAR,
        OUTPUT_XFOIL_LOG,
        OUTPUT_POLAR_CL_ALPHA,
        OUTPUT_POLAR_CD_ALPHA,
        OUTPUT_POLAR_CL_CD,
        OUTPUT_POLAR_LD_ALPHA,
        OUTPUT_POLAR_CM_ALPHA,
    ]

    # Limpiar Cp anteriores
    cp_txt_files = glob.glob(str(BASE_DIR / "cp_alpha_*.txt"))
    cp_png_files = glob.glob(str(BASE_DIR / "cp_alpha_*_black.png"))

    for file_path in files_to_clean:
        remove_if_exists(file_path)

    for path_str in cp_txt_files + cp_png_files:
        remove_if_exists(Path(path_str))


def merge_config(config: dict | None = None) -> dict:
    """
    Combina DEFAULT_CONFIG con la config externa recibida.

    Esto permite que más adelante Flask/n8n mande solo algunos valores.
    Ejemplo:
    {
        "user_params": {
            "chord_length_mm": 250
        }
    }

    Y el resto se rellena con defaults.
    """
    final_config = {
        "user_params": DEFAULT_USER_PARAMS.copy(),
        "velocidad_kmh": DEFAULT_CONFIG["velocidad_kmh"],
        "alphas": DEFAULT_CONFIG["alphas"].copy(),
    }

    if not config:
        return final_config

    if "user_params" in config and isinstance(config["user_params"], dict):
        final_config["user_params"].update(config["user_params"])

    if "velocidad_kmh" in config:
        final_config["velocidad_kmh"] = config["velocidad_kmh"]

    # El Reynolds NO se acepta a mano: es una cantidad derivada. Si el usuario lo
    # incluye, se lo explicamos y se ignora (se usara la velocidad para derivarlo).
    if "reynolds" in config:
        print("[AVISO] El número de Reynolds no se especifica manualmente. Se calcula "
              "automáticamente a partir de la cuerda del perfil y de la velocidad de "
              "paso. Por favor, indica una o varias velocidades en km/h "
              "('velocidad_kmh') y el sistema calculará el Reynolds correspondiente a "
              "cada una. (El 'reynolds' recibido en el JSON se ignora.)")

    if "alphas" in config:
        final_config["alphas"] = config["alphas"]

    return final_config


def resolve_velocidades(vel):
    """
    El usuario da VELOCIDAD(es) en km/h; el sistema deriva el Reynolds. Acepta un
    numero o una lista de numeros y devuelve una lista de floats positivos.
    Si no hay ninguna velocidad, lanza un error PEDAGOGICO (no asume nada).
    """
    if vel is None:
        raise ValueError(
            "No se ha indicado ninguna velocidad. Este pipeline necesita al menos "
            "una velocidad en km/h ('velocidad_kmh', p.ej. 180 o [110, 180, 290]): "
            "con ella y la cuerda del perfil el sistema DERIVA el número de Reynolds "
            "de cada condición. No se asume ningún Reynolds por defecto.")
    vels = vel if isinstance(vel, list) else [vel]
    vels = [float(v) for v in vels if isinstance(v, (int, float)) and v > 0]
    if not vels:
        raise ValueError(
            "La velocidad debe ser un número > 0 en km/h (o una lista de ellos), "
            "para poder derivar el Reynolds a partir de la cuerda del perfil.")
    return vels


def validate_config(config: dict) -> list[str]:
    """
    Validación básica del JSON/config de entrada.
    No es agresiva todavía para no romper el MVP.
    """
    errors = []

    user_params = config.get("user_params", {})

    required_user_keys = [
        "chord_length_mm",
        "chord_angle_deg",
        "leading_edge_angle_deg",
        "leading_edge_thickness_level",
        "trailing_edge_angle_deg",
        "trailing_edge_thickness_mm",
        "te_upr_angle_deg",
        "te_lwr_angle_deg",
    ]

    for key in required_user_keys:
        if key not in user_params:
            errors.append(f"Falta user_params.{key}")
        elif not isinstance(user_params[key], (int, float)):
            errors.append(f"user_params.{key} debe ser numérico")

    if errors:
        return errors

    if user_params["chord_length_mm"] <= 0:
        errors.append("user_params.chord_length_mm debe ser mayor que 0")

    if not (0.0 <= user_params["leading_edge_thickness_level"] <= 1.0):
        errors.append("user_params.leading_edge_thickness_level debe estar entre 0 y 1")

    if user_params["trailing_edge_thickness_mm"] <= 0:
        errors.append("user_params.trailing_edge_thickness_mm debe ser mayor que 0")

    # El Reynolds NO se valida como entrada: es derivado. Lo que se valida es la
    # velocidad (si se pasa). La AUSENCIA de velocidad se maneja mas adelante con
    # un mensaje pedagogico en resolve_velocidades, no aqui.
    if "velocidad_kmh" in config and config["velocidad_kmh"] is not None:
        vel = config["velocidad_kmh"]
        vs = vel if isinstance(vel, list) else [vel]
        if not vs or not all(isinstance(v, (int, float)) and v > 0 for v in vs):
            errors.append("velocidad_kmh debe ser un número > 0 en km/h o una lista de ellos")

    if "alphas" in config:
        if not isinstance(config["alphas"], list):
            errors.append("alphas debe ser una lista")
        else:
            for alpha in config["alphas"]:
                if not isinstance(alpha, (int, float)):
                    errors.append("todos los valores de alphas deben ser numéricos")
                    break

    return errors


def collect_outputs() -> dict:
    """
    Recoge las rutas de los archivos generados.
    """
    cp_txt_files = sorted(glob.glob(str(BASE_DIR / "cp_alpha_*.txt")))
    cp_png_files = sorted(glob.glob(str(BASE_DIR / "cp_alpha_*_black.png")))

    return {
        "csv_points": str(OUTPUT_CSV),
        "asc_file": str(OUTPUT_ASC),
        "dat_file": str(OUTPUT_DAT),
        "polar_file": str(OUTPUT_POLAR),
        "xfoil_log": str(OUTPUT_XFOIL_LOG),
        "polar_plots": {
            "cl_alpha": str(OUTPUT_POLAR_CL_ALPHA),
            "cd_alpha": str(OUTPUT_POLAR_CD_ALPHA),
            "cl_cd": str(OUTPUT_POLAR_CL_CD),
            "ld_alpha": str(OUTPUT_POLAR_LD_ALPHA),
            "cm_alpha": str(OUTPUT_POLAR_CM_ALPHA),
        },
        "cp_txt_files": cp_txt_files,
        "cp_plots": cp_png_files,
    }


# =========================================================
# PIPELINE API-READY
# =========================================================

def run_pipeline(config: dict | None = None) -> dict:
    """
    Ejecuta el pipeline completo:

    config/user_params
    -> CATIA
    -> puntos
    -> ASC
    -> DAT
    -> XFOIL
    -> polar
    -> gráficas polar
    -> gráficas Cp

    Devuelve un diccionario preparado para Flask/n8n.
    """

    try:
        print_header("[PIPELINE] AIRFOIL CATIA -> DAT -> XFOIL -> GRAFICAS")
        print(f"[INFO] Carpeta base: {BASE_DIR}")

        final_config = merge_config(config)
        config_errors = validate_config(final_config)

        if config_errors:
            return {
                "status": "error",
                "stage": "config_validation",
                "errors": config_errors,
                "config_used": final_config,
            }

        print_header("[CONFIG] Configuracion usada")
        print(json.dumps(final_config, indent=4))

        validate_environment()
        clean_previous_outputs()

        user_params = final_config["user_params"]
        user_params_json = json.dumps(user_params)

        # -------------------------------------------------
        # STEP 1 - Generar perfil alar en CATIA
        # -------------------------------------------------
        run_step(
            "1) Generar perfil alar en CATIA",
            [
                PYTHON_EXE,
                str(SCRIPT_1_GENERATOR),
                user_params_json,
            ],
            timeout=120,
        )

        print("[OK] Perfil generado en CATIA.")
        time.sleep(1.0)

        # -------------------------------------------------
        # STEP 2 - Crear puntos sobre el perfil
        # -------------------------------------------------
        run_step(
            "2) Crear puntos del perfil en CATIA",
            [
                PYTHON_EXE,
                str(SCRIPT_2_POINTS),
                str(OUTPUT_CSV),
            ],
            timeout=180,
        )

        check_output_exists(OUTPUT_CSV, "CSV de puntos")
        time.sleep(1.0)

        # -------------------------------------------------
        # STEP 3 - Exportar nube de puntos a ASC
        # -------------------------------------------------
        run_step(
            "3) Exportar nube de puntos a ASC",
            [
                PYTHON_EXE,
                str(SCRIPT_3_EXPORT_ASC),
                str(OUTPUT_ASC),
            ],
            timeout=180,
        )

        check_output_exists(OUTPUT_ASC, "Archivo ASC")
        time.sleep(1.0)

        # -------------------------------------------------
        # STEP 4 - Convertir ASC a DAT
        # -------------------------------------------------
        run_step(
            "4) Convertir ASC a DAT para XFOIL",
            [
                PYTHON_EXE,
                str(SCRIPT_4_ASC_TO_DAT),
                str(OUTPUT_ASC),
                str(OUTPUT_DAT),
            ],
            timeout=120,
        )

        check_output_exists(OUTPUT_DAT, "Archivo DAT")
        time.sleep(1.0)

        # -------------------------------------------------
        # STEP 5 - Ejecutar XFOIL (una vez por VELOCIDAD)
        # -------------------------------------------------
        # El Reynolds es DERIVADO: se calcula de la cuerda y la velocidad con la
        # MISMA funcion que generate_batch.py (fuente unica de verdad). Import
        # perezoso para evitar el import circular (generate_batch importa de este
        # modulo). La geometria (Steps 1-4) ya esta hecha una sola vez; aqui solo
        # se re-corre XFOIL por cada velocidad con su Reynolds.
        from generate_batch import compute_reynolds, parse_polar_at_alpha, compute_ld

        chord = final_config["user_params"]["chord_length_mm"]
        velocidades = resolve_velocidades(final_config["velocidad_kmh"])
        alphas = final_config["alphas"]
        alphas_json = json.dumps(alphas)

        resultados_por_velocidad = []
        for v in velocidades:
            reynolds = int(round(compute_reynolds(chord, v)))
            # Aviso TRANSPARENTE de como se derivo el Reynolds:
            print(f"[REYNOLDS] velocidad {v:g} km/h -> Reynolds calculado {reynolds:,} "
                  f"(con cuerda {chord:g} mm)")

            run_step(
                f"5) Ejecutar XFOIL @ {v:g} km/h (Re={reynolds})",
                [
                    PYTHON_EXE,
                    str(SCRIPT_5_RUN_XFOIL),
                    alphas_json,
                    str(reynolds),
                ],
                timeout=120,
            )
            check_output_exists(OUTPUT_POLAR, "Polar XFOIL")

            # Archivar la polar por velocidad para no pisarla entre corridas.
            polar_v = BASE_DIR / f"polar_v{int(round(v))}kmh.txt"
            shutil.copyfile(OUTPUT_POLAR, polar_v)

            # Leer coeficientes por angulo (misma parse/LD que el batch).
            filas = []
            for a in alphas:
                res = parse_polar_at_alpha(OUTPUT_POLAR, a)
                if res is not None:
                    cl, cd, cm = res
                    filas.append({"alpha_deg": a, "CL": cl, "CD": cd,
                                  "LD": compute_ld(cl, cd), "CM": cm, "status": "ok"})
                else:
                    filas.append({"alpha_deg": a, "status": "no_converge"})

            resultados_por_velocidad.append({
                "velocidad_kmh": v,
                "reynolds": reynolds,
                "polar_file": str(polar_v),
                "resultados": filas,
            })

        time.sleep(1.0)

        # -------------------------------------------------
        # STEP 6 - Generar graficas de polar
        # -------------------------------------------------
        run_step(
            "6) Generar graficas de polar",
            [
                PYTHON_EXE,
                str(SCRIPT_6_PLOT_POLAR),
                str(OUTPUT_POLAR),
            ],
            timeout=60,
        )

        check_output_exists(OUTPUT_POLAR_CL_ALPHA, "Grafica CL vs alpha")
        check_output_exists(OUTPUT_POLAR_CD_ALPHA, "Grafica CD vs alpha")
        check_output_exists(OUTPUT_POLAR_CL_CD, "Grafica CL vs CD")
        check_output_exists(OUTPUT_POLAR_LD_ALPHA, "Grafica CL/CD vs alpha")
        check_output_exists(OUTPUT_POLAR_CM_ALPHA, "Grafica CM vs alpha")

        # -------------------------------------------------
        # STEP 7 - Generar graficas Cp estilo XFOIL
        # -------------------------------------------------
        run_step(
            "7) Generar graficas Cp estilo XFOIL",
            [
                PYTHON_EXE,
                str(SCRIPT_7_PLOT_CP),
                "--all",
            ],
            timeout=120,
        )

        outputs = collect_outputs()

        # -------------------------------------------------
        # RESUMEN FINAL
        # -------------------------------------------------
        print_header("[OK] PIPELINE COMPLETADO")

        print("[RESULTADOS]")
        print(f"CSV puntos : {outputs['csv_points']}")
        print(f"ASC        : {outputs['asc_file']}")
        print(f"DAT        : {outputs['dat_file']}")
        print(f"POLAR      : {outputs['polar_file']}")
        print(f"XFOIL log  : {outputs['xfoil_log']}")
        print(f"CL-alpha   : {outputs['polar_plots']['cl_alpha']}")
        print(f"CD-alpha   : {outputs['polar_plots']['cd_alpha']}")
        print(f"CL-CD      : {outputs['polar_plots']['cl_cd']}")
        print(f"L/D-alpha  : {outputs['polar_plots']['ld_alpha']}")
        print(f"CP plots   : {str(BASE_DIR / 'cp_alpha_*_black.png')}")

        print("\n[OK] Automatizacion completa conseguida:")
        print("CATIA -> puntos -> ASC -> DAT -> XFOIL -> polar -> graficas polar -> graficas Cp")

        print("\n[RESULTADOS POR VELOCIDAD] (Reynolds derivado de cuerda + velocidad)")
        for rv in resultados_por_velocidad:
            print(f"  - {rv['velocidad_kmh']:g} km/h  Re={rv['reynolds']:,}")
            for fila in rv["resultados"]:
                if fila.get("status") == "ok":
                    print(f"      alpha {fila['alpha_deg']:>4}: "
                          f"CL={fila['CL']:.4f}  CD={fila['CD']:.5f}  L/D={fila['LD']:.2f}")
                else:
                    print(f"      alpha {fila['alpha_deg']:>4}: no converge")

        return {
            "status": "ok",
            "message": "Pipeline completed successfully",
            "config_used": final_config,
            "resultados_por_velocidad": resultados_por_velocidad,
            "outputs": outputs,
        }

    except subprocess.TimeoutExpired as e:
        print_header("[ERROR] TIMEOUT")
        print(f"Un paso ha tardado demasiado y se ha detenido:\n{e}")

        return {
            "status": "error",
            "stage": "timeout",
            "message": str(e),
        }

    except Exception as e:
        print_header("[ERROR] PIPELINE FALLIDO")
        print(str(e))

        return {
            "status": "error",
            "stage": "pipeline",
            "message": str(e),
        }


# =========================================================
# MAIN
# Permite ejecutar:
#
# 1) Sin JSON:
#    python pipeline_airfoil_api_ready.py
#
# 2) Con JSON:
#    python pipeline_airfoil_api_ready.py "{\"user_params\":{\"chord_length_mm\":250}}"
# =========================================================

def main() -> int:
    config = None

    if len(sys.argv) > 1:
        json_arg = sys.argv[1]

        try:
            config = json.loads(json_arg)
        except json.JSONDecodeError as e:
            print_header("[ERROR] JSON INVALIDO")
            print(str(e))
            return 1

        if not isinstance(config, dict):
            print_header("[ERROR] JSON INVALIDO")
            print("El JSON de entrada debe ser un objeto.")
            return 1

    result = run_pipeline(config)

    print_header("[JSON RESULT]")
    print(json.dumps(result, indent=4, default=str))

    return 0 if result.get("status") == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())