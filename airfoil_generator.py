import json
import sys
import pythoncom
import win32com.client
import traceback


# =========================================================
# PARÁMETROS INTERNOS DEL MOTOR
# Estos son los que entiende el método geométrico actual
# =========================================================
DEFAULT_PARAMS = {
    # LE POINT
    "le_point_x_mm": 250.0,
    "le_point_y_mm": 0.0,

    # CHORD
    "chord_angle_deg": 350.0,
    "chord_start_length_mm": 0.0,
    "chord_end_length_mm": -200.0,

    # LE CONTROL LINE
    "le_control_angle_deg": 3.5,
    "le_control_start_length_mm": 0.0,
    "le_control_end_length_mm": 32.0,

    # TE CONTROL LINE
    "te_control_angle_deg": 168.0,
    "te_control_start_length_mm": 0.0,
    "te_control_end_length_mm": 31.0,

    # POINT A
    "point_a_ratio": 0.055,

    # TE PROFILE
    "te_profile_angle_deg": 90.0,
    "te_profile_start_length_mm": -1.144,
    "te_profile_end_length_mm": 1.144,

    # TE UPR CONTROL LINE
    "te_upr_control_angle_deg": 10.0,
    "te_upr_control_start_length_mm": 0.0,
    "te_upr_control_end_length_mm": -16.0,

    # TE LWR CONTROL LINE
    "te_lwr_control_angle_deg": -2.0,
    "te_lwr_control_start_length_mm": 0.0,
    "te_lwr_control_end_length_mm": -16.0,

    # NORMALES EN POINT A
    "normal_point_a_angle_deg": -90.0,
    "normal_point_a_start_length_mm": 0.0,
    "normal_point_a_end_length_mm": 500.0,
    "opposite_normal_point_a_angle_deg": 90.0,
    "opposite_normal_point_a_start_length_mm": 0.0,
    "opposite_normal_point_a_end_length_mm": 500.0,

    # TANGENTES LE
    "le_upr_control_start_length_mm": 10.0,
    "le_upr_control_end_length_mm": -10.0,
    "le_lwr_control_start_length_mm": 10.0,
    "le_lwr_control_end_length_mm": -10.0,
}


# =========================================================
# PARÁMETROS DE USUARIO (V2)
# Interfaz técnica orientada a control geométrico real
# =========================================================
USER_DEFAULTS = {
    "chord_length_mm": 200.0,
    "chord_angle_deg": 350.0,

    "leading_edge_angle_deg": 3.5,
    "leading_edge_thickness_level": 0.5,

    "trailing_edge_angle_deg": 168.0,
    "trailing_edge_thickness_mm": 2.288,

    "te_upr_angle_deg": 10.0,
    "te_lwr_angle_deg": -2.0,
}


# =========================================================
# UTILIDADES MATEMÁTICAS
# =========================================================
def clamp(value, min_value, max_value):
    return max(min_value, min(value, max_value))


def lerp(a, b, t):
    return a + (b - a) * t


# =========================================================
# UTILIDADES GENERALES
# =========================================================
def append_and_update(part, target_set, shape):
    target_set.AppendHybridShape(shape)
    part.InWorkObject = shape
    part.Update()
    return shape


def get_shape(search_sets, shape_name):
    for geo_set in search_sets:
        try:
            return geo_set.HybridShapes.Item(shape_name)
        except Exception:
            continue
    raise ValueError(f"No se encontró la geometría '{shape_name}' en los sets indicados")


def merge_params(user_params=None):
    params = DEFAULT_PARAMS.copy()
    if user_params:
        params.update(user_params)
    return params


def validate_params(params):
    errors = []

    numeric_keys = [
        "le_point_x_mm",
        "le_point_y_mm",
        "chord_angle_deg",
        "chord_start_length_mm",
        "chord_end_length_mm",
        "le_control_angle_deg",
        "le_control_start_length_mm",
        "le_control_end_length_mm",
        "te_control_angle_deg",
        "te_control_start_length_mm",
        "te_control_end_length_mm",
        "point_a_ratio",
        "te_profile_angle_deg",
        "te_profile_start_length_mm",
        "te_profile_end_length_mm",
        "te_upr_control_angle_deg",
        "te_upr_control_start_length_mm",
        "te_upr_control_end_length_mm",
        "te_lwr_control_angle_deg",
        "te_lwr_control_start_length_mm",
        "te_lwr_control_end_length_mm",
        "normal_point_a_angle_deg",
        "normal_point_a_start_length_mm",
        "normal_point_a_end_length_mm",
        "opposite_normal_point_a_angle_deg",
        "opposite_normal_point_a_start_length_mm",
        "opposite_normal_point_a_end_length_mm",
        "le_upr_control_start_length_mm",
        "le_upr_control_end_length_mm",
        "le_lwr_control_start_length_mm",
        "le_lwr_control_end_length_mm",
    ]

    for key in numeric_keys:
        value = params.get(key)
        if not isinstance(value, (int, float)):
            errors.append(f"{key} debe ser numérico")

    if errors:
        return errors

    if not (0.0 < params["point_a_ratio"] < 1.0):
        errors.append("point_a_ratio debe estar entre 0 y 1")

    if params["chord_end_length_mm"] == 0.0 and params["chord_start_length_mm"] == 0.0:
        errors.append("La CHORD no puede tener longitud total cero")

    if params["te_profile_start_length_mm"] == params["te_profile_end_length_mm"]:
        errors.append("TE PROFILE necesita dos extremos distintos para definir espesor")

    return errors


