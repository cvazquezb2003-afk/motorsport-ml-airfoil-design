"""
GUARDAS BLANDAS de la velocidad como parametro de usuario (feature C5).

Aqui viven SOLO los avisos que NO bloquean. El unico rechazo duro es
`entrada_dashboard.valida_velocidad` (fuera de 95-330 km/h), calcado del molde de
`valida_cuerda`. La separacion es deliberada: `entrada_dashboard` valida entradas,
este modulo interpreta el DOMINIO DE ENTRENAMIENTO, que es otra cosa y cambia si
algun dia se regenera el dataset.

Los tres avisos siguen el molde de `inversa_ld_v2.aviso_confianza_150_200`: devuelven
`(etiqueta, mensaje)` o `None`, con el porque fisico dentro del mensaje.

  1. aviso_velocidad(v)          -> zonas 95-110 y 290-330 km/h
  2. aviso_angulo(v, alpha_abs)  -> el angulo recomendado se sale de la cobertura
                                    angular que el dataset tiene A ESA velocidad
  3. aviso_esquina_reynolds(c,v) -> la COMBINACION cuerda x velocidad supera el
                                    Reynolds maximo visto en entrenamiento

NUMEROS, todos medidos sobre el dataset de entrenamiento
(`airfoil_dataset.csv`, status=ok y cuerda>=150: 16.182 filas / 944 perfiles):

  - Velocidades realmente evaluadas: 110, 150, 180, 220, 250 y 290 km/h (SEIS, desde la
    densificacion). No hay barrido continuo, pero el hueco 180-290, que era de 110 km/h
    de ancho, ahora esta partido en tres.
  - Reynolds cubierto: 311.149 - 2.724.206, de forma CONTINUA (2.773 valores unicos,
    hueco mediano 588, mayor hueco 5.922). Por eso interpolar en Re es seguro y el
    riesgo esta en salirse de la banda, no en los huecos.
  - Cobertura angular POR velocidad, con paso de 1 grado (pares E impares):
    110 -> -10, 150 -> -11, 180 -> -12, 220 -> -13, 250 -> -13, 290 -> -14.

NO toca modelos, dataset ni la inversa. Solo lee constantes.
"""

# =====================================================================================
# DOS CONJUNTOS DE VELOCIDADES, Y NO SON EL MISMO. Distinguirlos es lo que mantiene
# coherente la interfaz tras la promocion de los modelos densificados:
#
#   V_MODELO   : las 6 velocidades con las que se ENTRENO el modelo de produccion
#                (airfoil_dataset_densif_merged.csv). Gobiernan los avisos de dominio:
#                predecir a 220 km/h ya NO es interpolar a ciegas.
#   V_CATALOGO : las 3 velocidades que hay en airfoil_dataset.csv, que NO se promociono
#                y sigue siendo el catalogo contra el que confianza.contexto_catalogo
#                compara el percentil. Gobiernan el encaje a velocidad de referencia.
#
# Fusionarlas seria el error facil: el modelo sabe de 6 velocidades, pero las MEDICIONES
# de XFOIL con las que se compara el optimo siguen existiendo solo en 3.
# =====================================================================================
V_MODELO = (110.0, 150.0, 180.0, 220.0, 250.0, 290.0)    # entrenamiento (densificado)
V_CATALOGO = (110.0, 180.0, 290.0)                        # airfoil_dataset.csv (sin promocionar)
V_EVALUADAS = V_MODELO                                    # compat: nombre anterior

RE_MAX_ENTRENAMIENTO = 2_724_206.0       # Reynolds maximo visto (cuerda 500 a 290 km/h)
RE_MIN_ENTRENAMIENTO = 311_149.0

# Anclas de cobertura angular: (velocidad, |alpha| maximo con datos). Ahora son las 6
# del dataset densificado; antes solo 110/180/290 y las intermedias se interpolaban.
# Las tres nuevas ya no son estimaciones: son los limites REALMENTE generados.
ALPHA_ANCLAS = ((110.0, 10.0), (150.0, 11.0), (180.0, 12.0),
                (220.0, 13.0), (250.0, 13.0), (290.0, 14.0))

