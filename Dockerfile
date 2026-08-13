# =============================================================================
# Inverted Wing Designer — imagen de despliegue (Linux, con XFOIL)
#
# Sirve igual en Render, Fly.io o un VPS: no lleva nada especifico de plataforma.
# El puerto se lee de la variable PORT, que es lo que inyectan Render y Fly.
# =============================================================================
FROM python:3.12-slim-bookworm

# XFOIL desde el repositorio de Debian: queda en /usr/bin/xfoil, dentro del PATH,
# que es justo lo que resuelve rutas.py con shutil.which("xfoil"). No hay que
# configurar ninguna variable: la cascada lo encuentra sola.
#
# libgfortran5 y libx11-6 son dependencias del binario. XFOIL enlaza X11 por su
# libreria de dibujo AUNQUE aqui se use solo en modo texto por stdin; sin ella no
# arranca. No hace falta servidor X, solo la libreria.
# xvfb: servidor X VIRTUAL. No es un rodeo, es un requisito del binario.
# El xfoil de Debian esta enlazado contra libX11 de forma NO opcional (ldd lo
# confirma) y su volcado del Cp pasa por la libreria de dibujo. Sin display:
#   - tal cual        -> "Cannot open display...aborting", cp.txt no se escribe
#   - con PLOP/G      -> SIGFPE (rc=136), cp.txt tampoco se escribe
# Comprobado ademas que NO es culpa de nuestra geometria: un NACA generado por
# el propio XFOIL falla igual, y sin viscoso tambien.
# xauth NO es opcional aunque apt lo liste como "recomendado": xvfb-run es un
# SCRIPT DE SHELL que llama a xauth para crear la cookie del display. Con
# --no-install-recommends se queda fuera y xvfb-run muere al instante, sin
# llegar a ejecutar XFOIL. Ya paso una vez: la prueba de humo dio "0 filas" en
# 0,1 s y parecia que xvfb no servia, cuando el que faltaba era xauth.
# xfonts-base evita los avisos de fuentes al arrancar el servidor X.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        xfoil \
        xvfb \
        xauth \
        xfonts-base \
        libgfortran5 \
        libx11-6 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependencias primero: esta capa se cachea y no se rehace al cambiar el codigo.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# El ensemble de sigma (106 MB) NO viaja en el repo: supera el limite de GitHub.
# Se regenera aqui desde airfoil_dataset_densif_merged.csv (~1 min).
# OJO: build_ensemble.py, no winner_curse.py — ese lee otro dataset y produciria
# un ensemble PRE-DENSIF con el nombre de produccion, sin avisar. Ver el
# comentario largo en build_ensemble.py.
RUN python build_ensemble.py

# Comprobacion en tiempo de BUILD: si XFOIL no esta donde se espera o la app no
# importa, el build FALLA aqui. Es preferible a descubrirlo con el servicio
# arriba y el Cp devolviendo el aviso de "version local" en un despliegue que
# justamente se hizo para tener Cp.
RUN python -c "import rutas, sys; \
print('XFOIL:', rutas.XFOIL_EXE, '|', rutas.XFOIL_ORIGEN); \
sys.exit(0 if rutas.XFOIL_DISPONIBLE else 1)" \
 && python -c "import dashboard_app; print('la app importa correctamente')"

# PRUEBA DE HUMO: que XFOIL PRODUZCA un Cp, no que exista y no de error.
# La comprobacion anterior (XFOIL_DISPONIBLE) es un os.path.isfile: paso durante
# todo un despliegue en el que el Cp no funcionaba. Aqui se exige el FICHERO con
# FILAS NUMERICAS, que es lo unico que demuestra algo.
# Se prueban las dos variantes para decidir con datos si PLOP hace falta bajo
# xvfb; basta con que UNA funcione para seguir, y el log dice cual.
COPY humo_xfoil.sh /usr/local/bin/humo_xfoil.sh
RUN chmod +x /usr/local/bin/humo_xfoil.sh && /usr/local/bin/humo_xfoil.sh

ENV PORT=5001 \
    PYTHONUNBUFFERED=1 \
    XFOIL_CONCURRENCIA=2 \
    XFOIL_TIMEOUT_S=20
EXPOSE 5001

# UN SOLO worker, con hilos. Cada worker carga sus propios ~640 MB de modelos, asi
# que dos workers son 1,3 GB: la concurrencia se saca de los HILOS, no de los
# procesos. Ademas el cache de Cp es un dict en memoria del proceso, y con varios
# workers cada uno tendria el suyo.
# XFOIL corre como subproceso y libera el GIL, asi que los hilos van bien.
# xvfb-run envuelve a TODO gunicorn: asi cada subproceso XFOIL hereda el DISPLAY
# del servidor X virtual. Un solo Xvfb para el proceso entero, no uno por llamada.
#   -a  elige un numero de display libre (evita choques si algo reinicia)
#   pantalla minima: no se muestra a nadie, solo tiene que existir
CMD ["sh", "-c", "xvfb-run -a --server-args='-screen 0 640x480x24' gunicorn --bind 0.0.0.0:${PORT:-5001} --workers 1 --threads 4 --timeout 120 dashboard_app:app"]