def validate_user_params(user_params):
    errors = []

    for key in USER_DEFAULTS.keys():
        if key in user_params and not isinstance(user_params[key], (int, float)):
            errors.append(f"{key} debe ser numérico")

    if errors:
        return errors

    if "chord_length_mm" in user_params:
        if float(user_params["chord_length_mm"]) <= 0.0:
            errors.append("chord_length_mm debe ser mayor que 0")

    if "chord_angle_deg" in user_params:
        value = float(user_params["chord_angle_deg"])
        if not (-360.0 <= value <= 360.0):
            errors.append("chord_angle_deg debe estar entre -360 y 360 grados")

    if "leading_edge_angle_deg" in user_params:
        value = float(user_params["leading_edge_angle_deg"])
        if not (-20.0 <= value <= 20.0):
            errors.append("leading_edge_angle_deg debe estar entre -20 y 20 grados")

    if "leading_edge_thickness_level" in user_params:
        value = float(user_params["leading_edge_thickness_level"])
        if not (0.0 <= value <= 1.0):
            errors.append("leading_edge_thickness_level debe estar entre 0 y 1")

    if "trailing_edge_angle_deg" in user_params:
        value = float(user_params["trailing_edge_angle_deg"])
        if not (140.0 <= value <= 185.0):
            errors.append("trailing_edge_angle_deg debe estar entre 140 y 185 grados")

    if "trailing_edge_thickness_mm" in user_params:
        value = float(user_params["trailing_edge_thickness_mm"])
        if not (0.1 <= value <= 10.0):
            errors.append("trailing_edge_thickness_mm debe estar entre 0.1 y 10 mm")

    if "te_upr_angle_deg" in user_params:
        value = float(user_params["te_upr_angle_deg"])
        if not (-30.0 <= value <= 30.0):
            errors.append("te_upr_angle_deg debe estar entre -30 y 30 grados")

    if "te_lwr_angle_deg" in user_params:
        value = float(user_params["te_lwr_angle_deg"])
        if not (-30.0 <= value <= 30.0):
            errors.append("te_lwr_angle_deg debe estar entre -30 y 30 grados")

    return errors


# =========================================================
# TRADUCCIÓN: PARÁMETROS DE USUARIO -> PARÁMETROS INTERNOS
# =========================================================
def translate_user_to_internal(user_params=None):
    u = USER_DEFAULTS.copy()
    if user_params:
        u.update(user_params)

    chord_length = max(1.0, float(u["chord_length_mm"]))
    chord_angle_deg = float(u["chord_angle_deg"]) % 360

    leading_edge_angle_deg = clamp(float(u["leading_edge_angle_deg"]), -20.0, 20.0)
    leading_edge_thickness_level = clamp(float(u["leading_edge_thickness_level"]), 0.0, 1.0)

    trailing_edge_angle_deg = clamp(float(u["trailing_edge_angle_deg"]), 140.0, 185.0)
    trailing_edge_thickness_mm = max(0.1, float(u["trailing_edge_thickness_mm"]))

    te_upr_angle_deg = clamp(float(u["te_upr_angle_deg"]), -30.0, 30.0)
    te_lwr_angle_deg = clamp(float(u["te_lwr_angle_deg"]), -30.0, 30.0)

    internal = DEFAULT_PARAMS.copy()

    # LE POINT
    internal["le_point_x_mm"] = 250.0
    internal["le_point_y_mm"] = 0.0

    # CHORD
    internal["chord_angle_deg"] = chord_angle_deg
    internal["chord_start_length_mm"] = 0.0
    internal["chord_end_length_mm"] = -chord_length

    # LEADING EDGE
    internal["le_control_angle_deg"] = leading_edge_angle_deg
    internal["le_control_start_length_mm"] = 0.0
    internal["le_control_end_length_mm"] = 32.0

    # POINT A -> espesor delantero / radio LE
    internal["point_a_ratio"] = lerp(0.03, 0.08, leading_edge_thickness_level)

    # TRAILING EDGE BASE
    internal["te_control_angle_deg"] = trailing_edge_angle_deg
    internal["te_control_start_length_mm"] = 0.0
    internal["te_control_end_length_mm"] = 31.0

    # TRAILING EDGE THICKNESS en mm reales
    te_half = trailing_edge_thickness_mm / 2.0
    internal["te_profile_angle_deg"] = 90.0
    internal["te_profile_start_length_mm"] = -te_half
    internal["te_profile_end_length_mm"] = te_half

    # TRAILING EDGE UPR/LWR
    internal["te_upr_control_angle_deg"] = te_upr_angle_deg
    internal["te_upr_control_start_length_mm"] = 0.0
    internal["te_upr_control_end_length_mm"] = -16.0

    internal["te_lwr_control_angle_deg"] = te_lwr_angle_deg
    internal["te_lwr_control_start_length_mm"] = 0.0
    internal["te_lwr_control_end_length_mm"] = -16.0

    return internal


