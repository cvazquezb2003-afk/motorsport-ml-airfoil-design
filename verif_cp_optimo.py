"""
VERIFICACION acotada: el .dat del generador ARREGLADO, ¿converge en XFOIL?
Si converge -> extrae Cp del optimo real y lo compara con el Cp del vecino.
Portable (XFOIL, sin CATIA). Solo lectura; no recalibra el generador.
"""
import os, tempfile
import numpy as np
import airfoil_geom_fixed as FIX
import inversa_service as S
from graficas_cp import _xfoil_cp, _split_arc, _reynolds
from graficas_forma import _dat_tereal
from vecino import encontrar_vecino

BASE = os.path.dirname(os.path.abspath(__file__))
SHAPE = ["chord_length_mm", "leading_edge_angle_deg", "leading_edge_thickness_level",
         "trailing_edge_angle_deg", "trailing_edge_thickness_mm",
         "te_upr_angle_deg", "te_lwr_angle_deg"]
WORK = os.path.join(tempfile.gettempdir(), "cp_optimo"); os.makedirs(WORK, exist_ok=True)

# 5 optimos variados (rango, cuerda)
CASOS = [("Monaco 9-14 c300", -14, -9, 300), ("Monza  0-5  c300", -5, 0, 300),
         ("Medium 5-9  c300", -9, -5, 300), ("High   9-14 c450", -14, -9, 450),
         ("Low    0-5  c200", -5, 0, 200)]


def escribe_dat(C, path, nombre="OPT"):
    with open(path, "w") as f:
        f.write(nombre + "\n")
        for x, y in C:
            f.write(f"{x:.6f} {y:.6f}\n")


def cp_por_superficie(arr):
    """arr (N,3) x,y,Cp orden de arco -> succion, presion (cada uno x ordenado)."""
    A, B = _split_arc(arr)
    suc, pre = (A, B) if np.nanmean(A[:, 2]) <= np.nanmean(B[:, 2]) else (B, A)
    return suc, pre


def cp_en_x(arr_surf, xs):
    o = np.argsort(arr_surf[:, 0])
    return np.interp(xs, arr_surf[o, 0], arr_surf[o, 2])


print("=" * 96)
print("XFOIL sobre el .dat del OPTIMO (generador arreglado) — ¿converge? + Cp vs vecino")
print("=" * 96)
print(f"{'caso':18s}{'a':>4s}{'conv_OPT':>10s}{'LD_opt':>8s}{'sim%':>6s}{'conv_VEC':>10s}"
      f"{'LD_vec':>8s}{'maxdCp':>8s}{'meandCp':>8s}")
xs = np.linspace(0.03, 0.97, 60)
for nombre, a_from, a_to, chord in CASOS:
    r = S.optimizar(chord, a_from, a_to)
    p = {k: float(r["shape_params"][k]) for k in SHAPE}
    mid = (abs(a_from) + abs(a_to)) / 2
    alpha = -int(round(mid))                  # angulo entero exacto (unificado)
    Re = int(round(_reynolds(chord, 290)))

    C, _ = FIX.generate_contour(p)
    dat = os.path.join(WORK, "opt.dat"); escribe_dat(C, dat)
    cp_opt, clcd_opt = _xfoil_cp(dat, Re, alpha, WORK)
    conv_opt = cp_opt is not None and len(cp_opt) > 20
    ld_opt = (clcd_opt[0] / clcd_opt[1]) if (clcd_opt and clcd_opt[1]) else None

    # vecino en la MISMA condicion
    v = encontrar_vecino(p)
    datv = _dat_tereal(v["run_id"])
    cp_vec, clcd_vec = _xfoil_cp(datv, Re, alpha, os.path.join(WORK, "vec"))
    conv_vec = cp_vec is not None and len(cp_vec) > 20
    ld_vec = (clcd_vec[0] / clcd_vec[1]) if (clcd_vec and clcd_vec[1]) else None

    maxd = meand = None
    if conv_opt and conv_vec:
        so, po = cp_por_superficie(cp_opt); sv, pv = cp_por_superficie(cp_vec)
        d = np.concatenate([np.abs(cp_en_x(so, xs) - cp_en_x(sv, xs)),
                            np.abs(cp_en_x(po, xs) - cp_en_x(pv, xs))])
        maxd, meand = float(np.nanmax(d)), float(np.nanmean(d))

    def f(x, w=8, d=2): return (f"{x:{w}.{d}f}" if x is not None else f"{'-':>{w}s}")
    print(f"{nombre:18s}{alpha:>4d}{('SI' if conv_opt else 'NO'):>10s}{f(ld_opt,8,1)}"
          f"{v['similitud_pct']:>6.0f}{('SI' if conv_vec else 'NO'):>10s}{f(ld_vec,8,1)}"
          f"{f(maxd)}{f(meand)}")

print("\n(maxdCp/meandCp = diferencia de Cp optimo vs vecino sobre la superficie, en unidades de Cp)")
