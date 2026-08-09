import csv
import os
import sys
import traceback
from typing import List, Tuple, Optional

import pythoncom
import win32com.client


# =========================================================
# CONFIG
# =========================================================
AIRFOIL_SET_NAME = "AIRFOIL"
CONSTRUCTION_SET_NAME = "AIRFOIL CONSTRUCTION"
CONTROL_SET_NAME = "CONTROLS"

UPR_PROFILE_NAME = "UPR PROFILE"
LE_ARC_NAME = "LE ARC"
LWR_PROFILE_NAME = "LWR PROFILE"
TE_PROFILE_NAME = "TE PROFILE"

EXPORT_SET_NAME = "POINTS_FOR_EXPORT"
DEFAULT_OUTPUT_CSV = "airfoil_points_xyz.csv"

DEFAULT_COUNTS = {
    "UPR": 0,
    "LE": 290,
    "LWR": 0,
    "TE": 10,
}


# =========================================================
# CATIA HELPERS
# =========================================================
def get_active_part_document():
    catia = win32com.client.Dispatch("CATIA.Application")
    part_doc = catia.ActiveDocument
    part = part_doc.Part
    return catia, part_doc, part


def find_hybrid_body_recursive(parent_hybrid_bodies, target_name: str):
    for i in range(1, parent_hybrid_bodies.Count + 1):
        hb = parent_hybrid_bodies.Item(i)
        if hb.Name == target_name:
            return hb

        child = find_hybrid_body_recursive(hb.HybridBodies, target_name)
        if child is not None:
            return child
    return None


def find_shape_recursive(hybrid_body, target_name: str):
    shapes = hybrid_body.HybridShapes
    for i in range(1, shapes.Count + 1):
        s = shapes.Item(i)
        if s.Name == target_name:
            return s

    child_bodies = hybrid_body.HybridBodies
    for i in range(1, child_bodies.Count + 1):
        child = child_bodies.Item(i)
        found = find_shape_recursive(child, target_name)
        if found is not None:
            return found

    return None


def get_or_create_child_set(parent_hybrid_body, target_name: str):
    child_bodies = parent_hybrid_body.HybridBodies

    for i in range(1, child_bodies.Count + 1):
        hb = child_bodies.Item(i)
        if hb.Name == target_name:
            return hb

    new_set = child_bodies.Add()
    new_set.Name = target_name
    return new_set


def clear_hybrid_body_contents(part_doc, hybrid_body) -> None:
    """
    Borra el contenido del set usando Selection.Delete.
    """
    selection = part_doc.Selection
    selection.Clear()

    try:
        hs = hybrid_body.HybridShapes
        for i in range(1, hs.Count + 1):
            selection.Add(hs.Item(i))

        hbs = hybrid_body.HybridBodies
        for i in range(1, hbs.Count + 1):
            selection.Add(hbs.Item(i))

        if selection.Count > 0:
            selection.Delete()
    finally:
        selection.Clear()


def create_point_on_curve_percent(part, target_set, curve_obj, percent: float, point_name: str):
    hsf = part.HybridShapeFactory
    curve_ref = part.CreateReferenceFromObject(curve_obj)

    pt = hsf.AddNewPointOnCurveFromPercent(curve_ref, percent, False)
    pt.Name = point_name
    target_set.AppendHybridShape(pt)

    part.InWorkObject = pt
    part.Update()

    return pt


def get_point_xyz(part_doc, part, point_obj) -> Optional[List[float]]:
    """
    Intenta medir coordenadas XYZ del punto creado.
    Si CATIA devuelve basura o no deja medir, devolvemos None.
    """
    try:
        spa = part_doc.GetWorkbench("SPAWorkbench")
        ref = part.CreateReferenceFromObject(point_obj)
        measurable = spa.GetMeasurable(ref)

        coords = [0.0, 0.0, 0.0]
        measurable.GetPoint(coords)

        xyz = [float(coords[0]), float(coords[1]), float(coords[2])]

        # filtro defensivo: si todo es 0, lo consideramos no fiable
        if abs(xyz[0]) < 1e-12 and abs(xyz[1]) < 1e-12 and abs(xyz[2]) < 1e-12:
            return None

        return xyz

    except Exception as e:
        point_name = getattr(point_obj, 'Name', '?')
        print(f"[WARN] get_point_xyz falló en '{point_name}': {type(e).__name__}: {e}")
        return None


# =========================================================
# EXPORT LOGIC
# =========================================================
def sample_curve_points(
    part_doc,
    part,
    export_set,
    curve_obj,
    group_name: str,
    n_points: int,
) -> Tuple[int, int, List[Tuple[str, int, float, float, float, float]]]:
    created = 0
    measured_ok = 0
    rows = []

    for i in range(n_points):
        t = i / (n_points - 1) if n_points > 1 else 0.0
        point_name = f"{group_name}_{i:03d}"

        pt = create_point_on_curve_percent(part, export_set, curve_obj, t, point_name)
        created += 1

        xyz = get_point_xyz(part_doc, part, pt)
        if xyz is not None:
            measured_ok += 1
            rows.append((group_name, i, t, xyz[0], xyz[1], xyz[2]))
        else:
            rows.append((group_name, i, t, float("nan"), float("nan"), float("nan")))

    return created, measured_ok, rows


