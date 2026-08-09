# AGENTS.md — Contexto del proyecto

Notas de contexto para futuras sesiones. Pipeline de **generación y análisis
de perfiles alares**: CATIA (geometría) → puntos → ASC → DAT → XFOIL (polar) →
gráficas, orquestado por `pipeline_airfoil_api.py`.

---

## 🗺️ MAPA RÁPIDO: los 4 bloques del proyecto

> Estado global: **núcleo técnico CERRADO** (datos, surrogates, inversa validada
> a ~4% de error). Lo que queda es la **capa de presentación**.
> Inventario completo de la carpeta: ver **"Inventario de archivos"** al final.

> ## 🟢 ACTUALIZACIÓN (2026-07-24): DATASET Y MODELOS TE-REAL EN PRODUCCIÓN
>
> Se regeneró todo el universo con el **conversor TE-real** (TE romo por hueco,
> sin el corte amputado) y se **promocionó a producción**. La **limitación 5 está
> RESUELTA**: el `trailing_edge_thickness_mm` ya llega a XFOIL y el kink de 42.1°
> desaparece (geometría con TE romo real).
>
> - **Dataset de producción** (`airfoil_dataset.csv`): ahora **TE-real** — **969
>   perfiles, 20.349 filas, 16.526 ok**, convergencia **81.2%** (antes 74.2%).
>   Mejor en las 3 zonas (150-200: 69.8%, 200-400: 82.2%, 400-500: 87.3%).
> - **Modelos de producción reentrenados** (mismos nombres, 11 features, mismo
>   protocolo): CL y LD mejoran (LD MAE 2.73→2.36, R² 0.881→0.902); CD apenas peor
>   en MAE pero **mejor R²** (0.869→0.875) — no preocupa.
> - **Batería revalidada (20 casos, geometrías TE-real en CATIA+XFOIL):**
>   **k=0 = 23.9%**, **k=2 = 4.1%** (viejo: 22.2% / 4.0%). El winner's curse se
>   controla igual de bien; k=2 sigue siendo el default seguro.
> - **`te_thickness` es RESTRICCIÓN DE FABRICACIÓN, no variable aerodinámica**
>   (confirmado en DOS datasets): al regenerar con TE-real su señal **NO subió**,
>   bajó (importancia LD de `te_rel` 4.7%→1.4%). El 7º parámetro no "se reconecta"
>   porque el óptimo aero está por debajo del mínimo fabricable de 1 mm (composite).
> - **Universo viejo archivado en `legacy/`** (`*_amputado_legacy.*`): dataset +
>   modelos + ensemble + meta. Nada borrado; reversible. Copias `*_tereal.*` también
>   conservadas en la raíz como referencia.
> - Inversa (`inversa_ld_v2.py`) verificada con los modelos nuevos: carga OK,
>   11 features OK, DE converge.

### 1️⃣ GENERAR — geometría y datos (CATIA + XFOIL)
| Script | Rol |
|---|---|
| `pipeline_airfoil_api.py` | Orquestador de un perfil (Steps 1-7). Deriva el Reynolds |
| `airfoil_generator.py` | Step 1: perfil en CATIA (plano ZX, Geometrical Sets) |
| `airfoil_points.py` | Step 2: nube de puntos (LE 290 + TE 10) |
| `export_cloud_ascii.py` | Step 3: export ASC ⚠️ **el paso más frágil** |
| `asc_to_dat.py` | Step 4: ASC→DAT + normalización a cuerda |
| `run_xfoil.py` | Step 5: XFOIL (alphas argv1, Reynolds argv2) |
| `generate_batch.py` | Lotes: `--random` / `--sobol` / `--sobol-extremos` / `--manual` |

### 2️⃣ APRENDER — surrogates (CL / CD / LD)
| Script | Rol |
|---|---|
| `feature_utils.py` | **Fuente única** de las 11 features. **Crítico** |
| `eda_ml_filtrado150.py` | **Entrenador de producción**. Guarda modelo + histórico |
| `winner_curse.py` | Entrena el ensemble de σ (~17 min). Regenerador |
| `modelo_LD_inversa_xgb.joblib` | Modelo de producción (11 features) |
| `ensemble_ld_sigma.joblib` | Ensemble de incertidumbre (**64 MB** ⚠️ GitHub) |
| `ml_history.json` / `.csv` | Histórico de reentrenos |

### 3️⃣ INVERTIR — proponer formas
| Script | Rol |
|---|---|
| `inversa_ld_v2.py` | **Producción**: zona fiable p5-p95 + avisos + penalización k=2 |
| `inversa_bateria.py` / `bateria_k2.py` | Generadores de la batería de validación |
| `bateria_resultados.json` / `bateria_k2_resultados.json` | **Evidencia** k=0 vs k=2 |

### 4️⃣ ENSEÑAR — capa visual (EN CONSTRUCCIÓN)
| Script | Rol | Estado |
|---|---|---|
| `plot_perfil.py` | Forma del perfil 1:1 | ✅ sirve tal cual |
| `cp_on_demand.py` | Cp a demanda (orden de arco, correcto) | ✅ sirve tal cual |
| `eda_velocidad.py` | L/D vs α con las 3 velocidades | 🟡 extender (falta CL y CD) |
| `plot_polar.py` | Polares de UNA velocidad | 🟡 extender |
| `airfoil_3d.py` | Ala 3D (extrude). **Solo visual** | ✅ aparte |
| `flask_airfoil_api.py` | **API REST ya montada** (para la UI futura) | 🟡 sin probar tras refactor |

---

## 🚫 Limitaciones conocidas: decisión CONSCIENTE de no corregir

> Las cuatro están medidas y documentadas. **No "arreglarlas" sin petición explícita.**

| # | Limitación | Por qué NO se corrige |
|---|---|---|
| 1 | **`te_rel` confundido con la cuerda** (corr. −0.662; zonas casi disjuntas: mediana 1.435% en 150-200 vs 0.559% en 400-500) | El espesor se sortea en mm absolutos. **Sin daño medido** (casos 4 y 5 en p1-p2 global verificaron con 4% y 0%). Corregirlo exige regenerar el dataset entero. *Si se generan datos nuevos: pasar a muestreo proporcional.* Detalle ↓ |
| 2 | **Saturación del TE en 1 mm** (6 de 8 propuestas en 1.17-1.27 mm) | El óptimo aerodinámico está por debajo del rango, pero **1 mm es el límite de fabricación en composite**. Es una **restricción real**, no un fallo. Bajarlo daría perfiles no fabricables. Detalle ↓ |
| 3 | ✅ **RESUELTA — Kink de 42.1° en el TE del `.dat`** — lo creaba el corte de `asc_to_dat.py`. Con el conversor TE-real (TE romo por hueco) el kink **desaparece**; los `.dat` de producción ya no lo tienen. Era el síntoma geométrico de la limitación 5, resuelta con ella | — |
| 4 | **Join `AIRFOIL` de CATIA no es extruible** (~1268 mm ≈ 2× el perímetro real: duplica extradós/intradós, que ya están dentro de `LE ARC`) | El join solo es un **elemento de árbol**; el `.dat` sale de la **nube de puntos**, no del join. Para el 3D se usa `LE ARC + TE PROFILE` (= contorno correcto, 667 mm). No afecta a ningún resultado. Detalle ↓ |
| 5 | ✅ **RESUELTA (2026-07-24) — `trailing_edge_thickness_mm` ya llega a XFOIL.** Se regeneró el dataset con el conversor **TE-real** (TE romo por hueco, sin el corte de la constante `0.03`) y se promocionó a producción. Batería revalidada (k=2 = 4.1%). **Hallazgo:** aun llegando a XFOIL, el 7º parámetro **sigue siendo señal débil** → es una **restricción de fabricación** (mín. 1 mm en composite), no una variable aero libre. Ver limitación 1 y el bloque de actualización arriba | Universo viejo archivado en `legacy/`. Detalle ↓ |

