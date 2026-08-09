"""
SERVICIO de inversa PORTABLE para el dashboard (sin CATIA, sin tocar produccion).

Reutiliza los MISMOS ingredientes validados que inversa_ld_v2.py:
  - modelos de disco (LD, CD) + ensemble de sigma (winner's curse)
  - features de feature_utils (fuente unica)
  - objetivo J = mean_ensemble(LD) + k*sigma   (k=2, anti winner's curse)
  - bounds p5-p95 de los datos >=150 (zona fiable), cuerda fijada

Pero parametrizado por lo que el dashboard necesita:
  - cuerda pedida
  - angulo objetivo (del rango de la Parte 1; se usa el punto medio del rango)
  - prioridad: "efficiency" (max |L/D|) | "drag" (min CD)

NO modifica inversa_ld_v2.py (produccion). Vectorizado (Sobol) para responder rapido.
"""
import os, json
import numpy as np
import pandas as pd
import joblib
from scipy.stats import qmc
from feature_utils import SHAPE, FEATURES, f_alpha_over_sqrtre, f_te_rel

BASE = os.path.dirname(os.path.abspath(__file__))
RHO, MU, V_KMH = 1.225, 1.81e-5, 180.0        # V fija = 180 (como produccion)
CHORD_MIN = 150.0
K_DEFAULT = 2.0

# --- carga UNICA de modelos + bounds (se hace al importar, se reutiliza) ---
_LD = joblib.load(os.path.join(BASE, "modelo_LD_inversa_xgb.joblib"))["model"]
_CD = joblib.load(os.path.join(BASE, "modelo_CD_xgb.joblib"))["model"]
_ENS = joblib.load(os.path.join(BASE, "ensemble_ld_sigma.joblib"))

_df = pd.read_csv(os.path.join(BASE, "airfoil_dataset.csv"))
_ok = _df[(_df.status == "ok") & (_df.chord_length_mm >= CHORD_MIN)]
_per = _ok.groupby("run_id")[SHAPE].first()
_P05, _P95 = _per.quantile(0.05), _per.quantile(0.95)
_DMIN, _DMAX = _per.min(), _per.max()
_FREE = [k for k in SHAPE if k != "chord_length_mm"]
_FREE_IDX = [SHAPE.index(k) for k in _FREE]


def _reynolds(chord_mm, v_kmh=V_KMH):
    """Re = rho*V*L/mu. V_KMH (180) queda como DEFAULT, no como constante cableada:
    asi la velocidad pasa a ser parametro de usuario sin que ninguna llamada existente
    cambie de comportamiento."""
    return RHO * (float(v_kmh) / 3.6) * (chord_mm / 1000.0) / MU


def _arma_X(shape_full, alpha, v_kmh=V_KMH):
    """(N,7) shape + alpha -> (N,11) en orden FEATURES, via feature_utils.
    La velocidad entra SOLO por el Reynolds: es la unica via por la que el modelo la ve
    (no hay feature de velocidad; ver feature_utils)."""
    n = shape_full.shape[0]
    chord = shape_full[:, 0]
    te = shape_full[:, 4]
    a = np.full(n, alpha)
    re = _reynolds(chord, v_kmh)
    return np.column_stack([shape_full, a, re,
                            f_alpha_over_sqrtre(a, re), f_te_rel(te, chord)])


def _ens_stats(X):
    P = np.stack([m.predict(X) for m in _ENS])
    return P.mean(axis=0), P.std(axis=0)


def _grid_angulos(a_from, a_to, step):
    """Rejilla de angulos entre a_from y a_to (negativos). Rango nulo -> un solo
    angulo (comportamiento validado de la version single-angle)."""
    lo, hi = sorted([float(a_from), float(a_to)])
    if abs(hi - lo) < 0.5:                       # angulo exacto / rango nulo
        return np.array([lo])
    g = np.arange(lo, hi + 1e-6, step)
    if g[-1] < hi - 1e-6:
        g = np.append(g, hi)
    return g


