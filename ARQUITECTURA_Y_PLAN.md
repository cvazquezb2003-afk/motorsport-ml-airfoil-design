# Arquitectura del producto y plan del mes

> Documento de decisiones, preguntas abiertas y plan.
> Fecha: 21 julio 2026. Contexto: se devuelve el equipo con CATIA en ~1 mes.
> Este documento resume una sesión de arquitectura. NO sustituye al CLAUDE.md
> (que sigue siendo la referencia técnica del núcleo); lo complementa a nivel de producto y planificación.

---

## 0. La restricción que manda sobre todo

**En ~1 mes se devuelve el equipo → se pierde CATIA. XFOIL es reinstalable.**

Consecuencia central: lo único que caduca es **generar geometría nueva** (CATIA construye los perfiles). Todo lo demás —dataset, modelos, inversa, gráficas, análisis— es **portable** y funciona en cualquier PC con Python.

Regla de priorización de todo el plan: **lo que depende de CATIA va primero.** Lo portable se puede hacer después, con calma, desde el PC personal.

---

## 1. Qué es el producto (decidido)

Un **explorador de diseño de perfiles basado en surrogates**: predice prestaciones en vez de calcularlas con CFD. Así es como se hace diseño preliminar en la industria moderna — modelos rápidos para explorar, cálculo caro solo para validar.

Esto resuelve el dilema "portfolio vs producto": **son lo mismo en este caso.** Demuestra ingeniería + ML + rigor metodológico (portfolio) Y permite a alguien meter un objetivo y obtener un perfil con prestaciones (producto), sin depender de nada que caduque.

### El flujo de usuario (visión completa)

1. El usuario define restricciones y objetivo (cuerda máx X mm, velocidad, qué prioriza: L/D, baja resistencia…).
2. El sistema propone perfil(es) candidato(s) con sus prestaciones predichas.
3. Muestra sus fichas visuales (CL/CD/L/D).
4. Recomienda el mejor según lo pedido, mostrando alternativas.
5. El usuario elige y **se lleva la geometría** a su CAD para construir su alerón.

### Entrega de geometría: dos ramas (decidido)

| | Usuario **sin** CATIA | Usuario **con** CATIA |
|---|---|---|
| **Qué recibe** | Un `.dat` del catálogo (vecino más cercano al óptimo) | Los parámetros del óptimo (ML) + generador para reconstruir el `.CATPart` en su CATIA |
| **Calidad geométrica** | Geometría real de CATIA, universal (cualquier CAD la importa) | El óptimo **exacto**, reconstruido con calidad perfecta por su propio CATIA |
| **Limitación** | Es el vecino, no el óptimo exacto | Nicho: requiere tener CATIA + saber ejecutar el script. Y hay que blindarlo AHORA (ver §4) |

Las dos ramas **se complementan**, no compiten. Cada usuario usa la que le sirve.

---

## 2. Decisiones tomadas (cerradas)

