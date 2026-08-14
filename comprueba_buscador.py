"""Does the deployed search find the same optima as the one that was validated?

The published 2.8% error was measured on 40 geometries built in CATIA and solved in
XFOIL. Those geometries were proposed by `differential_evolution` (bateria_densif.py).
The web app does NOT use differential evolution: `inversa_service.optimizar` sweeps a
Sobol sequence of 32,768 candidates and takes the argmin, because DE costs ~2.5 min per
case and a web request cannot wait that long.

Same objective, same k, same bounds, same models -- different search. This script asks
the obvious question nobody had asked: do the two searches land in the same place?

    python build_ensemble.py        # once: the 106 MB ensemble is not in the repo
    python comprueba_buscador.py

Read-only. Touches no model, no dataset, no result file.

--- WHY THE ANGLE IS PINNED ---
There are two known differences between the two paths, not one: the search algorithm,
and the fact that the battery optimised at a single fixed angle while the web averages
J over a band of angles. Calling optimizar() with a_from == a_to degenerates the band to
one angle, which cancels the second difference and isolates the first. Otherwise a
disagreement would be unattributable.

--- WHY THE TWO GUARDS ---
A comparison that cannot fail proves nothing. Guard 1 checks that the degenerate band
really does yield one angle (with a real band as a control, so the check itself can
fail). Guard 2 rebuilds J_DE from the stored per-case JSON files and requires it to
match what the battery reported -- if the reconstruction is wrong, every number below is
meaningless. Both are hard exits, not warnings.
"""
import os
import sys
import json
import time

import numpy as np

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import inversa_service as S
from feature_utils import SHAPE

K = 2.0                                   # same penalty as the published battery
RESULTADOS = os.path.join(BASE, "bateria_densif_k2_resultados.json")

FREE = S._FREE
RANGO = {k: float(S._P95[k] - S._P05[k]) for k in FREE}   # p5-p95 span, for normalising


def j_en(shape_dict, alpha_neg, vel):
    """(mean_ens, sigma, J, LD_pred) of one geometry at one angle. J = mean + K*sigma."""
    x = np.array([[float(shape_dict[k]) for k in SHAPE]])
    X = S._arma_X(x, alpha_neg, vel)
    mu, sd = S._ens_stats(X)
    return float(mu[0]), float(sd[0]), float(mu[0] + K * sd[0]), float(S._LD.predict(X)[0])


def guarda_1():
    """A pinned angle must give exactly one angle -- with a real band as control."""
    print("=" * 78)
    print("GUARD 1 -- does a_from == a_to really give ONE angle?")
    print("=" * 78)
    ok = True
    for lo, hi in ((-6.0, -6.0), (-8.0, -8.0), (-14.0, -9.0), (-12.0, -12.0)):
        g = S._grid_angulos(lo, hi, 1.0)
        print("   _grid_angulos(%6.1f, %6.1f) -> n=%d  %s   [%s]"
              % (lo, hi, len(g), np.round(g, 2),
                 "pinned" if lo == hi else "real band (control)"))
        if lo == hi and len(g) != 1:
            ok = False
    r = S.optimizar(300.0, -6.0, -6.0, v_kmh=180.0)
    print("   optimizar(300, -6, -6) -> n_angulos = %d" % r["n_angulos"])
    return ok and r["n_angulos"] == 1


def guarda_2(res, n=4):
    """J_DE rebuilt from the JSON files must reproduce what the battery reported."""
    print()
    print("=" * 78)
    print("GUARD 2 -- does J_DE rebuilt from the JSON match the battery?")
    print("=" * 78)
    print("   cases on file: %d" % len(res))
    print()
    print("   %-5s | %-33s | %-33s" % ("case", "REPORTED by the battery", "REBUILT from the JSON"))
    print("   %-5s | %10s %8s %10s | %10s %8s %10s"
          % ("", "mean_ens", "sigma", "LD_pred", "mean_ens", "sigma", "LD_pred"))
    print("   " + "-" * 84)
    peor = 0.0
    for c in res[:n]:
        cfg = json.load(open(os.path.join(BASE, c["json"]), encoding="utf-8"))["user_params"]
        mu, sd, _, ld = j_en(cfg, -abs(float(c["alpha"])), float(c["vel"]))
        d = max(abs(mu - c["mean_ens"]), abs(sd - c["sigma"]), abs(ld - c["LD_pred"]))
        peor = max(peor, d)
        print("   %-5s | %10.5f %8.5f %10.5f | %10.5f %8.5f %10.5f   max dif %.2e"
              % (c["caso"], c["mean_ens"], c["sigma"], c["LD_pred"], mu, sd, ld, d))
    print()
    print("   worst discrepancy: %.2e" % peor)
    return peor <= 1e-4


