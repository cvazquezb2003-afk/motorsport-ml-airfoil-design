"""
Bateria AMPLIADA (casos 9-20) — winner's curse, 12 casos nuevos.
Replica EXACTAMENTE el metodo de los 8 originales:
  - k=0 (como inversa_bateria.py): optimiza el modelo de PRODUCCION, maxiter=200,
    LD_pred = res.fun.
  - k=2 (como bateria_k2.py): optimiza J = mean_ens + 2*sigma, maxiter=150,
    LD_pred = prod.predict en el optimo.
Cuerda FIJA, 6 params libres en p5-p95 (dataset >=150), Reynolds derivado.

  python bateria_ampliada.py             -> ETAPA 1 (solo inversa, sin CATIA)
  python bateria_ampliada.py --verificar -> ETAPA 2 (genera 24 geom en CATIA + XFOIL)

No modifica ningun script ni dato existente.
"""
import os, sys, json, shutil
import numpy as np
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
RHO, MU = 1.225, 1.81e-5
def reynolds(c, v):
    return RHO * (v / 3.6) * (c / 1000.0) / MU

# casos 9-20 (aprobados; caso 13 a alpha=-10)
CASOS = [
    (9,  250, 180, -6), (10, 250, 290, -8), (11, 350, 110, -6),
    (12, 350, 180, -8), (13, 320, 290, -10),
    (14, 420, 180, -8), (15, 420, 110, -6), (16, 480, 290, -8), (17, 480, 180, -6),
    (18, 170, 290, -6), (19, 190, 180, -4), (20, 175, 290, -2),
]


# =========================================================
# ETAPA 1 — inversa (sin CATIA). Metodo identico a los 8 originales.
# =========================================================
def etapa1():
    import joblib
    from scipy.optimize import differential_evolution
    from feature_utils import SHAPE, f_alpha_over_sqrtre, f_te_rel

    ens = joblib.load(os.path.join(BASE, "ensemble_ld_sigma.joblib"))
    prod = joblib.load(os.path.join(BASE, "modelo_LD_inversa_xgb.joblib"))["model"]
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
        X = np.array([list(shape) + [alpha, re,
                                     f_alpha_over_sqrtre(alpha, re),
                                     f_te_rel(shape[4], chord)]])
        return X, shape

    def ens_stats(X):
        P = np.stack([m.predict(X) for m in ens])
        return P.mean(axis=0)[0], P.std(axis=0)[0]

    idx_k0, idx_k2 = [], []
    print("=" * 100)
    print("BATERIA AMPLIADA — ETAPA 1 (solo inversa, sin CATIA)")
    print("=" * 100)
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
            fn = f"amp_{tag}_{caso}_c{chord}_v{v}_a{abs(a)}.json"
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

    json.dump(idx_k0, open(os.path.join(BASE, "bateria_ampliada_k0_index.json"), "w",
                           encoding="utf-8"), indent=2)
    json.dump(idx_k2, open(os.path.join(BASE, "bateria_ampliada_k2_index.json"), "w",
                           encoding="utf-8"), indent=2)
    print("\n[OK] ETAPA 1 completada. Propuestas + indices guardados. CATIA NO tocado.")


# =========================================================
# ETAPA 2 — genera las 24 geometrias en CATIA + XFOIL, compara predicho vs real.
# =========================================================
def _catia_cerrar_parts():
    """Cierra los CATPart abiertos (mantiene memoria plana). No falla si no hay CATIA."""
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


def _ld_real_de(cfg):
    """Corre el pipeline (CATIA+XFOIL) y devuelve el LD real del unico alpha, o None."""
    import pipeline_airfoil_api as p
    r = p.run_pipeline(cfg)
    if r.get("status") != "ok":
        return None
    for rv in r.get("resultados_por_velocidad", []):
        for fila in rv["resultados"]:
            if fila.get("status") == "ok":
                return fila["LD"]
    return None


