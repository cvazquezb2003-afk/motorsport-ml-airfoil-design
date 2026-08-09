"""
FASE 1 — Generador de geometria de perfil en PYTHON PURO (sin CATIA).
Replica la receta de airfoil_generator.py a partir de los 7 params de forma.
Objetivo: reproducir FIELMENTE la geometria que CATIA produce hoy. NO arregla
la limitacion 5. Modulo NUEVO y aparte; no toca ningun script del pipeline.

Trabaja en FRAME CANONICO: LE en (0,0), cuerda sobre +x, longitud 1 (normalizada).
Los perfiles son de downforce (camber hacia abajo, y<0 dominante).
"""
import os
import numpy as np

# ---- constantes calibrables (convenciones de CATIA a ajustar contra .asc) ----
BEZIER_K = 0.15         # (legacy, usado como fallback)
SIGN_CAMBER = -1.0      # signo de la flecha (camber): -1 = hacia abajo (downforce)
K_CAMBER = 0.16         # manejador de la camberline (calibrado sobre 4 perfiles)
K_SURF_LE = 0.14        # manejador del lado LE de las superficies
K_SURF_TE = 0.14        # manejador del lado TE
SIGN_TE_NORMAL = -1.0   # signo de la normal del TE (TE_upr debe caer en y>0)


def _bezier(P0, P1, P2, P3, n):
    t = np.linspace(0, 1, n)[:, None]
    return ((1-t)**3)*P0 + 3*((1-t)**2)*t*P1 + 3*(1-t)*(t**2)*P2 + (t**3)*P3


def _unit(ang_deg):
    a = np.radians(ang_deg)
    return np.array([np.cos(a), np.sin(a)])


def generate_contour(p, n_upper=140, n_lower=140, n_nose=40, debug=False):
    """
    p: dict con los 7 params de forma. Devuelve (contorno Nx2, dict_debug).
    Frame canonico: cuerda de LE(0,0) a TE(1,0), normalizada por chord_length_mm.
    """
    chord = float(p["chord_length_mm"])
    le_ang = float(p["leading_edge_angle_deg"])
    le_lvl = float(p["leading_edge_thickness_level"])
    te_ang = float(p["trailing_edge_angle_deg"])
    te_mm = float(p["trailing_edge_thickness_mm"])
    te_upr = float(p["te_upr_angle_deg"])
    te_lwr = float(p["te_lwr_angle_deg"])

    LE = np.array([0.0, 0.0])
    TE = np.array([1.0, 0.0])

    # --- CAMBERLINE: cubic Bezier con tangentes en LE y TE ---
    # tangente LE: baja con leading_edge_angle_deg (camber down)
    dir_le = np.array([np.cos(np.radians(le_ang)), SIGN_CAMBER*np.sin(np.radians(le_ang))])
    # tangente TE: te_control_angle ~168 (rel. a cuerda). direccion entrante al TE.
    # angulo de la camber en el TE respecto a la cuerda = (180 - te_ang)
    beta = np.radians(180.0 - te_ang)
    # manejador del TE de la camber: DEBE apuntar hacia DENTRO (-x, hacia el LE).
    # Si no, el control cae en x>1 y todo el contorno se pliega tras el TE (XFOIL no converge).
    dir_te = np.array([-abs(np.cos(beta)), SIGN_CAMBER*np.sin(beta)])
    Pc1 = LE + K_CAMBER*dir_le
    Pc2 = TE + K_CAMBER*dir_te                # handle entrante al TE
    camber = _bezier(LE, Pc1, Pc2, TE, 400)

    # --- POINT A = centro del circulo LE, al ratio sobre la camber (arc-length) ---
    ratio = 0.03 + (0.08-0.03)*np.clip(le_lvl, 0, 1)     # lerp(0.03,0.08,level)
    seg = np.linalg.norm(np.diff(camber, axis=0), axis=1)
    s = np.concatenate([[0], np.cumsum(seg)]); s /= s[-1]
    A = np.array([np.interp(ratio, s, camber[:, 0]), np.interp(ratio, s, camber[:, 1])])
    R = np.linalg.norm(A - LE)                             # radio circulo LE

    # tangente/normal de la camber en A
    iA = np.searchsorted(s, ratio)
    tA = camber[min(iA+1, len(camber)-1)] - camber[max(iA-1, 0)]
    tA = tA/np.linalg.norm(tA)
    nA = np.array([-tA[1], tA[0]])                        # normal

    B = A + R*nA          # punto superior (arranque extrados)
    C = A - R*nA          # punto inferior (arranque intrados)

    # --- TE PROFILE: cara roma perpendicular a la camber en TE, altura te_mm ---
    te_half = (te_mm/2.0)/chord                           # normalizado
    tTE = TE - camber[-3]; tTE = tTE/np.linalg.norm(tTE)
    nTE = SIGN_TE_NORMAL * np.array([-tTE[1], tTE[0]])    # signo corregido: TE_upr en y>0
    # FIX (autointerseccion TE): la normal del TE DEBE apuntar al mismo lado que el
    # extrados (nA = normal de la camber en A, que apunta a B). En perfiles de
    # downforce cargados la tangente de la camber en el TE es empinada y la normal
    # fija se INVERTIA -> TE_upr caia por debajo de TE_lwr -> las superficies se
    # cruzaban ~6% antes del TE. Orientar nTE con nA garantiza cierre sin cruce.
    if np.dot(nTE, nA) < 0:
        nTE = -nTE
    TE_upr = TE + te_half*nTE
    TE_lwr = TE - te_half*nTE

    # --- tangentes de superficie en el TE (te_upr/te_lwr rel. a la camber) ---
    def rot(v, deg):
        a = np.radians(deg); c, sn = np.cos(a), np.sin(a)
        return np.array([c*v[0]-sn*v[1], sn*v[0]+c*v[1]])
    dir_te_upr = rot(-tTE, SIGN_CAMBER*te_upr)   # entrante al TE por arriba
    dir_te_lwr = rot(-tTE, SIGN_CAMBER*te_lwr)

    # tangente en B/C = tangente al circulo = direccion de la camber en A (tA)
    dir_B = tA.copy()
    dir_C = tA.copy()

    # --- EXTRADOS: Bezier B -> TE_upr  (handle LE largo, TE corto -> no overshoot) ---
    up = _bezier(B, B + K_SURF_LE*dir_B, TE_upr + K_SURF_TE*dir_te_upr, TE_upr, n_upper)
    # --- INTRADOS: Bezier C -> TE_lwr ---
    lo = _bezier(C, C + K_SURF_LE*dir_C, TE_lwr + K_SURF_TE*dir_te_lwr, TE_lwr, n_lower)

    # --- NARIZ: arco del circulo LE de B a C pasando por el morro (LE) ---
    aB = np.arctan2(B[1]-A[1], B[0]-A[0])
    aC = np.arctan2(C[1]-A[1], C[0]-A[0])
    aL = np.arctan2(LE[1]-A[1], LE[0]-A[0])
    # recorrer de B a C por el lado del LE (morro)
    angs = np.linspace(aB, aB + _arc_delta(aB, aC, aL), n_nose)
    nose = A + R*np.column_stack([np.cos(angs), np.sin(angs)])

    # --- ENSAMBLAR en orden de arco: TE_upr -> extrados(rev) -> B -> nariz -> C -> intrados -> TE_lwr ---
    contour = np.vstack([up[::-1], nose[1:-1], lo])
    dbg = dict(A=A, R=R, B=B, C=C, TE_upr=TE_upr, TE_lwr=TE_lwr,
               camber_min_y=camber[:, 1].min(), ratio=ratio)
    return contour, dbg


