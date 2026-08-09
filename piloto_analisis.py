"""
PILOTO TE-REAL — analisis A (amputado, CSV actual) vs B (TE-real). Solo lectura.
Responde: P1 convergencia, P2 reconexion del 7o parametro, P3 mejora del modelo,
P4 sesgo del TE. Sobre los MISMOS 100 perfiles y MISMAS condiciones.
"""
import os
import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold, cross_val_predict, cross_val_score
from xgboost import XGBRegressor
from feature_utils import SHAPE, FEATURES, add_derived

BASE = os.path.dirname(os.path.abspath(__file__))
B = pd.read_csv(os.path.join(BASE, "airfoil_dataset_TEreal_piloto.csv"))
Aall = pd.read_csv(os.path.join(BASE, "airfoil_dataset.csv"))
pilot = set(B.run_id.unique())
A = Aall[Aall.run_id.isin(pilot)].copy()   # mismos 100 perfiles, mismas condiciones
key = ["run_id", "alpha_deg", "velocidad_kmh"]

def zona(c):
    return "150-200" if c < 200 else ("200-400" if c < 400 else "400-500")
for d in (A, B):
    d["zona"] = d.chord_length_mm.apply(zona)

# =========================================================
print("=" * 70); print("P1 — CONVERGENCIA A (amputado) vs B (TE-real)"); print("=" * 70)
def conv(d): return (d.status == "ok").mean() * 100
print(f"  GLOBAL:  A={conv(A):.1f}%   B={conv(B):.1f}%   (n={len(A)} cond.)")
print("\n  por ZONA:")
for z in ["150-200", "200-400", "400-500"]:
    print(f"    {z}:  A={conv(A[A.zona==z]):5.1f}%   B={conv(B[B.zona==z]):5.1f}%")
print("\n  por ANGULO:")
for a in sorted(A.alpha_deg.unique()):
    print(f"    alpha {int(a):>3}:  A={conv(A[A.alpha_deg==a]):5.1f}%   B={conv(B[B.alpha_deg==a]):5.1f}%  (n={len(A[A.alpha_deg==a])})")
print("\n  por VELOCIDAD:")
for v in [110, 180, 290]:
    print(f"    {v} km/h:  A={conv(A[A.velocidad_kmh==v]):5.1f}%   B={conv(B[B.velocidad_kmh==v]):5.1f}%")

# =========================================================
print("\n" + "=" * 70); print("P4 — SESGO DEL TE (donde AMBOS convergen)"); print("=" * 70)
mA = A[A.status == "ok"][key + ["CL", "CD", "LD", "chord_length_mm", "zona"]]
mB = B[B.status == "ok"][key + ["CL", "CD", "LD"]].rename(columns={"CL": "CLb", "CD": "CDb", "LD": "LDb"})
M = mA.merge(mB, on=key)
M["dCL"] = (M.CLb - M.CL) / M.CL.abs() * 100
M["dCD"] = (M.CDb - M.CD) / M.CD.abs() * 100
M["dLD"] = (M.LDb - M.LD) / M.LD.abs() * 100
print(f"  condiciones con AMBOS ok: {len(M)}")
print(f"  ΔCL%: media={M.dCL.mean():+.1f}  mediana={M.dCL.median():+.1f}  std={M.dCL.std():.1f}")
print(f"  ΔCD%: media={M.dCD.mean():+.1f}  mediana={M.dCD.median():+.1f}  std={M.dCD.std():.1f}")
print(f"  ΔLD%: media={M.dLD.mean():+.1f}  mediana={M.dLD.median():+.1f}  std={M.dLD.std():.1f}")
print("\n  ΔCL medio por ZONA:")
for z in ["150-200", "200-400", "400-500"]:
    s = M[M.zona == z]; print(f"    {z}: ΔCL={s.dCL.mean():+5.1f}%  ΔCD={s.dCD.mean():+5.1f}%  (n={len(s)})")
print("  ΔCL medio por VELOCIDAD:")
for v in [110, 180, 290]:
    s = M[M.velocidad_kmh == v]; print(f"    {v}: ΔCL={s.dCL.mean():+5.1f}%  ΔCD={s.dCD.mean():+5.1f}%")
print("  ΔCL medio por ANGULO:")
for a in sorted(M.alpha_deg.unique()):
    s = M[M.alpha_deg == a]; print(f"    a{int(a):>3}: ΔCL={s.dCL.mean():+5.1f}%  ΔCD={s.dCD.mean():+5.1f}%  (n={len(s)})")

# =========================================================
# P2 y P3 — modelos A vs B sobre los MISMOS perfiles
# =========================================================
def prep(d):
    ok = d[d.status == "ok"].copy()
    ok = add_derived(ok)
    return ok
okA, okB = prep(A), prep(B)

print("\n" + "=" * 70); print("P2 — ¿SE RECONECTA te_thickness / te_rel?"); print("=" * 70)
print("  CORRELACION (Pearson) feature vs target:")
print(f"    {'feature':28s}{'target':4s}{'A(amput)':>10s}{'B(TEreal)':>11s}")
for feat in ["trailing_edge_thickness_mm", "te_rel"]:
    for tgt in ["CL", "CD", "LD"]:
        ca = np.corrcoef(okA[feat], okA[tgt])[0, 1]
        cb = np.corrcoef(okB[feat], okB[tgt])[0, 1]
        print(f"    {feat:28s}{tgt:4s}{ca:>10.3f}{cb:>11.3f}")

print("\n  IMPORTANCIA en XGBoost (LD y CD):")
def imp(ok, tgt):
    m = XGBRegressor(n_estimators=400, learning_rate=0.05, max_depth=5,
                     subsample=0.8, colsample_bytree=0.8, random_state=42, n_jobs=-1)
    m.fit(ok[FEATURES].values, ok[tgt].values)
    return dict(zip(FEATURES, m.feature_importances_))
for tgt in ["LD", "CD"]:
    iA, iB = imp(okA, tgt), imp(okB, tgt)
    print(f"    [{tgt}]  {'feature':28s}{'A':>8s}{'B':>8s}")
    for feat in ["trailing_edge_thickness_mm", "te_rel"]:
        print(f"          {feat:28s}{iA[feat]*100:7.1f}%{iB[feat]*100:7.1f}%")

print("\n" + "=" * 70); print("P3 — METRICAS CV (mismos 100 perfiles): A vs B"); print("=" * 70)
def cv(ok, tgt):
    X, y, g = ok[FEATURES].values, ok[tgt].values, ok.run_id.values
    gkf = GroupKFold(n_splits=5)
    m = XGBRegressor(n_estimators=400, learning_rate=0.05, max_depth=5,
                     subsample=0.8, colsample_bytree=0.8, random_state=42, n_jobs=-1)
    pred = cross_val_predict(m, X, y, groups=g, cv=gkf, n_jobs=-1)
    mae = np.mean(np.abs(y - pred))
    r2 = cross_val_score(m, X, y, groups=g, cv=gkf, scoring="r2").mean()
    return mae, r2
print(f"  {'target':6s}{'MAE_A':>10s}{'MAE_B':>10s}{'R2_A':>8s}{'R2_B':>8s}")
for tgt in ["CL", "CD", "LD"]:
    mA, rA = cv(okA, tgt); mB, rB = cv(okB, tgt)
    print(f"  {tgt:6s}{mA:10.5f}{mB:10.5f}{rA:8.3f}{rB:8.3f}")
