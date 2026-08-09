"""
DENSIFICACION del dataset: velocidades nuevas (150/220/250) + ANGULOS IMPARES en todas.

Sobre las geometrias que YA EXISTEN: no toca CATIA, no regenera nada. Recorre los
run_id con .dat archivado en dataset_runs/, relanza XFOIL a cada velocidad con el
barrido de paso 1 grado, y escribe SOLO las combinaciones (run_id, velocidad, angulo)
que no estan ya en airfoil_dataset.csv.

Sale a un CSV APARTE (airfoil_dataset_densificado.csv). NO toca produccion:
ni airfoil_dataset.csv, ni los modelos, ni dataset_runs (solo LEE los .dat).

REANUDABLE: la unidad de trabajo es (run_id, velocidad). Al arrancar lee lo ya escrito
y salta esos pares, asi que se puede cortar con Ctrl-C y volver a lanzar.

  python densificar.py --limite 10      # prueba corta
  python densificar.py                  # tirada completa
  python densificar.py --plan           # solo imprime el plan, no ejecuta

--- POR QUE SE CORRE EL BARRIDO COMPLETO Y NO SOLO LOS ANGULOS NUEVOS ---
XFOIL acumula la polar marchando SECUENCIALMENTE: cada ALFA parte de la solucion
convergida del anterior. Pedir solo los impares (0,-1,-3,-5...) daria saltos mayores
que el barrido de paso 1 y empeoraria la convergencia respecto al dataset actual. Se
corre 0..-amax de 1 en 1 y se DESCARTAN al escribir las combinaciones ya existentes.
Coste: se calculan 79 condiciones por perfil, se escriben 58.

--- LA GEOMETRIA SE REGENERA DEL .asc, NO SE USA EL .dat ARCHIVADO ---
CRITICO. El airfoil_v4.dat que hay en dataset_runs/ es de JUNIO: es la geometria
TE-AMPUTADO original. El dataset de produccion se regenero en julio con el conversor
TE-REAL a partir de los .asc, y esos .dat nunca se reescribieron en el archivo.
Usar el .dat archivado da otra geometria: medido, un desfase medio de 0.097 en CL
(hasta 0.184) contra las filas de produccion, ~10-20% del valor. Por eso aqui se
regenera el .dat del .asc con piloto_tereal.genera_tereal, igual que etapa1_tereal_965.

--- BUG DE RUTAS LARGAS DE XFOIL ---
XFOIL trunca las rutas largas ('File OPEN error. Nonexistent file: C'). Se reutiliza
piloto_tereal.xfoil_sweep, que ya carga por nombre corto con cwd en su scratch.
"""
import os, sys, csv, time, shutil, argparse, subprocess, tempfile
import numpy as np
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
PROD = os.path.join(BASE, "airfoil_dataset.csv")
OUT = os.path.join(BASE, "airfoil_dataset_densificado.csv")
DATASET_RUNS = os.path.join(BASE, "dataset_runs")
from rutas import XFOIL_EXE   # fuente unica de la ruta a XFOIL (ver rutas.py)
ITERATIONS = 100          # identico a run_xfoil.ITERATIONS
TIMEOUT = 180
CHORD_MIN = 150.0

# Reutiliza la fuente unica del pipeline (Reynolds y L/D) y el harness YA VALIDADO de
# la regeneracion TE-real (geometria + barrido XFOIL), para que las filas nuevas sean
# indistinguibles de las de produccion.
from generate_batch import compute_reynolds, compute_ld
from piloto_tereal import genera_tereal, xfoil_sweep

# TRAZABILIDAD: las filas de esta tirada llevan el source original + este sufijo, para
# poder aislarlas o retirarlas PARA SIEMPRE despues de fusionar, sin tocar las
# originales. Se eligio sufijar `source` en vez de anadir una columna para que el CSV
# siga teniendo las MISMAS 19 columnas que produccion y la fusion sea un concat directo.
#   filas de la densificacion : df[df.source.str.endswith("_densif")]
#   filas originales          : df[~df.source.str.endswith("_densif")]
# OJO: eda_ml_filtrado150.py arma su dataset de contraste con
# source.isin(["random","sobol"]); con el sufijo, estas filas quedan FUERA de ese
# subconjunto (que es un contraste historico 200-400), no del entrenamiento real,
# que filtra por cuerda. Es el comportamiento deseado, pero conviene saberlo.
SUFIJO_ORIGEN = "_densif"

SHAPE_COLS = ["chord_length_mm", "leading_edge_angle_deg", "leading_edge_thickness_level",
              "trailing_edge_angle_deg", "trailing_edge_thickness_mm",
              "te_upr_angle_deg", "te_lwr_angle_deg"]
COLS = ["run_id", "timestamp", "source"] + SHAPE_COLS + [
    "alpha_deg", "velocidad_kmh", "reynolds", "CL", "CD", "CM", "LD",
    "status", "error_detail"]

# --- barrido propuesto -------------------------------------------------------------
# Limites por interpolacion lineal a trozos de las anclas MEDIDAS del dataset actual
# (110->-10, 180->-12, 290->-14), redondeados al entero mas cercano. Es la misma
# interpolacion que usa guardas_velocidad.alpha_max_soportado, para que el dominio que
# se genera y el que la UI declara soportado no se separen.
VELS = [110, 150, 180, 220, 250, 290]
ALPHA_MAX = {110: 10, 150: 11, 180: 12, 220: 13, 250: 13, 290: 14}
ALPHAS = {v: [-a for a in range(0, ALPHA_MAX[v] + 1)] for v in VELS}


