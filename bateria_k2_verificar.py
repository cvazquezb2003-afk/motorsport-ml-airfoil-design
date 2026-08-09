"""Genera y verifica en XFOIL las 8 propuestas k=2, y compara contra k=0."""
import os, json
import pipeline_airfoil_api as p

BASE = os.path.dirname(os.path.abspath(__file__))
k2 = json.load(open(os.path.join(BASE, "bateria_k2_index.json"), encoding="utf-8"))
k0 = {c["caso"]: c for c in json.load(open(os.path.join(BASE, "bateria_resultados.json"),
                                            encoding="utf-8"))}
for c in k2:
    print("\n" + "#" * 70)
    print(f"# CASO {c['caso']} k=2: c{c['cuerda']} v{c['vel']} a{c['alpha']} | "
          f"LD_pred {c['LD_pred']:.2f} sigma {c['sigma']:.2f}")
    print("#" * 70)
    cfg = json.load(open(os.path.join(BASE, c["json"]), encoding="utf-8"))
    r = p.run_pipeline(cfg)
    real = None
    if r.get("status") == "ok":
        for rv in r["resultados_por_velocidad"]:
            for fila in rv["resultados"]:
                if fila.get("status") == "ok":
                    real = fila["LD"]
    c["LD_real"] = real
    print(f"[CASO {c['caso']}] pred={c['LD_pred']:.2f} real={real}")

json.dump(k2, open(os.path.join(BASE, "bateria_k2_resultados.json"), "w",
                   encoding="utf-8"), indent=2)

print("\n" + "=" * 92)
print("TABLA FINAL  k=2  (con comparacion contra k=0)")
print("=" * 92)
print(f"{'caso':5s}{'cuerda':>7s}{'vel':>5s}{'a':>4s}{'Re':>11s}{'LD_pred':>9s}"
      f"{'sigma':>7s}{'LD_real':>9s}{'err%':>7s}{'err%_k0':>9s}")
for c in k2:
    o = k0.get(c["caso"], {})
    if o.get("LD_real") is not None:
        e0 = f"{abs(o['LD_real'] - o['LD_pred']) / abs(o['LD_real']) * 100:.0f}%"
    else:
        e0 = "NOCONV"
    if c["LD_real"] is not None:
        err = abs(c["LD_real"] - c["LD_pred"]) / abs(c["LD_real"]) * 100
        print(f"{c['caso']:<5d}{c['cuerda']:>7d}{c['vel']:>5d}{c['alpha']:>4d}{c['Re']:>11,d}"
              f"{c['LD_pred']:>9.2f}{c['sigma']:>7.2f}{c['LD_real']:>9.2f}{err:>6.0f}%{e0:>9s}")
    else:
        print(f"{c['caso']:<5d}{c['cuerda']:>7d}{c['vel']:>5d}{c['alpha']:>4d}{c['Re']:>11,d}"
              f"{c['LD_pred']:>9.2f}{c['sigma']:>7.2f}{'NO CONV':>9s}{'':>7s}{e0:>9s}")
