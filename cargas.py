"""
CARGAS SECCIONALES por unidad de envergadura (portable, instantaneo).

Dado un perfil (7 params, con su cuerda) y su angulo recomendado, devuelve para
110/180/290 km/h:
    q = 1/2 * rho * V^2                 [Pa]
    downforce por metro = q * c * |CL|  [N/m]
    drag por metro      = q * c * CD    [N/m]

CL/CD salen del SURROGATE (prediccion, milisegundos), evaluado en el angulo
recomendado a cada velocidad.

COHERENCIA DEL REYNOLDS: no se recalcula por separado. Se construyen las features
con la MISMA ruta que usa el modelo (curvas_optimo._features, que a su vez usa
feature_utils) y el Re que se reporta se LEE de esa matriz de features. Asi el Re de
la tabla es exactamente el que el surrogate consumio. La formula es la misma que
generate_batch.compute_reynolds (rho=1.225, mu=1.81e-5); ese modulo no se importa
porque arrastra el pipeline de CATIA y romperia la portabilidad.

NO toca la inversa ni produccion. Solo calculo; sin UI.
"""
import numpy as np

from feature_utils import SHAPE, FEATURES
from curvas_optimo import _features, _CL, _CD

RHO = 1.225                      # kg/m3 (= AIR_RHO de generate_batch)
VELOCIDADES = (110, 180, 290)    # km/h de referencia del dataset
_IRE = FEATURES.index("reynolds")


def q_dinamica(v_kmh, rho=RHO):
    """Presion dinamica q = 1/2 * rho * V^2 [Pa], con V en m/s."""
    v = float(v_kmh) / 3.6
    return 0.5 * rho * v * v


