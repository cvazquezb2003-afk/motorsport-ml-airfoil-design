"""
BATERIA DENSIF — ETAPA B: verificacion de las 80 propuestas en CATIA + XFOIL.

Lee las propuestas de la ETAPA A densif:
    bateria_densif_k0_index.json   (40 casos)
    bateria_densif_k2_index.json   (40 casos)
y verifica cada una: CATIA (steps 1-3) -> genera_tereal (.dat TE romo) -> XFOIL,
para obtener el L/D REAL y contrastarlo con el predicho.

    python bateria_densif_etapaB.py            # ~2 h, REQUIERE CATIA ABIERTO
    python bateria_densif_etapaB.py --dry-run  # sin CATIA: valida indices y estructura

--- QUE NO CAMBIA RESPECTO A bateria_tereal.etapaB ---
La LOGICA DE VERIFICACION es la misma, importada literalmente de ese modulo:
`_ld_real_tereal` (los tres subprocess de CATIA + genera_tereal + xfoil_sweep) y
`_catia_cerrar_parts`. NO se reimplementa aqui. Lo unico que cambia es DE DONDE se leen
las propuestas y ADONDE se escriben los resultados. Si la verificacion difiriera aunque
fuese en un timeout, la comparacion contra el 3.8% de julio dejaria de ser valida.

--- QUE NO SE PISA ---
Resultados en `bateria_densif_k0/k2_resultados.json` y .dat estrella en
`bateria_densif_stars/`. Los ficheros de julio (`bateria_tereal_*`, `tr_*`, `tre_*`) y
produccion no se tocan: este script solo LEE `bateria_tereal_k0_resultados.json` para la
linea de referencia de la tabla final.

--- REANUDABLE ---
Vuelca el JSON de resultados tras CADA geometria y salta las que ya tengan LD_real.
Con ~2 h de CATIA por delante y el portatil contado, un corte cuesta como mucho un caso.

--- SUSPENSION ---
Bloquea la suspension del equipo mientras corre (SetThreadExecutionState). Es una
peticion POR PROCESO, no cambia la configuracion de energia de Windows y se libera sola
al terminar. La tirada anterior de la etapa A se corto justo por una suspension.
"""
import os, sys, json, ctypes, shutil, argparse
import numpy as np

BASE = os.path.dirname(os.path.abspath(__file__))
IDX = {"k0": os.path.join(BASE, "bateria_densif_k0_index.json"),
       "k2": os.path.join(BASE, "bateria_densif_k2_index.json")}
RES = {"k0": os.path.join(BASE, "bateria_densif_k0_resultados.json"),
       "k2": os.path.join(BASE, "bateria_densif_k2_resultados.json")}
STARS = os.path.join(BASE, "bateria_densif_stars")
REF_JULIO = {"k0": os.path.join(BASE, "bateria_tereal_k0_resultados.json"),
             "k2": os.path.join(BASE, "bateria_tereal_k2_resultados.json")}
# cifras publicadas de la bateria de julio, para la linea de contraste
REF_ERR = {"k0": 21.5, "k2": 3.8}

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001


def bloquea_suspension(activar=True):
    """Impide (o libera) la suspension del equipo. Peticion por proceso; no toca las
    opciones de energia de Windows y caduca al terminar el proceso."""
    try:
        flags = (ES_CONTINUOUS | ES_SYSTEM_REQUIRED) if activar else ES_CONTINUOUS
        return ctypes.windll.kernel32.SetThreadExecutionState(flags) != 0
    except Exception:
        return False


def _fusiona_previo(lista, path_res):
    """REANUDABLE: recupera del JSON de resultados los LD_real ya calculados."""
    if not os.path.exists(path_res):
        return lista, 0
    try:
        prev = {c["caso"]: c for c in json.load(open(path_res, encoding="utf-8"))}
    except Exception:
        return lista, 0
    n = 0
    for c in lista:
        p = prev.get(c["caso"])
        if p is not None and p.get("LD_real") is not None:
            c["LD_real"] = p["LD_real"]
            n += 1
    return lista, n


def carga_indices():
    k0 = json.load(open(IDX["k0"], encoding="utf-8"))
    k2 = json.load(open(IDX["k2"], encoding="utf-8"))
    return sorted(k0, key=lambda c: c["caso"]), sorted(k2, key=lambda c: c["caso"])