---

## Dominio: MOTORSPORT (alas invertidas)

- El objetivo son **alas invertidas que generan downforce**, no sustentación.
- Por tanto **los CL negativos son CORRECTOS y esperados** — NO son un error de
  signo. El downforce aumenta hacia **ángulos de ataque negativos**.
- No "corregir" el signo de CL ni asumir que algo está mal por ver CL < 0.

## Ángulo de ataque y normalización de geometría

- El ángulo de ataque lo controla **XFOIL** vía el parámetro `alphas`, **NO
  CATIA**.
- `project_to_chord_system` en `asc_to_dat.py` normaliza la geometría y
  neutraliza cualquier rotación. Por eso **`chord_angle_deg` no afecta al
  resultado aerodinámico** (se mantiene fijo en 350).

## Kink en el cierre del TE ✅ CAUSA IDENTIFICADA (antes mal atribuida)

> **CORREGIDO:** este apartado decía que el kink venía del cierre lineal. La causa
> real es la **constante `0.03`** de `order_le_chain_for_xfoil` (limitación 0 ↑).
> El kink es el **síntoma geométrico** del mismo bug.

- **El kink NO viene de CATIA.** Medido:
  - **El perfil de CATIA (`LE ARC`) es LISO**: giro mediano **0.18°** por vértice,
    **máximo 7°** (y ese máximo está en el **morro**, donde la curvatura es alta —
    no en el TE).
  - En el ASC crudo, la unión del perfil con el bloque TE forma **86.8° / 99.3°**:
    ese es el **TE romo real y LEGÍTIMO** de CATIA (una cara de ~3.76 mm). No es un
    defecto.
- **Los 42.15° del `.dat` los CREA `asc_to_dat.py`.** Es la recta del corte:
  de `(0.972, −0.0145)` a `(0.995, +0.0063)` → `atan2(0.0208, 0.0230) = 42.1°`
  — exactamente el ángulo medido en el `.dat`. El corte **sustituye el 2.3% final
  del perfil** por una recta.
- **No rompe la convergencia** de XFOIL y **no se corrige** (ver limitación 0:
  arreglarlo exige regenerar el dataset).
- **No reintentar arreglarlo sin que se pida explícitamente.**

### Por qué el kink se ve en el PNG y no en CATIA (no es un artefacto de dibujo)

- **`set_aspect("equal")` funciona**: medido del render real, **29.825 mm/pulgada en
  AMBOS ejes**, ratio Y/X = **1.000000**. Cero deformación.
- **No falta muestreo en el TE**: espaciado uniforme (mediana **2.018 mm**), 34 puntos
  en el último 10% de cuerda. Los segmentos más largos están en el **morro**, no en el TE.
- **Es escala de observación**: el corte ocupa ~1.3% de la cuerda. En CATIA miras el
  perfil entero y son un píxel (harían falta ~50:1 de zoom). En el PNG, con el eje Y
  comprimido a ~44 mm de rango, esos mismos mm ocupan ~8.5% de la altura visible.

### ❌ DESCARTADO: el escalado anisótropo de `project_to_chord_system` NO es un problema

> Documentado para **no volver a investigarlo**.

- `project_to_chord_system` reescala **solo X** a [0,1] (`(x - x_min)/(x_max - x_min)`)
  y **no toca Y** → escalado anisótropo. Suena mal, pero **es despreciable**.
- **Medido sobre 965 perfiles:**
  - `span = x_max − x_min` ∈ **[1.00027, 1.00581]** (mediana 1.00115) → se desvía de
    1.0 solo un **0.115%** de mediana, **0.58% máx**.
  - Factor de deformación dentro de **±0.6% en el 100%** de los perfiles
    (**0 fuera de ±2%**).
  - **Errores angulares: mediana 0.003°-0.019°, MÁXIMO 0.112°** (en
    `trailing_edge_angle_deg`). Sobre rangos muestreados de 7-12°, es ~1 parte en 100
    de la resolución. **Irrelevante.**
- **Es SISTEMÁTICO, la forma benigna**: factor < 1 en el **100%** de los perfiles,
  sesgo constante **−0.131%**, dispersión entre perfiles **0.075%**
  (ratio dispersión/sesgo = 0.57 → domina el sesgo, no el ruido). Un sesgo uniforme
  del 0.13% en X es invisible tras normalizar por la cuerda.
- Correlaciona con `chord` (+0.645) y `te_thickness` (−0.606), **pero da igual**:
  es una correlación real sobre una magnitud del 0.1%.
- **⚠️ No confundir con la limitación 0.** El 0.1% de esto **no explica** el desajuste
  de 2.3× del TE: la causa única de aquello es la **banda del 3%**.

## Generación del dataset (`generate_batch.py`)

- **Cuatro modos** (+ un flag):
  - `--random N` → sortea (uniforme independiente) los **7 parámetros de forma**
    dentro de `SHAPE_PARAM_RANGES`.
  - `--sobol N` → muestreo **Sobol** (cobertura uniforme del espacio 7D). Secuencia
    **continuable** vía `sobol_state.json` (`seed` + `consumed`): cada tanda arranca
    donde acabó la anterior, sin repetir puntos.
  - `--sobol-extremos N_HIGH N_LOW` → genera **solo en las bandas extremas de cuerda**
    (`CHORD_BANDS`: high = 400-500, low = 150-200), cada una con su **secuencia Sobol
    propia** (`sobol_state_ext_high.json` / `sobol_state_ext_low.json`) y su `source`
    (`sobol_ext_high` / `sobol_ext_low`). No interfiere con la secuencia principal.
  - `--manual archivo.json` → procesa perfiles concretos definidos por el usuario.
  - `--dry-run` → solo imprime los parámetros de forma (no corre CATIA, no toca el
    dataset ni el estado Sobol). Útil para inspeccionar cobertura antes de un lote.
- ⚠️ **El estado Sobol avanza al MUESTREAR, no al generar.** Si un lote se corta a
  medias, el `consumed` ya contabilizó todos los puntos muestreados → **rebobinarlo a
  mano** antes de reanudar o se saltarán puntos sin generar.
- Salida: **`airfoil_dataset.csv`**, formato **coma como separador de columnas
  y punto decimal** (estándar internacional, pensado para Python/pandas:
  `pd.read_csv(...)` sin argumentos).