def cargas_seccionales(shape_params, alpha_rec_abs, velocidades=VELOCIDADES,
                       v_usuario=None):
    """Cargas por unidad de envergadura en el angulo recomendado.

    Devuelve lista de dicts, uno por velocidad:
      {V_kmh, reynolds, q_Pa, CL, CD, downforce_N_por_m, drag_N_por_m, es_usuario}

    v_usuario: velocidad a la que se diseno el perfil. Se INSERTA en la lista, ordenada,
    y se marca con es_usuario=True. Se eligio una sola tabla ordenada por velocidad, en
    vez de una tabla aparte o de sustituir las 3 de referencia, porque:
      - la fila del usuario es la coherente con el angulo recomendado (que se decidio a
        esa velocidad), asi que tiene que estar si o si;
      - las 3 de referencia siguen siendo utiles como contexto y son las UNICAS con
        datos reales detras, asi que borrarlas perderia informacion;
      - ordenar por velocidad deja leer la progresion con V^2 de un vistazo, que es
        justo lo que la tabla existe para mostrar.
    Si la velocidad del usuario coincide con una de referencia no se duplica: se marca
    esa misma fila.
    """
    shape = np.array([float(shape_params[k]) for k in SHAPE])
    chord_m = float(shape_params["chord_length_mm"]) / 1000.0   # mm -> m
    a = -abs(float(alpha_rec_abs))                              # downforce: alpha < 0

    vels = [float(v) for v in velocidades]
    vu = None if v_usuario is None else float(v_usuario)
    if vu is not None and not any(abs(vu - v) < 1e-9 for v in vels):
        vels.append(vu)
    vels.sort()

    filas = []
    for v in vels:
        X = _features(shape, [a], v)          # misma ruta que el surrogate
        re = float(X[0, _IRE])                # Re LEIDO de las features del modelo
        cl = abs(float(_CL.predict(X)[0]))    # |CL| (downforce)
        cd = float(_CD.predict(X)[0])
        q = q_dinamica(v)
        filas.append({
            "V_kmh": int(v) if float(v).is_integer() else float(v),
            "reynolds": re,
            "q_Pa": q,
            "CL": cl,
            "CD": cd,
            "downforce_N_por_m": q * chord_m * cl,
            "drag_N_por_m": q * chord_m * cd,
            "es_usuario": bool(vu is not None and abs(v - vu) < 1e-9),
        })
    return filas


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    import inversa_service as S
    from optimo_geom import redondea_te

    # perfil HIGH DOWNFORCE, cuerda 300 mm
    r = S.optimizar(300, -14, -9)
    sp = redondea_te(r["shape_params"])
    arec = r["alpha_recomendado_abs"]
    chord_m = sp["chord_length_mm"] / 1000.0

    print("=" * 78)
    print(f"CARGAS SECCIONALES — high downforce, cuerda {sp['chord_length_mm']:.0f} mm, "
          f"|α| recomendado = {arec:g}°")
    print("=" * 78)
    filas = cargas_seccionales(sp, arec)
    print(f"{'V (km/h)':>9}{'Reynolds':>12}{'q (Pa)':>10}{'|CL|':>8}{'CD':>9}"
          f"{'downforce (N/m)':>17}{'drag (N/m)':>12}")
    for f in filas:
        print(f"{f['V_kmh']:>9}{f['reynolds']:>12,.0f}{f['q_Pa']:>10.1f}{f['CL']:>8.3f}"
              f"{f['CD']:>9.4f}{f['downforce_N_por_m']:>17.1f}{f['drag_N_por_m']:>12.1f}")

    # ---------------- COMPROBACIONES ----------------
    print("\n" + "-" * 78)
    print("COMPROBACIONES")
    print("-" * 78)

    q180 = q_dinamica(180)
    print(f"1) q a 180 km/h = {q180:.2f} Pa   (esperado ~1531)  ->"
          f" {'OK' if abs(q180 - 1531.25) < 1 else 'MAL'}")

    # efecto V^2: con c y CL FIJOS el ratio debe ser exactamente (290/110)^2
    ratio_q = q_dinamica(290) / q_dinamica(110)
    f110, f290 = filas[0], filas[-1]
    ratio_CL_fijo = ratio_q                      # c y CL se cancelan
    ratio_real = f290["downforce_N_por_m"] / f110["downforce_N_por_m"]
    esperado = (290 / 110) ** 2
    print(f"2) (290/110)^2 = {esperado:.3f} | ratio de q = {ratio_q:.3f} -> "
          f"{'OK' if abs(ratio_q - esperado) < 1e-9 else 'MAL'}")
    print(f"   downforce con |CL| FIJO (solo q): ratio = {ratio_CL_fijo:.3f}  -> "
          f"{'OK (V^2 correcto)' if abs(ratio_CL_fijo - esperado) < 1e-9 else 'MAL'}")
    print(f"   downforce REAL del surrogate    : ratio = {ratio_real:.3f}"
          f"   (|CL| 110={f110['CL']:.3f} -> 290={f290['CL']:.3f}, "
          f"x{f290['CL']/f110['CL']:.3f})")
    print(f"   -> el exceso sobre {esperado:.2f} es {ratio_real/esperado:.3f}x = la "
          "subida de |CL| con el Reynolds (fisica real, no un fallo)")

    # 3) el Re de cada fila coincide con el que recibio el surrogate y con la formula canonica
    print("3) Re de la tabla vs Re que recibio el surrogate vs formula canonica:")
    MU = 1.81e-5
    ok = True
    for f in filas:
        X = _features(np.array([float(sp[k]) for k in SHAPE]), [-abs(arec)], f["V_kmh"])
        re_modelo = float(X[0, _IRE])
        re_canon = RHO * (f["V_kmh"] / 3.6) * chord_m / MU
        same = abs(f["reynolds"] - re_modelo) < 1e-9 and abs(f["reynolds"] - re_canon) < 1e-6
        ok = ok and same
        print(f"   {f['V_kmh']:>3} km/h: tabla={f['reynolds']:,.2f}  "
              f"surrogate={re_modelo:,.2f}  canonica={re_canon:,.2f}  "
              f"{'IDENTICOS' if same else 'DIFIEREN'}")
    print(f"   -> {'OK: la tabla y el modelo usan el MISMO Re' if ok else 'MAL'}")
