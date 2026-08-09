"""
generate_batch.py
=================

Genera lotes de perfiles alares para construir un dataset.

Dos modos:

1) Aleatorio:
       python generate_batch.py --random 10

   Sortea (uniforme) los 7 parametros de forma dentro de rangos fijos.
   Solo chord_angle_deg se mantiene siempre fijo.

2) Manual:
       python generate_batch.py --manual perfiles.json

   Lee un JSON con una lista de diccionarios de parametros y procesa
   cada uno tal cual viene, sin sortear nada.

Dataset MULTI-ANGULO + BARRIDO DE REYNOLDS con BARRIDO DE ANGULOS ESCALONADO
POR VELOCIDAD: cada perfil es UNA sola geometria de CATIA, evaluada en XFOIL a 3
velocidades (VELOCITIES_KMH = [110,180,290]) y, en cada una, a su PROPIA lista de
angulos (VELOCITY_ALPHAS): 110->6, 180->7, 290->8 angulos. Son 6+7+8 = 21
condiciones por perfil; UNA fila por condicion. (A mas velocidad/Reynolds la
perdida se retrasa, asi que a alta velocidad se barren angulos mas agresivos.)

El Reynolds se calcula por perfil para cada velocidad con
Re = rho*V*L/mu (L = cuerda en metros, V en m/s), asi que depende de la cuerda.

Para cada perfil:
    - Genera un run_id unico (indice + timestamp). Las 21 filas del perfil
      comparten ese run_id; la clave de fila es (run_id, alpha_deg, velocidad_kmh).
    - Llama a run_pipeline() UNA vez SOLO para generar la geometria (el DAT).
    - Re-corre XFOIL en proceso 3 veces (una por velocidad), fijando
      run_xfoil.REYNOLDS al Re calculado y run_xfoil.ALPHAS a los angulos de esa
      velocidad (VELOCITY_ALPHAS[v]).
    - Para cada (angulo, velocidad), si la polar tiene su fila: extrae CL/CD/CM,
      calcula L/D y anade una fila ok (con velocidad_kmh y reynolds).
    - Convergencia PARCIAL: cada combinacion (angulo, velocidad) se registra por
      separado (ok / error_xfoil_no_converge). No se descarta el perfil entero.
    - Si la geometria falla (no hay DAT), las 21 filas se clasifican con la causa
      (sin inventar): error_catia (Steps 1/2/3) o error_otro. El mensaje original
      del pipeline va en error_detail. El lote continua sin detenerse.

Ademas, tras procesar cada perfil (ok o fallo), se archivan los archivos
clave que existan (DAT, polar y ASC) en:
    dataset_runs/{run_id}/
para poder inspeccionar cualquier perfil del dataset mas adelante.

El dataset se va acumulando (append, nunca sobrescribe) en:
    airfoil_dataset.csv
"""

import sys
import csv
import json
import random
import warnings
import shutil
import argparse
from datetime import datetime
from pathlib import Path

import numpy as np
from scipy.stats import qmc

from pipeline_airfoil_api import (
    run_pipeline,
    OUTPUT_POLAR,
    OUTPUT_DAT,
    OUTPUT_ASC,
)

# Se importa el modulo de XFOIL para re-correrlo en proceso con un Reynolds
# concreto por velocidad (fijando run_xfoil.REYNOLDS y run_xfoil.ALPHAS antes
# de cada corrida). Importar el modulo no ejecuta nada (tiene guard __main__).
import run_xfoil


# =========================================================
# CONFIG
# =========================================================

BASE_DIR = Path(__file__).resolve().parent
DATASET_CSV = BASE_DIR / "airfoil_dataset.csv"

# Carpeta donde se archiva, por run_id, una copia de los archivos clave
# (DAT / polar / ASC) de cada perfil, para poder inspeccionarlos despues.
DATASET_RUNS_DIR = BASE_DIR / "dataset_runs"

# Solo chord_angle_deg se mantiene fijo siempre.
FIXED_PARAMS = {
    "chord_angle_deg": 350.0,
}

# --- Barrido de Reynolds variable ---------------------------------------
# El Reynolds ya NO es fijo: se calcula por perfil a partir de su cuerda y de
# una velocidad de paso por curva, con aire estandar a nivel del mar.
#     Re = (rho * V * L) / mu
# donde L = cuerda en METROS (la cuerda del dataset esta en mm -> /1000) y
# V = velocidad en m/s (las velocidades estan en km/h -> /3.6).
AIR_RHO = 1.225        # densidad del aire [kg/m3]
AIR_MU = 1.81e-5       # viscosidad dinamica del aire [Pa.s]