# =========================================================
# FUNCIONES DE CONSTRUCCIÓN CATIA
# =========================================================
def create_control_plane(part, target_set):
    hybrid_shape_factory = part.HybridShapeFactory

    origin_elements = part.OriginElements
    zx_plane = origin_elements.PlaneZX
    zx_ref = part.CreateReferenceFromObject(zx_plane)

    plane = hybrid_shape_factory.AddNewPlaneOffset(zx_ref, 0.0, False)
    plane.Name = "PLANE CONTROL"

    return append_and_update(part, target_set, plane)


def create_point_on_plane(part, target_set, plane, point_name, x_mm, y_mm):
    hybrid_shape_factory = part.HybridShapeFactory
    plane_ref = part.CreateReferenceFromObject(plane)

    point = hybrid_shape_factory.AddNewPointOnPlane(plane_ref, x_mm, y_mm)
    point.Name = point_name

    return append_and_update(part, target_set, point)


def create_line_between_points(part, target_set, plane, line_name, x1, y1, x2, y2):
    hybrid_shape_factory = part.HybridShapeFactory
    plane_ref = part.CreateReferenceFromObject(plane)

    point_1 = hybrid_shape_factory.AddNewPointOnPlane(plane_ref, x1, y1)
    point_1.Name = line_name + "_START"
    target_set.AppendHybridShape(point_1)

    point_2 = hybrid_shape_factory.AddNewPointOnPlane(plane_ref, x2, y2)
    point_2.Name = line_name + "_END"
    target_set.AppendHybridShape(point_2)

    ref_1 = part.CreateReferenceFromObject(point_1)
    ref_2 = part.CreateReferenceFromObject(point_2)

    line = hybrid_shape_factory.AddNewLinePtPt(ref_1, ref_2)
    line.Name = line_name

    return append_and_update(part, target_set, line)


def create_chord_line(part, target_set, search_sets, line_name, angle_deg, start_length_mm, end_length_mm):
    hybrid_shape_factory = part.HybridShapeFactory

    x_axis = get_shape(search_sets, "X Axis")
    reference1 = part.CreateReferenceFromObject(x_axis)

    plane = get_shape(search_sets, "PLANE CONTROL")
    reference2 = part.CreateReferenceFromObject(plane)

    le_point = get_shape(search_sets, "LE POINT")
    reference3 = part.CreateReferenceFromObject(le_point)

    line = hybrid_shape_factory.AddNewLineAngle(
        reference1,
        reference2,
        reference3,
        False,
        start_length_mm,
        end_length_mm,
        angle_deg,
        False
    )

    line.Name = line_name
    return append_and_update(part, target_set, line)


def create_te_point_from_extremum(part, target_set, search_sets, point_name, extremum_mode=0):
    hybrid_shape_factory = part.HybridShapeFactory

    chord = get_shape(search_sets, "CHORD")
    chord_ref = part.CreateReferenceFromObject(chord)

    x_axis = get_shape(search_sets, "X Axis")
    x_axis_ref = part.CreateReferenceFromObject(x_axis)

    direction = hybrid_shape_factory.AddNewDirection(x_axis_ref)
    extremum = hybrid_shape_factory.AddNewExtremum(chord_ref, direction, extremum_mode)
    extremum.Name = point_name

    return append_and_update(part, target_set, extremum)


def create_le_control_line(part, target_set, search_sets, angle_deg, start_length_mm, end_length_mm):
    hybrid_shape_factory = part.HybridShapeFactory

    chord = get_shape(search_sets, "CHORD")
    reference1 = part.CreateReferenceFromObject(chord)

    plane = get_shape(search_sets, "PLANE CONTROL")
    reference2 = part.CreateReferenceFromObject(plane)

    le_point = get_shape(search_sets, "LE POINT")
    reference3 = part.CreateReferenceFromObject(le_point)

    line = hybrid_shape_factory.AddNewLineAngle(
        reference1,
        reference2,
        reference3,
        False,
        start_length_mm,
        end_length_mm,
        angle_deg,
        False
    )

    line.Name = "LE CONTROL LINE"
    return append_and_update(part, target_set, line)


