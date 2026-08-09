"""
Mide el efecto GLOBAL y POR ZONA de anadir 2 features fisicas:
   alpha_over_sqrtre = alpha_deg / sqrt(reynolds)     (termino viscoso, bajo Re)
   te_rel            = trailing_edge_thickness_mm / chord_length_mm  (TE relativo)
Compara 9 features (base) vs 11 (base + 2) en CL/CD/LD, split por perfil, CV
GroupKFold=5. CL=Lineal, CD/LD=XGBoost. NO cambia produccion; solo mide.
"""
import os
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.model_selection import GroupKFold, cross_val_predict, cross_val_score
from sklearn.linear_model import LinearRegression
from xgboost import XGBRegressor

BASE = os.path.dirname(os.path.abspath(__file__))
SHAPE = ["chord_length_mm", "leading_edge_angle_deg", "leading_edge_thickness_level",
         "trailing_edge_angle_deg", "trailing_edge_thickness_mm",
         "te_upr_angle_deg", "te_lwr_angle_deg"]
BASE_FEAT = SHAPE + ["alpha_deg", "reynolds"]
NEW_FEAT = BASE_FEAT + ["alpha_over_sqrtre", "te_rel"]
WINNER = {"CL": "Lineal", "CD": "XGBoost", "LD": "XGBoost"}
XGB = dict(n_estimators=400, learning_rate=0.05, max_depth=5, subsample=0.8,
           colsample_bytree=0.8, random_state=42, n_jobs=-1)
def mk(t):
    return LinearRegression() if WINNER[t] == "Lineal" else XGBRegressor(**XGB)

df = pd.read_csv(os.path.join(BASE, "airfoil_dataset.csv"))
ok = df[(df.status == "ok") & (df.chord_length_mm >= 150)].copy().reset_index(drop=True)
ok["alpha_over_sqrtre"] = ok["alpha_deg"] / np.sqrt(ok["reynolds"])
ok["te_rel"] = ok["trailing_edge_thickness_mm"] / ok["chord_length_mm"]
g = ok["run_id"].values
gkf = GroupKFold(n_splits=5)

def spearman_cond(yr, yp):
    t = ok[["alpha_deg", "velocidad_kmh"]].copy(); t["r"] = yr; t["p"] = yp
    rr = [spearmanr(x["r"], x["p"]).correlation for _, x in t.groupby(["alpha_deg", "velocidad_kmh"]) if len(x) >= 5]
    rr = [r for r in rr if np.isfinite(r)]
    return float(np.mean(rr))

ZONAS = [("150-200", 150, 200), ("200-400", 200, 400), ("400-500", 400, 500)]

def evalua(tgt, cols):
    X = ok[cols].values; y = ok[tgt].values
    pred = cross_val_predict(mk(tgt), X, y, groups=g, cv=gkf, n_jobs=-1)
    mae = float(np.mean(np.abs(y - pred)))
    r2 = float(cross_val_score(mk(tgt), X, y, groups=g, cv=gkf, scoring="r2").mean())
    sp = spearman_cond(y, pred)
    zonas = {}
    for name, lo, hi in ZONAS:
        m = ((ok.chord_length_mm >= lo) & (ok.chord_length_mm < hi)).values
        zonas[name] = np.mean(np.abs(y[m] - pred[m])) / y[m].std() * 100
    return mae, r2, sp, zonas

print("=" * 82)
print("GLOBAL: 9 features (base) vs 11 features (+alpha/sqrt(re) +te_rel)")
print("=" * 82)
print(f"{'tgt':4s}{'':8s}{'MAE_base':>11s}{'MAE_new':>11s}{'R2_base':>9s}{'R2_new':>9s}{'Sp_base':>9s}{'Sp_new':>9s}")
res = {}
for tgt in ("CL", "CD", "LD"):
    mb, rb, sb, zb = evalua(tgt, BASE_FEAT)
    mn, rn, sn, zn = evalua(tgt, NEW_FEAT)
    res[tgt] = (zb, zn)
    print(f"{tgt:4s}{WINNER[tgt]:8s}{mb:11.5f}{mn:11.5f}{rb:9.3f}{rn:9.3f}{sb:9.3f}{sn:9.3f}")

print("\n" + "=" * 82)
print("POR ZONA (MAE/std %), base vs new  -- confirma que NINGUNA zona empeora")
print("=" * 82)
for tgt in ("CD", "LD"):
    zb, zn = res[tgt]
    print(f"\n[{tgt}]  {'zona':10s}{'base':>8s}{'new':>8s}{'delta':>8s}")
    for name, _, _ in ZONAS:
        print(f"       {name:10s}{zb[name]:7.0f}%{zn[name]:7.0f}%{zn[name]-zb[name]:+7.0f}%")
