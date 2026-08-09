"""
VERIFICACION del generador FIJO sobre OPTIMOS REALES de la inversa + perfiles dataset.
Compara viejo (airfoil_geom_python) vs fijo (airfoil_geom_fixed): auto-intersecciones
y calidad-CAD del contorno. Solo lectura. NO toca produccion ni la inversa.
"""
import os, json
import numpy as np
import pandas as pd
import airfoil_geom_python as OLD
import airfoil_geom_fixed as FIX
import inversa_service as S

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "graficas", "_optimos_dats"); os.makedirs(OUT, exist_ok=True)
SHAPE = ["chord_length_mm", "leading_edge_angle_deg", "leading_edge_thickness_level",
         "trailing_edge_angle_deg", "trailing_edge_thickness_mm",
         "te_upr_angle_deg", "te_lwr_angle_deg"]


def cruces(C):
    n = len(C); c = 0
    def inter(a, b, r, s):
        d1 = b - a; dd = s - r; den = d1[0]*dd[1] - d1[1]*dd[0]
        if abs(den) < 1e-12: return False
        t = ((r[0]-a[0])*dd[1]-(r[1]-a[1])*dd[0])/den
        u = ((r[0]-a[0])*d1[1]-(r[1]-a[1])*d1[0])/den
        return 1e-9 < t < 1-1e-9 and 1e-9 < u < 1-1e-9
    for i in range(n-1):
        for j in range(i+2, n-1):
            if i == 0 and j == n-2: continue
            if inter(C[i], C[i+1], C[j], C[j+1]): c += 1
    return c


def cad_checks(C, te_rel):
    seg = np.linalg.norm(np.diff(C, axis=0), axis=1)
    d = np.diff(C, axis=0); ang = np.arctan2(d[:, 1], d[:, 0])
    turn = np.degrees(np.abs((np.diff(ang)+np.pi) % (2*np.pi) - np.pi))
    xmid = C[1:-1, 0]; te_zone = xmid > 0.85
    gap = float(np.linalg.norm(C[0]-C[-1]))
    return dict(n=len(C), dup=int((seg < 1e-6).sum()),
                salto=round(float(seg.max()/np.median(seg)), 2),
                giro_max_noTE=round(float(turn[xmid < 0.85].max()), 1),
                giro_max_TE=round(float(turn[te_zone].max()), 1) if te_zone.any() else None,
                gap_TE=round(gap, 5), te_rel=round(te_rel, 5))


# --- optimos reales de la inversa (3 rangos) + 2 perfiles del dataset ---
casos = []
print("Corriendo inversa para 3 optimos reales...")
for nombre, a_from, a_to in [("OPT Monaco 9-14", -14, -9),
                             ("OPT Monza  0-5 ", -5, 0),
                             ("OPT Medium 5-9 ", -9, -5)]:
    r = S.optimizar(300, a_from, a_to)
    casos.append((nombre, {k: float(r["shape_params"][k]) for k in SHAPE}))

df = pd.read_csv(os.path.join(BASE, "airfoil_dataset.csv"))
for rid in ["0014_20260711_193032", "0004_20260712_214451"]:
    row = df[df.run_id == rid]
    if not row.empty:
        casos.append(("DAT " + rid[:4] + "      ", {k: float(row.iloc[0][k]) for k in SHAPE}))

print("\n" + "=" * 88)
print("AUTO-INTERSECCIONES: generador VIEJO vs FIJO")
print("=" * 88)
print(f"{'caso':18s}{'te_mm':>7s}{'cruces_VIEJO':>14s}{'cruces_FIJO':>13s}")
for nombre, p in casos:
    Cv, _ = OLD.generate_contour(p)
    Cf, _ = FIX.generate_contour(p)
    print(f"{nombre:18s}{p['trailing_edge_thickness_mm']:7.2f}{cruces(Cv):>14d}{cruces(Cf):>13d}")

print("\n" + "=" * 88)
print("CALIDAD-CAD del contorno FIJO (optimos + dataset)")
print("=" * 88)
for nombre, p in casos:
    Cf, dbg = FIX.generate_contour(p)
    te_rel = p["trailing_edge_thickness_mm"]/p["chord_length_mm"]
    chk = cad_checks(Cf, te_rel)
    sep = float(dbg["TE_upr"][1] - dbg["TE_lwr"][1])   # ahora debe ser > 0
    print(f"{nombre}: sep_TE(y_upr-y_lwr)={sep:+.5f}  {json.dumps(chk)}")
    with open(os.path.join(OUT, f"{nombre.strip().replace(' ','_')}.dat"), "w") as f:
        f.write(nombre.strip()+"\n")
        for x, y in Cf: f.write(f"{x:.6f} {y:.6f}\n")

print(f"\n[OK] .dat de los optimos -> {OUT}")
