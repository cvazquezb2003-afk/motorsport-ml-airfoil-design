"""
Importancias del modelo FINAL de L/D (modelo_LD_inversa_xgb.joblib, 542 perfiles).
Ordena los 7 parametros de forma de mas a menos importante y diagnostica los
mudos cruzando con: (a) amplitud del rango muestreado, (b) correlacion directa
del parametro con LD en los datos ok. Solo lectura.
"""
import os
import numpy as np
import pandas as pd
import joblib
from scipy.stats import spearmanr

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

bundle = joblib.load(os.path.join(BASE, "modelo_LD_inversa_xgb.joblib"))
model = bundle["model"]
imp = dict(zip(FEATURES, model.feature_importances_))

df = pd.read_csv(os.path.join(BASE, "airfoil_dataset.csv"))
ok = df[df["status"] == "ok"].copy()

print("=" * 74)
print("IMPORTANCIA 9 INPUTS (XGBoost tuneado, LD, 542 perfiles)")
print("=" * 74)
for f, w in sorted(imp.items(), key=lambda t: -t[1]):
    print(f"   {f:32s} {w*100:5.1f}%  {'#'*int(round(w*80))}")

print("\n" + "=" * 74)
print("LOS 7 PARAMETROS DE FORMA, ordenados + diagnostico de mudos")
print("=" * 74)
print(f"{'param':32s}{'imp':>7s}{'|rho_LD|':>10s}{'rango':>16s}")
for f, w in sorted(((f, imp[f]) for f in SHAPE), key=lambda t: -t[1]):
    # correlacion de Spearman del parametro con LD (senal directa, sin el modelo)
    rho = abs(spearmanr(ok[f], ok["LD"]).correlation)
    lo, hi = RANGES[f]
    print(f"{f:32s}{w*100:6.1f}%{rho:10.3f}   [{lo:g}, {hi:g}]")
