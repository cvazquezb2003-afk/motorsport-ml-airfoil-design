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
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        xfoil \
        libgfortran5 \
        libx11-6 \
 && rm -rf /var/lib/apt/lists/*
# (no se invoca xfoil aqui a modo de prueba: es un programa INTERACTIVO que lee
#  stdin, y una comprobacion asi puede quedarse esperando. La verificacion de
#  verdad es el `python -c "import rutas..."` de mas abajo, que si falla el build)

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
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-5001} --workers 1 --threads 4 --timeout 120 dashboard_app:app"]
