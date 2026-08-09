"""
Busqueda inversa v2 - RESTRINGIDA A ZONA FIABLE (anti-extrapolacion).
El intento v1 se fue a esquinas extremas del espacio (parametros al limite) donde
hay pocos datos y el modelo predijo optimista (-98.9 pred vs -56.95 real XFOIL).
Arreglo (sin reentrenar): acotar la busqueda de cada parametro LIBRE a su rango
percentil 5-95 de los DATOS DE ENTRENAMIENTO (zona poblada), y permitir FIJAR
parametros por el usuario (reglamento). Consciente de extrapolacion en fijos.
Solo propone; no genera en CATIA.

Uso:
    python inversa_ld_v2.py                      # todos libres (comparar con v1)
    python inversa_ld_v2.py '{"chord_length_mm":350}'   # fijando cuerda=350
"""
import os
import sys
import json
import warnings
import numpy as np
import pandas as pd
import joblib
from scipy.stats import qmc
from scipy.optimize import differential_evolution
warnings.filterwarnings("ignore", category=UserWarning)

BASE = os.path.dirname(os.path.abspath(__file__))
# Features desde la FUENTE UNICA (misma que el entrenamiento). El modelo espera
# 11 features en el orden FEATURES; arma_X las construye en ese mismo orden.
from feature_utils import SHAPE, FEATURES, f_alpha_over_sqrtre, f_te_rel
FULL_RANGES = {
    "chord_length_mm": (200.0, 400.0), "leading_edge_angle_deg": (3.0, 10.0),
    "leading_edge_thickness_level": (0.2, 1.0), "trailing_edge_angle_deg": (158.0, 167.0),
    "trailing_edge_thickness_mm": (1.0, 4.0), "te_upr_angle_deg": (5.0, 15.0),
    "te_lwr_angle_deg": (-8.0, 4.0),
}

# --- condicion objetivo ---
ALPHA, V_KMH = -6.0, 180.0
RHO, MU = 1.225, 1.81e-5
def reynolds_de_cuerda(chord_mm):
    return RHO * (V_KMH / 3.6) * (chord_mm / 1000.0) / MU

model = joblib.load(os.path.join(BASE, "modelo_LD_inversa_xgb.joblib"))["model"]

# =========================================================
# PENALIZACION POR INCERTIDUMBRE (anti winner's curse)
# =========================================================
# El optimizador tiende a irse a rincones donde el modelo SOBREESTIMA (winner's
# curse): con k=0 la bateria de 8 casos dio errores del 8% al 59%, SIEMPRE
# optimistas. Solucion: penalizar la incertidumbre del modelo.
#   J(x) = mean_ensemble(x) + k * sigma(x)      (minimizamos; sigma>0 penaliza)
# sigma = std de un ENSEMBLE de XGBoost entrenados sobre bootstrap de PERFILES
# (alta donde hay pocos datos = justo donde el modelo sobreestima).
# El ensemble se CARGA de disco (entrenarlo tarda ~17 min): generarlo con
# winner_curse.py si falta. k=2 validado (error medio 2.5% vs 24% con k=0).
K_PENAL_DEFAULT = 2.0
ENS_PATH = os.path.join(BASE, "ensemble_ld_sigma.joblib")
if not os.path.exists(ENS_PATH):
    raise SystemExit(
        f"[ERROR] Falta el ensemble de incertidumbre ({os.path.basename(ENS_PATH)}). "
        "La inversa lo necesita para penalizar la incertidumbre (anti winner's curse). "
        "Generalo una vez con:  python winner_curse.py   (tarda ~17 min). "
        "NO se reentrena en cada llamada a proposito.")
ensemble = joblib.load(ENS_PATH)


def k_penal_from_argv():
    """k configurable como SEGUNDO argumento: python inversa_ld_v2.py '{...}' 1.5"""
    if len(sys.argv) > 2:
        try:
            k = float(sys.argv[2])
            if k < 0:
                print(f"[WARN] k debe ser >= 0. Uso k={K_PENAL_DEFAULT}.")
                return K_PENAL_DEFAULT
            return k
        except ValueError:
            print(f"[WARN] k no numerico ({sys.argv[2]!r}). Uso k={K_PENAL_DEFAULT}.")
    return K_PENAL_DEFAULT


K_PENAL = k_penal_from_argv()


def ens_stats(X):
    """Media y sigma del ensemble para una matriz X (N, 11). Devuelve (mu, sd)."""
    P = np.stack([m.predict(X) for m in ensemble])
    return P.mean(axis=0), P.std(axis=0)