- `status` distingue la causa de fallo: `ok`, `error_catia` (falló en Steps
  1/2/3 de geometría/export), `error_xfoil_no_converge` (llegó a XFOIL pero la
  polar quedó sin fila), `error_otro`. El mensaje original va en `error_detail`.
- Cada perfil archiva sus ficheros clave (DAT/polar/ASC) en `dataset_runs/{run_id}/`.

### Dataset MULTI-ÁNGULO + BARRIDO DE REYNOLDS + ÁNGULOS ESCALONADOS (vigente)

- Cada perfil es **una sola geometría de CATIA** evaluada en XFOIL a **3
  velocidades** (`VELOCITIES_KMH = [110, 180, 290]` km/h) y, en cada una, a su
  **propia lista de ángulos** (`VELOCITY_ALPHAS`), porque a más velocidad/Reynolds
  la pérdida se retrasa y se pueden barrer ángulos más agresivos:
  - **110 km/h:** `[0, -2, -4, -6, -8, -10]` (6 ángulos)
  - **180 km/h:** `[0, -2, -4, -6, -8, -10, -12]` (7 ángulos)
  - **290 km/h:** `[0, -2, -4, -6, -8, -10, -12, -14]` (8 ángulos)
- Son **6 + 7 + 8 = 21 condiciones por perfil** → 21 filas por perfil.
- La clave de fila es **(`run_id`, `alpha_deg`, `velocidad_kmh`)**; agrupar por
  `run_id` da el perfil completo.
- **Reynolds variable por cuerda:** el Re ya **no es fijo**. Se calcula por
  perfil y velocidad con **`Re = (rho · V · L) / mu`**, con aire a nivel del mar
  (`rho = 1.225 kg/m³`, `mu = 1.81e-5 Pa·s`), **L = cuerda en metros** (la cuerda
  del dataset está en mm → `/1000`) y **V en m/s** (velocidad en km/h → `/3.6`).
  La fórmula vive en `compute_reynolds` de `generate_batch.py`. Ej.: cuerda
  300 mm → Re ≈ 620.396 (110 km/h), 1.015.193 (180 km/h), 1.635.589 (290 km/h).
- La geometría de CATIA se genera **una sola vez** por perfil; lo que cambia es
  que **XFOIL se re-corre 3 veces** (una por velocidad) con el Reynolds
  correspondiente, fijando `run_xfoil.REYNOLDS` y `run_xfoil.ALPHAS` (= la lista
  de ángulos de esa velocidad).
- Columnas nuevas en el CSV: **`velocidad_kmh`** (110/180/290) y **`reynolds`**
  (el valor calculado para ese perfil a esa velocidad).
- **Convergencia parcial:** cada combinación (ángulo, velocidad) se registra por
  separado (`ok` / `error_xfoil_no_converge`). No se descarta el perfil entero.
- Datasets anteriores archivados (referencia, no borrar): **solo 0°** en
  `airfoil_dataset_alpha0.csv`; **multi-ángulo sin Reynolds** en
  `airfoil_dataset_multialpha.csv`.

## Hallazgos del análisis exploratorio (datos reales) ✅ validado

> ⚠️ **Muestra de estos hallazgos: 50 perfiles / 900 filas / 711 condiciones `ok`**
> (era el dataset de entonces). **El dataset actual tiene 989 perfiles / 20.769 filas
> / 15.107 `ok`** — ~20× más. Las conclusiones **NO se han recalculado** con el
> dataset completo.
>
> **Estado: se dan por válidas cualitativamente** (la física no cambia y el efecto
> Reynolds se ha reconfirmado indirectamente en cada reentreno: `reynolds` es la 1ª o
> 2ª feature en importancia en todos). Pero **las CIFRAS concretas de abajo (~48% de
> mejora, los ángulos óptimos exactos) son de la muestra vieja** — tratarlas como
> orden de magnitud, no como medición vigente. Recalcularlas es barato
> (`eda_velocidad.py`, `eda_optimo_290.py`) si alguna vez se necesitan exactas.

- **Efecto Reynolds confirmado:** a igual ángulo, **más velocidad = más
  eficiencia**. De 110 a 290 km/h la eficiencia (`|L/D|`) mejora **~48% de media**
  (de ~32 a ~48), en el **99% de los casos**. Causa: a más Reynolds **baja el CD**.
- **El ángulo de máxima eficiencia se DESPLAZA con la velocidad:** óptimo en
  **~−6° a 110 km/h**, **~−8° a 180 km/h**, **~−10° a 290 km/h**. A más velocidad
  la pérdida se retrasa y el óptimo se corre hacia ángulos más agresivos.
  **Implicación motorsport:** el reglaje ideal del ala depende de la
  velocidad/circuito (más suave a baja velocidad, más cargado a alta).
- **✅ RESUELTO — el óptimo a 290 km/h NO está más allá de −10°.** Antes se
  sospechaba que el óptimo a alta velocidad podía estar más allá de −10° (porque
  −10° era el borde del rango muestreado). Se implementó el **barrido de ángulos
  escalonado por velocidad** (hasta −14° a 290 km/h) precisamente para
  comprobarlo, y los datos lo **desmienten**: el óptimo de eficiencia a 290 km/h
  vive en la franja **−8°/−10°**, y los ángulos **−12/−14 son mayoritariamente
  zona de pérdida incipiente** (peor eficiencia), no óptimo. Prueba limpia: la
  media del ángulo óptimo apenas cambia al añadir −12/−14 (−7.5° recortando en
  −10° vs −7.8° con los datos profundos), porque −12/−14 caen *pasado* el óptimo.
  *(Validado con datos, pero con limitación: solo **11 perfiles** convergen hasta
  −14° a 290 km/h, así que la señal es sólida pero la muestra es pequeña y podría
  tener sesgo de selección.)*

## ⭐ Capa visual (PENDIENTE, MUY IMPORTANTE para el proyecto final)

> **Estado: PARCIALMENTE IMPLEMENTADA.** Es **capa de presentación**, no de
> generación de datos. El núcleo técnico ya está cerrado, así que **esto es lo que
> queda**. No perder esta visión.
>
> **Ya hecho:**
> - ✅ **Forma del perfil** — `plot_perfil.py` (1:1 real, desde `.dat` o `--run-id`)
> - ✅ **Cp a demanda** — `cp_on_demand.py` (orden de arco, Re real). **Correcto**
> - 🟡 **L/D vs α con las 3 velocidades** — `eda_velocidad.py`
>   (→ `eda_outputs/LD_vs_alpha_por_velocidad.png`)
>
> **Lo que falta de verdad:**
> - ❌ **Polar multi-velocidad con CL y CD** (hoy `eda_velocidad.py` solo hace L/D;
>   `plot_polar.py` hace CL/CD pero de **una sola velocidad**) → extender uno de los dos
> - ❌ **Compositor de la ficha** (forma + polares + Cp en una lámina)

- **Las gráficas NO se generan en la generación masiva** (modo `--random`): se
  mantiene el lote rápido y sin saturar el disco. **Se generan A DEMANDA.**