# Barrido de angulos DEPENDIENTE de la velocidad. Cada velocidad de paso por
# curva tiene su PROPIA lista de angulos de ataque: a mas velocidad (mas
# Reynolds) la perdida se retrasa, asi que se barren angulos mas agresivos.
# Cada velocidad da ademas un Reynolds distinto por perfil (depende de la cuerda).
VELOCITY_ALPHAS = {
    110: [0, -2, -4, -6, -8, -10],
    180: [0, -2, -4, -6, -8, -10, -12],
    290: [0, -2, -4, -6, -8, -10, -12, -14],
}
VELOCITIES_KMH = list(VELOCITY_ALPHAS.keys())


def compute_reynolds(chord_length_mm: float, velocity_kmh: float) -> float:
    """Re = rho * V * L / mu, con L en metros (mm/1000) y V en m/s (kmh/3.6)."""
    L = chord_length_mm / 1000.0     # mm -> m
    V = velocity_kmh / 3.6           # km/h -> m/s
    return AIR_RHO * V * L / AIR_MU

# Rangos exactos para el modo aleatorio (distribucion uniforme).
# Rango soportado de cuerda: 150-500 mm. Por debajo de 150 mm el Reynolds es
# demasiado bajo y XFOIL no converge de forma fiable (franja 100-150 excluida).
SHAPE_PARAM_RANGES = {
    "chord_length_mm": (150.0, 500.0),
    "leading_edge_angle_deg": (3.0, 10.0),
    "leading_edge_thickness_level": (0.2, 1.0),
    "trailing_edge_angle_deg": (158.0, 167.0),
    "trailing_edge_thickness_mm": (1.0, 4.0),
    "te_upr_angle_deg": (5.0, 15.0),
    "te_lwr_angle_deg": (-8.0, 4.0),
}

# Orden canonico de los 7 parametros de forma (para columnas del dataset).
SHAPE_PARAM_KEYS = list(SHAPE_PARAM_RANGES.keys())

# Las filas de un perfil comparten run_id (= identificador del perfil) y se
# distinguen por (alpha_deg, velocidad_kmh). Los angulos por velocidad estan en
# VELOCITY_ALPHAS (arriba); el barrido es escalonado por velocidad.

# Columnas del dataset, en orden.
# 'status' ahora distingue la causa del fallo (ok / error_catia /
# error_xfoil_no_converge / error_otro) y 'error_detail' guarda el mensaje
# original que reporto run_pipeline cuando algo falla.
DATASET_COLUMNS = (
    ["run_id", "timestamp", "source"]
    + SHAPE_PARAM_KEYS
    + ["alpha_deg", "velocidad_kmh", "reynolds",
       "CL", "CD", "CM", "LD", "status", "error_detail"]
)


# =========================================================
# PARAMETROS
# =========================================================

def sample_random_shape_params() -> dict:
    """Sortea los 6 parametros de forma con distribucion uniforme."""
    params = {}
    for key, (low, high) in SHAPE_PARAM_RANGES.items():
        params[key] = round(random.uniform(low, high), 6)
    return params


# =========================================================
# MUESTREO SOBOL (cuasi-aleatorio, continuable)
# =========================================================
# A diferencia de --random (uniforme independiente por parametro), Sobol reparte
# los puntos de forma uniforme por todo el espacio 7D -> mejor cobertura con las
# mismas N muestras. Sobol SOLO decide que geometrias se generan; el barrido de
# angulos/velocidades y el Reynolds NO cambian.
SOBOL_SEED = 20260711          # semilla fija (registrada) -> diseno reproducible
SOBOL_STATE_FILE = BASE_DIR / "sobol_state.json"


def _load_sobol_state() -> dict:
    """Estado de la secuencia: semilla + cuantos puntos se han consumido ya."""
    if SOBOL_STATE_FILE.is_file():
        with open(SOBOL_STATE_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)
        # Si alguien cambia la semilla, la cuenta antigua deja de ser valida.
        if state.get("seed") != SOBOL_SEED:
            print(f"[SOBOL][WARN] La semilla del estado ({state.get('seed')}) no "
                  f"coincide con SOBOL_SEED ({SOBOL_SEED}). Reinicio la cuenta a 0.")
            return {"seed": SOBOL_SEED, "consumed": 0}
        return state
    return {"seed": SOBOL_SEED, "consumed": 0}


