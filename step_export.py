"""
ESCRITOR DE STEP (ISO 10303-21) EN PYTHON PURO — sin OpenCASCADE.

Emite un AP214 con la curva CERRADA del contorno del perfil, en mm reales y en el
plano XY (z=0). No hay ninguna dependencia nueva: el ajuste de la B-spline usa
scipy.interpolate, que ya estaba en el proyecto.

POR QUE UNA COMPOSITE_CURVE DE DOS TRAMOS Y NO UNA SOLA SPLINE CERRADA
---------------------------------------------------------------------
El contorno NO es una curva suave cerrada: es una curva suave ABIERTA (extrados,
morro, intrados) mas una CARA PLANA en el borde de salida, porque el TE es romo
(TE-real, de espesor trailing_edge_thickness_mm). Cerrarlo con una unica spline
periodica redondearia las dos esquinas del TE, que son esquinas LEGITIMAS y
fabricables, no defectos. Por eso:

    tramo 1 : B_SPLINE_CURVE_WITH_KNOTS de grado 3 que INTERPOLA los N puntos
    tramo 2 : POLYLINE recta del ultimo punto al primero  (la cara del TE romo)
    cierre  : COMPOSITE_CURVE de los dos tramos

Asi las unicas esquinas vivas del resultado estan en el TE, que es donde deben
estar, y el resto es una spline nativa que el CAD puede extruir directamente.

ESTRUCTURA DEL FICHERO
----------------------
Wireframe conforme: GEOMETRICALLY_BOUNDED_WIREFRAME_REPRESENTATION sobre un
GEOMETRIC_CURVE_SET, colgado de la cadena PRODUCT -> PRODUCT_DEFINITION_SHAPE ->
SHAPE_DEFINITION_REPRESENTATION. Unidades declaradas en MILIMETRO explicitamente
(SI_UNIT(.MILLI.,.METRE.)): sin eso, el CAD receptor asume lo que quiere y la
escala se pierde.
"""
import datetime
import numpy as np

GRADO = 3                     # cubica: lo que espera un CAD de un perfil alar
ESQUEMA = "AUTOMOTIVE_DESIGN { 1 0 10303 214 1 1 1 1 }"     # AP214

# VERSION DEL ESCRITOR -- va en el nombre del fichero cacheado.
# SUBIRLA en cualquier cambio que altere el STEP producido (entidades, plano,
# unidades...). El cache se indexaba solo por el hash de los 7 parametros, asi
# que un fichero escrito por una version anterior seguia sirviendose como bueno:
# paso de verdad, con un CATIA importando una pieza vacia mientras el .step de
# al lado, regenerado a mano, estaba bien. Con la version en el nombre, cambiar
# el escritor invalida los ficheros viejos por si solo.
#   v1: entidad sin SHAPE (rechazada por CATIA) + plano XY
#   v2: GEOMETRICALLY_BOUNDED_WIREFRAME_SHAPE_REPRESENTATION + plano XZ
FORMATO = 2


def _r(v):
    """Real en sintaxis STEP: SIEMPRE con punto decimal (2 es invalido, 2. si)."""
    s = "%.10G" % float(v)
    if "." not in s and "E" not in s:
        s += "."
    if "E" in s and "." not in s.split("E")[0]:
        s = s.replace("E", ".E")
    return s


def _bspline_interpoladora(pts, grado=GRADO):
    """Ajusta una B-spline que PASA por todos los puntos y devuelve la forma que
    pide STEP: (grado, puntos de control, nudos unicos, multiplicidades).

    Parametrizacion por longitud de cuerda acumulada: reparte el parametro segun
    la distancia real entre puntos, que es lo que evita que la spline oscile en
    el morro (donde los puntos estan mas juntos y la curvatura es maxima)."""
    from scipy.interpolate import make_interp_spline

    d = np.sqrt(((pts[1:] - pts[:-1]) ** 2).sum(axis=1))
    u = np.concatenate([[0.0], np.cumsum(d)])
    u /= u[-1]

    spl = make_interp_spline(u, pts, k=grado)
    ctrl = np.asarray(spl.c, dtype=float)
    t = np.asarray(spl.t, dtype=float)

    # nudos repetidos -> (valor unico, multiplicidad), que es como los guarda STEP
    val, mult = [], []
    for x in t:
        if val and abs(x - val[-1]) < 1e-12:
            mult[-1] += 1
        else:
            val.append(float(x)); mult.append(1)

    # regla de cardinalidad de B_SPLINE_CURVE_WITH_KNOTS
    assert len(ctrl) == sum(mult) - grado - 1, "cardinalidad nudos/control"
    return grado, ctrl, val, mult, spl, u


