# CLAUDE.md — Contexto del proyecto

Notas de contexto para futuras sesiones. Pipeline de **generación y análisis
de perfiles alares**: CATIA (geometría) → puntos → ASC → DAT → XFOIL (polar) →
gráficas, orquestado por `pipeline_airfoil_api.py`.

---

## 🗺️ MAPA RÁPIDO: los 4 bloques del proyecto

> Estado global: **núcleo técnico CERRADO y densificado**. Datos, surrogates e inversa
> validada a ~2.8% de error; capa de presentación hecha (dashboard de 5 vistas);
> **entrega CAD hecha** (`.dat`/`.csv`/`.step`, el STEP validado en CATIA); **proyecto
> portable, empaquetado en Docker y publicado en GitHub**.
> Lo que queda NO es técnico: **README, desplegar de verdad y contarlo**.
> Inventario completo de la carpeta: ver **"Inventario de archivos"** al final.

> ## 🟢 ACTUALIZACIÓN (2026-08-08): ENTREGA CAD, EMPAQUETADO Y REPO PÚBLICO
>
> **El núcleo no se ha tocado.** Todo lo de esta tanda es capa de entrega: sacar la
> geometría al mundo real (CAD), pulir lo que se malinterpretaba, hacer el proyecto
> portable y dejarlo listo para desplegar. Detalle en las secciones **"La capa de
> entrega CAD"**, **"La ronda de QA"**, **"Portabilidad y despliegue"** más abajo.
>
> - **Exportación en 3 formatos** desde Results: `.dat` (análisis), `.csv` (mm reales)
>   y **`.step`** (curva CAD nativa), los tres de la MISMA geometría TE-real.
>   El STEP está **validado abriéndolo en CATIA de verdad**, no solo por estructura.
> - **Nombres con parámetros**: `Suzuka_300mm_180kmh.step`, misma receta que la
>   leyenda, con saneado por lista blanca probado contra entradas hostiles.
> - **Circuitos: de 42 a 61**, con 11 reclasificados de nivel y sus notas reescritas.
> - **Portabilidad**: `rutas.py` como fuente única (adiós a las 7 copias de la ruta de
>   XFOIL y a `C:\Users\MSI-06\...`), y **modo web** que degrada sin romperse cuando
>   no hay XFOIL.
> - **Empaquetado**: `Dockerfile` con XFOIL de `apt`, `requirements.txt` fijado, y el
>   ensemble de 106 MB **regenerado en el build** — la vía gratis al límite de GitHub.
> - **Proyecto en GitHub, público**: `ce18a00`, 1.706 ficheros, 43,8 MB, **0 secretos
>   verificados leyendo el contenido del commit**, no el árbol de trabajo.
>
> ⚠️ **El cabo suelto del ensemble de 111 MB está RESUELTO** (ver abajo): ya no
> bloquea nada.

> ## 🟢 ACTUALIZACIÓN (2026-08-06): DATASET DENSIFICADO Y MODELOS EN PRODUCCIÓN
>
> **Segunda promoción a producción del proyecto** (la primera fue TE-real, ver abajo).
> Se densificó el dataset en **velocidad y ángulo** sobre las geometrías que ya existían,
> se reentrenaron los modelos, se revalidó la batería de 40 casos en CATIA+XFOIL y se
> promocionó. Detalle completo en las secciones **"La densificación"**, **"Lo que enseñó
> la batería densif"** y **"La promoción"** más abajo; aquí solo el titular:
>
> - **Dataset densificado** (`airfoil_dataset_densif_merged.csv`): **75.101 filas**,
>   63.840 ok, 944 perfiles, **6 velocidades** (110/150/180/220/250/290) y **paso de 1°**
>   en ángulo (pares E impares). Casi **4× los datos convergidos** del anterior.
> - **Modelos de producción** = los densif (mismos nombres, mismo protocolo, 11 features).
>   LD MAE 2.333 → **2.156** en las condiciones originales; −33.8% en todas.
> - **Batería revalidada (40 casos, CATIA+XFOIL): k=2 = 2.8%** (julio 3.8%) y
>   **k=0 = 6.9%** (julio 21.5%). El hallazgo NO es que k=2 aguante, sino que
>   **densificar encoge el winner's curse en la base**. Ver la sección dedicada.
> - **`airfoil_dataset.csv` NO se promocionó** (sigue en 20.349 filas / 3 velocidades):
>   es el **catálogo de mediciones** contra el que se calcula el percentil. Los bounds
>   p5-p95 se verificaron **idénticos** (0.00%), así que la inversa no se entera.
> - **Modelos viejos en `legacy/pre_densif_20260806/`** con md5 verificado; reversión
>   en 10 s copiando 5 ficheros, sin tocar código. Ver `PROMOCION.md` en la raíz.
> - ⚠️ **`ensemble_ld_sigma.joblib` pesa ahora 111 MB** y supera el límite DURO de
>   GitHub. Bloquea el primer push hasta resolverlo (ver "Aviso para GitHub").

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
> - **Batería revalidada y AMPLIADA a 40 casos** (geometrías TE-real en CATIA+XFOIL):
>   **k=0 = 21.5%**, **k=2 = 3.8%** — factor de reducción **5.7×**. Con la tanda inicial
>   de 20 salía 23.9% / 4.1%: al doblar la muestra los números apenas se movieron, que
>   es justo lo que se quería ver (la conclusión no dependía de una muestra pequeña).
>   **Test de signos: en 36 de 38 casos convergidos el L/D real rinde PEOR que la
>   predicción k=0** (p < 10⁻⁷) → el sesgo optimista es estadísticamente aplastante,
>   no ruido. Por zona de cuerda, k=0 empeora donde el modelo está más seguro-pero-
>   equivocado (400-500 mm: 27.3%) y k=2 aguanta en las tres (3.6% / 2.1% / 6.6%).
> - **`te_thickness` es RESTRICCIÓN DE FABRICACIÓN, no variable aerodinámica**
>   (confirmado en DOS datasets): al regenerar con TE-real su señal **NO subió**,
>   bajó (importancia LD de `te_rel` 4.7%→1.4%). El 7º parámetro no "se reconecta"
>   porque el óptimo aero está por debajo del mínimo fabricable de 1 mm (composite).
> - **Universo viejo archivado en `legacy/`** (`*_amputado_legacy.*`): dataset +
>   modelos + ensemble + meta. Nada borrado; reversible. Copias `*_tereal.*` también
>   conservadas en la raíz como referencia.
> - Inversa (`inversa_ld_v2.py`) verificada con los modelos nuevos: carga OK,
>   11 features OK, DE converge.

---

## 🧪 LA DENSIFICACIÓN (2026-08) — más velocidades y ángulos, SIN CATIA

### Por qué se hizo

Dos huecos del muestreo original se habían vuelto visibles al construir el dashboard:

1. **El hueco 180-290 km/h.** Con solo 3 velocidades, entre 180 y 290 había 110 km/h sin
   un solo dato — y ahí es donde vive el uso real. Se midió: **σ se disparaba a 1.34 a
   250 km/h** frente a 0.46 a 180, tanto que saltaba la caja de "alta incertidumbre" en
   una velocidad perfectamente normal para un coche.
2. **El escalonado de 2° en el ángulo.** El dataset barría **solo ángulos pares**, así
   que el surrogate tenía resolución efectiva de ~2°: los impares heredaban el escalón
   del árbol. Medido a paso 0.5°, `|L/D|` era literalmente idéntico entre 0.5° y 1.0°
   (mismo leaf), y los impares puntuaban **sistemáticamente por encima** del par
   siguiente (en los 6 pares comprobados). Eso obligaba a presentar el ángulo
   recomendado como franja y hacía que saltara de forma no monótona con la velocidad
   (9° a 250 km/h, 7° a 300).

### Cómo se hizo: sin tocar CATIA

**La clave de que fuera barato.** No hacían falta geometrías nuevas: los 944 perfiles ya
existían y su `.asc` estaba archivado en `dataset_runs/`. Se regeneró el `.dat` TE-real
desde el `.asc` y se relanzó **solo XFOIL** a las velocidades y ángulos nuevos.
**3 h 20 min de cómputo portable**, cero minutos de portátil con CATIA.

- Script: **`densificar.py`** (reanudable por par `(run_id, velocidad)`).
- Reutiliza `piloto_tereal.genera_tereal` + `xfoil_sweep`, el harness ya validado en la
  regeneración TE-real. La lógica de verificación no se reimplementó.
- Salida a CSV aparte, fusionada después con **`fusionar_densif.py`**.

> ### ⚠️ EL ERROR QUE CASI ENVENENA LA TIRADA (leer antes de reusar `dataset_runs/`)
>
> El primer intento usó el **`.dat` archivado** en `dataset_runs/<run_id>/airfoil_v4.dat`.
> Es de **JUNIO: la geometría TE-AMPUTADO**. Cuando en julio se regeneró todo con el
> conversor TE-real, **esos `.dat` del archivo nunca se reescribieron** — solo el CSV.
>
> Medido a 110 km/h sobre ángulos pares y con la misma marcha que producción:
> ```
> |CL − prod| con .dat ARCHIVADO (junio, amputado): media 0.09690  max 0.18440
> |CL − prod| con .dat TE-REAL del .asc          : media 0.00227  max 0.03280
> ```
> **10-20% de desfase en CL**, suficiente para estropear el modelo y lo bastante
> pequeño para no saltar a la vista. Lo delató la prueba de 10 perfiles: coherencia
> física del 48% (un ángulo impar debe caer entre sus vecinos pares) y convergencia
> 76.9%. Con TE-real: **98.3% y 82.4%**.
>
> **Regla: en `dataset_runs/` el `.asc` es la fuente de verdad, el `.dat` NO.**

### Qué salió

| | producción (antes) | densificado |
|---|---|---|
| Filas | 20.349 | **75.101** |
| Filas `ok` | 16.526 | **63.840** (×3.86) |
| Perfiles | 969 | 944 (los de cuerda ≥150 con `.asc`) |
| Velocidades | 110 / 180 / 290 | **110 / 150 / 180 / 220 / 250 / 290** |
| Paso angular | 2° (solo pares) | **1° (pares e impares)** |
| Reynolds únicos `ok` | 2.845 | **5.633** |