def create_te_control_line(part, target_set, search_sets, angle_deg, start_length_mm, end_length_mm):
    hybrid_shape_factory = part.HybridShapeFactory

    chord = get_shape(search_sets, "CHORD")
    reference1 = part.CreateReferenceFromObject(chord)

    plane = get_shape(search_sets, "PLANE CONTROL")
    reference2 = part.CreateReferenceFromObject(plane)

    te_point = get_shape(search_sets, "TE POINT")
    reference3 = part.CreateReferenceFromObject(te_point)

    line = hybrid_shape_factory.AddNewLineAngle(
        reference1,
        reference2,
        reference3,
        False,
        start_length_mm,
        end_length_mm,
        angle_deg,
        False
    )

    line.Name = "TE CONTROL LINE"
    return append_and_update(part, target_set, line)


def create_camberline(part, target_set, search_sets):
    hybrid_shape_factory = part.HybridShapeFactory

    spline = hybrid_shape_factory.AddNewSpline()
    spline.SetSplineType(0)
    spline.SetClosing(0)

    le_point = get_shape(search_sets, "LE POINT")
    le_point_ref = part.CreateReferenceFromObject(le_point)

    le_control_line = get_shape(search_sets, "LE CONTROL LINE")
    le_control_line_ref = part.CreateReferenceFromObject(le_control_line)

    spline.AddPointWithConstraintFromCurve(
        le_point_ref,
        le_control_line_ref,
        1.0,
        -1,
        1
    )

    te_point = get_shape(search_sets, "TE POINT")
    te_point_ref = part.CreateReferenceFromObject(te_point)

    te_control_line = get_shape(search_sets, "TE CONTROL LINE")
    te_control_line_ref = part.CreateReferenceFromObject(te_control_line)

    spline.AddPointWithConstraintFromCurve(
        te_point_ref,
        te_control_line_ref,
        1.0,
        1,
        1
    )

    spline.Name = "CAMBERLINE"
    return append_and_update(part, target_set, spline)


def create_point_on_curve_ratio(part, target_set, search_sets, point_name, curve_name, ratio):
    hybrid_shape_factory = part.HybridShapeFactory

    curve = get_shape(search_sets, curve_name)
    curve_ref = part.CreateReferenceFromObject(curve)

    point = hybrid_shape_factory.AddNewPointOnCurveFromPercent(curve_ref, ratio, False)
    point.Name = point_name

    return append_and_update(part, target_set, point)


def create_le_circle(part, target_set, search_sets):
    hybrid_shape_factory = part.HybridShapeFactory

    point_a = get_shape(search_sets, "POINT A")
    center_ref = part.CreateReferenceFromObject(point_a)

    le_point = get_shape(search_sets, "LE POINT")
    point_ref = part.CreateReferenceFromObject(le_point)

    plane = get_shape(search_sets, "PLANE CONTROL")
    plane_ref = part.CreateReferenceFromObject(plane)

    circle = hybrid_shape_factory.AddNewCircleCtrPtWithAngles(
        center_ref,
        point_ref,
        plane_ref,
        False,
        0.0,
        360.0
    )

    circle.SetLimitation(0)
    circle.Name = "LE CIRCLE"

    return append_and_update(part, target_set, circle)


def create_normal_at_point_a(part, target_set, search_sets, angle_deg, start_length_mm, end_length_mm):
    hybrid_shape_factory = part.HybridShapeFactory

    camberline = get_shape(search_sets, "CAMBERLINE")
    curve_ref = part.CreateReferenceFromObject(camberline)

    plane = get_shape(search_sets, "PLANE CONTROL")
    plane_ref = part.CreateReferenceFromObject(plane)

    point_a = get_shape(search_sets, "POINT A")
    point_ref = part.CreateReferenceFromObject(point_a)

    line = hybrid_shape_factory.AddNewLineAngle(
        curve_ref,
        plane_ref,
        point_ref,
        False,
        start_length_mm,
        end_length_mm,
        angle_deg,
        False
    )

    line.Name = "NORMAL POINT A"
    return append_and_update(part, target_set, line)


def create_intersection_point(part, target_set, search_sets, point_name, element1_name, element2_name):
    hybrid_shape_factory = part.HybridShapeFactory

    element1 = get_shape(search_sets, element1_name)
    ref1 = part.CreateReferenceFromObject(element1)

    element2 = get_shape(search_sets, element2_name)
    ref2 = part.CreateReferenceFromObject(element2)

    intersection = hybrid_shape_factory.AddNewIntersection(ref1, ref2)
    intersection.Name = point_name

    return append_and_update(part, target_set, intersection)


def create_opposite_normal_at_point_a(part, target_set, search_sets, angle_deg, start_length_mm, end_length_mm):
    hybrid_shape_factory = part.HybridShapeFactory

    camberline = get_shape(search_sets, "CAMBERLINE")
    curve_ref = part.CreateReferenceFromObject(camberline)

    plane = get_shape(search_sets, "PLANE CONTROL")
    plane_ref = part.CreateReferenceFromObject(plane)

    point_a = get_shape(search_sets, "POINT A")
    point_ref = part.CreateReferenceFromObject(point_a)

    line = hybrid_shape_factory.AddNewLineAngle(
        curve_ref,
        plane_ref,
        point_ref,
        False,
        start_length_mm,
        end_length_mm,
        angle_deg,
        False
    )

    line.Name = "OPPOSITE NORMAL POINT A"
    return append_and_update(part, target_set, line)


