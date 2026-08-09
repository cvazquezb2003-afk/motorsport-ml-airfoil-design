"""
Dos comprobaciones sobre los modelos actuales (400 perfiles Sobol, filas ok,
split POR PERFIL, CV GroupKFold=5). No toca el pipeline.

COMP 1 - capacidad de ORDENAR: Spearman entre predicho y real sobre perfiles de
         test (out-of-fold). Dos versiones:
           * global: sobre TODAS las filas de test (mezcla alpha/velocidad).
           * por condicion: dentro de cada (alpha,velocidad) rankea perfiles y
             promedia Spearman -> mide si ordena FORMAS a igualdad de condicion
             (lo relevante para busqueda inversa).
COMP 2 - RandomForest vs XGBoost (MAE, R2, Spearman), mismos splits.
"""
import os
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.model_selection import GroupKFold, cross_val_predict, cross_val_score
from sklearn.ensemble import RandomForestRegressor
from xgboost import XGBRegressor

BASE = os.path.dirname(os.path.abspath(__file__))
SHAPE = ["chord_length_mm", "leading_edge_angle_deg", "leading_edge_thickness_level",
         "trailing_edge_angle_deg", "trailing_edge_thickness_mm",
         "te_upr_angle_deg", "te_lwr_angle_deg"]
FEATURES = SHAPE + ["alpha_deg", "reynolds"]

df = pd.read_csv(os.path.join(BASE, "airfoil_dataset.csv"))
sub = df[(df["status"] == "ok") & (df["source"] == "sobol")].copy().reset_index(drop=True)
X = sub[FEATURES].values
groups = sub["run_id"].values
gkf = GroupKFold(n_splits=5)
print(f"[DATOS] sobol ok: filas={len(sub)}  perfiles={sub['run_id'].nunique()}")

MODELS = {
    "RandomForest": RandomForestRegressor(n_estimators=400, random_state=42, n_jobs=-1),
    "XGBoost": XGBRegressor(n_estimators=400, learning_rate=0.05, max_depth=5,
                            subsample=0.8, colsample_bytree=0.8,
                            random_state=42, n_jobs=-1),
}


def spearman_por_condicion(y_real, y_pred):
    """Media de Spearman rankeando perfiles dentro de cada (alpha,velocidad)."""
    tmp = sub[["alpha_deg", "velocidad_kmh"]].copy()
    tmp["yr"] = y_real
    tmp["yp"] = y_pred
    rhos = []
    for _, g in tmp.groupby(["alpha_deg", "velocidad_kmh"]):
        if len(g) >= 5:                      # necesita varios perfiles para rankear
            rho = spearmanr(g["yr"], g["yp"]).correlation
            if np.isfinite(rho):
                rhos.append(rho)
    return float(np.mean(rhos)), len(rhos)


for tgt in ("LD", "CD"):
    y = sub[tgt].values
    print("\n" + "=" * 70)
    print(f"OBJETIVO {tgt}   (media={y.mean():.4f}  std={y.std():.4f})")
    print("=" * 70)
    print(f"{'modelo':13s}{'MAE':>11s}{'R2':>8s}{'Spear_glob':>12s}{'Spear_cond':>12s}")
    for mname, model in MODELS.items():
        # predicciones out-of-fold (cada fila predicha por un modelo que NO la vio)
        pred = cross_val_predict(model, X, y, groups=groups, cv=gkf, n_jobs=-1)
        mae = np.mean(np.abs(y - pred))
        # R2 CV (media de los folds, consistente con lo que veniamos reportando)
        r2 = cross_val_score(model, X, y, groups=groups, cv=gkf, scoring="r2").mean()
        sp_glob = spearmanr(y, pred).correlation
        sp_cond, ncond = spearman_por_condicion(y, pred)
        print(f"{mname:13s}{mae:11.5f}{r2:8.3f}{sp_glob:12.3f}{sp_cond:12.3f}")
    print(f"   (Spear_cond promediado sobre {ncond} condiciones alpha x velocidad)")
