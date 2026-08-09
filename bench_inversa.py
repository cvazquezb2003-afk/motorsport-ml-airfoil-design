"""
Benchmark de rendimiento/calidad de la inversa por rango. Solo lectura.
Compara n_sobol {65536, 32768, 16384} (y paso de angulo) en tiempo y en el OPTIMO
resultante (7 params + L/D) para Monaco/Monza/Medium. Referencia = 65536, step 1.
"""
import sys, time
import numpy as np
sys.stdout.reconfigure(encoding="utf-8") if hasattr(sys.stdout, "reconfigure") else None
import inversa_service as S

SHAPE = ["chord_length_mm", "leading_edge_angle_deg", "leading_edge_thickness_level",
         "trailing_edge_angle_deg", "trailing_edge_thickness_mm",
         "te_upr_angle_deg", "te_lwr_angle_deg"]
RNG = (S._DMAX.values - S._DMIN.values)
CASOS = [("Monaco 9-14", -14, -9), ("Monza  0-5 ", -5, 0), ("Medium 5-9 ", -9, -5)]
CONFIGS = [("65k s1", 65536, 1.0), ("32k s1", 32768, 1.0),
           ("16k s1", 16384, 1.0), ("32k s2", 32768, 2.0)]


def vec(r):
    return np.array([r["shape_params"][k] for k in SHAPE])


# referencia (65k, step1) por caso
ref = {}
print("Calculando referencia (65k, step1)...")
for nombre, af, at in CASOS:
    ref[nombre] = S.optimizar(300, af, at, n_sobol=65536, step=1.0)

print("\n" + "=" * 96)
print("TIEMPO por peticion (s) y DESVIACION del optimo vs referencia 65k")
print("=" * 96)
print(f"{'caso':13s}{'config':9s}{'seg':>7s}{'LD':>8s}{'dLD%':>7s}"
      f"{'maxdParam%':>12s}{'rec°':>6s}")
for nombre, af, at in CASOS:
    r0 = ref[nombre]; v0 = vec(r0)
    for cfg, ns, st in CONFIGS:
        t = time.time()
        r = S.optimizar(300, af, at, n_sobol=ns, step=st); dt = time.time() - t
        v = vec(r)
        dparam = float(np.max(np.abs((v - v0) / RNG)) * 100)     # max dif normalizada
        dld = abs(r["LD_predicho"] - r0["LD_predicho"]) / abs(r0["LD_predicho"]) * 100
        print(f"{nombre:13s}{cfg:9s}{dt:7.1f}{abs(r['LD_predicho']):8.1f}{dld:6.1f}%"
              f"{dparam:11.2f}%{r['alpha_recomendado_abs']:6.1f}")
    print()

print("(maxdParam% = mayor diferencia de un parametro respecto a 65k, en % del rango del dato)")
print("(dLD% = diferencia del L/D medio predicho respecto a 65k)")
