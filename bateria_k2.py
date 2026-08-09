"""
Bateria k=2: repropone los MISMOS 8 casos con objetivo penalizado
    J(x) = mean_ensemble(x) + 2*sigma(x)
para comparar directamente contra la bateria k=0. Guarda los JSON del pipeline.
NO genera en CATIA.
"""
import os, json
import numpy as np
import pandas as pd
import joblib
from scipy.optimize import differential_evolution
from feature_utils import SHAPE, FEATURES, f_alpha_over_sqrtre, f_te_rel

BASE = os.path.dirname(os.path.abspath(__file__))
K = 2.0
RHO, MU = 1.225, 1.81e-5
def reynolds(c, v):
    return RHO * (v / 3.6) * (c / 1000.0) / MU

ens = joblib.load(os.path.join(BASE, "ensemble_ld_sigma.joblib"))
prod = joblib.load(os.path.join(BASE, "modelo_LD_inversa_xgb.joblib"))["model"]

df = pd.read_csv(os.path.join(BASE, "airfoil_dataset.csv"))
ok = df[(df.status == "ok") & (df.chord_length_mm >= 150)]
per = ok.groupby("run_id")[SHAPE].first()
P05, P95 = per.quantile(0.05), per.quantile(0.95)
free_keys = [k for k in SHAPE if k != "chord_length_mm"]
free_idx = [SHAPE.index(k) for k in free_keys]
bounds = [(float(P05[k]), float(P95[k])) for k in free_keys]

def arma_X(vec, chord, alpha, v):
    shape = np.zeros(7); shape[0] = chord
    for j, idx in enumerate(free_idx):
        shape[idx] = vec[j]
    re = reynolds(chord, v)
    X = np.array([list(shape) + [alpha, re,
                                 f_alpha_over_sqrtre(alpha, re),
                                 f_te_rel(shape[4], chord)]])
    return X, shape

def ens_stats(X):
    P = np.stack([m.predict(X) for m in ens])
    return P.mean(axis=0)[0], P.std(axis=0)[0]

# mismos casos + su error con k=0 (de la bateria anterior)
CASOS = [
    (1, 300, 180, -6), (2, 300, 110, -6), (3, 300, 290, -8), (4, 450, 180, -6),
    (5, 450, 290, -6), (6, 450, 110, -8), (7, 180, 180, -6), (8, 180, 290, -6),
]
out = []
print("=" * 76)
print(f"BATERIA k={K:g}   J = mean_ens + {K:g}*sigma")
print("=" * 76)
print(f"{'caso':5s}{'cuerda':>7s}{'vel':>5s}{'a':>4s}{'Re':>11s}{'LD_pred':>9s}{'sigma':>8s}")
for caso, chord, v, a in CASOS:
    def obj(x):
        X, _ = arma_X(x, chord, a, v)
        mu, sd = ens_stats(X)
        return mu + K * sd
    res = differential_evolution(obj, bounds, seed=42, maxiter=150, tol=1e-7,
                                 polish=True, workers=1)
    X, shape = arma_X(res.x, chord, a, v)
    mu, sd = ens_stats(X)
    ld_pred = float(prod.predict(X)[0])
    up = {k: round(float(val), 6) for k, val in zip(SHAPE, shape)}
    up["chord_angle_deg"] = 350.0
    fname = f"k2_{caso}_c{chord}_v{v}_a{abs(a)}.json"
    json.dump({"user_params": up, "velocidad_kmh": v, "alphas": [a]},
              open(os.path.join(BASE, fname), "w", encoding="utf-8"), indent=2)
    re = int(round(reynolds(chord, v)))
    out.append({"caso": caso, "cuerda": chord, "vel": v, "alpha": a, "Re": re,
                "LD_pred": ld_pred, "sigma": float(sd), "json": fname})
    print(f"{caso:<5d}{chord:>7d}{v:>5d}{a:>4d}{re:>11,d}{ld_pred:>9.2f}{sd:>8.2f}")

json.dump(out, open(os.path.join(BASE, "bateria_k2_index.json"), "w", encoding="utf-8"),
          indent=2)
print(f"\n[OK] 8 propuestas k={K:g} guardadas + indice bateria_k2_index.json")
