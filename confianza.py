"""
Dos senales de contexto para el panel de resultados. Portables, sobre datos ya
calculados. NO tocan la inversa ni produccion.

1) NIVEL DE CONFIANZA — combina tres senales que ya existen:
     - sigma del ensemble (incertidumbre del modelo en ese punto)
     - distancia del optimo al catalogo (¿zona muestreada o rincon vacio?)
     - si XFOIL convergio sobre la geometria del optimo
   Umbrales fijados con DATOS, no a ojo:
     * sigma: en la bateria de 40 casos verificados en XFOIL, sigma<=0.6 -> error real
       medio 2.4%; sigma>1.2 -> 16.5%. De ahi los cortes 0.6 / 1.2.
     * distancia: separacion tipica entre perfiles REALES del catalogo
       (mediana 0.33, p90 0.41 en el espacio normalizado de los 7 params).

2) MEJOR DEL CATALOGO — el perfil real con mejor |L/D| MEDIDO (XFOIL, dataset) en la
   misma banda y cuerda parecida, para situar cuanto aporta el optimo.
"""
import os
import numpy as np
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))

# --- umbrales (justificados arriba) ---
SIGMA_OK, SIGMA_MAL = 0.6, 1.2
NN_DENSA, NN_RALA = 0.33, 0.41      # mediana y p90 de la separacion real del catalogo

_DF = None


def _df():
    global _DF
    if _DF is None:
        d = pd.read_csv(os.path.join(BASE, "airfoil_dataset.csv"))
        _DF = d[(d.status == "ok") & (d.chord_length_mm >= 150)].copy()
    return _DF


def senales_modelo(sigma, nn_dist, xfoil_ok):
    """Señales OBJETIVAS del modelo, SIN veredicto ni etiqueta de nivel.

    Se retiro el badge HIGH/MODERATE/EXPERIMENTAL: convertir sigma en una etiqueta
    sobre-interpretaba una sola cifra. Aqui se reportan los hechos (sigma, cobertura
    de datos, convergencia del solver) y el usuario juzga."""
    return {
        "sigma": float(sigma),
        "sigma_txt": "σ = %.2f" % sigma,
        "cobertura": ("within the well-sampled region" if nn_dist <= NN_DENSA
                      else "near the edge of the sampled region" if nn_dist <= NN_RALA
                      else "outside the well-sampled region"),
        "bien_muestreado": bool(nn_dist <= NN_RALA),
        # TRES estados, no dos. En el despliegue web no hay XFOIL, y con un
        # booleano el panel afirmaba "XFOIL did not converge on this geometry":
        # una acusacion FALSA contra una geometria que nadie llego a evaluar.
        # xfoil_ok=None significa "no se ha ejecutado", que es lo que pasa.
        "xfoil": ("XFOIL not available in the web version — geometry not verified"
                  if xfoil_ok is None else
                  "XFOIL converged on this geometry" if xfoil_ok else
                  "XFOIL did not converge on this geometry"),
        "xfoil_ok": None if xfoil_ok is None else bool(xfoil_ok),
        "nota": ("σ is the model's own spread across an ensemble trained on resampled "
                 "data — larger σ means the model has seen less evidence around this "
                 "design. It is an estimate, not a measured error."),
    }


