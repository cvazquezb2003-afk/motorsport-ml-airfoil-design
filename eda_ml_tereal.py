"""
ETAPA 2 — Reentrena surrogates + ensemble sobre airfoil_dataset_TEreal.csv.
Protocolo IDENTICO a eda_ml_filtrado150.py: 11 features feature_utils, filtro >=150,
CL=Lineal, CD/LD=XGBoost (LD tuneado), GroupKFold=5.
Compara VIEJO vs NUEVO sobre los MISMOS perfiles (aisla el efecto TE).
Guarda modelos *_tereal.joblib. NO toca produccion.
"""
import os, json, datetime
import numpy as np
import pandas as pd
import joblib
from sklearn.model_selection import GroupKFold, cross_val_predict, cross_val_score
from sklearn.linear_model import LinearRegression
from xgboost import XGBRegressor
from feature_utils import SHAPE, FEATURES, add_derived

BASE = os.path.dirname(os.path.abspath(__file__))
CHORD_MIN = 150.0
LD_TUNED = dict(n_estimators=400, learning_rate=0.02, max_depth=10,
                min_child_weight=5, subsample=0.6, colsample_bytree=0.9,
                reg_alpha=0.5, reg_lambda=5.0, random_state=42, n_jobs=-1)
def mk(tgt):
    if tgt == "CL":
        return LinearRegression()
    if tgt == "LD":
        return XGBRegressor(**LD_TUNED)
    return XGBRegressor(n_estimators=400, learning_rate=0.05, max_depth=5,
                        subsample=0.8, colsample_bytree=0.8, random_state=42, n_jobs=-1)

new = pd.read_csv(os.path.join(BASE, "airfoil_dataset_TEreal.csv"))
old = pd.read_csv(os.path.join(BASE, "airfoil_dataset.csv"))
pset = set(new.run_id.unique())
old = old[old.run_id.isin(pset)]                    # MISMOS perfiles -> A/B limpio

def prep(d):
    ok = d[d["status"] == "ok"].copy()
    ok = add_derived(ok)
    return ok[ok["chord_length_mm"] >= CHORD_MIN].reset_index(drop=True)
fN, fO = prep(new), prep(old)
print(f"[DATOS] TE-real: {fN.run_id.nunique()} perf / {len(fN)} filas | "
      f"viejo(mismos perf): {fO.run_id.nunique()} perf / {len(fO)} filas")

def cv(f, tgt):
    X, y, g = f[FEATURES].values, f[tgt].values, f.run_id.values
    gkf = GroupKFold(n_splits=5)
    pred = cross_val_predict(mk(tgt), X, y, groups=g, cv=gkf, n_jobs=-1)
    mae = float(np.mean(np.abs(y - pred)))
    r2 = float(cross_val_score(mk(tgt), X, y, groups=g, cv=gkf, scoring="r2").mean())
    return mae, r2

# ---------- 1) metricas viejo vs nuevo ----------
print("\n" + "=" * 70); print("1) METRICAS CV — VIEJO (amputado) vs NUEVO (TE-real), mismos perfiles"); print("=" * 70)
print(f"  {'tgt':5s}{'MAE_viejo':>12s}{'MAE_nuevo':>12s}{'R2_viejo':>10s}{'R2_nuevo':>10s}")
for tgt in ["CL", "CD", "LD"]:
    mo, ro = cv(fO, tgt); mn, rn = cv(fN, tgt)
    print(f"  {tgt:5s}{mo:12.5f}{mn:12.5f}{ro:10.3f}{rn:10.3f}")

# ---------- 2) importancias XGBoost (CD, LD) ----------
print("\n" + "=" * 70); print("2) IMPORTANCIAS XGBoost — viejo vs nuevo (CD y LD)"); print("=" * 70)
def imp(f, tgt):
    m = mk(tgt); m.fit(f[FEATURES].values, f[tgt].values)
    return dict(zip(FEATURES, m.feature_importances_))
for tgt in ["CD", "LD"]:
    iO, iN = imp(fO, tgt), imp(fN, tgt)
    print(f"\n  [{tgt}]  {'feature':30s}{'viejo':>9s}{'nuevo':>9s}")
    for feat in FEATURES:
        print(f"        {feat:30s}{iO[feat]*100:8.1f}%{iN[feat]*100:8.1f}%")

# ---------- 3) correlaciones te_thickness / te_rel (dataset nuevo) ----------
print("\n" + "=" * 70); print("3) CORRELACIONES en el dataset NUEVO (y viejo para contraste)"); print("=" * 70)
print(f"  {'feature':28s}{'target':4s}{'viejo':>9s}{'nuevo':>9s}")
for feat in ["trailing_edge_thickness_mm", "te_rel"]:
    for tgt in ["CL", "CD", "LD"]:
        co = np.corrcoef(fO[feat], fO[tgt])[0, 1]
        cn = np.corrcoef(fN[feat], fN[tgt])[0, 1]
        print(f"  {feat:28s}{tgt:4s}{co:9.3f}{cn:9.3f}")

# ---------- guardar modelo LD tereal + meta ----------
ld = mk("LD"); ld.fit(fN[FEATURES].values, fN["LD"].values)
meta = {"target": "LD", "features": FEATURES, "dataset": "airfoil_dataset_TEreal.csv",
        "n_perfiles": int(fN.run_id.nunique()), "n_filas_ok": int(len(fN)),
        "best_params": LD_TUNED, "fecha": datetime.datetime.now().isoformat(timespec="seconds")}
joblib.dump({"model": ld, "meta": meta}, os.path.join(BASE, "modelo_LD_inversa_xgb_tereal.joblib"))
json.dump(meta, open(os.path.join(BASE, "modelo_LD_inversa_meta_tereal.json"), "w",
                     encoding="utf-8"), indent=2, ensure_ascii=False)
print("\n[OK] modelo LD -> modelo_LD_inversa_xgb_tereal.joblib")

# ---------- entrenar ENSEMBLE (bootstrap de perfiles) -> sigma ----------
print("[ENSEMBLE] entrenando 10 XGBoost sobre bootstrap de perfiles (~min)...")
perfiles = fN.run_id.unique()
ens = []
for m in range(10):
    rng = np.random.RandomState(1000 + m)
    boot = pd.unique(rng.choice(perfiles, size=len(perfiles), replace=True))
    sub = fN[fN.run_id.isin(boot)]
    params = {**LD_TUNED, "random_state": 1000 + m}
    mdl = XGBRegressor(**params)
    mdl.fit(sub[FEATURES].values, sub["LD"].values)
    ens.append(mdl)
joblib.dump(ens, os.path.join(BASE, "ensemble_ld_sigma_tereal.joblib"))
print(f"[OK] ensemble -> ensemble_ld_sigma_tereal.joblib ({len(ens)} miembros)")
print("\n[OK] ETAPA 2 completada. Produccion INTACTA.")
