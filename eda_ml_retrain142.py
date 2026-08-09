"""
Reentrenamiento de los 3 modelos (CL, CD, LD) con el dataset ampliado.
Mismo enfoque honesto: split POR PERFIL, CV GroupKFold=5 (MAE y R2).
CL -> Lineal (ganaba); CD y LD -> RandomForest (ganaban). Entrena ambos para
confirmar. Importancia de los 9 inputs (RF) por modelo, agrupada forma/alpha/Re.
Solo lectura del dataset, no toca el pipeline.
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
HIST_JSON = os.path.join(BASE, "ml_history.json")   # log completo (append)
HIST_CSV = os.path.join(BASE, "ml_history.csv")     # vista plana para comparar
SHAPE = ["chord_length_mm", "leading_edge_angle_deg", "leading_edge_thickness_level",
         "trailing_edge_angle_deg", "trailing_edge_thickness_mm",
         "te_upr_angle_deg", "te_lwr_angle_deg"]
FEATURES = SHAPE + ["alpha_deg", "reynolds"]

df = pd.read_csv(os.path.join(BASE, "airfoil_dataset.csv"))
ok = df[df["status"] == "ok"].copy()
print(f"[DATOS] filas ok: {len(ok)} | perfiles: {ok['run_id'].nunique()}")
X = ok[FEATURES].values
groups = ok["run_id"].values
gkf = GroupKFold(n_splits=5)

MODELS = {
    "Lineal": lambda: LinearRegression(),
    "RandomForest": lambda: RandomForestRegressor(n_estimators=400, random_state=42, n_jobs=-1),
}

def cv_metrics(y, model_fn):
    mae = -cross_val_score(model_fn(), X, y, groups=groups, cv=gkf,
                           scoring="neg_mean_absolute_error")
    r2 = cross_val_score(model_fn(), X, y, groups=groups, cv=gkf, scoring="r2")
    return mae.mean(), mae.std(), r2.mean(), r2.std()

# Metodo "ganador" por objetivo (el que reportamos como principal).
WINNER = {"CL": "Lineal", "CD": "RandomForest", "LD": "RandomForest"}

metrics = {}   # metrics[tgt][modelo] = {mae, mae_std, r2, r2_std}
print("\n" + "=" * 78)
print("CV POR PERFIL (GroupKFold=5)  --  MAE y R2 medios")
print("=" * 78)
for tgt in ("CL", "CD", "LD"):
    y = ok[tgt].values
    metrics[tgt] = {"mean": float(y.mean()), "std": float(y.std()), "models": {}}
    print(f"\n[{tgt}]  media={y.mean():.4f}  std={y.std():.4f}")
    for mname, mfn in MODELS.items():
        mae_m, mae_s, r2_m, r2_s = cv_metrics(y, mfn)
        metrics[tgt]["models"][mname] = {
            "mae": float(mae_m), "mae_std": float(mae_s),
            "r2": float(r2_m), "r2_std": float(r2_s)}
        star = " <-- principal" if mname == WINNER[tgt] else ""
        print(f"   {mname:13s} MAE={mae_m:.5f}+/-{mae_s:.5f}   R2={r2_m:.3f}+/-{r2_s:.3f}{star}")

# ---- importancia de los 9 inputs (RF entrenado sobre TODO el dataset) ----
print("\n" + "=" * 78)
print("IMPORTANCIA DE LOS 9 INPUTS (Random Forest, entrenado sobre todo)")
print("=" * 78)
imp = {}
for tgt in ("CL", "CD", "LD"):
    rf = RandomForestRegressor(n_estimators=400, random_state=42, n_jobs=-1)
    rf.fit(X, ok[tgt].values)
    imp[tgt] = dict(zip(FEATURES, rf.feature_importances_))

hdr = f"{'input':32s}" + "".join(f"{t:>9s}" for t in ("CL", "CD", "LD"))
print(hdr)
for f in FEATURES:
    print(f"{f:32s}" + "".join(f"{imp[t][f]*100:8.1f}%" for t in ("CL", "CD", "LD")))

print("\n--- AGRUPADO (%) ---")
print(f"{'grupo':32s}" + "".join(f"{t:>9s}" for t in ("CL", "CD", "LD")))
grouped = {t: {} for t in ("CL", "CD", "LD")}
for label, keys in [("alpha_deg", ["alpha_deg"]),
                    ("FORMA (7 params)", SHAPE),
                    ("reynolds", ["reynolds"])]:
    print(f"{label:32s}" + "".join(f"{sum(imp[t][k] for k in keys)*100:8.1f}%" for t in ("CL", "CD", "LD")))
    for t in ("CL", "CD", "LD"):
        grouped[t][label] = float(sum(imp[t][k] for k in keys))

# =========================================================
# GUARDAR HISTORICO (append a JSON + vista plana en CSV)
# =========================================================
entry = {
    "fecha": datetime.datetime.now().isoformat(timespec="seconds"),
    "n_perfiles": int(ok["run_id"].nunique()),
    "n_filas_ok": int(len(ok)),
    "features": FEATURES,
    "winner": WINNER,
    "metrics": metrics,                                    # MAE/R2 por objetivo y modelo
    "importancia_9inputs": {t: {f: float(imp[t][f]) for f in FEATURES}
                            for t in ("CL", "CD", "LD")},   # RF, sobre todo el dataset
    "importancia_agrupada": grouped,                       # alpha / forma / reynolds
}

hist = []
if os.path.exists(HIST_JSON):
    with open(HIST_JSON, "r", encoding="utf-8") as fh:
        try:
            hist = json.load(fh)
        except json.JSONDecodeError:
            hist = []
hist.append(entry)
with open(HIST_JSON, "w", encoding="utf-8") as fh:
    json.dump(hist, fh, indent=2, ensure_ascii=False)

# vista plana: una fila por (fecha, n_perfiles, objetivo) con metricas del metodo
# principal + importancias agrupadas + importancia de cada input.
rows = []
for run in hist:
    for tgt in ("CL", "CD", "LD"):
        w = run["winner"][tgt]
        m = run["metrics"][tgt]["models"][w]
        row = {
            "fecha": run["fecha"], "n_perfiles": run["n_perfiles"],
            "n_filas_ok": run["n_filas_ok"], "objetivo": tgt, "metodo": w,
            "mae": m["mae"], "mae_std": m["mae_std"],
            "r2": m["r2"], "r2_std": m["r2_std"],
            "imp_alpha": run["importancia_agrupada"][tgt]["alpha_deg"],
            "imp_forma": run["importancia_agrupada"][tgt]["FORMA (7 params)"],
            "imp_reynolds": run["importancia_agrupada"][tgt]["reynolds"],
        }
        for f in run["features"]:
            row[f"imp_{f}"] = run["importancia_9inputs"][tgt][f]
        rows.append(row)
pd.DataFrame(rows).to_csv(HIST_CSV, index=False)

print(f"\n[OK] historico -> {HIST_JSON}")
print(f"[OK] vista plana -> {HIST_CSV}  ({len(rows)} filas, {len(hist)} reentrenos)")
