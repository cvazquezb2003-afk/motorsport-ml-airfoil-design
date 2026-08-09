"""
Reentreno con dataset FILTRADO a cuerda >= 150 mm (excluye 100-150, franja de
convergencias dudosas a Reynolds bajo). Protocolo de siempre: split por perfil,
CV GroupKFold=5. CL=Lineal, CD=XGBoost, LD=XGBoost. Compara con:
  (a) previo solo 200-400  y  (b) todo 100-500.
Da error por zona (150-200, 200-400, 400-500). Guarda 'filtrado_150_500' en
historico y RE-GUARDA el modelo de inversa de LD entrenado con datos >=150.
Solo lectura del dataset; NO borra filas del CSV (excluye <150 al entrenar).
"""
import os, json, datetime
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.model_selection import GroupKFold, cross_val_predict, cross_val_score
from sklearn.linear_model import LinearRegression
from xgboost import XGBRegressor
import joblib

BASE = os.path.dirname(os.path.abspath(__file__))
HIST_JSON = os.path.join(BASE, "ml_history.json")
# Features desde la FUENTE UNICA (base 9 + 2 derivadas fisicas). Debe coincidir
# con lo que calcula la inversa (inversa_ld_v2.py), por eso se importa de aqui.
from feature_utils import SHAPE, FEATURES, add_derived
WINNER = {"CL": "XGBoost", "CD": "XGBoost", "LD": "XGBoost"}
# CL pasado de Lineal a XGBoost (2026-07-24): CL es lineal en alpha pero NO en
# Reynolds; el lineal arrastraba ~4.4% de sesgo. XGBoost: MAE -62%, R2 0.930->0.984.
CHORD_MIN = 150.0
# Hiperparametros tuneados de LD (de la busqueda anterior); CD/CL por defecto.
LD_TUNED = dict(n_estimators=400, learning_rate=0.02, max_depth=10,
                min_child_weight=5, subsample=0.6, colsample_bytree=0.9,
                reg_alpha=0.5, reg_lambda=5.0, random_state=42, n_jobs=-1)
def mk(tgt):
    if tgt == "LD":
        return XGBRegressor(**LD_TUNED)
    # CL y CD: XGBoost con los mismos hiperparametros (CL validado 2026-07-24)
    return XGBRegressor(n_estimators=400, learning_rate=0.05, max_depth=5,
                        subsample=0.8, colsample_bytree=0.8, random_state=42, n_jobs=-1)

df = pd.read_csv(os.path.join(BASE, "airfoil_dataset.csv"))
ok = df[df["status"] == "ok"].copy()
ok = add_derived(ok)   # anade alpha_over_sqrtre y te_rel (las 2 features nuevas)
filt = ok[ok["chord_length_mm"] >= CHORD_MIN].copy().reset_index(drop=True)   # >=150
prev = ok[ok["source"].isin(["random", "sobol"])].copy().reset_index(drop=True)  # 200-400
full = ok.copy().reset_index(drop=True)                                          # 100-500
print(f"[FILTRO cuerda>=150] perfiles: {filt['run_id'].nunique()} (de {ok['run_id'].nunique()}), "
      f"filas ok: {len(filt)}")
print(f"  excluidos (<150mm): {ok['run_id'].nunique() - filt['run_id'].nunique()} perfiles, "
      f"{len(ok) - len(filt)} filas")

def spearman_cond(frame, yr, yp):
    t = frame[["alpha_deg", "velocidad_kmh"]].copy(); t["r"] = yr; t["p"] = yp
    rr = [spearmanr(g["r"], g["p"]).correlation for _, g in t.groupby(["alpha_deg", "velocidad_kmh"]) if len(g) >= 5]
    rr = [r for r in rr if np.isfinite(r)]
    return float(np.mean(rr)) if rr else float("nan")

def evalua(frame, tgt):
    frame = frame.reset_index(drop=True)
    X = frame[FEATURES].values; y = frame[tgt].values; g = frame["run_id"].values
    gkf = GroupKFold(n_splits=5)
    pred = cross_val_predict(mk(tgt), X, y, groups=g, cv=gkf, n_jobs=-1)
    mae = float(np.mean(np.abs(y - pred)))
    r2 = float(cross_val_score(mk(tgt), X, y, groups=g, cv=gkf, scoring="r2").mean())
    return mae, r2, spearman_cond(frame, y, pred), pred

print("\n" + "=" * 84)
print("COMPARATIVA:  (a) previo 200-400   (b) todo 100-500   (c) FILTRADO 150-500")
print("=" * 84)
print(f"{'tgt':4s}{'':9s}{'MAE_200-400':>13s}{'MAE_100-500':>13s}{'MAE_150-500':>13s}"
      f"{'R2_200-400':>12s}{'R2_100-500':>12s}{'R2_150-500':>12s}")
