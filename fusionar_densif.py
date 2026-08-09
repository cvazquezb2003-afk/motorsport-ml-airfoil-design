"""
FUSION del dataset densificado con el de produccion, a un CSV DE TRABAJO.

  airfoil_dataset.csv  (produccion, 20.349 filas)
+ airfoil_dataset_densificado.csv  (54.752 filas de la tirada de densificacion)
= airfoil_dataset_densif_merged.csv  (CSV de trabajo, NUEVO)

Concat directo: las 19 columnas ya son identicas y la tirada verifico 0 duplicados
contra produccion y 0 internos. Se conserva el ORDEN (produccion primero, luego las
nuevas), sin reordenar, para que el fichero sea reproducible byte a byte desde sus dos
fuentes.

NO toca produccion: airfoil_dataset.csv y los .joblib quedan como estan. Esto solo
escribe el CSV fusionado; no reentrena nada.

TRAZABILIDAD PERMANENTE: las filas de la densificacion llevan el sufijo "_densif" en
`source` (sobol -> sobol_densif, etc.), asi que siempre se pueden aislar o retirar:
    merged[merged.source.str.endswith("_densif")]      # solo densificacion
    merged[~merged.source.str.endswith("_densif")]     # solo el original
"""
import os, sys, hashlib
import numpy as np
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
PROD = os.path.join(BASE, "airfoil_dataset.csv")
DENS = os.path.join(BASE, "airfoil_dataset_densificado.csv")
OUT = os.path.join(BASE, "airfoil_dataset_densif_merged.csv")
SUF = "_densif"
CLAVE = ["run_id", "velocidad_kmh", "alpha_deg"]     # identifica una fila unica
VELS_ESPERADAS = [110, 150, 180, 220, 250, 290]
ALPHA_MAX = {110: 10, 150: 11, 180: 12, 220: 13, 250: 13, 290: 14}


def md5(p, limite=25e6):
    if os.path.getsize(p) > limite:
        return "(grande, se omite)"
    return hashlib.md5(open(p, "rb").read()).hexdigest()


def main():
    prod = pd.read_csv(PROD)
    dens = pd.read_csv(DENS)

    # --- huella de produccion ANTES de tocar nada ---
    antes = {f: (os.path.getsize(os.path.join(BASE, f)), md5(os.path.join(BASE, f)))
             for f in ("airfoil_dataset.csv", "modelo_LD_inversa_xgb.joblib",
                       "modelo_CD_xgb.joblib", "modelo_CL_xgb.joblib",
                       "ensemble_ld_sigma.joblib", "modelo_LD_inversa_meta.json")}

    print("=" * 98)
    print("FUSION")
    print("=" * 98)
    print("   produccion   : %s filas" % format(len(prod), ","))
    print("   densificado  : %s filas" % format(len(dens), ","))
    if list(prod.columns) != list(dens.columns):
        print("   [ABORTA] las columnas no coinciden"); return 1

    merged = pd.concat([prod, dens], ignore_index=True)
    merged.to_csv(OUT, index=False)
    print("   -> %s  (%s filas, %.1f MB)"
          % (os.path.basename(OUT), format(len(merged), ","), os.path.getsize(OUT) / 1e6))

    # ================= VERIFICACION =================
    m = pd.read_csv(OUT)          # se relee del disco: se valida lo ESCRITO
    ok = lambda b: "OK" if b else "MAL"

    print("\n" + "=" * 98)
    print("1) CONTEOS")
    print("=" * 98)
    n_tot, n_ok = len(m), (m.status == "ok").sum()
    print("   filas totales : %s  (esperado 75.101)   %s"
          % (format(n_tot, ","), ok(n_tot == 75101)))
    print("   filas ok      : %s  (esperado 63.840)   %s"
          % (format(n_ok, ","), ok(n_ok == 63840)))
    print("   convergencia  : %.1f%%" % (100 * n_ok / n_tot))
    print("   perfiles      : %s" % format(m.run_id.nunique(), ","))

    print("\n" + "=" * 98)
    print("2) DUPLICADOS por clave %s" % CLAVE)
    print("=" * 98)
    d = len(m) - len(m.drop_duplicates(subset=CLAVE))
    print("   duplicados: %d   %s" % (d, ok(d == 0)))

    print("\n" + "=" * 98)
    print("3) TRAZABILIDAD DEL ORIGEN")
    print("=" * 98)
    es_d = m.source.astype(str).str.endswith(SUF)
    print("   con sufijo '%s' : %s  (esperado 54.752)   %s"
          % (SUF, format(int(es_d.sum()), ","), ok(int(es_d.sum()) == 54752)))
    print("   sin sufijo       : %s  (esperado 20.349)   %s"
          % (format(int((~es_d).sum()), ","), ok(int((~es_d).sum()) == 20349)))
    print("   sources: %s" % dict(m.source.value_counts()))

    print("\n" + "=" * 98)
    print("4) COBERTURA")
    print("=" * 98)
    vs = sorted(m.velocidad_kmh.unique())
    print("   velocidades: %s   %s" % (vs, ok(vs == VELS_ESPERADAS)))
    print("\n   %-11s %-9s %-16s %-10s %s" % ("V", "angulos", "rango", "paso 1?", "filas ok"))
    todo_paso1 = True
    for v in vs:
        g = m[m.velocidad_kmh == v]
        a = sorted(g.alpha_deg.unique())
        esperado = list(range(-ALPHA_MAX[v], 1))
        p1 = (a == esperado)
        todo_paso1 &= p1
        print("   %-11s %-9d %-16s %-10s %s"
              % ("%d km/h" % v, len(a), "%d..%d" % (a[0], a[-1]), ok(p1),
                 format(int((g.status == "ok").sum()), ",")))
    print("\n   paso angular de 1 grado (pares E impares) en TODAS las velocidades: %s"
          % ok(todo_paso1))

    print("\n" + "=" * 98)
    print("5) REYNOLDS")
    print("=" * 98)
    mo = m[m.status == "ok"]
    po = prod[prod.status == "ok"]
    print("   Reynolds unicos (ok): %s   (produccion tenia %s)   %s"
          % (format(mo.reynolds.nunique(), ","), format(po.reynolds.nunique(), ","),
             ok(abs(mo.reynolds.nunique() - 5633) <= 5)))
    print("   rango: %s - %s" % (format(int(mo.reynolds.min()), ","),
                                 format(int(mo.reynolds.max()), ",")))
    hu = np.diff(np.sort(mo.reynolds.unique()))
    print("   hueco mediano %.0f | p95 %.0f | mayor %.0f"
          % (np.median(hu), np.percentile(hu, 95), hu.max()))

    print("\n" + "=" * 98)
    print("6) PRODUCCION INTACTA (md5 antes vs despues de la fusion)")
    print("=" * 98)
    for f, (sz0, h0) in antes.items():
        p = os.path.join(BASE, f)
        sz1, h1 = os.path.getsize(p), md5(p)
        igual = (sz0 == sz1) and (h0 == h1)
        print("   %-32s %13s B   %s   %s"
              % (f, format(sz1, ","),
                 pd.Timestamp(os.stat(p).st_mtime, unit="s").strftime("%Y-%m-%d %H:%M"),
                 ok(igual)))
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(main())
