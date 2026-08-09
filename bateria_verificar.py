"""Genera y verifica en XFOIL las 8 propuestas de la bateria, en secuencia."""
import os, json
import pipeline_airfoil_api as p

BASE = os.path.dirname(os.path.abspath(__file__))
idx = json.load(open(os.path.join(BASE, "bateria_index.json"), encoding="utf-8"))
salida = []
for caso in idx:
    print("\n" + "#" * 70)
    print(f"# CASO {caso['caso']}: cuerda {caso['cuerda']} v {caso['vel']} alpha {caso['alpha']} "
          f"| LD_pred {caso['LD_pred']:.2f}")
    print("#" * 70)
    cfg = json.load(open(os.path.join(BASE, caso["json"]), encoding="utf-8"))
    r = p.run_pipeline(cfg)
    real = None
    if r.get("status") == "ok":
        for rv in r["resultados_por_velocidad"]:
            for fila in rv["resultados"]:
                if fila.get("status") == "ok":
                    real = fila["LD"]
    caso["LD_real"] = real
    salida.append(caso)
    print(f"[CASO {caso['caso']}] LD_pred={caso['LD_pred']:.2f}  LD_real={real}")

json.dump(salida, open(os.path.join(BASE, "bateria_resultados.json"), "w", encoding="utf-8"),
          indent=2)
print("\n" + "=" * 70)
print("TABLA FINAL")
print("=" * 70)
print(f"{'caso':5s}{'cuerda':>7s}{'vel':>5s}{'a':>4s}{'Re':>11s}{'LD_pred':>9s}{'LD_real':>9s}{'dif':>8s}{'err%':>7s}")
for c in salida:
    if c["LD_real"] is not None:
        dif = c["LD_real"] - c["LD_pred"]
        err = abs(dif) / abs(c["LD_real"]) * 100
        print(f"{c['caso']:<5d}{c['cuerda']:>7d}{c['vel']:>5d}{c['alpha']:>4d}{c['Re']:>11,d}"
              f"{c['LD_pred']:>9.2f}{c['LD_real']:>9.2f}{dif:>8.2f}{err:>6.0f}%")
    else:
        print(f"{c['caso']:<5d}{c['cuerda']:>7d}{c['vel']:>5d}{c['alpha']:>4d}{c['Re']:>11,d}"
              f"{c['LD_pred']:>9.2f}{'NO CONV':>9s}")
