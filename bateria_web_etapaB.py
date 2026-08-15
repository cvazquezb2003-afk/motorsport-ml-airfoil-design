"""BATERIA WEB — ETAPA B: verifica en CATIA + XFOIL las 40 propuestas de la app.

    python bateria_web_etapaB.py --dry-run   # sin CATIA: valida indices y estructura
    python bateria_web_etapaB.py             # ~30 min, REQUIERE CATIA ABIERTO
    python bateria_web_etapaB.py --limite N

--- POR QUE NO SE USA EL ENVOLTORIO DE bateria_densif_etapaB ---
Su `valida()` exige DOS indices de 40 casos (k=0 y k=2). Aqui solo hay k=2, que es lo que
la web despliega (K_DEFAULT = 2.0); un arm k=0 no validaria nada y costaria el doble de
CATIA, que es el recurso que se acaba. A cambio se pierden sus comprobaciones
estructurales, asi que se REPONEN aqui una a una (ver `valida`).

Lo que NO se reimplementa es la medicion: `_ld_real_tereal` y `_catia_cerrar_parts` se
importan de bateria_tereal y se llaman sin tocarlas, igual que hace la etapa B densif.

--- COMO SE MIDE UNA BANDA SIN RECONSTRUIR 6 VECES ---
`_ld_real_tereal` solo mide `cfg["alphas"][0]`: no sabe de bandas. Pero deja el .dat
convertido en SCRATCH/trbat.dat. Asi que se la llama con el ANGULO RECOMENDADO —devuelve
la cifra accionable— y despues se barre el RESTO de la banda con `xfoil_sweep` sobre ese
mismo .dat. Una sola construccion de CATIA por geometria y la cadena de medicion intacta.

Cada angulo se mide de las DOS formas: ANGULO UNICO —`xfoil_sweep(dat, re, [a])`, la
convencion de todas las baterias anteriores— y MARCHA DE PASO 1 desde 0, que es el
regimen con el que se genero el dataset.

--- POR QUE LAS DOS ---
El caso 1 de la prueba corta dio |L/D| = 90,39 a -6 grados con angulo unico, dentro de una
curva por lo demas suave (-5: 59,33 · -7: 60,85). Con marcha de paso 1 y con marcha de
paso 2 da 60,29, que es el valor que encaja. Es la rama espuria del caso 10 otra vez: una
convergencia falsa que XFOIL solo encuentra cuando salta directo al angulo sin marchar.
Es determinista, asi que repetir la medida NO la detecta; solo cambiar el camino la
detecta.

Con 211 puntos no hay forma de saber cuales estan contaminados sin medirlos de las dos
maneras, y el coste es una corrida de XFOIL mas por caso (la marcha da todos los angulos
de golpe): unos 4 minutos en total, cero CATIA. Asi el artefacto queda medido y contado en
vez de escondido.

Las cifras de las baterias anteriores NO estan expuestas: ya se re-corrieron sus 76
geometrias con las dos marchas (1 de 38 sensible en densif —el caso 10, ya corregido— y
0 de 38 en Sobol), y el 2,83 % y el 2,09 % salen identicos al decimal.

--- CONVERGENCIA ---
Si algun angulo de una banda no converge, se registra como None y el caso se marca
INCOMPLETO. La media de banda medida se calcula SOLO sobre los casos completos; los
incompletos se reportan aparte, nunca promediados en silencio sobre un subconjunto.

--- REANUDABLE ---
Vuelca el JSON tras CADA caso y salta los que ya tengan medicion.
"""
import argparse
import json
import os
import shutil
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

IDX = os.path.join(BASE, "bateria_web_index.json")
RES = os.path.join(BASE, "bateria_web_resultados.json")
STARS = os.path.join(BASE, "bateria_web_stars")
REF_JULIO = os.path.join(BASE, "bateria_tereal_k0_resultados.json")


