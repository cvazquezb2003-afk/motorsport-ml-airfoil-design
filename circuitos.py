"""
Base de datos de circuitos -> ANGULO de trabajo del ala (no velocidad).

CONCEPTO: el circuito orienta a QUE ANGULO trabajaria el ala. Es una capa de
INTERPRETACION sobre las polares ya existentes: dice en que zona de la curva
CL/CD/L-D mirar segun el tipo de circuito. NO cambia la inversa ni el motor.

  low downforce  (Monza)   -> |alpha| ~ 0-5   (angulos suaves, bajo downforce/drag)
  medium         (Suzuka)  -> |alpha| ~ 5-9
  high downforce (Monaco)  -> |alpha| ~ 9-14  (angulos altos, alto downforce)

⚠️ ENCUADRE HONESTO (obligatorio en cualquier UI): es una guia ORIENTATIVA derivada
de la FISICA del tipo de circuito, NO de datos de setup reales (que no son publicos).
Usar siempre `mensaje_orientativo()` al mostrarlo.
"""
import os
import csv
import unicodedata


def _fold(s):
    """Normaliza para comparar: minusculas y sin acentos (Monaco == Mónaco)."""
    s = unicodedata.normalize("NFKD", str(s).strip().lower())
    return "".join(ch for ch in s if not unicodedata.combining(ch))

BASE = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(BASE, "circuitos.csv")

# Mapeo categoria -> rango de |alpha| (coherente con el barrido 0..14 de los datos)
CATEGORIA_RANGO = {"low": (0, 5), "medium": (5, 9), "high": (9, 14)}
CATEGORIA_ETIQUETA = {"low": "baja carga", "medium": "carga media", "high": "alta carga"}


def cargar():
    """Lee circuitos.csv -> lista de dicts."""
    with open(CSV, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def listar(categoria=None):
    """Lista circuitos, opcionalmente filtrados por categoria (low/medium/high)."""
    filas = cargar()
    if categoria:
        filas = [c for c in filas if c["categoria_downforce"] == categoria]
    return filas


def _buscar(nombre):
    nl = _fold(nombre)
    filas = cargar()
    for c in filas:                       # exacta (sin acentos, sin mayusculas)
        if _fold(c["nombre"]) == nl:
            return c
    for c in filas:                       # tolerante: coincidencia parcial
        if nl in _fold(c["nombre"]):
            return c
    raise KeyError(f"Circuito no encontrado: {nombre!r}")


def rango_angulo(nombre):
    """Devuelve (nombre_canonico, categoria, (lo, hi), rango_str) del circuito dado."""
    c = _buscar(nombre)
    cat = c["categoria_downforce"]
    return c["nombre"], cat, CATEGORIA_RANGO[cat], c["rango_angulo_deg"]


def mensaje_orientativo(nombre):
    """Texto de encuadre HONESTO para la UI. Deja claro que es orientativo/fisico,
    no un setup real. USAR SIEMPRE al presentar la sugerencia de un circuito."""
    c = _buscar(nombre)
    cat = c["categoria_downforce"]
    lo, hi = CATEGORIA_RANGO[cat]
    etiqueta = CATEGORIA_ETIQUETA[cat]
    prioridad = ("bajo drag" if cat == "low"
                 else "máximo downforce" if cat == "high"
                 else "equilibrio downforce/drag")
    return (f"En {c['nombre']} ({etiqueta}) trabajarías en torno a "
            f"|α| ≈ {lo}-{hi}°, priorizando {prioridad}. "
            f"Es una guía derivada del tipo de circuito; el ángulo real depende del "
            f"coche completo, el reglamento y las condiciones, que van más allá del "
            f"perfil aislado.")


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")   # consola Windows (cp1252) -> UTF-8
    except Exception:
        pass
    todos = cargar()
    print(f"{len(todos)} circuitos en la base de datos:\n")
    for cat in ("low", "medium", "high"):
        sub = listar(cat)
        lo, hi = CATEGORIA_RANGO[cat]
        print(f"  [{cat.upper()}]  |α| {lo}-{hi}°  ({len(sub)} circuitos): "
              + ", ".join(c["nombre"] for c in sub))
    print("\nEjemplo de encuadre honesto:")
    for n in ("Monza", "Suzuka", "Mónaco"):
        print("  - " + mensaje_orientativo(n))