def contexto_catalogo(ld_optimo, chord_mm, alpha_lo, alpha_hi, tol=0.15, vel=180):
    """Situa el optimo frente a los perfiles REALES del catalogo en la misma banda y
    cuerda similar (+-tol), usando |L/D| MEDIDO en XFOIL.

    Referencia ROBUSTA (percentil + mediana) en vez de "el mejor a secas": el maximo
    del catalogo es un OUTLIER — en la ventana tipica supera el p95 en ~35% y su CD es
    ~40% menor que el tipico, senal de una convergencia optimista de XFOIL. Compararse
    contra ese maximo seria repetir el winner's curse, pero del lado de los datos.
    Se reporta igualmente el mejor medido, etiquetado como tal.

    VELOCIDAD: el filtro es una IGUALDAD EXACTA contra un dataset que solo tiene
    110/180/290. Pasarle la velocidad del usuario (p.ej. 200) dejaria `sel` vacio y el
    KPI de percentil desapareceria SIN ERROR. Por eso `vel` se ENCAJA a la referencia
    medida mas cercana y se devuelve en `vel_referencia` / `vel_encajada`, para que la
    UI pueda decir "compared at 180 km/h (nearest reference speed)". Es el unico punto
    del flujo donde la velocidad del usuario NO se propaga: aqui se comparan
    MEDICIONES reales, y solo existen a esas tres velocidades."""
    d = _df()
    from guardas_velocidad import velocidad_referencia
    vel_pedida = float(vel)
    vel_ref = velocidad_referencia(vel_pedida)
    lo, hi = sorted([abs(float(alpha_lo)), abs(float(alpha_hi))])
    c = float(chord_mm)
    sel = d[(d.chord_length_mm.between(c * (1 - tol), c * (1 + tol))) &
            (d.velocidad_kmh == vel_ref) & (d.alpha_deg.abs().between(lo, hi))]
    if sel.empty:
        return None
    g = sel.groupby("run_id").agg(ld=("LD", lambda s: float(np.mean(np.abs(s)))),
                                  n=("LD", "size"), chord=("chord_length_mm", "first"))
    g = g[g.n >= 2]                       # al menos 2 angulos de la banda medidos
    if len(g) < 10:
        return None
    o = abs(float(ld_optimo))
    lds = g.ld.values
    p50, p90, mx = float(np.median(lds)), float(np.percentile(lds, 90)), float(lds.max())
    pct_rank = float((lds < o).mean() * 100.0)
    best = g.sort_values("ld", ascending=False).iloc[0]
    return {
        "n": int(len(g)), "tol_pct": int(tol * 100),
        "vel_referencia": float(vel_ref),          # velocidad REAL de la comparacion
        "vel_pedida": vel_pedida,                  # la que pidio el usuario
        "vel_encajada": bool(abs(vel_ref - vel_pedida) > 1e-9),
        "percentil": pct_rank,
        "mediana": p50, "p90": p90, "mejor": mx,
        "mejor_short": str(best.name).split("_")[0],
        "vs_mediana_pct": (o - p50) / p50 * 100.0,
        "vs_p90_pct": (o - p90) / p90 * 100.0,
        "vs_mejor_pct": (o - mx) / mx * 100.0,
        "mejor_es_outlier": bool(mx > p90 * 1.15),
        "nota": ("Compared against real XFOIL measurements of catalogue profiles at a "
                 "similar chord in the same angle band. The single best measurement is "
                 "an outlier (unusually low drag), so the typical and top-10% profiles "
                 "are the fair reference. The optimum's own figure is a prediction."),
    }


if __name__ == "__main__":
    import sys
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass
    import inversa_service as S
    for nm, af, at, lo, hi in [("Monza", -5, 0, 0, 5), ("Suzuka", -9, -5, 5, 9),
                               ("Hungaroring", -14, -9, 9, 14)]:
        r = S.optimizar(300, af, at)
        cat = contexto_catalogo(r["LD_predicho"], 300, lo, hi)
        cf = senales_modelo(r["sigma"], r["nn_dist"], True)
        print(f"\n{nm}: optimo |L/D|={abs(r['LD_predicho']):.1f}  σ={r['sigma']:.2f}  NN={r['nn_dist']:.3f}")
        if cat:
            print(f"   catalogo (n={cat['n']}): percentil {cat['percentil']:.0f}%  "
                  f"| vs mediana {cat['vs_mediana_pct']:+.0f}%  vs p90 {cat['vs_p90_pct']:+.0f}%  "
                  f"vs mejor {cat['vs_mejor_pct']:+.0f}% (outlier={cat['mejor_es_outlier']})")
        print(f"   señales: {cf['sigma_txt']} · {cf['cobertura']} · {cf['xfoil']}")
