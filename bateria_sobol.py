"""BATERIA SOBOL — ETAPA A: las mismas 40 condiciones, pero propuestas por el buscador
QUE EJECUTA LA WEB. Portable, sin CATIA.

`comprueba_buscador.py` demostro que el barrido de Sobol de `inversa_service` pierde contra
la differential evolution que produjo el 2,8 % publicado, en 40 casos de 40, y que aterriza
donde el ensemble esta un 44 % menos seguro. Eso deja el 2,8 % atribuido a las geometrias
de DE y sin reclamar para lo que la app devuelve.

Este script genera las propuestas del OTRO lado de esa comparacion, para que la Etapa B
pueda construirlas en CATIA y medirlas en XFOIL. El resultado sera la cifra real de lo que
la web entrega, no una heredada.

    python bateria_sobol.py             # ~2 min, sin CATIA
    python bateria_sobol.py --limite N  # solo los N primeros (prueba)

--- QUE SE CONSERVA IGUAL Y POR QUE ---
Las MISMAS 40 condiciones (cuerda, velocidad, angulo), leidas de
`bateria_densif_k2_resultados.json` para que no haya forma de que difieran. Mismos modelos,
mismo ensemble, mismos bounds p5-p95, mismo k=2. Lo UNICO que cambia es el buscador: Sobol
32.768 + argmin en vez de DE. Si cambiase algo mas, la comparacion contra el 2,8 % dejaria
de medir lo que dice medir.

--- ANGULO FIJADO ---
Se llama `optimizar()` con `a_from == a_to`, que degenera la banda a UN angulo. La web
promedia J sobre una banda; la bateria optimizaba a angulo fijo. Fijar el angulo cancela
esa segunda diferencia y deja el buscador como unica variable, igual que en
`comprueba_buscador.py`.

--- EL TE NO SE REDONDEA, A PROPOSITO ---
El endpoint aplica `redondea_te` (multiplo de 0,05 mm) como paso de ENTREGA, despues de
optimizar. Aqui no se aplica, porque las 40 geometrias de DE tampoco lo llevan (sus TE son
valores crudos: 2.406605, 1.223151...) y el redondeo es un paso posterior identico en ambos
caminos. Incluirlo solo en un lado metería una segunda diferencia en una comparacion que
existe para aislar una. La perturbacion que se omite es de +-0,025 mm.

--- OJO CON k=0 ---
Se generan k=0 y k=2 porque la Etapa B exige ambos indices. Pero el k=0 de la bateria de DE
minimizaba el MODELO LD de produccion (`prod.predict`), mientras que `optimizar(k=0)`
minimiza la MEDIA DEL ENSEMBLE. No es el mismo objetivo, asi que **el k=0 de aqui no es
comparable con el 6,9 % de la bateria densif**. El que si es comparable —mismo objetivo
`mu + 2*sigma`, mismos bounds, mismos modelos— es k=2, que es justamente el del 2,8 %.

--- QUE NO SE PISA ---
Ficheros propios con prefijo `bateria_sobol_` y configuraciones `sbl_*.json`. Los
`bateria_densif_*` y `dsf_*` de la tirada con DE quedan intactos: son la evidencia contra la
que esto se compara.
"""
import argparse
import json
import os
import sys
import time

import numpy as np

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import inversa_service as S
from feature_utils import SHAPE

CASOS_REF = os.path.join(BASE, "bateria_densif_k2_resultados.json")
CHORD_ANGLE = 350.0            # constante de construccion en CATIA, igual en los 80 dsf
CLAVES = list(SHAPE) + ["chord_angle_deg"]      # el orden EXACTO de los dsf_*.json


def config(shape, chord_mm):
    """user_params en el mismo orden y con las mismas 8 claves que los dsf_*.json.
    La Etapa B valida `len(user_params) == 8`, asi que el orden y el numero importan."""
    out = {}
    for k in SHAPE:
        out[k] = float(shape[k])
    out["chord_length_mm"] = float(chord_mm)
    out["chord_angle_deg"] = CHORD_ANGLE
    return {k: out[k] for k in CLAVES}


