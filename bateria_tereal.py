"""
ETAPA 3 — Bateria de validacion sobre el modelo TE-real.
Replica EXACTO el metodo de la bateria actual (inversa_bateria + bateria_k2 +
bateria_ampliada), pero con:
  - modelo_LD_inversa_xgb_tereal.joblib (k=0, maxiter=200)
  - ensemble_ld_sigma_tereal.joblib     (k=2, J=mean_ens+2*sigma, maxiter=150)
  - bounds p5-p95 sobre airfoil_dataset_TEreal.csv filtrado >=150
  - VERIFICACION con pipeline TE-real: CATIA (steps 1-3) -> genera_tereal (.dat TE
    romo) -> XFOIL. NO usa asc_to_dat.py amputado.

Los MISMOS 20 casos que la bateria existente (8 orig + 12 ampliada).

  python bateria_tereal.py             -> ETAPA A (solo inversa, sin CATIA)
  python bateria_tereal.py --verificar -> ETAPA B (40 geom en CATIA + XFOIL)

No sobrescribe baterias viejas ni modelos de produccion.
"""
import os, sys, json, subprocess, shutil
import numpy as np
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
RHO, MU = 1.225, 1.81e-5
def reynolds(c, v):
    return RHO * (v / 3.6) * (c / 1000.0) / MU

# 20 casos = 8 originales + 12 ampliada (mismas cuerdas/vel/angulos)
CASOS = [
    (1, 300, 180, -6), (2, 300, 110, -6), (3, 300, 290, -8), (4, 450, 180, -6),
    (5, 450, 290, -6), (6, 450, 110, -8), (7, 180, 180, -6), (8, 180, 290, -6),
    (9, 250, 180, -6), (10, 250, 290, -8), (11, 350, 110, -6), (12, 350, 180, -8),
    (13, 320, 290, -10), (14, 420, 180, -8), (15, 420, 110, -6), (16, 480, 290, -8),
    (17, 480, 180, -6), (18, 170, 290, -6), (19, 190, 180, -4), (20, 175, 290, -2),
]

MODEL = os.path.join(BASE, "modelo_LD_inversa_xgb_tereal.joblib")
ENS = os.path.join(BASE, "ensemble_ld_sigma_tereal.joblib")


# =========================================================
# ETAPA A — inversa (sin CATIA)
# =========================================================
def etapaA():
    import joblib
    from scipy.optimize import differential_evolution
    from feature_utils import SHAPE, f_alpha_over_sqrtre, f_te_rel

    ens = joblib.load(ENS)
    prod = joblib.load(MODEL)["model"]
    df = pd.read_csv(os.path.join(BASE, "airfoil_dataset_TEreal.csv"))
    ok = df[(df.status == "ok") & (df.chord_length_mm >= 150)]
    per = ok.groupby("run_id")[SHAPE].first()
    P05, P95 = per.quantile(0.05), per.quantile(0.95)
    free_keys = [k for k in SHAPE if k != "chord_length_mm"]
    free_idx = [SHAPE.index(k) for k in free_keys]
    bounds = [(float(P05[k]), float(P95[k])) for k in free_keys]

    def arma_X(vec, chord, alpha, v):
        shape = np.zeros(7); shape[0] = chord
        for j, idx in enumerate(free_idx):
            shape[idx] = vec[j]
        re = reynolds(chord, v)
        X = np.array([list(shape) + [alpha, re,
                                     f_alpha_over_sqrtre(alpha, re),
                                     f_te_rel(shape[4], chord)]])
        return X, shape

    def ens_stats(X):
        P = np.stack([m.predict(X) for m in ens])
        return P.mean(axis=0)[0], P.std(axis=0)[0]

    idx_k0, idx_k2 = [], []
    print("=" * 105)
    print("BATERIA TE-REAL — ETAPA A (solo inversa, sin CATIA)  |  bounds p5-p95 sobre dataset TE-real >=150")
    print("=" * 105)
    print(f"{'caso':4s}{'c':>5s}{'v':>5s}{'a':>4s}{'Re':>10s} | "
          + "".join(f"{k[:9]:>10s}" for k in free_keys)
          + f" | {'LD_k0':>8s}{'LD_k2':>8s}{'sigma':>7s}")
    for caso, chord, v, a in CASOS:
        def obj0(x):
            X, _ = arma_X(x, chord, a, v)
            return prod.predict(X)[0]
        r0 = differential_evolution(obj0, bounds, seed=42, maxiter=200, tol=1e-7,
                                    polish=True, workers=1)
        X0, sh0 = arma_X(r0.x, chord, a, v); ld_k0 = float(r0.fun)

        def obj2(x):
            X, _ = arma_X(x, chord, a, v)
            mu, sd = ens_stats(X)
            return mu + 2.0 * sd
        r2 = differential_evolution(obj2, bounds, seed=42, maxiter=150, tol=1e-7,
                                    polish=True, workers=1)
        X2, sh2 = arma_X(r2.x, chord, a, v)
        mu2, sd2 = ens_stats(X2); ld_k2 = float(prod.predict(X2)[0])

        re = int(round(reynolds(chord, v)))
        for tag, sh in [("k0", sh0), ("k2", sh2)]:
            up = {k: round(float(val), 6) for k, val in zip(SHAPE, sh)}
            up["chord_angle_deg"] = 350.0
            fn = f"tr_{tag}_{caso}_c{chord}_v{v}_a{abs(a)}.json"
            json.dump({"user_params": up, "velocidad_kmh": v, "alphas": [a]},
                      open(os.path.join(BASE, fn), "w", encoding="utf-8"), indent=2)
            entry = {"caso": caso, "cuerda": chord, "vel": v, "alpha": a, "Re": re, "json": fn}
            entry["LD_pred"] = ld_k0 if tag == "k0" else ld_k2
            if tag == "k2":
                entry["sigma"] = float(sd2)
            (idx_k0 if tag == "k0" else idx_k2).append(entry)

        vals = "".join(f"{sh2[i]:10.3f}" for i in free_idx)
        print(f"{caso:<4d}{chord:>5d}{v:>5d}{a:>4d}{re:>10d} | {vals} | "
              f"{ld_k0:8.2f}{ld_k2:8.2f}{sd2:7.2f}")

    json.dump(idx_k0, open(os.path.join(BASE, "bateria_tereal_k0_index.json"), "w",
                           encoding="utf-8"), indent=2)
    json.dump(idx_k2, open(os.path.join(BASE, "bateria_tereal_k2_index.json"), "w",
                           encoding="utf-8"), indent=2)
    print("\n[OK] ETAPA A completada. Propuestas + indices guardados. CATIA NO tocado.")


