"""
Detecta AUTOINTERSECCION del contorno: y_extrados < y_intrados en algun x
(las dos caras se cruzan). Recorre el contorno por ORDEN DE ARCO cortando en
argmin(x) (el LE), como hace XFOIL, e interpola ambas ramas en una rejilla de x
comun para comparar. Solo lectura.
"""
import os, sys, glob
import numpy as np
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
RUNS = os.path.join(BASE, "dataset_runs")


def leer_dat(path):
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        ls = f.readlines()
    pts = []
    for ln in ls[1:]:
        p = ln.split()
        if len(p) >= 2:
            try:
                pts.append((float(p[0]), float(p[1])))
            except ValueError:
                pass
    a = np.array(pts)
    return a[:, 0], a[:, 1]


def ramas(x, y):
    """Corta el contorno en el LE (argmin x) -> dos ramas ordenadas por x."""
    i_le = int(np.argmin(x))
    r1 = (x[:i_le + 1], y[:i_le + 1])
    r2 = (x[i_le:], y[i_le:])
    out = []
    for xs, ys in (r1, r2):
        o = np.argsort(xs)
        out.append((xs[o], ys[o]))
    return out


def cruce(path, n=400, tol=1e-9):
    """Devuelve (hay_cruce, x_cruce_max, gap_max_negativo, rango_x_cruce)."""
    x, y = leer_dat(path)
    (xa, ya), (xb, yb) = ramas(x, y)
    lo = max(xa.min(), xb.min())
    hi = min(xa.max(), xb.max())
    if hi <= lo:
        return False, None, 0.0, None
    xg = np.linspace(lo, hi, n)
    ia = np.interp(xg, xa, ya)
    ib = np.interp(xg, xb, yb)
    d = ia - ib
    # cual rama es la de arriba (mediana del signo en el interior)
    interior = (xg > lo + 0.02 * (hi - lo)) & (xg < hi - 0.02 * (hi - lo))
    if not interior.any():
        return False, None, 0.0, None
    signo = np.sign(np.median(d[interior]))
    if signo == 0:
        return False, None, 0.0, None
    dd = d * signo          # >0 = orden correcto (arriba por encima)
    mal = dd < -tol         # aqui la rama de arriba cae POR DEBAJO -> cruce
    mal &= interior
    if not mal.any():
        return False, None, 0.0, None
    return True, float(xg[mal].max()), float(dd[mal].min()), (float(xg[mal].min()), float(xg[mal].max()))


if __name__ == "__main__":
    # ---- 1) el perfil concreto ----
    rid = "0001_20260628_221136"
    p = os.path.join(RUNS, rid, "airfoil_v4.dat")
    x, y = leer_dat(p)
    (xa, ya), (xb, yb) = ramas(x, y)
    print("=" * 74)
    print(f"PERFIL {rid}  ({len(x)} puntos)")
    print("=" * 74)
    hay, xmax, gap, rng = cruce(p)
    print(f"  cruce detectado : {hay}")
    if hay:
        print(f"  rango x/c con cruce: {rng[0]:.4f} .. {rng[1]:.4f}")
        print(f"  solape maximo (y): {gap:.6f} (en unidades de cuerda)")
        print(f"  -> en mm (cuerda 280.87): x = {rng[0]*280.87:.1f} .. {rng[1]*280.87:.1f} mm, "
              f"solape {abs(gap)*280.87:.3f} mm")
    # tabla cerca del TE
    print("\n  y de cada rama cerca del TE (x/c -> y/c):")
    xg = np.linspace(0.90, min(xa.max(), xb.max()), 12)
    ia = np.interp(xg, xa, ya); ib = np.interp(xg, xb, yb)
    print(f"    {'x/c':>7s}{'rama A':>11s}{'rama B':>11s}{'A-B':>11s}")
    for xv, a, b in zip(xg, ia, ib):
        print(f"    {xv:7.4f}{a:11.5f}{b:11.5f}{a-b:11.5f}")

    # ---- 2) barrido de TODO el dataset ----
    print("\n" + "=" * 74)
    print("BARRIDO DEL DATASET (todos los dataset_runs con .dat)")
    print("=" * 74)
    dats = sorted(glob.glob(os.path.join(RUNS, "*", "airfoil_v4.dat")))
    tot = 0; con = []
    for d in dats:
        tot += 1
        try:
            hay, xmax, gap, rng = cruce(d)
        except Exception:
            continue
        if hay:
            con.append((os.path.basename(os.path.dirname(d)), rng[0], rng[1], gap))
    print(f"  perfiles con .dat : {tot}")
    print(f"  con AUTOINTERSECCION: {len(con)}  ({100*len(con)/max(tot,1):.1f}%)")
    if con:
        xs_ini = np.array([c[1] for c in con])
        gaps = np.array([abs(c[3]) for c in con])
        print(f"  x/c donde empieza el cruce: min={xs_ini.min():.3f} "
              f"mediana={np.median(xs_ini):.3f} max={xs_ini.max():.3f}")
        print(f"  solape (y/c): mediana={np.median(gaps):.5f} max={gaps.max():.5f}")
        print("\n  primeros 10 afectados:")
        for r, a, b, g in con[:10]:
            print(f"    {r}  x/c {a:.3f}-{b:.3f}  solape {abs(g):.5f}")
        pd.DataFrame(con, columns=["run_id", "x_ini", "x_fin", "gap"]).to_csv(
            os.path.join(BASE, "perfiles_autointersecados.csv"), index=False)
        print(f"\n  [OK] lista completa -> perfiles_autointersecados.csv")
