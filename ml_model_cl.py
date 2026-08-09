"""
Primer modelo ML: predecir CL a partir de los 7 parametros de forma.
Solo lectura del dataset, no toca el pipeline.
"""
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

BASE = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(BASE, "airfoil_dataset.csv")
OUTDIR = os.path.join(BASE, "eda_outputs")
os.makedirs(OUTDIR, exist_ok=True)

FEATURES = [
    "chord_length_mm", "leading_edge_angle_deg", "leading_edge_thickness_level",
    "trailing_edge_angle_deg", "trailing_edge_thickness_mm",
    "te_upr_angle_deg", "te_lwr_angle_deg",
]
TARGET = "CL"

# ---------- PASO 1: datos ----------
df = pd.read_csv(CSV)
ok = df[df["status"] == "ok"].copy()
ok = ok[ok["CD"] >= 0.012].copy()   # excluye el outlier run 0021 (CD=0.00802)
print(f"[PASO 1] perfiles usados: {len(ok)}  (136 esperados)")

X = ok[FEATURES].values
y = ok[TARGET].values
print(f"[PASO 1] X shape={X.shape} (filas, 7 inputs) | y = CL")
print(f"[PASO 1] CL: media={y.mean():.3f}  std={y.std():.3f}  "
      f"min={y.min():.3f}  max={y.max():.3f}")

# ---------- PASO 2: train/test split ----------
X_tr, X_te, y_tr, y_te = train_test_split(
    X, y, test_size=0.20, random_state=42
)
print(f"\n[PASO 2] entrenamiento: {len(X_tr)} | prueba: {len(X_te)} (80/20)")

# ---------- PASO 3: entrenar dos modelos ----------
lin = LinearRegression().fit(X_tr, y_tr)
rf = RandomForestRegressor(n_estimators=300, random_state=42).fit(X_tr, y_tr)


def evaluate(name, model):
    pred = model.predict(X_te)
    mae = mean_absolute_error(y_te, pred)
    rmse = np.sqrt(mean_squared_error(y_te, pred))
    r2 = r2_score(y_te, pred)
    # validacion cruzada 5-fold sobre TODO el set (MAE), mas honesto con pocos datos
    cv = -cross_val_score(model, X, y, cv=5,
                          scoring="neg_mean_absolute_error")
    print(f"\n[{name}]")
    print(f"   MAE  (test) = {mae:.4f} CL  (error medio absoluto)")
    print(f"   RMSE (test) = {rmse:.4f} CL  (penaliza errores grandes)")
    print(f"   R2   (test) = {r2:.3f}      (1=perfecto, 0=como predecir la media)")
    print(f"   MAE  (5-fold CV) = {cv.mean():.4f} +/- {cv.std():.4f} CL")
    return pred, mae, rmse, r2


print("\n" + "=" * 60)
print("PASO 4 - EVALUACION SOBRE EL CONJUNTO DE PRUEBA")
print("=" * 60)
pred_lin, *_ = evaluate("Regresion lineal", lin)
pred_rf, mae_rf, rmse_rf, r2_rf = evaluate("Random Forest", rf)

# contexto: error relativo al rango de CL
rng = y.max() - y.min()
print(f"\n[CONTEXTO] rango de CL = {rng:.3f}. "
      f"MAE RandomForest = {mae_rf:.4f} -> {mae_rf/rng*100:.1f}% del rango.")

# ---------- importancia de variables (Random Forest) ----------
print("\n[IMPORTANCIA de variables segun Random Forest]")
imp = sorted(zip(FEATURES, rf.feature_importances_), key=lambda t: -t[1])
for f, w in imp:
    print(f"   {f:32s} {w*100:5.1f}%")

# ---------- PASO 5: grafica predicho vs real (modelo ganador: lineal) ----------
mae_lin = mean_absolute_error(y_te, pred_lin)
r2_lin = r2_score(y_te, pred_lin)
fig, ax = plt.subplots(figsize=(6.5, 6.5))
ax.scatter(y_te, pred_lin, s=40, alpha=0.7, color="#2b6cb0", edgecolors="white")
lo, hi = min(y_te.min(), pred_lin.min()), max(y_te.max(), pred_lin.max())
ax.plot([lo, hi], [lo, hi], "r--", lw=1.5, label="prediccion perfecta (y=x)")
ax.set_xlabel("CL real (XFOIL)")
ax.set_ylabel("CL predicho (Regresion lineal)")
ax.set_title(f"Predicho vs Real - CL (test n={len(y_te)})\n"
             f"Regresion lineal:  MAE={mae_lin:.4f}  R2={r2_lin:.2f}")
ax.legend()
ax.grid(True, alpha=0.3)
fig.tight_layout()
out = os.path.join(OUTDIR, "pred_vs_real_CL_lineal.png")
fig.savefig(out, dpi=120)
plt.close(fig)
print(f"\n[OK] Grafica guardada: {out}")
