"""
Reentrena SOLO con los perfiles source=sobol (los 400 actuales), protocolo de
siempre: split por perfil, CV GroupKFold=5. CL lineal (principal), CD/LD RF.
Guarda en ml_history como sobol_only_n400 y saca la comparacion ENCADENADA
n142 -> n300 -> n400 (curva de aprendizaje). Solo lectura, no toca el pipeline.
"""
import os
import json
import datetime
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
LABEL = "sobol_only_n400"


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

# ---------- guardar ----------
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

# ---------- comparacion ENCADENADA n142 -> n300 -> n400 ----------
def find(label):
    return next((h for h in hist if h.get("label") == label), None)
pts = [("n142", find("sobol_only_n142")), ("n300", find("sobol_only_n300")), ("n400", res)]
pts = [(k, v) for k, v in pts if v is not None]

def metric_of(run, tgt, key):
    w = WINNER[tgt]
    return run["metrics"][tgt]["models"][w][key]

def grouped_of(run, tgt, grp):
    g = run["grouped"] if "grouped" in run else run["importancia_agrupada"]
    return g[tgt][grp]

def imp_of(run, tgt, f):
    im = run["imp9"] if "imp9" in run else run["importancia_9inputs"]
    return im[tgt][f]

print("\n" + "#" * 72)
print("# CURVA DE APRENDIZAJE  n142 -> n300 -> n400  (solo Sobol)")
print("#" * 72)
print("\n--- MAE / R2 (metodo principal) ---")
print(f"{'obj':4s}{'metrica':6s}" + "".join(f"{k:>10s}" for k, _ in pts))
for tgt in ("CL", "CD", "LD"):
    print(f"{tgt:4s}{'MAE':6s}" + "".join(f"{metric_of(v,tgt,'mae'):10.5f}" for _, v in pts))
    print(f"{'':4s}{'R2':6s}" + "".join(f"{metric_of(v,tgt,'r2'):10.3f}" for _, v in pts))

print("\n--- IMPORTANCIA FORMA (7 params agrupados) (%) ---")
print(f"{'obj':6s}" + "".join(f"{k:>8s}" for k, _ in pts))
for tgt in ("CL", "CD", "LD"):
    print(f"{tgt:6s}" + "".join(f"{grouped_of(v,tgt,'FORMA (7 params)')*100:7.1f}%" for _, v in pts))

print("\n--- FORMA POR PARAMETRO (%) ---")
for tgt in ("CL", "CD", "LD"):
    print(f"\n[{tgt}]  {'param':32s}" + "".join(f"{k:>8s}" for k, _ in pts))
    for f in SHAPE:
        print(f"      {f:32s}" + "".join(f"{imp_of(v,tgt,f)*100:7.1f}%" for _, v in pts))

print(f"\n[OK] guardado {LABEL} ({len(hist)} entradas en historico)")