def escribe_step_curva(pts_mm, destino, nombre="AIRFOIL", variante="wireframe",
                       plano="xz"):
    """Escribe el STEP de la curva cerrada del contorno.

    pts_mm : (N,2) en MM REALES, contorno ABIERTO (el primer punto NO se repite
             al final: la separacion entre el primero y el ultimo es justo el
             espesor del TE romo, y ese hueco lo cierra el tramo recto).

    variante: como se envuelve la curva en la representacion.
      "wireframe" -> GEOMETRICALLY_BOUNDED_WIREFRAME_SHAPE_REPRESENTATION,
                     que es la entidad ESTANDAR para geometria de alambre.
                     OJO con el nombre: lleva SHAPE. Sin el, la entidad no
                     existe y CATIA responde "Entity not defined in the current
                     schema" dejando la pieza VACIA.
      "shape"     -> SHAPE_REPRESENTATION a secas.
                     *** NO USAR: PROBADO Y NO FUNCIONA EN CATIA V5 ***
                     Se escribio como "reserva mas segura" razonando que es la
                     representacion mas basica de STEP. El razonamiento era justo
                     al reves: CATIA la lee SIN UN SOLO ERROR y luego IGNORA la
                     curva -> "[0556] There is Nothing to import". Un .err limpio
                     y una pieza vacia. Es peor que un fallo ruidoso, porque
                     parece que todo ha ido bien.
                     Se conserva solo como documentacion del experimento; la
                     variante valida es "wireframe" (verificada en CATIA V5R2019:
                     entra como Geometrical Set con la curva dentro).

    plano: en que plano se deposita el perfil.
      "xz" (POR DEFECTO) -> (x, 0, y): cuerda en X, espesor en Z, envergadura
                    libre en Y. Es la MISMA convencion que usa airfoil_generator
                    al construir el perfil en CATIA (plano ZX) y la que espera
                    airfoil_3d, que extruye en direccion Y. Asi el STEP aterriza
                    orientado igual que la geometria nativa del proyecto.
      "xy"        -> (x, y, 0). Se conserva por si algun flujo lo necesita.

    Devuelve un dict con lo necesario para verificar despues.
    """
    if variante not in ("wireframe", "shape"):
        raise ValueError("variante debe ser 'wireframe' o 'shape'")
    if plano not in ("xz", "xy"):
        raise ValueError("plano debe ser 'xz' o 'xy'")
    pts = np.asarray(pts_mm, dtype=float)
    if pts.ndim != 2 or pts.shape[1] != 2 or len(pts) < 8:
        raise ValueError("se esperan al menos 8 puntos (N,2) en mm")
    if np.allclose(pts[0], pts[-1]):
        raise ValueError("el contorno llega CERRADO; se espera abierto "
                         "(el ultimo punto no debe repetir el primero)")

    grado, ctrl, knots, mult, spl, u = _bspline_interpoladora(pts)

    L = []                      # lineas del bloque DATA
    n = [0]                     # contador de ids, en lista para mutar dentro

    def add(txt):
        n[0] += 1
        L.append("#%d = %s;" % (n[0], txt))
        return n[0]

    # --- contexto de aplicacion y producto ---
    ctx = add("APPLICATION_CONTEXT('automotive design')")
    add("APPLICATION_PROTOCOL_DEFINITION('international standard',"
        "'automotive_design',2010,#%d)" % ctx)
    pctx = add("MECHANICAL_CONTEXT('',#%d,'mechanical')" % ctx)
    prod = add("PRODUCT('%s','%s','',(#%d))" % (nombre, nombre, pctx))
    # sin esta categoria algunos lectores no dan de alta la pieza
    add("PRODUCT_RELATED_PRODUCT_CATEGORY('part','',(#%d))" % prod)
    pdf = add("PRODUCT_DEFINITION_FORMATION('','',#%d)" % prod)
    dctx = add("PRODUCT_DEFINITION_CONTEXT('part definition',#%d,'design')" % ctx)
    pd = add("PRODUCT_DEFINITION('design','',#%d,#%d)" % (pdf, dctx))
    pds = add("PRODUCT_DEFINITION_SHAPE('','',#%d)" % pd)

    # --- unidades: MILIMETRO explicito (sin esto se pierde la escala) ---
    u_len = add("(LENGTH_UNIT() NAMED_UNIT(*) SI_UNIT(.MILLI.,.METRE.))")
    u_ang = add("(NAMED_UNIT(*) PLANE_ANGLE_UNIT() SI_UNIT($,.RADIAN.))")
    u_sol = add("(NAMED_UNIT(*) SI_UNIT($,.STERADIAN.) SOLID_ANGLE_UNIT())")
    unc = add("UNCERTAINTY_MEASURE_WITH_UNIT(LENGTH_MEASURE(1.E-06),#%d,"
              "'distance_accuracy_value','confusion accuracy')" % u_len)
    gctx = add("(GEOMETRIC_REPRESENTATION_CONTEXT(3) "
               "GLOBAL_UNCERTAINTY_ASSIGNED_CONTEXT((#%d)) "
               "GLOBAL_UNIT_ASSIGNED_CONTEXT((#%d,#%d,#%d)) "
               "REPRESENTATION_CONTEXT('',''))" % (unc, u_len, u_ang, u_sol))

    # (u,v) del perfil -> las 3 coordenadas del plano elegido. Unico sitio donde
    # se decide el plano: todo lo demas (spline, recta del TE, ejes) va detras.
    def xyz(u, v):
        return (_r(u), "0.", _r(v)) if plano == "xz" else (_r(u), _r(v), "0.")

    # --- puntos de control de la spline ---
    ids_ctrl = [add("CARTESIAN_POINT('',(%s,%s,%s))" % xyz(x, y))
                for x, y in ctrl]

    spline = add("B_SPLINE_CURVE_WITH_KNOTS('perfil',%d,(%s),.UNSPECIFIED.,"
                 ".F.,.F.,(%s),(%s),.UNSPECIFIED.)"
                 % (grado,
                    ",".join("#%d" % i for i in ids_ctrl),
                    ",".join(str(m) for m in mult),
                    ",".join(_r(k) for k in knots)))

    # --- tramo recto: la cara del TE romo, del ultimo punto al primero ---
    p_fin = add("CARTESIAN_POINT('',(%s,%s,%s))" % xyz(pts[-1, 0], pts[-1, 1]))
    p_ini = add("CARTESIAN_POINT('',(%s,%s,%s))" % xyz(pts[0, 0], pts[0, 1]))
    recta = add("POLYLINE('borde de salida',(#%d,#%d))" % (p_fin, p_ini))

    s1 = add("COMPOSITE_CURVE_SEGMENT(.CONTINUOUS.,.T.,#%d)" % spline)
    s2 = add("COMPOSITE_CURVE_SEGMENT(.CONTINUOUS.,.T.,#%d)" % recta)
    comp = add("COMPOSITE_CURVE('contorno del perfil',(#%d,#%d),.F.)" % (s1, s2))

    # origen del sistema de coordenadas: los lectores lo esperan como primer item
    o = add("CARTESIAN_POINT('',(0.,0.,0.))")
    dz = add("DIRECTION('',(0.,0.,1.))")
    dx = add("DIRECTION('',(1.,0.,0.))")
    ejes = add("AXIS2_PLACEMENT_3D('',#%d,#%d,#%d)" % (o, dz, dx))

    # ENTIDAD SIMPLE, no compleja. El contexto (#gctx) se REFERENCIA como tercer
    # argumento; no se fusiona con la representacion. Fusionarlos produce
    # "GEOMETRIC_REPRESENTATION_CONTEXT+...+REPRESENTATION", que NO existe en el
    # esquema: CATIA lo rechaza con "Entity not defined in the current schema" y
    # la pieza sale VACIA sin que el fichero parezca roto. Ver el validador.
    if variante == "wireframe":
        cset = add("GEOMETRIC_CURVE_SET('%s',(#%d))" % (nombre, comp))
        rep = add("GEOMETRICALLY_BOUNDED_WIREFRAME_SHAPE_REPRESENTATION"
                  "('%s',(#%d,#%d),#%d)" % (nombre, ejes, cset, gctx))
    else:
        # la curva va directa como item de la representacion, sin envolverla en
        # un GEOMETRIC_CURVE_SET: menos capas, menos que pueda no soportarse
        rep = add("SHAPE_REPRESENTATION('%s',(#%d,#%d),#%d)"
                  % (nombre, ejes, comp, gctx))
    add("SHAPE_DEFINITION_REPRESENTATION(#%d,#%d)" % (pds, rep))

    ts = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    cab = [
        "ISO-10303-21;",
        "HEADER;",
        "FILE_DESCRIPTION(('airfoil contour curve, real scale mm'),'2;1');",
        "FILE_NAME('%s.step','%s',('inverted wing designer'),(''),"
        "'python pure step writer','',' ');" % (nombre.lower(), ts),
        "FILE_SCHEMA(('%s'));" % ESQUEMA,
        "ENDSEC;",
        "DATA;",
    ]
    pie = ["ENDSEC;", "END-ISO-10303-21;", ""]
    with open(destino, "w", encoding="ascii", newline="\n") as f:
        f.write("\n".join(cab + L + pie))

    # error de interpolacion, para poder afirmarlo y no suponerlo
    dev = float(np.abs(spl(u) - pts).max())
    return {"n_puntos": len(pts), "n_control": len(ctrl), "grado": grado,
            "n_entidades": n[0], "desv_max_mm": dev, "plano": plano,
            "hueco_te_mm": float(np.hypot(*(pts[0] - pts[-1])))}
