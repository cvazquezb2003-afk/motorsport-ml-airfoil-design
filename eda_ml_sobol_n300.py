"""
Reentrena SOLO con los perfiles source=sobol (los 300 actuales), protocolo de
siempre: split por perfil, CV GroupKFold=5. CL lineal (principal), CD y LD RF.
Guarda en ml_history con etiqueta sobol_only_n300 y compara DIRECTAMENTE contra
la entrada sobol_only_n142 ya guardada (respuesta a: duplicar volumen mejora la
captacion de la forma?). Solo lectura del dataset, no toca el pipeline.
"""
import os
import json
import datetime
import numpy as np
import pandas as pd
from sklearn.model_selection import cross_val_score, GroupKFold
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor

BASE = os.path.dirname(os.path.abspath(__file__))
HIST_JSON = os.path.join(BASE, "ml_history.json")
HIST_CSV = os.path.join(BASE, "ml_history.csv")

SHAPE = ["chord_length_mm", "leading_edge_angle_deg", "leading_edge_thickness_level",
         "trailing_edge_angle_deg", "trailing_edge_thickness_mm",
         "te_upr_angle_deg", "te_lwr_angle_deg"]
FEATURES = SHAPE + ["alpha_deg", "reynolds"]
WINNER = {"CL": "Lineal", "CD": "RandomForest", "LD": "RandomForest"}
LABEL = "sobol_only_n300"


def mk_model(name):
    if name == "Lineal":
        return LinearRegression()
    return RandomForestRegressor(n_estimators=400, random_state=42, n_jobs=-1)


df = pd.read_csv(os.path.join(BASE, "airfoil_dataset.csv"))
sub = df[(df["status"] == "ok") & (df["source"] == "sobol")].copy()
X = sub[FEATURES].values
groups = sub["run_id"].values
gkf = GroupKFold(n_splits=5)
print(f"[DATOS] sobol ok: filas={len(sub)}  perfiles={sub['run_id'].nunique()}")

res = {"label": LABEL, "n_perfiles": int(sub["run_id"].nunique()),
       "n_filas_ok": int(len(sub)), "metrics": {}, "imp9": {}, "grouped": {}}
for tgt in ("CL", "CD", "LD"):
    y = sub[tgt].values
    res["metrics"][tgt] = {"mean": float(y.mean()), "std": float(y.std()), "models": {}}
    for mname in ("Lineal", "RandomForest"):
        mae = -cross_val_score(mk_model(mname), X, y, groups=groups, cv=gkf,
                               scoring="neg_mean_absolute_error")
        r2 = cross_val_score(mk_model(mname), X, y, groups=groups, cv=gkf, scoring="r2")
        res["metrics"][tgt]["models"][mname] = {
            "mae": float(mae.mean()), "mae_std": float(mae.std()),
            "r2": float(r2.mean()), "r2_std": float(r2.std())}
    rf = RandomForestRegressor(n_estimators=400, random_state=42, n_jobs=-1)
    rf.fit(X, y)
    d = dict(zip(FEATURES, rf.feature_importances_))
    res["imp9"][tgt] = {f: float(d[f]) for f in FEATURES}
    res["grouped"][tgt] = {"alpha_deg": float(d["alpha_deg"]),
                           "FORMA (7 params)": float(sum(d[f] for f in SHAPE)),
                           "reynolds": float(d["reynolds"])}
    w = WINNER[tgt]
    m = res["metrics"][tgt]["models"][w]
    print(f"   {tgt} ({w}): MAE={m['mae']:.5f}  R2={m['r2']:.3f}")

# ---------- guardar en historico ----------
hist = []
if os.path.exists(HIST_JSON):
    with open(HIST_JSON, "r", encoding="utf-8") as fh:
        try:
            hist = json.load(fh)
        except json.JSONDecodeError:
            hist = []

entry = {"fecha": datetime.datetime.now().isoformat(timespec="seconds"), "label": LABEL,
         "n_perfiles": res["n_perfiles"], "n_filas_ok": res["n_filas_ok"],
         "features": FEATURES, "winner": WINNER, "metrics": res["metrics"],
         "importancia_9inputs": res["imp9"], "importancia_agrupada": res["grouped"]}
hist.append(entry)
with open(HIST_JSON, "w", encoding="utf-8") as fh:
    json.dump(hist, fh, indent=2, ensure_ascii=False)

rows = []
for run in hist:
    for tgt in ("CL", "CD", "LD"):
        w = run["winner"][tgt]
        m = run["metrics"][tgt]["models"][w]
        row = {"fecha": run["fecha"], "label": run.get("label", ""),
               "n_perfiles": run["n_perfiles"], "n_filas_ok": run["n_filas_ok"],
               "objetivo": tgt, "metodo": w, "mae": m["mae"], "mae_std": m["mae_std"],
               "r2": m["r2"], "r2_std": m["r2_std"],
               "imp_alpha": run["importancia_agrupada"][tgt]["alpha_deg"],
               "imp_forma": run["importancia_agrupada"][tgt]["FORMA (7 params)"],
               "imp_reynolds": run["importancia_agrupada"][tgt]["reynolds"]}
        for f in run["features"]:
            row[f"imp_{f}"] = run["importancia_9inputs"][tgt][f]
        rows.append(row)
pd.DataFrame(rows).to_csv(HIST_CSV, index=False)

# ---------- comparacion DIRECTA n142 vs n300 ----------
prev = next((h for h in hist if h.get("label") == "sobol_only_n142"), None)
if prev is None:
    print("[WARN] no encontre sobol_only_n142 en el historico.")
else:
    print("\n" + "#" * 76)
    print("# SOBOL n142 vs n300  --  MAE / R2 (metodo principal)")
    print("#" * 76)
    print(f"{'obj':4s}{'metodo':13s}{'MAE_142':>10s}{'MAE_300':>10s}{'R2_142':>9s}{'R2_300':>9s}")
    for tgt in ("CL", "CD", "LD"):
        w = WINNER[tgt]
        a = prev["metrics"][tgt]["models"][w]; b = res["metrics"][tgt]["models"][w]
        print(f"{tgt:4s}{w:13s}{a['mae']:10.5f}{b['mae']:10.5f}{a['r2']:9.3f}{b['r2']:9.3f}")

    print("\n" + "#" * 76)
    print("# IMPORTANCIA AGRUPADA (%)  alpha / FORMA / reynolds   n142 vs n300")
    print("#" * 76)
    print(f"{'obj':5s}{'grupo':20s}{'n142':>8s}{'n300':>8s}{'delta':>8s}")
    for tgt in ("CL", "CD", "LD"):
        for grp in ("alpha_deg", "FORMA (7 params)", "reynolds"):
            a = prev["importancia_agrupada"][tgt][grp] * 100
            b = res["grouped"][tgt][grp] * 100
            print(f"{tgt:5s}{grp:20s}{a:7.1f}%{b:7.1f}%{b-a:+7.1f}%")

    print("\n" + "#" * 76)
    print("# FORMA POR PARAMETRO (%)   n142 vs n300  (delta)")
    print("#" * 76)
    for tgt in ("CL", "CD", "LD"):
        print(f"\n-- {tgt} --   {'param':32s}{'n142':>8s}{'n300':>8s}{'delta':>8s}")
        for f in SHAPE:
            a = prev["importancia_9inputs"][tgt][f] * 100
            b = res["imp9"][tgt][f] * 100
            print(f"{'':10s}{f:32s}{a:7.1f}%{b:7.1f}%{b-a:+7.1f}%")

print(f"\n[OK] guardado {LABEL} en historico ({len(hist)} entradas)")
