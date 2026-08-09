"""DIAGNOSTICO honesto del modelo TE-real en produccion. SOLO LECTURA/ANALISIS."""
import os, numpy as np, pandas as pd
from sklearn.model_selection import GroupKFold, cross_val_predict
from sklearn.linear_model import LinearRegression
from xgboost import XGBRegressor
from feature_utils import SHAPE, FEATURES, add_derived

BASE = os.path.dirname(os.path.abspath(__file__))
LD_TUNED = dict(n_estimators=400, learning_rate=0.02, max_depth=10, min_child_weight=5,
                subsample=0.6, colsample_bytree=0.9, reg_alpha=0.5, reg_lambda=5.0,
                random_state=42, n_jobs=-1)
def mk(t):
    if t == "CL": return LinearRegression()
    if t == "LD": return XGBRegressor(**LD_TUNED)
    return XGBRegressor(n_estimators=400, learning_rate=0.05, max_depth=5,
                        subsample=0.8, colsample_bytree=0.8, random_state=42, n_jobs=-1)

df = pd.read_csv(os.path.join(BASE, "airfoil_dataset.csv"))
ok = df[df.status == "ok"].copy(); ok = add_derived(ok)
f = ok[ok.chord_length_mm >= 150].reset_index(drop=True)
f["zona"] = pd.cut(f.chord_length_mm, [150, 200, 400, 500], labels=["150-200","200-400","400-500"], include_lowest=True)
g = f.run_id.values
gkf = GroupKFold(5)
print(f"[DATOS] {f.run_id.nunique()} perfiles / {len(f)} filas ok (>=150)")

# OOF predictions
for t in ["CL","CD","LD"]:
    f[t+"_pred"] = cross_val_predict(mk(t), f[FEATURES].values, f[t].values, groups=g, cv=gkf, n_jobs=-1)
    f[t+"_res"] = f[t+"_pred"] - f[t]          # residuo = predicho - real
    f[t+"_ae"] = f[t+"_res"].abs()

def rel(t):  # error relativo % (evita div por ~0)
    d = f[t].abs().clip(lower=1e-6); return (f[t+"_ae"]/d*100)
for t in ["CL","CD","LD"]: f[t+"_rel"] = rel(t)

def blk(title): print("\n"+"="*78+"\n"+title+"\n"+"="*78)

# ---------- 1) DONDE FALLA ----------
blk("1) ERROR GLOBAL (OOF, GroupKFold=5)")
for t in ["CL","CD","LD"]:
    print(f"  {t}: MAE={f[t+'_ae'].mean():.4f}  medRel={f[t+'_rel'].median():.1f}%  "
          f"p90AE={f[t+'_ae'].quantile(.9):.4f}  bias(pred-real)={f[t+'_res'].mean():+.4f}")

for by,lab in [("zona","ZONA"),("velocidad_kmh","VELOCIDAD"),("alpha_deg","ALPHA")]:
    blk(f"1) MAE por {lab}")
    print(f"  {lab:10s}"+"".join(f"{t+'_MAE':>11s}{t+'_med%':>9s}" for t in ["CL","CD","LD"])+"    n")
    for v,sub in f.groupby(by, observed=True):
        row=f"  {str(v):10s}"
        for t in ["CL","CD","LD"]:
            row+=f"{sub[t+'_ae'].mean():11.4f}{sub[t+'_rel'].median():8.1f}%"
        print(row+f"{len(sub):6d}")

blk("1) MAE de LD por RANGO de |LD|")
f["ld_bin"]=pd.cut(f.LD.abs(),[0,30,50,70,90,200],labels=["<30","30-50","50-70","70-90",">90"])
for v,sub in f.groupby("ld_bin",observed=True):
    print(f"  |LD| {str(v):7s}: MAE_LD={sub.LD_ae.mean():6.2f}  medRel={sub.LD_rel.median():5.1f}%  n={len(sub)}")

