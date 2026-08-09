"""
Diagnostico de la zona de cuerda 150-200 (la de menor confianza). 3 pasos:
  D1: consistencia de XFOIL en 150-200 vs 200-400 (ruido de datos, ¿irreducible?)
  D2: modelo ponderado/especializado hacia 150-200 (¿baja el error del modelo?)
  D3: feature engineering para bajo Reynolds (¿baja el error?)
Todo mide el error de LD en 150-200 (out-of-fold, split por perfil). NO cambia el
modelo de produccion. Solo lectura del dataset.
"""
import os
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from sklearn.model_selection import GroupKFold, cross_val_predict
from xgboost import XGBRegressor

BASE = os.path.dirname(os.path.abspath(__file__))
SHAPE = ["chord_length_mm", "leading_edge_angle_deg", "leading_edge_thickness_level",
         "trailing_edge_angle_deg", "trailing_edge_thickness_mm",
         "te_upr_angle_deg", "te_lwr_angle_deg"]
FEATURES = SHAPE + ["alpha_deg", "reynolds"]
XGB = dict(n_estimators=400, learning_rate=0.05, max_depth=5, subsample=0.8,
           colsample_bytree=0.8, random_state=42, n_jobs=-1)

df = pd.read_csv(os.path.join(BASE, "airfoil_dataset.csv"))
ok = df[(df.status == "ok") & (df.chord_length_mm >= 150)].copy().reset_index(drop=True)
zona_baja = (ok.chord_length_mm >= 150) & (ok.chord_length_mm < 200)
zona_buena = (ok.chord_length_mm >= 200) & (ok.chord_length_mm < 400)

# =========================================================
# D1 - CONSISTENCIA DE XFOIL: perfiles vecinos, misma condicion
# =========================================================
# Para cada fila, buscamos filas de OTRO perfil con la MISMA (alpha, velocidad) y
# forma muy parecida (vecino cercano en el espacio de forma normalizado). La
# dispersion de LD entre vecinos ~identicos = ruido de XFOIL (no del modelo).
print("=" * 74)
print("D1 - CONSISTENCIA DE XFOIL (dispersion de LD entre perfiles casi identicos)")
print("=" * 74)
lows = ok[SHAPE].min().values
highs = ok[SHAPE].max().values
rng = np.where(highs > lows, highs - lows, 1.0)

def dispersión_vecinos(mask, k=5, r_max=0.06):
    """Mediana de la desviacion tipica de LD entre k vecinos de forma ~identica,
    dentro de la MISMA (alpha, velocidad). r_max = radio max en espacio norm."""
    sub = ok[mask]
    disp = []
    for (a, v), g in sub.groupby(["alpha_deg", "velocidad_kmh"]):
        if len(g) < k + 1:
            continue
        Xn = (g[SHAPE].values - lows) / rng
        tree = cKDTree(Xn)
        d, idx = tree.query(Xn, k=k + 1)   # incluye a si mismo
        for row_i in range(len(g)):
            vecinos = [j for jj, j in enumerate(idx[row_i]) if d[row_i][jj] <= r_max and j != row_i]
            if len(vecinos) >= 2:
                lds = g["LD"].values[[row_i] + vecinos]
                disp.append(np.std(lds))
    return np.median(disp) if disp else float("nan"), len(disp)

for mask, lab in [(zona_baja, "150-200"), (zona_buena, "200-400")]:
    d, n = dispersión_vecinos(mask)
    sub = ok[mask]
    print(f"  {lab}: std(LD) mediana entre vecinos ~identicos = {d:.2f}  "
          f"(sobre {n} grupos) | std(LD) global zona = {sub['LD'].std():.2f}")
print("  -> Si la dispersion entre vecinos identicos es MUCHO mayor en 150-200,")
print("     el ruido es de XFOIL (irreducible). Si es similar, el dato es limpio.")