**Convergencia mejor en las 3 velocidades que ya existían** (+3.0 a +4.6 pp): el barrido
de paso 1° marcha la polar en saltos más pequeños, así que XFOIL parte de una solución
más cercana en cada ángulo. Las nuevas caen justo donde deben por interpolación.

### Trazabilidad permanente

Las filas nuevas llevan el sufijo **`_densif`** en `source` (`sobol` → `sobol_densif`).
Se eligió sufijar en vez de añadir una columna para que el CSV mantenga las **mismas 19
columnas** y la fusión sea un `concat` directo:

```python
merged[merged.source.str.endswith("_densif")]      # solo densificación
merged[~merged.source.str.endswith("_densif")]     # solo el original
```

⚠️ Efecto lateral conocido: `eda_ml_filtrado150.py` arma un dataset de contraste con
`source.isin(["random","sobol"])`; con el sufijo estas filas quedan fuera de **ese
contraste histórico**, no del entrenamiento real (que filtra por cuerda). Es lo deseado.

---

## 🏆 LO QUE ENSEÑÓ LA BATERÍA DENSIF — el winner's curse se encoge en la base

> **Este es el hallazgo metodológico de la densificación, no un número suelto.**

Se revalidaron los **40 casos** de la batería con los modelos densif: misma receta, mismas
cuerdas/velocidades/ángulos (leídos del propio `bateria_tereal_k0_resultados.json` para
que fuese imposible que derivaran), mismo optimizador, 80 geometrías en CATIA+XFOIL.

```
                          JULIO      DENSIF     cambio
   error medio k=0        21.5%       6.9%     -14.6 pp
   error medio k=2         3.8%       2.8%      -1.0 pp
   factor k0/k2            5.7x       2.4x
   test de signos        36/38      33/37      (sigue aplastante)
```
*(el k=2 densif es el de DESPUES de corregir el caso 10; sin corregir salia 3.7% — ver
"El caso 10" mas abajo)*

**La hipótesis previa era la equivocada, y merece la pena registrarlo.** Se esperaba que
σ un 40% menor debilitara la penalización `k·σ` y disparara el error de k=2 — la
separación entre las propuestas k=0 y k=2 se había reducido a la mitad (6.67 → 3.33 de
|L/D|). **No pasó:** k=2 se queda en **2.8%** frente al 3.8% de julio — mejora, no empeora.

**Lo que sí cambió: k=0 se desploma de 21.5% a 6.9%.** El winner's curse no desaparece
—el test de signos sigue siendo aplastante, 33 de 37 casos rinden peor que lo prometido—
pero es **tres veces más pequeño**.

> **El principio:** el winner's curse no es una propiedad fija del método, es el
> **precio de los rincones de baja evidencia**. Optimizar sobre un modelo con error
> selecciona su mayor error positivo; si densificas donde el modelo tenía poca evidencia,
> esos rincones dejan de existir y **la maldición se encoge sola**. Densificar bien no
> solo mejora la precisión media: ataca el sesgo en su origen.

**⚠️ Cómo NO leer el factor 2.4×.** Baja de 5.7× a 2.4× **porque k=0 mejoró, no porque
k=2 empeorara** (k=2 también bajó, de 3.8% a 2.8%). Leerlo como degradación sería justo al
revés de lo que pasó. Es el recordatorio de que un ratio puede moverse por el denominador
o por el numerador, y aquí se movió por el bueno.

**Robustez:** mediana de k=2 **2.41%**, máximo **12.2%**. Tras corregir el caso 10 no queda
ningún error que descoloque la media.

---

## 🔍 EL CASO 10 — un artefacto de XFOIL cazado por olerse un número imposible

> **Otro eslabón del hilo conductor del proyecto**: casi todos los bugs serios de aquí
> los ha cazado la verificación, no el código. El kink del TE, el `.dat` amputado de
> `dataset_runs/`, el CL lineal… y este. El patrón se repite: **un número que no
> encaja, la tentación de aceptarlo porque "los datos son los datos", y la decisión de
> verificarlo antes de creerlo.**

**El síntoma.** En la batería densif, el caso 10 (cuerda **250 mm**, **290 km/h**, **−8°**)
daba 34.4% de error en k=2, con el resto entre 0 y 12%. Y en la dirección "buena": el
perfil rendía *mejor* que lo prometido (real −101.30 vs −66.42 predicho). Era tentador
dejarlo como "un error grande pero seguro".

**La prueba que lo delató: el valor depende del CAMINO DE MARCHA de XFOIL.**

```
alpha unico (lo que hace la bateria) : |L/D| = 101.30   CD = 0.01381
marcha paso 2 (0,-2,...,-8)          : |L/D| = 101.30
marcha paso 1 (0,-1,...,-8)          : |L/D| =  66.52   CD = 0.02162
```

Con marcha fina el punto encaja en una curva perfectamente suave
(−6: 67.1 · −7: 65.0 · **−8: 66.5** · −9: 66.3 · −10: 68.2). Con marcha gruesa, XFOIL
aterriza en una capa límite optimista con el **CD un 36% menor**. Es determinista (dos
corridas dan 101.30 exacto), así que no es ruido: es una **rama espuria**.

**Tres verificaciones más, todas negativas para el dato:**
- **Físicamente imposible:** de 160 perfiles reales medidos en esa ventana (250 mm ±15%,
  290 km/h, −8°) el máximo es **97.5**. Ninguno llega a 101.30.
- **Emparejamiento correcto:** el JSON, el nombre del fichero y el `.dat` estrella
  cuadran. No hubo cruce de casos.
- **No está en un borde:** 0 de 7 parámetros pegados a p5-p95.

**Y es el ÚNICO.** Se comprobaron los 38 casos convergidos con las tres marchas: en 37 el
resultado es **idéntico bit a bit**. El método de verificación es sólido; esto es un caso
patológico aislado, no un fallo sistemático.

**Corregido a −66.52**, con el original **conservado** en el propio JSON
(`LD_real_original`, `correccion`, `correccion_fecha`), copia en
`bateria_densif_k2_resultados.json.pre_caso10.bak`. El caso pasa de 34.4% a **0.15%** de
error, y la batería de 3.73% a **2.83%** con el máximo bajando de 34.4% a 12.2%.

> **La lección, que vale para el próximo dato raro:** un valor atípico *a favor* es tan
> sospechoso como uno en contra. Aquí lo único que separaba "hallazgo" de "artefacto" era
> preguntarse si el número era **físicamente posible** y volver a medirlo cambiando algo
> que no debería importar. El camino de marcha no debería cambiar el resultado; que lo
> cambiara era la prueba.

---

## 📐 LA CAPA DE ENTREGA CAD — tres formatos, una sola geometría

> Hasta aquí el proyecto terminaba en un `.dat` normalizado. El usuario tenía que
> escalarlo y reconstruir un spline a mano en su CAD. Esta sección cierra ese hueco.

### Los tres formatos y para qué es cada uno

| fichero | contenido | para qué |
|---|---|---|
| `.dat` | x/c, y/c **normalizados**, 318 puntos | XFOIL y cualquier herramienta de análisis |
| `.csv` | `x_mm, y_mm, z_mm` con **z = 0**, mm reales | importar la nube a escala, hoja de cálculo |
| `.step` | curva CAD nativa (ISO 10303-21, AP214) | abrir y extruir directamente en el CAD |

**Los tres describen el MISMO perfil, y eso es estructural, no una coincidencia que
haya que vigilar.** La cadena es `.dat → .csv → .step`: cada eslabón **lee los números
del anterior** en vez de recalcular la geometría. `gen_csv_optimo` escala el `.dat`
cacheado; `gen_step_optimo` lee ese CSV. Todos salen de la misma geometría TE-real y
del mismo hash de los 7 parámetros.

> ⚠️ **318 puntos, y NO hay ningún punto de TE duplicado que quitar.** El `.dat` y el
> `.csv` tienen exactamente los mismos 318. Lo que sí duplica el primer punto al final
> son las **siluetas de Compare**, porque Plotly necesita cerrar el trazo para dibujar —
> pero eso es de la gráfica, no de los ficheros. El contorno se entrega **abierto**: la
> separación entre el primer y el último punto ES el espesor del TE romo (medido 1,9498
> mm frente a 1,95 nominal), que es el convenio estándar de TE romo en XFOIL.

### El ángulo NO va en la geometría

Los tres ficheros salen **a 0°, alineados con la cuerda**. Es el formato estándar de
perfiles y además lo único coherente con el proyecto: aquí el ángulo de ataque lo
aplica **XFOIL**, nunca la geometría (`project_to_chord_system` neutraliza cualquier
rotación, ver más arriba).

Hay una nota en Results, junto a los botones, que lo dice e **inserta dinámicamente el
ángulo recomendado del diseño** — tomado de la **franja**, no del punto suelto, para que
diga lo mismo que el KPI de arriba.

> **Por qué la nota NO nombra un eje.** El borrador decía *"rotate about the Z axis"*.
> Habría sido falso para uno de los tres ficheros: el `.step` va en el plano **XZ**
> (giro sobre Y) y el `.csv` en **XY** (giro sobre Z). Se dejó en *"rotate the profile
> in its own plane"*, cierto para los tres. **No "mejorar" la frase metiendo el eje.**

### El plano del STEP es XZ, y es a propósito

Cuerda en X, espesor en Z, **envergadura libre en Y**: la misma convención que
`airfoil_generator` usa al construir el perfil en CATIA (plano ZX) y que espera
`airfoil_3d`, que extruye en dirección Y. Nació en XY y se cambió: con el perfil en un
plano distinto al de la geometría nativa, comparar o combinar ambas obligaba a rotar.

---

## 🕳️ EL STEP QUE SE IMPORTABA "BIEN" Y DEJABA LA PIEZA VACÍA

> **Cuarto eslabón del hilo conductor**, y el más incómodo de los cuatro. El kink del TE,
> el `.dat` amputado de `dataset_runs/`, el CL lineal, el caso 10 — y ahora este. El
> patrón vuelve a ser el mismo: **una comprobación que pasa y no demuestra lo que dice
> demostrar.**

