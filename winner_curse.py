"""
Ataca el winner's curse de la inversa: el optimizador se va a rincones donde el
modelo sobreestima. Solucion: penalizar la INCERTIDUMBRE en la funcion objetivo.

Incertidumbre: ensemble de M=10 XGBoost entrenados sobre BOOTSTRAP DE PERFILES
(remuestreo con reemplazo de run_id). sigma(x) = std de las 10 predicciones.
En zonas ralas el ajuste cambia mucho -> sigma alta. Es incertidumbre epistemica.

Objetivo penalizado (minimizamos, LD mas negativo = mejor):
    J(x) = mean_ensemble(x) + k * sigma(x)
sigma>0 siempre suma -> hace el punto MENOS atractivo donde el modelo duda.

NO toca produccion ni genera en CATIA. Solo mide y propone.
"""
import os, json
import numpy as np
import pandas as pd
import joblib
from scipy.optimize import differential_evolution
from xgboost import XGBRegressor
from feature_utils import SHAPE, FEATURES, f_alpha_over_sqrtre, f_te_rel

BASE = os.path.dirname(os.path.abspath(__file__))
RHO, MU = 1.225, 1.81e-5
def reynolds(chord_mm, v_kmh):
    return RHO * (v_kmh / 3.6) * (chord_mm / 1000.0) / MU

LD_TUNED = dict(n_estimators=400, learning_rate=0.02, max_depth=10,
                min_child_weight=5, subsample=0.6, colsample_bytree=0.9,
                reg_alpha=0.5, reg_lambda=5.0, n_jobs=-1)
M = 10   # miembros del ensemble

df = pd.read_csv(os.path.join(BASE, "airfoil_dataset.csv"))
ok = df[(df.status == "ok") & (df.chord_length_mm >= 150)].copy()
ok["alpha_over_sqrtre"] = f_alpha_over_sqrtre(ok["alpha_deg"], ok["reynolds"])
ok["te_rel"] = f_te_rel(ok["trailing_edge_thickness_mm"], ok["chord_length_mm"])
perfiles = ok["run_id"].unique()

ENS_PATH = os.path.join(BASE, "ensemble_ld_sigma.joblib")
if os.path.exists(ENS_PATH):
    ens = joblib.load(ENS_PATH)
    print(f"[ENSEMBLE] cargado de disco ({len(ens)} miembros)")
else:
    print(f"[ENSEMBLE] entrenando {M} XGBoost sobre bootstrap de perfiles...")
    ens = []
    for m in range(M):
        rng = np.random.RandomState(1000 + m)
        boot = rng.choice(perfiles, size=len(perfiles), replace=True)   # bootstrap de perfiles
        sub = pd.concat([ok[ok.run_id == r] for r in pd.unique(boot)], ignore_index=True)
        mdl = XGBRegressor(random_state=1000 + m, **LD_TUNED)
        mdl.fit(sub[FEATURES].values, sub["LD"].values)
        ens.append(mdl)
        print(f"   miembro {m+1}/{M} listo ({sub['run_id'].nunique()} perfiles)")
    joblib.dump(ens, ENS_PATH)
    print(f"[OK] ensemble guardado en {os.path.basename(ENS_PATH)}")

prod = joblib.load(os.path.join(BASE, "modelo_LD_inversa_xgb.joblib"))["model"]

def ens_stats(X):
    P = np.stack([m.predict(X) for m in ens])     # (M, N)
    return P.mean(axis=0), P.std(axis=0)

# ---- zona fiable p5-p95 para los 6 params no-cuerda ----
per = ok.groupby("run_id")[SHAPE].first()
P05, P95 = per.quantile(0.05), per.quantile(0.95)
free_keys = [k for k in SHAPE if k != "chord_length_mm"]
free_idx = [SHAPE.index(k) for k in free_keys]
bounds = [(float(P05[k]), float(P95[k])) for k in free_keys]

