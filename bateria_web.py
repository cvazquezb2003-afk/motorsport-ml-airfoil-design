"""BATERIA WEB — ETAPA A: las 40 propuestas EXACTAMENTE como las entrega la aplicacion.

Las baterias anteriores validan el buscador con el ANGULO FIJADO. La web hace dos cosas
mas al entregar: promedia J sobre una BANDA de angulos y REDONDEA el borde de salida al
multiplo de 0,05 mm. Esas dos diferencias estaban declaradas en el README como no
medidas. Esto las mide.

    python bateria_web.py             # ~2 min, sin CATIA
    python bateria_web.py --limite N  # solo los N primeros

--- LA BANDA DE CADA CASO ---
Solo hay TRES bandas en el sistema (entrada_dashboard.RANGO): low 0-5, medium 5-9,
high 9-14. Los 61 circuitos se reparten entre esas tres, asi que elegir circuito o
elegir nivel da la misma banda: el optimo depende de (banda, cuerda, velocidad).
A cada uno de los 40 casos se le asigna la banda que CONTIENE su |alpha|. Los angulos
presentes son 2,4,6,8,10,12 y ninguno cae en 5 ni en 9 —los unicos valores frontera—,
asi que no hay nada que decidir a mano.

OJO: no se puede reutilizar el modo "angulo exacto" de la web para esto. En ese modo el
endpoint optimiza a ANGULO UNICO y la banda implicita solo sirve para pintar la franja.
El promediado de banda solo ocurre en modo circuito y modo nivel.

--- LA SECUENCIA ES LA DEL ENDPOINT, EN SU ORDEN ---
    optimizar(cuerda, -hi, -lo, v)  ->  redondea_te  ->  metricas_banda
Recalcular con `metricas_banda` sobre la geometria YA REDONDEADA no es un detalle: es lo
que hace dashboard_app.py:1761. Usar el LD que devuelve `optimizar()` seria comparar
contra un numero que la web nunca ensena.

--- QUE NO SE PISA ---
Ficheros propios con prefijo `bateria_web_` y configuraciones `web_*.json`. Las baterias
de DE (`dsf_*`, `bateria_densif_*`) y de Sobol (`sbl_*`, `bateria_sobol_*`) quedan
intactas: son la evidencia contra la que esto se compara.
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
from optimo_geom import redondea_te, metricas_banda
from entrada_dashboard import RANGO

CASOS_REF = os.path.join(BASE, "bateria_densif_k2_resultados.json")
CHORD_ANGLE = 350.0
CLAVES = list(SHAPE) + ["chord_angle_deg"]


def banda_de(alpha_abs):
    """La banda que CONTIENE |alpha|. RANGO = low (0,5), medium (5,9), high (9,14)."""
    for nombre, (lo, hi) in RANGO.items():
        if lo <= alpha_abs < hi or (hi == 14 and alpha_abs == 14):
            return nombre, lo, hi
    raise ValueError("alpha fuera de las bandas: %s" % alpha_abs)


def config(shape, chord):
    out = {k: float(shape[k]) for k in SHAPE}
    out["chord_length_mm"] = float(chord)
    out["chord_angle_deg"] = CHORD_ANGLE
    return {k: out[k] for k in CLAVES}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--limite", type=int, default=None)
    args = ap.parse_args()

    casos = sorted(json.load(open(CASOS_REF, encoding="utf-8")), key=lambda c: c["caso"])
    if args.limite:
        casos = casos[:args.limite]

    print("=" * 104)
    print("BATERIA WEB — ETAPA A (banda promediada + TE redondeado, como entrega la app)")
    print("=" * 104)
    print("   condiciones : %s (mismas cuerda/velocidad que las otras baterias)"
          % os.path.basename(CASOS_REF))
    print("   casos       : %d" % len(casos))
    print()
    print("   %-5s %6s %5s %6s | %-7s %-8s %-4s | %9s %9s %8s %6s"
          % ("caso", "cuerda", "vel", "a_orig", "banda", "|a| band", "nang",
             "LD_banda", "LD_a_rec", "sigma", "a_rec"))
    print("   " + "-" * 100)

    idx = []
    t0 = time.perf_counter()
    for c in casos:
        ch, v = float(c["cuerda"]), float(c["vel"])
        aabs = abs(float(c["alpha"]))
        nombre, lo, hi = banda_de(aabs)

        # --- la secuencia del endpoint, en su orden ---
        r = S.optimizar(ch, -hi, -lo, v_kmh=v)
        te_exacto = float(r["shape_params"]["trailing_edge_thickness_mm"])
        sp = redondea_te(r["shape_params"])
        m = metricas_banda(sp, lo, hi, vel=v)

        angulos = [float(a) for a in S._grid_angulos(-hi, -lo, 1.0)]
        x = np.array([[float(sp[k]) for k in SHAPE]])
        ld_por_ang, sd_por_ang = {}, {}
        for a in angulos:
            X = S._arma_X(x, a, v)
            mu, sd = S._ens_stats(X)
            ld_por_ang["%.0f" % a] = float(S._LD.predict(X)[0])
            sd_por_ang["%.0f" % a] = float(sd[0])
        a_rec = float(m["alpha_rec_abs"])

        nombre_json = "web_%d_c%d_v%d_b%d-%d.json" % (c["caso"], int(ch), int(v), lo, hi)
        json.dump({"user_params": config(sp, ch),
                   "velocidad_kmh": c["vel"],
                   "alphas": [-int(round(a_rec))]},          # _ld_real_tereal mide este
                  open(os.path.join(BASE, nombre_json), "w", encoding="utf-8"),
                  indent=1, ensure_ascii=False)

        idx.append({
            "caso": c["caso"], "cuerda": c["cuerda"], "vel": c["vel"],
            "alpha_orig": c["alpha"], "banda": nombre, "banda_lo": lo, "banda_hi": hi,
            "angulos": angulos, "n_angulos": len(angulos),
            "Re": int(round(S._reynolds(ch, v))), "json": nombre_json,
            "LD_pred_banda": float(m["LD"]), "CD_pred_banda": float(m["CD"]),
            "sigma_banda": float(m["sigma"]), "alpha_rec_abs": a_rec,
            "LD_pred_por_angulo": ld_por_ang, "sigma_por_angulo": sd_por_ang,
            "LD_pred_en_rec": ld_por_ang["%.0f" % -a_rec],
            "te_exacto_mm": round(te_exacto, 3),
            "te_entregado_mm": sp["trailing_edge_thickness_mm"]})

        print("   %-5s %6.0f %5.0f %6.0f | %-7s %-8s %-4d | %9.3f %9.3f %8.4f %6.1f"
              % (c["caso"], ch, v, c["alpha"], nombre, "%d-%d" % (lo, hi), len(angulos),
                 m["LD"], idx[-1]["LD_pred_en_rec"], m["sigma"], a_rec))

    # coherencia interna: la media por angulo debe reproducir metricas_banda
    peor = max(abs(np.mean(list(e["LD_pred_por_angulo"].values())) - e["LD_pred_banda"])
               for e in idx)
    print()
    print("   coherencia media(por angulo) vs metricas_banda: dif max %.3g" % peor)

    destino = os.path.join(BASE, "bateria_web_index.json")
    json.dump(idx, open(destino, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print("[OK] %s  (%d casos)" % (os.path.basename(destino), len(idx)))
    print("[OK] %d configuraciones web_*.json" % len(idx))
    print("[OK] %.1f s" % (time.perf_counter() - t0))
    print("\nSiguiente: python bateria_web_etapaB.py --dry-run")
    return 0


if __name__ == "__main__":
    sys.exit(main())