Se escribió el STEP en **Python puro** (sin OpenCASCADE ni cadquery: solo `numpy` y
`scipy`, que ya eran dependencias). Se validó con un parser propio: estructura ISO
correcta, cero referencias colgantes, regla de cardinalidad de la B-spline cumplida,
unidades en milímetros. **Todo pasaba. Y CATIA abría el fichero y no mostraba nada.**

Tres fallos apilados en la misma línea, que fueron apareciendo al arreglar el anterior:

1. **Entidad compleja inventada**: se fusionó el *contexto* con la *representación*
   (`GEOMETRIC_REPRESENTATION_CONTEXT + ... + REPRESENTATION`). No existe en el esquema.
2. **El nombre correcto lleva `SHAPE` en medio**: es
   `GEOMETRICALLY_BOUNDED_WIREFRAME_**SHAPE**_REPRESENTATION`. El error anterior tapaba este.
3. **La "alternativa segura" era la peor.** Se escribió una variante con
   `SHAPE_REPRESENTATION` a secas, razonando que es la representación más básica de todo
   STEP y por tanto la más compatible. **Era exactamente al revés.**

> ### La lección: valid ≠ importado
>
> ```
> variante wireframe : entra en CATIA como Geometrical Set con la curva dentro.  ✅
> variante shape     : .err COMPLETAMENTE LIMPIO, cero errores de esquema,
>                      y "[0556] There is Nothing to import: the Output Part may
>                      be empty". Pieza VACÍA.                                    ❌
> ```
>
> La entidad genérica **falla en silencio**: CATIA la lee sin quejarse y luego ignora la
> curva, porque no reconoce una curva suelta como geometría importable. La específica
> —la que declara "esto es geometría de alambre"— es la que el lector sabe dónde
> colocar. **Un informe de importación limpio no significa que se haya importado nada.**
>
> La variante `"shape"` **se conserva en `step_export.py` marcada `*** NO USAR ***`**,
> con el resultado del experimento escrito al lado, para que nadie la active pensando
> que es la opción prudente.

**Lo que resolvió los tres fallos no fue mi validador: fue el `.err` de CATIA**, que da
número de instancia y diagnóstico exactos. Está en
`C:\Users\<user>\AppData\Local\DassaultSystemes\CATReport\<fichero>.err`. **Si un STEP
no aparece, ir ahí antes que a cualquier hipótesis.**

Y el validador se endureció: ahora comprueba que **toda entidad compleja sea una
combinación legal conocida**, y marca de inmediato cualquiera que mezcle un `*_CONTEXT`
con una `*_REPRESENTATION` — que es justo lo que dejó pasar la primera vez.

### Un cuarto fallo, de proceso: el servidor con el código viejo en memoria

Tras arreglar el escritor, el botón del dashboard **seguía sirviendo ficheros rotos**.
No era el código: era que se editó `step_export.py` tres veces y **nunca se reinició el
Flask**. Python cachea los módulos importados durante toda la vida del proceso, así que
el servidor siguió escribiendo con la versión original. En el caché convivían el fichero
bueno (regenerado a mano desde un proceso nuevo) y los que el servidor había escrito.

Peor: había **dos procesos de dashboard vivos** y se despacharon como "no molestan".
Eran exactamente la pista.

**Arreglo estructural:** el caché del STEP lleva ahora la **versión del escritor en el
nombre** (`<hash>.v2.step`, constante `FORMATO` en `step_export.py`). Indexar solo por el
hash de la geometría hacía que un fichero escrito por una versión anterior se sirviera
como bueno para siempre. **Al cambiar el escritor, subir `FORMATO`.**

---

## 🏷️ NOMBRES DE FICHERO CON LOS PARÁMETROS DEL DISEÑO

Las descargas salen como **`Suzuka_300mm_180kmh.step`** en vez de
`your_optimal_airfoil.step`, con la **misma receta que la leyenda y el guardado**
(circuito o nivel + cuerda + velocidad). No se reimplementó en paralelo: hay una función
`nombreFichero()` y un comentario diciendo que si los dos nombres divergieran, el fichero
en disco dejaría de poder emparejarse con el diseño guardado. Los acentos se normalizan
antes de sanear, así que **Mónaco → `Monaco`**, no `M_naco`.

La velocidad va incluida por la misma razón que en el guardado: el mismo circuito y la
misma cuerda a 180 o a 250 km/h son diseños distintos, y sin ella dos descargas se
pisarían en la carpeta.

> ### El saneado es por LISTA BLANCA, y no es paranoia decorativa
>
> El nombre lo manda el cliente en la URL (`?n=`) y **acaba en la cabecera
> `Content-Disposition`**. Eso lo convierte en una vía de inyección de cabeceras y de
> travesía de rutas. Por eso solo sobreviven letras, dígitos, punto, guion y guion bajo,
> y **la extensión la pone SIEMPRE el servidor**. Probado atacándolo:
>
> ```
> ../../../../windows/system32/evil  ->  windows_system32_evil.step
> malo\r\nX-Inyectado: si            ->  malo_X-Inyectado_si.step
> a"; filename="otro.exe             ->  a_filename_otro.exe.step
> virus.exe                          ->  virus.exe.step
> vacío / solo símbolos              ->  your_optimal_airfoil.step
> 300 caracteres                     ->  recortado a 80
> ```

---

## 🔍 LA RONDA DE QA — lo que confirmó y el bug que destapó

Verificación sistemática del sistema completo: coherencia entre vistas, tendencias
físicas, extremos y casos límite.

**La física responde como debe**, que es la comprobación que de verdad importa en un
surrogate:

- **CL y CD crecen monótonamente con el nivel de carga** (low → medium → high).
- **El pico de |L/D| está en `medium`**, no en `high`: es el compromiso carga/eficiencia,
  exactamente lo que se espera de un perfil de downforce.
- **El efecto Reynolds desplaza el ángulo óptimo con la velocidad**, coherente con el
  hallazgo del EDA (más velocidad → óptimo hacia ángulos más agresivos).

**Las guardas de dominio disparan por separado y no en bloque**, que era la duda:
`INTERPOLATED SPEED` y `REYNOLDS CORNER` saltan cada una en su condición. Y lo relevante:
**la combinación cuerda × velocidad extrapolada se detecta aunque las dos variables estén
individualmente en rango** — que es el caso que se te escapa si solo validas cada
parámetro por su cuenta.

### El bug: un panel huérfano, no un caché

Al abrir Compare con unos diseños después de haber pulsado "Compare Cp" con otros, se
veía **el Cp de la comparación anterior bajo la tabla de los nuevos**. Dos perfiles
distintos presentados como si fueran el mismo.

La sospecha natural era el caché por `(perfil, vel, ángulo)` del backend. **No era.** Ese
caché es correcto y no participa. `compararSel()` refrescaba la tabla, las curvas y las
siluetas, pero **`#cmp-cp` no aparecía en ninguna parte de esa función**: era el único de
los cuatro paneles de Compare que nadie limpiaba, así que el gráfico de Plotly anterior
sobrevivía en el DOM.

Se **vacía**, no se re-pide: el Cp es a demanda a propósito (XFOIL tarda la primera vez),
y el panel vacío con su botón comunica el estado mejor que un spinner. El caché por
perfil sigue intacto — volver a un conjunto ya calculado es instantáneo (**43 ms** frente
a **1.478 ms** en frío, medido).

---

## 🚀 LA PROMOCIÓN (2026-08-06) — cómo se hizo reversible

### Método: RENOMBRAR, no cambiar rutas

Se midió antes de decidir: **19 ficheros** referencian los nombres de producción
(`inversa_service.py`, `curvas_optimo.py`, `graficas_barrido_velocidad.py`,
`winner_curse.py`, `eda_ml_filtrado150.py`, cinco scripts de batería…).

> **Por qué NO se cambiaron las rutas de carga.** Habría exigido editar los 19 y acertar
> en los 19. Olvidar uno deja el sistema en **estado MIXTO** —la inversa con el modelo
> nuevo y las curvas con el viejo, o el ensemble de σ desparejado del modelo de L/D— que
> **no da error visible, da números sutilmente incoherentes**. Y hay un agravante:
> `eda_ml_filtrado150.py` **escribe** en los nombres de producción, así que un reentreno
> futuro habría deshecho la promoción en silencio.

Con el renombrado: cero cambios de código, los 19 consumidores se enteran a la vez, y el
nombre de producción sigue significando "lo que está en producción". Lo que se pierde
—que el nombre no diga que es el densif— se recupera del `meta` dentro del bundle
(`dataset: "densif_merged_150_500"`).

### Reversión: 10 segundos, sin tocar código

Modelos viejos en **`legacy/pre_densif_20260806/`** con md5 **verificado en destino** y
un `MANIFIESTO.json`. Antes de sobrescribir, el script **revalida el md5 del archivado y
aborta si algo no cuadra**. Comando y comprobación en **`PROMOCION.md`** (raíz).
`LINEA_BASE_casos.json` guarda 3 casos calculados con los modelos VIEJOS para verificar
que la reversión los restaura.

### Lo que NO se promocionó: `airfoil_dataset.csv`

Sigue en 20.349 filas y 3 velocidades. Dos razones, ambas verificadas:

1. **No hace falta.** La inversa lee de él los bounds p5-p95 de los 7 parámetros de
   forma, y se comprobó que son **idénticos** entre ambos datasets: **0.00% en los 7**,
   volumen de la caja de búsqueda ×1.00000. No es suerte: la densificación no generó
   geometrías nuevas, solo evaluó **las mismas** en más condiciones. Los 7 params son
   por perfil, así que su distribución solo se movería si cambiara el conjunto de
   perfiles con alguna condición convergida — y se verificó: **0 perfiles nuevos, 0
   perdidos**.
2. **Promocionarlo rompería el percentil.** `confianza.contexto_catalogo` filtra
   `velocidad_kmh == vel` con **igualdad exacta**. Con 6 velocidades en el catálogo
   cambiaría el KPI y la lógica de encaje. Es una decisión de producto aparte, no un
   efecto colateral que convenga colar en una promoción.