# Rango de cuerda SOPORTADO: 150-500 mm. Por debajo de 150 mm XFOIL no converge
# de forma fiable (Reynolds demasiado bajo), asi que esa franja se EXCLUYE del
# entrenamiento y de la zona fiable, y se avisa si el usuario la pide.
CHORD_SOPORTADO = (150.0, 500.0)

# --- ZONA FIABLE: percentil 5-95 de los datos de entrenamiento ---
# Se calcula por PERFIL (un valor por run_id), no por fila, para que el numero de
# angulos/velocidades convergidos de cada perfil no sesgue los percentiles.
df = pd.read_csv(os.path.join(BASE, "airfoil_dataset.csv"))
ok = df[(df["status"] == "ok") &
        (df["chord_length_mm"] >= CHORD_SOPORTADO[0])].copy()   # excluye <150mm
per_perfil = ok.groupby("run_id")[SHAPE].first()
P05 = per_perfil.quantile(0.05)
P95 = per_perfil.quantile(0.95)
DMIN = per_perfil.min()
DMAX = per_perfil.max()

def fixed_params_from_argv():
    if len(sys.argv) > 1:
        try:
            d = json.loads(sys.argv[1])
            return {k: float(v) for k, v in d.items() if k in SHAPE}
        except Exception as e:
            print(f"[WARN] No pude leer parametros fijos ({e}). Sigo sin fijar.")
    return {}

fixed = fixed_params_from_argv()

# Franja de MENOR confianza del rango soportado: cuerda 150-200 mm. Ahi el
# Reynolds es bajo y XFOIL pierde precision, asi que el modelo es menos fiable
# (y empeora hacia 150). Aviso GRADUADO: fuerte en 150-175, suave en 175-200.
ZONA_BAJA_CONF = (150.0, 200.0)
def aviso_confianza_150_200(chord):
    """Devuelve (etiqueta, mensaje) si la cuerda cae en 150-200; si no, None."""
    lo, hi = ZONA_BAJA_CONF
    if not (lo <= chord < hi):
        return None
    if chord < 175.0:
        return ("[!!] BAJA CONFIANZA",
                f"cuerda {chord:g} mm (franja 150-175): es la zona MENOS fiable del rango "
                "soportado. El error del modelo (predicho vs XFOIL real) aqui puede ser del "
                "orden de 3 veces mayor que en el resto del rango (200-500 mm), y EMPEORA "
                "cuanto mas te acercas a 150 mm, porque el Reynolds es mas bajo y XFOIL "
                "pierde precision en ese regimen. El L/D predicho tiende a ser optimista "
                "(quedar por encima del real). Se propone igualmente, pero VERIFICA la "
                "propuesta en XFOIL antes de fiarte del valor.")
    return ("[!] CONFIANZA REDUCIDA",
            f"cuerda {chord:g} mm (franja 175-200): parte baja del rango soportado, menos "
            "fiable que el grueso 200-500 mm (el error del modelo es sensiblemente mayor). "
            "Mejora hacia 200 mm y empeora hacia 150. Conviene verificar en XFOIL antes de "
            "fiarte del valor exacto.")

# --- construir bounds: fijos colapsan a un punto; libres a [p5,p95] ---
print("=" * 82)
print(f"INVERSA v2 (zona fiable p5-p95) | objetivo max eficiencia @ {V_KMH:g} km/h, alpha={ALPHA:g}")
print("=" * 82)
print(f"\n{'param':32s}{'estado':10s}{'busqueda / valor':>26s}{'  datos[min,max]':>22s}")
free_idx, bounds = [], []
base_point = np.zeros(len(SHAPE))
for i, k in enumerate(SHAPE):
    lo95, hi95 = float(P05[k]), float(P95[k])
    dmin, dmax = float(DMIN[k]), float(DMAX[k])
    if k in fixed:
        val = fixed[k]
        base_point[i] = val
        # consciencia de limites
        if val < dmin or val > dmax:
            estado = "FIJO!!"
            nota = f"  [{lo95:.3g},{hi95:.3g}] -> EXTRAPOLA (datos [{dmin:.3g},{dmax:.3g}])"
        elif val < lo95 or val > hi95:
            estado = "FIJO*"
            nota = f"  fuera de p5-p95 (poco dato)   [{dmin:.3g},{dmax:.3g}]"
        else:
            estado = "FIJO"
            nota = f"  dentro de zona fiable         [{dmin:.3g},{dmax:.3g}]"
        # La cuerda en 150-200 NO es "verde": es la franja de confianza reducida,
        # aunque caiga dentro de p5-p95. No la marcamos como plenamente fiable.
        if k == "chord_length_mm" and ZONA_BAJA_CONF[0] <= val < ZONA_BAJA_CONF[1] \
                and estado == "FIJO":
            estado = "FIJO~"
            nota = f"  CONFIANZA REDUCIDA (150-200)  [{dmin:.3g},{dmax:.3g}]"
        print(f"{k:32s}{estado:10s}{val:26.3f}{nota}")
    else:
        free_idx.append(i)
        bounds.append((lo95, hi95))
        base_point[i] = (lo95 + hi95) / 2
        print(f"{k:32s}{'libre':10s}{f'[{lo95:.3g}, {hi95:.3g}]':>26s}{f'  [{dmin:.3g},{dmax:.3g}]':>22s}")

