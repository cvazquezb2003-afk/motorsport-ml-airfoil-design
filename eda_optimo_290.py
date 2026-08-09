"""
Re-analisis del angulo de maxima eficiencia (mejor L/D) a 290 km/h, ahora con
datos a -12 y -14. Solo lectura, no toca el pipeline.
"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(BASE, "airfoil_dataset.csv")
OUTDIR = os.path.join(BASE, "eda_outputs")
os.makedirs(OUTDIR, exist_ok=True)

df = pd.read_csv(CSV)
ok = df[(df["status"] == "ok") & (df["velocidad_kmh"] == 290)].copy()
print(f"[INFO] filas ok a 290 km/h: {len(ok)} | perfiles: {ok['run_id'].nunique()}")

# Perfiles que SI tienen datos en la zona profunda nueva (-12 y -14) a 290.
# Asi el optimo no queda recortado por falta de muestreo.
def deep_ok(g):
    a = set(g["alpha_deg"])
    return (-12 in a) and (-14 in a)

deep_profiles = [rid for rid, g in ok.groupby("run_id") if deep_ok(g)]
print(f"[INFO] perfiles con ok en -12 Y -14 a 290 km/h: {len(deep_profiles)}")

# Optimo (min L/D = mas negativo = mas eficiente) por perfil, solo deep.
opt_alphas = []
for rid in deep_profiles:
    g = ok[ok["run_id"] == rid]
    a_best = g.loc[g["LD"].idxmin(), "alpha_deg"]
    opt_alphas.append(a_best)
s = pd.Series(opt_alphas)

print("\n=== ANGULO OPTIMO A 290 km/h (solo perfiles con -12 y -14) ===")
print("distribucion de angulos optimos:")
print(s.value_counts().sort_index().to_string())
print(f"\n  moda  = {int(s.mode().iloc[0])} deg")
print(f"  media = {s.mean():.1f} deg")
print(f"  % con optimo MAS ALLA de -10 (<=-12): {(s <= -12).mean()*100:.0f}%")
print(f"  % con optimo en -10 exacto:           {(s == -10).mean()*100:.0f}%")
print(f"  % con optimo mas suave que -10 (>-10): {(s > -10).mean()*100:.0f}%")

# Comparacion: que habria salido si nos hubieramos quedado en -10 (recorte)
clipped = []
for rid in deep_profiles:
    g = ok[(ok["run_id"] == rid) & (ok["alpha_deg"] >= -10)]
    clipped.append(g.loc[g["LD"].idxmin(), "alpha_deg"])
sc = pd.Series(clipped)
print(f"\n[CONTRASTE] si recortaramos en -10 (esquema viejo), moda seria "
      f"{int(sc.mode().iloc[0])} (media {sc.mean():.1f})")

# --- grafica: L/D vs alpha a 290 hasta -14, algunos perfiles deep ---
elegidos = deep_profiles[:6]
fig, ax = plt.subplots(figsize=(9, 6))
cmap = plt.get_cmap("tab10")
for i, rid in enumerate(elegidos):
    g = ok[ok["run_id"] == rid].sort_values("alpha_deg")
    ax.plot(g["alpha_deg"], g["LD"], "o-", color=cmap(i), alpha=0.8,
            label=f"{rid[:4]} (c={g['chord_length_mm'].iloc[0]:.0f}mm)")
    a_best = g.loc[g["LD"].idxmin(), "alpha_deg"]
    ld_best = g["LD"].min()
    ax.scatter([a_best], [ld_best], s=160, facecolors="none",
               edgecolors=cmap(i), linewidths=2, zorder=5)
ax.axvline(-10, color="gray", ls="--", lw=1, label="-10 (borde viejo)")
ax.set_xlabel("alpha (deg)")
ax.set_ylabel("L/D  (mas negativo = mas eficiente)")
ax.set_title("L/D vs alpha a 290 km/h (hasta -14)\no = optimo de cada perfil")
ax.grid(True, alpha=0.3)
ax.legend(fontsize=8, ncol=2)
fig.tight_layout()
out = os.path.join(OUTDIR, "optimo_290_hasta_-14.png")
fig.savefig(out, dpi=120)
plt.close(fig)
print(f"\n[OK] grafica: {out}")
