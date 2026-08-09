"""
Paso OPCIONAL y APARTE: genera el ala 3D en superficie sobre un CATPart YA
generado. No toca el pipeline de generacion (airfoil_generator / pipeline_airfoil_api
/ generate_batch quedan intactos).

Que hace sobre el Part ACTIVO de CATIA:
  1. Crea el Geometrical Set  "AIRFOIL 3D".
  2. Dentro, crea un Join     "AIRFOIL 3D" con las curvas indicadas
     (por defecto: LE ARC + TE PROFILE), con los mismos parametros que el join
     existente: SetConnex(1), SetManifold(0), SetSimplify(0), SetDeviation(0.001).
  3. Crea un Extrude sobre ese join en direccion Y, Limit1 = span (configurable),
     Limit2 = 0, sin extension simetrica (mirrored extent desactivado).
  4. Lo mete en "AIRFOIL 3D", actualiza y GUARDA el CATPart.

Uso:
    python airfoil_3d.py                          # span 600, curvas por defecto
    python airfoil_3d.py --span 400
    python airfoil_3d.py --curvas "UPR PROFILE,LE ARC,LWR PROFILE"
    python airfoil_3d.py --output "C:\\ruta\\ala.CATPart"
"""
import os
import sys
import argparse
import win32com.client
import pythoncom

SET_3D = "AIRFOIL 3D"
JOIN_3D = "AIRFOIL 3D"
EXTRUDE_3D = "AIRFOIL 3D EXTRUDE"
CURVAS_DEFECTO = ["LE ARC", "TE PROFILE"]

# Span por defecto = 900 mm, dentro del rango real de referencia:
#   ~600 mm  (Formula Student)  ...  ~1070 mm (F1 2026)
# Referencia FIA 2026: el flap del aleron trasero no puede exceder Y = 535 mm
# (de ahi ~1070 mm de envergadura total).
SPAN_DEFECTO = 900.0

# La extrusion es SOLO VISUAL: la aerodinamica del sistema sale del analisis
# XFOIL 2D del perfil. El span NO entra en ninguna prediccion (ni CL, ni CD, ni
# LD, ni Reynolds: el Reynolds se deriva de la CUERDA y la velocidad).
NOTA_VISUAL = (
    "[NOTA] La extrusion 3D es SOLO VISUAL (para inspeccion/render). La "
    "aerodinamica del sistema proviene del analisis XFOIL 2D del perfil: el SPAN "
    "NO afecta a ninguna prediccion (CL/CD/LD ni Reynolds, que se deriva de la "
    "cuerda y la velocidad). Cambiar el span no cambia ningun resultado aerodinamico."
)


def buscar_shape(part, nombre):
    """Busca un HybridShape por nombre recorriendo TODOS los Geometrical Sets."""
    def rec(hbs):
        for i in range(hbs.Count):
            hb = hbs.Item(i + 1)
            for j in range(hb.HybridShapes.Count):
                sh = hb.HybridShapes.Item(j + 1)
                if sh.Name == nombre:
                    return sh
            r = rec(hb.HybridBodies)
            if r is not None:
                return r
        return None
    return rec(part.HybridBodies)


def main():
    ap = argparse.ArgumentParser(description="Anade el ala 3D (extrude) a un CATPart ya generado.")
    ap.add_argument("--span", type=float, default=SPAN_DEFECTO,
                    help=f"Longitud del extrude en mm (Limit1). Por defecto {SPAN_DEFECTO:g} "
                         "(rango real de referencia: ~600 Formula Student a ~1070 F1 2026). "
                         "SOLO VISUAL: no afecta a ninguna prediccion aerodinamica.")
    ap.add_argument("--curvas", type=str, default=",".join(CURVAS_DEFECTO),
                    help="Curvas a unir en el join, separadas por comas. "
                         f"Por defecto: {','.join(CURVAS_DEFECTO)}")
    ap.add_argument("--output", type=str, default=None,
                    help="Ruta donde guardar el CATPart. Si se omite, se guarda junto "
                         "a este script como ala_3d.CATPart")
    args = ap.parse_args()

    curvas = [c.strip() for c in args.curvas.split(",") if c.strip()]
    if len(curvas) < 2:
        print("[ERROR] El join necesita al menos 2 curvas.")
        return 1

    pythoncom.CoInitialize()
    catia = win32com.client.GetActiveObject("CATIA.Application")
    doc = catia.ActiveDocument
    part = doc.Part
    print(f"[INFO] Documento activo: {doc.Name}")
    print(f"[INFO] Curvas del join : {curvas}")
    print(f"[INFO] Span (Limit1)   : {args.span:g} mm  |  Limit2 = 0 mm")
    print(NOTA_VISUAL)

    hsf = part.HybridShapeFactory

    # --- 1) Geometrical Set nuevo ---
    set_3d = part.HybridBodies.Add()
    set_3d.Name = SET_3D
    print(f"[OK] Geometrical Set creado: {SET_3D}")

    # --- 2) Join de las curvas indicadas ---
    elems = []
    for nombre in curvas:
        sh = buscar_shape(part, nombre)
        if sh is None:
            print(f"[ERROR] No encuentro la curva '{nombre}' en el Part.")
            return 1
        elems.append(sh)

    first_ref = part.CreateReferenceFromObject(elems[0])
    second_ref = part.CreateReferenceFromObject(elems[1])
    join = hsf.AddNewJoin(first_ref, second_ref)
    for sh in elems[2:]:
        join.AddElement(part.CreateReferenceFromObject(sh))

    join.SetConnex(1)
    join.SetManifold(0)
    join.SetSimplify(0)
    join.SetSuppressMode(0)
    join.SetDeviation(0.001)
    join.Name = JOIN_3D
    set_3d.AppendHybridShape(join)
    part.Update()
    print(f"[OK] Join creado: {JOIN_3D}  ({len(elems)} curvas)")

    # --- 3) Extrude en direccion Y ---
    direccion = hsf.AddNewDirectionByCoord(0.0, 1.0, 0.0)      # eje Y = span
    join_ref = part.CreateReferenceFromObject(join)
    extrude = hsf.AddNewExtrude(join_ref, args.span, 0.0, direccion)
    try:
        extrude.SymmetricalExtension = False                   # sin mirrored extent
    except Exception as e:
        print(f"[WARN] No pude fijar SymmetricalExtension ({e}); se deja por defecto.")
    extrude.Name = EXTRUDE_3D

    # --- 4) Al set, actualizar y guardar ---
    set_3d.AppendHybridShape(extrude)
    part.Update()
    print(f"[OK] Extrude creado: {EXTRUDE_3D}  (direccion Y, {args.span:g} mm)")

    salida = args.output or os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                         "ala_3d.CATPart")
    doc.SaveAs(salida)
    print(f"[OK] CATPart guardado en: {salida}")
    print(NOTA_VISUAL)
    return 0


if __name__ == "__main__":
    sys.exit(main())