- **Dos tipos de gráfica, con propósitos distintos:**
  - **Gráficas de Cp (distribución de presiones):** la "foto" de **UN punto
    concreto** (un ángulo + una velocidad). Se generan a demanda para
    inspeccionar un perfil específico, o para mostrarlas cuando el modelo de ML
    prediga/proponga un perfil.
  - **Gráficas de polar (CL vs α, CD vs α, L/D vs α):** **curvas** que resumen el
    perfil completo a lo largo de los ángulos. Con el barrido de Reynolds, cada
    perfil tiene **3 curvas (una por velocidad: 110, 180, 290 km/h)**, que se
    pueden **superponer** en una misma gráfica para ver de un vistazo cómo cambia
    el comportamiento según ángulo y velocidad. Es la **"ficha visual" resumen**
    de un perfil.
- **Visión de integración final:** cuando el ML proponga un perfil para un
  objetivo del usuario, el sistema le devolvería su **ficha visual completa**
  (curvas polares a las 3 velocidades + Cp del punto óptimo), como **presentación
  profesional** del resultado, no solo números.

### Zigzag en las gráficas de Cp: causa y arreglo ✅ resuelto / ⚠️ pendiente en plot_cp

- **Síntoma:** las gráficas de Cp mostraban una **sierra/zigzag de alta frecuencia
  cerca del borde de salida** (x≈0.7–1.0).
- **Hipótesis DESCARTADAS (con validación en la fuente):** no venía de XFOIL, ni
  del **kink del cierre del TE** (la geometría solo aporta una muesca minúscula),
  ni del **Reynolds** (mismo perfil a 110/180/290 km/h → sierra idéntica). El
  volcado **nativo de XFOIL** (`HARD` → `plot.ps`) y los datos crudos `x,y,Cp`
  (`CPWR`) salen **suaves**.
- **Causa REAL:** `plot_cp.py` separa extradós/intradós por **mediana de `y` +
  orden por `x`**. En perfiles **invertidos de downforce**, las dos caras tienen
  `y≈0` cerca del TE, así que puntos de ambas caras caen en la misma rama y, al
  ordenar por x, la curva salta entre las dos caras → la sierra.
- **Solución de raíz:** separar las caras por **ORDEN DE ARCO** (recorrer el
  contorno cortando en `argmin(x)` del LE, como hace XFOIL). Elimina el zigzag sin
  ningún suavizado y **de paso arregla las etiquetas succión/presión** (la succión
  es la cara **inferior** en downforce invertido).
- **Estado:** ✅ **aplicado en `cp_on_demand.py`** (la herramienta de Cp a
  demanda; incluye `--hardcopy` para volcar la gráfica nativa de XFOIL como
  contraste). ⚠️ **`plot_cp.py` (Step 7 del pipeline) TODAVÍA tiene el bug** de la
  mediana de y: si algún día se usa para gráficas de producción, aplicar ahí el
  mismo arreglo de orden de arco.

### Rango soportado de cuerda: 150 – 500 mm ✅

- **El rango soportado del sistema es cuerda 150 – 500 mm.** `SHAPE_PARAM_RANGES`
  usa `chord_length_mm = (150, 500)` y la banda baja de extremos
  (`CHORD_BANDS["low"]`) se recortó a 150 – 200.
- **La franja 100 – 150 mm quedó EXCLUIDA**: a esa cuerda el Reynolds es demasiado
  bajo (`< ~300k`) y **XFOIL no converge de forma fiable** (convergencias dudosas,
  TE proporcionalmente romo). Los perfiles `< 150 mm` **NO se borran del CSV**,
  pero se **excluyen del entrenamiento** (filtro `chord_length_mm >= 150`) y de la
  **zona fiable de la inversa**. Si un usuario pide cuerda `< 150 mm`, la inversa
  **avisa de que está fuera de rango soportado** (no se niega, pero marca baja
  confianza y exige verificación XFOIL).
- Reentrenar con el dataset filtrado `>= 150` mejora las tres zonas (150-200,
  200-400, 400-500) sin la de 100-150 arrastrando el promedio. Modelo de inversa
  de LD (`modelo_LD_inversa_xgb.joblib`) re-guardado con datos `>= 150`.

### Features del modelo: 11 (base 9 + 2 derivadas físicas) ✅

- El modelo usa **11 features**, definidas en **`feature_utils.py` (fuente única)**:
  los **7 de forma + `alpha_deg` + `reynolds`** (base) más **2 derivadas**:
  - **`alpha_over_sqrtre` = `alpha_deg / sqrt(reynolds)`** (término viscoso, ayuda
    en régimen de Reynolds bajo).
  - **`te_rel` = `trailing_edge_thickness_mm / chord_length_mm`** (espesor de TE
    relativo a la cuerda; señal fuerte en cuerda pequeña).
- **CRÍTICO:** entrenamiento (`eda_ml_filtrado150.py`, vía `add_derived`) e inversa
  (`inversa_ld_v2.py`, en `arma_X`, vía `f_alpha_over_sqrtre`/`f_te_rel`) calculan
  las derivadas con **las mismas funciones de `feature_utils.py`**. Si divergen, el
  modelo y la inversa dejan de casar. **No dupliques la fórmula: usa `feature_utils`.**
- Se adoptaron tras medir que **mejoran globalmente** (CD y LD: MAE −5/−7%, mejor
  R² y Spearman) y **no empeoran ninguna zona** (LD 150-200: 25%→23% de MAE/std).
  Diagnóstico previo: el error de 150-200 **no es ruido irreducible de XFOIL** (la
  consistencia de XFOIL ahí es como en 200-400), sino mejorable con features+datos.

### Elección de modelo por target: CL, CD y LD → XGBoost ✅ (CL corregido 2026-07-24)

- **Los tres targets usan XGBoost.** CL usaba **regresión lineal** hasta el
  2026-07-24. La corrección y su lección:
- **CL es lineal en el ángulo de ataque pero NO en el Reynolds.** La elección inicial
  de regresión lineal para CL se basó en la primera dimensión e ignoró la segunda,
  arrastrando un **sesgo sistemático del ~4.4%** (visible en el barrido de velocidad
  del perfil 0014: la recta predecía por debajo de los tres puntos de XFOIL).
- **Corregido pasando CL a XGBoost:** **MAE −62% (0.0595 → 0.0227)**, **R² 0.930 →
  0.984**, mejora en las **3 zonas de cuerda y los 8 ángulos**, sesgo del barrido
  **4.4% → 1.4%**. Modelo en `modelo_CL_xgb.joblib`; lineal archivado en
  `legacy/modelo_CL_lineal_legacy.joblib`. `eda_ml_filtrado150.py` ya entrena CL con
  XGBoost (mismos hiperparámetros que CD).
- **Lección:** un razonamiento físico correcto pero **incompleto** puede llevar a una
  decisión de modelado subóptima; **se detectó VISUALIZANDO, no analizando** (el
  barrido de velocidad lo hizo evidente). *Matiz honesto:* XGBoost elimina el sesgo
  (centra la predicción en los puntos), pero para un perfil concreto no captura la
  pequeña pendiente CL–Reynolds (la aplana); el error baja porque la variación de CL
  con la velocidad es diminuta (~0.03) y lo que dominaba era el offset, ahora corregido.

