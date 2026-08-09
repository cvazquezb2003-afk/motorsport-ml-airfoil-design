"""
Bateria de propuestas de la inversa (modelo 11 features) para varios casos que
cubren las 3 zonas de cuerda x varias velocidades/angulos. Para cada caso:
cuerda FIJA, optimiza los otros 6 params en zona fiable p5-p95, a su velocidad y
angulo, y guarda la propuesta como JSON del pipeline directo. NO genera en CATIA.
"""
import os, json
import numpy as np
import pandas as pd
import joblib
from scipy.optimize import differential_evolution
from feature_utils import SHAPE, f_alpha_over_sqrtre, f_te_rel

BASE = os.path.dirname(os.path.abspath(__file__))
RHO, MU = 1.225, 1.81e-5
def reynolds(chord_mm, v_kmh):
    return RHO * (v_kmh / 3.6) * (chord_mm / 1000.0) / MU

model = joblib.load(os.path.join(BASE, "modelo_LD_inversa_xgb.joblib"))["model"]

# zona fiable p5-p95 (por perfil, cuerda>=150) para los 6 params NO-cuerda
df = pd.read_csv(os.path.join(BASE, "airfoil_dataset.csv"))
ok = df[(df.status == "ok") & (df.chord_length_mm >= 150)]
per = ok.groupby("run_id")[SHAPE].first()
P05, P95 = per.quantile(0.05), per.quantile(0.95)
free_keys = [k for k in SHAPE if k != "chord_length_mm"]
free_idx = [SHAPE.index(k) for k in free_keys]
bounds = [(float(P05[k]), float(P95[k])) for k in free_keys]

# CASOS: (cuerda, velocidad, alpha)
CASOS = [
    (300, 180, -6), (300, 110, -6), (300, 290, -8),
    (450, 180, -6), (450, 290, -6), (450, 110, -8),
    (180, 180, -6), (180, 290, -6),
]

def arma_X(free_vec, chord, alpha, v):
    shape = np.zeros(7)
    shape[0] = chord
    for j, idx in enumerate(free_idx):
        shape[idx] = free_vec[j]
    re = reynolds(chord, v)
    aosr = f_alpha_over_sqrtre(alpha, re)
    trel = f_te_rel(shape[4], chord)          # te_thickness / chord
    return np.array([list(shape) + [alpha, re, aosr, trel]]), shape

resultados = []
print("=" * 78)
print("BATERIA DE PROPUESTAS (modelo 11 features)")
print("=" * 78)
for i, (chord, v, a) in enumerate(CASOS, 1):
    def obj(x):
        X, _ = arma_X(x, chord, a, v)
        return model.predict(X)[0]           # minimiza LD (mas negativo = mejor)
    res = differential_evolution(obj, bounds, seed=42, maxiter=200, tol=1e-7,
                                 polish=True, workers=1)
    _, shape = arma_X(res.x, chord, a, v)
    up = {k: round(float(val), 6) for k, val in zip(SHAPE, shape)}
    up["chord_angle_deg"] = 350.0
    cfg = {"user_params": up, "velocidad_kmh": v, "alphas": [a]}
    fname = f"bat_{i}_c{chord}_v{v}_a{abs(a)}.json"
    json.dump(cfg, open(os.path.join(BASE, fname), "w", encoding="utf-8"), indent=2)
    re = reynolds(chord, v)
    resultados.append({"caso": i, "cuerda": chord, "vel": v, "alpha": a,
                       "Re": int(round(re)), "LD_pred": float(res.fun), "json": fname})
    print(f"  caso {i}: c={chord} v={v} a={a} | Re={int(round(re)):,} | "
          f"LD_pred={res.fun:7.2f} | {fname}")

json.dump(resultados, open(os.path.join(BASE, "bateria_index.json"), "w", encoding="utf-8"),
          indent=2)
print(f"\n[OK] {len(CASOS)} propuestas guardadas + indice en bateria_index.json")