def stats(shape, alpha_neg, vel):
    """(LD_pred del modelo de produccion, sigma, mean_ens) en el punto y el angulo."""
    x = np.array([[float(shape[k]) for k in SHAPE]])
    X = S._arma_X(x, alpha_neg, vel)
    mu, sd = S._ens_stats(X)
    return float(S._LD.predict(X)[0]), float(sd[0]), float(mu[0])


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--limite", type=int, default=None,
                    help="generar solo los N primeros casos")
    args = ap.parse_args()

    casos = json.load(open(CASOS_REF, encoding="utf-8"))
    casos = sorted(casos, key=lambda c: c["caso"])
    if args.limite:
        casos = casos[:args.limite]

    print("=" * 104)
    print("BATERIA SOBOL — ETAPA A (buscador de la web: Sobol 32.768 + argmin)")
    print("=" * 104)
    print("   condiciones : %s (las MISMAS que la bateria densif)" % os.path.basename(CASOS_REF))
    print("   casos       : %d" % len(casos))
    print("   modelos     : modelo_LD_inversa_xgb.joblib + ensemble_ld_sigma.joblib")
    print("   bounds      : p5-p95, %d perfiles con cuerda >=%.0f" % (len(S._per), S.CHORD_MIN))
    print("   angulo      : FIJADO (a_from == a_to), 1 angulo por caso")
    print("   TE          : SIN redondear (como los dsf_*.json de DE)")
    print()

    indices = {"k0": [], "k2": []}
    t0 = time.perf_counter()
    print("   %-5s %6s %5s %6s | %-3s %11s %9s %11s | %s"
          % ("caso", "cuerda", "vel", "alpha", "k", "LD_pred", "sigma", "mean_ens", "config"))
    print("   " + "-" * 98)

    for c in casos:
        ch, v, a = float(c["cuerda"]), float(c["vel"]), -abs(float(c["alpha"]))
        for etiqueta, k in (("k0", 0.0), ("k2", 2.0)):
            r = S.optimizar(ch, a, a, k=k, v_kmh=v)
            sp = r["shape_params"]
            ld, sd, mu = stats(sp, a, v)

            nombre = "sbl_%s_%d_c%d_v%d_a%d.json" % (etiqueta, c["caso"], int(ch),
                                                     int(v), int(abs(a)))
            json.dump({"user_params": config(sp, ch),
                       "velocidad_kmh": c["vel"],
                       "alphas": [c["alpha"]]},
                      open(os.path.join(BASE, nombre), "w", encoding="utf-8"),
                      indent=1, ensure_ascii=False)

            indices[etiqueta].append({
                "caso": c["caso"], "cuerda": c["cuerda"], "vel": c["vel"],
                "alpha": c["alpha"], "Re": int(round(S._reynolds(ch, v))),
                "json": nombre, "LD_pred": ld, "sigma": sd, "mean_ens": mu})

            print("   %-5s %6.0f %5.0f %6.0f | %-3s %11.5f %9.5f %11.5f | %s"
                  % (c["caso"], ch, v, a, etiqueta, ld, sd, mu, nombre))

    for etiqueta in ("k0", "k2"):
        destino = os.path.join(BASE, "bateria_sobol_%s_index.json" % etiqueta)
        json.dump(indices[etiqueta], open(destino, "w", encoding="utf-8"),
                  indent=1, ensure_ascii=False)
        print("\n[OK] %s  (%d casos)" % (os.path.basename(destino), len(indices[etiqueta])))

    print("[OK] %d configuraciones sbl_*.json" % (2 * len(casos)))
    print("[OK] %.1f s" % (time.perf_counter() - t0))
    print("\nSiguiente: python bateria_sobol_etapaB.py --dry-run")
    return 0


if __name__ == "__main__":
    sys.exit(main())