def valida(k0, k2, verbose=True):
    """Comprobaciones que SI se pueden hacer sin CATIA."""
    problemas = []
    if len(k0) != 40 or len(k2) != 40:
        problemas.append("los indices no tienen 40 casos (%d / %d)" % (len(k0), len(k2)))
    c0 = {c["caso"] for c in k0}; c2 = {c["caso"] for c in k2}
    if c0 != c2 or c0 != set(range(1, 41)):
        problemas.append("los casos no son 1..40 en ambos indices")
    faltan = [c["json"] for c in k0 + k2 if not os.path.exists(os.path.join(BASE, c["json"]))]
    if faltan:
        problemas.append("faltan %d configuraciones dsf_*.json: %s" % (len(faltan), faltan[:5]))
    for c in k0 + k2:
        p = os.path.join(BASE, c["json"])
        if not os.path.exists(p):
            continue
        d = json.load(open(p, encoding="utf-8"))
        up = d.get("user_params", {})
        if len(up) != 8:
            problemas.append("%s: user_params tiene %d claves (esperadas 8)" % (c["json"], len(up)))
        if d.get("velocidad_kmh") != c["vel"] or d.get("alphas") != [c["alpha"]]:
            problemas.append("%s: velocidad/alpha no cuadran con el indice" % c["json"])
        if abs(float(up.get("chord_length_mm", -1)) - c["cuerda"]) > 0.5:
            problemas.append("%s: cuerda no cuadra con el indice" % c["json"])
    # los casos deben ser LOS MISMOS que la bateria de julio
    ref = {c["caso"]: (c["cuerda"], c["vel"], c["alpha"])
           for c in json.load(open(REF_JULIO["k0"], encoding="utf-8"))}
    dif = [c["caso"] for c in k0 if ref.get(c["caso"]) != (c["cuerda"], c["vel"], c["alpha"])]
    if dif:
        problemas.append("casos con condiciones distintas a julio: %s" % dif)
    if verbose:
        print("   indices: k=0 %d casos | k=2 %d casos" % (len(k0), len(k2)))
        print("   configuraciones dsf_*.json referenciadas y presentes: %d de %d"
              % (len(k0) + len(k2) - len(faltan), len(k0) + len(k2)))
        print("   condiciones identicas a la bateria de julio: %s"
              % ("SI" if not dif else "NO -> %s" % dif))
        print("   -> %s" % ("TODO CORRECTO" if not problemas else "PROBLEMAS:"))
        for p in problemas:
            print("      - %s" % p)
    return problemas


