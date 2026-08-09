"""
VECINO FABRICABLE: dado el optimo teorico (7 params del ML), encuentra el perfil
REAL mas cercano del catalogo TE-real, su similitud, su Cp y su .dat descargable.

Arquitectura: el optimo lo da el ML; el Cp y el .dat son geometria REAL fabricable
(este modulo), etiquetada con transparencia. Portable, NO toca produccion.

Reutiliza: inversa_service (_per/_DMIN/_DMAX ya cargados), graficas_cp (Cp), feature_utils.
"""
import os
import numpy as np
from inversa_service import _per, _DMIN, _DMAX
from feature_utils import SHAPE

BASE = os.path.dirname(os.path.abspath(__file__))
DATASET_RUNS = os.path.join(BASE, "dataset_runs")

# candidatos = perfiles del catalogo con .asc archivado (para .dat TE-real + Cp)
_ASC = [rid for rid in _per.index
        if os.path.exists(os.path.join(DATASET_RUNS, rid, "auto_export.asc"))]

# MODO WEB: dataset_runs/ no se despliega (21 MB, y sus .dat son la geometria
# AMPUTADA de junio). Sin el, _ASC queda VACIO y el np.argmin de encontrar_vecino
# reventaba con un 500 en /api/optimo -- y no en un sitio evidente, sino al pedir
# la geometria. Se cae de pie al catalogo COMPLETO: el vecino es contexto (nombre,
# similitud, cuerda) y eso sale del CSV, que si va al repo. Lo unico que se pierde
# es poder regenerar SU .dat o su Cp, que necesitan el .asc y XFOIL de todos modos.
GEOMETRIA_VECINO = bool(_ASC)          # False => solo contexto, sin .dat ni Cp
_CAND = _per.loc[_ASC] if _ASC else _per
_RANGE = (_DMAX.values - _DMIN.values)
_CP_CACHE = {}


def encontrar_vecino(shape_params):
    """Perfil real mas cercano por distancia euclidea en los 7 params NORMALIZADOS
    (cada uno por su rango). Devuelve run_id, similitud y diffs por parametro."""
    opt = np.array([float(shape_params[k]) for k in SHAPE])
    M = _CAND[SHAPE].values
    dn = (M - opt) / _RANGE                          # diferencias normalizadas
    dist = np.linalg.norm(dn, axis=1)
    i = int(np.argmin(dist))
    run_id = _CAND.index[i]
    diffs = {k: {"optimo": round(float(opt[j]), 3),
                 "vecino": round(float(M[i, j]), 3),
                 "dif_%": round(100 * abs(dn[i, j]), 1)}
             for j, k in enumerate(SHAPE)}
    sim = 100.0 * (1.0 - float(np.mean(np.abs(dn[i]))))   # cercania media por parametro
    return {
        "run_id": run_id,
        "chord_mm": float(M[i, 0]),
        "distancia": float(dist[i]),
        "similitud_pct": round(float(np.clip(sim, 0, 100)), 1),
        "diffs": diffs,
    }


def condicion_cp_vecino(run_id, alpha_abs=None):
    """Condicion 'relevante' para el Cp: angulo de diseno ENTERO EXACTO (negativo) a
    290 km/h; si XFOIL no converge ahi, cae al optimo |L/D| propio del perfil."""
    from graficas_cp import condicion_optima
    if alpha_abs is not None:
        a = -int(round(float(alpha_abs)))            # angulo entero exacto, negativo
        return 290, a
    return condicion_optima(run_id)


def fig_cp_vecino(run_id, alpha_abs=None):
    """Figura Cp del vecino (cacheada). Reutiliza graficas_cp.fig_cp (orden de arco,
    Cp invertido, tema oscuro). Fallback robusto al optimo del perfil."""
    from graficas_cp import fig_cp, condicion_optima
    v, a = condicion_cp_vecino(run_id, alpha_abs)
    key = (run_id, v, a)
    if key in _CP_CACHE:
        return _CP_CACHE[key]
    try:
        fig = fig_cp(run_id, v, a)
    except Exception:                                # no convergio -> optimo del perfil
        v, a = condicion_optima(run_id); key = (run_id, v, a)
        if key in _CP_CACHE:
            return _CP_CACHE[key]
        fig = fig_cp(run_id, v, a)
    _CP_CACHE[key] = fig
    return fig


def es_catalogo(run_id):
    """Guard anti path-traversal: run_id debe ser un perfil real del catalogo."""
    return run_id in set(_CAND.index)


if __name__ == "__main__":
    import sys, json, time
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass
    import inversa_service as S
    print("[optimo] Monaco 9-14, cuerda 300 ...")
    opt = S.optimizar(300, -14, -9)
    v = encontrar_vecino(opt["shape_params"])
    print(f"\nVECINO: {v['run_id']}  cuerda={v['chord_mm']:.0f}mm  "
          f"similitud={v['similitud_pct']}%  dist={v['distancia']:.3f}")
    print("diffs por parametro:")
    for k, d in v["diffs"].items():
        print(f"  {k:30s} optimo={d['optimo']:>9}  vecino={d['vecino']:>9}  dif={d['dif_%']}%")
    t = time.time(); fig = fig_cp_vecino(v["run_id"], alpha_abs=11.5)
    fig.write_image(os.path.join(BASE, "graficas", "_vecino_cp.png"), scale=2)
    print(f"\n[OK] Cp -> graficas/_vecino_cp.png  ({time.time()-t:.1f}s)")