| Decisión | Resultado | Motivo |
|---|---|---|
| **Backup** | ✅ Hecho | 34 MB verificados byte a byte, en Drive. Red de seguridad puesta |
| **Generador de geometría en Python** | ❌ Explorado y **descartado** | Se midió: XFOIL no converge sobre la geometría Python ni en casos fáciles. Problema estructural (suavidad de curvatura del spline), no de calibración. Cerrar la brecha = replicar el spline interno de CATIA ≈ proyecto de días con resultado incierto. Decidido por **datos**, con criterio aerodinámico, no geométrico |
| **Fuente de geometría** | Catálogo de **965 `.dat`** reales de CATIA | Geometría validada, XFOIL la digiere. Portable |
| **Rol del ML: Opción 1 vs 2** | **Opción 2** (inversa + vecino más cercano) | La Opción 1 (solo filtrar catálogo) convertiría el ML en un `sort_values` → el modelo sobraría. La inversa optimiza sobre el espacio **continuo**, encuentra óptimos en huecos que ningún perfil del catálogo ocupa. Ahí vive el valor del ML |
| **Generar más perfiles genéricos** | ❌ No compensa | Modelo en meseta (400→940 mejoró poco; la mejora real vino de las features). Maldición de la dimensionalidad: rellenar 6-7D necesita miles, no cientos. Zona difícil converge al 35%. Hereda la limitación 5 |
| **Ampliar batería 8→20** | ✅ Decidido, con CATIA | Refuerza el resultado estrella (winner's curse validado). Es lo que caduca y da valor real |
| **Reparto de la batería** | Repartida por zonas, "con cabeza" | Incluye zona difícil pero con ángulos suaves (evita el pozo de convergencia del 35%). Más honesta y convincente que ir solo a lo seguro |
| **Ampliar batería 8→20** | ✅ HECHO | 20 casos (15 pares completos). k=0 error medio 22,2%; k=2 error medio 4,0% → k=2 reduce el error 5,6×. Sesgo optimista de k=0 confirmado en muestra ampliada. 12 .dat estrella (k=2) guardados en bateria_ampliada_stars/. Casos 12/14/15 con convergencia parcial (normal en XFOIL). |
| **Arreglar limitación 5 (TE)** | ✅ HECHO (2026-07-24) | Se regeneró el dataset con TE-real, se reentrenaron los modelos y se revalidó la batería (k=2 4,1%). Promocionado a producción. Resultado clave: el 7º parámetro NO se reconecta → es restricción de fabricación, no variable aero |
| **Archivos de la Fase 1** | Conservar | Evidencia de "exploré, medí, decidí con datos". Suma en README/LinkedIn |

---

## 3. El núcleo (cerrado, no se toca)

Recordatorio del estado técnico, ya validado (detalle completo en CLAUDE.md):

- **Generar:** CATIA (COM) → puntos → `.asc` → `.dat` → XFOIL. Reynolds derivado de cuerda+velocidad.
- **Aprender:** surrogates con 11 features (7 forma + alpha + Re + `alpha/√Re` + `te_rel`). **XGBoost para CL, CD y LD** (CL pasó de lineal a XGBoost el 2026-07-24, ver §aprendizaje de modelado abajo).
- **Invertir:** `inversa_ld_v2.py`. Zona fiable p5–p95 + penalización `J = mean_ens + k·σ` (k=2). **Validada a ~2,5% de error.**
- **Dataset:** 989 perfiles / 20.769 filas / 15.107 ok / 19 columnas. **965 con `.dat` archivado.**

### Limitaciones conocidas (decisiones conscientes, documentadas)

> Numeración alineada al pie de la letra con la tabla del CLAUDE.md (§ "Limitaciones conocidas"). Detalle completo allí.

1. **`te_rel` confundido con la cuerda** — el espesor de TE se sortea en mm absolutos, así que `te_rel` es en buena parte un proxy del inverso de la cuerda (corr. −0.662). Sin daño medido. Corregirlo exige regenerar el dataset.
2. **Saturación del TE en 1 mm** — el optimizador satura el mínimo de `trailing_edge_thickness_mm`; el óptimo aerodinámico está por debajo del rango, pero 1 mm es el límite de fabricación en composite. No es un fallo, es una restricción real.
3. ✅ **RESUELTA — Kink de 42.1° en el TE del `.dat`** — lo creaba el corte de `asc_to_dat.py`. Con el dataset TE-real (TE romo por hueco) el kink desaparece. Resuelta junto con la limitación 5.
4. **Join `AIRFOIL` de CATIA no es extruible** — duplica extradós/intradós, que ya están dentro de `LE ARC` (~1268 mm ≈ 2× el perímetro real). El `.dat` sale de la nube de puntos, no del join; no afecta a ningún resultado.
5. ✅ **RESUELTA (2026-07-24) — `trailing_edge_thickness_mm` ya llega a XFOIL.** Se regeneró todo el dataset con el conversor **TE-real** (TE romo, sin la constante `0.03`) y se promocionó a producción; batería revalidada (k=0 23,9% / k=2 4,1%). **Hallazgo confirmado en dos datasets:** aun llegando a XFOIL, el 7º parámetro sigue siendo señal débil → es **restricción de fabricación** (mín. 1 mm en composite), no variable aerodinámica libre. Universo viejo archivado en `legacy/`.

Otras limitaciones conocidas (documentadas en secciones aparte del CLAUDE.md, no dentro de la tabla numerada): no hay Gurney flap (XFOIL no modela flujo separado fiable); la geometría 3D es solo visual, excluida del cálculo aero; `plot_cp.py` tiene un bug conocido (usar `cp_on_demand.py`); rango de cuerda soportado 150-500 mm.

### Aprendizaje de modelado: CL lineal → XGBoost (2026-07-24)

**CL es lineal en el ángulo de ataque pero NO en el Reynolds.** La elección inicial de
regresión lineal para CL se basó en la primera dimensión e ignoró la segunda,
arrastrando un sesgo sistemático del ~4.4% (visible en el barrido de velocidad del
perfil 0014). Corregido pasando CL a XGBoost: MAE −62% (0.0595 → 0.0227), R² 0.930 →
0.984, mejora en las 3 zonas de cuerda y los 8 ángulos, sesgo del barrido 4.4% → 1.4%.
**Lección: un razonamiento físico correcto pero incompleto puede llevar a una decisión
de modelado subóptima; se detectó VISUALIZANDO, no analizando.**

---

## 4. Preguntas abiertas (a resolver, no resueltas aún)

Estas son las ramas que fueron apareciendo. Ninguna bloquea empezar, pero hay que decidirlas antes de cerrar el producto.

### 4.1 Acoplamiento cuerda ↔ Reynolds (la más importante)
El usuario pide una cuerda. **La cuerda cambia el Reynolds, y el Reynolds cambia el comportamiento.** Un perfil óptimo a 250 mm / 180 km/h no es necesariamente óptimo a 400 mm / 180 km/h.
- **Pregunta:** cuando el usuario pide cuerda X, ¿la inversa **re-optimiza los parámetros PARA esa cuerda** (recalculando Re) — lo riguroso — o se adapta un perfil que fue óptimo a otra cuerda (más simple, menos correcto)?
- Afecta a las dos ramas de entrega.

### 4.2 Brecha vecino ↔ óptimo (Rama 1)
El `.dat` del catálogo es el vecino más cercano, no el óptimo exacto. Convertible en fortaleza: mostrar al usuario "óptimo teórico predicho = L/D X; perfil real entregado = L/D Y; la diferencia es tu margen de mejora en CAD".

### 4.3 Portabilidad del pack CATIA (Rama 2)
`airfoil_generator.py` está escrito para el montaje actual (versión de CATIA, rutas, COM). En otra máquina probablemente necesite ajustes. **Y tras devolver el equipo no se podrá probar en otros entornos.**
- **Acción:** blindar y probar el pack AHORA (ver Fase 1). Documentar honestamente lo que no se pueda verificar fuera del PC propio.

### 4.4 Generación de variedad ("5 perfiles")
La inversa da **el** óptimo (uno). Dar 5 buenos y *distintos* es otro problema (frente de Pareto: máx L/D, mín resistencia, equilibrado…). Queda como **visión v2**.

### 4.5 Guardar los `.dat` de los óptimos de la batería
Idea: al generar la batería ampliada, archivar los `.dat` de esos 20 óptimos → para los perfiles estrella tendrías geometría real del **óptimo**, no del vecino. Mata dos pájaros con la misma tanda de CATIA.

### 4.6 Lógica de respuesta según confianza
Cuando el usuario pide una condición fuera de la zona fiable, el producto NO debe darle un perfil-espejismo ni un "no" seco. Escala honesta: (1) perfil + banda σ si es fiable; (2) perfil + aviso si σ media-alta; (3) alternativa cercana fiable si la petición es dudosa; (4) "no" honesto solo si está fuera del dominio físico. Usa σ del ensemble + tabla de convergencia por zona + p5-p95. Es lógica de software (Fase 2/3), no necesita CATIA.

### 4.7 Perfil que no converge
Dos tipos. Tipo 1 (geometría válida, XFOIL no converge en condición dura) → gestionar con la lógica 4.6. Tipo 2 (modelo predice bien un perfil malo) → YA resuelto por la corrección del winner's curse (k=2 evita los espejismos). Preferir vecino del catálogo cuando exista, porque su convergencia ya está verificada.

---

## 5. Plan del mes

Ordenado por **lo que caduca** y **lo que desbloquea**. Con puntos de corte, no con fe (aplicamos el winner's curse a la propia planificación: no planificar asumiendo que todo sale bien).

### Fase 0 — Asegurar ✅ HECHO
Backup verificado en Drive.

### Fase 1 — Lo que CADUCA (AHORA, con CATIA vivo)
Todo lo que después será imposible. **Máxima prioridad.**

| Tarea | Qué es | Estado |
|---|---|---|
| **Ampliar batería 8→20** | Generar 12 óptimos nuevos repartidos por zonas + verificarlos en XFOIL | Decidido, pendiente lanzar |
| **Guardar `.dat` de esos óptimos** | Archivar la geometría real de los 20 óptimos de la batería | A incluir en el mismo prompt |
| **Blindar y probar el pack CATIA (Rama 2)** | Parámetros + `airfoil_generator.py` + defaults + README, probado en carpeta limpia para simular "otro usuario" | Pendiente decidir si entra |

### Fase 2 — El núcleo portable (después, cualquier PC — es el corazón del portfolio)

| Tarea | Qué es |
|---|---|
| **Gráficas de producto** | Ficha CL/CD/L/D vs α con las 3 velocidades superpuestas. Partir de `eda_velocidad.py` (ya separa velocidades) + lógica de dibujo de `plot_polar.py`. Corregir el bug 18→21 condiciones. Perfil de prueba: `0014_20260711_193032` |
| **Consolidar modelo + inversa** | Que todo corra limpio. **Pendiente: que el consultor vea por fin los números reales del ML** (baterías k0/k2, ml_history, métricas por zona) — hasta ahora solo se conocen los titulares del CLAUDE.md |
| **Gráficas de método** | Las 3 fuertes para LinkedIn: winner's curse k=0 vs k=2, sigma vs error real, óptimo desplazándose con la velocidad. Datos ya en los JSON |

### Fase 3 — Empaquetado y publicación (lo último, portable)

| Tarea | Qué es |
|---|---|
| Limpiar rutas | Quitar `C:\Users\MSI-06\...` hardcodeadas (aparecen en ~6 scripts). Hacerlas configurables |
| GitHub | `.gitignore` (excluir ensemble de 62 MB, `dataset_runs/`), README, requirements. Cuenta correcta: `cvazquezb2003-afk` (no MontiMaximus) |
| README | El 80% del impacto para LinkedIn. Contar el pipeline + ML + rigor |
| Post LinkedIn | Publicación final |

### VISIÓN (se cuenta, no se construye este mes)
Se mencionan en el post como "hacia dónde va esto" — vender visión es gratis y demuestra ambición:
- Los "5 perfiles" + recomendador + web funcional
- Re-optimización por cuerda (Reynolds correcto)
- ~~Arreglar limitación 5 (recuperar 7º parámetro) → regenerar + reentrenar~~ ✅ HECHO: el 7º parámetro resultó ser restricción de fabricación, no variable aero
- Generador Python con continuidad de curvatura (G2) usando los 965 pares

---

## 6. Puntos de corte (gestión de riesgo)

- **Si la Fase 1 se alarga, se come el tiempo de la Fase 3 (empaquetado), NUNCA el del núcleo (gráficas + modelo).** Si hay que sacrificar algo, es el pulido final, no lo que da valor.
- **No enamorarse de los problemas.** Ya aplicado con éxito al generador Python (explorado, medido, descartado sin drama).
- **Un proyecto con alcance realista y bien acabado > uno que lo intentó todo y quedó a medias en cinco cosas.** Saber qué NO hacer es señal de madurez técnica, y se nota en un portfolio.

---

## 7. Estado del arte de este momento

**Siguiente acción concreta:** lanzar la Fase 1 — batería ampliada 8→20 (+ guardar `.dat` de los óptimos), y decidir si el pack CATIA entra en esta tanda.

**Decisión pendiente inmediata:** ¿el pack CATIA (Rama 2) entra en la Fase 1, o se hace solo la batería? Depende de cuánto tiempo de CATIA quede y de la tolerancia a que el pack no se pueda verificar fuera del PC propio.

---

## 8. Alternativas de ML consideradas y vías de mejora

**CONSIDERADAS Y DESCARTADAS (con motivo):**

- **Deep learning:** en datos tabulares (~15k filas, 11 features) los árboles tipo XGBoost igualan o superan a las redes neuronales. Añadiría complejidad y opacidad sin mejorar el error. Descartado por criterio técnico, no por desconocimiento.
- **Generative AI (diseño generativo inverso):** conceptualmente aplicable, pero la inversa actual (evolución diferencial sobre surrogate) ya resuelve el problema inverso, validada al 4%. Un modelo generativo añadiría fragilidad para llegar donde ya estamos. Posible vía de investigación futura, no de implementación.
- **Reinforcement learning:** no encaja — el problema no es secuencial, es optimización de una función. La evolución diferencial es más directa y estable.

**VÍAS DE MEJORA REALES DEL MODELO (ordenadas por retorno), NO ejecutadas este mes por priorizar la entrega:**

1. ✅ **HECHO — Reconectar el 7º parámetro (limitación 5):** se regeneró con TE-real y se reentrenó. Resultado: te_thickness llega a XFOIL pero **no gana señal** → es restricción de fabricación (mín. 1 mm), no variable aero. El espacio efectivo sigue siendo ~6D por física, no por bug. Ya no es una vía de mejora abierta.
2. **Más feature engineering físico:** camino probado (alpha/√Re, te_rel dieron mejoras reales). Barato, portable, rendimiento decreciente.
3. **Optimización de hiperparámetros (XGBoost):** retorno modesto (1-3%), fácil, si no se hizo sistemáticamente.
4. **Cuantificación de incertidumbre más rigurosa (conformal prediction):** no baja el error medio pero mejora la fiabilidad de σ → valor de producto.
5. **Otros modelos tabulares (LightGBM, CatBoost):** mejoras marginales probables en modelo ya en meseta.

**DECISIÓN:** el modelo está en meseta y validado al 4%, suficiente para producto y portfolio. Se prioriza la capa visual y el empaquetado sobre exprimir un 1% de error. Saber dónde están los límites y elegir conscientemente la entrega es la decisión correcta.
