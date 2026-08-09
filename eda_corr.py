"""
EDA paso 2: correlaciones con/sin outlier run 0021 + heatmap global.
Solo lectura, no toca el pipeline.
"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(BASE, "airfoil_dataset.csv")
OUTDIR = os.path.join(BASE, "eda_outputs")
os.makedirs(OUTDIR, exist_ok=True)

SHAPE = [
    "chord_length_mm", "leading_edge_angle_deg", "leading_edge_thickness_level",
    "trailing_edge_angle_deg", "trailing_edge_thickness_mm",
    "te_upr_angle_deg", "te_lwr_angle_deg",
]
PERF = ["CL", "CD", "LD"]

df = pd.read_csv(CSV)
ok = df[df["status"] == "ok"].copy()

# outlier: el unico perfil con CD anomalamente bajo (CD=0.00802 / LD=-60).
# Lo identificamos por su valor unico de CD, NO por prefijo de run_id
# (varios lotes tienen un '0021_...' distinto).
mask_out = ok["CD"] < 0.012
ok_no = ok[~mask_out].copy()
print(f"[INFO] ok con outlier: {len(ok)} | sin outlier: {len(ok_no)}")
print(f"[INFO] filas marcadas como outlier: {int(mask_out.sum())}")
for rid in ok.loc[mask_out, "run_id"]:
    print(f"[INFO] outlier excluido: run_id={rid}")
print()

# ---------- comparacion de correlaciones param -> LD ----------
rows = []
for p in SHAPE:
    rows.append((p, ok[p].corr(ok["LD"]), ok_no[p].corr(ok_no["LD"])))
comp = pd.DataFrame(rows, columns=["param", "con_outlier", "sin_outlier"])
comp["delta"] = comp["sin_outlier"] - comp["con_outlier"]
comp["abs_sin"] = comp["sin_outlier"].abs()
comp = comp.sort_values("abs_sin", ascending=False)

print("=" * 70)
print("CORRELACION DE CADA PARAMETRO CON LD: con vs sin outlier 0021")
print("=" * 70)
print(f"{'param':32s} {'con_out':>9s} {'sin_out':>9s} {'cambio':>9s}")
for _, r in comp.iterrows():
    print(f"{r['param']:32s} {r['con_outlier']:+9.3f} {r['sin_outlier']:+9.3f} {r['delta']:+9.3f}")

# ---------- heatmap de correlacion global ----------
cols = SHAPE + PERF
corr = ok_no[cols].corr()  # usamos sin outlier para el mapa "limpio"

fig, ax = plt.subplots(figsize=(10, 8.5))
im = ax.imshow(corr.values, cmap="RdBu_r", vmin=-1, vmax=1)
ax.set_xticks(range(len(cols)))
ax.set_yticks(range(len(cols)))
ax.set_xticklabels(cols, rotation=45, ha="right", fontsize=8)
ax.set_yticklabels(cols, fontsize=8)
for i in range(len(cols)):
    for j in range(len(cols)):
        v = corr.values[i, j]
        ax.text(j, i, f"{v:.2f}", ha="center", va="center",
                color="white" if abs(v) > 0.55 else "black", fontsize=7)
cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
cbar.set_label("correlacion (Pearson)")
ax.set_title("Heatmap de correlacion (137 ok, sin outlier 0021)", fontsize=12)
fig.tight_layout()
heat = os.path.join(OUTDIR, "heatmap_correlacion.png")
fig.savefig(heat, dpi=120)
plt.close(fig)
print(f"\n[OK] Heatmap guardado: {heat}")

# correlaciones mas fuertes entre parametros de forma (posible redundancia)
print("\n[INFO] Correlaciones |r|>0.3 entre PARAMETROS de forma (sin outlier):")
found = False
for i in range(len(SHAPE)):
    for j in range(i + 1, len(SHAPE)):
        r = corr.loc[SHAPE[i], SHAPE[j]]
        if abs(r) > 0.3:
            print(f"   {SHAPE[i]} <-> {SHAPE[j]}: {r:+.2f}")
            found = True
if not found:
    print("   (ninguna: los 7 parametros son practicamente independientes entre si)")
