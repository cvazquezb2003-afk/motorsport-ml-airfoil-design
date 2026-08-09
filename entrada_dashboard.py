"""
PARTE 1 del dashboard (conversacion guiada): TRES PUERTAS al MISMO dato — el rango
(o valor) de ANGULO de trabajo objetivo, que alimenta el resto del flujo
(cuerda -> objetivo -> disenar -> resultados).

Primera pregunta: "How do you want to set the downforce level?"
  A "By circuit"         -> selector de circuitos (circuitos.csv) -> categoria + rango
  B "By downforce level" -> Low (0-5) / Medium (5-9) / High (9-14) directo
  C "By exact angle"     -> |alpha| objetivo numerico (0-14), usuario experto

Las tres desembocan en el MISMO objeto `ObjetivoAngulo`. Por dentro es la misma
logica; solo cambia la forma de preguntar. NO se anaden mas puertas: el objetivo es
llegar rapido al primer resultado, no un formulario largo.

Encuadre HONESTO integrado: toda salida trae `framing` dejando claro que es una guia
derivada de la fisica, no un setup real (que no es publico).

Reutilizable para Flask:
    from entrada_dashboard import primera_pregunta, resolver
    q = primera_pregunta()                       # -> dict para pintar la pregunta
    obj = resolver("circuit", "Monza")           # -> ObjetivoAngulo
    obj = resolver("level", "high")
    obj = resolver("angle", 7)
"""
from dataclasses import dataclass, asdict
import circuitos as C

# Rango de |alpha| por categoria (coherente con el barrido 0..14 de los datos)
RANGO = {"low": (0, 5), "medium": (5, 9), "high": (9, 14)}
ETIQUETA = {"low": "low downforce", "medium": "medium downforce", "high": "high downforce"}
PRIORIDAD = {"low": "low drag", "medium": "downforce–drag balance", "high": "maximum downforce"}
ANGULO_MIN, ANGULO_MAX = 0, 14

# --- PASO 2: cuerda + prioridad ---
CUERDA_MIN, CUERDA_MAX = 150, 500          # rango SOPORTADO por el sistema
CUERDA_RAPIDAS = [250, 300, 450]           # opciones rapidas

# --- PASO 2b: velocidad (feature C5) ---
# Rango SOPORTADO 95-330 km/h. El dataset solo evaluo 110/180/290, pero el eje Reynolds
# queda cubierto de forma CONTINUA porque la cuerda barre 150-500 mm: con tolerancia de
# +-15% en cuerda, la ventana sin extrapolar es [110/1.15, 290*1.15] = [96, 334] km/h
# para CUALQUIER cuerda (Re es lineal en cuerda y en velocidad). De ahi 95-330.
# Fuera de ahi se RECHAZA; dentro, los avisos blandos viven en guardas_velocidad.py.
VELOCIDAD_MIN, VELOCIDAD_MAX = 95, 330
VELOCIDAD_DEFAULT = 180                    # las 3 evaluadas: 110 / 180 / 290
VELOCIDAD_RAPIDAS = [110, 180, 290]        # opciones rapidas = las realmente medidas
PRIORIDADES = {
    "efficiency": {"label": "Max efficiency (L/D)", "short": "max efficiency"},
    "drag":       {"label": "Min drag (CD)",        "short": "min drag"},
}


@dataclass
class ObjetivoAngulo:
    """Resultado unico de la Parte 1. Alimenta el resto del flujo."""
    modo: str                 # "circuit" | "level" | "angle"
    categoria: str            # "low" | "medium" | "high"
    alpha_lo: float
    alpha_hi: float
    es_rango: bool            # False solo en la puerta C (angulo exacto)
    alpha_exact: float | None # valor exacto (puerta C), si aplica
    target_str: str           # p.ej. "|α| 5–9°"  o  "|α| = 7°"
    prioridad: str            # low drag / balance / maximum downforce
    circuito: str | None      # nombre del circuito (solo puerta A)
    framing: str              # encuadre honesto para la UI
    equivalencia: str | None = None   # "el circuito solo fija el nivel" (puerta A)

    def dict(self):
        return asdict(self)