### Qué cambió al promocionar (3 casos medidos, viejo → nuevo)

```
medium 5-9 @180 : alpha 5→6 | franja 5-7°→6° | L/D 58.49→57.97 | sigma 0.458→0.283 (-38%)
high  9-14 @180 : alpha 9→9 | franja    9°→9° | L/D 52.69→52.19 | sigma 0.531→0.339 (-36%)
medium 5-9 @250 : alpha 9→9 | franja 7-9°→9° | L/D 69.16→67.20 | sigma 1.337→0.324 (-76%)
```

**σ cae un 50% de media, y la mayor caída es a 250 km/h (−76%)** — la velocidad
intermedia, justo el hueco que la densificación venía a rellenar. Las de 180, donde ya
había datos, bajan la mitad. **Ese contraste es la firma de que la información añadida es
real** y no un simple estrechamiento del bootstrap por tener más filas.

**El L/D prometido baja un 1-3%, y eso es bueno:** es el modelo dejando de prometer de
más, coherente con que k=0 pasara de 21.5% a 6.9%. Promete menos porque acierta más.

⚠️ **Las formas propuestas cambian bastante** (hasta 54% en un parámetro). Es esperable
—otro modelo, otra superficie— pero significa que **un diseño guardado con los modelos
viejos ya no se reproduce igual**. Los guardados en `localStorage` conservan sus valores
congelados, así que no se rompen: simplemente son de otra época.

### 1️⃣ GENERAR — geometría y datos (CATIA + XFOIL)
| Script | Rol |
|---|---|
| `pipeline_airfoil_api.py` | Orquestador de un perfil (Steps 1-7). Deriva el Reynolds |
| `airfoil_generator.py` | Step 1: perfil en CATIA (plano ZX, Geometrical Sets) |
| `airfoil_points.py` | Step 2: nube de puntos (LE 290 + TE 10) |
| `export_cloud_ascii.py` | Step 3: export ASC ⚠️ **el paso más frágil** |
| `asc_to_dat.py` | Step 4: ASC→DAT + normalización a cuerda |
| `run_xfoil.py` | Step 5: XFOIL (alphas argv1, Reynolds argv2) |
| `generate_batch.py` | Lotes: `--random` / `--sobol` / `--sobol-extremos` / `--manual`. **Requiere CATIA** |
| `densificar.py` | **Añade velocidades/ángulos SIN CATIA** sobre geometrías existentes: regenera el `.dat` TE-real del `.asc` y relanza XFOIL. Reanudable |
| `fusionar_densif.py` | Fusiona lo densificado con el CSV base → `airfoil_dataset_densif_merged.csv` (con verificación) |

### 2️⃣ APRENDER — surrogates (CL / CD / LD)
| Script | Rol |
|---|---|
| `feature_utils.py` | **Fuente única** de las 11 features. **Crítico** |
| `eda_ml_filtrado150.py` | **Entrenador de producción**. Guarda modelo + histórico |
| `reentreno_densif.py` | Reentrena sobre el fusionado a nombres `*_densif` y **compara BASE vs NUEVO** con el mismo GroupKFold. El molde para futuras promociones |
| `winner_curse.py` | Entrena el ensemble de σ (**~1 min**) + corre las optimizaciones DE de la batería (eso es lo que hace largo el script entero) |
| `modelo_LD_inversa_xgb.joblib` | Modelo de producción (11 features) |
| `ensemble_ld_sigma.joblib` | Ensemble de incertidumbre (**111 MB** ⛔ supera el límite DURO de GitHub) |
| `ml_history.json` / `.csv` | Histórico de reentrenos |

### 3️⃣ INVERTIR — proponer formas
| Script | Rol |
|---|---|
| `inversa_ld_v2.py` | Inversa **CLI**: zona fiable p5-p95 + avisos + penalización k=2. Ángulo **fijo −6°**, velocidad fija 180. **⚠️ NO es la que invoca el dashboard** |
| `inversa_service.py` | **La inversa que USA el dashboard**: misma receta (k=2, bounds p5-p95, mismos modelos y ensemble) pero **parametrizada por RANGO de ángulo** y cuerda. Sobol 32.768, ~6-9 s |
| `inversa_bateria.py` / `bateria_k2.py` | Generadores de la batería original (8 casos) |
| `bateria_tereal.py` / `bateria_tereal_ext.py` | Batería TE-real: 20 + 20 = **40 casos** (k=0 y k=2, CATIA+XFOIL). Etapa B ahora **reanudable** |
| `bateria_densif.py` | **Etapa A** de la batería densif (portable, ~3 h): 40 casos × k0/k2 → 80 propuestas + configs `dsf_*.json` |
| `bateria_densif_etapaB.py` | **Etapa B** de la batería densif: verifica las 80 en CATIA+XFOIL. Reanudable, bloquea la suspensión, y **emite el veredicto** comparando contra julio |
| `bateria_*_resultados.json` | **Evidencia** k=0 vs k=2. `bateria_tereal_*` = julio (modelos TE-real); `bateria_densif_*` = agosto (modelos densif). **Ambos vigentes: el contraste ES el resultado** |

> **Por qué la batería se parte en dos etapas y por qué importa.** La A (inversa) es
> **portable y cara en CPU** (~3 h); la B (verificación) **necesita CATIA** y son ~2 h de
> portátil. Separarlas deja adelantar toda la A sin el portátil. La B además se hizo
> **reanudable** (vuelca tras cada geometría y salta las hechas): antes era "2 horas o
> nada" y un fallo de CATIA en el caso 35 tiraba la tirada entera.

> **Por qué existen DOS inversas y no se fusionaron:** `inversa_ld_v2.py` es el CLI
> validado con el que se hizo toda la batería — tocarlo invalidaría esa evidencia. El
> dashboard necesitaba optimizar sobre un **rango** de ángulos (una banda de circuito),
> no sobre −6° fijo, así que `inversa_service.py` reimplementa la MISMA receta con esa
> parametrización, reutilizando modelos y ensemble de disco. Si cambias el criterio de
> optimización, hay que tocar los dos o la batería deja de describir lo que hace la app.

### 4️⃣ ENSEÑAR — capa visual ✅ HECHA (Plotly, tema oscuro)
| Script | Rol | Estado |
|---|---|---|
| `estilo_graficas.py` | **Fuente única** de paleta y layout (tema oscuro tipo telemetría). Todas las gráficas lo importan | ✅ crítico |
| `graficas_winner_curse.py` | Winner's curse: 40 casos, pred vs real | ✅ |
| `graficas_winner_zona.py` | Winner's curse por zona de cuerda (barras) | ✅ |
| `graficas_sigma_error.py` | σ predicha vs error real | ✅ |
| `graficas_forma.py` | Forma del perfil 1:1 (regenera el `.dat` TE-real del `.asc`) | ✅ |
| `graficas_polares.py` | **Polar multi-velocidad con CL, CD y L/D** (3 velocidades) | ✅ |
| `graficas_barrido_velocidad.py` | Surrogate vs XFOIL barriendo velocidad | ✅ |
| `graficas_cp.py` | Cp (orden de arco) + **silueta como inset**. `fig_cp_from_dat` sirve para un `.dat` cualquiera | ✅ |
| `graficas_ficha.py` | **Compositor de ficha**: forma + polares + Cp en una lámina | ✅ |
| `plot_perfil.py` / `cp_on_demand.py` | Versiones matplotlib originales | ✅ siguen sirviendo |
| `eda_velocidad.py` / `plot_polar.py` | Precursores (solo L/D / una velocidad) | 🔵 superados por los `graficas_*` |
| `airfoil_3d.py` | Ala 3D (extrude). **Solo visual** | ✅ aparte |

### 5️⃣ ENTREGAR — dashboard web (PORTABLE, sin CATIA)
| Script | Rol |
|---|---|
| `dashboard_app.py` | **El front real**: Flask + HTML/JS embebido, **5 vistas** (Design · Results · Saved designs · Compare · The method). Puerto **5001** |
| `entrada_dashboard.py` | Parte 1 del flujo: 3 puertas (circuito / nivel / ángulo exacto) → un único `ObjetivoAngulo` |
| `circuitos.py` + `circuitos.csv` | **61 circuitos** → nivel de downforce → rango de \|α\|. Atajo, con nota de equivalencia y aviso de orientativo |
| `curvas_optimo.py` | Curvas predichas del óptimo (3 velocidades) y **L/D vs velocidad** |
| `optimo_geom.py` | `.dat` + `.csv` + `.step` del óptimo + **redondeo del TE a 0.05 mm** + Cp (fallback al vecino, **blindado**) + cachés |
| `step_export.py` | **Escritor de STEP en Python puro** (AP214, sin OpenCASCADE). Constante `FORMATO` = versión del escritor, va en el nombre del caché |
| `rutas.py` | **Fuente única** de `BASE` y de la ruta a XFOIL (cascada + `XFOIL_DISPONIBLE`) + límites de concurrencia y timeout. **Crítico para el despliegue** |
| `build_ensemble.py` | Regenera `ensemble_ld_sigma.joblib` en el build de Docker. ⚠️ **No usar `winner_curse.py` para esto** |
| `Dockerfile` · `requirements.txt` · `.dockerignore` · `render.yaml` | Empaquetado del despliegue (XFOIL por `apt`, gunicorn 1 worker × 4 hilos) |
| `airfoil_geom_fixed.py` | Generador de geometría **con el fix de la auto-intersección del TE** |
| `vecino.py` | Perfil real más cercano del catálogo (referencia de contexto) |
| `comparar.py` | Comparación: curvas superpuestas, **siluetas a escala real en mm**, **Cp superpuesto** |
| `cargas.py` | **Cargas seccionales** por unidad de envergadura (q·c·CL, q·c·CD) |
| `confianza.py` | Señales del modelo (σ, cobertura) + posición frente al catálogo |
| `flask_airfoil_api.py` | **OTRA COSA**: API de **generación de geometría**, requiere **CATIA**. NO es el backend del dashboard |

