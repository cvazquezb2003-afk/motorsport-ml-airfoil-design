"""
Experimento acotado: CL lineal (produccion) vs CL XGBoost.
Mismas 11 features feature_utils, filtro >=150, GroupKFold=5 por run_id.
Guarda modelo_CL_xgb.joblib. NO toca produccion. Solo compara.
"""
import os, numpy as np, pandas as pd, joblib
from sklearn.model_selection import GroupKFold, cross_val_predict, cross_val_score
from sklearn.linear_model import LinearRegression
from xgboost import XGBRegressor
from feature_utils import SHAPE, FEATURES, add_derived

BASE = os.path.dirname(os.path.abspath(__file__))
RHO, MU = 1.225, 1.81e-5
def reynolds(c, v): return RHO * (v / 3.6) * (c / 1000.0) / MU

# arranque = hiperparametros de CD
XGB = dict(n_estimators=400, learning_rate=0.05, max_depth=5, subsample=0.8,
           colsample_bytree=0.8, random_state=42, n_jobs=-1)

df = pd.read_csv(os.path.join(BASE, "airfoil_dataset.csv"))
ok = add_derived(df[df.status == "ok"].copy())
f = ok[ok.chord_length_mm >= 150].reset_index(drop=True)
f["zona"] = pd.cut(f.chord_length_mm, [150, 200, 400, 500],
                   labels=["150-200", "200-400", "400-500"], include_lowest=True)
X, y, g = f[FEATURES].values, f["CL"].values, f.run_id.values
gkf = GroupKFold(5)

def blk(t): print("\n" + "=" * 74 + "\n" + t + "\n" + "=" * 74)

# ---------- CV A/B ----------
blk("1) CV A/B — CL Lineal (produccion) vs CL XGBoost")
mods = {"Lineal": LinearRegression(), "XGBoost": XGBRegressor(**XGB)}
pred = {}
for nm, m in mods.items():
    pred[nm] = cross_val_predict(m, X, y, groups=g, cv=gkf, n_jobs=-1)
    mae = np.mean(np.abs(y - pred[nm]))
    r2 = cross_val_score(m, X, y, groups=g, cv=gkf, scoring="r2").mean()
    bias = np.mean(pred[nm] - y)
    print(f"  {nm:8s}: MAE={mae:.5f}  R2={r2:.4f}  bias(pred-real)={bias:+.5f}")
f["ae_lin"] = np.abs(y - pred["Lineal"]); f["ae_xgb"] = np.abs(y - pred["XGBoost"])

# ---------- por ZONA ----------
blk("2) MAE de CL por ZONA de cuerda (menor es mejor)")
print(f"  {'zona':10s}{'Lineal':>10s}{'XGBoost':>10s}{'mejora%':>9s}{'n':>7s}")
for z, s in f.groupby("zona", observed=True):
    l, x = s.ae_lin.mean(), s.ae_xgb.mean()
    print(f"  {z:10s}{l:10.5f}{x:10.5f}{(l-x)/l*100:8.1f}%{len(s):7d}")

# ---------- por ANGULO ----------
blk("3) MAE de CL por ANGULO (menor es mejor)")
print(f"  {'alpha':>6s}{'Lineal':>10s}{'XGBoost':>10s}{'mejora%':>9s}{'n':>7s}")
for a, s in f.groupby("alpha_deg"):
    l, x = s.ae_lin.mean(), s.ae_xgb.mean()
    print(f"  {int(a):>6d}{l:10.5f}{x:10.5f}{(l-x)/l*100:8.1f}%{len(s):7d}")

# ---------- barrido perfil 0014 @ alpha -6 ----------
blk("4) BARRIDO perfil 0014 @ |alpha|=6 — error por velocidad vs XFOIL")
lin_full = LinearRegression().fit(X, y)
xgb_full = XGBRegressor(**XGB).fit(X, y)
g14 = df[(df.run_id == "0014_20260711_193032") & (df.status == "ok") & (df.alpha_deg == -6)]
sh = {k: float(g14[k].iloc[0]) for k in SHAPE}
print(f"  {'v':>4}{'CL_meas':>9}{'lin':>9}{'err_lin':>8}{'xgb':>9}{'err_xgb':>8}")
for _, r in g14.sort_values("velocidad_kmh").iterrows():
    v = r.velocidad_kmh
    row = {k: sh[k] for k in SHAPE}; row["alpha_deg"] = -6
    row["reynolds"] = reynolds(sh["chord_length_mm"], v)
    XX = add_derived(pd.DataFrame([row]))[FEATURES].values
    pl, px = lin_full.predict(XX)[0], xgb_full.predict(XX)[0]
    e = lambda a, b: abs(b - a) / abs(a) * 100
    print(f"  {int(v):>4}{r.CL:>9.3f}{pl:>9.3f}{e(r.CL, pl):>7.1f}%{px:>9.3f}{e(r.CL, px):>7.1f}%")

# guardar modelo nuevo (aparte)
joblib.dump({"model": xgb_full, "meta": {"target": "CL", "features": FEATURES,
            "params": XGB, "dataset": "airfoil_dataset.csv (TE-real)"}},
            os.path.join(BASE, "modelo_CL_xgb.joblib"))
print("\n[OK] modelo_CL_xgb.joblib guardado (NO promocionado). Produccion intacta.")
