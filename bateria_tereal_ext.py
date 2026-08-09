"""
AMPLIACION de la bateria TE-real: casos 21-40 (20 nuevos).
Metodo IDENTICO a bateria_tereal.py (k=0 maxiter=200 sobre modelo produccion;
k=2 J=mean_ens+2sigma maxiter=150; bounds p5-p95 del dataset TE-real >=150;
verificacion con pipeline TE-real: CATIA steps 1-3 -> genera_tereal -> XFOIL).

Cuerdas NUEVAS (no solapan con las 20 existentes: 170,175,180,190,250,300,320,
350,420,450,480). Reparto proporcional: 4 en 150-200 (angulos suaves), 11 en
200-400, 5 en 400-500. Velocidades equilibradas 6/7/7 (110/180/290).

  python bateria_tereal_ext.py             -> PASO 1 (solo inversa, sin CATIA)
  python bateria_tereal_ext.py --verificar -> PASO 2 (40 geom CATIA + XFOIL + merge)
"""
import os, sys, json, subprocess, shutil
import numpy as np
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
RHO, MU = 1.225, 1.81e-5
def reynolds(c, v):
    return RHO * (v / 3.6) * (c / 1000.0) / MU

# casos 21-40 (cuerdas nuevas). Zona baja: solo angulos [0..-6].
CASOS = [
    # 150-200 (4) angulos suaves
    (21, 160, 110, -4), (22, 185, 180, -6), (23, 195, 290, -2), (24, 165, 180, -6),
    # 200-400 (11)
    (25, 220, 110, -6), (26, 240, 180, -8), (27, 260, 290, -10), (28, 275, 110, -4),
    (29, 290, 180, -6), (30, 310, 290, -8), (31, 330, 180, -10), (32, 360, 110, -8),
    (33, 375, 290, -12), (34, 390, 290, -4), (35, 340, 110, -6),
    # 400-500 (5)
    (36, 410, 110, -6), (37, 430, 180, -8), (38, 445, 290, -10), (39, 465, 180, -6),
    (40, 495, 290, -8),
]

MODEL = os.path.join(BASE, "modelo_LD_inversa_xgb.joblib")     # produccion = TE-real
ENS = os.path.join(BASE, "ensemble_ld_sigma.joblib")
STARS = os.path.join(BASE, "bateria_tereal_stars")


