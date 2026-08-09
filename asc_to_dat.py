import os
import sys
import numpy as np
import matplotlib.pyplot as plt


# =========================================================
# CONFIG
# =========================================================
from rutas import BASE as _BASE
DEFAULT_INPUT_ASC = os.path.join(_BASE, "auto_export.asc")
DEFAULT_OUTPUT_DAT = os.path.join(_BASE, "airfoil_v4.dat")

PROFILE_NAME = "AIRFOIL_LE_TE_V4"

N_LE = 290
N_TE = 10

PLANE_MODE = "XZ"

# Para visualizar cerrado, lo dejamos True.
# Si luego XFOIL se queja, lo ponemos en False.
ADD_TE_CLOSURE = True
N_TE_CLOSURE_FALLBACK = 30


# =========================================================
# READ ASC
# =========================================================
def read_asc_points(filepath, plane_mode="XZ"):
    points = []

    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip().replace(",", ".")

            if not line:
                continue

            parts = line.split()

            # Saltar primera línea si es solo "400"
            if len(parts) == 1:
                continue

            if len(parts) < 3:
                continue

            try:
                x3 = float(parts[0])
                y3 = float(parts[1])
                z3 = float(parts[2])

                if not (np.isfinite(x3) and np.isfinite(y3) and np.isfinite(z3)):
                    continue

                if plane_mode == "XZ":
                    points.append([x3, z3])
                elif plane_mode == "XY":
                    points.append([x3, y3])
                else:
                    raise ValueError("PLANE_MODE debe ser 'XZ' o 'XY'")

            except Exception:
                continue

    points = np.array(points, dtype=float)

    if len(points) < N_LE:
        raise ValueError(f"ASC incompleto: leídos {len(points)}, esperados al menos {N_LE}")

    return points


def remove_consecutive_duplicates(points, tol=1e-8):
    if len(points) == 0:
        return points

    cleaned = [points[0]]
    for p in points[1:]:
        if np.linalg.norm(p - cleaned[-1]) > tol:
            cleaned.append(p)

    return np.array(cleaned, dtype=float)

# =========================================================
# NORMALIZACIÓN
# =========================================================
def project_to_chord_system(le_raw, te_raw):
    """
    Usa:
    - TE reference = media del bloque TE
    - LE reference = punto del bloque LE más alejado del TE

    Esto evita depender de nombres del árbol.
    """

    le_raw = remove_consecutive_duplicates(le_raw)
    te_raw = remove_consecutive_duplicates(te_raw)

    if len(te_raw) >= 2:
        te_ref = np.mean(te_raw, axis=0)
    else:
        # fallback: punto de LE con x máximo
        te_ref = le_raw[int(np.argmax(le_raw[:, 0]))]

    distances = np.linalg.norm(le_raw - te_ref, axis=1)
    le_ref = le_raw[int(np.argmax(distances))]

    chord_vec = te_ref - le_ref
    chord = float(np.linalg.norm(chord_vec))

    if chord < 1e-9:
        raise ValueError("Cuerda inválida: LE y TE demasiado cerca")

    ex = chord_vec / chord
    ey = np.array([-ex[1], ex[0]], dtype=float)

    def project(points):
        out = []
        for p in points:
            v = p - le_ref
            x = float(np.dot(v, ex) / chord)
            y = float(np.dot(v, ey) / chord)
            out.append([x, y])
        return np.array(out, dtype=float)

    le_norm = project(le_raw)
    te_norm = project(te_raw) if len(te_raw) else np.empty((0, 2))

    # Reescalar X exactamente 0-1 usando el contorno principal LE
    x_min = float(np.min(le_norm[:, 0]))
    x_max = float(np.max(le_norm[:, 0]))

    if abs(x_max - x_min) < 1e-9:
        raise ValueError("No se puede normalizar: x_min y x_max casi iguales")

    le_norm[:, 0] = (le_norm[:, 0] - x_min) / (x_max - x_min)

    if len(te_norm):
        te_norm[:, 0] = (te_norm[:, 0] - x_min) / (x_max - x_min)

    return le_norm, te_norm, chord


# =========================================================
# ORDEN XFOIL
# =========================================================
def cyclic_segment(points, start_idx, end_idx):
    """
    Segmento circular desde start_idx hasta end_idx, incluyendo ambos.
    """
    if start_idx <= end_idx:
        return points[start_idx:end_idx + 1]

    return np.vstack([
        points[start_idx:],
        points[:end_idx + 1]
    ])