# =========================================================
# ETAPA B — CATIA (steps 1-3) + genera_tereal + XFOIL. Coherencia TE-real.
# =========================================================
def _catia_cerrar_parts():
    try:
        import win32com.client as w
        app = w.GetActiveObject("CATIA.Application")
        docs = app.Documents
        for i in range(docs.Count, 0, -1):
            d = docs.Item(i)
            if d.Name.endswith(".CATPart"):
                try: d.Close()
                except Exception: pass
        return app.Documents.Count
    except Exception as e:
        return f"CATIA no accesible: {e}"


def _ld_real_tereal(cfg):
    """Genera geometria en CATIA (steps 1-3), convierte con TE-real y corre XFOIL.
    Devuelve LD real del unico (v, alpha), o None."""
    import pipeline_airfoil_api as P
    from piloto_tereal import genera_tereal, xfoil_sweep, SCRATCH

    up = dict(cfg["user_params"]); up.setdefault("chord_angle_deg", 350.0)
    v = cfg["velocidad_kmh"] if not isinstance(cfg["velocidad_kmh"], list) else cfg["velocidad_kmh"][0]
    a = int(cfg["alphas"][0])
    chord = up["chord_length_mm"]
    up_json = json.dumps(up)

    # STEP 1-3 (CATIA -> puntos -> ASC), como el pipeline
    try:
        subprocess.run([P.PYTHON_EXE, str(P.SCRIPT_1_GENERATOR), up_json],
                       check=True, timeout=140, capture_output=True, text=True)
        subprocess.run([P.PYTHON_EXE, str(P.SCRIPT_2_POINTS), str(P.OUTPUT_CSV)],
                       check=True, timeout=200, capture_output=True, text=True)
        subprocess.run([P.PYTHON_EXE, str(P.SCRIPT_3_EXPORT_ASC), str(P.OUTPUT_ASC)],
                       check=True, timeout=200, capture_output=True, text=True)
    except Exception as e:
        print(f"   [CATIA/ASC FALLO] {e}")
        return None
    if not os.path.exists(P.OUTPUT_ASC):
        print("   [ASC no generado]")
        return None

    # STEP 4' - TE-real (NO amputado) + XFOIL en (Re, alpha)
    dat = os.path.join(SCRATCH, "trbat.dat")
    try:
        genera_tereal(str(P.OUTPUT_ASC), dat)
    except Exception as e:
        print(f"   [genera_tereal FALLO] {e}")
        return None
    re = int(round(reynolds(chord, v)))
    pol = xfoil_sweep(dat, re, [a])
    if a in pol:
        cl, cd, cm = pol[a]
        return (cl / cd) if cd else None
    return None


def _fusiona_previo(lista, path_res):
    """REANUDABLE: si ya existe el JSON de resultados, copia a la lista los LD_real que
    ya se calcularon. Devuelve (lista, n_ya_hechos).

    Por que hace falta: la etapa B son ~2 h de CATIA y antes solo escribia al final, asi
    que un fallo en el caso 35 tiraba las dos horas. Ahora se vuelca tras CADA caso y al
    relanzar se saltan los que ya tienen LD_real. Mismo patron que densificar.py.
    La LOGICA DE VERIFICACION no cambia: solo la persistencia."""
    if not os.path.exists(path_res):
        return lista, 0
    try:
        prev = {c["caso"]: c for c in json.load(open(path_res, encoding="utf-8"))}
    except Exception:
        return lista, 0
    n = 0
    for c in lista:
        p = prev.get(c["caso"])
        if p is not None and p.get("LD_real") is not None:
            c["LD_real"] = p["LD_real"]
            n += 1
    return lista, n


