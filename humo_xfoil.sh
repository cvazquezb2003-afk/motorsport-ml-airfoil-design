#!/bin/sh
# =============================================================================
# PRUEBA DE HUMO DE XFOIL — se ejecuta durante el `docker build`.
#
# Por que existe:
#   La comprobacion anterior era `rutas.XFOIL_DISPONIBLE`, un os.path.isfile.
#   Paso durante un despliegue entero en el que el Cp NO funcionaba: XFOIL
#   existia, era ejecutable, convergia... y moria antes de escribir el fichero.
#   Que un programa este no demuestra que haga su trabajo.
#
# QUE EXIGE (y que no):
#   Aborta el build si XFOIL NO CONVERGE, si cp.txt NO EXISTE, o si cp.txt no
#   tiene FILAS NUMERICAS suficientes. El NUMERO DE COLUMNAS se informa pero no
#   tumba el build: el parser acepta 2 y 3 columnas a proposito (el XFOIL de
#   Debian escribe 2, el de Windows 3), asi que exigir 3 romperia el despliegue
#   bueno. Lo que no puede pasar es un fichero vacio.
#
#   Esa ultima guarda faltaba. Durante el ciclo de depuracion de xvfb el script
#   quedo en modo diagnostico —contaba las filas y solo las IMPRIMIA— y asi se
#   quedo, mientras el Dockerfile afirmaba que "se exige el FICHERO con FILAS
#   NUMERICAS". No se exigia: un cp.txt vacio pasaba el build. Detectado en la
#   auditoria del 2026-08-15. La guarda esta probada EN NEGATIVO con un cp.txt
#   vacio y con uno de solo cabecera; sin esa prueba seria otra comprobacion que
#   nadie ha visto fallar.
#
#   Se mide ademas el TIEMPO: si XFOIL "falla" en menos de un segundo es que no
#   llego a arrancar, y eso es el envoltorio (xvfb-run/xauth/display), no XFOIL.
#   Distinguirlo importa: ya paso una vez que leimos "0 filas" y la conclusion
#   facil habria sido "xvfb no sirve", cuando el que faltaba era xauth.
# =============================================================================
set -eu

DIR=/tmp/humo
MIN_SEG=1
# Minimo de filas numericas para creerse un Cp. Un perfil real da ~160 puntos; se
# pide 20 y no 1 porque tres numeros sueltos no son una distribucion de presion, y
# no 100 para no romper el build por un perfil de pocos paneles.
MIN_FILAS=20

rm -rf "$DIR"; mkdir -p "$DIR"; cd "$DIR"

echo "  === XFOIL bajo xvfb, SIN PLOP (la configuracion que usa la app) ==="

ini=$(date +%s)
set +e
printf "%b" "NACA 2412\nPANE\nOPER\nVISC 1000000\nITER 200\nALFA -9\nCPWR cp.txt\n\nQUIT\n" \
    | xvfb-run -a --server-args="-screen 0 640x480x24" xfoil > log.txt 2>&1
rc=$?
set -e
fin=$(date +%s)
seg=$((fin - ini))

echo "  rc=${rc}   duracion=${seg}s"

# ¿convergio? XFOIL imprime el residuo rms y la linea de resultados
if grep -q "rms:" log.txt; then
    echo "  convergencia: SI (hay iteraciones con rms en el log)"
    grep -E "^ +a = " log.txt | tail -1 | sed 's/^/    /'
    CONVERGE=1
else
    echo "  convergencia: NO"
    CONVERGE=0
fi

if [ ! -f cp.txt ]; then
    echo "  *** cp.txt NO EXISTE ***"
    if [ "$seg" -lt "$MIN_SEG" ] && [ "$CONVERGE" = "0" ]; then
        echo "  *** murio en ${seg}s sin converger: es el ENVOLTORIO, no XFOIL ***"
    fi
    echo "  --- log (ultimas 25 lineas) ---"
    tail -25 log.txt
    exit 1
fi

# ---- AQUI ESTA EL DIAGNOSTICO: el formato real del fichero ----
TOT=$(wc -l < cp.txt | tr -d ' ')
C2=$(awk 'NF==2' cp.txt | wc -l | tr -d ' ')
C3=$(awk 'NF==3' cp.txt | wc -l | tr -d ' ')
CGE2=$(awk 'NF>=2' cp.txt | wc -l | tr -d ' ')
CGE3=$(awk 'NF>=3' cp.txt | wc -l | tr -d ' ')
# FILAS NUMERICAS de verdad: >=2 campos y los dos primeros empiezan por digito o
# signo. Asi la cabecera de texto que escribe XFOIL no cuenta como dato.
NUM=$(awk 'NF>=2 && $1 ~ /^[-+]?[0-9.]/ && $2 ~ /^[-+]?[0-9.]/' cp.txt | wc -l | tr -d ' ')

echo "  === FORMATO REAL DEL cp.txt QUE ESCRIBE EL XFOIL DE DEBIAN ==="
echo "    wc -l (lineas totales) : ${TOT}"
echo "    lineas con EXACTAMENTE 2 columnas : ${C2}"
echo "    lineas con EXACTAMENTE 3 columnas : ${C3}"
echo "    lineas con >=2 columnas           : ${CGE2}"
echo "    lineas con >=3 columnas           : ${CGE3}"
echo "    FILAS NUMERICAS (>=2 campos)      : ${NUM}   <-- lo que se EXIGE (min ${MIN_FILAS})"
echo "  --- head -8 del contenido REAL ---"
head -8 cp.txt | cat -A | sed 's/\$$//' | sed 's/^/    |/'
echo "  ----------------------------------"

if [ "$CONVERGE" = "0" ]; then
    echo "  *** XFOIL no convergio: build abortado ***"
    tail -25 log.txt
    exit 1
fi

if [ "$NUM" -lt "$MIN_FILAS" ]; then
    echo "  *** cp.txt EXISTE pero solo tiene ${NUM} filas numericas (minimo ${MIN_FILAS})"
    echo "  *** un fichero vacio o de solo cabecera NO es un Cp: build abortado ***"
    tail -25 log.txt
    exit 1
fi

echo "  OK: XFOIL converge y escribe un cp.txt con ${NUM} filas numericas."
rm -rf "$DIR"