oof_filt = {}
metrics_filt = {}
sp_row = {}
for tgt in ("CL", "CD", "LD"):
    ma, ra, sa, _ = evalua(prev, tgt)
    mb, rb, sb, _ = evalua(full, tgt)
    mc, rc, sc, pc = evalua(filt, tgt)
    oof_filt[tgt] = pc
    metrics_filt[tgt] = {"mae": mc, "r2": rc, "spear_cond": sc}
    sp_row[tgt] = (sa, sb, sc)
    print(f"{tgt:4s}{WINNER[tgt]:9s}{ma:13.5f}{mb:13.5f}{mc:13.5f}{ra:12.3f}{rb:12.3f}{rc:12.3f}")
print("\n  Spearman por condicion (200-400 | 100-500 | 150-500):")
for tgt in ("CL", "CD", "LD"):
    print(f"    {tgt}: {sp_row[tgt][0]:.3f} | {sp_row[tgt][1]:.3f} | {sp_row[tgt][2]:.3f}")

# ---------- error por zona en el FILTRADO ----------
ZONAS = [("150-200", 150, 200), ("200-400", 200, 400), ("400-500", 400, 500)]
print("\n" + "=" * 84)
print("ERROR POR ZONA (modelo FILTRADO 150-500, out-of-fold)")
print("=" * 84)
for tgt in ("CD", "LD"):
    y = filt[tgt].values; pred = oof_filt[tgt]
    print(f"\n[{tgt}]  {'zona':10s}{'n_filas':>9s}{'n_perf':>8s}{'MAE':>12s}{'R2':>8s}{'MAE/std':>9s}")
    for name, lo, hi in ZONAS:
        m = ((filt["chord_length_mm"] >= lo) & (filt["chord_length_mm"] < hi)).values
        yz, pz = y[m], pred[m]
        mae = np.mean(np.abs(yz - pz))
        ss_res = np.sum((yz - pz) ** 2); ss_tot = np.sum((yz - yz.mean()) ** 2)
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else float("nan")
        print(f"           {name:10s}{int(m.sum()):>9d}{filt[m]['run_id'].nunique():>8d}"
              f"{mae:12.5f}{r2:8.3f}{mae/yz.std()*100:8.0f}%")

# ---------- guardar en historico ----------
imp9 = {}; grouped = {}
for tgt in ("CD", "LD"):
    m = mk(tgt); m.fit(filt[FEATURES].values, filt[tgt].values)
    d = dict(zip(FEATURES, m.feature_importances_))
    imp9[tgt] = {f: float(d[f]) for f in FEATURES}
    grouped[tgt] = {"alpha_deg": float(d["alpha_deg"]),
                    "FORMA (7 params)": float(sum(d[f] for f in SHAPE)),
                    "reynolds": float(d["reynolds"])}
    if tgt == "CD":
        # PERSISTIR el modelo de CD (antes se ajustaba inline en los consumidores)
        meta_cd = {"target": "CD", "features": FEATURES, "dataset": "filtrado_150_500",
                   "n_perfiles": int(filt["run_id"].nunique()), "n_filas_ok": int(len(filt)),
                   "cv": {"mae": metrics_filt["CD"]["mae"], "r2": metrics_filt["CD"]["r2"]}}
        joblib.dump({"model": m, "meta": meta_cd},
                    os.path.join(BASE, "modelo_CD_xgb.joblib"))
        print("[OK] modelo de CD GUARDADO (modelo_CD_xgb.joblib)")
    if tgt == "LD":
        # RE-GUARDAR el modelo de inversa con datos filtrados >=150
        meta = {"target": "LD", "features": FEATURES, "dataset": "filtrado_150_500",
                "n_perfiles": int(filt["run_id"].nunique()), "n_filas_ok": int(len(filt)),
                "best_params": LD_TUNED,
                "cv": {"mae": metrics_filt["LD"]["mae"], "r2": metrics_filt["LD"]["r2"],
                       "spear_cond": metrics_filt["LD"]["spear_cond"]}}
        joblib.dump({"model": m, "meta": meta},
                    os.path.join(BASE, "modelo_LD_inversa_xgb.joblib"))
        json.dump(meta, open(os.path.join(BASE, "modelo_LD_inversa_meta.json"), "w",
                             encoding="utf-8"), indent=2, ensure_ascii=False)
        print("\n[OK] modelo de inversa RE-GUARDADO con datos >=150 (modelo_LD_inversa_xgb.joblib)")

hist = json.load(open(HIST_JSON, encoding="utf-8")) if os.path.exists(HIST_JSON) else []
hist.append({"fecha": datetime.datetime.now().isoformat(timespec="seconds"),
             "label": "filtrado_150_500", "n_perfiles": int(filt["run_id"].nunique()),
             "n_filas_ok": int(len(filt)), "features": FEATURES, "winner": WINNER,
             "metrics": {t: {"mean": float(filt[t].mean()), "std": float(filt[t].std()),
                             "models": {WINNER[t]: {"mae": metrics_filt[t]["mae"], "mae_std": 0.0,
                                                    "r2": metrics_filt[t]["r2"], "r2_std": 0.0}}}
                         for t in ("CL", "CD", "LD")},
             "importancia_9inputs": imp9, "importancia_agrupada": grouped})
json.dump(hist, open(HIST_JSON, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
print(f"[OK] guardado 'filtrado_150_500' en historico ({len(hist)} entradas)")