# zonas de velocidad interpolada (dentro del rango soportado pero fuera de lo evaluado)
V_ZONA_BAJA = (95.0, 110.0)
V_ZONA_ALTA = (290.0, 330.0)

RHO, MU = 1.225, 1.81e-5                 # identicos a generate_batch.AIR_RHO / AIR_MU

# Umbral de sigma "alta". NO se define aqui: se reexporta el de confianza.py para que
# no haya dos verdades. Se reexporta (en vez de que la UI importe de confianza) porque
# el aviso de velocidad y la sigma se presentan JUNTOS: la sigma disparada es la
# confirmacion, por parte del propio modelo, de lo que el aviso de dominio anticipa.
from confianza import SIGMA_MAL as SIGMA_ALTA_REF


def reynolds(chord_mm, v_kmh):
    """Re = rho * V * L / mu. Misma formula que generate_batch.compute_reynolds; se
    replica en vez de importar porque ese modulo arrastra el pipeline de CATIA y
    romperia la portabilidad (mismo criterio que en cargas.py)."""
    return RHO * (float(v_kmh) / 3.6) * (float(chord_mm) / 1000.0) / MU


def velocidad_referencia(v_kmh):
    """La velocidad del CATALOGO mas cercana (110/180/290). Para comparaciones que
    exigen igualdad exacta contra airfoil_dataset.csv, como confianza.contexto_catalogo.

    OJO: usa V_CATALOGO, no V_MODELO. El modelo conoce 6 velocidades, pero el catalogo
    de mediciones XFOIL contra el que se calcula el percentil sigue teniendo 3."""
    v = float(v_kmh)
    return min(V_CATALOGO, key=lambda x: abs(x - v))


def alpha_max_soportado(v_kmh):
    """|alpha| maximo con datos a esa velocidad. Lineal a trozos entre las anclas
    medidas (110,10) (180,12) (290,14); satura fuera del rango de anclas.

    Por que interpolar y no usar el escalon: la cobertura angular sube con el Reynolds
    de forma continua (a mas velocidad la perdida se retrasa), asi que el escalon de la
    tabla es un artefacto de haber muestreado solo 3 velocidades, no un limite fisico.
    """
    v = float(v_kmh)
    if v <= ALPHA_ANCLAS[0][0]:
        return ALPHA_ANCLAS[0][1]
    if v >= ALPHA_ANCLAS[-1][0]:
        return ALPHA_ANCLAS[-1][1]
    for (v0, a0), (v1, a1) in zip(ALPHA_ANCLAS, ALPHA_ANCLAS[1:]):
        if v0 <= v <= v1:
            return a0 + (a1 - a0) * (v - v0) / (v1 - v0)
    return ALPHA_ANCLAS[-1][1]


def aviso_velocidad(v_kmh):
    """Zonas 95-110 y 290-330: dentro del rango soportado, pero FUERA del intervalo
    110-290 que el modelo tiene medido. Devuelve (etiqueta, mensaje) o None.

    Que cambio con la densificacion: entre 110 y 290 el modelo se entreno en SEIS
    velocidades (110/150/180/220/250/290) en vez de tres, asi que pedir 220 km/h ya no
    es interpolar sobre un hueco de 110 km/h de ancho. Los avisos solo cubren los
    EXTREMOS, que siguen siendo los mismos: por debajo de 110 y por encima de 290 no hay
    ningun dato, densificado o no."""
    v = float(v_kmh)
    lo1, hi1 = V_ZONA_BAJA
    lo2, hi2 = V_ZONA_ALTA
    if lo1 <= v < hi1:
        return ("[!] INTERPOLATED SPEED",
                f"{v:g} km/h is below 110 km/h, the lowest speed the model was trained "
                "on. The Reynolds axis is covered continuously by the chord sweep, so the "
                "model interpolates rather than invents, but no profile was ever run "
                "below 110 km/h. Low Reynolds is also where XFOIL itself loses accuracy. "
                "Treat the numbers as indicative and verify in XFOIL before trusting them.")
    if lo2 < v <= hi2:
        return ("[!] INTERPOLATED SPEED",
                f"{v:g} km/h is above 290 km/h, the highest speed the model was trained "
                "on. The Reynolds reached is still inside the training envelope for most "
                "chords (the chord sweep covers it), but no profile was ever run above "
                "290 km/h, and the optimum angle keeps shifting to more aggressive "
                "settings with Reynolds. Treat the numbers as indicative.")
    return None


