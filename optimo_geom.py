"""
GEOMETRIA Y Cp DEL OPTIMO REAL (portable, XFOIL sin CATIA).
- .dat del optimo con el generador ARREGLADO (airfoil_geom_fixed, sin cruce del TE).
- Cp del optimo via XFOIL; si no converge -> FALLBACK al Cp del vecino (registra cual).
- Caches: .dat por hash de los 7 params; figura Cp por (hash, vel, alpha).

Reutiliza: airfoil_geom_fixed, graficas_cp.fig_cp_from_dat, cp_on_demand (via graficas_cp),
vecino (fallback). NO toca produccion.
"""
import os, json, hashlib, tempfile
import airfoil_geom_fixed as FIX
from graficas_cp import fig_cp_from_dat, _reynolds
from feature_utils import SHAPE
from rutas import XFOIL_DISPONIBLE, MSG_CP, MSG_CP_FALLO

BASE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(BASE, "graficas", "_optimo_cache"); os.makedirs(CACHE, exist_ok=True)
_CP_CACHE = {}


TE_STEP = 0.05          # incremento fabricable del espesor de TE (mm)


def redondea_te(sp):
    """ENTREGA: redondea trailing_edge_thickness_mm al multiplo de 0.05 mm mas cercano.
    La inversa NO se toca (optimiza con el valor exacto); esto solo afecta a lo que se
    genera, se muestra y se descarga, para que todo sea el MISMO perfil fabricable."""
    out = {k: float(v) for k, v in sp.items()}
    te = out.get("trailing_edge_thickness_mm")
    if te is not None:
        out["trailing_edge_thickness_mm"] = round(round(te / TE_STEP) * TE_STEP, 2)
    return out


def metricas_banda(sp, alpha_lo, alpha_hi, vel=180.0):
    """LD/CD/sigma medios y angulo recomendado para UNOS params dados, con la MISMA
    convencion que la inversa (media sobre la banda, a la velocidad `vel`). Solo lectura
    de los modelos ya cargados; no altera la inversa.

    OJO: `vel` existia en la firma desde el principio pero NO estaba conectado — el
    cuerpo llamaba a S._arma_X sin pasarlo, asi que todo salia a 180 km/h aunque
    pidieras otra cosa, y en silencio. Ya se propaga (feature C5)."""
    import numpy as np
    import inversa_service as S
    lo, hi = sorted([abs(float(alpha_lo)), abs(float(alpha_hi))])
    angs = -np.arange(lo, hi + 1e-6, 1.0) if hi > lo else np.array([-lo])
    shape = np.array([[float(sp[k]) for k in SHAPE]])
    lds, cds, sds = [], [], []
    for a in angs:
        X = S._arma_X(shape, float(a), float(vel))
        mu, sd = S._ens_stats(X)
        lds.append(float(S._LD.predict(X)[0]))
        cds.append(float(S._CD.predict(X)[0]))
        sds.append(float(sd[0]))
    i_best = int(np.argmax(np.abs(lds)))
    return {"LD": float(np.mean(lds)), "CD": float(np.mean(cds)),
            "sigma": float(np.mean(sds)), "alpha_rec_abs": float(abs(angs[i_best]))}