def write_csv(rows, output_csv: str) -> None:
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["group", "index", "percent", "x_mm", "y_mm", "z_mm"])
        for row in rows:
            group_name, idx, t, x, y, z = row
            writer.writerow([group_name, idx, f"{t:.6f}", x, y, z])


# =========================================================
# MAIN
# =========================================================
def main(output_csv: str = DEFAULT_OUTPUT_CSV) -> int:
    pythoncom.CoInitialize()

    try:
        catia, part_doc, part = get_active_part_document()
        print(f"[OK] Documento activo: {part_doc.Name}")

        root_hbs = part.HybridBodies

        airfoil_set = find_hybrid_body_recursive(root_hbs, AIRFOIL_SET_NAME)
        if airfoil_set is None:
            raise ValueError(f"No se encontró el set '{AIRFOIL_SET_NAME}'")

        construction_set = find_hybrid_body_recursive(root_hbs, CONSTRUCTION_SET_NAME)
        if construction_set is None:
            raise ValueError(f"No se encontró el set '{CONSTRUCTION_SET_NAME}'")

        controls_set = find_hybrid_body_recursive(root_hbs, CONTROL_SET_NAME)
        if controls_set is None:
            raise ValueError(f"No se encontró el set '{CONTROL_SET_NAME}'")

        # Curvas según tu árbol real
        upr_profile = find_shape_recursive(construction_set, UPR_PROFILE_NAME)
        le_arc = find_shape_recursive(construction_set, LE_ARC_NAME)
        lwr_profile = find_shape_recursive(construction_set, LWR_PROFILE_NAME)

        te_profile = find_shape_recursive(construction_set, TE_PROFILE_NAME)
        if te_profile is None:
            te_profile = find_shape_recursive(controls_set, TE_PROFILE_NAME)

        missing = []
        if upr_profile is None:
            missing.append(UPR_PROFILE_NAME)
        if le_arc is None:
            missing.append(LE_ARC_NAME)
        if lwr_profile is None:
            missing.append(LWR_PROFILE_NAME)
        if te_profile is None:
            missing.append(TE_PROFILE_NAME)

        if missing:
            raise ValueError(f"Faltan curvas necesarias: {missing}")

        export_set = get_or_create_child_set(airfoil_set, EXPORT_SET_NAME)
        clear_hybrid_body_contents(part_doc, export_set)
        part.Update()

        print(f"[OK] Set de exportación preparado: {EXPORT_SET_NAME}")

        all_rows = []
        summary = []

        curves = [
            ("UPR", upr_profile, DEFAULT_COUNTS["UPR"]),
            ("LE", le_arc, DEFAULT_COUNTS["LE"]),
            ("LWR", lwr_profile, DEFAULT_COUNTS["LWR"]),
            ("TE", te_profile, DEFAULT_COUNTS["TE"]),
        ]

        for group_name, curve_obj, n_points in curves:
            if n_points <= 0:
               print(f"[SKIP] {group_name}: 0 puntos")
               summary.append((group_name, 0, 0))
               continue

            print(f"[INFO] Muestreando {group_name} con {n_points} puntos...")
            created, measured_ok, rows = sample_curve_points(
                part_doc=part_doc,
                part=part,
                export_set=export_set,
                curve_obj=curve_obj,
                group_name=group_name,
                n_points=n_points,
            )
            all_rows.extend(rows)
            summary.append((group_name, created, measured_ok))

        output_csv = os.path.abspath(output_csv)
        write_csv(all_rows, output_csv)

        print("\n[RESUMEN]")
        total_created = 0
        total_measured = 0
        for group_name, created, measured_ok in summary:
            total_created += created
            total_measured += measured_ok
            print(f"  {group_name}: creados={created}, medidos_ok={measured_ok}")

        print(f"\n[OK] CSV exportado: {output_csv}")
        print(f"[OK] Total puntos creados: {total_created}")
        print(f"[OK] Total puntos medidos bien: {total_measured}")

        if total_measured == 0:
            print(
                "\n[AVISO] Se han creado todos los puntos, pero CATIA no ha devuelto "
                "coordenadas medibles en esta sesión. Aun así, el set POINTS_FOR_EXPORT "
                "queda listo para usarlo con la nube de puntos/export ASCII."
            )

        return 0

    except Exception as e:
        print("\n[ERROR]")
        print(str(e))
        traceback.print_exc()
        return 1

    finally:
        pythoncom.CoUninitialize()


if __name__ == "__main__":
    output_csv = DEFAULT_OUTPUT_CSV
    if len(sys.argv) > 1:
        output_csv = sys.argv[1]

    sys.exit(main(output_csv))