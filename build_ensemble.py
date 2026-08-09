"""
REGENERA ensemble_ld_sigma.joblib EN EL BUILD DEL DESPLIEGUE.

Por que existe
--------------
El ensemble pesa 106 MB y el limite DURO de GitHub son 100 MiB: no puede ir al
repo (esta en .gitignore). Como es el artefacto mas barato de reproducir del
proyecto (~1 min), se regenera durante el `docker build` a partir del dataset de
entrenamiento, que si cabe (13,4 MB).

⚠️ POR QUE **NO** SE USA winner_curse.py PARA ESTO
--------------------------------------------------
Seria lo intuitivo — winner_curse.py entrena el ensemble si no lo encuentra — y
seria un ERROR SILENCIOSO: ese script lee `airfoil_dataset.csv`, que es el
CATALOGO de 20.349 filas, no el dataset de entrenamiento. El ensemble de
produccion se entreno sobre `airfoil_dataset_densif_merged.csv` (63.496 filas ok)
en reentreno_densif.py, y se promociono renombrando.

Regenerar con winner_curse.py produciria un ensemble PRE-DENSIF bajo el nombre de
produccion: 64 MB en vez de 106, sigma distinta, y la bateria de validacion
dejaria de describir el modelo desplegado. Sin ningun error a la vista.

Este script replica EXACTAMENTE el bloque de reentreno_densif.py: mismo dataset,
mismo filtro, mismas 11 features, M=10, semillas 1000+i, mismos hiperparametros y
mismo bootstrap POR PERFIL (no por filas).
"""
import os
import sys
import time

import joblib
import numpy as np
import pandas as pd
from xgboost import XGBRegressor

from feature_utils import FEATURES, f_alpha_over_sqrtre, f_te_rel
from rutas import BASE

MERGED = os.path.join(BASE, "airfoil_dataset_densif_merged.csv")
SALIDA = os.path.join(BASE, "ensemble_ld_sigma.joblib")

# Identicos a reentreno_densif.py / eda_ml_filtrado150.py, que son los que
# entrenaron el ensemble de PRODUCCION. Verificado contra los parametros que el
# propio .joblib lleva guardados (subsample 0.6, min_child_weight 5,
# reg_lambda 5.0), no copiados de otro script.
#
# ⚠️ winner_curse.py define un LD_TUNED DISTINTO (subsample 0.9,
# min_child_weight 3, reg_lambda 1.0). Copiarlo de ahi -- que es lo que se hizo
# en el primer intento -- da un ensemble de 156 MB con una sigma un 24% mayor:
# mismo nombre de fichero, misma pinta, otro modelo. Cualquier cambio en esta
# linea cambia sigma y deja de valer la bateria de validacion.
LD_TUNED = dict(n_estimators=400, learning_rate=0.02, max_depth=10,
                min_child_weight=5, subsample=0.6, colsample_bytree=0.9,
                reg_alpha=0.5, reg_lambda=5.0, random_state=42, n_jobs=-1)
M = 10


def main():
    if os.path.exists(SALIDA):
        print("[ENSEMBLE] ya existe, no se regenera: %s" % SALIDA)
        return 0
    if not os.path.exists(MERGED):
        print("[ERROR] falta el dataset de entrenamiento: %s\n"
              "        sin el no se puede regenerar el ensemble." % MERGED,
              file=sys.stderr)
        return 1

    df = pd.read_csv(MERGED)
    d = df[(df.status == "ok") & (df.chord_length_mm >= 150)].copy()
    d["alpha_over_sqrtre"] = f_alpha_over_sqrtre(d["alpha_deg"], d["reynolds"])
    d["te_rel"] = f_te_rel(d["trailing_edge_thickness_mm"], d["chord_length_mm"])
    d = d.reset_index(drop=True)
    X = d[FEATURES].values
    y = d["LD"].values
    print("[ENSEMBLE] %s filas ok, %d perfiles, %d features"
          % (format(len(d), ","), d.run_id.nunique(), len(FEATURES)))

    perfiles = d.run_id.unique()
    idx_por_perfil = {r: g.index.values for r, g in d.groupby("run_id")}
    ens, t0 = [], time.time()
    for i in range(M):
        rng = np.random.RandomState(1000 + i)          # bootstrap DE PERFILES
        boot = pd.unique(rng.choice(perfiles, size=len(perfiles), replace=True))
        idx = np.concatenate([idx_por_perfil[r] for r in boot])
        mdl = XGBRegressor(random_state=1000 + i,
                           **{k: v for k, v in LD_TUNED.items()
                              if k != "random_state"})
        mdl.fit(X[idx], y[idx])
        ens.append(mdl)
        print("   miembro %2d/%d  (%d perfiles, %s filas)  [%.0f s]"
              % (i + 1, M, len(boot), format(len(idx), ","), time.time() - t0))
        sys.stdout.flush()

    joblib.dump(ens, SALIDA)
    print("[OK] %s  (%.1f MB, %.0f s)"
          % (os.path.basename(SALIDA), os.path.getsize(SALIDA) / 1024 / 1024,
             time.time() - t0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
