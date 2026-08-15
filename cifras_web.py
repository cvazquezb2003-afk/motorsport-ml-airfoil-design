"""Cifras de la BATERIA WEB, calculadas aparte desde el JSON de resultados.

Mide lo que la aplicacion entrega de verdad: banda de angulos promediada y borde de salida
redondeado a 0,05 mm. Cada angulo esta medido de DOS formas (angulo unico y marcha de paso
1) porque XFOIL tiene una rama espuria que solo aparece al saltar directo al angulo.

    python cifras_web.py

Solo lectura.

--- QUE SE PROMEDIA Y QUE NO ---
La media de banda medida se calcula SOLO sobre los casos con la banda COMPLETA en el
metodo correspondiente. Un caso al que le falta un angulo no entra en la media: promediar
sobre un subconjunto y llamarlo "media de banda" seria comparar contra otra cosa. Los
incompletos se cuentan y se listan aparte.
"""
import json
import os
import sys
from collections import Counter

import numpy as np

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

RES = os.path.join(BASE, "bateria_web_resultados.json")
UMBRAL = 0.5          # |L/D| de diferencia para considerar un punto contaminado


def err(pred, real):
    return 100 * abs(abs(pred) - abs(real)) / abs(real)


def main():
    d = json.load(open(RES, encoding="utf-8"))
    con = [c for c in d if c.get("LD_real_marcha")]

    print("#" * 78)
    print("BATERIA WEB — lo que la aplicacion entrega (banda promediada + TE redondeado)")
    print("#" * 78)
    print("   casos construidos en CATIA : %d de %d" % (len(con), len(d)))

    # ── 1. puntos: los dos metodos ───────────────────────────────────────────
    pts, difs = 0, []
    nc = {"unico": 0, "marcha": 0}
    for c in con:
        for a, u in c["LD_real_unico"].items():
            m = c["LD_real_marcha"].get(a)
            if u is None:
                nc["unico"] += 1
            if m is None:
                nc["marcha"] += 1
            if u is None or m is None:
                continue
            pts += 1
            g = abs(abs(u) - abs(m))
            if g > UMBRAL:
                difs.append(dict(caso=c["caso"], ang=int(a), cuerda=c["cuerda"],
                                 vel=c["vel"], banda=c["banda"],
                                 uni=abs(u), mar=abs(m), dif=g))

    print()
    print("=" * 78)
    print("2. LOS DOS METODOS DE MEDIDA")
    print("=" * 78)
    print("   puntos angulo-geometria comparables : %d" % pts)
    print("   angulos que NO convergen  unico %d | marcha %d" % (nc["unico"], nc["marcha"]))
    print("   puntos que DIFIEREN (>%.1f) : %d de %d  (%.1f %%)"
          % (UMBRAL, len(difs), pts, 100 * len(difs) / max(pts, 1)))
    if difs:
        g = np.array([x["dif"] for x in difs])
        print("   magnitud de la diferencia: mediana %.2f  min %.2f  max %.2f"
              % (np.median(g), g.min(), g.max()))
        print()
        print("   %-5s %-6s %6s %5s %-7s %9s %9s %8s"
              % ("caso", "angulo", "cuerda", "vel", "banda", "unico", "marcha", "dif"))
        for x in sorted(difs, key=lambda y: -y["dif"]):
            print("   %-5d %-6d %6d %5d %-7s %9.2f %9.2f %8.2f"
                  % (x["caso"], x["ang"], x["cuerda"], x["vel"], x["banda"],
                     x["uni"], x["mar"], x["dif"]))
        print()
        print("   ¿el artefacto tiene patron?")
        for campo, etq in (("ang", "angulo"), ("cuerda", "cuerda"),
                           ("vel", "velocidad"), ("banda", "banda")):
            c2 = Counter(x[campo] for x in difs)
            tot = Counter(x[campo] for x in
                          [dict(ang=int(a), cuerda=c["cuerda"], vel=c["vel"], banda=c["banda"])
                           for c in con for a in c["LD_real_unico"]])
            piezas = ["%s: %d/%d" % (k, v, tot[k]) for k, v in sorted(c2.items(), key=lambda z: str(z[0]))]
            print("     %-10s %s" % (etq, "  ".join(piezas)))
        print("     (x/y = puntos contaminados / puntos medidos con ese valor)")

    # ── 2. cifra titular y accionable, por metodo ────────────────────────────
    print()
    print("=" * 78)
    print("3. LAS CIFRAS")
    print("=" * 78)
    for metodo, clave, krec in (("ANGULO UNICO", "LD_real_unico", "LD_real_en_rec_unico"),
                                ("MARCHA PASO 1", "LD_real_marcha", "LD_real_en_rec_marcha")):
        comp = [c for c in con if c[clave] and all(v is not None for v in c[clave].values())]
        e_band = np.array([err(c["LD_pred_banda"],
                               np.mean([abs(v) for v in c[clave].values()])) for c in comp])
        rec = [c for c in con if c.get(krec) is not None]
        e_rec = np.array([err(c["LD_pred_en_rec"], c[krec]) for c in rec])
        print()
        print("   --- %s ---" % metodo)
        print("     bandas COMPLETAS : %d de %d" % (len(comp), len(con)))
        print("     TITULAR  (media de banda medida vs LD_predicho de la app)")
        print("       media %.2f %%   mediana %.2f %%   max %.2f %%   (n=%d)"
              % (e_band.mean(), np.median(e_band), e_band.max(), len(e_band)))
        print("     ACCIONABLE  (en alpha_recomendado)")
        print("       media %.2f %%   mediana %.2f %%   max %.2f %%   (n=%d)"
              % (e_rec.mean(), np.median(e_rec), e_rec.max(), len(e_rec)))
        peor = comp[int(e_band.argmax())]
        print("     peor caso de banda: %d (c%d v%d %s)"
              % (peor["caso"], peor["cuerda"], peor["vel"], peor["banda"]))

    # ── 3. incompletos ───────────────────────────────────────────────────────
    inc = [c for c in con if not c.get("completo")]
    print()
    print("=" * 78)
    print("4. CASOS INCOMPLETOS (fuera de la media de banda, no promediados en silencio)")
    print("=" * 78)
    print("   %d de %d casos" % (len(inc), len(con)))
    for c in inc:
        fu = [a for a, v in c["LD_real_unico"].items() if v is None]
        fm = [a for a, v in c["LD_real_marcha"].items() if v is None]
        print("     caso %-3d c%-4d v%-4d %-7s | sin converger  unico %s  marcha %s"
              % (c["caso"], c["cuerda"], c["vel"], c["banda"], fu or "-", fm or "-"))

    # ── 4. contraste con la bateria de angulo fijo ───────────────────────────
    print()
    print("=" * 78)
    print("5. CONTRASTE CON EL 2,09 % DE ANGULO FIJO (bateria Sobol)")
    print("=" * 78)
    s = [c for c in json.load(open(os.path.join(BASE, "bateria_sobol_k2_resultados.json"),
                                   encoding="utf-8")) if c.get("LD_real") is not None]
    es = np.array([err(c["LD_pred"], c["LD_real"]) for c in s])
    print("   %-46s %8s %8s %8s" % ("", "media", "mediana", "max"))
    print("   " + "-" * 74)
    print("   %-46s %7.2f%% %7.2f%% %7.2f%%"
          % ("Sobol, angulo fijado, TE sin redondear (n=%d)" % len(es),
             es.mean(), np.median(es), es.max()))
    for metodo, clave in (("marcha", "LD_real_marcha"), ("unico", "LD_real_unico")):
        comp = [c for c in con if c[clave] and all(v is not None for v in c[clave].values())]
        e = np.array([err(c["LD_pred_banda"],
                          np.mean([abs(v) for v in c[clave].values()])) for c in comp])
        print("   %-46s %7.2f%% %7.2f%% %7.2f%%"
              % ("Web, banda + TE redondeado, %s (n=%d)" % (metodo, len(e)),
                 e.mean(), np.median(e), e.max()))


if __name__ == "__main__":
    main()
