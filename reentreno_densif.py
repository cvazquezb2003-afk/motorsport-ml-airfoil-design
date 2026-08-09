"""
REENTRENO sobre el dataset DENSIFICADO fusionado, a modelos con nombre NUEVO.

  entrada : airfoil_dataset_densif_merged.csv   (75.101 filas, 63.840 ok)
  salida  : modelo_CL_densif.joblib
            modelo_CD_densif.joblib
            modelo_LD_inversa_densif.joblib
            ensemble_ld_sigma_densif.joblib

NO toca produccion: ni airfoil_dataset.csv, ni modelo_*_xgb.joblib, ni
ensemble_ld_sigma.joblib, ni lo que usa el dashboard. Entrena EN PARALELO para comparar.

--- COMO SE COMPARA (esto es lo que decide si promocionar) ---
Comparar el modelo nuevo contra el .joblib de produccion CARGADO DE DISCO seria
tramposo: ese modelo se entreno con TODOS los perfiles, asi que cualquier fila de test
es una fila que ya vio. La comparacion honesta es a igualdad de protocolo:

  GroupKFold(5) POR run_id sobre el dataset fusionado. En cada fold:
     BASE  = se entrena SOLO con las filas ORIGINALES (source sin '_densif')
             de los perfiles de entrenamiento  -> equivale al modelo actual
     NUEVO = se entrena con TODAS las filas (originales + densificadas)
             de los MISMOS perfiles de entrenamiento
     Ambos se evaluan sobre los MISMOS perfiles retenidos, que ninguno ha visto.

Se reporta sobre dos conjuntos de test:
  (a) CONDICIONES ORIGINALES (3 velocidades, angulos pares) -> comparacion
      manzana-con-manzana: el terreno para el que se diseno el modelo actual.
  (b) TODAS las condiciones (6 velocidades, paso 1 grado) -> el terreno real de uso
      del dashboard desde la feature C5, donde el usuario pide velocidades intermedias.

  python reentreno_densif.py            # comparacion + entrena y guarda
  python reentreno_densif.py --solo-cv  # solo la comparacion, no guarda modelos
"""
import os, sys, json, time, argparse, hashlib
import numpy as np
import pandas as pd
import joblib
from xgboost import XGBRegressor
from sklearn.model_selection import GroupKFold
from scipy.stats import spearmanr

BASE = os.path.dirname(os.path.abspath(__file__))
MERGED = os.path.join(BASE, "airfoil_dataset_densif_merged.csv")
CHORD_MIN = 150.0
SUF = "_densif"

from feature_utils import SHAPE, FEATURES, add_derived

# Config IDENTICA a produccion (eda_ml_filtrado150.mk): no se cambia nada del modelo,
# para que la unica variable del experimento sean LOS DATOS.
LD_TUNED = dict(n_estimators=400, learning_rate=0.02, max_depth=10,
                min_child_weight=5, subsample=0.6, colsample_bytree=0.9,
                reg_alpha=0.5, reg_lambda=5.0, random_state=42, n_jobs=-1)


def mk(tgt):
    if tgt == "LD":
        return XGBRegressor(**LD_TUNED)
    return XGBRegressor(n_estimators=400, learning_rate=0.05, max_depth=5,
                        subsample=0.8, colsample_bytree=0.8, random_state=42, n_jobs=-1)


def spearman_cond(frame, y, p):
    """Calidad de RANKING dentro de cada condicion (alpha, velocidad): es lo que le
    importa a la inversa, que compara perfiles entre si a igualdad de condicion."""
    t = frame[["alpha_deg", "velocidad_kmh"]].copy()
    t["r"], t["p"] = y, p
    rr = [spearmanr(g["r"], g["p"]).correlation
          for _, g in t.groupby(["alpha_deg", "velocidad_kmh"]) if len(g) >= 5]
    rr = [r for r in rr if np.isfinite(r)]
    return float(np.mean(rr)) if rr else float("nan")