def mide_banda(dat, re, angulos, a_rec, ld_rec):
    """Mide la banda de las DOS formas sobre un .dat YA construido.

    - angulo unico: una corrida de XFOIL por angulo, como todas las baterias anteriores.
      El angulo recomendado no se remide: se reutiliza el que devolvio _ld_real_tereal,
      que es exactamente esa misma llamada.
    - marcha paso 1: UNA sola corrida 0 -> angulo mas profundo, que devuelve todos los
      angulos de la banda de golpe. Es el regimen con el que se genero el dataset.

    Devuelve (dict_unico, dict_marcha) con clave "%d" por angulo y None si no converge.
    """
    from piloto_tereal import xfoil_sweep

    ang = [int(round(a)) for a in angulos]
    unico = {}
    for ai in ang:
        if ai == a_rec:
            unico["%d" % ai] = ld_rec
            continue
        pol = xfoil_sweep(dat, re, [ai])
        cl_cd = pol.get(ai)
        unico["%d" % ai] = (cl_cd[0] / cl_cd[1]) if (cl_cd and cl_cd[1]) else None

    marcha = {}
    pol = xfoil_sweep(dat, re, list(range(0, min(ang) - 1, -1)))
    for ai in ang:
        cl_cd = pol.get(ai)
        marcha["%d" % ai] = (cl_cd[0] / cl_cd[1]) if (cl_cd and cl_cd[1]) else None
    return unico, marcha


def valida(idx, verbose=True):
    """Las comprobaciones de valida() de la etapa B densif, repuestas para un solo arm."""
    p = []
    if len(idx) != 40:
        p.append("el indice no tiene 40 casos (%d)" % len(idx))
    if {c["caso"] for c in idx} != set(range(1, 41)):
        p.append("los casos no son 1..40")
    faltan = [c["json"] for c in idx if not os.path.exists(os.path.join(BASE, c["json"]))]
    if faltan:
        p.append("faltan %d configuraciones: %s" % (len(faltan), faltan[:5]))
    for c in idx:
        ruta = os.path.join(BASE, c["json"])
        if not os.path.exists(ruta):
            continue
        d = json.load(open(ruta, encoding="utf-8"))
        up = d.get("user_params", {})
        if len(up) != 8:
            p.append("%s: user_params tiene %d claves (esperadas 8)" % (c["json"], len(up)))
        if d.get("velocidad_kmh") != c["vel"]:
            p.append("%s: velocidad no cuadra con el indice" % c["json"])
        if d.get("alphas") != [-int(round(c["alpha_rec_abs"]))]:
            p.append("%s: alphas no es el angulo recomendado" % c["json"])
        if abs(float(up.get("chord_length_mm", -1)) - c["cuerda"]) > 0.5:
            p.append("%s: cuerda no cuadra con el indice" % c["json"])
        te = float(up["trailing_edge_thickness_mm"])
        if abs(round(te / 0.05) * 0.05 - te) > 1e-9:
            p.append("%s: el TE NO esta redondeado a 0,05 (%r)" % (c["json"], te))
        if not (c["banda_lo"] <= c["alpha_rec_abs"] <= c["banda_hi"]):
            p.append("%s: el angulo recomendado cae fuera de su banda" % c["json"])
    # cuerda y velocidad deben ser las de julio; el ANGULO cambia a proposito (es banda)
    ref = {c["caso"]: (c["cuerda"], c["vel"])
           for c in json.load(open(REF_JULIO, encoding="utf-8"))}
    dif = [c["caso"] for c in idx if ref.get(c["caso"]) != (c["cuerda"], c["vel"])]
    if dif:
        p.append("casos con cuerda/velocidad distintas a julio: %s" % dif)
    if verbose:
        print("   casos en el indice            : %d" % len(idx))
        print("   configuraciones presentes     : %d de %d" % (len(idx) - len(faltan), len(idx)))
        print("   TE redondeado a 0,05 en todas : %s"
              % ("SI" if not any("TE NO esta redondeado" in x for x in p) else "NO"))
        print("   cuerda/velocidad como julio   : %s" % ("SI" if not dif else "NO -> %s" % dif))
        print("   -> %s" % ("TODO CORRECTO" if not p else "PROBLEMAS:"))
        for x in p:
            print("      - %s" % x)
    return p