### Winner's curse en la inversa: penalización por incertidumbre ✅ resuelto

- **Problema detectado:** el optimizador de la inversa **se iba a rincones donde el
  modelo SOBREESTIMA**. Una batería de **8 casos** (3 zonas de cuerda × 3
  velocidades × 2 ángulos) verificados en XFOIL dio errores del **8% al 59%,
  SIEMPRE optimistas** (nunca conservadores), y **2 casos ni convergían** en XFOIL.
  Es el *winner's curse*: optimizar sobre un modelo con error **selecciona su mayor
  error positivo**. No es un fallo del modelo (su CV es sano), es de la
  **optimización**. Una sola verificación previa (8%) dio una imagen falsamente buena.
- **Solución:** penalizar la incertidumbre en la función objetivo:
  **`J(x) = mean_ensemble(x) + k · sigma(x)`** (se minimiza; `sigma>0` siempre suma,
  haciendo el punto menos atractivo donde el modelo duda).
- **sigma = ENSEMBLE BOOTSTRAP SOBRE PERFILES:** M=10 XGBoost entrenados cada uno
  sobre un remuestreo con reemplazo de los **`run_id`** (no de filas: remuestrear
  perfiles respeta la estructura de grupo). En zonas ralas el ajuste cambia mucho →
  **sigma alta**; en zonas densas → **sigma baja**. Mide incertidumbre **epistémica
  por escasez de datos**, que es justo lo que dispara el winner's curse.
  - *No usar "dispersión entre árboles" de XGBoost:* es **boosting**, no bagging —
    los árboles son correcciones secuenciales, no predictores independientes; su
    dispersión NO es incertidumbre. (En Random Forest sí valdría.)
  - El ensemble vive en **`ensemble_ld_sigma.joblib`** y la inversa lo **CARGA de
    disco**; entrenarlo tarda **~17 min**, así que **nunca se reentrena por llamada**.
    Si falta, regenerarlo una vez con `python winner_curse.py`.
- **k = 2 por defecto, configurable** como 2º argumento:
  `python inversa_ld_v2.py '{"chord_length_mm":450}' 1.5`
- **Validación (batería de 8 casos, k=2 vs k=0):**
  - Error medio **2.5% (rango 0-6%)** vs **~24% (rango 8-59%)** con k=0.
  - **Sesgo optimista eliminado**: pasa a levemente conservador (6 de 8 casos rinden
    algo mejor que lo prometido).
  - **8/8 convergen** en XFOIL (con k=0 solo 6/8): los rincones de sigma alta también
    eran geometrías raras que XFOIL no resolvía.
  - **No hay compromiso**: en los 8 casos el L/D REAL de la propuesta penalizada es
    **mejor** que el de k=0. Penalizar no cuesta rendimiento, lo gana (k=0 perseguía
    espejismos del modelo).
  - `k=1` es **insuficiente** (en el peor caso apenas bajaba sigma de 26.8 a 25.7).
- **⏳ Afinado pendiente OPCIONAL:** como k=2 queda *levemente conservador*, un
  **k≈1.5** podría arañar algo más de rendimiento real manteniendo el control. No es
  necesario; k=2 es el default seguro y validado.

### Ala 3D: `airfoil_3d.py` (paso OPCIONAL y aparte) — solo visual

- Script **independiente**: coge un CATPart **ya generado** (Part activo en CATIA),
  le añade un Geometrical Set `AIRFOIL 3D` con un Join y un Extrude en **dirección Y**
  (el plano del perfil es **ZX**), y guarda el CATPart. **No toca el pipeline de
  generación** (`airfoil_generator` / `pipeline_airfoil_api` / `generate_batch`).
- **Span por defecto = 900 mm**, configurable (`--span`). Rango real de referencia:
  **~600 mm (Formula Student) a ~1070 mm (F1 2026)**; ref. FIA 2026: el flap del
  alerón trasero no puede exceder **Y = 535 mm**.
- **⚠️ La extrusión es SOLO VISUAL.** La aerodinámica sale del **análisis XFOIL 2D**
  del perfil: el **span NO entra en ninguna predicción** (ni CL/CD/LD ni Reynolds —
  que se deriva de la **cuerda** y la velocidad). Cambiar el span no altera ningún
  resultado. El script lo avisa en su salida.
- **Qué es `LE ARC` realmente (medido, no supuesto):** pese a su nombre, **NO es un
  arco de morro ni una circunferencia sin recortar**. Es la **CURVA COMPLETA del
  perfil**: extradós + morro + intradós. Prueba numérica exacta (perfil de cuerda
  318 mm):
  ```
  UPR PROFILE (297.240) + mitad de LE CIRCLE (64.076) + LWR PROFILE (303.630)
                                                      = 664.946
  LE ARC medido                                       = 664.945   ✅
  ```
  Por eso mide ~665 mm (~2× la cuerda): **ya contiene** el extradós y el intradós.
- **El contorno CORRECTO para extruir es `LE ARC` + `TE PROFILE`** (los valores por
  defecto de `--curvas`): 664.945 + 2.087 = **667.03 mm**, con
  **perímetro/cuerda = 2.097** — exactamente el ratio típico de un perfil alar
  (~2.0-2.1). Es el contorno cerrado completo.
- **Por qué el join `AIRFOIL` NO sirve para extruir:** une
  `UPR + LE ARC + LWR + TE` = **1267.90 mm ≈ 2× el perímetro real**, porque
  **DUPLICA** extradós e intradós (están sueltos *y además* dentro de `LE ARC`).
  Esa **redundancia** (no una "curva gigante rara") es lo que CATIA rechaza. Ver
  limitación #4 arriba: no se corrige porque el join solo es un elemento de árbol
  y el `.dat` sale de la nube de puntos, no del join.
- **De dónde sale el `.dat`:** los 290 puntos `LE_xxx` se muestrean sobre `LE ARC`
  (= el perfil entero) y los 10 `TE_xxx` sobre `TE PROFILE`. Encaja con
  `N_LE = 290` / `N_TE = 10` de `asc_to_dat.py`. **El `.dat` está limpio**: se
  verificaron los 1.261 perfiles archivados y **0 tienen autointersección**.

### Limitaciones conocidas (documentadas, NO se corrigen)

#### 1. `te_rel` está confundido con la cuerda por construcción ⚠️ aceptado

- `trailing_edge_thickness_mm` se sortea en **mm ABSOLUTOS [1, 4]**, sin escalar con
  la cuerda. Al dividir por cuerdas de 150-500 mm, **`te_rel` es en buena parte un
  proxy del inverso de la cuerda**, no una señal de forma independiente.
- **Correlación cuerda vs `te_rel` = −0.662.** Las tres zonas son **casi disjuntas**
  (mediana de `te_rel`): **1.435% en 150-200** vs 0.812% en 200-400 vs **0.559% en
  400-500** — el p25 de la zona baja (1.000%) supera el p75 de la alta (0.717%). El
  histograma global es en realidad **tres distribuciones superpuestas**, una por zona.