def create_te_profile(part, target_set, search_sets, angle_deg, start_length_mm, end_length_mm):
    hybrid_shape_factory = part.HybridShapeFactory

    camberline = get_shape(search_sets, "CAMBERLINE")
    curve_ref = part.CreateReferenceFromObject(camberline)

    plane = get_shape(search_sets, "PLANE CONTROL")
    plane_ref = part.CreateReferenceFromObject(plane)

    te_point = get_shape(search_sets, "TE POINT")
    point_ref = part.CreateReferenceFromObject(te_point)

    line = hybrid_shape_factory.AddNewLineAngle(
        curve_ref,
        plane_ref,
        point_ref,
        False,
        start_length_mm,
        end_length_mm,
        angle_deg,
        False
    )

    line.Name = "TE PROFILE"
    return append_and_update(part, target_set, line)


def create_te_upr_pt(part, target_set, search_sets):
    hybrid_shape_factory = part.HybridShapeFactory

    te_profile = get_shape(search_sets, "TE PROFILE")
    curve_ref = part.CreateReferenceFromObject(te_profile)

    point = hybrid_shape_factory.AddNewPointOnCurveFromPercent(curve_ref, 0.0, False)
    point.Name = "TE UPR PT"

    return append_and_update(part, target_set, point)


def create_te_lwr_pt(part, target_set, search_sets):
    hybrid_shape_factory = part.HybridShapeFactory

    te_profile = get_shape(search_sets, "TE PROFILE")
    curve_ref = part.CreateReferenceFromObject(te_profile)

    point = hybrid_shape_factory.AddNewPointOnCurveFromPercent(curve_ref, 1.0, False)
    point.Name = "TE LWR PT"

    return append_and_update(part, target_set, point)


def create_te_upr_control_line(part, target_set, search_sets, angle_deg, start_length_mm, end_length_mm):
    hybrid_shape_factory = part.HybridShapeFactory

    te_control_line = get_shape(search_sets, "TE CONTROL LINE")
    curve_ref = part.CreateReferenceFromObject(te_control_line)

    plane = get_shape(search_sets, "PLANE CONTROL")
    plane_ref = part.CreateReferenceFromObject(plane)

    te_upr_pt = get_shape(search_sets, "TE UPR PT")
    point_ref = part.CreateReferenceFromObject(te_upr_pt)

    line = hybrid_shape_factory.AddNewLineAngle(
        curve_ref,
        plane_ref,
        point_ref,
        False,
        start_length_mm,
        end_length_mm,
        angle_deg,
        False
    )

    line.Name = "TE UPR CONTROL LINE"
    return append_and_update(part, target_set, line)


def create_te_lwr_control_line(part, target_set, search_sets, angle_deg, start_length_mm, end_length_mm):
    hybrid_shape_factory = part.HybridShapeFactory

    te_control_line = get_shape(search_sets, "TE CONTROL LINE")
    curve_ref = part.CreateReferenceFromObject(te_control_line)

    plane = get_shape(search_sets, "PLANE CONTROL")
    plane_ref = part.CreateReferenceFromObject(plane)

    te_lwr_pt = get_shape(search_sets, "TE LWR PT")
    point_ref = part.CreateReferenceFromObject(te_lwr_pt)

    line = hybrid_shape_factory.AddNewLineAngle(
        curve_ref,
        plane_ref,
        point_ref,
        False,
        start_length_mm,
        end_length_mm,
        angle_deg,
        False
    )

    line.Name = "TE LWR CONTROL LINE"
    return append_and_update(part, target_set, line)


def create_tangent_line_on_support(
    part,
    target_set,
    search_sets,
    line_name,
    curve_name,
    point_name,
    support_name,
    start_length_mm,
    end_length_mm
):
    hybrid_shape_factory = part.HybridShapeFactory

    curve = get_shape(search_sets, curve_name)
    reference1 = part.CreateReferenceFromObject(curve)

    point = get_shape(search_sets, point_name)
    reference2 = part.CreateReferenceFromObject(point)

    support = get_shape(search_sets, support_name)
    reference3 = part.CreateReferenceFromObject(support)

    line = hybrid_shape_factory.AddNewLineTangencyOnSupport(
        reference1,
        reference2,
        reference3,
        start_length_mm,
        end_length_mm,
        False
    )

    line.Name = line_name
    return append_and_update(part, target_set, line)