# aviso especifico de RANGO SOPORTADO: cuerda < 150 mm queda fuera (XFOIL no
# fiable a Reynolds tan bajo). Se avisa fuerte pero NO se rechaza la propuesta.
if "chord_length_mm" in fixed and fixed["chord_length_mm"] < CHORD_SOPORTADO[0]:
    print(f"\n[!!] FUERA DE RANGO SOPORTADO: cuerda fijada = {fixed['chord_length_mm']:g} mm "
          f"< {CHORD_SOPORTADO[0]:g} mm. El sistema solo es fiable en {CHORD_SOPORTADO[0]:g}-"
          f"{CHORD_SOPORTADO[1]:g} mm: por debajo de 150 mm el Reynolds es demasiado bajo y "
          "XFOIL no converge de forma fiable, por lo que esa franja se EXCLUYO del "
          "entrenamiento. La prediccion aqui es POCO FIABLE. Se propone igualmente, pero "
          "tomala con mucha cautela y verifica en XFOIL.")

# avisos de extrapolacion (resumen)
extrap = [k for k in fixed if fixed[k] < float(DMIN[k]) or fixed[k] > float(DMAX[k])]
if extrap:
    print("\n[!!] AVISO DE EXTRAPOLACION: " + ", ".join(extrap) + " esta(n) FUERA del "
          "rango de datos de entrenamiento. El modelo NO ha visto perfiles ahi: la "
          "prediccion es POCO FIABLE. Para fiarte, habria que GENERAR datos en ese "
          "rango. Se propone igualmente, pero tomalo con cautela.")

def arma_X(free_matrix):
    """
    free_matrix (N, n_free) -> matriz (N, 11) en el orden canonico FEATURES:
    7 forma + alpha + reynolds + alpha_over_sqrtre + te_rel. Las 2 derivadas se
    calculan con las MISMAS funciones que el entrenamiento (feature_utils), para
    que modelo e inversa casen exactamente.
    """
    n = free_matrix.shape[0]
    shape_full = np.tile(base_point, (n, 1))
    for j, idx in enumerate(free_idx):
        shape_full[:, idx] = free_matrix[:, j]
    chord = shape_full[:, 0]                        # SHAPE[0]
    te_thick = shape_full[:, 4]                     # SHAPE[4] = trailing_edge_thickness_mm
    alpha = np.full(n, ALPHA)
    re = reynolds_de_cuerda(chord)
    aosr = f_alpha_over_sqrtre(alpha, re)
    trel = f_te_rel(te_thick, chord)
    X = np.column_stack([shape_full, alpha, re, aosr, trel])   # (N, 11) orden FEATURES
    return X, shape_full

def predice(free_matrix):
    """LD del modelo de PRODUCCION (el valor que se reporta)."""
    X, _ = arma_X(free_matrix)
    return model.predict(X)


def objetivo_penalizado(free_matrix):
    """J = mean_ensemble + K_PENAL*sigma (lo que se OPTIMIZA). Devuelve (J, mu, sd)."""
    X, _ = arma_X(free_matrix)
    mu, sd = ens_stats(X)
    return mu + K_PENAL * sd, mu, sd


if not free_idx:
    print("\n[INFO] No hay parametros libres (todos fijos): evaluo el punto unico.")
    ld = predice(np.zeros((1, 0)))[0]   # arma_X construye las 11 features
    _, _, sd = objetivo_penalizado(np.zeros((1, 0)))
    print(f"  LD predicho = {ld:.2f}   sigma = {sd[0]:.2f}")
    sys.exit(0)

LOWS = np.array([b[0] for b in bounds]); HIGHS = np.array([b[1] for b in bounds])

# ===== (A) Sobol restringido: top-5 diversas (rankeadas por J penalizado) =====
N = 200_000
unit = qmc.Sobol(d=len(free_idx), scramble=True, seed=7).random(N)
cand = qmc.scale(unit, LOWS, HIGHS)
J_cand, mu_cand, sd_cand = objetivo_penalizado(cand)   # ranking por J, no por LD_pred
ld = predice(cand)                                      # LD de produccion (reporte)
order = np.argsort(J_cand)
def norm(m): return (m - LOWS) / (HIGHS - LOWS)
sel = []
for idx in order:
    if not sel:
        sel.append(idx); continue
    if np.min(np.linalg.norm(norm(cand[sel]) - norm(cand[idx]), axis=1)) > 0.25:
        sel.append(idx)
    if len(sel) == 5:
        break