def franja_angulo(sp, alpha_lo, alpha_hi, vel=180.0):
    """FRANJA de angulos que el modelo NO distingue del mejor.

    Definicion: todos los angulos de la rejilla de 1 grado cuyo |L/D| predicho cumple
        |LD(a)| >= |LD(a_argmax)| - sigma
    es decir, los que caen dentro de una sigma del argmax.

    POR QUE una franja y no un punto: el argmax suele ganar por MENOS QUE LA PROPIA
    SIGMA del modelo, asi que publicar un grado concreto finge una resolucion que no
    existe. La franja tambien absorbe el salto no monotono del angulo al cambiar de
    velocidad.

    NOTA (actualizada tras la densificacion): el motivo original incluia que el dataset
    barria SOLO ANGULOS PARES, lo que daba al surrogate una resolucion efectiva de ~2
    grados. Eso YA NO ES CIERTO: el dataset de produccion tiene paso de 1 grado (pares e
    impares) en las seis velocidades. La franja se mantiene porque su razon de fondo
    -que la ventaja del argmax cae por debajo de sigma- sigue siendo cierta, pero ahora
    sale mas estrecha (sigma bajo ~40% al densificar).

    QUE SIGMA: la MEDIA de la banda, que es exactamente la que se publica en el KPI
    "Uncertainty". Dos razones, y la segunda es la que decide:
      1. Coherencia visible: el usuario ve "L/D 58.5 +-0.46" y puede rehacer la cuenta
         de la franja con esos dos numeros. Si la franja usara otra sigma, la interfaz
         estaria mostrando una cifra y calculando con otra.
      2. Se probo usar la sigma LOCAL del argmax y hay que descartarlo: el argmax tiende
         a caer donde el ensemble esta mas de acuerdo, asi que su sigma es la MENOR de la
         banda y estrecha la franja justo por ser el punto mas comodo. Medido en
         medium/300mm a 180 km/h: sigma local del argmax 0.337 (la minima de las cinco;
         las otras van de 0.39 a 0.55) y con ella 7 grados quedaba fuera por 0.0006 en
         L/D. Una franja que colapsa a un punto por seis diezmilesimas no esta midiendo
         nada; usar la media de la banda da 5-7 grados, que es la lectura honesta.

    ENVOLVENTE, no tramo contiguo: se devuelve [min, max] de TODOS los angulos que
    cumplen la condicion. Se probo exigir contiguidad y hay que descartarlo: la curva de
    L/D puede alternar, asi que un angulo cumple el umbral y su vecino inmediato no. Con
    los modelos PRE-densificacion (dataset solo-pares, diente de sierra acusado) esto
    colapsaba la franja a un punto justo en el caso que motivo la feature: en
    medium/300mm a 180 km/h, 7 grados cumplia (58.81 vs umbral 58.81) pero 6 no (58.02).
    Con el dataset densificado (paso 1 grado) el diente de sierra es mucho menor, pero
    la envolvente se mantiene: sigue siendo lo unico interpretable como reglaje (un
    rango, no un conjunto con huecos) y no depende de que la curva sea suave.

    La rejilla es la banda pedida, asi que la franja queda RECORTADA a ella por
    construccion. Si la banda es un solo angulo (puerta C), la franja colapsa a un punto.
    """
    import numpy as np
    import inversa_service as S
    lo, hi = sorted([abs(float(alpha_lo)), abs(float(alpha_hi))])
    angs = np.arange(lo, hi + 1e-6, 1.0) if hi > lo else np.array([lo])
    shape = np.array([[float(sp[k]) for k in SHAPE]])
    lds, sds = [], []
    for a in angs:
        X = S._arma_X(shape, float(-a), float(vel))
        _mu, sd = S._ens_stats(X)
        lds.append(abs(float(S._LD.predict(X)[0])))
        sds.append(float(sd[0]))
    lds, sds = np.array(lds), np.array(sds)

    i = int(np.argmax(lds))
    sigma_ref = float(np.mean(sds))          # = la sigma del KPI (media de la banda)
    umbral = float(lds[i]) - sigma_ref
    dentro = np.where(lds >= umbral - 1e-9)[0]
    j0, j1 = int(dentro.min()), int(dentro.max())

    return {
        "lo": float(angs[j0]), "hi": float(angs[j1]),
        "argmax": float(angs[i]), "sigma_ref": sigma_ref,
        "sigma_argmax": float(sds[i]),       # informativa: la local, no la que decide
        "umbral_LD": umbral, "LD_argmax": float(lds[i]),
        # Dispersion REAL de L/D dentro de la franja. No confundir con (LD_argmax -
        # umbral), que es sigma por definicion y no informa de nada.
        # delta_extremos: caida del argmax a los EXTREMOS de la franja. Por construccion
        # es <= sigma (los extremos cumplen el umbral), asi que es la cifra que se puede
        # comparar con sigma sin decir una incoherencia. Es la que usa la UI.
        # delta_interior: la mayor caida en CUALQUIER angulo de la franja. Puede SUPERAR
        # sigma, porque la envolvente incluye angulos interiores que se hunden bajo el
        # umbral (el diente de sierra del muestreo par). Se expone por honestidad.
        "LD_min_franja": float(lds[j0:j1 + 1].min()),
        "delta_extremos": float(lds[i] - min(lds[j0], lds[j1])),
        "delta_interior": float(lds[i] - lds[j0:j1 + 1].min()),
        "n": int(j1 - j0 + 1), "es_punto": bool(j0 == j1),
        "texto": (f"{angs[i]:g}°" if j0 == j1 else f"{angs[j0]:g}–{angs[j1]:g}°"),
    }