- **Sin daño medido:** los casos 4 y 5 de la batería cayeron en el **p1-p2 GLOBAL** de
  `te_rel` (el borde de la nube en esa dimensión) y aun así verificaron con **4% y 0%
  de error**. La feature ayuda predictivamente aunque sea difícil de interpretar.
- **DECISIÓN: no se corrige.** Si en el futuro se generan datos nuevos, cambiar el
  muestreo del espesor de TE a **proporcional a la cuerda** (no en mm absolutos).

#### 0. ✅ RESUELTA — `trailing_edge_thickness_mm` ya llega a XFOIL (era el más serio)

> **RESUELTA (2026-07-24).** Se regeneró el dataset con el conversor **TE-real** y
> se promocionó a producción (ver bloque de actualización al inicio del documento).
> El diagnóstico de abajo explica **por qué** el corte amputado rompía el 7º
> parámetro; se conserva como evidencia. **Post-arreglo:** el TE real llega a XFOIL,
> pero el 7º parámetro **sigue siendo señal débil** — confirmado en dos datasets →
> es **restricción de fabricación** (mín. 1 mm), no variable aero (limitación 1).

> **Este era el hallazgo de fondo que explicaba las limitaciones 1 y 2.** El parámetro
> que creías estar controlando **llegaba al solver casi como ruido** (con el corte
> amputado, ya retirado en producción).

**El mecanismo (dos funciones de `asc_to_dat.py` encadenadas):**

1. **`order_le_chain_for_xfoil`** — constante **`0.03` hardcodeada**:
   ```python
   te_zone_idx = np.where(x > x_max - 0.03)[0]              # banda del 3% final
   te_upper_idx = te_zone_idx[argmax(pts[te_zone_idx, 1])]  # y MAXIMA de la banda
   te_lower_idx = te_zone_idx[argmin(pts[te_zone_idx, 1])]  # y MINIMA de la banda
   ```
   Los extremos de la cadena **NO son las esquinas reales del TE**: son los puntos de
   `y` máx/mín dentro de una banda arbitraria del **3% final de la cuerda**.
2. **`append_te_block_closure`** traza una **recta** entre esos dos puntos,
   **amputando ~2.3% de cuerda**. (De los 10 puntos `TE_xxx` de CATIA solo usa el
   **número**: `s_vals = np.linspace(0, 1, len(te))`; sus coordenadas se descartan.)

**Medido sobre 400 perfiles (detectando el bloque TE por espaciado uniforme, sin asumir 9 puntos):**
- **corr(gap, ancho del corte) = 0.918** ← lo que manda
- **corr(gap, `te_rel`) = 0.189** ← casi nula
- Banda del corte: mediana 0.0234, máx 0.0276 — **el 100% por debajo de 0.03** (la constante)
- **Un perfil con TE de 1.00 mm y otro de 3.99 mm acaban con el mismo gap: 0.0287 vs 0.0296.**

**Consecuencias (todo encaja):**
- **El espacio de diseño efectivo es de 6 parámetros, no 7.**
- **`te_rel` funciona como proxy de la cuerda** (r = −0.662), **no como física del TE** →
  ver limitación 1.
- **El optimizador satura `te_thickness` al mínimo sin coste** porque mover ese
  parámetro **apenas cambia lo que XFOIL ve** → ver limitación 2.
- Lo que XFOIL sí ve del TE es la **pendiente de aproximación** (`te_upr`/`te_lwr`)
  más un TE romo de tamaño casi constante (~0.029 de cuerda).

**DECISIÓN (histórica): no se corregía** por el coste de regenerar. ✅ **YA CORREGIDA
(2026-07-24):** se regeneró el dataset entero con TE-real y se revalidó la batería
(k=2 = 4.1%). **XFOIL admite TE romo** — se aprovechó justo eso. El muestreo del TE
sigue en mm absolutos (limitación 1), pero es irrelevante: el TE es restricción de
fabricación, no variable aero.

#### 2. El optimizador satura el mínimo de `trailing_edge_thickness_mm` ✅ no es un fallo

- En la batería k=2, **6 de 8 propuestas** salieron con `te_mm` ≈ **1.17-1.27 mm**,
  pegadas al **mínimo muestreado de 1.0 mm**. El optimizador quiere el borde de salida
  lo más fino posible (menos resistencia de base) — es físicamente correcto.
- El **óptimo aerodinámico está por DEBAJO del rango** muestreado, pero **1 mm es el
  límite de fabricación viable en composite**. Por tanto el corte del rango es una
  **restricción real de manufactura**, no una limitación del método ni del modelo.
- No hay nada que arreglar: bajar el mínimo daría perfiles no fabricables.

### Rangos de muestreo actuales

| Parámetro | Rango |
|---|---|
| `chord_length_mm` | **150 – 500** (soportado; `<150` excluido, ver arriba) |
| `leading_edge_angle_deg` | 3 – 10 |
| `leading_edge_thickness_level` | 0.2 – 1 |
| `trailing_edge_angle_deg` | 158 – 167 |
| `trailing_edge_thickness_mm` | 1 – 4 |
| `te_upr_angle_deg` | 5 – 15 |
| `te_lwr_angle_deg` | −8 – 4 |
| `chord_angle_deg` | **fijo = 350** |
| `alpha` (dataset) | **escalonado por velocidad:** 110→0…−10, 180→0…−12, 290→0…−14 |
| `velocidad` (dataset) | **110, 180, 290 km/h** (→ Reynolds por cuerda) |

## Fragilidad: el export ASC (Step 3)

- El paso **más frágil** del pipeline es el **export ASC**
  (`export_cloud_ascii.py`, Step 3): depende de **pywinauto y del foco de
  ventana** de CATIA.
- **NO tocar el ratón ni el teclado durante la ejecución de un lote**, y dejar
  CATIA en primer plano. La interferencia de input provoca fallos `error_catia`.

## Cómo lanzar las cosas

Requiere **CATIA abierto**. Durante un lote, no tocar ratón/teclado.

```bash
# Un solo perfil: el JSON exige user_params + VELOCIDAD(es); alphas opcional.
# El Reynolds NO se pasa: se DERIVA de cuerda + velocidad (ver nota abajo).
python pipeline_airfoil_api.py "{\"user_params\":{\"chord_length_mm\":365},\"velocidad_kmh\":180,\"alphas\":[-6]}"

# Varias velocidades en una sola llamada (geometría 1 vez, XFOIL por velocidad):
python pipeline_airfoil_api.py "{\"user_params\":{...},\"velocidad_kmh\":[110,180,290]}"

# Tanda aleatoria / Sobol / manual de N perfiles
python generate_batch.py --random N
python generate_batch.py --sobol N        # cobertura uniforme, secuencia continuable
python generate_batch.py --manual archivo.json
```

### Reynolds derivado también en el pipeline directo ✅ resuelto