def aviso_angulo(v_kmh, alpha_rec_abs):
    """El angulo recomendado se sale de la cobertura angular que hay A ESA velocidad.
    NO recorta el angulo: solo avisa. Devuelve (etiqueta, mensaje) o None."""
    v = float(v_kmh)
    a = abs(float(alpha_rec_abs))
    amax = alpha_max_soportado(v)
    if a <= amax + 1e-9:
        return None
    return ("[!] ANGLE BEYOND DATA",
            f"at {v:g} km/h, the recommended angle (|α| = {a:g}°) falls beyond the "
            f"data-supported range (|α| <= {amax:.1f}° at this speed) — treat as "
            "indicative. The angle sweep in the dataset is stepped by speed "
            "(110 km/h reaches -10°, 150 -11°, 180 -12°, 220 and 250 -13°, 290 -14°) "
            "because stall is delayed at higher Reynolds. Beyond that limit the model "
            "extrapolates.")


def aviso_esquina_reynolds(chord_mm, v_kmh):
    """ESQUINA del dominio: cada variable por separado esta en rango, pero su
    COMBINACION da un Reynolds nunca visto. Es el caso cuerda grande + velocidad alta
    (p.ej. 500 mm a 330 km/h). Avisa y DEJA PASAR. Devuelve (etiqueta, mensaje) o None."""
    re = reynolds(chord_mm, v_kmh)
    if re <= RE_MAX_ENTRENAMIENTO:
        return None
    exceso = 100.0 * (re / RE_MAX_ENTRENAMIENTO - 1.0)
    return ("[!] REYNOLDS CORNER",
            f"this chord+speed combination exceeds the Reynolds range seen in training "
            f"— treat as indicative. Chord {float(chord_mm):g} mm at {float(v_kmh):g} km/h "
            f"gives Re = {re:,.0f}, {exceso:.0f}% above the training maximum of "
            f"{RE_MAX_ENTRENAMIENTO:,.0f}. Chord and speed are each inside their own "
            "supported range; it is their combination that leaves the sampled region, "
            "so this is genuine extrapolation, not interpolation.")


def avisos(chord_mm, v_kmh, alpha_rec_abs=None):
    """Los tres avisos blandos de una vez, en una lista de dicts (vacia si todo limpio).
    El aviso de angulo solo se evalua si ya se conoce el angulo recomendado."""
    out = []
    for av in (aviso_velocidad(v_kmh),
               aviso_esquina_reynolds(chord_mm, v_kmh),
               aviso_angulo(v_kmh, alpha_rec_abs) if alpha_rec_abs is not None else None):
        if av is not None:
            out.append({"etiqueta": av[0], "mensaje": av[1]})
    return out


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    print("alpha_max_soportado por velocidad:")
    for v in (95, 110, 140, 180, 200, 250, 290, 330):
        print(f"   {v:>3} km/h -> |α| <= {alpha_max_soportado(v):.2f}°   "
              f"(ref. mas cercana: {velocidad_referencia(v):g})")
    print("\nesquina Reynolds (Re max entrenamiento = %s):" % f"{RE_MAX_ENTRENAMIENTO:,.0f}")
    for c, v in ((300, 200), (500, 290), (500, 330), (150, 330)):
        re = reynolds(c, v)
        av = aviso_esquina_reynolds(c, v)
        print(f"   cuerda {c:>3} mm @ {v:>3} km/h -> Re = {re:>11,.0f}  "
              f"{'AVISO' if av else 'ok'}")
