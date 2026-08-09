"""
Comparacion limpia SOBOL vs RANDOM a numero de perfiles IGUALADO.
Entrena dos conjuntos de modelos por separado (solo random / solo sobol),
mismo N de perfiles (142), split POR PERFIL, CV GroupKFold=5.
Objetivos: CL (lineal, principal), CD y LD (RandomForest, principal).
Compara MAE/R2 y, sobre todo, la IMPORTANCIA de la forma (7 params agrupados
y por parametro). Guarda ambos resultados en ml_history.json / ml_history.csv.
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
HIST_JSON = os.path.join(BASE, "ml_history.json")
HIST_CSV = os.path.join(BASE, "ml_history.csv")

SHAPE = ["chord_length_mm", "leading_edge_angle_deg", "leading_edge_thickness_level",
         "trailing_edge_angle_deg", "trailing_edge_thickness_mm",
         "te_upr_angle_deg", "te_lwr_angle_deg"]
FEATURES = SHAPE + ["alpha_deg", "reynolds"]
WINNER = {"CL": "Lineal", "CD": "RandomForest", "LD": "RandomForest"}
N_MATCH = 142           # igualamos ambos grupos a 142 perfiles
SUBSAMPLE_SEED = 0      # para elegir 142 de los 150 sobol de forma reproducible

def mk_model(name):
    if name == "Lineal":
        return LinearRegression()
    return RandomForestRegressor(n_estimators=400, random_state=42, n_jobs=-1)

df = pd.read_csv(os.path.join(BASE, "airfoil_dataset.csv"))
ok = df[df["status"] == "ok"].copy()


def build_group(source):
    """Filas ok de un source, recortadas a N_MATCH perfiles (reproducible)."""
    sub = ok[ok["source"] == source].copy()
    perfiles = np.array(sorted(sub["run_id"].unique()))
    if len(perfiles) > N_MATCH:
        rng = np.random.RandomState(SUBSAMPLE_SEED)
        keep = set(rng.choice(perfiles, size=N_MATCH, replace=False))
        sub = sub[sub["run_id"].isin(keep)].copy()
    return sub


def train_group(sub, label):
    X = sub[FEATURES].values
    groups = sub["run_id"].values
    gkf = GroupKFold(n_splits=5)
    res = {"label": label, "n_perfiles": int(sub["run_id"].nunique()),
           "n_filas_ok": int(len(sub)), "metrics": {}, "imp9": {}, "grouped": {}}
    print(f"\n{'='*78}\n[{label}]  perfiles={res['n_perfiles']}  filas_ok={res['n_filas_ok']}\n{'='*78}")
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
        w = WINNER[tgt]
        m = res["metrics"][tgt]["models"][w]
        print(f"   {tgt} ({w}): MAE={m['mae']:.5f}  R2={m['r2']:.3f}")
        # importancia RF sobre todo el grupo
        rf = RandomForestRegressor(n_estimators=400, random_state=42, n_jobs=-1)
        rf.fit(X, y)
        d = dict(zip(FEATURES, rf.feature_importances_))
        res["imp9"][tgt] = {f: float(d[f]) for f in FEATURES}
        res["grouped"][tgt] = {
            "alpha_deg": float(d["alpha_deg"]),
            "FORMA (7 params)": float(sum(d[f] for f in SHAPE)),
            "reynolds": float(d["reynolds"])}
    return res


g_rand = train_group(build_group("random"), f"random_only_n{N_MATCH}")
g_sob = train_group(build_group("sobol"), f"sobol_only_n{N_MATCH}")

# ---------- tablas comparativas ----------
print("\n" + "#" * 78)
print("# COMPARATIVA MAE / R2  (metodo principal)  random vs sobol")
print("#" * 78)
print(f"{'obj':4s}{'metodo':13s}{'MAE_rand':>11s}{'MAE_sob':>11s}{'R2_rand':>9s}{'R2_sob':>9s}")
for tgt in ("CL", "CD", "LD"):
    w = WINNER[tgt]
    mr = g_rand["metrics"][tgt]["models"][w]
    ms = g_sob["metrics"][tgt]["models"][w]
    print(f"{tgt:4s}{w:13s}{mr['mae']:11.5f}{ms['mae']:11.5f}{mr['r2']:9.3f}{ms['r2']:9.3f}")

print("\n" + "#" * 78)
print("# IMPORTANCIA AGRUPADA (%)  alpha / FORMA / reynolds   random vs sobol")
print("#" * 78)
print(f"{'obj':5s}{'grupo':20s}{'random':>9s}{'sobol':>9s}{'delta':>9s}")
for tgt in ("CL", "CD", "LD"):
    for grp in ("alpha_deg", "FORMA (7 params)", "reynolds"):
        r = g_rand["grouped"][tgt][grp] * 100
        s = g_sob["grouped"][tgt][grp] * 100
        print(f"{tgt:5s}{grp:20s}{r:8.1f}%{s:8.1f}%{s-r:+8.1f}%")

print("\n" + "#" * 78)
print("# IMPORTANCIA DE FORMA POR PARAMETRO (%)   random vs sobol")
print("#" * 78)
for tgt in ("CL", "CD", "LD"):
    print(f"\n-- {tgt} --   {'param':32s}{'random':>9s}{'sobol':>9s}")
    for f in SHAPE:
        r = g_rand["imp9"][tgt][f] * 100
        s = g_sob["imp9"][tgt][f] * 100
        print(f"{'':10s}{f:32s}{r:8.1f}%{s:8.1f}%")

# ---------- guardar en historico ----------
def to_entry(res):
    return {
        "fecha": datetime.datetime.now().isoformat(timespec="seconds"),
        "label": res["label"],
        "n_perfiles": res["n_perfiles"], "n_filas_ok": res["n_filas_ok"],
        "features": FEATURES, "winner": WINNER,
        "metrics": res["metrics"],
        "importancia_9inputs": res["imp9"],
        "importancia_agrupada": res["grouped"],
    }

hist = []
if os.path.exists(HIST_JSON):
    with open(HIST_JSON, "r", encoding="utf-8") as fh:
        try:
            hist = json.load(fh)
        except json.JSONDecodeError:
            hist = []
hist.append(to_entry(g_rand))
hist.append(to_entry(g_sob))
with open(HIST_JSON, "w", encoding="utf-8") as fh:
    json.dump(hist, fh, indent=2, ensure_ascii=False)

# vista plana (regenerada desde el JSON completo)
rows = []
for run in hist:
    for tgt in ("CL", "CD", "LD"):
        w = run["winner"][tgt]
        m = run["metrics"][tgt]["models"][w]
        row = {"fecha": run["fecha"], "label": run.get("label", ""),
               "n_perfiles": run["n_perfiles"], "n_filas_ok": run["n_filas_ok"],
               "objetivo": tgt, "metodo": w,
               "mae": m["mae"], "mae_std": m["mae_std"],
               "r2": m["r2"], "r2_std": m["r2_std"],
               "imp_alpha": run["importancia_agrupada"][tgt]["alpha_deg"],
               "imp_forma": run["importancia_agrupada"][tgt]["FORMA (7 params)"],
               "imp_reynolds": run["importancia_agrupada"][tgt]["reynolds"]}
        for f in run["features"]:
            row[f"imp_{f}"] = run["importancia_9inputs"][tgt][f]
        rows.append(row)
pd.DataFrame(rows).to_csv(HIST_CSV, index=False)
print(f"\n[OK] historico -> {HIST_JSON}  ({len(hist)} entradas)")
print(f"[OK] vista plana -> {HIST_CSV}  ({len(rows)} filas)")