- El **Reynolds es una cantidad DERIVADA**, nunca de entrada. Tanto el batch como
  el **pipeline directo** (`pipeline_airfoil_api.py`) lo calculan de la cuerda y la
  velocidad con la **misma** `compute_reynolds` de `generate_batch.py` (fuente
  única; el pipeline directo la importa de forma **perezosa** dentro de
  `run_pipeline` para evitar el import circular).
- El JSON del pipeline directo acepta **`velocidad_kmh`** (número o lista). Para
  cada velocidad imprime `[REYNOLDS] velocidad X km/h -> Reynolds calculado Y (con
  cuerda Z mm)` y re-corre XFOIL con ese Re (pasándolo a `run_xfoil.py` como 2º
  argumento). Devuelve `resultados_por_velocidad`.
- Si el JSON trae `reynolds`, se **ignora con un aviso pedagógico**. Si no hay
  ninguna velocidad, **falla con mensaje claro** (no asume nada).
- **Deuda técnica retirada:** ya NO hay Reynolds hardcodeado a 1e6 en el camino de
  pipeline. El `REYNOLDS = 1_000_000` de `run_xfoil.py` queda solo como fallback
  de uso standalone (`python run_xfoil.py "[-6]" "<Re>"` acepta Re como 2º arg).

## Archivos de respaldo

Existen copias `airfoil_dataset_legacy*.csv` como respaldo de datasets
anteriores (formatos previos). Solo backup; ignorarlos para el trabajo actual.

## Conteos del cierre del TE (correspondencia crítica)

- `asc_to_dat.py` usa **`N_LE = 290`** y **`N_TE = 10`**.
- Deben **coincidir** con los conteos de `airfoil_points.py` (LE: 290, TE: 10).
- **No cambiar estos valores sin verificar esa correspondencia** en ambos
  archivos.

---

# 📦 INVENTARIO DE ARCHIVOS

> Recorrido completo de la carpeta. **51 `.py`, 12 `.csv`, 40 `.json`, 2 `.joblib`,
> 9 `.png`, 1 `.md`** + `dataset_runs/` (1.293 carpetas), `eda_outputs/` (31 PNG),
> `__pycache__/`.
> Leyenda: ✅ **vivo** · 🟡 **extender** · 🔵 **diagnóstico (cumplió)** · ❌ **superado** · 🗑️ **basura**

## ✅ VIVO — Pipeline de generación (no tocar)

| Archivo | Qué hace | Estado |
|---|---|---|
| `pipeline_airfoil_api.py` | Orquestador CATIA→puntos→ASC→DAT→XFOIL→gráficas. Reynolds derivado, multi-velocidad | ✅ funciona |
| `airfoil_generator.py` | Step 1: perfil en CATIA (Geometrical Sets, plano ZX) | ✅ funciona |
| `airfoil_points.py` | Step 2: nube de puntos (LE 290, TE 10) | ✅ funciona |
| `export_cloud_ascii.py` | Step 3: export ASC (pywinauto + foco) | ✅ funciona ⚠️ frágil |
| `asc_to_dat.py` | Step 4: ASC→DAT, normaliza al sistema de cuerda | ✅ funciona (kink TE conocido) |
| `run_xfoil.py` | Step 5: XFOIL. alphas (argv1) + Reynolds (argv2) | ✅ funciona |
| `generate_batch.py` | Lotes: `--random`/`--sobol`/`--sobol-extremos`/`--manual`/`--dry-run` | ✅ funciona |
| `feature_utils.py` | Fuente única de las 11 features | ✅ **crítico** |

## ✅ VIVO — ML / Surrogates

| Archivo | Qué hace | Estado |
|---|---|---|
| `eda_ml_filtrado150.py` | **Entrenador de producción** CL/CD/LD (filtro ≥150). Guarda modelo + histórico | ✅ funciona |
| `winner_curse.py` | Entrena el ensemble de σ (bootstrap de perfiles, ~17 min) | ✅ funciona |
| `ml_history.json` / `ml_history.csv` | Histórico de reentrenos (9 entradas) | ✅ datos |
| `modelo_LD_inversa_xgb.joblib` (8 MB) | Modelo de producción, 11 features | ✅ artefacto |
| `ensemble_ld_sigma.joblib` (**64 MB**) | Ensemble de incertidumbre | ✅ artefacto ⚠️ pesa |
| `modelo_LD_inversa_meta.json` | Metadatos del modelo | ✅ datos |

## ✅ VIVO — Inversa

| Archivo | Qué hace | Estado |
|---|---|---|
| `inversa_ld_v2.py` | **Producción**: zona fiable, avisos graduados, `J = mean_ens + k·σ` (k=2 configurable) | ✅ funciona |
| `inversa_bateria.py` | Genera la batería de 8 propuestas (k=0) | ✅ funciona |
| `bateria_k2.py` | Genera la batería de 8 propuestas (k=2) | ✅ funciona |
| `bateria_verificar.py` / `bateria_k2_verificar.py` | Generan las 8 en CATIA/XFOIL y comparan | ✅ funciona |
| `bateria_resultados.json` / `bateria_k2_resultados.json` | **Evidencia**: predicho/real/σ de k=0 y k=2 | ✅ **datos de las gráficas de proyecto** |
| `bateria_index.json` / `bateria_k2_index.json` | Índices de la batería | ✅ datos |
| `bat_*.json` (8) / `k2_*.json` (8) | Propuestas concretas de cada caso | 🟡 conservar (evidencia) |

## 🟡 VISUALIZACIÓN — el foco de lo que viene

| Archivo | Qué hace | Veredicto |
|---|---|---|
| `plot_perfil.py` | Forma del perfil, 1:1 real, desde `.dat` o `--run-id` | ✅ **sirve tal cual** |
| `cp_on_demand.py` | Cp a demanda (run_id + velocidad + ángulo), Re real, **orden de arco** | ✅ **sirve tal cual** |
| `eda_velocidad.py` | L/D vs α con las **3 velocidades** superpuestas | 🟡 **extender**: falta CL y CD |
| `plot_polar.py` | Step 6: CL-α, CD-α, CL-CD, L/D-α, CM-α | 🟡 **extender**: solo UNA velocidad |
| `plot_cp.py` | Step 7: Cp estilo XFOIL | ❌ **no usar**: bug de la mediana de y (zigzag) |
| `airfoil_3d.py` | Ala 3D por extrude. Span 900 mm. Solo visual | ✅ funciona (aparte) |

## 🔵 DIAGNÓSTICO — cumplieron su función (trazabilidad)

`diag_zigzag.py`, `diag_zigzag_vel.py`, `diag_xfoil_native.py`, `diag_ps_render.py`,
`diag_timing.py`, `diag_zona_baja.py`, `diag_d1_consistencia.py`,
`diag_features_global.py`, `diag_autointerseccion.py`, `eda_explore.py`,
`eda_corr.py`, `eda_optimo_290.py`, `run_alphas_robusto.py`.

Todos **funcionan** y documentan **por qué el proyecto es como es**. No son basura:
son la evidencia de las decisiones. Candidatos a una carpeta `diagnostics/`.

