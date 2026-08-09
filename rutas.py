"""
RUTAS DEL PROYECTO Y LOCALIZACION DE XFOIL — fuente unica.

Existe por dos motivos:

1. La carpeta del proyecto se derivaba de `__file__` en 78 de 97 modulos, pero unos
   pocos llevaban `C:\\Users\\MSI-06\\...` escrito a mano. Aqui esta una sola vez.

2. La ruta a xfoil.exe estaba declarada LITERALMENTE en SIETE ficheros. Siete copias
   del mismo valor sin fuente unica: si alguien mueve XFOIL y arregla cinco, el
   sistema queda a medias — la inversa funciona y el Cp no, que es el peor modo de
   fallo porque no parece un fallo.

MODO WEB vs MODO LOCAL
----------------------
El despliegue web NO lleva XFOIL. En vez de reventar, `XFOIL_DISPONIBLE` queda en
False y quien lo necesite degrada con un aviso (ver MSG_CP). Todo lo que vive del
surrogate — diseno, KPIs, cargas, siluetas, comparacion de formas — funciona igual
en los dos modos, porque no toca XFOIL en ningun momento.
"""
import os
import shutil

BASE = os.path.dirname(os.path.abspath(__file__))

# Carpetas del proyecto, derivadas de BASE (nunca absolutas a mano)
GRAFICAS = os.path.join(BASE, "graficas")
DATASET_RUNS = os.path.join(BASE, "dataset_runs")


def _localiza_xfoil():
    """Resuelve el ejecutable de XFOIL en cascada. Devuelve (ruta, origen).

    El orden importa: la variable de entorno gana SIEMPRE, para que un despliegue
    o un contenedor puedan imponer su binario sin tocar codigo. La ruta de la
    maquina de desarrollo va la ULTIMA, como cortesia para que siga funcionando
    sin configurar nada, no como valor de referencia.
    """
    env = os.environ.get("XFOIL_EXE", "").strip().strip('"')
    if env:
        if os.path.isfile(env):
            return env, "variable de entorno XFOIL_EXE"
        # configurado pero mal: es un error del operador, no un 'no hay XFOIL'
        return None, f"XFOIL_EXE apunta a algo que no existe: {env}"

    for nombre in ("xfoil", "xfoil.exe"):
        p = shutil.which(nombre)
        if p:
            return p, f"encontrado en el PATH ({nombre})"

    # ultimo recurso: la instalacion de la maquina de desarrollo
    local = r"C:\Users\MSI-06\Desktop\XFOIL\xfoil.exe"
    if os.path.isfile(local):
        return local, "instalacion local de desarrollo"

    return None, "no encontrado"


XFOIL_EXE, XFOIL_ORIGEN = _localiza_xfoil()
XFOIL_DISPONIBLE = XFOIL_EXE is not None

# Aviso UNICO para cuando falta XFOIL. Se escribe aqui y no en cada endpoint para
# que el texto que ve el usuario no pueda divergir entre Results y Compare.
MSG_CP = ("Pressure distribution (Cp) requires XFOIL, available in the local "
          "version. Clone the repo from GitHub to run the full analysis. "
          "The ML design, KPIs and shape comparison work fully here.")

# Caso distinto: XFOIL SI existe pero no ha podido resolver este perfil concreto.
# No es lo mismo y no debe decirse igual: aqui no falta una capacidad, ha fallado
# un calculo sobre una geometria. La geometria descargable NO depende de XFOIL,
# asi que el aviso lo dice explicitamente para que nadie crea que se ha perdido.
MSG_CP_FALLO = ("Pressure distribution (Cp) could not be computed for this "
                "profile: XFOIL did not converge on it, and no reference "
                "profile was available as a fallback. The geometry and its "
                "downloads below are unaffected.")


# -----------------------------------------------------------------------------
# LIMITES DE EJECUCION DE XFOIL  (importan en el despliegue publico)
# -----------------------------------------------------------------------------
# Medido en esta maquina: una llamada de Cp tarda 0,48 s de mediana (0,30-1,19 s)
# y su proceso ocupa 5,6 MB. Barato. El problema no es el coste unitario sino que
# el boton "Compare Cp" de una web publica lanza PROCESOS DEL SISTEMA sin freno.
#
# SEMAFORO: en un servidor de 1 vCPU las llamadas se serializan igual, asi que
# dejar entrar mas de 2-3 a la vez no acelera nada y solo alarga la cola de todos.
# Se limita la CONCURRENCIA, no el numero total.
#
# TIMEOUT: estaba en 120 s. Con llamadas de medio segundo eso es una eternidad:
# unas pocas peticiones colgadas bloqueaban el servicio dos minutos. 20 s deja
# margen de sobra (40x la mediana) y corta rapido lo que se atasque.
XFOIL_CONCURRENCIA = int(os.environ.get("XFOIL_CONCURRENCIA", "2"))
XFOIL_TIMEOUT_S = int(os.environ.get("XFOIL_TIMEOUT_S", "20"))

_sem = None


def semaforo_xfoil():
    """Semaforo compartido para no lanzar mas de XFOIL_CONCURRENCIA a la vez.
    Perezoso: no se crea si nadie usa XFOIL (modo web sin binario)."""
    global _sem
    if _sem is None:
        import threading
        _sem = threading.BoundedSemaphore(max(1, XFOIL_CONCURRENCIA))
    return _sem


def exige_xfoil(que="esta operacion"):
    """Lanza con un mensaje util si no hay XFOIL. Para los scripts de consola
    (densificacion, baterias, pipeline), donde lo correcto es parar y decir como
    configurarlo, no degradar en silencio."""
    if not XFOIL_DISPONIBLE:
        raise RuntimeError(
            "%s necesita XFOIL y no se ha encontrado (%s).\n"
            "Indica el ejecutable con la variable de entorno XFOIL_EXE, "
            "o ponlo en el PATH." % (que, XFOIL_ORIGEN))
    return XFOIL_EXE


if __name__ == "__main__":
    print("BASE            : %s" % BASE)
    print("XFOIL_EXE       : %s" % XFOIL_EXE)
    print("origen          : %s" % XFOIL_ORIGEN)
    print("XFOIL_DISPONIBLE: %s" % XFOIL_DISPONIBLE)
    print("modo            : %s" % ("LOCAL (analisis completo)" if XFOIL_DISPONIBLE
                                    else "WEB (sin Cp)"))