def etapaB():
    STARS = os.path.join(BASE, "bateria_tereal_stars")
    os.makedirs(STARS, exist_ok=True)
    k0 = json.load(open(os.path.join(BASE, "bateria_tereal_k0_index.json"), encoding="utf-8"))
    k2 = json.load(open(os.path.join(BASE, "bateria_tereal_k2_index.json"), encoding="utf-8"))
    RES_K0 = os.path.join(BASE, "bateria_tereal_k0_resultados.json")
    RES_K2 = os.path.join(BASE, "bateria_tereal_k2_resultados.json")

    print("=" * 70)
    print("BATERIA TE-REAL — ETAPA B (40 geometrias en CATIA + XFOIL, TE romo)")
    print("=" * 70)
    k0, n0 = _fusiona_previo(k0, RES_K0)
    k2, n2 = _fusiona_previo(k2, RES_K2)
    if n0 or n2:
        print(f"[REANUDA] ya hechos: k=0 {n0}/{len(k0)} | k=2 {n2}/{len(k2)} -> se saltan")
    print("[CATIA] estado inicial:", _catia_cerrar_parts())

    def verifica(lista, etiqueta, path_res, guardar_dat=False):
        for c in lista:
            if c.get("LD_real") is not None:
                print(f"#### CASO {c['caso']} [{etiqueta}] ya hecho "
                      f"(LD_real={c['LD_real']:.2f}) -> salta"); sys.stdout.flush()
                continue
            cfg = json.load(open(os.path.join(BASE, c["json"]), encoding="utf-8"))
            print(f"\n#### CASO {c['caso']} [{etiqueta}] c{c['cuerda']} v{c['vel']} a{c['alpha']} "
                  f"| LD_pred={c['LD_pred']:.2f}"); sys.stdout.flush()
            c["LD_real"] = _ld_real_tereal(cfg)
            print(f"   LD_real = {c['LD_real']}"); sys.stdout.flush()
            if guardar_dat:
                from piloto_tereal import SCRATCH
                src = os.path.join(SCRATCH, "trbat.dat")
                if os.path.exists(src):
                    shutil.copy2(src, os.path.join(
                        STARS, f"caso{c['caso']}_c{c['cuerda']}_v{c['vel']}_a{abs(c['alpha'])}.dat"))
            # VOLCADO INCREMENTAL: el progreso sobrevive a un corte
            json.dump(lista, open(path_res, "w", encoding="utf-8"), indent=2)
            _catia_cerrar_parts()
        return lista

    k0 = verifica(k0, "k=0", RES_K0, guardar_dat=False)
    k2 = verifica(k2, "k=2", RES_K2, guardar_dat=True)

    json.dump(k0, open(RES_K0, "w", encoding="utf-8"), indent=2)
    json.dump(k2, open(RES_K2, "w", encoding="utf-8"), indent=2)

    print("\n" + "=" * 105)
    print("TABLA FINAL — bateria TE-real (20 casos, k=0 y k=2)")
    print("=" * 105)
    m = {c["caso"]: c for c in k0}
    print(f"{'caso':5s}{'c':>5s}{'v':>5s}{'a':>4s}"
          f"{'pred_k0':>9s}{'real_k0':>9s}{'err_k0':>8s}"
          f"{'pred_k2':>9s}{'real_k2':>9s}{'err_k2':>8s}")
    e0s, e2s = [], []
    for c2 in k2:
        c0 = m[c2["caso"]]
        def err(pred, real):
            return abs(real - pred) / abs(real) * 100 if real else None
        e0 = err(c0["LD_pred"], c0["LD_real"]); e2 = err(c2["LD_pred"], c2["LD_real"])
        if e0 is not None: e0s.append(e0)
        if e2 is not None: e2s.append(e2)
        r0 = f"{c0['LD_real']:9.2f}" if c0["LD_real"] else f"{'NOCONV':>9s}"
        r2 = f"{c2['LD_real']:9.2f}" if c2["LD_real"] else f"{'NOCONV':>9s}"
        s0 = f"{e0:6.0f}%" if e0 is not None else f"{'-':>7s}"
        s2 = f"{e2:6.0f}%" if e2 is not None else f"{'-':>7s}"
        print(f"{c2['caso']:<5d}{c2['cuerda']:>5d}{c2['vel']:>5d}{c2['alpha']:>4d}"
              f"{c0['LD_pred']:9.2f}{r0}{s0}"
              f"{c2['LD_pred']:9.2f}{r2}{s2}")
    print("-" * 105)
    print(f"ERROR MEDIO  k=0: {np.mean(e0s):5.1f}%  ({len(e0s)}/20 conv)   |   "
          f"k=2: {np.mean(e2s):5.1f}%  ({len(e2s)}/20 conv)")
    print(f"[REF viejo]  k=0: 22.2%   k=2: 4.0%")
    print(f"\n[OK] resultados -> bateria_tereal_k0/k2_resultados.json   |   .dat estrella -> {STARS}")


if __name__ == "__main__":
    if "--verificar" in sys.argv:
        etapaB()
    else:
        etapaA()