def _previo(idx):
    if not os.path.exists(RES):
        return {c["caso"]: dict(c) for c in idx}, 0
    hechos = {c["caso"]: c for c in json.load(open(RES, encoding="utf-8"))}
    out, n = {}, 0
    for c in idx:
        if c["caso"] in hechos and hechos[c["caso"]].get("LD_real_marcha"):
            out[c["caso"]] = hechos[c["caso"]]; n += 1
        else:
            out[c["caso"]] = dict(c)
    return out, n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limite", type=int, default=None)
    args = ap.parse_args()

    idx = sorted(json.load(open(IDX, encoding="utf-8")), key=lambda c: c["caso"])
    print("=" * 100)
    print("BATERIA WEB — ETAPA B (%d geometrias en CATIA + XFOIL, banda + TE redondeado)"
          % len(idx))
    print("=" * 100)
    problemas = valida(idx)
    estado, ya = _previo(idx)

    if args.dry_run:
        ang = sum(c["n_angulos"] for c in idx)
        print("\n[DRY-RUN] no se toca CATIA. Resultados irian a:")
        print("   %s" % os.path.basename(RES))
        print("   .dat -> %s" % os.path.basename(STARS))
        print("[DRY-RUN] ya hechos: %d de %d" % (ya, len(idx)))
        print("[DRY-RUN] pendientes de CATIA: %d geometrias, %d corridas de XFOIL"
              % (len(idx) - ya, ang))
        return 0 if not problemas else 1

    if problemas:
        print("\n[ABORTA] corrige los problemas antes de gastar CATIA.")
        return 1

    from bateria_tereal import _ld_real_tereal, _catia_cerrar_parts, reynolds
    from piloto_tereal import xfoil_sweep, SCRATCH
    import ctypes
    ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)
    print("[SUSPENSION] bloqueada mientras corre")
    print("[AVISO] no toques raton ni teclado; CATIA debe quedar en primer plano.\n")
    os.makedirs(STARS, exist_ok=True)

    pend = [c for c in idx if not estado[c["caso"]].get("LD_real_marcha")]
    if args.limite:
        pend = pend[:args.limite]

    try:
        for c in pend:
            e = estado[c["caso"]]
            cfg = json.load(open(os.path.join(BASE, c["json"]), encoding="utf-8"))
            a_rec = -int(round(c["alpha_rec_abs"]))
            print("#### CASO %d  c%d v%d  banda %d-%d  a_rec %d | LD_banda=%.2f"
                  % (c["caso"], c["cuerda"], c["vel"], c["banda_lo"], c["banda_hi"],
                     a_rec, c["LD_pred_banda"]))
            sys.stdout.flush()

            ld_rec = _ld_real_tereal(cfg)               # CATIA + XFOIL, sin tocar
            dat = os.path.join(SCRATCH, "trbat.dat")
            unico = marcha = None
            if ld_rec is not None and os.path.exists(dat):
                re = int(round(reynolds(float(c["cuerda"]), float(c["vel"]))))
                unico, marcha = mide_banda(dat, re, c["angulos"], a_rec, ld_rec)
                shutil.copy2(dat, os.path.join(
                    STARS, "caso%d_c%d_v%d_b%d-%d.dat"
                    % (c["caso"], c["cuerda"], c["vel"], c["banda_lo"], c["banda_hi"])))

            e["LD_real_en_rec_unico"] = ld_rec
            e["LD_real_en_rec_marcha"] = (marcha or {}).get("%d" % a_rec)
            e["LD_real_unico"] = unico
            e["LD_real_marcha"] = marcha
            e["completo"] = bool(unico) and bool(marcha) and \
                all(v is not None for v in unico.values()) and \
                all(v is not None for v in marcha.values())
            nu = sum(1 for v in (unico or {}).values() if v is not None)
            nm = sum(1 for v in (marcha or {}).values() if v is not None)
            dif = [k for k in (unico or {})
                   if unico[k] is not None and marcha.get(k) is not None
                   and abs(abs(unico[k]) - abs(marcha[k])) > 0.5]
            print("   a_rec unico %s / marcha %s | convergen %d y %d de %d | difieren %d | %s"
                  % ("%.2f" % abs(ld_rec) if ld_rec else "NO",
                     "%.2f" % abs(e["LD_real_en_rec_marcha"]) if e["LD_real_en_rec_marcha"] else "NO",
                     nu, nm, c["n_angulos"], len(dif),
                     "COMPLETO" if e["completo"] else "INCOMPLETO"))
            sys.stdout.flush()
            json.dump([estado[k["caso"]] for k in idx],
                      open(RES, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
            _catia_cerrar_parts()
    finally:
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
        print("[SUSPENSION] liberada")

    print("\n[OK] resultados -> %s" % os.path.basename(RES))
    print("[OK] .dat -> %s" % os.path.basename(STARS))
    print("[OK] baterias anteriores y produccion NO tocadas.")
    print("\nLas cifras se calculan aparte con cifras_web.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
