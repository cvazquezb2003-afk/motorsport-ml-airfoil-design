"""
EDA del efecto de la velocidad (Reynolds) sobre la eficiencia L/D.
Solo lectura, no toca el pipeline.
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

VELS = [110, 180, 290]
COLORS = {110: "#2b6cb0", 180: "#dd6b20", 290: "#c53030"}
ALPHAS = [0, -2, -4, -6, -8, -10]

df = pd.read_csv(CSV)
ok = df[df["status"] == "ok"].copy()
print(f"[INFO] filas ok: {len(ok)} | perfiles: {ok['run_id'].nunique()}")

# --- elegir perfiles que convergieron en (casi) todas sus 18 condiciones ---
counts = ok.groupby("run_id").size().sort_values(ascending=False)
full = counts[counts == 18].index.tolist()
print(f"[INFO] perfiles con las 18 condiciones ok: {len(full)}")
elegidos = full[:3] if len(full) >= 3 else counts.index[:3].tolist()
print(f"[INFO] perfiles elegidos: {elegidos}")

# --- grafica L/D vs alpha, 3 curvas (una por velocidad) por perfil ---
fig, axes = plt.subplots(1, len(elegidos), figsize=(6 * len(elegidos), 5.2),
                         squeeze=False)
for k, rid in enumerate(elegidos):
    ax = axes[0][k]
    g = ok[ok["run_id"] == rid]
    chord = g["chord_length_mm"].iloc[0]
    for v in VELS:
        gv = g[g["velocidad_kmh"] == v].sort_values("alpha_deg")
        ax.plot(gv["alpha_deg"], gv["LD"], "o-", color=COLORS[v],
                label=f"{v} km/h (Re={gv['reynolds'].iloc[0]/1e6:.2f}M)")
    ax.set_title(f"{rid}\ncuerda={chord:.0f} mm", fontsize=9)
    ax.set_xlabel("alpha (deg)")
    ax.set_ylabel("L/D")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8)
fig.suptitle("L/D vs alpha por velocidad (efecto del Reynolds)", fontsize=13)
fig.tight_layout(rect=[0, 0, 1, 0.95])
out = os.path.join(OUTDIR, "LD_vs_alpha_por_velocidad.png")
fig.savefig(out, dpi=120)
plt.close(fig)
print(f"[OK] grafica: {out}")

# --- efecto medio de la velocidad sobre L/D a igual angulo ---
# emparejamos cada (run_id, alpha) que exista a las 3 velocidades
piv = ok.pivot_table(index=["run_id", "alpha_deg"],
                     columns="velocidad_kmh", values="LD")
piv = piv.dropna(subset=VELS)  # solo condiciones presentes a las 3 velocidades
print(f"\n[INFO] (perfil, alpha) presentes a las 3 velocidades: {len(piv)}")

print("\n=== L/D MEDIO por velocidad (sobre esas condiciones emparejadas) ===")
for v in VELS:
    print(f"  {v} km/h : L/D medio = {piv[v].mean():.2f}")

# como L/D es negativo, 'mas eficiente' = mas negativo (mayor magnitud)
delta = piv[290] - piv[110]            # raw
print(f"\n[RESUMEN] cambio medio de L/D al pasar de 110 a 290 km/h: "
      f"{delta.mean():+.2f}")
print(f"          |L/D| medio: 110={piv[110].abs().mean():.2f}  "
      f"180={piv[180].abs().mean():.2f}  290={piv[290].abs().mean():.2f}")
mejora = (piv[290].abs() > piv[110].abs()).mean() * 100
print(f"          % de casos donde |L/D| sube (mas eficiente) de 110 a 290: "
      f"{mejora:.0f}%")

# --- angulo de maxima eficiencia (mejor L/D = mas negativo) por velocidad ---
print("\n=== ANGULO DE MAXIMA EFICIENCIA (mejor L/D) por velocidad ===")
print("(por perfil; luego la moda sobre todos los perfiles)")
best_by_vel = {v: [] for v in VELS}
for rid, g in ok.groupby("run_id"):
    for v in VELS:
        gv = g[g["velocidad_kmh"] == v]
        if len(gv) >= 4:  # suficientes angulos para que tenga sentido
            a_best = gv.loc[gv["LD"].idxmin(), "alpha_deg"]  # min = mas negativo
            best_by_vel[v].append(a_best)
for v in VELS:
    s = pd.Series(best_by_vel[v])
    print(f"  {v} km/h : angulo optimo mas frecuente = {int(s.mode().iloc[0])}  "
          f"(media {s.mean():.1f}, n={len(s)} perfiles)")