# =========================================================
# Utilidad: error de LD en 150-200 (out-of-fold, split por perfil)
# =========================================================
def error_zona_baja(Xcols, sample_weight=None, subset_mask=None, label=""):
    data = ok if subset_mask is None else ok[subset_mask].reset_index(drop=True)
    mzb = ((data.chord_length_mm >= 150) & (data.chord_length_mm < 200)).values
    X = data[Xcols].values
    y = data["LD"].values
    g = data["run_id"].values
    sw = sample_weight(data) if sample_weight is not None else None
    pred = np.zeros_like(y, dtype=float)
    for tr, te in GroupKFold(n_splits=5).split(X, y, g):
        m = XGBRegressor(**XGB)
        m.fit(X[tr], y[tr], sample_weight=(sw[tr] if sw is not None else None))
        pred[te] = m.predict(X[te])
    yz, pz = y[mzb], pred[mzb]
    mae = np.mean(np.abs(yz - pz))
    return mae, mae / yz.std() * 100, int(mzb.sum())

# baseline: modelo global actual
base_mae, base_rel, nzb = error_zona_baja(FEATURES, label="global")
print("\n" + "=" * 74)
print(f"BASELINE (modelo global, 9 features): LD en 150-200  MAE={base_mae:.3f}  "
      f"MAE/std={base_rel:.0f}%  (n={nzb})")

# =========================================================
# D2 - modelo PONDERADO hacia 150-200  y  ESPECIALIZADO (solo 150-200)
# =========================================================
print("\n" + "=" * 74)
print("D2 - PONDERAR / ESPECIALIZAR el modelo hacia la zona baja")
print("=" * 74)
# (a) ponderado: peso x5 a las muestras de 150-200
def w_zonabaja(data):
    m = (data.chord_length_mm >= 150) & (data.chord_length_mm < 200)
    return np.where(m, 5.0, 1.0)
w_mae, w_rel, _ = error_zona_baja(FEATURES, sample_weight=w_zonabaja)
print(f"  (a) ponderado x5 en 150-200 : MAE={w_mae:.3f}  MAE/std={w_rel:.0f}%   "
      f"(baseline {base_rel:.0f}%)")
# (b) especializado: modelo entrenado SOLO con perfiles de cuerda < 250
mask_peq = ok.chord_length_mm < 250
sp_mae, sp_rel, nsp = error_zona_baja(FEATURES, subset_mask=mask_peq, label="especializado")
print(f"  (b) especializado (<250mm)  : MAE={sp_mae:.3f}  MAE/std={sp_rel:.0f}%   "
      f"(baseline {base_rel:.0f}%)  [entrenado con {ok[mask_peq]['run_id'].nunique()} perfiles]")

# =========================================================
# D3 - FEATURE ENGINEERING para bajo Reynolds
# =========================================================
print("\n" + "=" * 74)
print("D3 - FEATURES DERIVADAS (regimen de bajo Reynolds)")
print("=" * 74)
ok["log_re"] = np.log10(ok["reynolds"])
ok["chord_x_alpha"] = ok["chord_length_mm"] * ok["alpha_deg"]
ok["alpha_over_sqrtre"] = ok["alpha_deg"] / np.sqrt(ok["reynolds"])   # ~efecto viscoso
ok["inv_re"] = 1e6 / ok["reynolds"]                                    # 1/Re (grande a Re bajo)
ok["te_rel"] = ok["trailing_edge_thickness_mm"] / ok["chord_length_mm"]  # TE relativo
combos = {
    "+log_re": FEATURES + ["log_re"],
    "+inv_re": FEATURES + ["inv_re"],
    "+chord_x_alpha": FEATURES + ["chord_x_alpha"],
    "+alpha/sqrt(re)": FEATURES + ["alpha_over_sqrtre"],
    "+te_rel": FEATURES + ["te_rel"],
    "+todas": FEATURES + ["log_re", "inv_re", "chord_x_alpha", "alpha_over_sqrtre", "te_rel"],
}
for name, cols in combos.items():
    m, r, _ = error_zona_baja(cols)
    print(f"  {name:18s}: MAE={m:.3f}  MAE/std={r:.0f}%   (baseline {base_rel:.0f}%)")