def create_upper_profile(part, target_set, search_sets):
    hybrid_shape_factory = part.HybridShapeFactory

    spline = hybrid_shape_factory.AddNewSpline()
    spline.SetSplineType(0)
    spline.SetClosing(0)

    point_b = get_shape(search_sets, "POINT B")
    point_b_ref = part.CreateReferenceFromObject(point_b)

    le_upr_control_line = get_shape(search_sets, "LE UPR CONTROL LINE")
    le_upr_control_line_ref = part.CreateReferenceFromObject(le_upr_control_line)

    spline.AddPointWithConstraintFromCurve(
        point_b_ref,
        le_upr_control_line_ref,
        1.0,
        1,
        1
    )

    te_upr_pt = get_shape(search_sets, "TE UPR PT")
    te_upr_pt_ref = part.CreateReferenceFromObject(te_upr_pt)

    te_upr_control_line = get_shape(search_sets, "TE UPR CONTROL LINE")
    te_upr_control_line_ref = part.CreateReferenceFromObject(te_upr_control_line)

    spline.AddPointWithConstraintFromCurve(
        te_upr_pt_ref,
        te_upr_control_line_ref,
        1.0,
        1,
        1
    )

    spline.Name = "UPR PROFILE"
    return append_and_update(part, target_set, spline)


def create_lower_profile(part, target_set, search_sets):
    hybrid_shape_factory = part.HybridShapeFactory

    spline = hybrid_shape_factory.AddNewSpline()
    spline.SetSplineType(0)
    spline.SetClosing(0)

    point_c = get_shape(search_sets, "POINT C")
    point_c_ref = part.CreateReferenceFromObject(point_c)

    le_lwr_control_line = get_shape(search_sets, "LE LWR CONTROL LINE")
    le_lwr_control_line_ref = part.CreateReferenceFromObject(le_lwr_control_line)

    spline.AddPointWithConstraintFromCurve(
        point_c_ref,
        le_lwr_control_line_ref,
        1.0,
        -1,
        1
    )

    te_lwr_pt = get_shape(search_sets, "TE LWR PT")
    te_lwr_pt_ref = part.CreateReferenceFromObject(te_lwr_pt)

    te_lwr_control_line = get_shape(search_sets, "TE LWR CONTROL LINE")
    te_lwr_control_line_ref = part.CreateReferenceFromObject(te_lwr_control_line)

    spline.AddPointWithConstraintFromCurve(
        te_lwr_pt_ref,
        te_lwr_control_line_ref,
        1.0,
        1,
        1
    )

    spline.Name = "LWR PROFILE"
    return append_and_update(part, target_set, spline)


def create_le_arc_trim(part, target_set, search_sets, trim_name="LE ARC", hide_inputs=True):
    # A pesar del nombre, este trim recorta y une UPR PROFILE, LE CIRCLE y LWR PROFILE.
    # El resultado "LE ARC" cubre prácticamente todo el contorno del perfil
    # (extradós + arco del borde de ataque + intradós), no solo el arco del LE.
    # El nombre viene de que la operación de trim tiene como elemento central el LE CIRCLE.
    hybrid_shape_factory = part.HybridShapeFactory

    trim = hybrid_shape_factory.AddNewHybridTrim(None, 1, None, 1)
    trim.Connex = True
    trim.Manifold = True
    trim.Mode = 2

    upr_profile = get_shape(search_sets, "UPR PROFILE")
    upr_ref = part.CreateReferenceFromObject(upr_profile)
    trim.SetElem(0, upr_ref)
    trim.SetPortionToKeep(1, 1)

    le_circle = get_shape(search_sets, "LE CIRCLE")
    circle_ref = part.CreateReferenceFromObject(le_circle)
    trim.SetElem(0, circle_ref)
    trim.SetPortionToKeep(2, 1)

    lwr_profile = get_shape(search_sets, "LWR PROFILE")
    lwr_ref = part.CreateReferenceFromObject(lwr_profile)
    trim.SetElem(0, lwr_ref)
    trim.SetPortionToKeep(3, 1)

    trim.Name = trim_name
    target_set.AppendHybridShape(trim)

    if hide_inputs:
        try:
            hybrid_shape_factory.GSMVisibility(upr_ref, 0)
        except Exception:
            pass
        try:
            hybrid_shape_factory.GSMVisibility(circle_ref, 0)
        except Exception:
            pass
        try:
            hybrid_shape_factory.GSMVisibility(lwr_ref, 0)
        except Exception:
            pass

    part.InWorkObject = trim
    part.Update()

    try:
        trim_ref = part.CreateReferenceFromObject(trim)
        hybrid_shape_factory.GSMVisibility(trim_ref, 1)
        part.Update()
    except Exception:
        pass

    return trim


