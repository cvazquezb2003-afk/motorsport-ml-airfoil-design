"""BATERIA SOBOL — ETAPA B: verifica en CATIA + XFOIL las propuestas del buscador
que ejecuta la web.

    python bateria_sobol_etapaB.py --dry-run   # sin CATIA: valida indices y estructura
    python bateria_sobol_etapaB.py             # ~2 h, REQUIERE CATIA ABIERTO
    python bateria_sobol_etapaB.py --limite N  # solo los N primeros casos

--- POR QUE ESTO ES UN ENVOLTORIO Y NO UN SCRIPT NUEVO ---
La logica de verificacion NO se reimplementa ni se modifica: se ejecuta la de
`bateria_densif_etapaB.py`, tal cual, que a su vez importa `_ld_real_tereal` de la bateria
de julio. Lo UNICO que cambia es de donde se leen las propuestas y adonde se escriben los
resultados. Si la verificacion difiriera aunque fuese en un timeout, la comparacion contra
el 2,8 % dejaria de ser valida — es el mismo argumento que ese script se aplica a si mismo
respecto a julio.

Por eso se reasignan sus constantes de rutas antes de llamar a su `main()`, en vez de
tocar el fichero. `carga_indices()`, `_fusiona_previo()` y el bucle de CATIA leen esas
constantes en tiempo de ejecucion, asi que redirigirlas basta.

Lo que NO se toca:
  - `valida()`, el bucle de CATIA/XFOIL y la tabla final: identicos.
  - `REF_JULIO`: sigue apuntando a la bateria de julio, que es la linea de referencia
    correcta tambien aqui (las 40 condiciones son las mismas).
  - Los ficheros `bateria_densif_*`, `dsf_*` y `bateria_densif_stars/` de la tirada con DE:
    esto escribe solo en `bateria_sobol_*` y `bateria_sobol_stars/`.

--- OJO CON EL k=0 ---
La Etapa B exige los dos indices, asi que se verifican k=0 y k=2. Pero el k=0 de la bateria
de DE minimizaba el MODELO LD de produccion, mientras que el de aqui minimiza la MEDIA DEL
ENSEMBLE: no es el mismo objetivo y **su cifra no es comparable con el 6,9 %**. El
comparable es k=2, que es el del 2,8 %. La tabla final imprimira ambos; hay que leerla con
esto delante.
"""
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

import bateria_densif_etapaB as B

# --- unico cambio: de donde se lee y adonde se escribe --------------------------
B.IDX = {"k0": os.path.join(BASE, "bateria_sobol_k0_index.json"),
         "k2": os.path.join(BASE, "bateria_sobol_k2_index.json")}
B.RES = {"k0": os.path.join(BASE, "bateria_sobol_k0_resultados.json"),
         "k2": os.path.join(BASE, "bateria_sobol_k2_resultados.json")}
B.STARS = os.path.join(BASE, "bateria_sobol_stars")

if __name__ == "__main__":
    print("=" * 100)
    print("BATERIA SOBOL — ETAPA B  (envoltorio sobre bateria_densif_etapaB, sin modificarlo)")
    print("=" * 100)
    print("   indices    : %s" % ", ".join(os.path.basename(p) for p in B.IDX.values()))
    print("   resultados : %s" % ", ".join(os.path.basename(p) for p in B.RES.values()))
    print("   .dat       : %s" % os.path.basename(B.STARS))
    print("   referencia : %s (intacta)"
          % ", ".join(os.path.basename(p) for p in B.REF_JULIO.values()))
    print()
    sys.exit(B.main())