_, full_sel = arma_X(cand[sel])
print(f"\nTOP-5 FORMAS DIVERSAS (zona fiable, rankeadas por J = mean_ens + {K_PENAL:g}*sigma)."
      " LD mas negativo = mejor:")
print("  #  " + "".join(f"{k[:11]:>12s}" for k in SHAPE) + f"{'LD_pred':>10s}{'sigma':>8s}")
top5_en_zona = False
for i, idx in enumerate(sel, 1):
    vals = "".join(f"{full_sel[i-1][j]:12.3f}" for j in range(7))
    av = aviso_confianza_150_200(full_sel[i-1][0])   # marca por cuerda de la propuesta
    tag = f"   <-- {av[0]}" if av else ""
    if av:
        top5_en_zona = True
    print(f"  {i}  {vals}{ld[idx]:10.2f}{sd_cand[idx]:8.2f}{tag}")
if top5_en_zona:
    print("     (Las propuestas marcadas caen en la franja 150-200 mm, de CONFIANZA "
          "REDUCIDA: cuerda pequena -> Reynolds bajo -> XFOIL menos preciso. Verifica "
          "esas propuestas en XFOIL antes de fiarte del L/D predicho.)")

# ===== (B) DE restringido, sobre el objetivo PENALIZADO =====
res = differential_evolution(lambda x: objetivo_penalizado(x.reshape(1, -1))[0][0], bounds,
                             seed=42, maxiter=300, tol=1e-7, polish=True, workers=1)
_, full_de = arma_X(res.x.reshape(1, -1))
print(f"\nOptimo DE (zona fiable, objetivo penalizado k={K_PENAL:g}):")
for k, v in zip(SHAPE, full_de[0]):
    print(f"   {k:32s} {v:10.3f}")
print(f"   Re(cuerda,{V_KMH:g}) = {reynolds_de_cuerda(full_de[0][0]):,.0f}")
# OJO: res.fun es J (objetivo penalizado), NO el L/D. El L/D que se reporta es el
# del modelo de produccion en el punto optimo.
_ld_de = float(predice(res.x.reshape(1, -1))[0])
_, _mu_de, _sd_de = objetivo_penalizado(res.x.reshape(1, -1))
print(f"   LD predicho = {_ld_de:.2f}   sigma = {_sd_de[0]:.2f}   "
      f"(J penalizado = {res.fun:.2f}, k={K_PENAL:g})")
# aviso graduado de confianza si el optimo cae en la franja 150-200 mm
_av_de = aviso_confianza_150_200(full_de[0][0])
if _av_de:
    print(f"\n   {_av_de[0]}: {_av_de[1]}")

# ===== chequeo: caen dentro de la nube de datos? (vecino mas cercano) =====
Xtr = norm_tr = (per_perfil[SHAPE].values - DMIN.values) / (DMAX.values - DMIN.values)
def nn_dist(shape_row):
    q = (shape_row - DMIN.values) / (DMAX.values - DMIN.values)
    return np.min(np.linalg.norm(Xtr - q, axis=1))
# distancia tipica entre vecinos en los datos (para referencia)
import scipy.spatial
tree = scipy.spatial.cKDTree(Xtr)
typ = np.median(tree.query(Xtr, k=2)[0][:, 1])
print(f"\n[NUBE DE DATOS] dist. vecino-mas-cercano en espacio normalizado "
      f"(tipica entre perfiles reales ~ {typ:.3f}):")
print(f"   optimo DE     -> NN={nn_dist(full_de[0]):.3f}")
for i, idx in enumerate(sel, 1):
    print(f"   top-{i} Sobol   -> NN={nn_dist(full_sel[i-1]):.3f}")

# guarda la mejor propuesta DE
best_shape = {k: round(float(v), 6) for k, v in zip(SHAPE, full_de[0])}
with open(os.path.join(BASE, "inversa_v2_propuesta_top1.json"), "w", encoding="utf-8") as f:
    json.dump({"objetivo": {"velocidad_kmh": V_KMH, "alpha_deg": ALPHA},
               "fixed": fixed, "k_penalizacion": K_PENAL,
               "LD_predicho": _ld_de,          # LD del modelo de produccion (no J)
               "sigma": float(_sd_de[0]),
               "J_penalizado": float(res.fun),
               "shape_params": best_shape}, f, indent=2, ensure_ascii=False)
print("\n[OK] mejor propuesta -> inversa_v2_propuesta_top1.json")