def create_airfoil_join(part, target_set, search_sets, join_name, element_names):
    hybrid_shape_factory = part.HybridShapeFactory

    first_element = get_shape(search_sets, element_names[0])
    first_ref = part.CreateReferenceFromObject(first_element)

    second_element = get_shape(search_sets, element_names[1])
    second_ref = part.CreateReferenceFromObject(second_element)

    join = hybrid_shape_factory.AddNewJoin(first_ref, second_ref)

    for name in element_names[2:]:
        elem = get_shape(search_sets, name)
        elem_ref = part.CreateReferenceFromObject(elem)
        join.AddElement(elem_ref)

    join.SetConnex(1)
    join.SetManifold(0)
    join.SetSimplify(0)
    join.SetSuppressMode(0)
    join.SetDeviation(0.001)

    join.Name = join_name
    target_set.AppendHybridShape(join)

    part.InWorkObject = join
    part.Update()

    return join


def hide_geometrical_set(part, geo_set):
    hybrid_shape_factory = part.HybridShapeFactory

    hybrid_shapes = geo_set.HybridShapes
    for i in range(1, hybrid_shapes.Count + 1):
        shape = hybrid_shapes.Item(i)
        try:
            ref = part.CreateReferenceFromObject(shape)
            hybrid_shape_factory.GSMVisibility(ref, 0)
        except Exception:
            pass

    hybrid_bodies = geo_set.HybridBodies
    for i in range(1, hybrid_bodies.Count + 1):
        sub_set = hybrid_bodies.Item(i)
        hide_geometrical_set(part, sub_set)


# =========================================================
# MOTOR PARAMÉTRICO INTERNO
# =========================================================
def build_airfoil(part, params, airfoil_set, construction_set, control_set):
    search_sets = [construction_set, control_set]

    te_point_extremum_mode = 0

    control_plane = create_control_plane(part, control_set)

    create_line_between_points(
        part,
        construction_set,
        control_plane,
        "X Axis",
        0.0,
        0.0,
        100.0,
        0.0
    )

    create_point_on_plane(
        part,
        control_set,
        control_plane,
        "LE POINT",
        params["le_point_x_mm"],
        params["le_point_y_mm"]
    )

    create_chord_line(
        part,
        control_set,
        search_sets,
        "CHORD",
        params["chord_angle_deg"],
        params["chord_start_length_mm"],
        params["chord_end_length_mm"]
    )

    create_te_point_from_extremum(
        part,
        construction_set,
        search_sets,
        "TE POINT",
        te_point_extremum_mode
    )

    create_le_control_line(
        part,
        control_set,
        search_sets,
        params["le_control_angle_deg"],
        params["le_control_start_length_mm"],
        params["le_control_end_length_mm"]
    )

    create_te_control_line(
        part,
        control_set,
        search_sets,
        params["te_control_angle_deg"],
        params["te_control_start_length_mm"],
        params["te_control_end_length_mm"]
    )

    create_camberline(part, construction_set, search_sets)

    create_point_on_curve_ratio(
        part,
        control_set,
        search_sets,
        "POINT A",
        "CAMBERLINE",
        params["point_a_ratio"]
    )

    create_le_circle(part, construction_set, search_sets)

    create_normal_at_point_a(
        part,
        construction_set,
        search_sets,
        params["normal_point_a_angle_deg"],
        params["normal_point_a_start_length_mm"],
        params["normal_point_a_end_length_mm"]
    )

    create_intersection_point(
        part,
        construction_set,
        search_sets,
        "POINT B",
        "NORMAL POINT A",
        "LE CIRCLE"
    )

    create_opposite_normal_at_point_a(
        part,
        construction_set,
        search_sets,
        params["opposite_normal_point_a_angle_deg"],
        params["opposite_normal_point_a_start_length_mm"],
        params["opposite_normal_point_a_end_length_mm"]
    )

    create_intersection_point(
        part,
        construction_set,
        search_sets,
        "POINT C",
        "OPPOSITE NORMAL POINT A",
        "LE CIRCLE"
    )

    create_te_profile(
        part,
        control_set,
        search_sets,
        params["te_profile_angle_deg"],
        params["te_profile_start_length_mm"],
        params["te_profile_end_length_mm"]
    )

    create_te_upr_pt(part, construction_set, search_sets)
    create_te_lwr_pt(part, construction_set, search_sets)

    create_te_upr_control_line(
        part,
        control_set,
        search_sets,
        params["te_upr_control_angle_deg"],
        params["te_upr_control_start_length_mm"],
        params["te_upr_control_end_length_mm"]
    )

    create_te_lwr_control_line(
        part,
        control_set,
        search_sets,
        params["te_lwr_control_angle_deg"],
        params["te_lwr_control_start_length_mm"],
        params["te_lwr_control_end_length_mm"]
    )

    create_tangent_line_on_support(
        part,
        construction_set,
        search_sets,
        "LE UPR CONTROL LINE",
        "LE CIRCLE",
        "POINT B",
        "PLANE CONTROL",
        params["le_upr_control_start_length_mm"],
        params["le_upr_control_end_length_mm"]
    )

    create_tangent_line_on_support(
        part,
        construction_set,
        search_sets,
        "LE LWR CONTROL LINE",
        "LE CIRCLE",
        "POINT C",
        "PLANE CONTROL",
        params["le_lwr_control_start_length_mm"],
        params["le_lwr_control_end_length_mm"]
    )

    create_upper_profile(part, construction_set, search_sets)
    create_lower_profile(part, construction_set, search_sets)

    create_le_arc_trim(
        part,
        construction_set,
        search_sets,
        "LE ARC",
        hide_inputs=True
    )

    create_airfoil_join(
        part,
        airfoil_set,
        search_sets,
        "AIRFOIL",
        ["UPR PROFILE", "LE ARC", "LWR PROFILE", "TE PROFILE"]
    )

    hide_geometrical_set(part, construction_set)
    hide_geometrical_set(part, control_set)

    part.Update()