def metricas(frame, y, p):
    mae = float(np.mean(np.abs(y - p)))
    ss_res = float(np.sum((y - p) ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    return mae, r2, spearman_cond(frame, y, p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--solo-cv", action="store_true", help="no guarda los modelos")
    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    # huella de produccion ANTES
    PROD_FILES = ("airfoil_dataset.csv", "modelo_LD_inversa_xgb.joblib",
                  "modelo_CD_xgb.joblib", "modelo_CL_xgb.joblib",
                  "ensemble_ld_sigma.joblib", "modelo_LD_inversa_meta.json")
    antes = {}
    for f in PROD_FILES:
        p = os.path.join(BASE, f)
        antes[f] = (os.path.getsize(p),
                    hashlib.md5(open(p, "rb").read()).hexdigest()
                    if os.path.getsize(p) < 25e6 else "(grande)")

    df = pd.read_csv(MERGED)
    ok = add_derived(df[df["status"] == "ok"].copy())
    d = ok[ok["chord_length_mm"] >= CHORD_MIN].reset_index(drop=True)
    d["es_densif"] = d["source"].astype(str).str.endswith(SUF)

    print("=" * 104)
    print("DATASET FUSIONADO (status ok, cuerda>=150)")
    print("=" * 104)
    print("   filas: %s  | perfiles: %s" % (format(len(d), ","), format(d.run_id.nunique(), ",")))
    print("   originales: %s   densificadas: %s"
          % (format(int((~d.es_densif).sum()), ","), format(int(d.es_densif.sum()), ",")))

    X = d[FEATURES].values
    grupos = d["run_id"].values
    gkf = GroupKFold(n_splits=5)
    folds = list(gkf.split(X, groups=grupos))

    # ---- CV: BASE (solo filas originales) vs NUEVO (todas), MISMO test ----
    print("\n" + "=" * 104)
    print("COMPARACION POR VALIDACION CRUZADA (GroupKFold 5 por run_id)")
    print("   BASE  = entrenado solo con las filas ORIGINALES de los perfiles de train")
    print("   NUEVO = entrenado con originales + densificadas de LOS MISMOS perfiles")
    print("   Ambos evaluados sobre los MISMOS perfiles retenidos.")
    print("=" * 104)

    oof = {t: {"base": np.full(len(d), np.nan), "nuevo": np.full(len(d), np.nan)}
           for t in ("CL", "CD", "LD")}
    t0 = time.time()
    for i, (tr, te) in enumerate(folds, 1):
        tr_base = tr[~d.es_densif.values[tr]]
        for tgt in ("CL", "CD", "LD"):
            y = d[tgt].values
            m1 = mk(tgt); m1.fit(X[tr_base], y[tr_base])
            oof[tgt]["base"][te] = m1.predict(X[te])
            m2 = mk(tgt); m2.fit(X[tr], y[tr])
            oof[tgt]["nuevo"][te] = m2.predict(X[te])
        print("   fold %d/5 listo  (%d perfiles test, train base %s / nuevo %s filas) [%.0f s]"
              % (i, len(np.unique(grupos[te])), format(len(tr_base), ","),
                 format(len(tr), ","), time.time() - t0))
        sys.stdout.flush()

    subsets = [("CONDICIONES ORIGINALES (3 vel, angulos pares)", ~d.es_densif.values),
               ("TODAS LAS CONDICIONES (6 vel, paso 1 grado)", np.ones(len(d), bool))]
    resumen = {}
    for nombre, mask in subsets:
        print("\n" + "-" * 104)
        print("TEST SOBRE: %s   (%s filas)" % (nombre, format(int(mask.sum()), ",")))
        print("-" * 104)
        print("   %-5s %-26s %-11s %-11s %-11s %s"
              % ("tgt", "metrica", "BASE", "NUEVO", "delta", "veredicto"))
        for tgt in ("CL", "CD", "LD"):
            fr = d[mask]
            y = d[tgt].values[mask]
            mb = metricas(fr, y, oof[tgt]["base"][mask])
            mn = metricas(fr, y, oof[tgt]["nuevo"][mask])
            resumen[(nombre, tgt)] = (mb, mn)
            for j, (et, mejor_si_baja) in enumerate(
                    [("MAE", True), ("R2", False), ("Spearman por condicion", False)]):
                b, n = mb[j], mn[j]
                dlt = n - b
                pct = 100 * dlt / abs(b) if b else 0
                mejora = (dlt < 0) if mejor_si_baja else (dlt > 0)
                ver = "MEJORA" if abs(pct) > 1 and mejora else (
                      "empeora" if abs(pct) > 1 else "igual")
                fmt = "%.5f" if et == "MAE" and tgt == "CD" else "%.4f"
                print("   %-5s %-26s %-11s %-11s %-11s %s"
                      % (tgt if j == 0 else "", et, fmt % b, fmt % n,
                         "%+.1f%%" % pct, ver))

    if args.solo_cv:
        print("\n[--solo-cv] no se guardan modelos.")
        return 0

    # ---- entrenamiento FINAL sobre todo el fusionado + guardado ----
    print("\n" + "=" * 104)
    print("ENTRENAMIENTO FINAL (todo el fusionado) Y GUARDADO")
    print("=" * 104)
    nombres = {"CL": "modelo_CL_densif.joblib", "CD": "modelo_CD_densif.joblib",
               "LD": "modelo_LD_inversa_densif.joblib"}
    for tgt in ("CL", "CD", "LD"):
        m = mk(tgt); m.fit(X, d[tgt].values)
        mb, mn = resumen[("TODAS LAS CONDICIONES (6 vel, paso 1 grado)", tgt)]
        meta = {"target": tgt, "features": FEATURES, "dataset": "densif_merged_150_500",
                "n_perfiles": int(d.run_id.nunique()), "n_filas_ok": int(len(d)),
                "cv_groupkfold5": {"mae": mn[0], "r2": mn[1], "spearman_cond": mn[2]},
                "cv_base_solo_originales": {"mae": mb[0], "r2": mb[1], "spearman_cond": mb[2]},
                "nota": "Entrenado sobre el dataset densificado. NO es produccion."}
        joblib.dump({"model": m, "meta": meta}, os.path.join(BASE, nombres[tgt]))
        print("   [OK] %s" % nombres[tgt])

    # ---- ensemble de sigma ----
    print("\n   ensemble de sigma (10 miembros, bootstrap de PERFILES)...")
    perfiles = d.run_id.unique()
    ens = []
    t0 = time.time()
    idx_por_perfil = {r: g.index.values for r, g in d.groupby("run_id")}
    for m_i in range(10):
        rng = np.random.RandomState(1000 + m_i)
        boot = pd.unique(rng.choice(perfiles, size=len(perfiles), replace=True))
        idx = np.concatenate([idx_por_perfil[r] for r in boot])
        mdl = XGBRegressor(random_state=1000 + m_i, **{k: v for k, v in LD_TUNED.items()
                                                       if k != "random_state"})
        mdl.fit(X[idx], d["LD"].values[idx])
        ens.append(mdl)
        print("      miembro %2d/10 (%d perfiles, %s filas) [%.0f s]"
              % (m_i + 1, len(boot), format(len(idx), ","), time.time() - t0))
        sys.stdout.flush()
    joblib.dump(ens, os.path.join(BASE, "ensemble_ld_sigma_densif.joblib"))
    print("   [OK] ensemble_ld_sigma_densif.joblib")

    # ---- produccion intacta ----
    print("\n" + "=" * 104)
    print("PRODUCCION INTACTA (md5 antes vs despues)")
    print("=" * 104)
    for f, (sz0, h0) in antes.items():
        p = os.path.join(BASE, f)
        sz1 = os.path.getsize(p)
        h1 = hashlib.md5(open(p, "rb").read()).hexdigest() if sz1 < 25e6 else "(grande)"
        print("   %-32s %13s B   %s"
              % (f, format(sz1, ","), "OK" if (sz0 == sz1 and h0 == h1) else "MODIFICADO"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
