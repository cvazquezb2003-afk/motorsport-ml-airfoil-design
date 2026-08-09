"""
Modelo 3D del CD (resistencia): X = 7 forma + alpha + reynolds. Split por perfil.
Ademas recopila las importancias agrupadas (alpha/forma/reynolds) de los TRES
modelos (CL, CD, LD) en una tabla. Solo lectura, no toca el pipeline.
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
groups = ok["run_id"].values
X = ok[FEATURES].values
print(f"[DATOS] filas ok: {len(ok)} | perfiles: {ok['run_id'].nunique()}")


def run_target(colname, label):
    y = ok[colname].values
    gss = GroupShuffleSplit(n_splits=1, test_size=0.20, random_state=42)
    itr, ite = next(gss.split(X, y, groups))
    out = {"std": y.std(), "range": (y.min(), y.max()), "mean": y.mean()}
    for name, model in [("Lineal", LinearRegression()),
                        ("RandomForest", RandomForestRegressor(
                            n_estimators=400, random_state=42, n_jobs=-1))]:
        model.fit(X[itr], y[itr])
        p = model.predict(X[ite])
        mae = mean_absolute_error(y[ite], p)
        r2 = r2_score(y[ite], p)
        gkf = GroupKFold(n_splits=5)
        cv = -cross_val_score(model, X, y, groups=groups, cv=gkf,
                              scoring="neg_mean_absolute_error")
        out[name] = {"mae": mae, "r2": r2, "cv": (cv.mean(), cv.std()),
                     "model": model if name == "RandomForest" else None,
                     "pred": p, "ytest": y[ite]}
    return out


# ---------- CD (foco de esta tarea) ----------
cd = run_target("CD", "CD")
print("\n" + "=" * 64)
print("MODELO DE CD (resistencia)  --  test = perfiles NUEVOS")
print(f"   y=CD: media {cd['mean']:.5f}  std {cd['std']:.5f}  "
      f"rango [{cd['range'][0]:.5f}, {cd['range'][1]:.5f}]")
print("=" * 64)
for name in ("Lineal", "RandomForest"):
    r = cd[name]
    print(f"   {name:13s} MAE={r['mae']:.5f}  R2={r['r2']:.3f}  "
          f"CV_MAE={r['cv'][0]:.5f} +/- {r['cv'][1]:.5f}")

# importancia CD
rf_cd = cd["RandomForest"]["model"]
print("\nIMPORTANCIA DE LOS 9 INPUTS PARA EL CD (Random Forest):")
for f, w in sorted(zip(FEATURES, rf_cd.feature_importances_), key=lambda t: -t[1]):
    print(f"   {f:30s} {w*100:5.1f}%  {'#'*int(round(w*50))}")

# ---------- tabla comparada de importancias agrupadas: CL / CD / LD ----------
def grouped_importance(colname):
    y = ok[colname].values
    gss = GroupShuffleSplit(n_splits=1, test_size=0.20, random_state=42)
    itr, ite = next(gss.split(X, y, groups))
    rf = RandomForestRegressor(n_estimators=400, random_state=42, n_jobs=-1).fit(X[itr], y[itr])
    d = dict(zip(FEATURES, rf.feature_importances_))
    return (d["alpha_deg"], sum(d[f] for f in SHAPE), d["reynolds"])


print("\n" + "=" * 64)
print("IMPORTANCIAS AGRUPADAS (Random Forest) EN LOS TRES MODELOS")
print("=" * 64)
print(f"   {'target':10s} {'alpha':>8s} {'forma':>8s} {'reynolds':>9s}")
for col in ("CL", "CD", "LD"):
    a, fo, re = grouped_importance(col)
    print(f"   {col:10s} {a*100:7.1f}% {fo*100:7.1f}% {re*100:8.1f}%")

# ---------- grafica CD predicho vs real ----------
fig, axes = plt.subplots(1, 2, figsize=(13, 6))
for ax, name in zip(axes, ("Lineal", "RandomForest")):
    r = cd[name]
    ax.scatter(r["ytest"], r["pred"], s=14, alpha=0.5, color="#2b6cb0", edgecolors="none")
    lo, hi = min(r["ytest"].min(), r["pred"].min()), max(r["ytest"].max(), r["pred"].max())
    ax.plot([lo, hi], [lo, hi], "r--", lw=1.5)
    ax.set_xlabel("CD real (XFOIL)"); ax.set_ylabel(f"CD predicho ({name})")
    ax.set_title(f"{name}\nMAE={r['mae']:.5f}  R2={r['r2']:.2f}"); ax.grid(alpha=0.3)
fig.suptitle(f"Predicho vs Real - CD (perfiles NUEVOS, n={len(cd['RandomForest']['ytest'])})",
             fontsize=13)
fig.tight_layout(rect=[0, 0, 1, 0.94])
out = os.path.join(OUTDIR, "pred_vs_real_CD_3D.png")
fig.savefig(out, dpi=120); plt.close(fig)
print(f"\n[OK] grafica: {out}")

# error relativo a la std, comparado con CL y LD
print("\n[ERROR RELATIVO A LA STD (RF, split por perfil)]")
print(f"   CD: MAE {cd['RandomForest']['mae']:.5f} / std {cd['std']:.5f} = "
      f"{cd['RandomForest']['mae']/cd['std']*100:.0f}%   (CL ~14%, LD ~27%)")