def hash_params(sp):
    """Hash estable de los 7 params (para cachear .dat y Cp del optimo)."""
    key = {k: round(float(sp[k]), 4) for k in SHAPE}
    return hashlib.md5(json.dumps(key, sort_keys=True).encode()).hexdigest()[:12]


def gen_dat_optimo(sp):
    """Genera (cacheado) el .dat del optimo con el generador arreglado. Devuelve (path, hash).
    Redondea el TE por si acaso: el .dat entregado es SIEMPRE el fabricable."""
    sp = redondea_te(sp)
    h = hash_params(sp)
    path = os.path.join(CACHE, h + ".dat")
    if not os.path.exists(path):
        C, _ = FIX.generate_contour({k: float(sp[k]) for k in SHAPE})
        with open(path, "w") as f:
            f.write("OPTIMUM\n")
            for x, y in C:
                f.write(f"{x:.6f} {y:.6f}\n")
    return path, h


def dat_path(h):
    """Ruta del .dat cacheado por hash (para el endpoint de descarga)."""
    p = os.path.join(CACHE, h + ".dat")
    return p if os.path.exists(p) else None


def gen_csv_optimo(sp):
    """CSV del optimo en mm REALES (x_mm,y_mm,z_mm) para importar a CATIA a escala.

    NO regenera geometria: LEE EL PROPIO .dat ya cacheado y lo escala. Asi es
    imposible que el CSV y el .dat describan perfiles distintos -- son los mismos
    puntos, en el mismo orden (XFOIL: TE -> extrados -> LE -> intrados -> TE),
    multiplicados por la cuerda. z_mm = 0: el perfil es 2D, en el plano XY.

    Alineado por el LE en x=0 restando el x minimo YA ESCALADO. Hace falta: el arco
    del morro sobresale unas decimas de mm del origen (x_min ~ -0.0005 de cuerda),
    porque LE=(0,0) esta SOBRE el circulo del LE, no en su punto mas a la izquierda.
    """
    path, h = gen_dat_optimo(sp)                  # cacheado; no recalcula si ya existe
    cpath = os.path.join(CACHE, h + ".csv")
    if not os.path.exists(cpath):
        chord = float(redondea_te(sp)["chord_length_mm"])
        pts = []
        with open(path) as f:
            next(f)                               # cabecera "OPTIMUM"
            for ln in f:
                q = ln.split()
                if len(q) == 2:
                    pts.append((float(q[0]) * chord, float(q[1]) * chord))
        x0 = min(p[0] for p in pts)               # offset del LE, ya en mm
        with open(cpath, "w", newline="") as f:
            f.write("x_mm,y_mm,z_mm\n")
            for x, y in pts:
                f.write("%.4f,%.4f,0.0000\n" % (x - x0, y))
    return cpath, h


def csv_path(h):
    """Ruta del CSV cacheado por hash (para el endpoint de descarga)."""
    p = os.path.join(CACHE, h + ".csv")
    return p if os.path.exists(p) else None


def gen_step_optimo(sp):
    """STEP (ISO 10303-21, AP214) con la curva CERRADA del contorno, en mm reales.

    NO recalcula geometria y NO reescala: LEE EL PROPIO CSV, que a su vez se
    derivo del .dat. La cadena es .dat -> .csv -> .step, y cada eslabon copia los
    numeros del anterior, asi que los tres ficheros describen el MISMO perfil por
    construccion, no por coincidencia.

    Los N puntos van tal cual, sin cerrar el contorno a mano: el primero y el
    ultimo estan separados justo por el espesor del TE romo, y ese hueco lo cierra
    el tramo recto de la COMPOSITE_CURVE (ver step_export)."""
    cpath, h = gen_csv_optimo(sp)
    spath = step_path(h) or os.path.join(CACHE, _nombre_step(h))
    if not os.path.exists(spath):
        import csv as _csv
        from step_export import escribe_step_curva          # import perezoso
        pts = []
        with open(cpath, newline="") as f:
            for fila in _csv.DictReader(f):
                pts.append((float(fila["x_mm"]), float(fila["y_mm"])))
        escribe_step_curva(pts, spath, nombre="AIRFOIL")
    return spath, h


def _nombre_step(h):
    """Nombre del STEP cacheado: hash de la geometria + VERSION DEL ESCRITOR.
    La version en el nombre es lo que impide servir un fichero escrito por una
    version anterior del escritor (ver el comentario de FORMATO en step_export)."""
    from step_export import FORMATO
    return "%s.v%d.step" % (h, FORMATO)


