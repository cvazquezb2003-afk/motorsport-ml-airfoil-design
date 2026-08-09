"""
Primer modelo completo 3D: predecir CL a partir de forma + angulo + Reynolds.
Compara split POR FILAS (con fuga de datos) vs POR PERFIL (honesto).
Solo lectura del dataset, no toca el pipeline.
"""
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from sklearn.model_selection import (train_test_split, cross_val_score,
                                     GroupShuffleSplit, GroupKFold)
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
# El outlier antiguo 0021 (CD=0.00802) NO esta en este dataset escalonado; las
# filas de CD bajo aqui son puntos legitimos de baja resistencia -> NO se excluyen.
print(f"[DATOS] filas ok: {len(ok)} | perfiles: {ok['run_id'].nunique()}  (sin exclusiones)")

X = ok[FEATURES].values
y = ok["CL"].values
groups = ok["run_id"].values
print(f"[DATOS] X={X.shape} (9 inputs) | y=CL (media {y.mean():.3f}, std {y.std():.3f}, "
      f"rango [{y.min():.3f},{y.max():.3f}])")


def fit_eval(X_tr, X_te, y_tr, y_te):
    res = {}
    for name, model in [("Lineal", LinearRegression()),
                        ("RandomForest", RandomForestRegressor(
                            n_estimators=400, random_state=42, n_jobs=-1))]:
        model.fit(X_tr, y_tr)
        p = model.predict(X_te)
        res[name] = (mean_absolute_error(y_te, p),
                     np.sqrt(mean_squared_error(y_te, p)),
                     r2_score(y_te, p), model, p)
    return res


# ---------- A) split POR FILAS (con fuga: mismo perfil en train y test) ----------
Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.20, random_state=42)
resA = fit_eval(Xtr, Xte, ytr, yte)
print("\n" + "=" * 64)
print("A) SPLIT POR FILAS (80/20)  --  OJO: fuga de datos (mismo perfil en ambos)")
print("=" * 64)
for name in ("Lineal", "RandomForest"):
    mae, rmse, r2, _, _ = resA[name]
    print(f"   {name:13s} MAE={mae:.4f}  RMSE={rmse:.4f}  R2={r2:.3f}")

# ---------- B) split POR PERFIL (honesto: perfiles de test nunca vistos) ----------
gss = GroupShuffleSplit(n_splits=1, test_size=0.20, random_state=42)
itr, ite = next(gss.split(X, y, groups))
resB = fit_eval(X[itr], X[ite], y[itr], y[ite])
print("\n" + "=" * 64)
print("B) SPLIT POR PERFIL (run_id)  --  HONESTO: predecir perfiles NUEVOS")
print(f"   perfiles train={len(set(groups[itr]))}  perfiles test={len(set(groups[ite]))}")
print("=" * 64)
for name in ("Lineal", "RandomForest"):
    mae, rmse, r2, _, _ = resB[name]
    print(f"   {name:13s} MAE={mae:.4f}  RMSE={rmse:.4f}  R2={r2:.3f}")

# ---------- validacion cruzada POR PERFIL (GroupKFold, la mas fiable) ----------
print("\n[CV por perfil, GroupKFold=5]  (MAE medio +/- std)")
gkf = GroupKFold(n_splits=5)
for name, model in [("Lineal", LinearRegression()),
                    ("RandomForest", RandomForestRegressor(
                        n_estimators=400, random_state=42, n_jobs=-1))]:
    sc = -cross_val_score(model, X, y, groups=groups, cv=gkf,
                          scoring="neg_mean_absolute_error")
    print(f"   {name:13s} MAE_CV = {sc.mean():.4f} +/- {sc.std():.4f}")

# ---------- importancia de los 9 inputs (RF, entrenado por perfil) ----------
rf = resB["RandomForest"][3]
print("\n" + "=" * 64)
print("IMPORTANCIA DE LOS 9 INPUTS (Random Forest)")
print("=" * 64)
for f, w in sorted(zip(FEATURES, rf.feature_importances_), key=lambda t: -t[1]):
    print(f"   {f:30s} {w*100:5.1f}%  {'#'*int(round(w*50))}")
d = dict(zip(FEATURES, rf.feature_importances_))
print("\n   --- agrupado ---")
print(f"   {'alpha_deg':20s} {d['alpha_deg']*100:5.1f}%")
print(f"   {'forma (7 params)':20s} {sum(d[f] for f in SHAPE)*100:5.1f}%")
print(f"   {'reynolds':20s} {d['reynolds']*100:5.1f}%")

# ---------- grafica predicho vs real (RF, split honesto por perfil) ----------
p = resB["RandomForest"][4]; yte_b = y[ite]
fig, ax = plt.subplots(figsize=(6.5, 6.5))
ax.scatter(yte_b, p, s=14, alpha=0.5, color="#2b6cb0", edgecolors="none")
lo, hi = min(yte_b.min(), p.min()), max(yte_b.max(), p.max())
ax.plot([lo, hi], [lo, hi], "r--", lw=1.5, label="prediccion perfecta")
ax.set_xlabel("CL real (XFOIL)"); ax.set_ylabel("CL predicho (RandomForest)")
ax.set_title(f"Predicho vs Real - CL (perfiles NUEVOS, n={len(yte_b)})\n"
             f"RF split por perfil: MAE={resB['RandomForest'][0]:.4f}  R2={resB['RandomForest'][2]:.2f}")
ax.legend(); ax.grid(alpha=0.3); fig.tight_layout()
out = os.path.join(OUTDIR, "pred_vs_real_CL_3D_grupo.png")
fig.savefig(out, dpi=120); plt.close(fig)
print(f"\n[OK] grafica: {out}")