## ❌ SUPERADOS — fases pasadas del ML

| Archivo | Por qué está superado |
|---|---|
| `ml_model_cl.py` | Primer modelo: solo 7 params de forma (sin alpha/reynolds) |
| `eda_ml_full.py`, `eda_ml_ld.py`, `eda_ml_cd.py` | Modelos por objetivo, pre-XGBoost |
| `eda_ml_retrain142.py`, `eda_ml_sobol_n300.py`, `eda_ml_sobol_n400.py` | Reentrenos de hitos concretos |
| `eda_ml_sobol_vs_random.py` | Comparativa de muestreo (ya concluida) |
| `eda_ml_ld_inverse.py`, `eda_ml_rank_xgb.py`, `eda_ml_extendido.py` | Iteraciones previas al entrenador actual |
| `eda_ld_importancias.py` | ⚠️ **ROMPERÍA**: espera 9 features, el modelo tiene 11 |
| `inversa_ld.py` | Inversa v1, sin restricción (el fallo del 74%) |
| `test_pipeline_json.py` | ⚠️ **ROTO**: pasa config sin `velocidad_kmh` → falla con el pipeline actual |

## 🔴 EXPORT / BI — era MVP, superado

| Archivo | Qué hace exactamente | Estado |
|---|---|---|
| `export_powerbi_data.py` (12-may) | Lee **solo** `polar_v4_auto.txt` + `cp_alpha_*.txt`. **Hardcodea** `RUN_ID="run_001"`, `chord=250`, `reynolds=1000000`. **No conoce el dataset** | ❌ **no reutilizable** |
| `open_powerbi_dashboard.py` (13-may) | Lanzador: ejecuta el export y abre el `.pbix`. Ruta absoluta hardcodeada | 🟡 solo lanzador |
| `airfoil_dashboard.pbix` (54 KB) | Dashboard Power BI | ❓ **binario, no inspeccionable** sin abrir Power BI |
| `powerbi_results_summary.csv` | **7 filas**, 1 perfil, Re=1e6, alphas −8…+4 (rango antiguo con positivos) | 🗑️ obsoleto (13-may) |
| `powerbi_cp_summary.csv` | 1.121 filas de (x,y,Cp) de un perfil | 🗑️ obsoleto (13-may) |

**Veredicto:** la capa BI es de la era MVP (**1 perfil × 7 ángulos**) frente al dataset
actual (**989 perfiles × 21 condiciones**). La forma del dato es incompatible:
**rehacer desde `airfoil_dataset.csv` sale más rápido que adaptarlo.** El `.pbix`
puede servir como referencia de layout si al abrirlo gusta.

## 🗑️ BASURA

| Qué | Cantidad | Nota |
|---|---|---|
| `*.log` (`diag_*`, `batch_run*`, `pipeline_*`, `xfoil_*`) | ~30 (~1 MB) | Logs de corridas viejas |
| `__pycache__/` | — | Gitignore |
| `airfoil_v4_OLD.dat`, `airfoil_points_xyz.csv` | 2 | Restos |
| `_prop180.json`, `_prop450.json`, `_new180.json`, `_new450.json` | 4 | Temporales |
| `powerbi_*_summary.csv` | 2 | Obsoletos (mayo) |
| `inversa_propuesta_*.json`, `inversa_v2_*.json`, `verif_new*.json`, `inversa_chord*.json` | ~8 | Regenerables |

## 🟡 DATOS — conservar

- **`airfoil_dataset.csv`** (3.7 MB): **TE-real — 969 perfiles / 20.349 filas / 16.526 ok** (conv. 81.2%). El activo central. El viejo amputado (989/20.769/15.107) está en `legacy/airfoil_dataset_amputado_legacy.csv`.
- **`dataset_runs/`** (1.293 carpetas): `.dat` + `.asc` + polar por perfil. ⚠️ Enorme para GitHub.
- **CSV legacy** (7): `legacy`, `legacy_semicolon`, `alpha0`, `multialpha`, `18cond`,
  `alphas_3-6-9-12`, `prueba_reynolds90`. Archivar; AGENTS.md dice **no borrar**.
- **`eda_outputs/`** (31 PNG): gráficas de diagnóstico y EDA ya generadas.
- **`ala_3d.CATPart`**: primer ala 3D generada.

## Utilidades / API

| Archivo | Estado |
|---|---|
| `flask_airfoil_api.py` | ⭐ **API REST ya montada**: `/health` + `POST /generate_airfoil` → `run_pipeline`. **Base del backend de la UI futura**. ⚠️ sin probar desde el refactor del Reynolds (el JSON debe incluir `velocidad_kmh`) |

---

## ✅ Lo que YA TIENES (aunque no lo recuerdes)

1. **API REST montada** (`flask_airfoil_api.py`) — el backend de la UI ya existe.
2. **Cp a demanda resuelto y correcto** (`cp_on_demand.py`) — pieza 3 de la ficha visual, hecha.
3. **Polar multi-velocidad de L/D** — `eda_velocidad.py` ya la genera
   (`eda_outputs/LD_vs_alpha_por_velocidad.png`). Faltan CL y CD.
4. **Gráficas predicho-vs-real** — ya existen en `eda_outputs/pred_vs_real_*.png` (modelos antiguos).
5. **Los datos de las gráficas de proyecto** — `bateria_resultados.json` (k=0) y
   `bateria_k2_resultados.json` (k=2) contienen predicho, real y σ. **Solo falta dibujarlos.**
6. **Histórico de ML** (`ml_history.json`, 9 reentrenos) — listo para una gráfica de evolución.
7. **Un dashboard Power BI** (`airfoil_dashboard.pbix`) — aunque sus fuentes estén obsoletas.

## ❌ Lo que FALTA de verdad

| Necesidad | Estado | Esfuerzo |
|---|---|---|
| Polar multi-velocidad **con CL y CD** | Parcial (solo LD) | 🟢 bajo — extender `eda_velocidad.py` |
| **Compositor de ficha visual** (forma + polares + Cp en una lámina) | ❌ no existe | 🟡 medio |
| **Gráficas de proyecto** (pred-vs-real batería, k=0 vs k=2) | Datos ✅ / gráficas ❌ | 🟢 bajo |
| **Capa SQL** | ❌ nada: sin BD, sin esquema, sin ETL | 🟡 medio |
| **Power BI sobre el dataset real** | ❌ rehacer desde cero | 🟡 medio |
| **GitHub** | ❌ **sin `.git`, `.gitignore`, `README`, `requirements.txt`** | 🟢 bajo |
| **UI** | Backend ✅ / front ❌ | 🔴 alto |

### ⚠️ Aviso para GitHub (antes del primer commit)

- **`ensemble_ld_sigma.joblib` pesa 64 MB** (aviso de GitHub a 50 MB, límite duro 100 MB).
- **`dataset_runs/` tiene 1.293 carpetas**.
- Hace falta un **`.gitignore` bien pensado** (y quizá Git LFS, o **regenerar** el
  ensemble con `winner_curse.py` en vez de versionarlo) **antes** del primer commit.
  Si no, el repo nace envenenado.
