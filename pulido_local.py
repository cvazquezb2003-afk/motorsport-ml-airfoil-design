"""Can a cheap local polish close the gap between the deployed search and the validated one?

`comprueba_buscador.py` establishes the problem: the Sobol sweep the web runs is worse
than the differential evolution that produced the published 2.8%, in 40 cases out of 40.
The obvious hope is that the sweep lands *near* the right answer and just fails to
resolve it -- in which case a local refinement from the Sobol best, costing a fraction of
DE's ~150 s per case, would recover it and the deployed path could inherit the validation.

This script tests that hope. It does not survive.

    python build_ensemble.py        # once: the 106 MB ensemble is not in the repo
    python pulido_local.py

Read-only. Touches no model, no dataset, no result file. Takes ~20 min: Powell is
derivative-free and spends hundreds of objective evaluations per case.

--- WHY TWO POLISHES AND NOT ONE ---
L-BFGS-B is the natural first choice and the one worth reporting. But the objective is a
bootstrap ensemble of gradient-boosted TREES: J is piecewise constant, and its gradient is
exactly zero almost everywhere. A finite-difference step only sees a slope if it happens to
cross a split in the trees. So L-BFGS can stop at the first iteration, believing it has
converged, without having moved at all -- and a reader would not be able to tell whether the
polish failed or the gradient did. Powell is derivative-free and does not depend on that, so
running both separates the two explanations.

Watch `nfev` in the output. For L-BFGS it comes out at 7 = d+1 in every single case: one
finite-difference gradient, all zeros, done.

--- WHAT THE ANSWER TURNS OUT TO BE ---
Neither polish reaches DE. L-BFGS cannot start; Powell moves but usually uphill, because on
a stepped surface its line search accepts moves across the flat regions and nothing rejects
the final extrapolation. Two different local methods failing from the same start is the
evidence that matters: the gap is not resolution near a shared optimum, it is a different
basin. That is why the published 2.8% cannot simply be transferred to the deployed path.
"""
import os
import sys
import json
import time

import numpy as np
from scipy.optimize import minimize

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import inversa_service as S

K = 2.0
RESULTADOS = os.path.join(BASE, "bateria_densif_k2_resultados.json")

FREE, FIDX = S._FREE, S._FREE_IDX
RANGO = {k: float(S._P95[k] - S._P05[k]) for k in FREE}
BOUNDS = [(float(S._P05[k]), float(S._P95[k])) for k in FREE]


def _X(xfree, chord, a, v):
    x = np.zeros((1, 7))
    x[0, 0] = chord
    for j, idx in enumerate(FIDX):
        x[0, idx] = xfree[j]
    return S._arma_X(x, a, v)


def objetivo(xfree, chord, a, v):
    """J = mean_ensemble + K*sigma. Minimised (L/D is negative for inverted wings)."""
    mu, sd = S._ens_stats(_X(xfree, chord, a, v))
    return float(mu[0] + K * sd[0])


def detalle(xfree, chord, a, v):
    """(sigma, J, LD_pred) at one point and one angle."""
    X = _X(xfree, chord, a, v)
    mu, sd = S._ens_stats(X)
    return float(sd[0]), float(mu[0] + K * sd[0]), float(S._LD.predict(X)[0])


def _dist(xfree, de):
    """Per-parameter |x - x_DE| normalised by the p5-p95 span."""
    d = {k: abs(float(xfree[i]) - float(de[k])) / RANGO[k] for i, k in enumerate(FREE)}
    return float(np.mean(list(d.values()))), d


def bloque(nombre, filas, kj, ksd, kld, kdist, kt):
    j = np.array([f[kj] for f in filas])
    jd = np.array([f["j_de"] for f in filas])
    d = j - jd
    tol = 1e-6
    dist = np.array([f[kdist] for f in filas])
    sd = np.array([f[ksd] for f in filas])
    sdd = np.array([f["sd_de"] for f in filas])
    t = np.array([f[kt] for f in filas])
    print()
    print("   --- %s ---" % nombre)
    print("     matches or beats J_DE : %2d / %d   (better %2d, tie %2d, worse %2d)"
          % (int((d <= tol).sum()), len(filas), int((d < -tol).sum()),
             int((np.abs(d) <= tol).sum()), int((d > tol).sum())))
    print("     J gap      : median %+.4f   min %+.4f   max %+.4f"
          % (np.median(d), d.min(), d.max()))
    print("     as %% |J_DE|: median %+.3f%%   worst %+.3f%%"
          % (100 * np.median(d / np.abs(jd)), 100 * (d / np.abs(jd)).max()))
    print("     param dist vs DE (mean of 6): median %.1f%%   max %.1f%%"
          % (100 * np.median(dist), 100 * dist.max()))
    print("     sigma      : median %.4f  (DE %.4f)   gap %+.4f"
          % (np.median(sd), np.median(sdd), np.median(sd - sdd)))
    print("     |L/D| pred : median %.2f  (DE %.2f)"
          % (np.median([abs(f[kld]) for f in filas]),
             np.median([abs(f["ld_de"]) for f in filas])))
    print("     time       : median %.2f s   max %.2f s   (per case, ONE angle)"
          % (np.median(t), t.max()))