def tabla_final(k0, k2):
    """Tabla y veredicto, con el MISMO formato que la bateria de julio + la
    comparacion explicita contra sus cifras."""
    def err(c):
        if c.get("LD_real") is None:
            return None
        return abs(c["LD_real"] - c["LD_pred"]) / abs(c["LD_real"]) * 100

    m2 = {c["caso"]: c for c in k2}
    print("\n" + "=" * 100)
    print("TABLA FINAL — BATERIA DENSIF (40 casos, k=0 y k=2)")
    print("=" * 100)
    print(f"{'caso':5s}{'c':>5s}{'v':>5s}{'a':>4s}{'pred_k0':>9s}{'real_k0':>9s}{'err_k0':>8s}"
          f"{'pred_k2':>9s}{'real_k2':>9s}{'err_k2':>8s}{'sigma':>8s}")
    e0s, e2s, signos, n0 = [], [], 0, 0
    for c0 in k0:
        c2 = m2[c0["caso"]]
        e0, e2 = err(c0), err(c2)
        if e0 is not None:
            e0s.append(e0); n0 += 1
            if abs(c0["LD_real"]) < abs(c0["LD_pred"]):
                signos += 1
        if e2 is not None:
            e2s.append(e2)
        r0 = f"{c0['LD_real']:9.2f}" if c0.get("LD_real") is not None else f"{'NOCONV':>9s}"
        r2 = f"{c2['LD_real']:9.2f}" if c2.get("LD_real") is not None else f"{'NOCONV':>9s}"
        s0 = f"{e0:6.0f}%" if e0 is not None else f"{'-':>7s}"
        s2 = f"{e2:6.0f}%" if e2 is not None else f"{'-':>7s}"
        print(f"{c0['caso']:<5d}{c0['cuerda']:>5d}{c0['vel']:>5d}{c0['alpha']:>4d}"
              f"{c0['LD_pred']:9.2f}{r0}{s0}{c2['LD_pred']:9.2f}{r2}{s2}"
              f"{c2.get('sigma', float('nan')):8.2f}")

    m0 = float(np.mean(e0s)) if e0s else float("nan")
    m2m = float(np.mean(e2s)) if e2s else float("nan")
    print("-" * 100)
    print(f"ERROR MEDIO 40 casos  k=0: {m0:5.1f}%  ({len(e0s)}/40 conv)   |   "
          f"k=2: {m2m:5.1f}%  ({len(e2s)}/40 conv)")
    print(f"TEST DE SIGNOS: en {signos}/{n0} casos convergidos el real rinde PEOR que "
          f"la prediccion k=0 (sesgo optimista)")

    print("\n" + "=" * 100)
    print("VEREDICTO — DENSIF vs JULIO (la pregunta: ¿sigue k=2 protegiendo?)")
    print("=" * 100)
    print(f"   {'':22s}{'JULIO':>12s}{'DENSIF':>12s}{'cambio':>12s}")
    print(f"   {'error medio k=0':22s}{REF_ERR['k0']:11.1f}%{m0:11.1f}%"
          f"{m0 - REF_ERR['k0']:+11.1f} pp")
    print(f"   {'error medio k=2':22s}{REF_ERR['k2']:11.1f}%{m2m:11.1f}%"
          f"{m2m - REF_ERR['k2']:+11.1f} pp")
    fac_j = REF_ERR["k0"] / REF_ERR["k2"]
    fac_d = m0 / m2m if m2m else float("nan")
    print(f"   {'factor k0/k2':22s}{fac_j:11.1f}x{fac_d:11.1f}x")
    # k que igualaria el MARGEN ABSOLUTO de penalizacion (k*sigma) de julio, calculado
    # con las sigmas reales de cada tirada, no con constantes cableadas.
    s_new = np.mean([c["sigma"] for c in k2 if "sigma" in c])
    ref2 = json.load(open(REF_JULIO["k2"], encoding="utf-8"))
    s_old = np.mean([c["sigma"] for c in ref2 if "sigma" in c])
    k_sug = 2.0 * s_old / s_new if s_new else float("nan")
    print()
    print(f"   sigma media en el optimo k=2:  julio {s_old:.2f}  ->  densif {s_new:.2f}"
          f"   ({100 * (s_new - s_old) / s_old:+.0f}%)")
    print(f"   margen de penalizacion k*sigma: julio {2 * s_old:.2f}  ->  densif {2 * s_new:.2f}")
    print()
    if m2m <= REF_ERR["k2"] * 1.3:
        print("   -> k=2 SIGUE PROTEGIENDO. El error se mantiene en el orden del 3.8% de")
        print("      julio pese a que sigma cayo. La penalizacion k=2 sigue valiendo y los")
        print("      modelos densif son promocionables sin recalibrar.")
    elif m2m <= REF_ERR["k2"] * 2.5:
        print("   -> k=2 SE HA DEBILITADO. El error de k=2 sube claramente sobre el 3.8%.")
        print(f"      Para recuperar el MISMO margen absoluto de julio haria falta")
        print(f"      k ~ {k_sug:.1f}  (= 2.0 x {s_old:.2f}/{s_new:.2f}). Conviene repetir la")
        print("      bateria con ese k antes de promocionar.")
    else:
        print("   -> k=2 YA NO PROTEGE. El error se acerca al de k=0: la penalizacion")
        print("      dejo de separar. RECALIBRAR k al alza (arranque sugerido: "
              f"k ~ {k_sug:.1f}) antes de promocionar nada.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="valida indices y estructura SIN CATIA")
    ap.add_argument("--limite", type=int, default=None,
                    help="verificar solo los N primeros casos")
    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    k0, k2 = carga_indices()
    print("=" * 100)
    print("BATERIA DENSIF — ETAPA B (%d geometrias en CATIA + XFOIL, TE romo)"
          % (len(k0) + len(k2)))
    print("=" * 100)
    problemas = valida(k0, k2)

    if args.dry_run:
        print("\n[DRY-RUN] no se toca CATIA. Resultados irian a:")
        for t in ("k0", "k2"):
            print("   %s" % os.path.basename(RES[t]))
        print("   .dat estrella -> %s" % os.path.basename(STARS))
        k0d, n0 = _fusiona_previo([dict(c) for c in k0], RES["k0"])
        k2d, n2 = _fusiona_previo([dict(c) for c in k2], RES["k2"])
        print("\n[DRY-RUN] reanudacion: ya hechos k=0 %d/%d | k=2 %d/%d"
              % (n0, len(k0), n2, len(k2)))
        print("[DRY-RUN] pendientes de CATIA: %d geometrias"
              % ((len(k0) - n0) + (len(k2) - n2)))
        return 0 if not problemas else 1

    if problemas:
        print("\n[ABORTA] corrige los problemas antes de gastar CATIA.")
        return 1

    # ---- verificacion real: importa la LOGICA DE JULIO sin reimplementarla ----
    from bateria_tereal import _ld_real_tereal, _catia_cerrar_parts
    from piloto_tereal import SCRATCH
    os.makedirs(STARS, exist_ok=True)

    if args.limite:
        k0, k2 = k0[:args.limite], k2[:args.limite]

    k0, n0 = _fusiona_previo(k0, RES["k0"])
    k2, n2 = _fusiona_previo(k2, RES["k2"])
    if n0 or n2:
        print("\n[REANUDA] ya hechos: k=0 %d/%d | k=2 %d/%d -> se saltan"
              % (n0, len(k0), n2, len(k2)))

    ok_sleep = bloquea_suspension(True)
    print("[SUSPENSION] bloqueada mientras corre: %s" % ("SI" if ok_sleep else "NO se pudo"))
    print("[CATIA] estado inicial:", _catia_cerrar_parts())
    print("[AVISO] no toques raton ni teclado; CATIA debe quedar en primer plano.\n")

    try:
        def verifica(lista, etiqueta, path_res, guardar_dat):
            for c in lista:
                if c.get("LD_real") is not None:
                    print(f"#### CASO {c['caso']} [{etiqueta}] ya hecho "
                          f"(LD_real={c['LD_real']:.2f}) -> salta"); sys.stdout.flush()
                    continue
                cfg = json.load(open(os.path.join(BASE, c["json"]), encoding="utf-8"))
                print(f"\n#### CASO {c['caso']} [{etiqueta}] c{c['cuerda']} v{c['vel']} "
                      f"a{c['alpha']} | LD_pred={c['LD_pred']:.2f}"); sys.stdout.flush()
                c["LD_real"] = _ld_real_tereal(cfg)     # <- LOGICA DE JULIO, sin tocar
                print(f"   LD_real = {c['LD_real']}"); sys.stdout.flush()
                if guardar_dat:
                    src = os.path.join(SCRATCH, "trbat.dat")
                    if os.path.exists(src):
                        shutil.copy2(src, os.path.join(
                            STARS, f"caso{c['caso']}_c{c['cuerda']}_v{c['vel']}"
                                   f"_a{abs(c['alpha'])}.dat"))
                json.dump(lista, open(path_res, "w", encoding="utf-8"), indent=2)
                _catia_cerrar_parts()
            return lista

        k0 = verifica(k0, "k=0", RES["k0"], guardar_dat=False)
        k2 = verifica(k2, "k=2", RES["k2"], guardar_dat=True)
        json.dump(k0, open(RES["k0"], "w", encoding="utf-8"), indent=2)
        json.dump(k2, open(RES["k2"], "w", encoding="utf-8"), indent=2)
        tabla_final(k0, k2)
        print("\n[OK] resultados -> %s | %s"
              % (os.path.basename(RES["k0"]), os.path.basename(RES["k2"])))
        print("[OK] .dat estrella -> %s" % STARS)
        print("[OK] bateria de julio y produccion NO tocadas.")
    finally:
        bloquea_suspension(False)
        print("[SUSPENSION] liberada.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
