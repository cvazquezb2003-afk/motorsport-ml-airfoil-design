"""
D1 (rehecho) - Consistencia de XFOIL en 150-200 vs 200-400.
Para cada (alpha, velocidad), toma los k vecinos MAS CERCANOS en forma (sin filtro
de radio) y mide la dispersion de LD entre ellos, junto a la distancia media de
vecindad (para comparar zonas de forma justa). Si a distancia de forma similar la
dispersion de LD es mayor en 150-200, el ruido es de XFOIL (irreducible).
"""
import os
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

BASE = os.path.dirname(os.path.abspath(__file__))
SHAPE = ["chord_length_mm", "leading_edge_angle_deg", "leading_edge_thickness_level",
         "trailing_edge_angle_deg", "trailing_edge_thickness_mm",
         "te_upr_angle_deg", "te_lwr_angle_deg"]
df = pd.read_csv(os.path.join(BASE, "airfoil_dataset.csv"))
ok = df[(df.status == "ok") & (df.chord_length_mm >= 150)].copy()
lows = ok[SHAPE].min().values; highs = ok[SHAPE].max().values
rng = np.where(highs > lows, highs - lows, 1.0)

def consistencia(lo, hi, k=4):
    sub = ok[(ok.chord_length_mm >= lo) & (ok.chord_length_mm < hi)]
    lds, dists = [], []
    for (a, v), g in sub.groupby(["alpha_deg", "velocidad_kmh"]):
        if len(g) < k + 1:
            continue
        Xn = (g[SHAPE].values - lows) / rng
        tree = cKDTree(Xn)
        d, idx = tree.query(Xn, k=k + 1)      # incluye a si mismo (col 0)
        for i in range(len(g)):
            vec = idx[i][1:]                   # k vecinos
            lds.append(np.std(g["LD"].values[np.r_[i, vec]]))
            dists.append(np.mean(d[i][1:]))
    return (np.median(lds), np.median(dists), len(lds))

print("=" * 72)
print("D1 - CONSISTENCIA DE XFOIL (dispersion de LD entre k=4 vecinos de forma)")
print("=" * 72)
print(f"{'zona':10s}{'std(LD) vecinos':>18s}{'dist forma media':>18s}{'n':>8s}{'std(LD) zona':>15s}")
for lo, hi, lab in [(150, 200, "150-200"), (200, 400, "200-400")]:
    s, dm, n = consistencia(lo, hi)
    zst = ok[(ok.chord_length_mm >= lo) & (ok.chord_length_mm < hi)]["LD"].std()
    print(f"{lab:10s}{s:18.2f}{dm:18.3f}{n:8d}{zst:15.2f}")
print("\nLectura: 'std(LD) vecinos' = ruido local de XFOIL (dispersion de L/D entre")
print("perfiles de forma casi igual, misma condicion). Si en 150-200 es mucho mayor")
print("que en 200-400 A DISTANCIA DE FORMA SIMILAR -> ruido de XFOIL (irreducible).")
