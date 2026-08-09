"""
VERIFICACION acotada: el .dat del generador Python, ¿es importable LIMPIO a un CAD?
(No importa que XFOIL converja: solo la calidad del contorno como nube+spline.)
Solo lectura/analisis. NO modifica el generador.
"""
import os, json
import numpy as np
import pandas as pd
from airfoil_geom_python import generate_contour, load_asc, to_canonical, nn_error

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "graficas", "_cad_dats"); os.makedirs(OUT, exist_ok=True)
SHAPE = ["chord_length_mm", "leading_edge_angle_deg", "leading_edge_thickness_level",
         "trailing_edge_angle_deg", "trailing_edge_thickness_mm",
         "te_upr_angle_deg", "te_lwr_angle_deg"]


def _seg_cross(p, q, r, s):
    """¿Se cruzan los segmentos p-q y r-s? (excluye extremos compartidos)."""
    d1, d2 = q - p, s - r
    den = d1[0]*d2[1] - d1[1]*d2[0]
    if abs(den) < 1e-12:
        return False
    t = ((r[0]-p[0])*d2[1] - (r[1]-p[1])*d2[0]) / den
    u = ((r[0]-p[0])*d1[1] - (r[1]-p[1])*d1[0]) / den
    return 1e-9 < t < 1-1e-9 and 1e-9 < u < 1-1e-9


def cad_checks(C, te_mm_rel):
    """Bateria de calidad-CAD sobre el contorno (Nx2, orden de arco)."""
    n = len(C)
    seg = np.linalg.norm(np.diff(C, axis=0), axis=1)
    # 1) duplicados consecutivos
    dup = int((seg < 1e-6).sum())
    # 2) saltos (segmento largo vs mediana)
    med = float(np.median(seg)); jump = float(seg.max()/med)
    # 3) picos: giro por vertice
    d = np.diff(C, axis=0)
    ang = np.arctan2(d[:, 1], d[:, 0])
    turn = np.abs((np.diff(ang)+np.pi) % (2*np.pi) - np.pi)
    turn_deg = np.degrees(turn)
    # LE = zona de x minima (morro): la curvatura alta ahi es LEGITIMA
    xmid = C[1:-1, 0]
    le_zone = xmid < 0.03
    turn_te = turn_deg[~le_zone]           # picos fuera del morro (los que romperian spline)
    # 4) TE romo: primer y ultimo punto = esquinas del TE; hueco ~ te_mm_rel
    gap = float(np.linalg.norm(C[0]-C[-1]))
    # 5) LE cerrado por el morro: el punto de x minima existe y es unico-ish
    x_le = float(C[:, 0].min())
    # 6) auto-interseccion (segmentos no adyacentes). Muestreo para velocidad.
    cruces = 0
    for i in range(n-1):
        pi, qi = C[i], C[i+1]
        for j in range(i+2, n-1):
            if i == 0 and j == n-2:      # primer y ultimo comparten el TE romo: saltar
                continue
            if _seg_cross(pi, qi, C[j], C[j+1]):
                cruces += 1
                if cruces > 5:
                    break
        if cruces > 5:
            break
    return {
        "n_puntos": n, "duplicados": dup, "salto_max_x_mediana": round(jump, 2),
        "giro_max_global_deg": round(float(turn_deg.max()), 1),
        "giro_max_fuera_morro_deg": round(float(turn_te.max()), 1),
        "giro_mediano_deg": round(float(np.median(turn_deg)), 2),
        "gap_TE_rel": round(gap, 5), "te_mm_rel_esperado": round(te_mm_rel, 5),
        "x_LE_min": round(x_le, 4), "auto_intersecciones": cruces,
    }


def escribir_dat(C, path, nombre):
    with open(path, "w") as f:
        f.write(nombre + "\n")
        for x, y in C:
            f.write(f"{x:.6f} {y:.6f}\n")


df = pd.read_csv(os.path.join(BASE, "airfoil_dataset.csv"))
tests = ["0014_20260711_193032", "0004_20260712_214451",
         "0005_20260713_141006", "0001_20260628_221136"]

print("=" * 92)
print("1-2) PERFILES DEL DATASET: error geometrico vs CATIA + calidad CAD del .dat Python")
print("=" * 92)
for rid in tests:
    row = df[df.run_id == rid]
    asc = os.path.join(BASE, "dataset_runs", rid, "auto_export.asc")
    if row.empty or not os.path.exists(asc):
        print(f"{rid}: falta CSV o .asc"); continue
    p = {k: float(row.iloc[0][k]) for k in SHAPE}
    C, dbg = generate_contour(p)
    real, chord = to_canonical(load_asc(asc))
    emax, emed = nn_error(C, real)
    te_rel = (p["trailing_edge_thickness_mm"]) / p["chord_length_mm"]
    chk = cad_checks(C, te_rel)
    escribir_dat(C, os.path.join(OUT, f"py_{rid[:4]}.dat"), f"PY_{rid[:4]}")
    print(f"\n[{rid[:4]}] cuerda={chord:.0f}mm  err_geom: max={emax*100:.2f}% med={emed*100:.2f}%")
    print(f"      {json.dumps(chk)}")

# ---------- 3) OPTIMO de la inversa ----------
print("\n" + "=" * 92)
print("3) .dat de un OPTIMO de la inversa")
print("=" * 92)
prop = os.path.join(BASE, "inversa_v2_propuesta_top1.json")
if os.path.exists(prop):
    d = json.load(open(prop, encoding="utf-8"))
    up = d.get("user_params", d)
    p = {k: float(up[k]) for k in SHAPE}
    C, dbg = generate_contour(p)
    chk = cad_checks(C, p["trailing_edge_thickness_mm"]/p["chord_length_mm"])
    escribir_dat(C, os.path.join(OUT, "py_OPTIMO.dat"), "PY_OPTIMO")
    print(f"optimo (cuerda {p['chord_length_mm']:.0f}mm) -> py_OPTIMO.dat")
    print(f"  params: {json.dumps({k: round(v,3) for k,v in p.items()})}")
    print(f"  calidad CAD: {json.dumps(chk)}")
else:
    print("No hay inversa_v2_propuesta_top1.json; ejecuta la inversa primero.")

print(f"\n[OK] .dat escritos en {OUT}")
