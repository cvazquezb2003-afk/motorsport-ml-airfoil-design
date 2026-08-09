"""
Modelo FINAL de L/D para la inversa. Sin tocar el pipeline.
1) XGBoost LD con 542 perfiles (400 sobol + 142 random, filas ok) vs solo-400-sobol.
   Split por perfil, CV GroupKFold=5. Metricas: MAE, R2, Spearman por condicion.
2) Sobre el dataset ganador, tunea XGBoost (RandomizedSearchCV con GroupKFold,
   sin fuga). Por defecto vs tuneado.
3) Guarda el mejor modelo (joblib) para la inversa.
"""
import os
import json
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.model_selection import (GroupKFold, cross_val_predict,
                                     cross_val_score, RandomizedSearchCV)
from xgboost import XGBRegressor
import joblib

BASE = os.path.dirname(os.path.abspath(__file__))
SHAPE = ["chord_length_mm", "leading_edge_angle_deg", "leading_edge_thickness_level",
         "trailing_edge_angle_deg", "trailing_edge_thickness_mm",
         "te_upr_angle_deg", "te_lwr_angle_deg"]
FEATURES = SHAPE + ["alpha_deg", "reynolds"]
TGT = "LD"

df = pd.read_csv(os.path.join(BASE, "airfoil_dataset.csv"))
ok = df[df["status"] == "ok"].copy()

DEFAULT_XGB = dict(n_estimators=400, learning_rate=0.05, max_depth=5,
                   subsample=0.8, colsample_bytree=0.8, random_state=42, n_jobs=-1)


def spearman_por_condicion(frame, y_real, y_pred):
    tmp = frame[["alpha_deg", "velocidad_kmh"]].copy()
    tmp["yr"] = y_real; tmp["yp"] = y_pred
    rhos = []
    for _, g in tmp.groupby(["alpha_deg", "velocidad_kmh"]):
        if len(g) >= 5:
            rho = spearmanr(g["yr"], g["yp"]).correlation
            if np.isfinite(rho):
                rhos.append(rho)
    return float(np.mean(rhos)), len(rhos)


def evaluar(frame, model, label):
    frame = frame.reset_index(drop=True)
    X = frame[FEATURES].values
    y = frame[TGT].values
    groups = frame["run_id"].values
    gkf = GroupKFold(n_splits=5)
    pred = cross_val_predict(model, X, y, groups=groups, cv=gkf, n_jobs=-1)
    mae = float(np.mean(np.abs(y - pred)))
    r2 = float(cross_val_score(model, X, y, groups=groups, cv=gkf, scoring="r2").mean())
    sp, nc = spearman_por_condicion(frame, y, pred)
    print(f"   {label:28s} MAE={mae:.5f}  R2={r2:.3f}  Spear_cond={sp:.3f}  (n_perf={frame['run_id'].nunique()})")
    return {"mae": mae, "r2": r2, "spear_cond": sp}


# ---------- 1) 400 sobol vs 542 combinado ----------
sob = ok[ok["source"] == "sobol"].copy()
allp = ok.copy()
print("=" * 74)
print("1) DATASET: solo-400-sobol  vs  542-combinado (XGBoost por defecto, LD)")
print("=" * 74)
r_400 = evaluar(sob, XGBRegressor(**DEFAULT_XGB), "solo-400-sobol")
r_542 = evaluar(allp, XGBRegressor(**DEFAULT_XGB), "542-combinado")

mejora = (r_542["r2"] >= r_400["r2"] - 0.005)   # igual o mejor (margen ruido)
winner_df = allp if mejora else sob
winner_name = "542-combinado" if mejora else "solo-400-sobol"
print(f"\n   -> Dataset ganador: {winner_name}")

# ---------- 2) tuning sobre el ganador ----------
print("\n" + "=" * 74)
print(f"2) TUNING XGBoost (RandomizedSearchCV, GroupKFold=5) sobre {winner_name}")
print("=" * 74)
wf = winner_df.reset_index(drop=True)
Xw = wf[FEATURES].values
yw = wf[TGT].values
gw = wf["run_id"].values
gkf = GroupKFold(n_splits=5)

param_dist = {
    "n_estimators": [200, 400, 600, 800, 1200],
    "learning_rate": [0.01, 0.02, 0.03, 0.05, 0.08, 0.1],
    "max_depth": [3, 4, 5, 6, 8, 10],
    "subsample": [0.6, 0.7, 0.8, 0.9, 1.0],
    "colsample_bytree": [0.6, 0.7, 0.8, 0.9, 1.0],
    "min_child_weight": [1, 3, 5, 7],
    "reg_lambda": [0.5, 1.0, 2.0, 5.0],
    "reg_alpha": [0.0, 0.1, 0.5, 1.0],
}
search = RandomizedSearchCV(
    XGBRegressor(random_state=42, n_jobs=-1),
    param_distributions=param_dist, n_iter=60, scoring="r2",
    cv=gkf, random_state=42, n_jobs=-1, verbose=0)
search.fit(Xw, yw, groups=gw)
best_params = search.best_params_
print("   mejores hiperparametros:")
for k, v in sorted(best_params.items()):
    print(f"      {k:18s} {v}")

print("\n   --- comparacion en el dataset ganador ---")
r_def = evaluar(wf, XGBRegressor(**DEFAULT_XGB), "XGBoost por defecto")
r_tun = evaluar(wf, XGBRegressor(random_state=42, n_jobs=-1, **best_params), "XGBoost tuneado")

# ---------- 3) guardar el mejor modelo (entrenado con TODO el ganador) ----------
best_model = XGBRegressor(random_state=42, n_jobs=-1, **best_params)
best_model.fit(Xw, yw)
model_path = os.path.join(BASE, "modelo_LD_inversa_xgb.joblib")
meta = {"target": TGT, "features": FEATURES, "dataset": winner_name,
        "n_perfiles": int(wf["run_id"].nunique()), "n_filas_ok": int(len(wf)),
        "best_params": best_params,
        "cv_por_defecto": r_def, "cv_tuneado": r_tun}
joblib.dump({"model": best_model, "meta": meta}, model_path)
with open(os.path.join(BASE, "modelo_LD_inversa_meta.json"), "w", encoding="utf-8") as f:
    json.dump(meta, f, indent=2, ensure_ascii=False)
print(f"\n[OK] modelo guardado -> {os.path.basename(model_path)}")
print(f"[OK] meta -> modelo_LD_inversa_meta.json")