def _save_sobol_state(consumed: int) -> None:
    with open(SOBOL_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump({"seed": SOBOL_SEED, "consumed": consumed,
                   "updated": datetime.now().isoformat(timespec="seconds")},
                  f, indent=2)


def sample_sobol_shape_params(n: int, advance_state: bool = True) -> list:
    """
    Devuelve una lista de n dicts de parametros de forma tomados de la secuencia
    Sobol, CONTINUANDO donde termino el lote anterior.

    Continuidad: el fichero sobol_state.json guarda 'consumed' = cuantos puntos de
    la secuencia se han emitido hasta ahora. Reconstruimos el MISMO generador
    Sobol (misma semilla), saltamos esos 'consumed' puntos con fast_forward() y
    emitimos los n siguientes. Asi cada tanda arranca donde acabo la previa y
    nunca se repiten puntos. Si advance_state=True se persiste consumed += n
    (usar False para una vista previa que NO deba consumir la secuencia).
    """
    state = _load_sobol_state()
    consumed = state["consumed"]

    keys = SHAPE_PARAM_KEYS
    lows = np.array([SHAPE_PARAM_RANGES[k][0] for k in keys], dtype=float)
    highs = np.array([SHAPE_PARAM_RANGES[k][1] for k in keys], dtype=float)

    sampler = qmc.Sobol(d=len(keys), scramble=True, seed=SOBOL_SEED)
    if consumed:
        sampler.fast_forward(consumed)          # salta lo ya emitido
    # Emitimos N arbitrario a proposito (un lote = N perfiles). El aviso de Sobol
    # sobre "n potencia de 2" no aplica a nuestro uso; lo silenciamos.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=UserWarning)
        unit = sampler.random(n)                 # n x 7 en [0,1)
    scaled = qmc.scale(unit, lows, highs)        # a los rangos reales

    out = []
    for row in scaled:
        out.append({k: round(float(v), 6) for k, v in zip(keys, row)})

    if advance_state:
        _save_sobol_state(consumed + n)
        print(f"[SOBOL] secuencia: consumidos {consumed} -> {consumed + n} "
              f"(seed={SOBOL_SEED}, estado en {SOBOL_STATE_FILE.name})")
    else:
        print(f"[SOBOL][preview] mostraria puntos {consumed}..{consumed + n} "
              f"SIN avanzar el estado (seed={SOBOL_SEED})")
    return out


# =========================================================
# MUESTREO SOBOL POR BANDA DE CUERDA (rango ampliado / extremos)
# =========================================================
# Para cubrir extremos de cuerda (retrovisores ~100mm, alas grandes ~500mm) sin
# malgastar perfiles en el centro 200-400 (ya poblado), se genera SOLO en las
# bandas nuevas. Cada banda tiene su PROPIA secuencia Sobol (semilla + estado
# independientes), asi que NO interfiere con la secuencia principal
# (sobol_state.json, consumed=400), que queda intacta y continuable. Solo cambia
# el rango de la CUERDA; los otros 6 parametros usan sus rangos normales, y el
# barrido de angulos/velocidades y el Reynolds derivado NO cambian.
CHORD_BANDS = {
    "high": {"chord_range": (400.0, 500.0), "seed": 20260712,
             "state": BASE_DIR / "sobol_state_ext_high.json", "source": "sobol_ext_high"},
    # Banda baja recortada a 150-200: por debajo de 150 mm XFOIL no es fiable
    # (Reynolds demasiado bajo), asi que 100-150 queda fuera del rango soportado.
    "low":  {"chord_range": (150.0, 200.0), "seed": 20260713,
             "state": BASE_DIR / "sobol_state_ext_low.json",  "source": "sobol_ext_low"},
}


def _load_band_state(state_file, seed) -> int:
    if state_file.is_file():
        with open(state_file, "r", encoding="utf-8") as f:
            st = json.load(f)
        if st.get("seed") != seed:
            print(f"[SOBOL-BANDA][WARN] semilla del estado ({st.get('seed')}) != {seed}. "
                  f"Reinicio la cuenta a 0.")
            return 0
        return st.get("consumed", 0)
    return 0


def _save_band_state(state_file, seed, consumed) -> None:
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump({"seed": seed, "consumed": consumed,
                   "updated": datetime.now().isoformat(timespec="seconds")}, f, indent=2)


def sample_sobol_band(n: int, band_key: str) -> list:
    """
    Como sample_sobol_shape_params, pero escalando la CUERDA al rango de la banda
    (CHORD_BANDS[band_key]) y usando la secuencia Sobol PROPIA de esa banda
    (semilla + estado independientes, continuables). Los otros 6 parametros usan
    sus rangos normales de SHAPE_PARAM_RANGES.
    """
    band = CHORD_BANDS[band_key]
    seed, state_file = band["seed"], band["state"]
    consumed = _load_band_state(state_file, seed)

    keys = SHAPE_PARAM_KEYS
    lows, highs = [], []
    for k in keys:
        if k == "chord_length_mm":
            lo, hi = band["chord_range"]           # cuerda a la banda
        else:
            lo, hi = SHAPE_PARAM_RANGES[k]         # resto, rango normal
        lows.append(lo); highs.append(hi)
    lows = np.array(lows, dtype=float); highs = np.array(highs, dtype=float)

    sampler = qmc.Sobol(d=len(keys), scramble=True, seed=seed)
    if consumed:
        sampler.fast_forward(consumed)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=UserWarning)
        unit = sampler.random(n)
    scaled = qmc.scale(unit, lows, highs)

    out = [{k: round(float(v), 6) for k, v in zip(keys, row)} for row in scaled]
    _save_band_state(state_file, seed, consumed + n)
    print(f"[SOBOL-BANDA '{band_key}'] cuerda {band['chord_range']} | secuencia "
          f"{consumed} -> {consumed + n} (seed={seed}, estado {state_file.name})")
    return out