def _arc_delta(aB, aC, aL):
    """delta angular de B a C pasando por el lado de LE (aL)."""
    def norm(d): return (d + np.pi) % (2*np.pi) - np.pi
    d_pos = norm(aC - aB) if norm(aC-aB) > 0 else norm(aC-aB) + 2*np.pi
    # elegimos el sentido que pasa cerca de aL
    d1 = norm(aC-aB); d2 = d1 - np.sign(d1)*2*np.pi
    # probar cual incluye aL
    for d in (d1, d2):
        mid = aB + d/2
        if abs(norm(mid-aL)) < np.pi/2:
            return d
    return d1


# =========================================================
# VALIDACION contra .asc crudo de CATIA
# =========================================================
def load_asc(path):
    pts = []
    for ln in open(path, encoding="utf-8", errors="ignore"):
        q = ln.replace(",", ".").split()
        if len(q) == 3:
            try: pts.append((float(q[0]), float(q[2])))   # plano ZX -> (x,z)
            except ValueError: pass
    return np.array(pts)


def to_canonical(P, n_le=290, n_te=10):
    """Lleva una nube (mm) al frame canonico: LE origen, TE en +x, escala 1/cuerda."""
    le_raw, te_raw = P[:n_le], P[n_le:n_le+n_te]
    te_ref = te_raw.mean(axis=0)
    le_ref = le_raw[int(np.argmax(np.linalg.norm(le_raw - te_ref, axis=1)))]
    chord_vec = te_ref - le_ref
    chord = np.linalg.norm(chord_vec)
    ex = chord_vec/chord; ey = np.array([-ex[1], ex[0]])
    Q = np.column_stack([(P-le_ref) @ ex, (P-le_ref) @ ey]) / chord
    return Q, chord


def nn_error(gen, real):
    """Distancia de cada punto generado al polilinea real (y viceversa)."""
    from scipy.spatial import cKDTree
    # densificar real por si acaso
    tr = cKDTree(real)
    d1, _ = tr.query(gen)
    tg = cKDTree(gen)
    d2, _ = tg.query(real)
    return max(d1.max(), d2.max()), (d1.mean()+d2.mean())/2


if __name__ == "__main__":
    import pandas as pd
    BASE = os.path.dirname(os.path.abspath(__file__))
    df = pd.read_csv(os.path.join(BASE, "airfoil_dataset.csv"))
    SHAPE = ["chord_length_mm", "leading_edge_angle_deg", "leading_edge_thickness_level",
             "trailing_edge_angle_deg", "trailing_edge_thickness_mm",
             "te_upr_angle_deg", "te_lwr_angle_deg"]
    tests = ["0014_20260711_193032", "0004_20260712_214451",
             "0005_20260713_141006", "0001_20260628_221136"]
    print(f"{'run_id':26s}{'cuerda':>8s}{'err_max%':>10s}{'err_med%':>10s}")
    for rid in tests:
        row = df[df.run_id == rid]
        asc_p = os.path.join(BASE, "dataset_runs", rid, "auto_export.asc")
        if row.empty or not os.path.exists(asc_p):
            print(f"{rid:26s}  (falta CSV o .asc)"); continue
        p = {k: row.iloc[0][k] for k in SHAPE}
        gen, dbg = generate_contour(p)
        real, chord = to_canonical(load_asc(asc_p))
        emax, emed = nn_error(gen, real)
        print(f"{rid:26s}{chord:>8.1f}{emax*100:>9.3f}%{emed*100:>9.3f}%")