def pasoA():
    import joblib
    from scipy.optimize import differential_evolution
    from feature_utils import SHAPE, f_alpha_over_sqrtre, f_te_rel

    ens = joblib.load(ENS)
    prod = joblib.load(MODEL)["model"]
    df = pd.read_csv(os.path.join(BASE, "airfoil_dataset.csv"))
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
        X = np.array([list(shape) + [alpha, re, f_alpha_over_sqrtre(alpha, re),
                                     f_te_rel(shape[4], chord)]])
        return X, shape

    def ens_stats(X):
        P = np.stack([m.predict(X) for m in ens])
        return P.mean(axis=0)[0], P.std(axis=0)[0]

    idx_k0, idx_k2 = [], []
    print("=" * 92)
    print("BATERIA TE-REAL EXT — PASO 1 (inversa, sin CATIA) | casos 21-40")
    print("=" * 92)
    print(f"{'caso':4s}{'c':>5s}{'v':>5s}{'a':>4s}{'Re':>10s} | "
          f"{'LD_pred_k0':>11s}{'LD_pred_k2':>11s}{'sigma':>8s}")
    for caso, chord, v, a in CASOS:
        def obj0(x):
            X, _ = arma_X(x, chord, a, v); return prod.predict(X)[0]
        r0 = differential_evolution(obj0, bounds, seed=42, maxiter=200, tol=1e-7,
                                    polish=True, workers=1)
        X0, sh0 = arma_X(r0.x, chord, a, v); ld_k0 = float(r0.fun)

        def obj2(x):
            X, _ = arma_X(x, chord, a, v); mu, sd = ens_stats(X); return mu + 2.0 * sd
        r2 = differential_evolution(obj2, bounds, seed=42, maxiter=150, tol=1e-7,
                                    polish=True, workers=1)
        X2, sh2 = arma_X(r2.x, chord, a, v)
        mu2, sd2 = ens_stats(X2); ld_k2 = float(prod.predict(X2)[0])

        re = int(round(reynolds(chord, v)))
        for tag, sh, ld in [("k0", sh0, ld_k0), ("k2", sh2, ld_k2)]:
            up = {k: round(float(val), 6) for k, val in zip(SHAPE, sh)}
            up["chord_angle_deg"] = 350.0
            fn = f"tre_{tag}_{caso}_c{chord}_v{v}_a{abs(a)}.json"
            json.dump({"user_params": up, "velocidad_kmh": v, "alphas": [a]},
                      open(os.path.join(BASE, fn), "w", encoding="utf-8"), indent=2)
            entry = {"caso": caso, "cuerda": chord, "vel": v, "alpha": a, "Re": re,
                     "json": fn, "LD_pred": ld}
            if tag == "k2":
                entry["sigma"] = float(sd2)
            (idx_k0 if tag == "k0" else idx_k2).append(entry)

        print(f"{caso:<4d}{chord:>5d}{v:>5d}{a:>4d}{re:>10d} | "
              f"{ld_k0:11.2f}{ld_k2:11.2f}{sd2:8.2f}")

    json.dump(idx_k0, open(os.path.join(BASE, "bateria_tereal_ext_k0_index.json"), "w",
                           encoding="utf-8"), indent=2)
    json.dump(idx_k2, open(os.path.join(BASE, "bateria_tereal_ext_k2_index.json"), "w",
                           encoding="utf-8"), indent=2)
    print("\n[OK] PASO 1 completado. Propuestas + indices guardados. CATIA NO tocado.")


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
    import pipeline_airfoil_api as P
    from piloto_tereal import genera_tereal, xfoil_sweep, SCRATCH
    up = dict(cfg["user_params"]); up.setdefault("chord_angle_deg", 350.0)
    v = cfg["velocidad_kmh"] if not isinstance(cfg["velocidad_kmh"], list) else cfg["velocidad_kmh"][0]
    a = int(cfg["alphas"][0]); chord = up["chord_length_mm"]
    up_json = json.dumps(up)
    try:
        subprocess.run([P.PYTHON_EXE, str(P.SCRIPT_1_GENERATOR), up_json],
                       check=True, timeout=140, capture_output=True, text=True)
        subprocess.run([P.PYTHON_EXE, str(P.SCRIPT_2_POINTS), str(P.OUTPUT_CSV)],
                       check=True, timeout=200, capture_output=True, text=True)
        subprocess.run([P.PYTHON_EXE, str(P.SCRIPT_3_EXPORT_ASC), str(P.OUTPUT_ASC)],
                       check=True, timeout=200, capture_output=True, text=True)
    except Exception as e:
        print(f"   [CATIA/ASC FALLO] {e}"); return None
    if not os.path.exists(P.OUTPUT_ASC):
        print("   [ASC no generado]"); return None
    dat = os.path.join(SCRATCH, "trebat.dat")
    try:
        genera_tereal(str(P.OUTPUT_ASC), dat)
    except Exception as e:
        print(f"   [genera_tereal FALLO] {e}"); return None
    re = int(round(reynolds(chord, v)))
    pol = xfoil_sweep(dat, re, [a])
    if a in pol:
        cl, cd, cm = pol[a]; return (cl / cd) if cd else None
    return None


def _fusiona_previo(lista, path_res):
    """REANUDABLE: recupera del JSON de resultados los LD_real ya calculados.
    Ver la nota en bateria_tereal._fusiona_previo: solo cambia la persistencia,
    no la logica de verificacion."""
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