def step_path(h):
    """Ruta del STEP cacheado por hash (para el endpoint de descarga)."""
    p = os.path.join(CACHE, _nombre_step(h))
    return p if os.path.exists(p) else None


def cp_optimo(sp, alpha_abs, vel=290):
    """Cp del optimo (XFOIL sobre el .dat arreglado). Fallback al vecino si no converge.
    Devuelve dict: {cp (fig json), cp_source: 'optimum'|'neighbour', dat_hash, chord_mm, alpha}."""
    sp = redondea_te(sp)                                  # Cp sobre la geometria ENTREGADA
    chord = float(sp["chord_length_mm"])
    # Angulo ENTERO EXACTO (no se redondea a par): _xfoil_cp marcha en pasos de 2 pero
    # remata en el angulo pedido, asi que los impares convergen igual. Unificado con la
    # comparacion de Cp para que Results y Compare usen SIEMPRE el mismo angulo.
    alpha = -int(round(float(alpha_abs)))
    h = hash_params(sp)
    key = (h, vel, alpha)
    if key in _CP_CACHE:
        return _CP_CACHE[key]

    # MODO WEB: sin XFOIL no hay Cp. Se devuelve la MISMA forma de dict con cp=None,
    # para que los consumidores (dat_hash, chord_mm, alpha) sigan funcionando: la
    # geometria descargable no depende de XFOIL y debe seguir entregandose.
    if not XFOIL_DISPONIBLE:
        out = {"cp": None, "cp_source": "unavailable", "cp_aviso": MSG_CP,
               "dat_hash": gen_dat_optimo(sp)[1], "chord_mm": chord, "alpha": alpha}
        _CP_CACHE[key] = out
        return out

    dat, _ = gen_dat_optimo(sp)
    source, fig = "optimum", None
    try:
        fig, _ = fig_cp_from_dat(
            dat, chord, vel, alpha,
            "Pressure distribution (Cp) — your optimal profile",
            (f"your optimal geometry &nbsp;·&nbsp; chord {chord:.0f} mm &nbsp;·&nbsp; "
             f"{vel} km/h &nbsp;·&nbsp; |α| = {abs(alpha)}°"),
            workdir=os.path.join(tempfile.gettempdir(), "cp_opt", h))
    except Exception:                                     # FALLBACK al vecino
        # El fallback va en su PROPIO try. Antes no lo tenia, y si fallaba —por
        # ejemplo sin el .asc archivado, que es justo lo que pasa en un servidor
        # sin dataset_runs— la excepcion salia de dentro del `except` y se
        # propagaba al endpoint: /api/optimo devolvia 400 con solo {"error"} y el
        # usuario perdia dat_url, csv_url y step_url. Descargas que NO dependen de
        # XFOIL para nada, tumbadas por un fallo del Cp.
        try:
            from vecino import encontrar_vecino, fig_cp_vecino
            v = encontrar_vecino(sp)
            fig = fig_cp_vecino(v["run_id"], alpha_abs)
            short = v["run_id"].split("_")[0]
            fig.update_layout(title=dict(text=(
                "<b>Cp of nearest profile (optimum did not converge)</b>"
                f"<br><span style='font-size:12px'>profile {short} · "
                f"{v['similitud_pct']}% match · XFOIL on the closest real geometry"
                "</span>")))
            source = "neighbour"
        except Exception:
            fig, source = None, "failed"

    if fig is None:                                       # ni optimo ni vecino
        out = {"cp": None, "cp_source": "failed", "cp_aviso": MSG_CP_FALLO,
               "dat_hash": h, "chord_mm": chord, "alpha": alpha}
        _CP_CACHE[key] = out
        return out

    out = {"cp": json.loads(fig.to_json()), "cp_source": source,
           "dat_hash": h, "chord_mm": chord, "alpha": alpha}
    _CP_CACHE[key] = out
    return out


if __name__ == "__main__":
    import sys, time
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass
    import inversa_service as S
    r = S.optimizar(300, -14, -9)                         # Monaco
    t = time.time(); res = cp_optimo(r["shape_params"], 11.5)
    print(f"cp_source={res['cp_source']}  dat_hash={res['dat_hash']}  "
          f"cp_traces={len(res['cp']['data'])}  [{time.time()-t:.1f}s]")
    print("dat cacheado:", dat_path(res["dat_hash"]))