> **⚠️ No confundir los dos Flask.** `dashboard_app.py` es portable (solo modelos, XFOIL
> y dataset) y es el que sirve la aplicación. `flask_airfoil_api.py` llama a
> `run_pipeline`, que construye geometría en CATIA: solo funciona en la máquina con
> CATIA y **no** sirve la UI.

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

### Dataset MULTI-ÁNGULO + BARRIDO DE REYNOLDS + ÁNGULOS ESCALONADOS

> ⚠️ **Esto describe el muestreo de `generate_batch.py`, que es el que genera perfiles
> NUEVOS con CATIA — sigue siendo de 3 velocidades y paso 2°.** El dataset con el que se
> ENTRENAN los modelos de producción es el **densificado** (6 velocidades, paso 1°); ver
> "La densificación". La diferencia es deliberada: `generate_batch` crea geometrías
> nuevas (caro, necesita CATIA) y `densificar.py` añade condiciones sobre geometrías
> existentes (barato, portable). **Si algún día se generan perfiles nuevos, hay que
> pasarles después `densificar.py`** o quedarán con menos condiciones que el resto.

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

## ⭐ Capa visual ✅ HECHA (y convertida en dashboard)

> **Estado: COMPLETADA.** Era capa de **presentación**, no de generación de datos, y
> era lo que quedaba tras cerrar el núcleo técnico. Se hizo entera y además se
> convirtió en una **aplicación web** (`dashboard_app.py`, ver bloque 5️⃣ del mapa).
> La visión original se cumplió: el sistema ya devuelve una ficha visual completa
> cuando el ML propone un perfil.
>
> **Todo hecho:**
> - ✅ **Forma del perfil** — `plot_perfil.py` (matplotlib) y `graficas_forma.py` (Plotly)
> - ✅ **Cp a demanda** — `cp_on_demand.py` y `graficas_cp.py` (orden de arco, Re real)
> - ✅ **Polar multi-velocidad CON CL y CD** — `graficas_polares.py` (3 velocidades)
> - ✅ **Compositor de la ficha** — `graficas_ficha.py` (forma + polares + Cp en una lámina)
> - ✅ **Gráficas de método** (winner's curse, por zona, σ vs error, surrogate vs XFOIL),
>   reunidas en la vista **"The method"** del dashboard
>
> Precursores: `eda_velocidad.py` (solo L/D) y `plot_polar.py` (una sola velocidad)
> siguen ahí y funcionan, pero los `graficas_*.py` los superan.

### 🎬 La vista "THE METHOD" — 5 apartados, y por qué está así montada

Es la **vista escaparate** (defensa y LinkedIn), así que la prioridad es claridad
narrativa, no densidad. Estructura:

| # | Apartado | Figura |
|---|---|---|
| 1 | The winner's curse | `fig_winner_curse` — scatter predicho vs real, **solo densif** |
| 2 | **What densification changed** | `fig_evolucion` — el antes/después, **solo y a tamaño completo** |
| 3 | It holds across the whole domain | `fig_winner_zona` — dos barras por zona |
| 4 | The model knows when to doubt itself | `fig_sigma_error` — σ vs error real |
| 5 | Predictions vs measured reality | `fig_barrido` — barrido de velocidad, **6 puntos XFOIL** |

> #### Por qué el contraste julio→densif va en un bloque APARTE y no dentro de cada gráfica
>
> Se probó meterlo dentro (nube fantasma en la 1, barras grises en la 2) y **hubo que
> deshacerlo**. Dos motivos, y el segundo es el serio:
> 1. Doblaba los elementos visuales para transmitir un dato que **cabe en una línea de
>    texto**. Mal reparto: mucho gasto visual, poca ganancia.
> 2. **La gráfica trabajaba contra su propio texto.** Con cuatro barras el ojo empareja
>    lo *adyacente* —k2-julio con k2-densif— y concluye "no ha cambiado nada", cuando el
>    mensaje es que **k=0** se desplomó.
>
> El antes/después es **una sola idea**, así que tiene su propia figura, sola, donde
> nada compite con ella. Las otras cuatro vuelven a tener **una idea cada una**, que es
> lo que las hacía legibles antes de la densificación.

#### ⚠️ ERR_MEDIO hardcodeado: la deuda que cobró en la promoción

`graficas_winner_curse.py` tenía `ERR_MEDIO = {"k0": 21.5, "k2": 3.8}` **escrito a
mano**. Al promocionar los modelos densif, la vista escaparate **siguió mostrando los
números de julio** — y no daba ningún error: simplemente mentía. Lo mismo pasaba con
`"36 of 38"`, `"27.3%"`, `"ρ = 0.39"` y `"the three points"` en el HTML.

**Ahora TODO se deriva de los datos**: `stats_bateria()` en el módulo de gráficas y
`_metodo_numeros()` en `dashboard_app.py` (19 valores calculados de las dos baterías).
Verificado con una prueba de sensibilidad: alterando una copia en memoria de los casos,
el número dibujado cambia. **Regla: en la vista escaparate, ningún número a mano.**

#### 🔬 El hallazgo incómodo de la gráfica 4 (σ), que se muestra en vez de esconderse

Con los datos densif, σ **ya NO correlaciona significativamente** con el error real:

```
julio  : Spearman ρ = 0.39  (p = 0.017)   σ ∈ [0.11, 2.52]
densif : Spearman ρ = 0.14  (p = 0.42)    σ ∈ [0.11, 1.30]   NO significativo
```

El título original —*"High σ flags the largest errors"*— dejó de ser defendible.

**Pero σ no se ha roto: le queda muchísimo menos que ordenar.** Su rango se redujo a la
mitad y los errores grandes que ordenaba han desaparecido. Es la consecuencia lógica de
que el modelo acierte más, no un fallo del ensemble.

Se decidió **mostrarlo**: título honesto (*"σ flagged the big failures — and now there
are barely any"*), los dos ρ con sus p-valores en la caja, y la conclusión escrita —
**σ sigue siendo un guardarraíl** (se niega a estar segura donde no hay datos) **pero ya
no es un predictor fino** de cuánto se va a equivocar una propuesta. En una vista de
escaparate era tentador enseñar solo julio, donde el número queda bonito. Habría sido
vender una capacidad que los datos vigentes ya no respaldan.

*(Nota: corregir el caso 10 **empeora** ligeramente este ρ, de 0.22 a 0.14. Coherente:
el artefacto era un error grande con σ baja, y quitarlo deja aún menos varianza que
ordenar. La conclusión de fondo no cambia en ninguno de los escenarios.)*

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
  contraste) y en **`graficas_cp.py`**, que es la ruta viva del dashboard. ⚠️
  **`plot_cp.py` TODAVÍA tiene el bug** de la mediana de y. Hoy `plot_cp` se importa
  **solo como lector** de ficheros (`.dat`, cp, polar) desde `cp_on_demand.py` y tres
  `diag_*`; **nunca se usa para trazar**. Si alguna vez se usa para dibujar, aplicar
  ahí el mismo arreglo de orden de arco.

### ⚠️ FALSO AMIGO: dónde está DE VERDAD el Cp (`cp.txt`, no `cp_alpha_*.txt`)

> Aviso para quien (persona o agente) busque "dónde se genera el Cp". Es fácil
> aterrizar en código muerto: pasó durante el desarrollo de la comparación de Cp.

- **Ruta VIVA:** `graficas_cp._xfoil_cp(dat, Re, alpha, workdir)` lanza XFOIL con
  `CPWR cp.txt` y escribe **`cp.txt`** (+ `polar.txt`) en un **workdir temporal**
  (`%TEMP%/cp_opt/<hash>`, `%TEMP%/cp_cmp/<hash>`). Devuelve `Nx3 (x, y, Cp)` en
  orden de arco. Todo el Cp del dashboard pasa por ahí:
  `optimo_geom.cp_optimo` (Results) y `comparar._cp_de_diseno` (Compare).
- **NO existe ningún `cp_alpha_{p9|m4}.txt` vivo.** Ese naming solo aparece en
  `export_powerbi_data.py`, que es de la **era MVP y está obsoleto** (hardcodea
  `RUN_ID="run_001"`, cuerda 250, Re 1e6, y no conoce el dataset). Ver la sección
  EXPORT/BI del inventario.

### Ángulo del Cp: unificado a ENTERO EXACTO ✅ resuelto (antes se redondeaba a par)

- **Qué pasaba:** el Cp de **Results** redondeaba el ángulo al **par más cercano**
  (`-int(round(α/2)*2)`), herencia de que el dataset barre ángulos pares. El Cp de
  **Compare** usaba el entero exacto. Con un ángulo recomendado de 5°, Results
  dibujaba el Cp a **4°** mientras el KPI decía "~5°": **el panel se contradecía a sí
  mismo** y los dos Cp del mismo perfil no coincidían.
- **Por qué el redondeo a par NO era necesario:** `_xfoil_cp` construye la marcha con
  `range(0, alpha-1, -2)` y **añade el ángulo pedido al final**. Para −5 la secuencia
  es `[0, -2, -4, -5]`: el paso de 2 es solo la **marcha de convergencia**, no una
  restricción sobre el ángulo final. Los impares convergen sin problema (verificado).
- **Arreglo:** unificado a `-int(round(α))` en los **3 puntos** que dependían de ello:
  `optimo_geom.py` (Cp de Results), `vecino.py` (Cp del vecino) y `verif_cp_optimo.py`
  (script de diagnóstico). Copias previas en `*.pre_alpha_exacto.bak`.
- **Impacto — mayor de lo que parecía:** de 8 combinaciones circuito × cuerda
  probadas, **las 8** tenían ángulo recomendado **impar**. Es lógico: el recomendado es
  el argmax de |L/D| sobre una rejilla de paso 1° dentro de bandas 0-5 / 5-9 / 9-14, y
  suele caer en los **bordes** (5, 9). Así que el Cp de Results estaba desplazado casi
  siempre. Y no era cosmético: en un caso típico el pico de succión pasó de **−3.67 a
  −4.15** (13% más profundo). En un caso (Monza c200, α_rec 3°) el redondeo incluso
  **subía** a 4°, alejándose del óptimo en la dirección contraria.
- **Verificado:** con α_rec **par** el Cp es idéntico bit a bit antes/después (no se
  rompió nada); con α_rec **impar** Results pasa de −4 a −5 y **coincide exactamente**
  con Compare (mismo `cp_min` a 5 decimales, mismo nº de puntos).

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

### Rango soportado de velocidad: 95 – 330 km/h, y las DOS listas de velocidades ✅

Desde la feature C5 la velocidad es entrada de usuario, no una constante oculta. Las
guardas viven en **`guardas_velocidad.py`** y el rechazo duro en
`entrada_dashboard.valida_velocidad` (molde de `valida_cuerda`).

- **95 – 330 km/h**: fuera de ahí se **rechaza**. El límite no es arbitrario: con
  tolerancia de ±15% en cuerda, la ventana sin extrapolar es `[110/1.15, 290·1.15]`
  ≈ `[96, 334]` para **cualquier** cuerda (Re es lineal en cuerda y en velocidad).
- Dentro del rango, **tres avisos que NO bloquean**: zona interpolada (95-110 y
  290-330), ángulo sin datos a esa velocidad, y esquina de Reynolds (la combinación
  cuerda×velocidad supera el Re máximo visto).

> #### ⚠️ V_MODELO vs V_CATALOGO: no son la misma lista, y fusionarlas es el error fácil
>
> ```python
> V_MODELO   = (110, 150, 180, 220, 250, 290)   # entrenamiento (densificado)
> V_CATALOGO = (110, 180, 290)                  # airfoil_dataset.csv (sin promocionar)
> ```
>
> - **`V_MODELO`** gobierna los **avisos de dominio**: predecir a 220 km/h ya NO es
>   interpolar a ciegas, hay datos reales ahí.
> - **`V_CATALOGO`** gobierna el **encaje a velocidad de referencia** de
>   `confianza.contexto_catalogo`, que filtra `velocidad_kmh == vel` con igualdad
>   exacta. El modelo sabe de 6 velocidades, pero las **MEDICIONES de XFOIL** con las
>   que se compara el percentil siguen existiendo solo en 3.
>
> La UI lo dice explícitamente: *"compared at 180 km/h (nearest measured speed) — the
> model predicts at your 220 km/h, but the catalogue it is ranked against holds XFOIL
> measurements, and those only exist at 110, 180 and 290 km/h"*. **Es una asimetría
> honesta, no un bug.** Se resuelve sola el día que se promocione el CSV, que es una
> decisión de producto aparte.

#### Límites angulares por velocidad (`ALPHA_ANCLAS`) — 6 anclas desde la densificación

| V | \|α\| máx | origen |
|---|---|---|
| 110 | 10 | ancla (dato real) |
| 150 | 11 | ancla (dato real) |
| 180 | 12 | ancla (dato real) |
| 220 | 13 | ancla (dato real) |
| 250 | 13 | ancla (dato real) |
| 290 | 14 | ancla (dato real) |

`alpha_max_soportado(v)` interpola linealmente a trozos entre ellas. Antes solo había
3 anclas y 150/220/250 se **estimaban**; ahora son medidas. Es la misma función que usa
`densificar.py` para decidir hasta dónde barrer y `curvas_optimo._alphas_de` para no
dibujar más allá de donde hay datos: **una sola fuente para el límite del dominio.**

### El ángulo recomendado se presenta como FRANJA, no como punto ✅

`optimo_geom.franja_angulo` devuelve el rango de ángulos que el modelo **no distingue**
del mejor: los que cumplen `|LD(a)| >= |LD(argmax)| − σ`. El KPI dice "6–8°", no "7°".

> **Por qué.** El argmax suele ganar por **menos que la propia σ del modelo**. Medido en
> medium/300 mm a 180 km/h: ganaba por **0.34** con σ = **0.46**. Publicar un grado
> concreto finge una resolución que no existe. La franja además absorbe el salto no
> monótono del ángulo al cambiar de velocidad.

> ⚠️ **CORRECCIÓN (2026-08): la justificación original ha CADUCADO en parte.** Decía
> también que "el dataset barre solo ángulos pares, así que el surrogate resuelve ~2°".
> **Eso ya no es cierto**: el dataset de entrenamiento tiene paso de 1°. El microtexto de
> la UI que lo repetía se retiró. **La franja se mantiene** porque su razón de fondo —la
> ventaja del argmax cae por debajo de σ— sigue siendo cierta; simplemente ahora sale
> **más estrecha** (σ bajó ~40% al densificar: 5–7° → 6°, 7–9° → 9°).

Tres decisiones de implementación, todas contrastadas con datos:

1. **ENVOLVENTE, no tramo contiguo.** Se probó exigir contigüidad y hubo que descartarlo:
   la curva alterna, así que un ángulo cumple el umbral y su vecino no. Con los modelos
   pre-densificación eso **colapsaba la franja a un punto justo en el caso que motivó la
   feature**. Además un rango es lo único interpretable como reglaje.
2. **σ media de la banda, no σ local del argmax.** Se probó la local y se descartó: el
   argmax cae donde el ensemble está más de acuerdo, así que su σ es **la menor de la
   banda** y estrecha la franja precisamente por ser el punto más cómodo. Con ella, 7°
   quedaba fuera **por 0.0006** en L/D. Y la media de banda es **la σ que ya se publica
   en el KPI**, así que el usuario puede rehacer la cuenta con los dos números que ve.
3. **El texto usa `delta_extremos`, no la caída interior.** Un borrador decía "L/D varía
   solo 1.39 frente a σ = 1.34" — un sinsentido (1.39 > 1.34), porque la envolvente
   incluye ángulos interiores que se hunden bajo el umbral. `delta_extremos` es por
   construcción ≤ σ y sí se puede comparar con ella.

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
    disco**; **nunca se reentrena por llamada**. Si falta, regenerarlo con
    `python winner_curse.py`.
  - ⚠️ **CORRECCIÓN medida (2026-08):** aquí ponía que entrenar el ensemble tarda
    **~17 min**. **Es falso: tarda ~1 min** (10 miembros × ~5 s cada uno, medido sobre
    63.496 filas). Los ~17 minutos son del **script completo**, que además del ensemble
    corre las optimizaciones `differential_evolution` de la batería. Importa porque el
    dato equivocado hacía parecer caro regenerarlo, y es justo lo contrario: es el
    artefacto más barato de reproducir del proyecto — de ahí que la salida preferida
    para GitHub sea `.gitignore` + regenerar en destino.
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
| `alpha` (`generate_batch`, perfiles nuevos) | escalonado, **paso 2°**: 110→0…−10, 180→0…−12, 290→0…−14 |
| `velocidad` (`generate_batch`, perfiles nuevos) | **110, 180, 290 km/h** (→ Reynolds por cuerda) |
| `alpha` (**dataset de entrenamiento**, densificado) | escalonado, **paso 1° (pares e impares)**: 110→0…−10, 150→0…−11, 180→0…−12, 220→0…−13, 250→0…−13, 290→0…−14 |
| `velocidad` (**dataset de entrenamiento**, densificado) | **110, 150, 180, 220, 250, 290 km/h** |

> Las dos últimas filas son las que ve el MODELO; las dos anteriores, las que usa
> `generate_batch.py` al crear geometrías nuevas con CATIA. Ver el aviso en "Dataset
> multi-ángulo".

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

## 🏁 RECLASIFICACIÓN DE CIRCUITOS — de 42 a 61, y 11 cambios de nivel

Se cruzó el catálogo con una clasificación nueva de 61 circuitos (investigación cruzada
+ criterio propio) y se aplicó. **11 de los 42 originales cambiaron de nivel:**

| → LOW | → MEDIUM | → HIGH |
|---|---|---|
| Montreal, Red Bull Ring | Sepang, Spa-Francorchamps, Yas Marina, Nordschleife, Termas de Río Hondo | Barcelona-Catalunya, Mugello, Silverstone, Suzuka |

**Spa pasó a MEDIUM** corrigiendo la fuente original, que lo ponía en LOW: Kemmel pide
poca carga, pero Eau Rouge y el sector 2 piden más.

**Las 11 notas se reescribieron.** No es cosmética: la columna `nota` se muestra en la
UI y justificaba el nivel *anterior*. Sin tocarla, el usuario habría leído
"Nordschleife · carga media — Revirado extremo".

**Se añadieron los 19 que faltaban** hasta los 61. Los cinco históricos (Goodwood, Reims,
AVUS, Rouen, Jacarepaguá) llevan `confianza: baja`, un valor nuevo en esa columna: son
trazados sin referencia aerodinámica moderna, clasificados solo por la geometría del
trazado, y marcarlos igual que Monza sería deshonesto. La columna es documental —
**ningún código la lee**, comprobado antes de añadir el valor.

> **Se descartó dividir en 5 niveles.** Sería falsa precisión: la clasificación sale del
> tipo de trazado, no de datos de reglaje reales, y afinarla a 5 escalones sugiere una
> resolución que no existe. Además reabriría el núcleo — las bandas de ángulo
> (`CATEGORIA_RANGO`) están cableadas a tres y todo el dataset se barrió con ellas.

`rango_angulo_deg` se reescribió **derivándolo** de `CATEGORIA_RANGO` en cada fila, no a
mano, así que no puede desincronizarse: 0-5 / 5-9 / 9-14 en las 61 filas.

**Mensaje de orientativo en la UI**, entre el desplegable y el botón — antes de elegir,
no después: *"Guideline based on the circuit's typical downforce profile — adjust to your
category and setup."*

---

## 🎨 EL PULIDO FINAL DE LA UI

### Dos mensajes que se malinterpretaban

- **"better than 90% of existing profiles"** se reescribió: es un **ranking, no un
  margen**. Ahora dice explícitamente que el óptimo *supera* al 90% de los perfiles
  reales, no que sea un 90% mejor, y que la vara de medir son **mediciones de XFOIL**,
  no teoría.
- **"closest to database"** se retiró de la UI. No daba ninguna decisión accionable:
  saber que tu óptimo se parece un 78% a un perfil del catálogo no cambia nada de lo que
  vas a hacer con el `.dat`. ⚠️ **El CÁLCULO se mantiene y NO debe borrarse**: alimenta
  el fallback del Cp, lo sirve `/api/vecino`, y cuesta 0,8 ms.

### Las tres cajas de aviso de Results: qué se pliega y qué no

Results había acumulado texto hasta pesar demasiado para un primer vistazo. Se plegaron
**dos** de las tres cajas tras un `?` (patrón `details.fold`): la del catálogo y la del
porqué de la franja. Son **explicación y validación**.

> **La caja de σ NO se pliega, y el aviso de alta incertidumbre es estructuralmente
> imposible de plegar**: vive en `renderAvisos()`, fuera de los dos `<details>`. No es
> disciplina al escribir el markup, es que no está dentro. Además se reordenó el
> `innerHTML` para que lo accionable vaya ARRIBA del contenido plegado.
>
> **El principio: plegar validación está bien; plegar una advertencia de riesgo, no.**
> Verificado en un caso de σ alta (high / 160 mm / 95 km/h → σ = 1,479): el aviso ámbar
> sale entero y por encima de lo plegado.

### Compare: siluetas alineadas con la tabla

Las dos cajas comparten **arriba y abajo** (`align-items: stretch` en `.cgrid`, con la
gráfica centrada dentro). Antes colgaban desde arriba y el escalón inferior iba de
**105 px con 2 diseños a 203 px con 3** — por eso no servía una altura fija: el desfase
depende de lo que compares.

> Se probó estirar también la gráfica (`height=null`) y **se descartó**: el 1:1 aguantaba
> (`scaleanchor` reparte el alto sobrante como rango, no como escala — verificado a ratio
> 1.000000), pero el título va anclado a `y=0.95` del papel y la leyenda al borde del
> área de trazado, que no se mueve: con 3 diseños la leyenda se comía el título.

---

## 🚀 PORTABILIDAD Y DESPLIEGUE

### `rutas.py` — fuente única de rutas y de XFOIL

Había **14 rutas absolutas** a `C:\Users\MSI-06\...` en 11 ficheros, y lo peor: **la ruta
de XFOIL declarada literalmente en SIETE sitios**. Siete copias del mismo valor sin
fuente única: si alguien mueve XFOIL y arregla cinco, el sistema queda a medias —la
inversa funciona y el Cp no—, que es el peor modo de fallo porque no parece un fallo.

`rutas.py` centraliza `BASE` (por `__file__`, como ya hacían 78 de 97 módulos) y resuelve
XFOIL **en cascada**:

```
1. variable de entorno XFOIL_EXE   (lo que impone el despliegue)
2. xfoil / xfoil.exe en el PATH    (shutil.which)
3. instalación local de desarrollo (cortesía, para no configurar nada en local)
4. nada -> XFOIL_DISPONIBLE = False, SIN crash
```

> Si `XFOIL_EXE` está definida pero apunta a algo inexistente, **no** cae a las siguientes
> ramas: eso es un error del operador, no un "aquí no hay XFOIL", y silenciarlo daría un
> modo web accidental en un servidor donde sí querías XFOIL.

También expone `XFOIL_CONCURRENCIA` (2) y `XFOIL_TIMEOUT_S` (20). El timeout estaba en
**120 s** para llamadas cuya mediana medida es **0,48 s**: unas pocas colgadas bloqueaban
el servicio dos minutos.

### Modo web: degradar sin romperse

Si no hay XFOIL, los Cp devuelven un aviso informativo (borde teal, no rojo: no se ha
roto nada, es una capacidad que vive en la versión local) y **todo lo que sale del
surrogate funciona igual**: diseño, KPIs, cargas, siluetas, comparación de formas.

> **Un problema de honestidad que apareció aquí:** `senales_modelo` recibía un booleano
> `xfoil_ok`. Sin XFOIL habría sido `False` y el panel diría *"XFOIL did not converge on
> this geometry"* — una acusación falsa contra una geometría que nadie llegó a evaluar.
> Ahora son **tres estados** y en web dice *"XFOIL not available in the web version —
> geometry not verified"*.

**El fallback del Cp está blindado.** Antes, si fallaba el fallback al vecino —por
ejemplo sin el `.asc` archivado, que es justo lo que pasa en un servidor sin
`dataset_runs/`— la excepción salía desde dentro del `except` de `cp_optimo` y se
propagaba: `/api/optimo` devolvía **400 con solo `{"error"}`** y el usuario perdía
`dat_url`, `csv_url` y `step_url`. **Descargas que no dependen de XFOIL para nada,
tumbadas por un fallo del Cp.** Ahora el fallback tiene su propio `try` y hay cuatro
estados de `cp_source` (`optimum` / `neighbour` / `unavailable` / `failed`).

| escenario | HTTP | descargas |
|---|---|---|
| XFOIL converge | 200 | dat + csv + step |
| XFOIL falla, hay `.asc` | 200 | dat + csv + step |
| XFOIL falla, sin `.asc` ni cachés | 200 | **dat + csv + step** |

`vecino.py` también se cayó de pie: construía su lista de candidatos filtrando por
perfiles con `.asc`, y sin `dataset_runs/` quedaba **vacía** → `np.argmin` reventaba con
un 500 en `/api/optimo`. Ahora cae al catálogo completo (`GEOMETRIA_VECINO = False`).

### Empaquetado

- **`Dockerfile`**: `python:3.12-slim-bookworm` + `apt-get install xfoil` (verificado:
  **6.99.dfsg+1-3, sección `science`, en `main`** — importa, porque la imagen slim solo
  trae `main`) + `requirements.txt` fijado + gunicorn con **1 worker y 4 hilos** (cada
  worker carga sus propios ~640 MB, así que la concurrencia sale de los hilos).
- **`build_ensemble.py`**: regenera el ensemble de 106 MB **en el build** (~62 s). Es la
  vía gratis al límite duro de 100 MiB de GitHub.

> ### ⚠️ NO regenerar el ensemble con `winner_curse.py`
>
> Es lo intuitivo —ese script lo entrena si no lo encuentra— y sería un **error
> silencioso**: lee `airfoil_dataset.csv`, el CATÁLOGO de 16.182 filas ok, no el dataset
> de entrenamiento de 63.496. Y su `LD_TUNED` **es distinto** del que entrenó producción
> (`subsample` 0.9 vs 0.6, `min_child_weight` 3 vs 5, `reg_lambda` 1.0 vs 5.0).
>
> El primer intento cayó justo ahí: salió un ensemble de **156 MB con σ un 24% mayor**,
> mismo nombre de fichero, otro modelo. Con los hiperparámetros correctos —verificados
> contra los que el propio `.joblib` lleva guardados dentro, no copiados de otro script—
> el resultado es **idéntico**: 105,8 MB y **σ con diferencia máxima 0.000e+00**.
>
> Por eso `requirements.txt` **fija `xgboost==3.3.0`**: es la versión con la que se
> entrenaron los modelos versionados, y el ensemble regenerado tiene que casar con ellos.

### El repo

Público en `github.com/cvazquezb2003-afk/motorsport-ml-airfoil-design`, commit `ce18a00`:
**1.706 ficheros, 43,8 MB**. Entra el código, los 3 modelos pequeños (14,3 MB), el
dataset de entrenamiento (13,4 MB, necesario para el build), el catálogo, los JSON de
evidencia de las baterías y **los 1.265 `.asc` de `dataset_runs/`** (11,4 MB).

> **De `dataset_runs/` entran SOLO los `.asc`.** Son la fuente de verdad y el fallback
> del vecino los necesita. Los `.dat` archivados **NO**: son de junio, geometría
> TE-AMPUTADA, y publicarlos sería repartir 1.261 ficheros que parecen buenos y no lo son.
>
> La regla de reinclusión no funcionó a la primera y **la primera pasada dio 0 `.asc` sin
> avisar**: `auto_export.asc`, la regla del residuo del pipeline en la raíz, coincide a
> **cualquier profundidad** y volvía a excluirlos. Anclado con barra inicial
> (`/auto_export.asc`). Solo se ve **contando ficheros**, no leyendo el `.gitignore`.

**0 secretos**, verificado sobre el **contenido del commit** (`git grep` en `HEAD`), no
sobre el árbol de trabajo: 12 patrones, cero coincidencias, cero ficheros sensibles.

---

# 📦 INVENTARIO DE ARCHIVOS

> Recorrido de la carpeta. Conteo **verificado el 2026-08-08**: **99 `.py`, 19 `.csv`,
> 238 `.json`, 4 `.joblib`, 9 `.png`, 4 `.md`** + los ficheros de despliegue
> (`Dockerfile`, `requirements.txt`, `render.yaml`, `.gitignore`, `.dockerignore`)
> + `dataset_runs/` (1.293 carpetas),
> `graficas/` (115 ficheros: PNG/HTML del dashboard y del método, más el caché
> `_optimo_cache/`), `eda_outputs/` (29 PNG), `bateria_densif_stars/` (40 `.dat`),
> `legacy/` (con `pre_densif_20260806/`), `__pycache__/`.
>
> El salto de `.json` (154 → 238) es casi todo **propuestas de la batería densif**: 80
> configuraciones `dsf_*.json` + índices + resultados. Es evidencia, no basura.
>
> ⚠️ **Las tablas de abajo cubren el núcleo histórico** (pipeline, ML, inversa,
> diagnóstico). La **capa de entrega** —dashboard, `graficas_*.py`, servicios
> portables— está catalogada en el **bloque 5️⃣ del mapa rápido**, no aquí: se
> documentó allí para que el mapa siga siendo el índice único de "qué hace qué".
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
| `winner_curse.py` | Ensemble de σ (bootstrap de perfiles, **~1 min**) + optimizaciones DE de la batería (el resto del tiempo) | ✅ funciona |
| `ml_history.json` / `ml_history.csv` | Histórico de reentrenos (9 entradas) | ✅ datos |
| `modelo_LD_inversa_xgb.joblib` (8 MB) | Modelo de producción, 11 features | ✅ artefacto |
| `ensemble_ld_sigma.joblib` (**111 MB**) | Ensemble de incertidumbre (densif) | ✅ artefacto ⛔ **bloquea GitHub** |
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

## 🔵 VISUALIZACIÓN (matplotlib) — precursores, ya superados por los `graficas_*.py`

> Estos son los **originales en matplotlib**. Siguen funcionando y sirven para
> inspección rápida desde consola, pero la capa visual del producto es Plotly
> (bloque 5️⃣ del mapa). Se conservan porque documentan cómo se llegó allí.

| Archivo | Qué hace | Veredicto |
|---|---|---|
| `plot_perfil.py` | Forma del perfil, 1:1 real, desde `.dat` o `--run-id` | ✅ **sirve tal cual** |
| `cp_on_demand.py` | Cp a demanda (run_id + velocidad + ángulo), Re real, **orden de arco** | ✅ **sirve tal cual** |
| `eda_velocidad.py` | L/D vs α con las **3 velocidades** superpuestas | 🔵 superado por `graficas_polares.py` (que sí trae CL y CD) |
| `plot_polar.py` | Step 6: CL-α, CD-α, CL-CD, L/D-α, CM-α | 🔵 superado por `graficas_polares.py` (este solo hace UNA velocidad) |
| `plot_cp.py` | Step 7: Cp estilo XFOIL | ❌ **no trazar con él**: bug de la mediana de y (zigzag). Hoy solo se usa como **lector** de ficheros |
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

- **`airfoil_dataset_densif_merged.csv`** (14,1 MB): **el dataset con el que se ENTRENAN
  los modelos de producción** — 944 perfiles / **75.101 filas** / 63.840 ok, 6 velocidades,
  paso angular 1°. Lo generan `densificar.py` + `fusionar_densif.py`. Las filas
  densificadas llevan sufijo `_densif` en `source`.
- **`airfoil_dataset.csv`** (3.7 MB): TE-real — 969 perfiles / 20.349 filas / 16.526 ok
  (conv. 81.2%). **Ya NO es el dataset de entrenamiento, pero sigue siendo activo crítico:**
  es el **catálogo de mediciones** de `confianza.contexto_catalogo` (percentil) y la fuente
  de los **bounds p5-p95** de la inversa. **No promocionar sin leer "La promoción".**
  El viejo amputado (989/20.769/15.107) está en `legacy/airfoil_dataset_amputado_legacy.csv`.
- **`airfoil_dataset_densificado.csv`** (10,4 MB): solo las 54.752 filas nuevas, antes de
  fusionar. Redundante con el merged; se conserva por trazabilidad de la tirada.
- **`dataset_runs/`** (1.293 carpetas): `.asc` + `.dat` + polar por perfil. ⚠️ Enorme para
  GitHub. **El `.asc` es la fuente de verdad; el `.dat` es de JUNIO (TE amputado)** — ver
  el aviso en "La densificación".
- **CSV legacy** (7): `legacy`, `legacy_semicolon`, `alpha0`, `multialpha`, `18cond`,
  `alphas_3-6-9-12`, `prueba_reynolds90`. Archivar; CLAUDE.md dice **no borrar**.
- **`eda_outputs/`** (31 PNG): gráficas de diagnóstico y EDA ya generadas.
- **`ala_3d.CATPart`**: primer ala 3D generada.

## Utilidades / API

| Archivo | Estado |
|---|---|
| `flask_airfoil_api.py` | API de **generación de geometría** (`/health` + `POST /generate_airfoil` → `run_pipeline`). **Requiere CATIA.** ⚠️ **NO es el backend del dashboard** — ese es `dashboard_app.py` (portable, puerto 5001). Ver el aviso del bloque 5️⃣ |

---

## ✅ Lo que YA TIENES (aunque no lo recuerdes)

1. **Dashboard web funcionando** (`dashboard_app.py`, puerto 5001): 5 vistas, portable,
   sin CATIA. Es el entregable del proyecto, no un prototipo.
2. **API REST de generación** (`flask_airfoil_api.py`) — con CATIA, para geometría nueva.
3. **Cp a demanda resuelto y correcto** (`cp_on_demand.py` / `graficas_cp.py`).
4. **Ficha visual completa** — forma + polares (3 velocidades, CL/CD/LD) + Cp, compuesta
   en `graficas_ficha.py` y servida en el dashboard.
5. **Gráficas del método** — winner's curse (40 casos), por zona, σ vs error, surrogate vs
   XFOIL. Datos en `bateria_*_resultados.json`, dibujadas en `graficas_*.py`.
6. **Histórico de ML** (`ml_history.json`) — listo para una gráfica de evolución.
7. **Un dashboard Power BI** (`airfoil_dashboard.pbix`) — fuentes obsoletas, superado por
   el dashboard propio.
8. **Exportación CAD en 3 formatos** — `.dat` / `.csv` / `.step`, el STEP validado
   abriéndolo en CATIA. Ver "La capa de entrega CAD".
9. **El proyecto en GitHub, público y con el repo limpio** — `ce18a00`.
10. **Imagen de despliegue lista** — `Dockerfile` con XFOIL, `requirements.txt` fijado y
    el ensemble regenerándose en el build.

## ❌ Lo que FALTA de verdad

> Lo visual, lo de producto y el empaquetado **ya están**. Lo que queda es **pulsar el
> botón del despliegue** y contarlo.

| Necesidad | Estado | Esfuerzo |
|---|---|---|
| **README.md** | ❌ **no existe** — GitHub muestra la portada vacía, y es lo primero que ve quien entra. Máxima prioridad ahora que el repo es público | 🟢 bajo |
| **Despliegue efectivo** | 🟡 todo preparado; falta activar el pago del hosting y `fly deploy --remote-only` | 🟢 bajo |
| **Post de LinkedIn** | ❌ pendiente: es el objetivo de todo el escaparate | 🟢 bajo |
| **Capa SQL** | ❌ nada: sin BD, sin esquema, sin ETL | 🟡 medio |
| **Power BI sobre el dataset real** | ❌ rehacer desde cero (opcional: el dashboard propio ya cubre la función) | 🟡 medio |
| **Persistencia de diseños en servidor** | 🟡 hoy es `localStorage` del navegador (decisión consciente: cero infra) | 🟡 medio |

### ✅ RESUELTO — el cabo suelto del ensemble de 111 MB

> Fue el bloqueo del primer push durante toda la fase densif. **Ya no bloquea nada.**

La salida elegida fue la primera de las tres que se barajaron: **`.gitignore` + regenerar
en destino**, pero ejecutada con un matiz que resultó ser todo el asunto — **no se
regenera con `winner_curse.py`**, que era el plan original y habría producido un ensemble
distinto en silencio. Se hizo con **`build_ensemble.py`**, verificado **idéntico** al de
producción (σ con diferencia máxima 0.000e+00). Ver "Empaquetado" arriba.

Git LFS y el almacenamiento en la nube quedaron descartados por ser de pago; regenerar en
el build es gratis y autocontenido.

### ⚠️ La memoria, no el ensemble, es lo que condiciona dónde se despliega

Medido por etapas en el arranque: el proceso llega a **~640 MB** de residente
(12 intérprete + 60 numpy/pandas/scipy + 74 xgboost + 289 modelos y ensemble + 205 el
resto). Eso **descarta las capas gratuitas de 512 MB** (Render free y starter). Opciones
evaluadas: Fly.io con 1 GB (~5-6 $/mes, el Dockerfile vale tal cual) o HF Spaces, que da
**16 GB gratis de RAM** pero **exige plan de pago para crear un Space Docker** (los
gratuitos son solo Gradio sobre ZeroGPU).

Si algún día el coste molesta, la palanca es el ensemble —de ahí salen los 289 MB— pero
tocarlo **cambia σ** y obliga a revalidar la batería: es una decisión de modelo, no de
infraestructura.

### 📋 PENDIENTES de producto y layout (ninguno bloquea; son de pulido)

> Lista viva. Nada de esto afecta a la corrección de los resultados: son mejoras de
> entrega y de comunicación. Se anotan aquí para que no se pierdan entre sesiones.

**Dashboard / layout — CASI TODO HECHO en la tanda del 2026-08-08**
- [x] ~~**CSV descargable**~~ — hecho, y además `.step`. Ver "La capa de entrega CAD".
- [x] ~~**Reducir el texto de Results**~~ — hecho con el patrón `details.fold`, dejando
      la caja de σ y el aviso de riesgo siempre visibles. Ver "El pulido final de la UI".
- [x] ~~**Aclarar los dos mensajes que se malinterpretan**~~ — el del percentil reescrito
      como ranking; "closest to database" retirado de la UI (el cálculo se conserva).
- [x] ~~**Revisar la clasificación de circuitos**~~ — hecho: 61 circuitos, 11
      reclasificados, notas reescritas y mensaje de orientativo en la UI.
- [x] ~~**Alinear la vista Compare** con Results~~ — siluetas y tabla comparten base y
      cabecera (`align-items: stretch`).
- [ ] Layout de la vista "The Method": el texto de los apartados no llega al borde del
      panel. **Se probó repartirlo en columnas y se descartó** (con párrafos de 5-6
      líneas obliga a bajar y volver a subir; se lee peor de lo que gana en equilibrio).
      Alternativa no explorada: poner el texto **al lado** de la figura en los apartados
      cuya gráfica es cuadrada (1, 3 y 4), en vez de encima.
- [ ] **Persistencia de los diseños guardados**: siguen en `localStorage`, así que se
      pierden al cambiar de navegador. Con la app desplegada esto se nota más.

**Geometría / CATIA**
- [x] ~~**Checks del `.dat` generado en CATIA**~~ — cubierto de otra forma, y mejor: la
      exportación **STEP** obliga a que el contorno sea una curva cerrada válida, y el
      escritor comprueba en cada llamada que el contorno llega **abierto** (si no, lanza),
      que hay puntos suficientes, y devuelve la desviación de la spline y el hueco del TE
      medidos. Además el validador de STEP verifica cardinalidad de nudos y cierre. Los
      dos episodios que motivaron este pendiente —el kink del TE y el `.dat` amputado—
      están resueltos y documentados arriba.
