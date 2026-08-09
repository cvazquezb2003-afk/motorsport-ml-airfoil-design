"""
EDA inicial del dataset de perfiles alares. Solo lectura: NO toca el pipeline.
Genera estadisticas, deteccion de outliers y scatter plots param->LD.
"""
import os
import matplotlib
matplotlib.use("Agg")  # backend sin ventana (headless)
import matplotlib.pyplot as plt
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(BASE, "airfoil_dataset.csv")
OUTDIR = os.path.join(BASE, "eda_outputs")
os.makedirs(OUTDIR, exist_ok=True)

SHAPE_PARAMS = [
    "chord_length_mm", "leading_edge_angle_deg", "leading_edge_thickness_level",
    "trailing_edge_angle_deg", "trailing_edge_thickness_mm",
    "te_upr_angle_deg", "te_lwr_angle_deg",
]

# ---------- PASO 1: carga y filtrado ----------
df = pd.read_csv(CSV)
n_total = len(df)
n_ok = int((df["status"] == "ok").sum())
ok = df[df["status"] == "ok"].copy().reset_index(drop=True)

print("=" * 60)
print("PASO 1 - CARGA Y FILTRADO")
print("=" * 60)
print(f"Filas totales        : {n_total}")
print(f"Filas status=ok      : {n_ok}")
print(f"Filas descartadas    : {n_total - n_ok} (sin datos aerodinamicos)")
print(f"Trabajaremos con     : {len(ok)} perfiles")

# ---------- PASO 2: estadisticas de rendimiento ----------
print("\n" + "=" * 60)
print("PASO 2 - ESTADISTICAS DE RENDIMIENTO (solo ok)")
print("=" * 60)
stats = ok[["CL", "CD", "LD"]].agg(["min", "max", "mean", "median"]).T
stats.columns = ["min", "max", "media", "mediana"]
print(stats.to_string(float_format=lambda x: f"{x:.5f}"))

# ---------- PASO 3: outliers ----------
print("\n" + "=" * 60)
print("PASO 3 - DETECCION DE OUTLIERS (metodo IQR)")
print("=" * 60)


def iqr_bounds(s, k=1.5):
    q1, q3 = s.quantile(0.25), s.quantile(0.75)
    iqr = q3 - q1
    return q1 - k * iqr, q3 + k * iqr


for col in ["CD", "LD"]:
    lo, hi = iqr_bounds(ok[col])
    out = ok[(ok[col] < lo) | (ok[col] > hi)]
    print(f"\n{col}: rango normal IQR = [{lo:.5f}, {hi:.5f}]  -> {len(out)} outliers")
    for _, r in out.iterrows():
        print(f"   run={r['run_id']}  chord={r['chord_length_mm']:.1f}  "
              f"CD={r['CD']:.5f}  LD={r['LD']:.2f}  CL={r['CL']:.3f}")

# fila 54 del dataset completo (1-based) = la del CD anomalo
print("\n[CHEQUEO] fila 54 del dataset completo (1-based):")
r54 = df.iloc[53]
print(f"   run={r54['run_id']}  status={r54['status']}  CD={r54['CD']}  LD={r54['LD']}")

# ---------- PASO 4: scatter plots param -> LD ----------
print("\n" + "=" * 60)
print("PASO 4 - SCATTER PLOTS (cada parametro vs LD) + correlacion")
print("=" * 60)

fig, axes = plt.subplots(3, 3, figsize=(15, 12))
axes = axes.flatten()
corrs = {}
for i, p in enumerate(SHAPE_PARAMS):
    ax = axes[i]
    ax.scatter(ok[p], ok["LD"], s=18, alpha=0.6, color="#2b6cb0", edgecolors="none")
    r = ok[p].corr(ok["LD"])
    corrs[p] = r
    ax.set_title(f"{p}\ncorr con LD = {r:+.2f}", fontsize=10)
    ax.set_xlabel(p, fontsize=8)
    ax.set_ylabel("LD", fontsize=8)
    ax.grid(True, alpha=0.3)
for j in range(len(SHAPE_PARAMS), len(axes)):
    axes[j].axis("off")
fig.suptitle("Parametros de forma vs L/D (eficiencia)  -  n=%d perfiles ok" % len(ok),
             fontsize=13)
fig.tight_layout(rect=[0, 0, 1, 0.97])
combined = os.path.join(OUTDIR, "scatter_params_vs_LD.png")
fig.savefig(combined, dpi=110)
plt.close(fig)

# tambien uno por parametro, por si los quieres sueltos
for p in SHAPE_PARAMS:
    f, a = plt.subplots(figsize=(6, 4))
    a.scatter(ok[p], ok["LD"], s=20, alpha=0.6, color="#2b6cb0", edgecolors="none")
    a.set_title(f"{p} vs LD  (corr={corrs[p]:+.2f})")
    a.set_xlabel(p); a.set_ylabel("LD"); a.grid(True, alpha=0.3)
    f.tight_layout()
    f.savefig(os.path.join(OUTDIR, f"scatter_{p}_vs_LD.png"), dpi=100)
    plt.close(f)

print("Correlacion (Pearson) de cada parametro con LD, ordenada por |valor|:")
for p, r in sorted(corrs.items(), key=lambda kv: -abs(kv[1])):
    print(f"   {p:32s} {r:+.3f}")
print(f"\n[OK] Grafica combinada: {combined}")
print(f"[OK] Graficas sueltas en: {OUTDIR}")