def order_le_chain_for_xfoil(le_norm):
    """
    Convierte el bloque LE completo en una cadena:
    TE upper -> contorno -> LE -> contorno -> TE lower

    Si el bloque LE ya está ordenado, solo lo rota.
    """

    pts = remove_consecutive_duplicates(le_norm)

    # Candidatos de TE: puntos más a la derecha
    x = pts[:, 0]
    x_max = float(np.max(x))
    te_zone_idx = np.where(x > x_max - 0.03)[0]

    if len(te_zone_idx) < 2:
        te_zone_idx = np.argsort(x)[-20:]

    # TE upper = mayor y en zona TE
    # TE lower = menor y en zona TE
    te_upper_idx = int(te_zone_idx[np.argmax(pts[te_zone_idx, 1])])
    te_lower_idx = int(te_zone_idx[np.argmin(pts[te_zone_idx, 1])])

    if te_upper_idx == te_lower_idx:
        # fallback si solo detecta un punto
        te_upper_idx = int(np.argmax(x))
        te_lower_idx = int(np.argmax(x))

    path_a = cyclic_segment(pts, te_upper_idx, te_lower_idx)
    path_b = cyclic_segment(pts, te_lower_idx, te_upper_idx)

    # La ruta buena debe pasar por el leading edge, es decir, tener x mínimo pequeño
    min_a = float(np.min(path_a[:, 0]))
    min_b = float(np.min(path_b[:, 0]))

    if min_a <= min_b:
        chain = path_a
    else:
        chain = path_b[::-1]

    # Asegurar que empieza arriba y termina abajo
    if chain[0, 1] < chain[-1, 1]:
        chain = chain[::-1]

    # Forzar rangos pequeños
    chain[:, 0] = np.clip(chain[:, 0], 0.0, 1.0)

    return remove_consecutive_duplicates(chain)




def orient_y_positive_upper(chain):
    """
    Si el perfil sale boca abajo, invertimos y.
    """
    pts = chain.copy()

    # Antes del LE suele estar la cara superior si el orden es TE upper -> LE
    le_idx = int(np.argmin(pts[:, 0]))

    upper_part = pts[:le_idx + 1]
    lower_part = pts[le_idx:]

    if len(upper_part) > 5 and len(lower_part) > 5:
        if np.mean(upper_part[:, 1]) < np.mean(lower_part[:, 1]):
            pts[:, 1] *= -1.0

    return pts




def append_te_block_closure(chain, te_norm):
    """
    Añade el bloque TE real al final de la cadena.

    La cadena principal LE viene:
    TE UPR -> perfil completo -> TE LWR

    El bloque TE debe cerrar:
    TE LWR -> TE UPR

    Esta versión fuerza el bloque TE a enganchar exactamente:
    - inicio del TE = final de la cadena principal
    - final del TE = inicio de la cadena principal
    """

    pts = remove_consecutive_duplicates(np.array(chain, dtype=float))
    te = remove_consecutive_duplicates(np.array(te_norm, dtype=float))

    if len(te) < 2:
        print("[TE BLOCK] No hay suficientes puntos TE. Se deja la cadena sin TE real.")
        return pts

    # El TE debe ir desde el final de la cadena hasta el inicio
    target_start = pts[-1].copy()   # TE lower real de la cadena principal
    target_end = pts[0].copy()      # TE upper real de la cadena principal

    # Elegir orientación del TE
    d_normal = np.linalg.norm(te[0] - target_start) + np.linalg.norm(te[-1] - target_end)
    d_reverse = np.linalg.norm(te[-1] - target_start) + np.linalg.norm(te[0] - target_end)

    if d_reverse < d_normal:
        te = te[::-1]

    # Reparametrizar el bloque TE entre target_start y target_end.
    # Esto conserva el reparto de puntos, pero garantiza cierre exacto.
    s_vals = np.linspace(0.0, 1.0, len(te))

    te_fixed = []
    for s in s_vals:
        p = (1.0 - s) * target_start + s * target_end
        te_fixed.append(p)

    te_fixed = np.array(te_fixed, dtype=float)

    out = np.vstack([
        pts,
        te_fixed[1:]
    ])

    out = remove_consecutive_duplicates(out)

    print("\n[TE BLOCK CLOSURE FIXED]")
    print(f"target_start = {target_start}")
    print(f"target_end   = {target_end}")
    print(f"te_fixed[0]  = {te_fixed[0]}")
    print(f"te_fixed[-1] = {te_fixed[-1]}")
    print(f"TE points added = {len(te_fixed) - 1}")

    return out

def force_chain_closed(chain, tol=1e-8):
    pts = remove_consecutive_duplicates(np.array(chain, dtype=float))

    start = pts[0].copy()
    end = pts[-1].copy()

    gap = np.linalg.norm(start - end)

    print("\n[FORCE CLOSED CHAIN]")
    print(f"start = {start}")
    print(f"end   = {end}")
    print(f"gap   = {gap:.8f}")

    if gap < tol:
        print("[FORCE CLOSED CHAIN] Ya estaba cerrado.")
        return pts

    pts_closed = np.vstack([
        pts,
        start.reshape(1, 2)
    ])

    print("[FORCE CLOSED CHAIN] Punto inicial añadido al final.")
    return pts_closed