blk("1) 25 PEORES casos de LD (AE absoluto)")
w=f.nlargest(25,"LD_ae")[["run_id","chord_length_mm","velocidad_kmh","alpha_deg","LD","LD_pred","LD_ae","zona"]]
print(w.to_string(index=False))
print("\n  Composicion de los 40 peores LD:")
w40=f.nlargest(40,"LD_ae")
print("   por zona:", dict(w40.zona.value_counts()))
print("   por vel :", dict(w40.velocidad_kmh.value_counts()))
print("   por alpha:", dict(w40.alpha_deg.value_counts().sort_index()))
print("   perfiles repetidos (>=2 en top40):", (w40.run_id.value_counts()>=2).sum())

# ---------- 2) RESIDUOS ----------
blk("2) ESTRUCTURA DE RESIDUOS de LD (corr residuo vs variables)")
for c in FEATURES+["LD"]:
    print(f"  corr(LD_res, {c:22s}) = {np.corrcoef(f[c],f.LD_res)[0,1]:+.3f}")
print("\n  media de LD_res por alpha (¿sesgo sistematico por angulo?):")
for a,sub in f.groupby("alpha_deg"):
    print(f"   alpha {int(a):>3}: bias={sub.LD_res.mean():+6.2f}  |res|med={sub.LD_ae.median():5.2f}  n={len(sub)}")
print("\n  media de LD_res por velocidad:")
for v,sub in f.groupby("velocidad_kmh"):
    print(f"   v {int(v)}: bias={sub.LD_res.mean():+6.2f}")

# ---------- 3) CALIDAD DE DATOS ----------
blk("3) CALIDAD DE DATOS")
print("  Rangos fisicos (ok, >=150):")
for c in ["CL","CD","LD","CM"]:
    print(f"   {c}: min={f[c].min():.4f} max={f[c].max():.4f} med={f[c].median():.4f}")
print(f"  CD<=0 (no fisico): {(f.CD<=0).sum()}   CD<0.001 (dudoso): {(f.CD<0.001).sum()}")
print(f"  CL>0 (a downforce, alpha<=0): {((f.CL>0)&(f.alpha_deg<=0)).sum()}")
print(f"  |LD|>150 (sospechoso): {(f.LD.abs()>150).sum()}")
print(f"  filas duplicadas exactas de features: {f.duplicated(FEATURES).sum()}")
blk("3) COBERTURA por perfil (nº de condiciones ok por run_id)")
cc=f.groupby("run_id").size()
print(f"  perfiles con <5 filas ok: {(cc<5).sum()}   <10: {(cc<10).sum()}   media={cc.mean():.1f}")
blk("3) DENSIDAD del espacio de forma (perfiles por zona)")
per=f.groupby("run_id").first()
print("  perfiles unicos por zona:", dict(per.zona.value_counts()))
print("  cobertura te_lwr_angle_deg (¿colas ralas?): p5..p95 =",
      f"{per.te_lwr_angle_deg.quantile(.05):.1f}..{per.te_lwr_angle_deg.quantile(.95):.1f}",
      "min/max", f"{per.te_lwr_angle_deg.min():.1f}/{per.te_lwr_angle_deg.max():.1f}")

# ---------- 4) AJUSTE ----------
blk("4) OVER/UNDERFIT: train vs OOF (LD y CD)")
for t in ["LD","CD"]:
    m=mk(t); m.fit(f[FEATURES].values,f[t].values)
    tr=np.abs(m.predict(f[FEATURES].values)-f[t]).mean()
    oof=f[t+"_ae"].mean()
    print(f"  {t}: MAE_train={tr:.4f}  MAE_OOF={oof:.4f}  gap={oof-tr:+.4f}  ratio={oof/tr:.2f}")
print("\n  (gap grande train<<OOF => sobreajuste; ambos altos y juntos => infraajuste)")

f.to_csv(os.path.join(BASE,"_diag_oof.csv"),index=False)
print("\n[OK] OOF guardado en _diag_oof.csv")