def main():
    if not guarda_1():
        sys.exit("\n*** GUARD 1 FAILED: the comparison would not isolate the search. ***")
    print("   OK")

    res = json.load(open(RESULTADOS, encoding="utf-8"))
    if not guarda_2(res):
        sys.exit("\n*** GUARD 2 FAILED: the JSON files do not reproduce the battery. ***")
    print("   OK")

    print()
    print("=" * 78)
    print("COMPARISON -- 40 cases, same objective, same angle, same bounds")
    print("=" * 78)
    print("   J = mean_ens + 2*sigma, MINIMISED (L/D is negative). Lower J = better.")
    print()
    print("   %-4s %5s %4s %4s | %9s %9s %8s | %8s | %6s %6s"
          % ("case", "chord", "vel", "alfa", "J_DE", "J_Sobol", "dif",
             "par dist", "sig_DE", "sig_Sb"))
    print("   " + "-" * 92)

    filas = []
    t0 = time.perf_counter()
    for c in res:
        ch, v, a = float(c["cuerda"]), float(c["vel"]), -abs(float(c["alpha"]))
        de = json.load(open(os.path.join(BASE, c["json"]), encoding="utf-8"))["user_params"]
        _, sd_de, j_de, ld_de = j_en(de, a, v)

        o = S.optimizar(ch, a, a, v_kmh=v)
        sb = o["shape_params"]
        _, sd_sb, j_sb, ld_sb = j_en(sb, a, v)

        por_par = {k: abs(float(sb[k]) - float(de[k])) / RANGO[k] for k in FREE}
        filas.append(dict(caso=c["caso"], j_de=j_de, j_sb=j_sb,
                          dist=float(np.mean(list(por_par.values()))),
                          dmax=float(np.max(list(por_par.values()))),
                          por_par=por_par, sd_de=sd_de, sd_sb=sd_sb,
                          ld_de=ld_de, ld_sb=ld_sb))
        print("   %-4s %5.0f %4.0f %4.0f | %9.4f %9.4f %+8.4f | %7.1f%% | %6.4f %6.4f"
              % (c["caso"], ch, v, a, j_de, j_sb, j_sb - j_de,
                 100 * filas[-1]["dist"], sd_de, sd_sb))
    dt = time.perf_counter() - t0

    d = np.array([f["j_sb"] - f["j_de"] for f in filas])
    jd = np.abs([f["j_de"] for f in filas])
    dist = np.array([f["dist"] for f in filas])
    dmax = np.array([f["dmax"] for f in filas])

    print()
    print("=" * 78)
    print("SUMMARY")
    print("=" * 78)
    print("   compute time: %.1f s for %d cases" % (dt, len(filas)))
    print()
    print("   J_Sobol BETTER than J_DE (lower) : %2d / %d" % (int((d < -1e-6).sum()), len(filas)))
    print("   J_Sobol equal (|dif| <= 1e-6)    : %2d / %d" % (int((np.abs(d) <= 1e-6).sum()), len(filas)))
    print("   J_Sobol WORSE than J_DE          : %2d / %d" % (int((d > 1e-6).sum()), len(filas)))
    print()
    print("   J gap : median %+.4f   best %+.4f   worst %+.4f" % (np.median(d), d.min(), d.max()))
    print("   as %% of |J_DE| : median %+.3f%%   worst %+.3f%%"
          % (100 * np.median(d / jd), 100 * (d / jd).max()))
    print()
    print("   parameter distance (normalised by the p5-p95 span):")
    print("     mean of the 6  : median %.1f%%   min %.1f%%   max %.1f%%"
          % (100 * np.median(dist), 100 * dist.min(), 100 * dist.max()))
    print("     worst parameter: median %.1f%%   max %.1f%%"
          % (100 * np.median(dmax), 100 * dmax.max()))
    print()
    print("   sigma      : DE median %.4f   Sobol median %.4f   gap %+.4f"
          % (np.median([f["sd_de"] for f in filas]),
             np.median([f["sd_sb"] for f in filas]),
             np.median([f["sd_sb"] - f["sd_de"] for f in filas])))
    print("   |L/D| pred : DE median %.2f   Sobol median %.2f"
          % (np.median([abs(f["ld_de"]) for f in filas]),
             np.median([abs(f["ld_sb"]) for f in filas])))
    print()
    print("   per parameter, normalised distance |Sobol - DE| / span:")
    for k in FREE:
        dd = np.array([f["por_par"][k] for f in filas])
        print("     %-30s median %5.1f%%   max %5.1f%%" % (k, 100 * np.median(dd), 100 * dd.max()))


if __name__ == "__main__":
    main()
