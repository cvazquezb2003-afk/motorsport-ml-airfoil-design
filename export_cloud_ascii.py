import os
import sys
import time
import glob
import shutil
import traceback

import pythoncom
import win32com.client

from pywinauto import Desktop
from pywinauto.keyboard import send_keys


AIRFOIL_SET_NAME = "AIRFOIL"
POINTS_SET_NAME = "POINTS_FOR_EXPORT"
from rutas import BASE as _BASE
DEFAULT_OUTPUT_ASC = os.path.join(_BASE, "auto_export.asc")


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


def list_all_clouds_recursive(hybrid_bodies):
    found = []

    def walk(hbs):
        for i in range(1, hbs.Count + 1):
            hb = hbs.Item(i)

            hs = hb.HybridShapes
            for j in range(1, hs.Count + 1):
                s = hs.Item(j)
                try:
                    name = s.Name
                except Exception:
                    continue

                if name.startswith("Cloud of Points"):
                    found.append(s)

            walk(hb.HybridBodies)

    walk(hybrid_bodies)
    return found


def wait_for_new_cloud(root_hbs, previous_count: int, timeout_s: float = 10.0, poll_s: float = 0.4):
    start = time.time()
    while time.time() - start < timeout_s:
        clouds = list_all_clouds_recursive(root_hbs)
        if len(clouds) > previous_count:
            return clouds[-1]
        time.sleep(poll_s)
    return None


def selection_add_all_points_from_set(part_doc, points_set) -> int:
    selection = part_doc.Selection
    selection.Clear()

    count = 0
    hs = points_set.HybridShapes
    for i in range(1, hs.Count + 1):
        obj = hs.Item(i)
        selection.Add(obj)
        count += 1

    return count


def wait_window(title_regex: str, timeout_s: float = 10.0, backend: str = "win32"):
    start = time.time()
    desk = Desktop(backend=backend)

    while time.time() - start < timeout_s:
        try:
            wins = desk.windows(title_re=title_regex, visible_only=True)
            if wins:
                return wins[0]
        except Exception:
            pass
        time.sleep(0.25)

    return None


def find_latest_cloud_by_selection_search(part_doc):
    """
    Busca cualquier 'Cloud of Points*' usando Selection.Search,
    que suele ser más fiable que recorrer el árbol manualmente.
    """
    selection = part_doc.Selection
    selection.Clear()

    selection.Search("Name='Cloud of Points*',all")

    if selection.Count == 0:
        selection.Clear()
        return None

    found = []
    for i in range(1, selection.Count + 1):
        try:
            obj = selection.Item(i).Value
            found.append(obj)
        except Exception:
            pass

    selection.Clear()

    if not found:
        return None

    def extract_cloud_index(name: str) -> int:
        try:
            if "." in name:
                return int(name.split(".")[-1])
        except Exception:
            pass
        return 0

    found.sort(key=lambda o: extract_cloud_index(o.Name))
    return found[-1]


def wait_for_cloud(part_doc, part, timeout_s=10.0, poll_s=0.25):
    """
    Espera (polling) a que exista una 'Cloud of Points' localizable por
    Selection.Search tras confirmar el diálogo 'Cloud / Points'.
    Devuelve el objeto en cuanto aparece, o None si expira el timeout.
    """
    start = time.time()
    try:
        part.Update()
    except Exception:
        pass
    while time.time() - start < timeout_s:
        cloud = find_latest_cloud_by_selection_search(part_doc)
        if cloud is not None:
            return cloud
        time.sleep(poll_s)
    return None


def click_button_in_window(win, candidates):
    """
    Intenta pulsar uno de varios nombres posibles de botón.
    """
    for name in candidates:
        try:
            btn = win.child_window(title=name, control_type="Button")
            if btn.exists():
                btn.click_input()
                return True
        except Exception:
            pass

    try:
        for ctrl in win.descendants():
            try:
                txt = ctrl.window_text()
                if txt in candidates:
                    ctrl.click_input()
                    return True
            except Exception:
                pass
    except Exception:
        pass

    return False


def move_latest_asc_to_folder(target_folder, filename="auto_export.asc"):
    """
    Busca el archivo .asc o .asc_rgb más reciente en el Desktop
    y lo mueve a la carpeta destino con el nombre indicado.
    """
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")

    patterns = ["*.asc", "*.asc_rgb"]
    candidates = []

    for pattern in patterns:
        files = glob.glob(os.path.join(desktop, pattern))
        candidates.extend(files)

    if not candidates:
        print("[ERROR] No se encontró ningún archivo .asc/.asc_rgb en Desktop")
        return None

    candidates.sort(key=os.path.getmtime, reverse=True)
    latest_file = candidates[0]

    print(f"[INFO] Archivo detectado en Desktop: {latest_file}")

    os.makedirs(target_folder, exist_ok=True)

    destination_path = os.path.join(target_folder, filename)

    try:
        if os.path.exists(destination_path):
            os.remove(destination_path)

        shutil.move(latest_file, destination_path)
        print(f"[OK] Archivo movido a: {destination_path}")
        return destination_path
    except Exception as e:
        print(f"[ERROR] No se pudo mover el archivo: {e}")
        return None


def wait_for_fresh_asc(desktop_dir, since_ts, timeout_s=10.0, poll_s=0.25):
    """
    Espera (polling) a que aparezca un .asc/.asc_rgb en el Desktop escrito
    por ESTE export (mtime >= since_ts). Devuelve la ruta o None si expira.
    """
    patterns = ["*.asc", "*.asc_rgb"]
    start = time.time()
    while time.time() - start < timeout_s:
        candidates = []
        for pat in patterns:
            for f in glob.glob(os.path.join(desktop_dir, pat)):
                try:
                    if os.path.getmtime(f) >= since_ts - 1.0:
                        candidates.append(f)
                except OSError:
                    pass
        if candidates:
            candidates.sort(key=os.path.getmtime, reverse=True)
            return candidates[0]
        time.sleep(poll_s)
    return None