def build_config(shape_params: dict) -> dict:
    """
    Combina los parametros de forma con los fijos (chord) y devuelve
    el config que espera run_pipeline. Los valores explicitos en
    shape_params tienen prioridad sobre los fijos.
    """
    user_params = dict(FIXED_PARAMS)
    user_params.update(shape_params)

    return {
        "user_params": user_params,
        # run_pipeline solo se usa para generar la GEOMETRIA (el DAT); su XFOIL
        # interno se descarta (re-corremos XFOIL por velocidad). Pasamos [0] para
        # que esa corrida interna desechada sea minima.
        "alphas": [0],
    }


# =========================================================
# LECTURA DE LA POLAR
# =========================================================

def parse_polar_at_alpha(polar_path, target_alpha, tol=0.5):
    """
    Lee un archivo polar de XFOIL y devuelve (CL, CD, CM) en la fila
    correspondiente a target_alpha.

    Formato de columnas esperado:
        alpha  CL  CD  CDp  CM  Top_Xtr  Bot_Xtr

    Devuelve None si no hay ninguna fila para ese alpha. IMPORTANTE para
    multi-alpha: si la fila mas cercana esta a mas de `tol` grados del alpha
    pedido, ese angulo concreto NO convergio y devolvemos None (no colamos los
    coeficientes de un angulo vecino). Los alphas estan separados 2 grados, asi
    que tol=0.5 distingue "presente" (diff ~0) de "ausente" (diff >= 2).
    """
    polar_path = Path(polar_path)
    if not polar_path.is_file():
        return None

    best = None
    best_diff = None

    with open(polar_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            parts = line.split()

            # Una fila de datos empieza por un numero (el alpha).
            if len(parts) < 5:
                continue

            try:
                alpha = float(parts[0])
                cl = float(parts[1])
                cd = float(parts[2])
                cm = float(parts[4])
            except ValueError:
                # Cabeceras, separadores, texto: se ignoran.
                continue

            diff = abs(alpha - target_alpha)
            if best_diff is None or diff < best_diff:
                best_diff = diff
                best = (cl, cd, cm)

    if best is None:
        return None

    # Si la fila mas cercana esta mas lejos que tol, ese alpha no convergio:
    # devolvemos None para que se registre como error_xfoil_no_converge y NO
    # se confunda con los coeficientes de un angulo vecino.
    if best_diff is not None and best_diff > tol:
        return None

    return best


def compute_ld(cl, cd):
    """L/D con proteccion frente a CD = 0."""
    if cd is None or abs(cd) < 1e-12:
        return None
    return cl / cd


# =========================================================
# ESCRITURA DEL DATASET
# =========================================================

def append_dataset_row(row: dict) -> None:
    """
    Anade una fila al dataset (modo append). Escribe la cabecera solo
    si el archivo aun no existe.
    """
    file_exists = DATASET_CSV.exists()

    with open(DATASET_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=DATASET_COLUMNS, delimiter=",")
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


def build_row(run_id, timestamp, source, user_params, alpha,
              velocidad_kmh=None, reynolds=None,
              cl=None, cd=None, cm=None, ld=None, status="error",
              error_detail="") -> dict:
    """Construye una fila del dataset a partir de los datos disponibles."""
    # Aplanamos el mensaje a una sola linea para no romper el CSV.
    error_detail = " ".join((error_detail or "").split())

    row = {
        "run_id": run_id,
        "timestamp": timestamp,
        "source": source,
        "alpha_deg": alpha,
        "velocidad_kmh": "" if velocidad_kmh is None else velocidad_kmh,
        "reynolds": "" if reynolds is None else f"{reynolds:.0f}",
        "CL": "" if cl is None else f"{cl:.6f}",
        "CD": "" if cd is None else f"{cd:.6f}",
        "CM": "" if cm is None else f"{cm:.6f}",
        "LD": "" if ld is None else f"{ld:.6f}",
        "status": status,
        "error_detail": error_detail,
    }

    for key in SHAPE_PARAM_KEYS:
        value = user_params.get(key, "")
        row[key] = value

    return row


# =========================================================
# CLASIFICACION DE LA CAUSA DEL FALLO
# =========================================================

def classify_failure(result: dict, pipeline_status) -> str:
    """
    Decide el 'status' de una fila cuando la polar NO dio datos validos.

    Se basa EXCLUSIVAMENTE en lo que run_pipeline reporta (status, stage y
    message). No infiere causas que el pipeline no respalde.

    run_pipeline mete el Step que fallo dentro de 'message', con una de dos
    formas:
        - "Fallo el paso: N) ..."           (RuntimeError de run_step)
        - "No se ha generado <etiqueta>: ..." (check_output_exists)

    Devuelve:
        - "error_catia"             -> fallo en Steps 1/2/3 (geometria/export CATIA)
        - "error_xfoil_no_converge" -> llego a XFOIL pero la polar quedo sin fila
        - "error_otro"              -> no se puede determinar con seguridad
    """
    # Si el pipeline completo TODO (status ok) pero aun asi no hay fila en la
    # polar para el alpha pedido, es que XFOIL corrio y no convergio.
    if pipeline_status == "ok":
        return "error_xfoil_no_converge"

    stage = result.get("stage")

    # Validacion de config: ni siquiera se ejecuto ningun Step.
    if stage == "config_validation":
        return "error_otro"

    message = (result.get("message") or "").lower()

    # Marcadores de los Steps de geometria/export en CATIA (1, 2 y 3).
    catia_markers = (
        "1) generar perfil",
        "2) crear puntos",
        "3) exportar nube",
        "csv de puntos",   # check_output_exists del Step 2
        "archivo asc",     # check_output_exists del Step 3
    )
    # Marcadores de XFOIL y de las graficas que dependen de la polar.
    # Una polar vacia no tumba el Step 5 (el archivo existe), sino que
    # revienta aguas abajo en el Step 6 (graficas de polar).
    xfoil_markers = (
        "5) ejecutar xfoil",
        "polar xfoil",          # check_output_exists del Step 5
        "6) generar graficas",  # plot_polar sobre polar vacia
        "7) generar graficas",
    )

    if any(m in message for m in catia_markers):
        return "error_catia"

    if any(m in message for m in xfoil_markers):
        return "error_xfoil_no_converge"

    # Cualquier otra cosa (p.ej. fallo en el Step 4 ASC->DAT, timeout sin
    # Step identificable, excepcion inesperada): no lo forzamos a una causa.
    return "error_otro"


# =========================================================
# ARCHIVADO DE ARCHIVOS POR PERFIL
# =========================================================

def archive_run_files(run_id: str) -> list:
    """
    Copia a dataset_runs/{run_id}/ los archivos clave que existan de esta
    ejecucion: el .dat, la polar y el .asc. Los que falten (porque el perfil
    fallo antes de generarlos) se ignoran sin error.

    Nota: run_pipeline limpia estos archivos al INICIO de cada ejecucion, asi
    que los que esten en disco ahora pertenecen al perfil recien procesado.

    Devuelve la lista de nombres de archivo realmente copiados.
    """
    dest_dir = DATASET_RUNS_DIR / run_id
    dest_dir.mkdir(parents=True, exist_ok=True)

    archived = []
    for src in (OUTPUT_DAT, OUTPUT_POLAR, OUTPUT_ASC):
        src_path = Path(src)
        try:
            if src_path.is_file():
                shutil.copy2(src_path, dest_dir / src_path.name)
                archived.append(src_path.name)
        except Exception as e:
            print(f"[WARN] No se pudo archivar {src_path.name}: {e}")

    return archived


# =========================================================
# PROCESADO DE UN PERFIL
# =========================================================

def process_one(idx: int, shape_params: dict, source: str) -> bool:
    """
    Procesa un unico perfil de principio a fin y anade su fila al
    dataset. Devuelve True si tuvo exito, False si fallo.
    """
    timestamp = datetime.now().isoformat(timespec="seconds")
    ts_compact = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_id = f"{idx:04d}_{ts_compact}"

    config = build_config(shape_params)
    user_params = config["user_params"]
    chord_mm = float(user_params["chord_length_mm"])

    # (velocidad_kmh, Reynolds) de este perfil. El Re depende de la cuerda.
    vel_re = [(v, compute_reynolds(chord_mm, v)) for v in VELOCITIES_KMH]
    # Total de condiciones del perfil = suma de angulos sobre las velocidades.
    n_cond = sum(len(VELOCITY_ALPHAS[v]) for v in VELOCITIES_KMH)

    print("\n" + "#" * 80)
    print(f"# PERFIL {idx} | run_id = {run_id} | source = {source}")
    print(f"# params = {json.dumps(shape_params)}")
    print(f"# barrido escalonado ({n_cond} condiciones): "
          + " | ".join(f"{v}km/h {VELOCITY_ALPHAS[v]}" for v in VELOCITIES_KMH))
    print(f"# Reynolds = " + ", ".join(f"{v}km/h->{Re:.0f}" for v, Re in vel_re))
    print("#" * 80)

    # --- Geometria: se genera UNA sola vez con run_pipeline ---
    try:
        result = run_pipeline(config)
    except Exception as e:
        print(f"[ERROR] run_pipeline lanzo una excepcion: {e}")
        result = {"status": "error", "stage": "pipeline", "message": str(e)}
    pipeline_status = result.get("status")

    # La geometria esta lista si existe el DAT (Step 4). Que la XFOIL/graficas
    # INTERNAS de run_pipeline fallen no importa: re-corremos XFOIL nosotros con
    # el Reynolds de cada velocidad. (Esa corrida interna a Re=1e6 es trabajo
    # desechado; conocido y aparcado para optimizar.)
    geometry_ok = Path(OUTPUT_DAT).is_file()

    if not geometry_ok:
        # Geometria fallida (CATIA Steps 1/2/3, o ASC->DAT). TODAS las condiciones
        # (angulos x velocidades, segun el barrido escalonado) con esa causa.
        fail_status = classify_failure(result, pipeline_status)
        detail = result.get("message", "") or ""
        print(f"[FALLO] Perfil {idx}: geometria no generada -> status={fail_status}. "
              f"Se registran {n_cond} filas con ese estado.")
        for v, Re in vel_re:
            for a in VELOCITY_ALPHAS[v]:
                row = build_row(run_id, timestamp, source, user_params, a,
                                velocidad_kmh=v, reynolds=Re,
                                status=fail_status, error_detail=detail)
                append_dataset_row(row)
        archive_run_files(run_id)
        return False

    # --- Geometria OK: XFOIL una vez por velocidad (Reynolds distinto) ---
    (DATASET_RUNS_DIR / run_id).mkdir(parents=True, exist_ok=True)
    n_ok = 0
    n_total = 0
    resumen = []
    for v, Re in vel_re:
        alphas_v = VELOCITY_ALPHAS[v]
        # Re-corremos XFOIL en proceso fijando los angulos de ESTA velocidad y su
        # Reynolds.
        run_xfoil.ALPHAS = list(alphas_v)
        run_xfoil.REYNOLDS = int(round(Re))
        try:
            run_xfoil.run_xfoil()
        except Exception as e:
            print(f"[WARN] XFOIL fallo a v={v} km/h (Re={Re:.0f}): {e}")

        # Una fila por angulo para esta velocidad. Convergencia parcial: cada
        # combinacion (angulo, velocidad) se registra por separado.
        v_ok = 0
        for a in alphas_v:
            n_total += 1
            coeffs = parse_polar_at_alpha(OUTPUT_POLAR, a)
            if coeffs is not None:
                cl, cd, cm = coeffs
                ld = compute_ld(cl, cd)
                row = build_row(run_id, timestamp, source, user_params, a,
                                velocidad_kmh=v, reynolds=Re,
                                cl=cl, cd=cd, cm=cm, ld=ld, status="ok")
                n_ok += 1
                v_ok += 1
            else:
                row = build_row(
                    run_id, timestamp, source, user_params, a,
                    velocidad_kmh=v, reynolds=Re,
                    status="error_xfoil_no_converge",
                    error_detail=(f"alpha {a} a v={v} km/h (Re={Re:.0f}) "
                                  f"sin fila en la polar (no convergio)"))
            append_dataset_row(row)

        # Archivar la polar de esta velocidad (con nombre etiquetado).
        try:
            shutil.copy2(OUTPUT_POLAR,
                         DATASET_RUNS_DIR / run_id / f"polar_v{v}kmh.txt")
        except Exception as e:
            print(f"[WARN] No se pudo archivar la polar de v={v}: {e}")

        resumen.append(f"v{v}(Re={Re/1e6:.2f}M):{v_ok}/{len(alphas_v)}")

    # Archivar geometria del perfil (DAT/ASC).
    archive_run_files(run_id)
    print(f"[PERFIL {idx}] {n_ok}/{n_total} condiciones ok | " + " ".join(resumen))

    # 'exito' del perfil = al menos una condicion (angulo, velocidad) convergio.
    return n_ok > 0


# =========================================================
# LOTES
# =========================================================

def run_random_batch(n: int) -> tuple:
    """Genera n perfiles aleatorios. Devuelve (exitos, fallos)."""
    success = 0
    fail = 0

    for i in range(1, n + 1):
        shape_params = sample_random_shape_params()
        ok = process_one(i, shape_params, source="random")
        if ok:
            success += 1
        else:
            fail += 1

    return success, fail


def run_sobol_batch(n: int) -> tuple:
    """
    Genera n perfiles con muestreo Sobol continuable. La geometria es lo unico
    que cambia respecto a --random; el resto del pipeline (angulos, velocidades,
    Reynolds) es identico. Devuelve (exitos, fallos).
    """
    shape_list = sample_sobol_shape_params(n, advance_state=True)
    success = 0
    fail = 0
    for i, shape_params in enumerate(shape_list, start=1):
        ok = process_one(i, shape_params, source="sobol")
        if ok:
            success += 1
        else:
            fail += 1
    return success, fail


def run_sobol_band_batch(n: int, band_key: str) -> tuple:
    """
    Genera n perfiles en una banda de cuerda (extremos de rango ampliado), con la
    secuencia Sobol propia de la banda y etiquetados con su source
    (sobol_ext_high / sobol_ext_low). Devuelve (exitos, fallos).
    """
    band = CHORD_BANDS[band_key]
    shape_list = sample_sobol_band(n, band_key)
    success = 0
    fail = 0
    for i, shape_params in enumerate(shape_list, start=1):
        ok = process_one(i, shape_params, source=band["source"])
        if ok:
            success += 1
        else:
            fail += 1
    return success, fail


def run_manual_batch(json_path: str) -> tuple:
    """
    Lee una lista de diccionarios de parametros desde un JSON y procesa
    cada uno tal cual. Devuelve (exitos, fallos).
    """
    path = Path(json_path)
    if not path.is_file():
        raise FileNotFoundError(f"No existe el archivo manual: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("El JSON manual debe ser una lista de diccionarios.")

    success = 0
    fail = 0

    for i, entry in enumerate(data, start=1):
        if not isinstance(entry, dict):
            print(f"[WARN] Entrada {i} no es un diccionario. Se omite.")
            fail += 1
            continue

        ok = process_one(i, entry, source="manual")
        if ok:
            success += 1
        else:
            fail += 1

    return success, fail


# =========================================================
# MAIN
# =========================================================

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Genera lotes de perfiles alares para construir un dataset."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--random",
        type=int,
        metavar="N",
        help="Genera N perfiles con parametros aleatorios.",
    )
    group.add_argument(
        "--sobol",
        type=int,
        metavar="N",
        help="Genera N perfiles con muestreo Sobol (cobertura uniforme, "
             "secuencia continuable). No afecta a --random.",
    )
    group.add_argument(
        "--manual",
        type=str,
        metavar="PERFILES.JSON",
        help="Procesa los perfiles definidos en un archivo JSON (lista de dicts).",
    )
    group.add_argument(
        "--sobol-extremos",
        type=int,
        nargs=2,
        metavar=("N_HIGH", "N_LOW"),
        help="Genera N_HIGH perfiles con cuerda 400-500 y N_LOW con cuerda 100-200 "
             "(bandas extremas de rango ampliado), cada banda con su secuencia Sobol "
             "propia. No afecta a la secuencia Sobol principal.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Solo genera e imprime los parametros de forma (no corre CATIA ni "
             "toca el dataset ni el estado Sobol). Util para inspeccionar la "
             "cobertura del muestreo antes de lanzar un lote.",
    )

    args = parser.parse_args()

    # -------------------------------------------------
    # DRY-RUN: solo parametros, sin pipeline
    # -------------------------------------------------
    if args.dry_run:
        if args.manual is not None:
            print("[ERROR] --dry-run solo aplica a --random / --sobol.")
            return 1
        n = args.random if args.random is not None else args.sobol
        if n is None or n <= 0:
            print("[ERROR] --dry-run requiere --random N o --sobol N (N > 0).")
            return 1
        if args.sobol is not None:
            print(f"[DRY-RUN] {n} perfiles SOBOL (sin avanzar el estado)")
            shapes = sample_sobol_shape_params(n, advance_state=False)
        else:
            print(f"[DRY-RUN] {n} perfiles ALEATORIOS")
            shapes = [sample_random_shape_params() for _ in range(n)]
        print(json.dumps(shapes, indent=2))
        return 0

    print("=" * 80)
    print("[GENERATE BATCH] Construccion de dataset de perfiles alares")
    print(f"[INFO] Dataset destino: {DATASET_CSV}")
    print("=" * 80)

    results = {}

    if args.random is not None:
        if args.random <= 0:
            print("[ERROR] --random debe ser un entero positivo.")
            return 1
        print(f"[MODO] Aleatorio: {args.random} perfiles")
        success, fail = run_random_batch(args.random)
        results["random"] = (success, fail)

    elif args.sobol is not None:
        if args.sobol <= 0:
            print("[ERROR] --sobol debe ser un entero positivo.")
            return 1
        print(f"[MODO] Sobol: {args.sobol} perfiles")
        success, fail = run_sobol_batch(args.sobol)
        results["sobol"] = (success, fail)

    elif args.sobol_extremos is not None:
        n_high, n_low = args.sobol_extremos
        if n_high < 0 or n_low < 0 or (n_high + n_low) == 0:
            print("[ERROR] --sobol-extremos requiere dos enteros >= 0 y no ambos cero.")
            return 1
        print(f"[MODO] Sobol extremos: {n_high} en cuerda 400-500, {n_low} en 100-200")
        # Orden alta -> baja: la banda de Re bajo (mas fragil) va al final.
        if n_high > 0:
            oh, fh = run_sobol_band_batch(n_high, "high")
            results["sobol_ext_high"] = (oh, fh)
        if n_low > 0:
            ol, fl = run_sobol_band_batch(n_low, "low")
            results["sobol_ext_low"] = (ol, fl)

    elif args.manual is not None:
        print(f"[MODO] Manual: {args.manual}")
        success, fail = run_manual_batch(args.manual)
        results["manual"] = (success, fail)

    # -------------------------------------------------
    # RESUMEN FINAL
    # -------------------------------------------------
    print("\n" + "=" * 80)
    print("[RESUMEN FINAL]")
    print("=" * 80)

    total_ok = 0
    total_fail = 0

    for mode, (ok, fail) in results.items():
        total = ok + fail
        total_ok += ok
        total_fail += fail
        print(f"  Modo '{mode}': {ok} OK / {fail} fallidos  (total {total})")

    print("-" * 80)
    print(f"  TOTAL: {total_ok} OK / {total_fail} fallidos")
    print(f"  Dataset: {DATASET_CSV}")
    print("=" * 80)

    return 0


if __name__ == "__main__":
    sys.exit(main())