def pasoB():
    os.makedirs(STARS, exist_ok=True)
    k0 = json.load(open(os.path.join(BASE, "bateria_tereal_ext_k0_index.json"), encoding="utf-8"))
    k2 = json.load(open(os.path.join(BASE, "bateria_tereal_ext_k2_index.json"), encoding="utf-8"))
    RES_K0 = os.path.join(BASE, "bateria_tereal_ext_k0_resultados.json")
    RES_K2 = os.path.join(BASE, "bateria_tereal_ext_k2_resultados.json")

    print("=" * 70)
    print("BATERIA TE-REAL EXT — PASO 2 (40 geometrias CATIA + XFOIL, TE romo)")
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
                src = os.path.join(SCRATCH, "trebat.dat")
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

    # --- MERGE con los 20 originales -> 40 juntos (mismo esquema, para la grafica) ---
    def merge(tag, nuevos):
        main = os.path.join(BASE, f"bateria_tereal_{tag}_resultados.json")
        orig = json.load(open(main, encoding="utf-8"))
        by = {c["caso"]: c for c in orig}
        for c in nuevos:
            by[c["caso"]] = c
        full = [by[k] for k in sorted(by)]
        json.dump(full, open(main, "w", encoding="utf-8"), indent=2)
        return full
    full_k0 = merge("k0", k0); full_k2 = merge("k2", k2)

    # --- estadisticas de los 40 ---
    def err(c):
        return abs(c["LD_real"] - c["LD_pred"]) / abs(c["LD_real"]) * 100 if c.get("LD_real") else None
    m2 = {c["caso"]: c for c in full_k2}

    print("\n" + "=" * 96)
    print("TABLA FINAL — bateria TE-real AMPLIADA (40 casos)")
    print("=" * 96)
    print(f"{'caso':5s}{'c':>5s}{'v':>5s}{'a':>4s}{'pred_k0':>9s}{'real_k0':>9s}{'err_k0':>8s}"
          f"{'pred_k2':>9s}{'real_k2':>9s}{'err_k2':>8s}")
    e0s, e2s, signos = [], [], 0
    for c0 in full_k0:
        c2 = m2[c0["caso"]]
        e0, e2 = err(c0), err(c2)
        if e0 is not None: e0s.append(e0)
        if e2 is not None: e2s.append(e2)
        # test de signos: real rinde PEOR que lo predicho por k=0 (|real|<|pred|)
        if c0.get("LD_real") and abs(c0["LD_real"]) < abs(c0["LD_pred"]):
            signos += 1
        r0 = f"{c0['LD_real']:9.2f}" if c0.get("LD_real") else f"{'NOCONV':>9s}"
        r2 = f"{c2['LD_real']:9.2f}" if c2.get("LD_real") else f"{'NOCONV':>9s}"
        s0 = f"{e0:6.0f}%" if e0 is not None else f"{'-':>7s}"
        s2 = f"{e2:6.0f}%" if e2 is not None else f"{'-':>7s}"
        print(f"{c0['caso']:<5d}{c0['cuerda']:>5d}{c0['vel']:>5d}{c0['alpha']:>4d}"
              f"{c0['LD_pred']:9.2f}{r0}{s0}{c2['LD_pred']:9.2f}{r2}{s2}")
    n0 = len([c for c in full_k0 if c.get("LD_real")])
    print("-" * 96)
    print(f"ERROR MEDIO 40 casos  k=0: {np.mean(e0s):5.1f}%  ({len(e0s)}/40 conv)   |   "
          f"k=2: {np.mean(e2s):5.1f}%  ({len(e2s)}/40 conv)")
    print(f"TEST DE SIGNOS: en {signos}/{n0} casos convergidos el real rinde PEOR que "
          f"la prediccion k=0 (sesgo optimista)")
    print(f"[REF 20 casos] k=0 23.9% / k=2 4.1%")
    print(f"\n[OK] merge -> bateria_tereal_k0/k2_resultados.json (40 casos)")
    print(f"[OK] .dat estrella nuevos -> {STARS}")


if __name__ == "__main__":
    if "--verificar" in sys.argv:
        pasoB()
    else:
        pasoA()