def create_cloud_with_ui(catia, part_doc, part):
    """
    Lanza Cloud / Points, pulsa Apply y OK usando pywinauto.
    Después busca la nube creada con Selection.Search.
    """
    print("[INFO] Lanzando 'Cloud / Points'...")
    catia.StartCommand("Cloud / Points")

    win = wait_window(r"Cloud / Points", timeout_s=8.0, backend="win32")
    if win is None:
        raise RuntimeError("No apareció la ventana 'Cloud / Points'")

    try:
        win.set_focus()
    except Exception:
        pass

    ok_apply = click_button_in_window(win, ["Apply", "&Apply"])
    if not ok_apply:
        raise RuntimeError("No se pudo pulsar 'Apply' en la ventana 'Cloud / Points'")

    time.sleep(1.5)

    ok_ok = click_button_in_window(win, ["OK", "&OK"])
    if not ok_ok:
        print("[AVISO] No se pudo pulsar 'OK' automáticamente; seguimos igualmente.")

    # Polling en vez de dormir 1.0 + 2.0 s a ciegas: devuelve en cuanto la
    # nube aparece (rápido en el caso normal) y falla con mensaje claro si no.
    cloud_obj = wait_for_cloud(part_doc, part, timeout_s=10.0, poll_s=0.25)
    if cloud_obj is None:
        raise RuntimeError(
            "Tras pulsar OK en 'Cloud / Points', la nube no apareció en 10 s "
            "(Selection.Search no encontró 'Cloud of Points')."
        )

    return cloud_obj


def export_cloud_ascii_with_ui(catia, part_doc, cloud_obj, output_asc: str):
    """
    Selecciona la nube, lanza Export y guarda el archivo.
    En tu CATIA la ventana se llama 'Export'.
    """
    selection = part_doc.Selection
    selection.Clear()
    selection.Add(cloud_obj)

    print("[INFO] Lanzando 'Export'...")
    catia.StartCommand("Export")

    export_win = wait_window(r"Export", timeout_s=10.0, backend="win32")
    if export_win is None:
        raise RuntimeError("No apareció la ventana 'Export'")

    try:
        export_win.set_focus()
    except Exception:
        pass

    output_asc = os.path.abspath(output_asc)
    print(f"[INFO] Ruta objetivo deseada: {output_asc}")

    wrote = False

    try:
        edits = export_win.descendants(control_type="Edit")
        for e in edits:
            try:
                filename = os.path.basename(output_asc)
                e.set_edit_text(filename)
                print(f"[INFO] Nombre enviado a CATIA: {filename}")
                wrote = True
                break
            except Exception:
                pass
    except Exception:
        pass

    if not wrote:
        filename = os.path.basename(output_asc)
        send_keys(filename, with_spaces=True, pause=0.01)
        print(f"[INFO] Nombre enviado por teclado a CATIA: {filename}")

    time.sleep(0.4)

    export_start = time.time()
    ok_clicked = click_button_in_window(export_win, ["OK", "&OK"])
    if not ok_clicked:
        send_keys("{ENTER}")
        time.sleep(1.0)

    # Polling en vez de dormir 2.0 s a ciegas: espera a que CATIA escriba
    # realmente el .asc en el Desktop, y falla claro si no aparece.
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    asc_path = wait_for_fresh_asc(desktop, export_start, timeout_s=10.0, poll_s=0.25)
    if asc_path is None:
        raise RuntimeError(
            "Tras confirmar 'Export', no apareció ningún .asc nuevo en el "
            "Desktop en 10 s (CATIA no escribió el archivo)."
        )
    return output_asc


def main(output_asc: str = DEFAULT_OUTPUT_ASC) -> int:
    pythoncom.CoInitialize()

    try:
        catia, part_doc, part = get_active_part_document()
        print(f"[OK] Documento activo: {part_doc.Name}")

        root_hbs = part.HybridBodies

        airfoil_set = find_hybrid_body_recursive(root_hbs, AIRFOIL_SET_NAME)
        if airfoil_set is None:
            raise ValueError(f"No se encontró el set '{AIRFOIL_SET_NAME}'")

        points_set = find_hybrid_body_recursive(root_hbs, POINTS_SET_NAME)
        if points_set is None:
            raise ValueError(f"No se encontró el set '{POINTS_SET_NAME}'")

        n_selected = selection_add_all_points_from_set(part_doc, points_set)
        if n_selected == 0:
            raise ValueError("No hay puntos en POINTS_FOR_EXPORT")

        print(f"[OK] Puntos seleccionados: {n_selected}")

        cloud_obj = create_cloud_with_ui(catia, part_doc, part)
        print(f"[OK] Nube creada: {cloud_obj.Name}")

        out_path = export_cloud_ascii_with_ui(catia, part_doc, cloud_obj, output_asc)
        print(f"[OK] Export lanzado: {out_path}")

        target_folder = _BASE
        final_path = move_latest_asc_to_folder(target_folder, filename="auto_export.asc")

        if final_path:
            print(f"[FINAL] Archivo listo en: {final_path}")
        else:
            print("[FINAL] No se pudo recuperar el archivo .asc")

        print(
            "\nSi CATIA tenía recordado 'ASCII free (*.asc)' como último formato, "
            "el archivo debería haberse guardado correctamente."
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
    output_asc = DEFAULT_OUTPUT_ASC
    if len(sys.argv) > 1:
        output_asc = sys.argv[1]

    sys.exit(main(output_asc))