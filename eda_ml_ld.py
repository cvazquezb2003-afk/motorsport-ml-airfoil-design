"""
Modelo 3D de la EFICIENCIA: predecir L/D a partir de forma + angulo + Reynolds.
Solo splits POR PERFIL (sin fuga de datos). Solo lectura, no toca el pipeline.
"""
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from sklearn.model_selection import GroupShuffleSplit, GroupKFold, cross_val_score
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

BASE = os.path.dirname(os.path.abspath(__file__))
OUTDIR = os.path.join(BASE, "eda_outputs")

SHAPE = ["chord_length_mm", "leading_edge_angle_deg", "leading_edge_thickness_level",
         "trailing_edge_angle_deg", "trailing_edge_thickness_mm",
         "te_upr_angle_deg", "te_lwr_angle_deg"]
FEATURES = SHAPE + ["alpha_deg", "reynolds"]

df = pd.read_csv(os.path.join(BASE, "airfoil_dataset.csv"))
ok = df[df["status"] == "ok"].copy()
print(f"[DATOS] filas ok: {len(ok)} | perfiles: {ok['run_id'].nunique()} (sin exclusiones)")

X = ok[FEATURES].values
y = ok["LD"].values
groups = ok["run_id"].values
print(f"[DATOS] X={X.shape} | y=LD (media {y.mean():.2f}, std {y.std():.2f}, "
      f"rango [{y.min():.2f}, {y.max():.2f}])")

# ---------- split POR PERFIL (honesto) ----------
gss = GroupShuffleSplit(n_splits=1, test_size=0.20, random_state=42)
itr, ite = next(gss.split(X, y, groups))
X_tr, X_te, y_tr, y_te = X[itr], X[ite], y[itr], y[ite]
print(f"\n[SPLIT por perfil] train: {len(set(groups[itr]))} perfiles ({len(itr)} filas) | "
      f"test: {len(set(groups[ite]))} perfiles ({len(ite)} filas)")

models = {
    "Lineal": LinearRegression(),
    "RandomForest": RandomForestRegressor(n_estimators=400, random_state=42, n_jobs=-1),
}

print("\n" + "=" * 64)
print("EVALUACION (test = perfiles NUEVOS)")
print("=" * 64)
results = {}
for name, model in models.items():
    model.fit(X_tr, y_tr)
    p = model.predict(X_te)
    mae = mean_absolute_error(y_te, p)
    rmse = np.sqrt(mean_squared_error(y_te, p))
    r2 = r2_score(y_te, p)
    results[name] = (mae, rmse, r2, model, p)
    print(f"   {name:13s} MAE={mae:.2f}  RMSE={rmse:.2f}  R2={r2:.3f}")

print("\n[CV por perfil, GroupKFold=5]  (MAE medio +/- std)")
gkf = GroupKFold(n_splits=5)
cv_res = {}
for name, model in [("Lineal", LinearRegression()),
                    ("RandomForest", RandomForestRegressor(
                        n_estimators=400, random_state=42, n_jobs=-1))]:
    sc = -cross_val_score(model, X, y, groups=groups, cv=gkf,
                          scoring="neg_mean_absolute_error")
    cv_res[name] = (sc.mean(), sc.std())
    print(f"   {name:13s} MAE_CV = {sc.mean():.2f} +/- {sc.std():.2f}")

# ---------- importancia de inputs (RF) ----------
rf = results["RandomForest"][3]
print("\n" + "=" * 64)
print("IMPORTANCIA DE LOS 9 INPUTS PARA EL L/D (Random Forest)")
print("=" * 64)
for f, w in sorted(zip(FEATURES, rf.feature_importances_), key=lambda t: -t[1]):
    print(f"   {f:30s} {w*100:5.1f}%  {'#'*int(round(w*50))}")
d = dict(zip(FEATURES, rf.feature_importances_))
print("\n   --- agrupado ---")
print(f"   {'alpha_deg':20s} {d['alpha_deg']*100:5.1f}%")
print(f"   {'forma (7 params)':20s} {sum(d[f] for f in SHAPE)*100:5.1f}%")
print(f"   {'reynolds':20s} {d['reynolds']*100:5.1f}%")

# ---------- grafica predicho vs real de ambos, lado a lado ----------
fig, axes = plt.subplots(1, 2, figsize=(13, 6))
for ax, name in zip(axes, ("Lineal", "RandomForest")):
    mae, rmse, r2, _, p = results[name]
    ax.scatter(y_te, p, s=14, alpha=0.5, color="#2b6cb0", edgecolors="none")
    lo, hi = min(y_te.min(), p.min()), max(y_te.max(), p.max())
    ax.plot([lo, hi], [lo, hi], "r--", lw=1.5)
    ax.set_xlabel("L/D real (XFOIL)"); ax.set_ylabel(f"L/D predicho ({name})")
    ax.set_title(f"{name}\nMAE={mae:.2f}  R2={r2:.2f}")
    ax.grid(alpha=0.3)
fig.suptitle(f"Predicho vs Real - L/D (perfiles NUEVOS, n={len(y_te)})", fontsize=13)
fig.tight_layout(rect=[0, 0, 1, 0.94])
out = os.path.join(OUTDIR, "pred_vs_real_LD_3D.png")
fig.savefig(out, dpi=120); plt.close(fig)
print(f"\n[OK] grafica: {out}")

# contexto para comparacion relativa con el modelo de CL
print(f"\n[CONTEXTO] std LD = {y.std():.2f} -> MAE relativo RF = "
      f"{results['RandomForest'][0]/y.std()*100:.0f}% de la std "
      f"(CL era ~14%)")
