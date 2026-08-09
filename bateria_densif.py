"""
BATERIA DE REVALIDACION con los modelos DENSIF — ETAPA A (portable, sin CATIA).

Repite las 40 propuestas de la bateria del 24/07 (k=0 y k=2 por caso = 80 geometrias)
pero con los modelos entrenados sobre el dataset densificado:
    modelo_LD_inversa_densif.joblib
    ensemble_ld_sigma_densif.joblib
    bounds p5-p95 sobre airfoil_dataset_densif_merged.csv filtrado >=150

OBJETIVO: ver si k=2 sigue dando ~3.8% de error o hay que recalibrar k.

--- QUE SE CONSERVA IGUAL Y POR QUE ---
Los MISMOS 40 casos (cuerda, velocidad, angulo) que la bateria del 24/07, leidos de sus
resultados para que no haya forma de que difieran. Y el MISMO optimizador: DE estandar,
workers=1, maxiter=200 (k=0) / 150 (k=2), seed=42, sin vectorizar. Se midio que
`vectorized=True` cambia el optimo (updating deferred vs immediate: dif J = 2.2e-02) y
que `inplace_predict` lo preserva pero solo acelera un 13%. Cambiar el optimizador
habria roto la comparabilidad con la evidencia de julio, que es justo lo que esta
tirada existe para comparar.

--- QUE NO SE PISA ---
Nada de la bateria original. Ficheros propios con prefijo `bateria_densif_` y configs
`dsf_*.json`; los `tr_*.json` / `tre_*.json` y los `bateria_tereal_*` del 24/07 quedan
intactos como evidencia de referencia.

REANUDABLE: el indice se vuelca tras CADA caso; al relanzar se saltan los ya hechos.

    python bateria_densif.py            # etapa A completa (~3.4 h)
    python bateria_densif.py --limite N  # solo los N primeros casos (prueba)
"""
import os, sys, json, time, argparse
import numpy as np
import pandas as pd
import joblib
from scipy.optimize import differential_evolution

BASE = os.path.dirname(os.path.abspath(__file__))
RHO, MU = 1.225, 1.81e-5
CHORD_MIN = 150.0

MODEL = os.path.join(BASE, "modelo_LD_inversa_densif.joblib")
ENS = os.path.join(BASE, "ensemble_ld_sigma_densif.joblib")
DATASET = os.path.join(BASE, "airfoil_dataset_densif_merged.csv")
IDX = {"k0": os.path.join(BASE, "bateria_densif_k0_index.json"),
       "k2": os.path.join(BASE, "bateria_densif_k2_index.json")}
# los 40 casos se leen de la bateria del 24/07 (solo LECTURA)
CASOS_REF = os.path.join(BASE, "bateria_tereal_k0_resultados.json")

from feature_utils import SHAPE, f_alpha_over_sqrtre, f_te_rel