def fila(base, alpha, vel, re, coeffs):
    """Construye la fila con el MISMO formato y columnas que airfoil_dataset.csv."""
    r = {c: base[c] for c in ["run_id", "timestamp", "source"] + SHAPE_COLS}
    r["alpha_deg"] = int(alpha)
    r["velocidad_kmh"] = int(vel)
    r["reynolds"] = int(round(re))
    if coeffs is None:
        r.update({"CL": "", "CD": "", "CM": "", "LD": "",
                  "status": "error_xfoil_no_converge",
                  "error_detail": "no convergio en la polar (densificacion)"})
    else:
        cl, cd, cm = coeffs
        r.update({"CL": cl, "CD": cd, "CM": cm, "LD": compute_ld(cl, cd),
                  "status": "ok", "error_detail": ""})
    return r


def main():
    ap = argparse.ArgumentParser(description="Densificacion de velocidades y angulos.")
    ap.add_argument("--limite", type=int, default=None,
                    help="procesar solo los N primeros perfiles (prueba corta)")
    ap.add_argument("--plan", action="store_true", help="imprime el plan y sale")
    args = ap.parse_args()

    prod = pd.read_csv(PROD)
    existentes = set(zip(prod.run_id, prod.velocidad_kmh, prod.alpha_deg))
    per = prod.groupby("run_id").first()

    objetivo = []
    for rid in prod.run_id.unique():
        asc = os.path.join(DATASET_RUNS, rid, "auto_export.asc")
        if float(per.loc[rid, "chord_length_mm"]) >= CHORD_MIN and os.path.exists(asc):
            objetivo.append(rid)
    objetivo.sort()
    if args.limite:
        objetivo = objetivo[:args.limite]

    calc = sum(len(ALPHAS[v]) for v in VELS) * len(objetivo)
    nuevas = sum(1 for rid in objetivo for v in VELS for a in ALPHAS[v]
                 if (rid, v, a) not in existentes)
    print("=" * 92)
    print("DENSIFICACION — perfiles: %d | velocidades: %s" % (len(objetivo), VELS))
    print("   angulos por velocidad: " + " | ".join(
        "%d km/h: 0..%d (%d)" % (v, -ALPHA_MAX[v], len(ALPHAS[v])) for v in VELS))
    print("   condiciones a CALCULAR: %s   filas NUEVAS a escribir: %s"
          % (format(calc, ","), format(nuevas, ",")))
    print("   salida: %s   (produccion NO se toca)" % os.path.basename(OUT))
    print("=" * 92)
    if args.plan:
        return 0

    # --- reanudable: pares (run_id, velocidad) ya escritos ---
    hechos = set()
    if os.path.exists(OUT):
        prev = pd.read_csv(OUT)
        hechos = set(zip(prev.run_id, prev.velocidad_kmh))
        print("[REANUDA] %s filas ya escritas, %d pares (perfil,velocidad) hechos\n"
              % (format(len(prev), ","), len(hechos)))
    else:
        with open(OUT, "w", newline="", encoding="utf-8") as fh:
            csv.DictWriter(fh, fieldnames=COLS).writeheader()

    work = os.path.join(tempfile.gettempdir(), "densificar")
    t0 = time.time()
    n_filas = n_ok = n_inv = 0
    with open(OUT, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS)
        for k, rid in enumerate(objetivo, 1):
            base = per.loc[rid]
            base = {c: (rid if c == "run_id" else base[c])
                    for c in ["run_id", "timestamp", "source"] + SHAPE_COLS}
            # marca de origen: sobol -> sobol_densif (ver SUFIJO_ORIGEN arriba)
            base["source"] = str(base["source"]) + SUFIJO_ORIGEN
            chord = float(base["chord_length_mm"])
            # GEOMETRIA TE-REAL regenerada del .asc (el .dat archivado es el amputado)
            asc = os.path.join(DATASET_RUNS, rid, "auto_export.asc")
            dat = os.path.join(work, "tr.dat")
            os.makedirs(work, exist_ok=True)
            try:
                genera_tereal(asc, dat)
            except Exception as e:
                print("[%4d/%4d] %s  FALLO al regenerar la geometria: %s"
                      % (k, len(objetivo), rid, e))
                continue
            linea = []
            for v in VELS:
                if (rid, v) in hechos:
                    linea.append("%d:skip" % v)
                    continue
                re = compute_reynolds(chord, v)
                res = xfoil_sweep(dat, re, ALPHAS[v])   # {alpha: (CL,CD,CM)}
                n_inv += 1
                v_ok = v_new = 0
                for a in ALPHAS[v]:
                    if (rid, v, a) in existentes:
                        continue                      # ya esta en produccion: no duplicar
                    coeffs = res.get(int(a))
                    w.writerow(fila(base, a, v, re, coeffs))
                    n_filas += 1; v_new += 1
                    if coeffs is not None:
                        v_ok += 1; n_ok += 1
                linea.append("%d:%d/%d" % (v, v_ok, v_new))
            fh.flush()
            el = time.time() - t0
            print("[%4d/%4d] %s c=%3.0f  %s  | %.1f s/perfil"
                  % (k, len(objetivo), rid, chord, "  ".join(linea), el / k))
            sys.stdout.flush()

    el = time.time() - t0
    print("\n" + "=" * 92)
    print("RESUMEN: %s filas nuevas | %s ok (%.1f%%) | %d invocaciones de XFOIL"
          % (format(n_filas, ","), format(n_ok, ","),
             100 * n_ok / n_filas if n_filas else 0, n_inv))
    print("   tiempo: %.1f s (%.2f s/perfil, %.3f s/condicion calculada)"
          % (el, el / max(len(objetivo), 1),
             el / max(calc, 1)))
    print("   -> extrapolado a 940 perfiles: %.2f h" % (el / max(len(objetivo), 1) * 940 / 3600))
    shutil.rmtree(work, ignore_errors=True)
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(main())
