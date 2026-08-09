"""
COMPARACION DE SIGMA: ensemble de produccion vs ensemble densificado.

sigma no es una metrica de validacion cruzada: es la DISPERSION del ensemble en un
punto de consulta. Asi que no se compara con un test set, sino evaluando LOS DOS
ensembles sobre LOS MISMOS puntos de consulta y viendo como cambia la dispersion.

Puntos de consulta: los 7 params de cada perfil real del catalogo (>=150 mm), barridos
en velocidad de 110 a 290 km/h y en angulo dentro de la banda util. Es el espacio por
el que se mueve la inversa cuando el usuario pide una velocidad cualquiera.

EXPECTATIVA A CONTRASTAR: sigma deberia BAJAR sobre todo en el hueco 180-290 km/h, que
es lo que la densificacion venia a rellenar. Si bajara por igual en todas partes seria
sospechoso (mas datos siempre estrechan el bootstrap); lo que valida la tirada es que
baje MAS donde no habia datos.

NO toca produccion ni reentrena: solo carga los dos .joblib y predice.
"""
import os, sys
import numpy as np
import pandas as pd
import joblib

BASE = os.path.dirname(os.path.abspath(__file__))
from feature_utils import SHAPE, FEATURES, f_alpha_over_sqrtre, f_te_rel

RHO, MU = 1.225, 1.81e-5
ENS_PROD = os.path.join(BASE, "ensemble_ld_sigma.joblib")
ENS_NEW = os.path.join(BASE, "ensemble_ld_sigma_densif.joblib")


def reynolds(c_mm, v):
    return RHO * (v / 3.6) * (c_mm / 1000.0) / MU


def arma_X(shape_rows, alpha, v):
    n = len(shape_rows)
    chord = shape_rows[:, 0]
    te = shape_rows[:, 4]
    a = np.full(n, float(alpha))
    re = reynolds(chord, v)
    return np.column_stack([shape_rows, a, re, f_alpha_over_sqrtre(a, re),
                            f_te_rel(te, chord)])


def sigma(ens, X):
    P = np.stack([m.predict(X) for m in ens])
    return P.std(axis=0)


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    prod = pd.read_csv(os.path.join(BASE, "airfoil_dataset.csv"))
    ok = prod[(prod.status == "ok") & (prod.chord_length_mm >= 150)]
    per = ok.groupby("run_id")[SHAPE].first()
    S = per.values
    print("puntos de consulta: %d perfiles reales del catalogo" % len(S))

    e_prod = joblib.load(ENS_PROD)
    e_new = joblib.load(ENS_NEW)
    print("ensembles: produccion %d miembros | densificado %d miembros\n"
          % (len(e_prod), len(e_new)))

    VELS = [110, 130, 150, 170, 180, 200, 220, 250, 270, 290]
    ALPHAS = [-4, -6, -8, -10]
    filas = []
    for v in VELS:
        for a in ALPHAS:
            X = arma_X(S, a, v)
            filas.append({"v": v, "alpha": a,
                          "s_prod": float(np.mean(sigma(e_prod, X))),
                          "s_new": float(np.mean(sigma(e_new, X)))})
    t = pd.DataFrame(filas)
    t["delta_pct"] = 100 * (t.s_new - t.s_prod) / t.s_prod

    print("=" * 96)
    print("SIGMA MEDIA por velocidad (promediada sobre %d perfiles y %d angulos)"
          % (len(S), len(ALPHAS)))
    print("=" * 96)
    print("   %-11s %-12s %-12s %-11s %s" % ("V", "sigma PROD", "sigma NUEVO", "cambio", "zona"))
    g = t.groupby("v").agg(s_prod=("s_prod", "mean"), s_new=("s_new", "mean"))
    g["delta_pct"] = 100 * (g.s_new - g.s_prod) / g.s_prod
    for v, r in g.iterrows():
        if v in (110, 180, 290):
            z = "velocidad CON datos (antes y ahora)"
        elif v in (150, 220, 250):
            z = "velocidad NUEVA (generada)"
        else:
            z = "interpolada (nunca evaluada)"
        print("   %-11s %-12.4f %-12.4f %-11s %s"
              % ("%d km/h" % v, r.s_prod, r.s_new, "%+.1f%%" % r.delta_pct, z))

    print("\n" + "=" * 96)
    print("EL CONTRASTE QUE IMPORTA: hueco 180-290 vs velocidades que ya tenian datos")
    print("=" * 96)
    hueco = t[(t.v > 180) & (t.v < 290)]
    conds = t[t.v.isin([110, 180, 290])]
    for nombre, sub in (("velocidades CON datos previos (110/180/290)", conds),
                        ("HUECO 180-290 (200/220/250/270)", hueco)):
        print("   %-46s sigma %.4f -> %.4f   %+.1f%%"
              % (nombre, sub.s_prod.mean(), sub.s_new.mean(),
                 100 * (sub.s_new.mean() - sub.s_prod.mean()) / sub.s_prod.mean()))
    r_h = 100 * (hueco.s_new.mean() - hueco.s_prod.mean()) / hueco.s_prod.mean()
    r_c = 100 * (conds.s_new.mean() - conds.s_prod.mean()) / conds.s_prod.mean()
    print("\n   -> la caida en el hueco es %.1fx la de las velocidades ya cubiertas"
          % (r_h / r_c if r_c else float("nan")))

    print("\n" + "=" * 96)
    print("SIGMA por ANGULO (los impares eran los que no existian)")
    print("=" * 96)
    filas2 = []
    for a in range(0, -15, -1):
        X = arma_X(S, a, 180)
        filas2.append({"alpha": a, "s_prod": float(np.mean(sigma(e_prod, X))),
                       "s_new": float(np.mean(sigma(e_new, X)))})
    t2 = pd.DataFrame(filas2)
    t2["delta_pct"] = 100 * (t2.s_new - t2.s_prod) / t2.s_prod
    print("   (a 180 km/h)")
    print("   %-8s %-12s %-12s %-10s %s" % ("alpha", "PROD", "NUEVO", "cambio", "paridad"))
    for _, r in t2.iterrows():
        print("   %-8d %-12.4f %-12.4f %-10s %s"
              % (r.alpha, r.s_prod, r.s_new, "%+.1f%%" % r.delta_pct,
                 "par (ya existia)" if int(r.alpha) % 2 == 0 else "IMPAR (nuevo)"))
    par = t2[t2.alpha % 2 == 0]; imp = t2[t2.alpha % 2 != 0]
    print("\n   media pares  : %.4f -> %.4f  (%+.1f%%)"
          % (par.s_prod.mean(), par.s_new.mean(),
             100 * (par.s_new.mean() - par.s_prod.mean()) / par.s_prod.mean()))
    print("   media impares: %.4f -> %.4f  (%+.1f%%)"
          % (imp.s_prod.mean(), imp.s_new.mean(),
             100 * (imp.s_new.mean() - imp.s_prod.mean()) / imp.s_prod.mean()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