def densify_final_te_gap(chain, n_insert=3, min_dx=0.012, only_after_x=0.90):
    """
    Inserta puntos SOLO en el último salto del .dat.

    Caso típico:
        penúltimo punto = último punto real del intradós
        último punto    = primer punto repetido del extradós

    Ejemplo:
        0.972202 -0.006795
        0.997596  0.011169

    Queremos meter 2/3 puntos entre ambos para que XFOIL no vea un salto tan brusco.
    """

    pts = np.array(chain, dtype=float)

    if len(pts) < 3:
        return pts

    p0 = pts[-2].copy()   # penúltimo punto
    p1 = pts[-1].copy()   # último punto, normalmente start repetido

    dx = abs(p1[0] - p0[0])
    dy = abs(p1[1] - p0[1])

    near_te = min(p0[0], p1[0]) >= only_after_x

    print("\n[FINAL TE GAP CHECK]")
    print(f"p0 penúltimo = {p0}")
    print(f"p1 último    = {p1}")
    print(f"dx = {dx:.6f}")
    print(f"dy = {dy:.6f}")

    if not near_te:
        print("[FINAL TE GAP] No está cerca del TE. No se aplica.")
        return pts

    if dx < min_dx:
        print("[FINAL TE GAP] El salto en x es pequeño. No se aplica.")
        return pts

    # Crear puntos intermedios suaves entre p0 y p1
    bridge = []

    for k in range(1, n_insert + 1):
        t = k / (n_insert + 1)

        # smoothstep
        s = t * t * (3.0 - 2.0 * t)

        p_new = (1.0 - s) * p0 + s * p1
        bridge.append(p_new)

    bridge = np.array(bridge, dtype=float)

    pts_new = np.vstack([
        pts[:-1],
        bridge,
        pts[-1:]
    ])

    print(f"[FINAL TE GAP] Insertados {len(bridge)} puntos antes del cierre final")

    return pts_new

# =========================================================
# WRITE / PLOT
# =========================================================
def write_dat(filepath, chain):
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(PROFILE_NAME + "\n")
        for x, y in chain:
            f.write(f"{x:.6f} {y:.6f}\n")


def plot_chain(chain):
    plt.figure(figsize=(12, 4))
    plt.plot(chain[:, 0], chain[:, 1], linewidth=1.5, label="airfoil")
    plt.scatter([chain[0, 0]], [chain[0, 1]], marker="o", label="start")
    plt.scatter([chain[-1, 0]], [chain[-1, 1]], marker="x", label="end")
    plt.axis("equal")
    plt.grid(True)
    plt.xlabel("x/c")
    plt.ylabel("y/c")
    plt.title("Airfoil V4 desde ASC LE + TE")
    plt.legend()
    #plt.show()


# =========================================================
# MAIN
# =========================================================
def main(input_asc=DEFAULT_INPUT_ASC, output_dat=DEFAULT_OUTPUT_DAT):
    print("\n[ASC LE+TE -> DAT V4]")
    print(f"[INFO] Input ASC : {input_asc}")
    print(f"[INFO] Output DAT: {output_dat}")

    points = read_asc_points(input_asc, plane_mode=PLANE_MODE)

    print(f"[OK] Puntos leídos del ASC: {len(points)}")

    if len(points) < N_LE + N_TE:
        print("[WARN] Hay menos puntos de los esperados. Se usará lo disponible.")

    le_raw = points[:N_LE]
    te_raw = points[N_LE:N_LE + N_TE]
    # El bloque LE ya va de TE UPR -> TE LWR.
    # El bloque TE, tal como sale de CATIA, también va de TE UPR -> TE LWR.
    # Para cerrar bien el contorno, necesitamos invertir TE:
    # TE LWR -> TE UPR.
    if len(te_raw) > 0:
        te_raw = te_raw[::-1]

    print(f"[OK] LE raw: {len(le_raw)} puntos")
    print(f"[OK] TE raw: {len(te_raw)} puntos")

    le_norm, te_norm, chord = project_to_chord_system(le_raw, te_raw)

    chain = order_le_chain_for_xfoil(le_norm)
    chain = orient_y_positive_upper(chain)

    chain = append_te_block_closure(chain, te_norm)

    # Primero forzamos el cierre, porque AQUÍ se crea el salto final
    chain = force_chain_closed(chain)

    # Ahora sí: metemos 3 puntos solo entre el penúltimo y el último punto
    chain = densify_final_te_gap(
    chain,
    n_insert=3,
    min_dx=0.012,
    only_after_x=0.90
    )

    write_dat(output_dat, chain)

    print(f"[OK] Cuerda aprox: {chord:.6f} mm")
    print(f"[OK] Puntos DAT : {len(chain)}")
    print(f"[OK] DAT creado : {os.path.abspath(output_dat)}")

    print("\n[DEBUG]")
    print(f"start = {chain[0]}")
    print(f"end   = {chain[-1]}")
    print(f"x min/max = {chain[:,0].min():.6f} / {chain[:,0].max():.6f}")
    print(f"y min/max = {chain[:,1].min():.6f} / {chain[:,1].max():.6f}")

    plot_chain(chain)

    return 0


if __name__ == "__main__":
    input_asc = DEFAULT_INPUT_ASC
    output_dat = DEFAULT_OUTPUT_DAT

    if len(sys.argv) >= 2:
        input_asc = sys.argv[1]

    if len(sys.argv) >= 3:
        output_dat = sys.argv[2]

    sys.exit(main(input_asc, output_dat))