# =========================================================
# MAIN INTERNO
# =========================================================
def main(internal_params=None) -> dict:
    pythoncom.CoInitialize()

    try:
        params = merge_params(internal_params)
        errors = validate_params(params)

        if errors:
            print("[ERROR] Error de validación interna:")
            for err in errors:
                print(f"   - {err}")
            return {"status": "error", "stage": "validation", "errors": errors}

        print("[INFO] Parámetros internos usados:")
        for key, value in params.items():
            print(f"   {key} = {value}")

        catia = win32com.client.Dispatch("CATIA.Application")
        catia.Visible = True

        documents = catia.Documents
        part_doc = documents.Add("Part")
        part = part_doc.Part

        axis_systems = part.AxisSystems
        axis_system = axis_systems.Add()
        axis_system.Name = "Axis System.1"

        hybrid_bodies = part.HybridBodies

        airfoil_set = hybrid_bodies.Add()
        airfoil_set.Name = "AIRFOIL"

        construction_set = airfoil_set.HybridBodies.Add()
        construction_set.Name = "AIRFOIL CONSTRUCTION"

        control_set = airfoil_set.HybridBodies.Add()
        control_set.Name = "CONTROLS"

        build_airfoil(part, params, airfoil_set, construction_set, control_set)

        print("[OK] Perfil AIRFOIL creado correctamente")
        return {"status": "ok", "params_used": params}

    except Exception as e:
        print("[ERROR] Error:", e)
        traceback.print_exc()
        return {"status": "error", "stage": "catia", "message": str(e)}

    finally:
        pythoncom.CoUninitialize()


# =========================================================
# MAIN DE USUARIO
# =========================================================
def main_user(user_params=None) -> dict:
    user_errors = validate_user_params(user_params or {})
    if user_errors:
        print("[ERROR] Error de validación de usuario:")
        for err in user_errors:
            print(f"   - {err}")
        return {"status": "error", "stage": "user_validation", "errors": user_errors}

    merged_user = USER_DEFAULTS.copy()
    if user_params:
        merged_user.update(user_params)

    print("[INFO] Parámetros de usuario:")
    for key, value in merged_user.items():
        print(f"   {key} = {value}")

    internal_params = translate_user_to_internal(merged_user)

    print("\n[MAP] Traducción a parámetros internos:")
    for key, value in internal_params.items():
        print(f"   {key} = {value}")

    return main(internal_params)


# =========================================================
# PUNTO DE ENTRADA PARA n8n / LLM
# =========================================================
def run_from_json(json_string: str) -> dict:
    print(f"[JSON] JSON recibido: {json_string}")

    try:
        user_params = json.loads(json_string)
    except json.JSONDecodeError as e:
        msg = f"JSON inválido: {e}"
        print(f"[ERROR] {msg}")
        return {"status": "error", "stage": "json_parse", "message": msg}

    if not isinstance(user_params, dict):
        msg = "El JSON debe ser un objeto con los parámetros de usuario"
        print(f"[ERROR] {msg}")
        return {"status": "error", "stage": "json_parse", "message": msg}

    known_keys = set(USER_DEFAULTS.keys())
    unknown = set(user_params.keys()) - known_keys
    warnings = []
    if unknown:
        msg = f"Claves ignoradas (no reconocidas): {sorted(unknown)}"
        print(f"[WARN] {msg}")
        warnings.append(msg)
        user_params = {k: v for k, v in user_params.items() if k in known_keys}

    result = main_user(user_params)
    if warnings:
        result["warnings"] = warnings
    return result


if __name__ == "__main__":
    if len(sys.argv) > 1:
        result = run_from_json(sys.argv[1])
        print(json.dumps(result, default=str))
        sys.exit(0 if result.get("status") == "ok" else 1)
    else:
        result = main_user({
            "chord_length_mm": 200.0,
            "chord_angle_deg": 350.0,
            "leading_edge_angle_deg": 3.5,
            "leading_edge_thickness_level": 0.5,
            "trailing_edge_angle_deg": 168.0,
            "trailing_edge_thickness_mm": 0.5,
            "te_upr_angle_deg": 10.0,
            "te_lwr_angle_deg": -2.0,
        })
        print(json.dumps(result, default=str))