def etapa2():
    STARS = os.path.join(BASE, "bateria_ampliada_stars")
    os.makedirs(STARS, exist_ok=True)
    k0 = json.load(open(os.path.join(BASE, "bateria_ampliada_k0_index.json"), encoding="utf-8"))
    k2 = json.load(open(os.path.join(BASE, "bateria_ampliada_k2_index.json"), encoding="utf-8"))

    print("=" * 70)
    print("BATERIA AMPLIADA — ETAPA 2 (24 geometrias en CATIA + XFOIL)")
    print("=" * 70)
    print("[CATIA] estado inicial:", _catia_cerrar_parts())

    def verifica_lista(lista, etiqueta, guardar_dat=False):
        for c in lista:
            cfg = json.load(open(os.path.join(BASE, c["json"]), encoding="utf-8"))
            print(f"\n#### CASO {c['caso']} [{etiqueta}] c{c['cuerda']} v{c['vel']} a{c['alpha']} "
                  f"| LD_pred={c['LD_pred']:.2f}")
            c["LD_real"] = _ld_real_de(cfg)
            print(f"   LD_real = {c['LD_real']}")
            if guardar_dat:
                src = os.path.join(BASE, "airfoil_v4.dat")
                if os.path.exists(src):
                    shutil.copy2(src, os.path.join(
                        STARS, f"caso{c['caso']}_c{c['cuerda']}_v{c['vel']}_a{abs(c['alpha'])}.dat"))
            _catia_cerrar_parts()   # memoria plana tras cada geometria
        return lista

    k0 = verifica_lista(k0, "k=0", guardar_dat=False)
    k2 = verifica_lista(k2, "k=2", guardar_dat=True)   # los .dat estrella

    json.dump(k0, open(os.path.join(BASE, "bateria_ampliada_k0_resultados.json"), "w",
                       encoding="utf-8"), indent=2)
    json.dump(k2, open(os.path.join(BASE, "bateria_ampliada_k2_resultados.json"), "w",
                       encoding="utf-8"), indent=2)

    # tabla final
    print("\n" + "=" * 100)
    print("TABLA FINAL — bateria ampliada (12 casos, k=0 y k=2)")
    print("=" * 100)
    m = {c["caso"]: c for c in k0}
    print(f"{'caso':5s}{'c':>5s}{'v':>5s}{'a':>4s}"
          f"{'pred_k0':>9s}{'real_k0':>9s}{'err_k0':>8s}"
          f"{'pred_k2':>9s}{'real_k2':>9s}{'err_k2':>8s}  estado")
    for c2 in k2:
        c0 = m[c2["caso"]]
        def err(pred, real):
            return abs(real - pred) / abs(real) * 100 if real else None
        e0 = err(c0["LD_pred"], c0["LD_real"]); e2 = err(c2["LD_pred"], c2["LD_real"])
        r0 = f"{c0['LD_real']:9.2f}" if c0["LD_real"] else f"{'NOCONV':>9s}"
        r2 = f"{c2['LD_real']:9.2f}" if c2["LD_real"] else f"{'NOCONV':>9s}"
        s0 = f"{e0:6.0f}%" if e0 is not None else f"{'-':>7s}"
        s2 = f"{e2:6.0f}%" if e2 is not None else f"{'-':>7s}"
        est = ("k0:" + ("ok" if c0["LD_real"] else "NO") + " k2:" + ("ok" if c2["LD_real"] else "NO"))
        print(f"{c2['caso']:<5d}{c2['cuerda']:>5d}{c2['vel']:>5d}{c2['alpha']:>4d}"
              f"{c0['LD_pred']:9.2f}{r0}{s0}"
              f"{c2['LD_pred']:9.2f}{r2}{s2}  {est}")
    print(f"\n[OK] resultados -> bateria_ampliada_k0_resultados.json / _k2_resultados.json")
    print(f"[OK] .dat estrella (k=2) -> {STARS}")


if __name__ == "__main__":
    if "--verificar" in sys.argv:
        etapa2()
    else:
        etapa1()