def primera_pregunta():
    """Estructura de la primera pregunta para la UI (las TRES puertas)."""
    return {
        "pregunta": "How do you want to set the downforce level?",
        "opciones": [
            {"id": "circuit", "label": "By circuit",
             "desc": "Pick a track; we translate it to a working-angle range.",
             "input": "select", "fuente": "circuitos.csv"},
            {"id": "level", "label": "By downforce level",
             "desc": "Low (|α| 0–5°) · Medium (5–9°) · High (9–14°).",
             "input": "buttons", "valores": ["low", "medium", "high"]},
            {"id": "angle", "label": "By exact angle",
             "desc": f"Enter a target |α| directly ({ANGULO_MIN}–{ANGULO_MAX}°).",
             "input": "number", "min": ANGULO_MIN, "max": ANGULO_MAX},
        ],
    }


def _clasifica_angulo(a):
    """|alpha| exacto -> categoria (para el encuadre; el valor exacto se respeta)."""
    if a <= 5:
        return "low"
    if a <= 9:
        return "medium"
    return "high"


def por_circuito(nombre):
    """PUERTA A: circuito -> categoria + rango + mensaje orientativo (de circuitos.py)."""
    nom, cat, (lo, hi), _ = C.rango_angulo(nombre)
    return ObjetivoAngulo(
        modo="circuit", categoria=cat, alpha_lo=lo, alpha_hi=hi, es_rango=True,
        alpha_exact=None, target_str=f"|α| {lo}–{hi}°", prioridad=PRIORIDAD[cat],
        circuito=nom, framing=_framing_rango(cat, lo, hi, circuito=nom),
        # honestidad: el circuito es un ATAJO, no un calculo especifico del trazado
        equivalencia=(f"{nom} → {ETIQUETA[cat]} (|α| {lo}–{hi}°). The circuit only sets "
                      f"the downforce level — picking “{cat} downforce” directly gives "
                      f"exactly the same result."))


def por_nivel(nivel):
    """PUERTA B: nivel low/medium/high directo, sin circuito."""
    nivel = str(nivel).strip().lower()
    if nivel not in RANGO:
        raise ValueError(f"Nivel invalido: {nivel!r}. Usa low / medium / high.")
    lo, hi = RANGO[nivel]
    return ObjetivoAngulo(
        modo="level", categoria=nivel, alpha_lo=lo, alpha_hi=hi, es_rango=True,
        alpha_exact=None, target_str=f"|α| {lo}–{hi}°", prioridad=PRIORIDAD[nivel],
        circuito=None, framing=_framing_rango(nivel, lo, hi))


def por_angulo(alpha):
    """PUERTA C: |alpha| objetivo exacto (0-14). Usuario experto."""
    try:
        a = float(alpha)
    except (TypeError, ValueError):
        raise ValueError(f"Angulo no numerico: {alpha!r}")
    if not (ANGULO_MIN <= a <= ANGULO_MAX):
        raise ValueError(f"|α| fuera de rango: {a}. Debe estar entre "
                         f"{ANGULO_MIN} y {ANGULO_MAX}°.")
    cat = _clasifica_angulo(a)
    return ObjetivoAngulo(
        modo="angle", categoria=cat, alpha_lo=a, alpha_hi=a, es_rango=False,
        alpha_exact=a, target_str=f"|α| = {a:g}°", prioridad=PRIORIDAD[cat],
        circuito=None, framing=_framing_exacto(a, cat))


def valida_cuerda(valor):
    """PASO 2a: valida la cuerda dentro del rango soportado (150-500 mm)."""
    try:
        c = float(valor)
    except (TypeError, ValueError):
        raise ValueError(f"Chord is not a number: {valor!r}")
    if not (CUERDA_MIN <= c <= CUERDA_MAX):
        raise ValueError(f"Chord out of supported range: {c:g} mm. Must be between "
                         f"{CUERDA_MIN} and {CUERDA_MAX} mm (system's reliable range).")
    return c


def valida_velocidad(valor=None):
    """PASO 2b: valida la velocidad dentro del rango soportado (95-330 km/h).
    None / vacio -> VELOCIDAD_DEFAULT (180), para que el flujo siga siendo el de antes
    si el usuario no toca el campo. Unico RECHAZO DURO de la feature: los tres avisos
    de dominio (zona interpolada, angulo sin datos, esquina de Reynolds) no bloquean y
    viven en guardas_velocidad.py."""
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        return float(VELOCIDAD_DEFAULT)
    try:
        v = float(valor)
    except (TypeError, ValueError):
        raise ValueError(f"Speed is not a number: {valor!r}")
    if not (VELOCIDAD_MIN <= v <= VELOCIDAD_MAX):
        raise ValueError(f"Speed out of supported range: {v:g} km/h. Must be between "
                         f"{VELOCIDAD_MIN} and {VELOCIDAD_MAX} km/h — the system's "
                         "reliable range.")
    return v


