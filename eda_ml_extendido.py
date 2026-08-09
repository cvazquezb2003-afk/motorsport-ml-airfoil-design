"""
Reentreno con dataset AMPLIADO (todas las filas ok, cuerda 100-500) y analisis
POR ZONA DE CUERDA. Protocolo de siempre: split por perfil, CV GroupKFold=5.
CL=Lineal, CD=XGBoost, LD=XGBoost. Compara 'previo' (solo 200-400: source
random/sobol) vs 'extendido' (todo). Guarda el extendido en ml_history.

NOTA: el espesor de TE es en mm ABSOLUTOS en TODO el dataset (no proporcional a
la cuerda). No hay conversion proporcional; se entrena con los datos reales.
Solo lectura del dataset, no toca el pipeline.
"""
import os, json, datetime
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.model_selection import GroupKFold, cross_val_predict, cross_val_score
from sklearn.linear_model import LinearRegression
from xgboost import XGBRegressor

BASE = os.path.dirname(os.path.abspath(__file__))
HIST_JSON = os.path.join(BASE, "ml_history.json")
HIST_CSV = os.path.join(BASE, "ml_history.csv")
SHAPE = ["chord_length_mm", "leading_edge_angle_deg", "leading_edge_thickness_level",
         "trailing_edge_angle_deg", "trailing_edge_thickness_mm",
         "te_upr_angle_deg", "te_lwr_angle_deg"]
FEATURES = SHAPE + ["alpha_deg", "reynolds"]
WINNER = {"CL": "Lineal", "CD": "XGBoost", "LD": "XGBoost"}

def mk(name):
    if name == "Lineal":
        return LinearRegression()
    return XGBRegressor(n_estimators=400, learning_rate=0.05, max_depth=5,
                        subsample=0.8, colsample_bytree=0.8, random_state=42, n_jobs=-1)

df = pd.read_csv(os.path.join(BASE, "airfoil_dataset.csv"))
ok = df[df["status"] == "ok"].copy().reset_index(drop=True)
previo = ok[ok["source"].isin(["random", "sobol"])].copy().reset_index(drop=True)   # 200-400
print(f"[DATOS] extendido: {len(ok)} filas / {ok['run_id'].nunique()} perfiles")
print(f"[DATOS] previo(200-400): {len(previo)} filas / {previo['run_id'].nunique()} perfiles")

def spearman_cond(frame, yr, yp):
    t = frame[["alpha_deg", "velocidad_kmh"]].copy(); t["r"] = yr; t["p"] = yp
    rhos = [spearmanr(g["r"], g["p"]).correlation for _, g in t.groupby(["alpha_deg", "velocidad_kmh"]) if len(g) >= 5]
    rhos = [r for r in rhos if np.isfinite(r)]
    return float(np.mean(rhos)) if rhos else float("nan")

def evalua(frame, tgt):
    frame = frame.reset_index(drop=True)
    X = frame[FEATURES].values; y = frame[tgt].values; g = frame["run_id"].values
    gkf = GroupKFold(n_splits=5)
    pred = cross_val_predict(mk(WINNER[tgt]), X, y, groups=g, cv=gkf, n_jobs=-1)
    mae = float(np.mean(np.abs(y - pred)))
    r2 = float(cross_val_score(mk(WINNER[tgt]), X, y, groups=g, cv=gkf, scoring="r2").mean())
    sp = spearman_cond(frame, y, pred)
    return mae, r2, sp, pred

print("\n" + "=" * 74)
print("GLOBAL: previo (200-400) vs extendido (100-500)")
print("=" * 74)
print(f"{'tgt':4s}{'modelo':9s}{'MAE_prev':>11s}{'MAE_ext':>11s}{'R2_prev':>9s}{'R2_ext':>9s}{'Sp_prev':>9s}{'Sp_ext':>9s}")
oof = {}
metrics_ext = {}
for tgt in ("CL", "CD", "LD"):
    mp, rp, sp_p, _ = evalua(previo, tgt)
    me, re_, sp_e, pred_ext = evalua(ok, tgt)
    oof[tgt] = pred_ext
    metrics_ext[tgt] = {"mae": me, "r2": re_, "spear_cond": sp_e}
    print(f"{tgt:4s}{WINNER[tgt]:9s}{mp:11.5f}{me:11.5f}{rp:9.3f}{re_:9.3f}{sp_p:9.3f}{sp_e:9.3f}")

# ---------- ERROR POR ZONA DE CUERDA (out-of-fold del extendido) ----------
ZONAS = [("100-150", 100, 150), ("150-200", 150, 200), ("200-400", 200, 400),
         ("400-500", 400, 500)]
print("\n" + "=" * 74)
print("ERROR POR ZONA DE CUERDA (predicciones out-of-fold, perfiles no vistos)")
print("=" * 74)
for tgt in ("CD", "LD"):
    y = ok[tgt].values; pred = oof[tgt]
    print(f"\n[{tgt}]  {'zona':10s}{'n_filas':>9s}{'n_perf':>8s}{'MAE':>11s}{'R2':>8s}{'MAE/std':>9s}")
    for name, lo, hi in ZONAS:
        m = (ok["chord_length_mm"] >= lo) & (ok["chord_length_mm"] < hi)
        if m.sum() < 5:
            print(f"           {name:10s}{int(m.sum()):>9d}   (pocos datos)")
            continue
        yz, pz = y[m.values], pred[m.values]
        mae = np.mean(np.abs(yz - pz))
        # R2 zona
        ss_res = np.sum((yz - pz) ** 2); ss_tot = np.sum((yz - yz.mean()) ** 2)
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else float("nan")
        std = yz.std()
        print(f"           {name:10s}{int(m.sum()):>9d}{ok[m]['run_id'].nunique():>8d}"
              f"{mae:11.5f}{r2:8.3f}{mae/std*100:8.0f}%")

# ---------- guardar extendido en historico ----------
imp9 = {}; grouped = {}
for tgt in ("CL", "CD", "LD"):
    if WINNER[tgt] == "Lineal":
        continue
    m = mk(WINNER[tgt]); m.fit(ok[FEATURES].values, ok[tgt].values)
    d = dict(zip(FEATURES, m.feature_importances_))
    imp9[tgt] = {f: float(d[f]) for f in FEATURES}
    grouped[tgt] = {"alpha_deg": float(d["alpha_deg"]),
                    "FORMA (7 params)": float(sum(d[f] for f in SHAPE)),
                    "reynolds": float(d["reynolds"])}

hist = json.load(open(HIST_JSON, encoding="utf-8")) if os.path.exists(HIST_JSON) else []
entry = {"fecha": datetime.datetime.now().isoformat(timespec="seconds"),
         "label": "extendido_100_500", "n_perfiles": int(ok["run_id"].nunique()),
         "n_filas_ok": int(len(ok)), "features": FEATURES, "winner": WINNER,
         "metrics": {t: {"mean": float(ok[t].mean()), "std": float(ok[t].std()),
                         "models": {WINNER[t]: {"mae": metrics_ext[t]["mae"], "mae_std": 0.0,
                                                "r2": metrics_ext[t]["r2"], "r2_std": 0.0}}}
                     for t in ("CL", "CD", "LD")},
         "importancia_9inputs": imp9, "importancia_agrupada": grouped}
hist.append(entry)
json.dump(hist, open(HIST_JSON, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
print(f"\n[OK] guardado 'extendido_100_500' en historico ({len(hist)} entradas)")