def optimizar(chord_mm, a_from, a_to=None, prioridad="efficiency",
              k=K_DEFAULT, n_sobol=32_768, step=1.0, seed=7, v_kmh=V_KMH):
    """Optimiza en la zona fiable (cuerda fija) el L/D EVALUADO EN EL RANGO de
    angulos [a_from, a_to] (negativos). Agregacion = MEDIA sobre el rango.

    - Rango (ej. Monaco -14..-9): busca el perfil con mejor L/D MEDIO en la franja.
    - Angulo exacto (a_to=None o == a_from): un solo angulo = version validada.
    - efficiency: min  media_a( mean_ens_LD(a) + k*sigma(a) )   (anti winner's curse)
    - drag:       min  media_a( CD(a) )
    - k=2 se mantiene igual. Robusto: si el rango es amplio, promedia mas angulos.

    v_kmh: velocidad a la que se evalua TODO (Reynolds -> forma elegida, angulo
    recomendado y KPIs). Default 180 = comportamiento historico, bit a bit. Las guardas
    de rango viven fuera (entrada_dashboard.valida_velocidad y guardas_velocidad): aqui
    no se valida ni se recorta, para no mezclar optimizacion con politica de dominio.
    """
    chord = float(chord_mm)
    vel = float(v_kmh)
    # compat hacia atras: llamada antigua optimizar(chord, alpha, prioridad_str)
    if isinstance(a_to, str):
        prioridad = a_to
        a_to = None
    if a_to is None:
        a_to = a_from
    angles = _grid_angulos(a_from, a_to, step)
    m = len(angles)

    lows = np.array([float(_P05[kk]) for kk in _FREE])
    highs = np.array([float(_P95[kk]) for kk in _FREE])
    unit = qmc.Sobol(d=len(_FREE), scramble=True, seed=seed).random(n_sobol)
    cand_free = qmc.scale(unit, lows, highs)                       # (N,6)
    shape_full = np.zeros((n_sobol, 7))
    shape_full[:, 0] = chord
    for j, idx in enumerate(_FREE_IDX):
        shape_full[:, idx] = cand_free[:, j]

    # acumular objetivo/LD/CD/sigma promediando sobre el rango de angulos
    Jsum = np.zeros(n_sobol); ld_sum = np.zeros(n_sobol)
    cd_sum = np.zeros(n_sobol); sd_sum = np.zeros(n_sobol)
    for a in angles:
        X = _arma_X(shape_full, a, vel)
        mu, sd = _ens_stats(X)
        ld = _LD.predict(X); cd = _CD.predict(X)
        Jsum += (cd if prioridad == "drag" else (mu + k * sd))
        ld_sum += ld; cd_sum += cd; sd_sum += sd
    J = Jsum / m
    best = int(np.argmin(J))

    # angulo RECOMENDADO: |alpha| de la banda con mayor |L/D| del optimo elegido
    sh_best = shape_full[best]
    lds = np.array([_LD.predict(_arma_X(sh_best.reshape(1, -1), a, vel))[0] for a in angles])
    alpha_rec_abs = float(abs(angles[int(np.argmax(np.abs(lds)))]))

    shape_best = {kk: round(float(shape_full[best, i]), 6) for i, kk in enumerate(SHAPE)}
    q = (shape_full[best] - _DMIN.values) / (_DMAX.values - _DMIN.values)
    Xtr = (_per[SHAPE].values - _DMIN.values) / (_DMAX.values - _DMIN.values)
    nn = float(np.min(np.linalg.norm(Xtr - q, axis=1)))
    lo, hi = sorted([abs(float(a_from)), abs(float(a_to))])

    return {
        "shape_params": shape_best,
        "cuerda_mm": chord, "velocidad_kmh": vel,
        "reynolds": int(round(_reynolds(chord, vel))),
        "alpha_lo_abs": lo, "alpha_hi_abs": hi, "n_angulos": m,
        "alpha_recomendado_abs": round(alpha_rec_abs, 1),
        "prioridad": prioridad, "k_penalizacion": k,
        "LD_predicho": float(ld_sum[best] / m),      # L/D MEDIO en el rango
        "sigma": float(sd_sum[best] / m),
        "CD_predicho": float(cd_sum[best] / m),
        "nn_dist": nn,
    }


if __name__ == "__main__":
    import sys, time
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass
    t0 = time.time()
    r = optimizar(300, -14, -9)          # rango Monaco 9-14
    dt = time.time() - t0
    print(json.dumps(r, indent=2, ensure_ascii=False))
    print(f"\n[TIEMPO] {dt:.1f} s")
