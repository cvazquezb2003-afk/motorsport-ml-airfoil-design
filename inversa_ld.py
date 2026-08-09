"""
PROTOTIPO de busqueda inversa de forma (optimizacion sobre el forward model).
Objetivo: MAXIMA eficiencia (LD mas negativo) a 180 km/h y alpha=-6.
Evaluador: modelo XGBoost tuneado de LD (modelo_LD_inversa_xgb.joblib, 542 perf).
Explora los 7 parametros de forma en sus rangos; el Reynolds se calcula de la
cuerda de cada candidata a 180 km/h (rho=1.225, mu=1.81e-5).
NO genera en CATIA: solo propone y predice.

Metodo (doble, ver informe): (A) muestreo Sobol masivo evaluado en bloque por el
modelo -> panorama del espacio + top-5 diversas; (B) differential_evolution ->
confirma el optimo global afinado. El modelo predice en ms y es vectorizable, asi
que barrer 200k candidatas es casi instantaneo y da varias formas casi-optimas
DIVERSAS (lo que pide "5 mejores"); DE comprueba que no se escapa un optimo mas fino.
"""
import os
import warnings
import numpy as np
import pandas as pd
import joblib
from scipy.stats import qmc
from scipy.optimize import differential_evolution
warnings.filterwarnings("ignore", category=UserWarning)

BASE = os.path.dirname(os.path.abspath(__file__))
SHAPE = ["chord_length_mm", "leading_edge_angle_deg", "leading_edge_thickness_level",
         "trailing_edge_angle_deg", "trailing_edge_thickness_mm",
         "te_upr_angle_deg", "te_lwr_angle_deg"]
FEATURES = SHAPE + ["alpha_deg", "reynolds"]
RANGES = {
    "chord_length_mm": (200.0, 400.0), "leading_edge_angle_deg": (3.0, 10.0),
    "leading_edge_thickness_level": (0.2, 1.0), "trailing_edge_angle_deg": (158.0, 167.0),
    "trailing_edge_thickness_mm": (1.0, 4.0), "te_upr_angle_deg": (5.0, 15.0),
    "te_lwr_angle_deg": (-8.0, 4.0),
}
LOWS = np.array([RANGES[k][0] for k in SHAPE])
HIGHS = np.array([RANGES[k][1] for k in SHAPE])

# --- condicion objetivo ---
ALPHA = -6.0
V_KMH = 180.0
RHO, MU = 1.225, 1.81e-5

def reynolds_de_cuerda(chord_mm):
    V = V_KMH / 3.6          # m/s
    L = chord_mm / 1000.0    # m
    return RHO * V * L / MU

model = joblib.load(os.path.join(BASE, "modelo_LD_inversa_xgb.joblib"))["model"]

def predice_LD(shape_matrix):
    """shape_matrix: (N,7) -> LD predicho (N,). Anade alpha fijo y Re(cuerda)."""
    n = shape_matrix.shape[0]
    re = reynolds_de_cuerda(shape_matrix[:, 0])          # cuerda = col 0
    X = np.column_stack([shape_matrix, np.full(n, ALPHA), re])
    return model.predict(X)

# ================= (A) muestreo Sobol masivo =================
N = 200_000
sob = qmc.Sobol(d=7, scramble=True, seed=7)
unit = sob.random(N)
cand = qmc.scale(unit, LOWS, HIGHS)
ld = predice_LD(cand)                    # queremos el MAS NEGATIVO

order = np.argsort(ld)                    # ascendente: mas negativo primero
# top-5 DIVERSAS: seleccion voraz con distancia minima en espacio normalizado
def norm(m): return (m - LOWS) / (HIGHS - LOWS)
sel = []
for idx in order:
    if not sel:
        sel.append(idx); continue
    d = np.min(np.linalg.norm(norm(cand[sel]) - norm(cand[idx]), axis=1))
    if d > 0.35:                          # evita clones (umbral en 7D normalizado)
        sel.append(idx)
    if len(sel) == 5:
        break

print("=" * 78)
print(f"OBJETIVO: max eficiencia (LD mas negativo) @ {V_KMH:g} km/h, alpha={ALPHA:g}")
print(f"Evaluador: XGBoost LD (542). Metodo A: Sobol {N} candidatas.")
print("=" * 78)
print("\nTOP-5 FORMAS DIVERSAS (LD predicho, mas negativo = mejor):")
hdr = "  #  " + "".join(f"{k[:12]:>13s}" for k in SHAPE) + f"{'LD_pred':>10s}"
print(hdr)
for i, idx in enumerate(sel, 1):
    vals = "".join(f"{cand[idx][j]:13.3f}" for j in range(7))
    print(f"  {i}  {vals}{ld[idx]:10.2f}")

# ================= (B) differential evolution =================
def objetivo(x):
    return predice_LD(x.reshape(1, -1))[0]   # minimiza LD (mas negativo)

bounds = list(zip(LOWS, HIGHS))
res = differential_evolution(objetivo, bounds, seed=42, maxiter=300,
                             tol=1e-7, polish=True, workers=1)
print("\n" + "=" * 78)
print("Metodo B: differential_evolution (optimo global afinado)")
print("=" * 78)
best = res.x
print("  forma optima DE:")
for k, v in zip(SHAPE, best):
    print(f"     {k:32s} {v:10.3f}   (rango [{RANGES[k][0]:g},{RANGES[k][1]:g}])")
print(f"  Re(cuerda,180) = {reynolds_de_cuerda(best[0]):,.0f}")
print(f"  LD predicho    = {res.fun:.2f}")

# comparacion best A vs best B
print("\n[RESUMEN] mejor LD predicho:")
print(f"   Sobol top-1 : {ld[order[0]]:.2f}")
print(f"   DE          : {res.fun:.2f}")

# guarda la mejor propuesta (DE) para posible verificacion posterior en pipeline
best_shape = {k: round(float(v), 6) for k, v in zip(SHAPE, best)}
import json
with open(os.path.join(BASE, "inversa_propuesta_top1.json"), "w", encoding="utf-8") as f:
    json.dump({"objetivo": {"velocidad_kmh": V_KMH, "alpha_deg": ALPHA},
               "reynolds": reynolds_de_cuerda(best[0]),
               "LD_predicho": float(res.fun),
               "shape_params": best_shape}, f, indent=2, ensure_ascii=False)
print("\n[OK] mejor propuesta -> inversa_propuesta_top1.json (para verificar luego)")