def reynolds(c, v):
    return RHO * (v / 3.6) * (c / 1000.0) / MU


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limite", type=int, default=None)
    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    casos = [(c["caso"], int(c["cuerda"]), int(c["vel"]), int(c["alpha"]))
             for c in json.load(open(CASOS_REF, encoding="utf-8"))]
    casos.sort()
    if args.limite:
        casos = casos[:args.limite]

    prod = joblib.load(MODEL)["model"]
    ens = joblib.load(ENS)
    df = pd.read_csv(DATASET)
    ok = df[(df.status == "ok") & (df.chord_length_mm >= CHORD_MIN)]
    per = ok.groupby("run_id")[SHAPE].first()
    P05, P95 = per.quantile(0.05), per.quantile(0.95)
    free = [k for k in SHAPE if k != "chord_length_mm"]
    fidx = [SHAPE.index(k) for k in free]
    bounds = [(float(P05[k]), float(P95[k])) for k in free]

    print("=" * 112)
    print("BATERIA DENSIF — ETAPA A (solo inversa, sin CATIA)")
    print("   modelo   : modelo_LD_inversa_densif.joblib")
    print("   ensemble : ensemble_ld_sigma_densif.joblib (%d miembros)" % len(ens))
    print("   bounds   : p5-p95 sobre %s (%s perfiles >=150)"
          % (os.path.basename(DATASET), format(per.shape[0], ",")))
    print("   casos    : %d  ->  %d geometrias para la etapa B" % (len(casos), 2 * len(casos)))
    print("=" * 112)

    # --- reanudable ---
    hechos = {}
    for tag in ("k0", "k2"):
        if os.path.exists(IDX[tag]):
            hechos[tag] = {e["caso"]: e for e in json.load(open(IDX[tag], encoding="utf-8"))}
        else:
            hechos[tag] = {}
    ya = set(hechos["k0"]) & set(hechos["k2"])
    if ya:
        print("[REANUDA] %d casos ya propuestos -> se saltan\n" % len(ya))

    def arma_X(vec, chord, alpha, v):
        shape = np.zeros(7); shape[0] = chord
        for j, idx in enumerate(fidx):
            shape[idx] = vec[j]
        re = reynolds(chord, v)
        X = np.array([list(shape) + [alpha, re, f_alpha_over_sqrtre(alpha, re),
                                     f_te_rel(shape[4], chord)]])
        return X, shape

    def ens_stats(X):
        P = np.stack([m.predict(X) for m in ens])
        return P.mean(axis=0)[0], P.std(axis=0)[0]

    print("%-5s%5s%5s%4s%11s | %9s%9s%8s | %s"
          % ("caso", "c", "v", "a", "Re", "LD_k0", "LD_k2", "sigma", "tiempo"))
    t0 = time.time()
    n_hechos = 0
    for caso, chord, v, a in casos:
        if caso in ya:
            e0, e2 = hechos["k0"][caso], hechos["k2"][caso]
            print("%-5d%5d%5d%4d%11d | %9.2f%9.2f%8.2f | (ya hecho)"
                  % (caso, chord, v, a, e0["Re"], e0["LD_pred"], e2["LD_pred"],
                     e2.get("sigma", float("nan"))))
            continue
        tc = time.time()

        def obj0(x):
            X, _ = arma_X(x, chord, a, v)
            return prod.predict(X)[0]
        r0 = differential_evolution(obj0, bounds, seed=42, maxiter=200, tol=1e-7,
                                    polish=True, workers=1)
        _, sh0 = arma_X(r0.x, chord, a, v)
        ld_k0 = float(r0.fun)

        def obj2(x):
            X, _ = arma_X(x, chord, a, v)
            mu, sd = ens_stats(X)
            return mu + 2.0 * sd
        r2 = differential_evolution(obj2, bounds, seed=42, maxiter=150, tol=1e-7,
                                    polish=True, workers=1)
        X2, sh2 = arma_X(r2.x, chord, a, v)
        mu2, sd2 = ens_stats(X2)
        ld_k2 = float(prod.predict(X2)[0])

        re = int(round(reynolds(chord, v)))
        for tag, sh in (("k0", sh0), ("k2", sh2)):
            up = {k: round(float(val), 6) for k, val in zip(SHAPE, sh)}
            up["chord_angle_deg"] = 350.0
            fn = f"dsf_{tag}_{caso}_c{chord}_v{v}_a{abs(a)}.json"
            json.dump({"user_params": up, "velocidad_kmh": v, "alphas": [a]},
                      open(os.path.join(BASE, fn), "w", encoding="utf-8"), indent=2)
            entry = {"caso": caso, "cuerda": chord, "vel": v, "alpha": a, "Re": re,
                     "json": fn, "LD_pred": ld_k0 if tag == "k0" else ld_k2}
            if tag == "k2":
                entry["sigma"] = float(sd2)
                entry["mean_ens"] = float(mu2)
            hechos[tag][caso] = entry
        # VOLCADO INCREMENTAL tras cada caso -> reanudable
        for tag in ("k0", "k2"):
            json.dump([hechos[tag][c] for c in sorted(hechos[tag])],
                      open(IDX[tag], "w", encoding="utf-8"), indent=2)
        n_hechos += 1
        el = time.time() - t0
        print("%-5d%5d%5d%4d%11d | %9.2f%9.2f%8.2f | %.0f s  (media %.0f s, quedan ~%.0f min)"
              % (caso, chord, v, a, re, ld_k0, ld_k2, sd2, time.time() - tc,
                 el / n_hechos, (len(casos) - len(ya) - n_hechos) * el / n_hechos / 60))
        sys.stdout.flush()

    print("\n" + "=" * 112)
    k0 = json.load(open(IDX["k0"], encoding="utf-8"))
    k2 = json.load(open(IDX["k2"], encoding="utf-8"))
    print("[OK] ETAPA A COMPLETADA en %.1f min" % ((time.time() - t0) / 60))
    print("   propuestas: k=0 %d | k=2 %d  ->  %d configuraciones JSON para la etapa B"
          % (len(k0), len(k2), len(k0) + len(k2)))
    print("   indices: %s | %s"
          % (os.path.basename(IDX["k0"]), os.path.basename(IDX["k2"])))
    print("   CATIA NO tocado. Bateria del 24/07 NO tocada.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