def main():
    res = json.load(open(RESULTADOS, encoding="utf-8"))

    print("=" * 96)
    print("LOCAL POLISH from the Sobol best -- 40 cases, angle pinned")
    print("=" * 96)
    print("   J = mean_ens + 2*sigma, MINIMISED. Lower is better. Reference: J_DE.")
    print("   nfev = objective evaluations. L-BFGS at d+1 = 7 means it never moved.")
    print()
    print("   %-4s | %9s %9s %9s %9s | %7s %7s | %6s %6s"
          % ("case", "J_DE", "J_Sobol", "J_LBFGS", "J_Powell",
             "t_lbfgs", "t_powll", "nf_L", "nf_P"))
    print("   " + "-" * 90)

    filas = []
    for c in res:
        ch, v, a = float(c["cuerda"]), float(c["vel"]), -abs(float(c["alpha"]))
        de = json.load(open(os.path.join(BASE, c["json"]), encoding="utf-8"))["user_params"]
        sd_de, j_de, ld_de = detalle([float(de[k]) for k in FREE], ch, a, v)

        t0 = time.perf_counter()
        o = S.optimizar(ch, a, a, v_kmh=v)
        t_sob = time.perf_counter() - t0
        x0 = np.array([float(o["shape_params"][k]) for k in FREE])
        sd_sb, j_sb, ld_sb = detalle(x0, ch, a, v)

        t0 = time.perf_counter()
        rl = minimize(objetivo, x0, args=(ch, a, v), method="L-BFGS-B", bounds=BOUNDS)
        t_l = time.perf_counter() - t0
        sd_l, j_l, ld_l = detalle(rl.x, ch, a, v)

        t0 = time.perf_counter()
        rp = minimize(objetivo, x0, args=(ch, a, v), method="Powell", bounds=BOUNDS,
                      options={"maxfev": 3000, "xtol": 1e-4, "ftol": 1e-6})
        t_p = time.perf_counter() - t0
        sd_p, j_p, ld_p = detalle(rp.x, ch, a, v)

        dm_s, _ = _dist(x0, de)
        dm_l, _ = _dist(rl.x, de)
        dm_p, pp = _dist(rp.x, de)

        filas.append(dict(caso=c["caso"], j_de=j_de, j_sb=j_sb, j_l=j_l, j_p=j_p,
                          sd_de=sd_de, sd_sb=sd_sb, sd_l=sd_l, sd_p=sd_p,
                          ld_de=ld_de, ld_sb=ld_sb, ld_l=ld_l, ld_p=ld_p,
                          dm_s=dm_s, dm_l=dm_l, dm_p=dm_p, por_par=pp,
                          t_sob=t_sob, t_l=t_l, t_p=t_p,
                          nf_l=int(rl.nfev), nf_p=int(rp.nfev)))
        print("   %-4s | %9.4f %9.4f %9.4f %9.4f | %6.2fs %6.2fs | %6d %6d"
              % (c["caso"], j_de, j_sb, j_l, j_p, t_l, t_p, rl.nfev, rp.nfev))

    print()
    print("=" * 96)
    print("SUMMARY")
    print("=" * 96)
    bloque("SOBOL only (what the web does today)", filas, "j_sb", "sd_sb", "ld_sb", "dm_s", "t_sob")
    bloque("SOBOL + L-BFGS-B", filas, "j_l", "sd_l", "ld_l", "dm_l", "t_l")
    bloque("SOBOL + POWELL", filas, "j_p", "sd_p", "ld_p", "dm_p", "t_p")

    nf = np.array([f["nf_l"] for f in filas])
    print()
    print("   --- DID L-BFGS MOVE AT ALL? ---")
    print("     nfev: min %d, max %d, all equal to d+1=7 in %d / %d cases"
          % (nf.min(), nf.max(), int((nf == len(FREE) + 1).sum()), len(filas)))
    print("     J identical to plain Sobol in %d / %d cases"
          % (int((np.abs([f["j_l"] - f["j_sb"] for f in filas]) <= 1e-12).sum()), len(filas)))
    print("     -> a zero gradient on a piecewise-constant objective, as expected.")

    print()
    print("   --- COST IN A WEB REQUEST ---")
    print("     the real endpoint sweeps a BAND of angles (typically 6), not one.")
    for nom, kt in (("Sobol", "t_sob"), ("L-BFGS", "t_l"), ("Powell", "t_p")):
        t = np.median([f[kt] for f in filas])
        print("     %-7s  1 angle: %5.2f s   x6 angles: %5.2f s" % (nom, t, 6 * t))

    print()
    print("   per parameter, normalised distance Powell vs DE:")
    for k in FREE:
        dd = np.array([f["por_par"][k] for f in filas])
        print("     %-30s median %5.1f%%   max %5.1f%%" % (k, 100 * np.median(dd), 100 * dd.max()))


if __name__ == "__main__":
    main()