def arma_X(free_vec, chord, alpha, v):
    shape = np.zeros(7); shape[0] = chord
    for j, idx in enumerate(free_idx):
        shape[idx] = free_vec[j]
    re = reynolds(chord, v)
    X = np.array([list(shape) + [alpha, re,
                                 f_alpha_over_sqrtre(alpha, re),
                                 f_te_rel(shape[4], chord)]])
    return X, shape

# =========================================================
# VALIDACION: sigma detecta los casos que fallaron?
# =========================================================
print("\n" + "=" * 78)
print("VALIDACION: sigma en las propuestas de la BATERIA vs su error real")
print("=" * 78)
bat = json.load(open(os.path.join(BASE, "bateria_resultados.json"), encoding="utf-8"))
print(f"{'caso':5s}{'cuerda':>7s}{'vel':>5s}{'LD_pred':>9s}{'LD_real':>9s}{'err%':>7s}{'sigma':>8s}")
filas = []
for c in bat:
    cfg = json.load(open(os.path.join(BASE, c["json"]), encoding="utf-8"))["user_params"]
    shape = np.array([cfg[k] for k in SHAPE])
    re = reynolds(cfg["chord_length_mm"], c["vel"])
    X = np.array([list(shape) + [c["alpha"], re,
                                 f_alpha_over_sqrtre(c["alpha"], re),
                                 f_te_rel(shape[4], shape[0])]])
    mu, sd = ens_stats(X)
    if c["LD_real"] is not None:
        err = abs(c["LD_real"] - c["LD_pred"]) / abs(c["LD_real"]) * 100
        print(f"{c['caso']:<5d}{c['cuerda']:>7d}{c['vel']:>5d}{c['LD_pred']:>9.2f}"
              f"{c['LD_real']:>9.2f}{err:>6.0f}%{sd[0]:>8.2f}")
        filas.append((err, sd[0]))
    else:
        print(f"{c['caso']:<5d}{c['cuerda']:>7d}{c['vel']:>5d}{c['LD_pred']:>9.2f}"
              f"{'NO CONV':>9s}{'':>7s}{sd[0]:>8.2f}")
if len(filas) >= 3:
    e = np.array([f[0] for f in filas]); s = np.array([f[1] for f in filas])
    print(f"\n  correlacion (Pearson) error% vs sigma = {np.corrcoef(e, s)[0,1]:.3f}")
    print("  -> si es alta y positiva, sigma DETECTA donde el modelo sobreestima.")

# =========================================================
# REPROPUESTA PENALIZADA para los casos 1 y 5 (los peores)
# =========================================================
CASOS_MALOS = [(1, 300, 180, -6, -69.79), (5, 450, 290, -6, -126.86)]
print("\n" + "=" * 78)
print("PROPUESTAS PENALIZADAS  J = mean_ens + k*sigma   (k = 0, 1, 2)")
print("=" * 78)
for caso, chord, v, a, ld_viejo in CASOS_MALOS:
    print(f"\n--- CASO {caso}: cuerda {chord}, {v} km/h, alpha {a} "
          f"(antes: LD_pred={ld_viejo:.2f}) ---")
    print(f"   {'k':>3s}{'LD_pred(prod)':>15s}{'mean_ens':>10s}{'sigma':>8s}{'J':>10s}")
    for k in (0.0, 1.0, 2.0):
        def obj(x):
            X, _ = arma_X(x, chord, a, v)
            mu, sd = ens_stats(X)
            return mu[0] + k * sd[0]
        res = differential_evolution(obj, bounds, seed=42, maxiter=150, tol=1e-7,
                                     polish=True, workers=1)
        X, shape = arma_X(res.x, chord, a, v)
        mu, sd = ens_stats(X)
        ld_prod = float(prod.predict(X)[0])
        print(f"   {k:>3.0f}{ld_prod:>15.2f}{mu[0]:>10.2f}{sd[0]:>8.2f}{res.fun:>10.2f}")