def valida_prioridad(valor):
    """PASO 2b: valida la prioridad (efficiency / drag)."""
    p = str(valor).strip().lower()
    if p not in PRIORIDADES:
        raise ValueError(f"Invalid priority: {valor!r}. Use efficiency / drag.")
    return p


def _resumen(obj, cuerda, velocidad=None):
    """Frase de resumen para la UI: 'Designing for: ... · chord ... mm · ... km/h'.

    La velocidad entra en el resumen porque desde la feature C5 es parte del DISEÑO,
    no del contexto: define el angulo recomendado y todos los KPIs. Dos disenos con
    el mismo circuito y la misma cuerda pero distinta velocidad son disenos distintos,
    asi que el resumen (que ademas es el nombre por defecto al guardar) debe separarlos.
    """
    if obj.modo == "circuit":
        que = f"{obj.circuito} ({obj.categoria} downforce, {obj.target_str})"
    elif obj.modo == "level":
        que = f"{obj.categoria} downforce ({obj.target_str})"
    else:  # angle
        que = f"{obj.target_str} ({obj.categoria} downforce)"
    txt = f"Designing for: {que} · chord {cuerda:g} mm"
    if velocidad is not None:
        txt += f" · {float(velocidad):g} km/h"
    return txt


def construir_diseno(obj, cuerda, velocidad=None):
    """Ensambla el objetivo: PARTE 1 (angulo) + cuerda + velocidad. Resumen para la UI.
    (La prioridad se retiro del flujo; la inversa optimiza eficiencia por defecto.)"""
    c = valida_cuerda(cuerda)
    v = valida_velocidad(velocidad)
    return {
        "objetivo_angulo": obj.dict(),
        "cuerda_mm": c,
        "velocidad_kmh": v,
        "summary": _resumen(obj, c, v),
    }


def resolver(modo, valor):
    """Despacho unico de las tres puertas -> ObjetivoAngulo."""
    modo = str(modo).strip().lower()
    if modo == "circuit":
        return por_circuito(valor)
    if modo == "level":
        return por_nivel(valor)
    if modo == "angle":
        return por_angulo(valor)
    raise ValueError(f"Modo desconocido: {modo!r}. Usa circuit / level / angle.")


# ---- encuadre honesto (mismo mensaje base para las tres puertas) ----
_COLA = ("This is a guide derived from the circuit/aerodynamics type; the real "
         "angle depends on the full car, the regulations and the conditions, which "
         "go beyond the isolated profile.")


def _framing_rango(cat, lo, hi, circuito=None):
    if circuito:
        inicio = f"At {circuito} ({ETIQUETA[cat]}) you'd work around"
    else:
        inicio = f"A {ETIQUETA[cat]} setup works around"
    return (f"{inicio} |α| ≈ {lo}–{hi}°, prioritising {PRIORIDAD[cat]}. {_COLA}")


def _framing_exacto(a, cat):
    return (f"Targeting |α| = {a:g}° directly ({ETIQUETA[cat]} region), prioritising "
            f"{PRIORIDAD[cat]}. {_COLA}")


if __name__ == "__main__":
    import sys, json
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    print("PRIMERA PREGUNTA:")
    print(json.dumps(primera_pregunta(), indent=2, ensure_ascii=False))
    print("\nLAS TRES PUERTAS -> mismo tipo de resultado:\n")
    for modo, val in [("circuit", "Monza"), ("circuit", "Mónaco"),
                      ("level", "medium"), ("angle", 7), ("angle", 11.5)]:
        o = resolver(modo, val)
        print(f"[{modo:8s} {str(val):8s}] cat={o.categoria:6s} target={o.target_str:9s} "
              f"prio={o.prioridad}")
        print(f"    {o.framing}\n")
    # validaciones
    for bad in [("angle", 20), ("level", "extreme")]:
        try:
            resolver(*bad)
        except (ValueError, KeyError) as e:
            print(f"[validacion] resolver{bad} -> {e}")
