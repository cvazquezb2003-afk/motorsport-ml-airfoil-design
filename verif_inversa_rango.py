"""
VERIFICACION del CAMBIO 2: la inversa optimiza L/D en el RANGO de angulos.
3 casos (misma cuerda 300): Monaco 9-14, Monza 0-5, Medium 5-9.
Comprueba: (a) dan perfiles DISTINTOS; (b) cada uno rinde mejor en SU rango.
Solo lectura/analisis.
"""
import os, time
import numpy as np
import joblib
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from feature_utils import SHAPE, f_alpha_over_sqrtre, f_te_rel
from estilo_graficas import PALETA
import inversa_service as S

BASE = os.path.dirname(os.path.abspath(__file__))
_LD = joblib.load(os.path.join(BASE, "modelo_LD_inversa_xgb.joblib"))["model"]
RHO, MU, V = 1.225, 1.81e-5, 180.0

CASOS = [("Monaco (9-14)", -14, -9, (9, 14)),
         ("Monza  (0-5) ", -5, 0, (0, 5)),
         ("Medium (5-9) ", -9, -5, (5, 9))]
CHORD = 300


def ld_medio(shape, rango_abs, v=V):
    """|L/D| medio predicho de un perfil en un rango de |alpha| (a v km/h)."""
    lo, hi = rango_abs
    alphas = -np.arange(lo, hi + 1e-6, 1.0)
    re = RHO * (v / 3.6) * (shape[0] / 1000.0) / MU
    n = len(alphas)
    full = np.tile(shape, (n, 1))
    trel = np.full(n, f_te_rel(shape[4], shape[0]))
    X = np.column_stack([full, alphas, np.full(n, re),
                         f_alpha_over_sqrtre(alphas, re), trel])
    return float(np.mean(np.abs(_LD.predict(X))))


# --- optimizar los 3 casos ---
res = {}
print("=" * 92)
print("OPTIMOS POR RANGO (cuerda 300). ¿Perfiles distintos?")
print("=" * 92)
print(f"{'caso':16s}" + "".join(f"{k[:10]:>11s}" for k in SHAPE[1:]) + f"{'LDmed':>8s}{'seg':>6s}")
shapes = {}
for nombre, a_from, a_to, rango in CASOS:
    t = time.time(); r = S.optimizar(CHORD, a_from, a_to); dt = time.time() - t
    sp = r["shape_params"]; shapes[nombre] = np.array([sp[k] for k in SHAPE])
    res[nombre] = r
    vals = "".join(f"{sp[k]:11.3f}" for k in SHAPE[1:])
    print(f"{nombre:16s}{vals}{abs(r['LD_predicho']):8.1f}{dt:6.1f}")

# --- distancia entre los 3 perfiles (normalizada) para cuantificar que difieren ---
def norm(s): return (s - S._DMIN.values) / (S._DMAX.values - S._DMIN.values)
nm = list(shapes)
print("\nDistancia entre perfiles (espacio normalizado; ~0.33 = separacion tipica real):")
for i in range(len(nm)):
    for j in range(i + 1, len(nm)):
        d = np.linalg.norm(norm(shapes[nm[i]]) - norm(shapes[nm[j]]))
        print(f"  {nm[i]} vs {nm[j]}: {d:.3f}")

# --- TABLA CRUZADA: |L/D| medio de cada perfil en cada rango ---
print("\n" + "=" * 92)
print("TABLA CRUZADA — |L/D| medio predicho (fila=perfil optimizado, col=rango evaluado, 180 km/h)")
print("Esperado: cada perfil GANA en SU propio rango (diagonal la mas alta de su columna)")
print("=" * 92)
rangos = [(nombre, rango) for nombre, _, _, rango in CASOS]
print(f"{'perfil \\ evaluado en':22s}" + "".join(f"{n.strip():>16s}" for n, _ in rangos))
tabla = {}
for nombre in nm:
    fila = []
    for _, rango in rangos:
        fila.append(ld_medio(shapes[nombre], rango))
    tabla[nombre] = fila
    print(f"{nombre:22s}" + "".join(f"{v:16.1f}" for v in fila))
# quien gana cada columna
print("\nGanador de cada rango (columna):")
for c, (n_col, _) in enumerate(rangos):
    best = max(nm, key=lambda r: tabla[r][c])
    ok = "OK" if best == n_col.replace(" ", "").lower()[:6] or best.split()[0] in n_col else best
    print(f"  rango {n_col.strip():12s}: mejor perfil = {best.split()[0]}")

# --- curvas |L/D| vs |alpha| superpuestas (290 km/h, donde se ve mejor) ---
fig, ax = plt.subplots(figsize=(8, 5), facecolor=PALETA["fondo_papel"])
ax.set_facecolor(PALETA["fondo"])
cols = {nm[0]: PALETA["k2"], nm[1]: PALETA["k0"], nm[2]: "#a06cd5"}
xa = np.arange(0, 14.1, 1.0)
for nombre in nm:
    s = shapes[nombre]; re = RHO * (290 / 3.6) * (s[0] / 1000) / MU
    n = len(xa); full = np.tile(s, (n, 1)); al = -xa
    X = np.column_stack([full, al, np.full(n, re), f_alpha_over_sqrtre(al, re),
                         np.full(n, f_te_rel(s[4], s[0]))])
    ax.plot(xa, np.abs(_LD.predict(X)), "-o", ms=3, color=cols[nombre], label=nombre.strip())
for _, _, _, (lo, hi) in CASOS:
    ax.axvspan(lo, hi, color="#ffffff", alpha=0.04)
ax.set_xlabel("|alpha| (deg)", color=PALETA["texto"]); ax.set_ylabel("|L/D| predicho (290 km/h)", color=PALETA["texto"])
ax.set_title("Optimos por rango — |L/D| vs angulo (bandas = rangos objetivo)", color=PALETA["texto"])
ax.tick_params(colors=PALETA["eje"]); ax.grid(True, color=PALETA["rejilla"], lw=0.5)
ax.legend(facecolor=PALETA["fondo_papel"], edgecolor=PALETA["rejilla"], labelcolor=PALETA["texto"])
fig.savefig(os.path.join(BASE, "graficas", "_verif_rango.png"), dpi=140, facecolor=PALETA["fondo_papel"], bbox_inches="tight")
print("\n[OK] curvas -> graficas/_verif_rango.png")
