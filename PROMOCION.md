# PROMOCION DE MODELOS — densificado

**Fecha:** 2026-08-06 15:05

Los modelos de produccion pasan a ser los entrenados sobre el dataset
**densificado fusionado** (`airfoil_dataset_densif_merged.csv`, 75.101 filas /
63.840 ok / 944 perfiles), en lugar de los entrenados sobre `airfoil_dataset.csv`
(20.349 filas).

## Metodo

**Renombrado**, no cambio de rutas en el codigo. Los nombres de produccion los
referencian **19 ficheros** (`inversa_service.py`, `curvas_optimo.py`,
`graficas_barrido_velocidad.py`, `winner_curse.py`, `eda_ml_filtrado150.py`, las
baterias...). Editar rutas obligaria a acertar en los 19; olvidar uno dejaria el
sistema en estado MIXTO (inversa con el modelo nuevo y curvas con el viejo), que no
da error visible sino numeros incoherentes. Ademas `eda_ml_filtrado150.py` ESCRIBE
en los nombres de produccion: un reentreno futuro habria deshecho la promocion en
silencio.

## Evidencia que respalda la promocion

- **CV GroupKFold(5) por perfil**, mismo protocolo: LD MAE 2.333 -> 2.156 (-7.6%)
  en las condiciones originales; -33.8% en todas las condiciones.
- **Bateria de 40 casos verificada en CATIA + XFOIL** (`bateria_densif_*`):
  k=2 **3.7%** (julio: 3.8%) y k=0 **6.9%** (julio: 21.5%).
  El winner's curse se reduce 3x; k=2 sigue protegiendo.
- **Bounds p5-p95 verificados identicos** (0.00% en los 7 parametros) entre el CSV
  de produccion y el fusionado: la caja de busqueda de la inversa no cambia.

## Lo que NO se promociona

- **`airfoil_dataset.csv` se queda como esta** (20.349 filas). Los bounds no cambian
  (verificado) y promocionar el fusionado romperia `confianza.contexto_catalogo`,
  que filtra `velocidad_kmh == vel` con igualdad exacta contra 110/180/290.

## Aviso

- `ensemble_ld_sigma.joblib` pasa de 66,4 MB a **105,8 MB**, por encima del limite
  duro de 100 MB de GitHub. Resolver antes de subir el repo (regenerar en destino
  con `winner_curse.py`, Git LFS, o `.gitignore`).

## Ficheros archivados (md5 verificado en destino)

Carpeta: `legacy/pre_densif_20260806/`

| fichero | bytes | md5 |
|---|---|---|
| `ensemble_ld_sigma.joblib` | 66,416,536 | `8a79825b8b6e161363606841efbb5fca` |
| `modelo_CD_xgb.joblib` | 1,062,539 | `4b3dc4b11c5b6b7144f2e885bb922907` |
| `modelo_CL_xgb.joblib` | 1,083,657 | `2a6c27724b549ac8ebc418b0bce66322` |
| `modelo_LD_inversa_meta.json` | 727 | `862f16a8c4c9ce6513dcee1c2a6f5b9f` |
| `modelo_LD_inversa_xgb.joblib` | 8,010,241 | `3a8ad2f4272687421f019bd5f97677ad` |

## Md5 de los modelos AHORA en produccion

| fichero | md5 |
|---|---|
| `ensemble_ld_sigma.joblib` | `444cf10b4038853a864e40ba9061eebb` |
| `modelo_CD_xgb.joblib` | `77b84cb0f33228da79dd3d18b1b66df0` |
| `modelo_CL_xgb.joblib` | `e668c0b5e0cfb81e6667e1538ce705f0` |
| `modelo_LD_inversa_meta.json` | `511ef4fab9bbef3ce0f883a3f3455d9d` |
| `modelo_LD_inversa_xgb.joblib` | `5500bd492b89aa30f76867f90260271c` |

## REVERSION

Copiar los 5 ficheros de vuelta a la raiz. No hay que tocar ni una linea de codigo.

```powershell
cd C:\Users\MSI-06\Desktop\catIA\notas_airfoil
Copy-Item 'legacy\pre_densif_20260806\*' -Destination . -Force -Exclude 'MANIFIESTO.json','LINEA_BASE_casos.json'
```

Despues, reiniciar el dashboard. Para comprobar que la reversion tomo efecto:

```powershell
python -c "import joblib,json; print(json.dumps(joblib.load('modelo_LD_inversa_xgb.joblib')['meta'],indent=1))"
```

El meta debe decir `dataset: filtrado_150_500` (viejo) en vez de
`densif_merged_150_500` (nuevo).

La linea base de 3 casos calculada con los modelos VIEJOS esta en
`legacy/pre_densif_20260806/LINEA_BASE_casos.json` para comprobar que la reversion restaura los valores.
