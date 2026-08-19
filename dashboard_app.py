"""
SHELL del dashboard (PORTABLE, sin CATIA). Tema oscuro (paleta estilo_graficas).
Enchufa la PARTE 1 (entrada_dashboard.py): tres puertas -> ObjetivoAngulo.

NO confundir con flask_airfoil_api.py (ese genera geometria y REQUIERE CATIA).
Este solo sirve la conversacion guiada + logica portable.

  python dashboard_app.py   ->  http://127.0.0.1:5001
"""
import os
import re
import json
from flask import Flask, jsonify, request, render_template_string, send_file

import circuitos as C
from entrada_dashboard import (primera_pregunta, resolver, construir_diseno,
                               valida_cuerda, valida_prioridad, valida_velocidad,
                               CUERDA_RAPIDAS, CUERDA_MIN, CUERDA_MAX,
                               VELOCIDAD_MIN, VELOCIDAD_MAX, VELOCIDAD_DEFAULT,
                               VELOCIDAD_RAPIDAS)
from inversa_service import optimizar
from curvas_optimo import fig_curvas_optimo, fig_ld_vs_velocidad
from vecino import encontrar_vecino, fig_cp_vecino, es_catalogo
from optimo_geom import (cp_optimo, dat_path, gen_csv_optimo, csv_path,
                         gen_step_optimo, step_path)
from rutas import XFOIL_DISPONIBLE, MSG_CP
from graficas_forma import _dat_tereal
from estilo_graficas import PALETA

app = Flask(__name__)

PAGE = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Inverted Wing Designer</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<!-- Analitica: Umami en la nube. SIN cookies y sin datos personales, asi que no
     necesita banner de consentimiento. El data-website-id es un identificador PUBLICO
     de solo escritura: viaja en el HTML de cada visita por diseno, no es un secreto y
     no da acceso al panel. `defer` para que no bloquee el render. -->
<script defer src="https://cloud.umami.is/script.js" data-website-id="66231b12-36cb-4296-84b0-cdc5968d8a46"></script>
<style>
  :root{
    --bg:{{p.fondo}}; --panel:{{p.fondo_papel}}; --txt:{{p.texto}};
    --eje:{{p.eje}}; --grid:{{p.rejilla}}; --teal:{{p.k2}}; --amber:{{p.k0}};
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--txt);
    font-family:"Segoe UI",Helvetica,Arial,sans-serif;line-height:1.5}
  header{background:var(--panel);border-bottom:1px solid var(--grid);
    padding:18px 26px;display:flex;align-items:baseline;gap:14px}
  header .dot{width:12px;height:12px;border-radius:50%;background:var(--teal);
    box-shadow:0 0 10px var(--teal)}
  header h1{font-size:20px;margin:0;font-weight:700}
  header .sub{color:var(--eje);font-size:13px}
  main{max-width:1560px;margin:28px auto;padding:0 26px}
  /* el formulario se lee mejor estrecho y centrado; los resultados usan el ancho */
  #view-design{max-width:900px;margin:0 auto}
  /* rejilla de RESULTADOS: curvas (izq) + Cp (der); colapsa a 1 columna en estrecho */
  .rgrid{display:grid;grid-template-columns:minmax(0,55fr) minmax(0,45fr);
    gap:16px;align-items:start}
  /* rejilla de COMPARE: tabla (izq) + siluetas (der).
     align-items:stretch -> las dos cajas comparten ARRIBA Y ABAJO. La tabla es
     siempre la mas alta y la unica que varia (crece con el nº de columnas y con la
     fila opcional de |CL|): con 'start' el sobrante caia abajo como escalon de
     105 px con 2 disenos y 203 px con 3, y con 'end' se iba arriba. Ninguna altura
     fija sirve, porque el desfase depende de lo que compares -> el panel de
     siluetas se estira y la grafica se CENTRA dentro, a su altura de diseno.
     Se probo estirar tambien la grafica (height=null) y se descarto: el 1:1
     aguantaba (scaleanchor reparte el alto sobrante como rango, no como escala,
     verificado a ratio 1.000000), pero el titulo va anclado a y=0.95 del papel y la
     leyenda al borde del area de trazado, que no se mueve -> con 3 disenos la
     leyenda de 3 filas se comia el titulo. Centrar deja la figura exactamente como
     esta disenada y no depende de la altura. Por debajo de 1100px la rejilla es de
     1 columna, no hay sobrante y el centrado no hace nada. */
  .cgrid{display:grid;grid-template-columns:minmax(0,56fr) minmax(0,44fr);
    gap:16px;align-items:stretch}
  #cmp-siluetas{display:flex;flex-direction:column;justify-content:center}
  @media(max-width:1100px){
    .rgrid,.cgrid{grid-template-columns:1fr}
  }
  .q{font-size:22px;font-weight:700;margin:0 0 4px}
  .qsub{color:var(--eje);font-size:14px;margin:0 0 22px}
  /* HOW TO USE: plegable, cerrado por defecto. Quien llega de un enlace sin contexto
     necesita saber que es esto; quien ya lo sabe no deberia tener que esquivarlo. Por eso
     <details> nativo: sin JS, sin dependencias y accesible por teclado de serie. */
  .howto{background:var(--panel);border:1px solid var(--grid);border-radius:12px;
    margin:0 0 18px}
  /* El indicador es el MARCADOR NATIVO de <details>: lo dibuja el navegador con su propia
     fuente, asi que no depende de soporte de emoji ni de escapes CSS. El intento anterior
     lo pintaba con ::before y un guion escrito a mano, y colo un caracter de control
     INVISIBLE (Python leyo la secuencia como escape OCTAL): se veia un cuadrado y un 3.
     No se pone display:flex en el summary: eso impide que Chrome pinte el marcador. */
  .howto>summary{cursor:pointer;padding:13px 16px;font-size:14px;font-weight:600;
    color:var(--teal);user-select:none;border-radius:12px}
  .howto[open]>summary{border-radius:12px 12px 0 0}
  .howto>summary:hover{background:var(--bg)}
  .howto .hbody{padding:4px 16px 16px;border-top:1px solid var(--grid)}
  .howto h4{margin:14px 0 3px;font-size:11px;letter-spacing:.09em;
    text-transform:uppercase;color:var(--eje);font-weight:700}
  .howto .hbody p{margin:0;font-size:14px;max-width:78ch}
  .howto .htail{margin-top:15px;padding-top:12px;border-top:1px solid var(--grid);
    font-size:13px;color:var(--eje);max-width:78ch}
  .doors{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}
  @media(max-width:640px){.doors{grid-template-columns:1fr}}
  .door{background:var(--panel);border:1px solid var(--grid);border-radius:12px;
    padding:18px;cursor:pointer;transition:border-color .15s,transform .1s;text-align:left}
  .door:hover{border-color:var(--eje);transform:translateY(-2px)}
  .door.active{border-color:var(--teal);box-shadow:0 0 0 1px var(--teal)}
  .door .lab{font-size:16px;font-weight:600;margin-bottom:6px}
  .door .desc{font-size:12.5px;color:var(--eje)}
  .panel{background:var(--panel);border:1px solid var(--grid);border-radius:12px;
    padding:20px;margin-top:18px}
  .hide{display:none}
  label{font-size:13px;color:var(--eje);display:block;margin-bottom:8px}
  select,input[type=number]{width:100%;background:var(--bg);color:var(--txt);
    border:1px solid var(--grid);border-radius:8px;padding:11px 12px;font-size:15px}
  select:focus,input:focus{outline:none;border-color:var(--teal)}
  .levels{display:flex;gap:12px;flex-wrap:wrap}
  .lvl{flex:1;min-width:120px;background:var(--bg);border:1px solid var(--grid);
    border-radius:10px;padding:14px;cursor:pointer;text-align:center;font-weight:600}
  .lvl:hover{border-color:var(--eje)}
  .lvl small{display:block;color:var(--eje);font-weight:400;margin-top:4px}
  .btn{background:var(--teal);color:#04120f;border:none;border-radius:8px;
    padding:11px 18px;font-size:15px;font-weight:600;cursor:pointer;margin-top:12px}
  .btn:hover{filter:brightness(1.08)}
  .row{display:flex;gap:12px;align-items:flex-end}
  .row>div{flex:1}
  /* resultado */
  .result{margin-top:22px}
  .badge{display:inline-block;padding:4px 12px;border-radius:20px;font-size:13px;
    font-weight:700;color:#04120f}
  .target{font-size:30px;font-weight:800;margin:12px 0 4px}
  .prio{color:var(--eje);font-size:14px;margin-bottom:14px}
  .framing{background:var(--bg);border-left:3px solid var(--teal);border-radius:6px;
    padding:14px 16px;font-size:13.5px;color:#c9d3dd}
  .framing b{color:var(--amber)}
  .q.step{font-size:19px;margin:30px 0 4px}
  .lvl.chosen{border-color:var(--teal);box-shadow:0 0 0 1px var(--teal)}
  .btn.big{padding:13px 24px;font-size:16px;margin-top:16px}
  .summary-line{font-size:16.5px;font-weight:600;line-height:1.6}
  .summary-line b{color:var(--teal)}
  pre.obj{background:var(--bg);border:1px solid var(--grid);border-radius:8px;
    padding:14px 16px;font-size:12.5px;color:#c9d3dd;overflow:auto;margin:12px 0 0}
  .nav{margin-left:auto;display:flex;gap:8px}
  .navbtn{background:transparent;color:var(--eje);border:1px solid var(--grid);
    border-radius:8px;padding:7px 14px;font-size:13px;font-weight:600;cursor:pointer}
  .navbtn:hover{color:var(--txt);border-color:var(--eje)}
  .navbtn.on{color:var(--teal);border-color:var(--teal)}
  .cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:14px}
  .card{background:var(--panel);border:1px solid var(--grid);border-radius:12px;padding:16px}
  .card .nm{font-size:16px;font-weight:700;margin-bottom:2px}
  .card .meta{font-size:12.5px;color:var(--eje);margin-bottom:10px}
  .card .ld{font-size:22px;font-weight:800;color:var(--teal)}
  .card .ldl{font-size:11.5px;color:var(--eje);margin-bottom:12px}
  .card .acts{display:flex;gap:8px}
  .mini{border-radius:7px;padding:7px 12px;font-size:12.5px;font-weight:600;cursor:pointer;
    background:transparent;border:1px solid var(--teal);color:var(--teal)}
  .mini:hover{background:rgba(27,158,138,0.12)}
  .mini.del{border-color:#8a4a3a;color:var(--amber)}
  .mini.del:hover{background:rgba(232,161,58,0.10)}
  .saverow{display:flex;gap:10px;align-items:center;margin-top:14px;flex-wrap:wrap}
  .saverow input{flex:1;min-width:200px;background:var(--bg);color:var(--txt);
    border:1px solid var(--grid);border-radius:8px;padding:10px 12px;font-size:14px}
  .empty{color:var(--eje);font-size:14.5px;padding:28px 0}
  .card.sel{border-color:var(--teal);box-shadow:0 0 0 1px var(--teal)}
  .card .pick{display:flex;align-items:center;gap:8px;font-size:12.5px;color:var(--eje);
    margin-bottom:10px;cursor:pointer;user-select:none}
  .card .pick input{width:15px;height:15px;accent-color:var(--teal);cursor:pointer}
  table.cmp{width:100%;border-collapse:collapse;font-size:13px}
  table.cmp th,table.cmp td{padding:8px 10px;border-bottom:1px solid var(--grid);text-align:right}
  table.cmp th:first-child,table.cmp td:first-child{text-align:left;color:var(--eje)}
  table.cmp thead th{color:var(--txt);font-size:13.5px;border-bottom:1px solid var(--eje)}
  table.cmp td.best{color:var(--teal);font-weight:700}
  .swatch{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px}
  .m-h{font-size:17px;font-weight:700;color:var(--teal);margin-bottom:6px}
  /* Se probo repartir el texto en COLUMNAS para que llegara al borde del panel y se
     descarto: con parrafos cortos (5-6 lineas) obliga a bajar y volver a subir para
     leer dos lineas, y se lee peor de lo que gana en equilibrio visual. Se vuelve a
     una sola columna de medida fija. */
  .m-t{font-size:14px;line-height:1.65;color:#c9d3dd;margin:0 0 14px;max-width:96ch}
  .m-t b{color:var(--txt)}
  .cargas{margin-top:18px;border-top:1px solid var(--grid);padding-top:14px}
  .cargas-h{font-size:14px;font-weight:600;color:var(--txt);margin-bottom:8px}
  table.loads td:first-child,table.loads th:first-child{text-align:right;color:var(--txt)}
  table.loads td{font-variant-numeric:tabular-nums}
  table.loads td:nth-child(3){color:var(--teal);font-weight:600}
  .cargas-n{font-size:11.5px;color:var(--eje);margin-top:9px;line-height:1.55}
  details.tech{margin-top:18px;border-top:1px solid var(--grid);padding-top:12px}
  details.tech summary{cursor:pointer;color:var(--eje);font-size:13px;font-weight:600;
    list-style:none;user-select:none}
  details.tech summary::-webkit-details-marker{display:none}
  details.tech summary:before{content:"▸ ";color:var(--teal)}
  details.tech[open] summary:before{content:"▾ "}
  details.tech summary:hover{color:var(--txt)}
  .confbox{border-left:3px solid var(--grid);background:var(--bg);border-radius:6px;
    padding:12px 14px;margin-top:12px}
  .confwhy{font-size:13px;color:#c9d3dd;margin-left:10px}
  .signal{font-size:13.5px;color:#c9d3dd}
  .signal b{color:var(--txt)}
  .signal .dim{color:var(--eje);font-size:12.5px}
  .sep{color:var(--eje);margin:0 10px}
  .confnote{font-size:12px;color:var(--eje);margin-top:7px;line-height:1.55}
  .results-bar{display:flex;align-items:center;gap:16px;margin-bottom:18px;flex-wrap:wrap}
  .backbtn{background:transparent;color:var(--teal);border:1px solid var(--teal);
    border-radius:8px;padding:9px 16px;font-size:14px;font-weight:600;cursor:pointer}
  .backbtn:hover{background:rgba(27,158,138,0.12)}
  .results-crumb{color:var(--eje);font-size:13.5px}
  .spin{display:inline-block;width:16px;height:16px;border:2px solid var(--grid);
    border-top-color:var(--teal);border-radius:50%;animation:sp .8s linear infinite;
    vertical-align:middle;margin-right:10px}
  @keyframes sp{to{transform:rotate(360deg)}}
  .kpis{display:flex;gap:30px;flex-wrap:wrap;margin:12px 0 16px}
  .kpi .v{font-size:26px;font-weight:800;color:var(--txt)}
  .kpi .l{font-size:12px;color:var(--eje);line-height:1.35}
  /* "?" con el detalle largo en tooltip nativo: la nota corta se lee de un vistazo y
     el razonamiento completo sigue disponible sin convertirse en un muro de texto */
  .qmark{display:inline-flex;align-items:center;justify-content:center;width:15px;
    height:15px;border-radius:50%;border:1px solid var(--eje);color:var(--eje);
    font-size:10.5px;line-height:1;cursor:help;vertical-align:1px;user-select:none}
  .qmark:hover{border-color:var(--teal);color:var(--teal)}
  /* PLEGABLE de validacion/explicacion. Se usa SOLO para contenido que explica o
     respalda, NUNCA para un aviso de riesgo: la caja de sigma y los avisos de dominio
     van siempre desplegados (ver renderAvisos). Plegar validacion esta bien; plegar
     una advertencia, no. */
  details.fold{margin-top:10px;border:1px solid var(--grid);border-radius:8px;
    background:rgba(22,27,34,.55)}
  details.fold>summary{list-style:none;cursor:pointer;padding:9px 12px;
    font-size:13px;color:var(--eje);display:flex;align-items:center;gap:9px;
    user-select:none}
  details.fold>summary::-webkit-details-marker{display:none}
  details.fold>summary:hover{color:var(--txt)}
  details.fold>summary .qmark{flex:0 0 auto}
  details.fold>summary:hover .qmark{border-color:var(--teal);color:var(--teal)}
  details.fold>summary .fold-hint{margin-left:auto;font-size:11.5px;opacity:.65}
  details.fold[open]>summary{border-bottom:1px solid var(--grid);color:var(--txt)}
  details.fold[open]>summary .fold-hint::after{content:'hide'}
  details.fold:not([open])>summary .fold-hint::after{content:'show'}
  .fold-body{padding:11px 13px 13px;font-size:13px;line-height:1.6;color:#c9d3dd}
  .fold-body b{color:var(--txt)}
  /* condicion de evaluacion del KPI (velocidad y agregacion): que nunca sea implicita */
  .kpi .at{font-size:10.5px;color:var(--eje);opacity:.72;letter-spacing:.2px}
  table.params{width:100%;border-collapse:collapse;font-size:13px;margin-top:6px}
  table.params td{padding:5px 8px;border-bottom:1px solid var(--grid)}
  table.params td:first-child{color:var(--eje)}
  table.params td:last-child{text-align:right;color:var(--teal);font-variant-numeric:tabular-nums}
</style></head><body>
<header>
  <span class="dot"></span>
  <h1>Inverted Wing Designer</h1>
  <span class="sub">motorsport downforce airfoils · surrogate + inverse design</span>
  <span class="nav">
    <button class="navbtn on" id="nav-design" onclick="volverDesign()">Design</button>
    <button class="navbtn" id="nav-saved" onclick="mostrarSaved()">Saved designs <span id="nav-count"></span></button>
    <button class="navbtn" id="nav-metodo" onclick="mostrarMetodo()">The method</button>
  </span>
</header>
<main>
<!-- ================= VISTA 1: DESIGN (formulario) ================= -->
<div id="view-design">
  <p class="q">{{ q.pregunta }}</p>
  <p class="qsub">Three ways in, same target: the wing's working angle. Pick whichever fits you.</p>

  <details class="howto">
    <summary>New here? How this works</summary>
    <div class="hbody">
      <h4>What this is</h4>
      <p>A tool that proposes downforce wing sections for motorsport. Instead of drawing a
        profile and then testing it, you describe what you need and it proposes the geometry.</p>

      <h4>What you give it</h4>
      <p>A circuit &mdash; or a downforce level, or an exact angle &mdash; plus the chord in
        millimetres and the speed in km/h.</p>

      <h4>What you get back</h4>
      <p>The proposed section with its predicted L/D and CD, the model's own uncertainty
        (&sigma;), a recommended angle range rather than a single number, polars across
        several speeds, the pressure distribution computed in XFOIL on that geometry, and
        sectional loads per unit span.</p>

      <h4>What you can do next</h4>
      <p>Save designs, compare two or three of them at a time &mdash; silhouettes at true
        scale in millimetres, overlaid polars and pressure distributions &mdash; and download
        the geometry as .dat, .csv or .step to take into CAD.</p>

      <h4>Where it comes from</h4>
      <p>A design space of 944 aerofoils generated in CATIA and solved in XFOIL.</p>

      <div class="htail">Generating a design takes about 30 seconds. There is a real sweep of
        32,768 candidates behind it, not a loading animation.</div>
    </div>
  </details>

  <div class="doors" id="doors">
    {% for o in q.opciones %}
    <div class="door" data-id="{{o.id}}">
      <div class="lab">{{o.label}}</div>
      <div class="desc">{{o.desc}}</div>
    </div>
    {% endfor %}
  </div>

  <!-- A: circuit -->
  <div class="panel hide" id="p-circuit">
    <label>Choose a circuit</label>
    <select id="sel-circuit"><option value="">Loading…</option></select>
    <!-- La clasificacion low/medium/high de circuitos.csv se agrupa por el perfil de
         carga TIPICO del trazado, no por datos de setup reales (que no son publicos).
         Va aqui, junto al selector, para que se lea ANTES de elegir. -->
    <div class="framing" style="margin-top:10px">Guideline based on the circuit's
      typical downforce profile — adjust to your category and setup.</div>
    <button class="btn" onclick="go('circuit', document.getElementById('sel-circuit').value)">Set target</button>
  </div>

  <!-- B: level -->
  <div class="panel hide" id="p-level">
    <label>Downforce level</label>
    <div class="levels">
      <div class="lvl" onclick="go('level','low')">Low<small>|α| 0–5°</small></div>
      <div class="lvl" onclick="go('level','medium')">Medium<small>|α| 5–9°</small></div>
      <div class="lvl" onclick="go('level','high')">High<small>|α| 9–14°</small></div>
    </div>
  </div>

  <!-- C: angle -->
  <div class="panel hide" id="p-angle">
    <div class="row">
      <div>
        <label>Target |α| (degrees, 0–14)</label>
        <input type="number" id="in-angle" min="0" max="14" step="0.5" value="7">
      </div>
      <button class="btn" onclick="go('angle', document.getElementById('in-angle').value)">Set target</button>
    </div>
  </div>

  <!-- PASO 1: resultado del angulo -->
  <div class="panel result hide" id="result"></div>

  <!-- PASO 2a: cuerda -->
  <div id="step2" class="hide">
    <p class="q step">What chord length?</p>
    <p class="qsub" style="margin:-2px 0 10px">Regulations usually cap the chord — running close
      to the maximum allowed generates more downforce. Check your rulebook; this is only a guide.</p>
    <div class="panel">
      <div class="levels">
        <div class="lvl" onclick="setChord(250,this)">250 mm</div>
        <div class="lvl" onclick="setChord(300,this)">300 mm</div>
        <div class="lvl" onclick="setChord(450,this)">450 mm</div>
      </div>
      <div class="row" style="margin-top:14px">
        <div>
          <label>Custom (150–500 mm)</label>
          <input type="number" id="in-chord" min="150" max="500" step="10" placeholder="e.g. 320">
        </div>
        <button class="btn" onclick="setChord(document.getElementById('in-chord').value, null)">Use custom</button>
      </div>
      <div id="chord-err" class="framing hide" style="border-color:var(--amber);margin-top:12px"></div>
    </div>
  </div>

  <!-- PASO 2b: velocidad -->
  <div id="step2b" class="hide">
    <p class="q step">At what speed?</p>
    <p class="qsub" style="margin:-2px 0 10px">Average speed where the wing works (not top
      speed) — the angle of best efficiency shifts with speed.</p>
    <div class="panel">
      <div class="levels">
        <div class="lvl" onclick="setSpeed(110,this)">110 km/h</div>
        <div class="lvl chosen" onclick="setSpeed(180,this)">180 km/h</div>
        <div class="lvl" onclick="setSpeed(290,this)">290 km/h</div>
      </div>
      <div class="row" style="margin-top:14px">
        <div>
          <label>Custom ({{vmin}}–{{vmax}} km/h)</label>
          <input type="number" id="in-speed" min="{{vmin}}" max="{{vmax}}" step="5" placeholder="e.g. 250">
        </div>
        <button class="btn" onclick="setSpeed(document.getElementById('in-speed').value, null)">Use custom</button>
      </div>
      <div class="qsub" style="margin:12px 0 0">The model was trained at six speeds
        (110, 150, 180, 220, 250 and 290 km/h), so anything between 110 and 290 is a
        short interpolation. Outside {{vmin}}–{{vmax}} km/h the model is not reliable and
        the request is rejected.</div>
      <div id="speed-err" class="framing hide" style="border-color:var(--amber);margin-top:12px"></div>
    </div>
  </div>

  <!-- RESUMEN + boton final -->
  <div id="summary" class="panel hide">
    <div id="summary-text" class="summary-line"></div>
    <button class="btn big" onclick="disenar()">Design my airfoil</button>
  </div>

</div><!-- /view-design -->

<!-- ================= VISTA 2: RESULTS ================= -->
<div id="view-results" class="hide">
  <div class="results-bar">
    <button class="backbtn" onclick="volverDesign()">&larr; New search</button>
    <span id="results-title" class="results-crumb"></span>
    <button class="mini" id="btn-save" style="margin-left:auto" onclick="abrirGuardar()">Save this design</button>
  </div>
  <div id="save-row" class="panel hide" style="padding:14px 16px">
    <label>Name this design</label>
    <div class="saverow">
      <input type="text" id="save-name" placeholder="e.g. Monaco · 300mm · 250 km/h">
      <button class="btn" onclick="guardarDiseno()">Save</button>
      <button class="mini" onclick="hide('save-row')">Cancel</button>
    </div>
    <div id="save-msg" style="font-size:12.5px;color:var(--eje);margin-top:8px"></div>
  </div>
  <!-- KPIs del optimo: fila a todo lo ancho -->
  <div id="kpis" class="panel hide"></div>
  <!-- rejilla: curvas (izq) | Cp + descarga (der) -->
  <div class="rgrid">
    <div id="final" class="panel hide"></div>
    <div id="vecino" class="panel hide"></div>
  </div>
</div><!-- /view-results -->

<!-- ================= VISTA 3: SAVED DESIGNS ================= -->
<div id="view-saved" class="hide">
  <div class="results-bar">
    <button class="backbtn" onclick="volverDesign()">&larr; Back to design</button>
    <span class="results-crumb">Saved in this browser (localStorage)</span>
  </div>
  <p class="q step" style="margin-top:0">Saved designs</p>
  <div id="cmp-bar" class="panel hide" style="padding:12px 16px;margin-bottom:14px">
    <span id="cmp-count" style="font-size:13.5px;color:var(--eje)"></span>
    <button class="btn" style="margin-top:0;margin-left:12px" onclick="compararSel()">Compare selected</button>
    <button class="mini" style="margin-left:8px" onclick="limpiarSel()">Clear</button>
    <div id="cmp-msg" style="font-size:12.5px;color:var(--amber);margin-top:8px"></div>
  </div>
  <div id="saved-list"></div>
</div><!-- /view-saved -->

<!-- ================= VISTA 4: COMPARE ================= -->
<div id="view-compare" class="hide">
  <div class="results-bar">
    <button class="backbtn" onclick="mostrarSaved()">&larr; Back to saved</button>
    <span class="results-crumb">Comparing saved designs · no recalculation ·
      each design shown at its own design speed</span>
  </div>
  <div class="cgrid">
    <div id="cmp-table" class="panel"></div>
    <div id="cmp-siluetas" class="panel"></div>
  </div>
  <div id="cmp-curvas" class="panel" style="margin-top:16px"></div>
  <div class="panel" style="margin-top:16px">
    <button class="btn" style="margin-top:0" onclick="compararCp()">Compare Cp</button>
    <span style="font-size:12.5px;color:var(--eje);margin-left:12px">
      Runs XFOIL on each profile at its recommended angle — a few seconds the first time,
      then cached.</span>
    <div id="cmp-cp" style="margin-top:14px"></div>
  </div>
</div><!-- /view-compare -->

<!-- ================= VISTA 5: THE METHOD ================= -->
<div id="view-metodo" class="hide">
  <p class="q" style="margin-bottom:2px">How this is validated</p>
  <p class="qsub">The model proposes shapes. These are the checks that say when to trust it —
    every number below was verified against XFOIL, not assumed.</p>

  <div class="panel" style="margin-top:18px">
    <div class="m-h">1 · The winner's curse</div>
    <p class="m-t">Optimising <i>on top of a model</i> is not the same as optimising reality.
      Ask a model for its best profile and it hands you the point where it is most
      over-optimistic. We measured it: <b>{{ m.n_casos }} proposals</b> generated as real
      geometry and verified in XFOIL. Naive optimisation overshoots by <b>{{ m.d0 }}%</b>
      on average; penalising the model's own uncertainty brings it to <b>{{ m.d2 }}%</b>.
      The bias is systematic, not noise: the real profile underperforms the naive
      prediction in <b>{{ m.signos }} of {{ m.n_signos }}</b> converged cases.</p>
    <div id="m-winner"></div>
  </div>

  <div class="panel" style="margin-top:16px">
    <div class="m-h">2 · What densification changed</div>
    <p class="m-t">The curse is not a fixed property of the method — it is the
      <b>price of low-evidence corners</b>. Optimising on a model with error selects its
      largest positive error, so if you add data exactly where the model had least
      evidence, those corners stop existing and the curse shrinks on its own.</p>
    <p class="m-t">We did that: three more speeds and every intermediate angle, on the
      same geometries. The naive error fell from <b>{{ m.j0 }}%</b> to
      <b>{{ m.d0 }}%</b>, while the penalised one barely moved ({{ m.j2 }}% →
      {{ m.d2 }}%). The gap between them narrowed from <b>{{ m.jfac }}×</b> to
      <b>{{ m.dfac }}×</b> — and that is the part worth reading carefully:
      <b style="color:var(--amber)">not because the penalty stopped working, but because
      there is far less left to correct.</b></p>
    <div id="m-evol"></div>
  </div>

  <div class="panel" style="margin-top:16px">
    <div class="m-h">3 · It holds across the whole domain</div>
    <p class="m-t">A good average can hide a bad corner. Split by chord length, naive
      optimisation used to degrade most exactly where the model was confidently wrong —
      large chords, <b>{{ m.j_peor }}%</b>. That corner is now gone: the naive error sits
      between <b>{{ m.d_mejor }}%</b> and <b>{{ m.d_peor }}%</b> across all three zones,
      and the penalty still keeps the error low in every one. The correction was never a
      lucky average.</p>
    <div id="m-zona"></div>
  </div>

  <div class="panel" style="margin-top:16px">
    <div class="m-h">4 · The model knows when to doubt itself — and now has less to doubt</div>
    <p class="m-t">Every proposal carries a σ from an ensemble of models trained on
      resampled profiles: high where the data is sparse. On the earlier battery that σ
      tracked the real error well enough to be useful (Spearman ρ = {{ m.rho_j }},
      p = {{ m.p_j }}): <b>the large failures landed where σ was high</b>.</p>
    <p class="m-t">On the densified battery the correlation drops to ρ = {{ m.rho_d }}
      and is <b>no longer significant</b> (p = {{ m.p_d }}) — and that is honest to show
      rather than hide. σ did not break: it has <b>less left to rank</b>. Its range
      collapsed from {{ m.sig_j }} to {{ m.sig_d }}, and the big errors it used to sort
      have largely disappeared. It stays as a <i>guard</i> — it still refuses to be
      confident where there is no data — but it is no longer a fine-grained predictor of
      how wrong a proposal will be.</p>
    <div id="m-sigma"></div>
  </div>

  <div class="panel" style="margin-top:16px">
    <div class="m-h">5 · Predictions vs measured reality</div>
    <p class="m-t">The basic sanity check. For one profile we sweep speed continuously with
      the surrogate and overlay the <b>{{ m.n_medidas }} speeds actually computed in
      XFOIL</b> — there used to be three, before densification added the intermediate
      ones. CD and L/D land on the line; |CL| stays essentially flat with speed, which is
      what the physics says should happen, and a useful reminder that the axis, not the
      model, can dramatise a 1% difference.</p>
    <div id="m-barrido"></div>
  </div>
</div><!-- /view-metodo -->
</main>

<script>
const CAT_COLOR = {low:"{{p.k0}}", medium:"{{p.eje}}", high:"{{p.k2}}"};

// puertas: activar y mostrar su panel
document.querySelectorAll('.door').forEach(d=>{
  d.onclick=()=>{
    document.querySelectorAll('.door').forEach(x=>x.classList.remove('active'));
    d.classList.add('active');
    ['circuit','level','angle'].forEach(id=>
      document.getElementById('p-'+id).classList.toggle('hide', id!==d.dataset.id));
    document.getElementById('result').classList.add('hide');
  };
});

// cargar circuitos
fetch('/api/circuitos').then(r=>r.json()).then(data=>{
  const sel=document.getElementById('sel-circuit');
  sel.innerHTML='<option value="">— select —</option>';
  data.forEach(g=>{
    const og=document.createElement('optgroup');
    og.label=g.categoria.toUpperCase()+"  (|α| "+g.rango+")";
    g.circuitos.forEach(c=>{
      const op=document.createElement('option'); op.value=c.nombre;
      op.textContent=c.nombre+" — "+c.pais; og.appendChild(op);
    });
    sel.appendChild(og);
  });
  actualizarContador();
  _autorun();   // tras poblar el selector (por si el deep-link es un circuito)
});

// deep-link opcional (?open=circuit|level|angle & val=...) para demos/pruebas
function _autorun(){
  const q=new URLSearchParams(location.search);
  if(q.get('view')==='saved'){ mostrarSaved(); return; }
  if(q.get('view')==='method'){ mostrarMetodo(); return; }
  // demo/QA: ?seed=Monza,Suzuka,Silverstone&chord=300&then=compare
  const seed=q.get('seed');
  if(seed){ _seedYComparar(seed.split(','), +(q.get('chord')||300),
                            q.get('then')==='compare'); return; }
  const open=q.get('open'), val=q.get('val');
  if(!open) return;
  const d=document.querySelector('.door[data-id="'+open+'"]'); if(d) d.click();
  if(!val) return;
  setTimeout(()=>go(open,val), 250);
  const chord=q.get('chord');
  if(chord) setTimeout(()=>setChord(chord,null), 700);
  if(q.get('design')) setTimeout(()=>disenar(), 1500);
  const sv=q.get('save');   // guarda automaticamente cuando el resultado este listo
  if(sv) _esperaYGuarda(sv, 0);
}
// demo/QA: ejecuta el flujo REAL (mismos endpoints y mismo guardado) para N circuitos
async function _seedYComparar(nombres, chord, abrirCompare){
  for(const n of nombres){
    const inv=await (await fetch('/api/inversa',{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({modo:'circuit', valor:n, cuerda:chord})})).json();
    if(inv.error) continue;
    const opt=await (await fetch('/api/optimo',{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({shape_params:inv.shape_params, alpha_abs:inv.alpha_abs})})).json();
    const oa=inv.objetivo_angulo||{};
    LAST={inversa:inv, optimo:opt,
          summary:'Designing for: '+n+' ('+oa.categoria+' downforce, '+oa.target_str
                  +') · chord '+chord+' mm'};
    ST={modo:'circuit', valor:n, cuerda:chord, design:{summary:LAST.summary}};
    abrirGuardar(); guardarDiseno();
  }
  SEL=leerSaved().slice(0, nombres.length).map(d=>d.id);
  if(abrirCompare){ mostrarSaved(); setTimeout(()=>compararSel(), 200); }
  else mostrarSaved();
}

function _esperaYGuarda(nombre, intentos){
  if(LAST.inversa && LAST.optimo){
    abrirGuardar();
    if(nombre!=='1') document.getElementById('save-name').value=nombre;
    guardarDiseno();
    if(new URLSearchParams(location.search).get('then')==='saved')
      setTimeout(()=>mostrarSaved(), 300);
    return;
  }
  if(intentos<80) setTimeout(()=>_esperaYGuarda(nombre, intentos+1), 500);
}

// estado acumulado de las 3 preguntas
let ST={};
const reveal=id=>{const e=document.getElementById(id); if(e) e.classList.remove('hide');};
const hide=id=>{const e=document.getElementById(id); if(e) e.classList.add('hide');};
const clearChosen=sel=>document.querySelectorAll(sel).forEach(x=>x.classList.remove('chosen'));

// PASO 1: resolver el angulo y abrir el paso 2
function go(modo, valor){
  if(!valor){return;}
  fetch('/api/resolver',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({modo, valor})})
  .then(r=>r.json()).then(o=>{
    if(o.error){show_err(o.error);return;}
    const col=CAT_COLOR[o.categoria]||"{{p.k2}}";
    const box=document.getElementById('result');
    box.innerHTML=
      '<span class="badge" style="background:'+col+'">'+o.categoria.toUpperCase()+' downforce</span>'
      +(o.circuito?'<span style="color:var(--eje);margin-left:10px">'+o.circuito+'</span>':'')
      +'<div class="target">'+o.target_str+'</div>'
      +'<div class="prio">Priority: '+o.prioridad+'</div>'
      +(o.equivalencia ? '<div class="framing" style="border-color:var(--eje);margin-bottom:10px">'
        +o.equivalencia+'</div>' : '')
      +'<div class="framing">'+o.framing+'</div>';
    box.classList.remove('hide');
    // guardar y reiniciar aguas abajo
    ST={modo:modo, valor:valor, velocidad:{{vdef}}};
    clearChosen('#step2 .lvl');
    hide('summary'); hide('final'); hide('vecino'); hide('chord-err');
    hide('step2b'); hide('speed-err');
    reveal('step2');
    box.scrollIntoView({behavior:'smooth',block:'nearest'});
  });
}
function show_err(msg){
  const box=document.getElementById('result');
  box.innerHTML='<div class="framing" style="border-color:'+"{{p.k0}}"+'">'+msg+'</div>';
  box.classList.remove('hide');
}

// PASO 2a: cuerda (rango soportado 150-500)
function setChord(v, el){
  const n=Number(v);
  const err=document.getElementById('chord-err');
  if(v===''||v===null||isNaN(n)||n<{{cmin}}||n>{{cmax}}){
    err.textContent='Chord out of supported range: must be between {{cmin}} and {{cmax}} mm '
      +'(the system is not reliable outside this range).';
    reveal('chord-err');
    hide('step2b'); hide('summary'); hide('final');
    return;
  }
  hide('chord-err');
  ST.cuerda=n;
  clearChosen('#step2 .lvl'); if(el) el.classList.add('chosen');
  hide('final'); hide('vecino');
  reveal('step2b');                       // PASO 2b: velocidad
  if(ST.velocidad==null) ST.velocidad={{vdef}};
  _resumen();
}

// PASO 2b: velocidad (rango soportado 95-330; default 180 = comportamiento historico)
function setSpeed(v, el){
  const n=Number(v);
  const err=document.getElementById('speed-err');
  if(v===''||v===null||isNaN(n)||n<{{vmin}}||n>{{vmax}}){
    err.textContent='Speed out of supported range: must be between {{vmin}} and {{vmax}} km/h '
      +'(the system is not reliable outside this range).';
    reveal('speed-err');
    hide('summary'); hide('final');
    return;
  }
  hide('speed-err');
  ST.velocidad=n;
  clearChosen('#step2b .lvl'); if(el) el.classList.add('chosen');
  hide('final'); hide('vecino');
  _resumen();
}

// resumen (sin prioridad) + boton de disenar. Comun a cuerda y velocidad.
function _resumen(){
  if(ST.cuerda==null) return;
  fetch('/api/disenar',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify(ST)})
  .then(r=>r.json()).then(d=>{
    if(d.error){document.getElementById('summary-text').innerHTML=
      '<span style="color:{{p.k0}}">'+d.error+'</span>'; reveal('summary'); return;}
    ST.design=d;
    // la velocidad YA viene dentro de d.summary (entrada_dashboard._resumen): no se
    // concatena aqui, para que la cabecera y el nombre por defecto no diverjan
    document.getElementById('summary-text').innerHTML='<b>Summary</b> · '+d.summary;
    reveal('summary');
    document.getElementById('summary').scrollIntoView({behavior:'smooth',block:'nearest'});
  });
}

// ---------- NAVEGACION entre las 3 vistas (mismo DOM: no se pierde nada) ----------
let LAST={};                       // ultimo resultado calculado (para guardar)
const VIEWS=['view-design','view-results','view-saved','view-compare','view-metodo'];
const CMPC=['#1b9e8a','#e8a13a','#a06cd5'];   // = COMPARE_COLORS (estilo_graficas)
let SEL=[];
// Velocidad de un guardado. Los ANTERIORES a C5 no la traen: eran 180 por la constante
// cableada de la inversa, no por suposicion. Se marca con † alla donde se muestre.
const CMPVEL_LEGACY=180;
function velDis(d){
  if(d.velocidad_kmh!=null) return Number(d.velocidad_kmh);
  if(d.inversa&&d.inversa.velocidad_kmh!=null) return Number(d.inversa.velocidad_kmh);
  return CMPVEL_LEGACY;
}
function velAsumida(d){
  return !(d.velocidad_kmh!=null||(d.inversa&&d.inversa.velocidad_kmh!=null));
}
function irA(v){
  VIEWS.forEach(x=>{ x===v ? reveal(x) : hide(x); });
  const nd=document.getElementById('nav-design'), ns=document.getElementById('nav-saved'),
        nm=document.getElementById('nav-metodo');
  const enSaved=(v==='view-saved'||v==='view-compare'), enMet=(v==='view-metodo');
  nd.classList.toggle('on', !enSaved&&!enMet);
  ns.classList.toggle('on', enSaved); nm.classList.toggle('on', enMet);
  window.scrollTo({top:0,behavior:'instant'});
}
function mostrarResults(){ irA('view-results'); }
function volverDesign(){ irA('view-design'); }
function mostrarSaved(){ pintarSaved(); irA('view-saved'); }

// ---------- THE METHOD (graficas de rigor; se piden una vez y se cachean) ----------
let METODO=null;
function mostrarMetodo(){
  irA('view-metodo');
  if(METODO){ return; }
  const slots=[['m-winner','winner'],['m-evol','evolucion'],['m-zona','zona'],
               ['m-sigma','sigma'],['m-barrido','barrido']];
  slots.forEach(s=>{document.getElementById(s[0]).innerHTML=
    '<div style="font-size:14px;color:var(--eje)"><span class="spin"></span>Loading chart…</div>';});
  fetch('/api/metodo').then(r=>r.json()).then(o=>{
    if(o.error){return;}
    METODO=o;
    slots.forEach(s=>{
      const f=o[s[1]]; if(!f) return;
      document.getElementById(s[0]).innerHTML='';
      const lay=f.layout; lay.width=null; lay.autosize=true;
      Plotly.newPlot(s[0], f.data, lay, {displayModeBar:false, responsive:true});
    });
  });
}

// ---------- ALMACENAMIENTO (localStorage; sin backend, sin login) ----------
const SKEY='iwd_saved_designs_v1';
function leerSaved(){
  try{ return JSON.parse(localStorage.getItem(SKEY)||'[]'); }catch(e){ return []; }
}
function escribirSaved(arr){
  try{ localStorage.setItem(SKEY, JSON.stringify(arr)); return true; }
  catch(e){ return false; }
}
function actualizarContador(){
  const n=leerSaved().length;
  document.getElementById('nav-count').textContent = n ? '('+n+')' : '';
}

// Nombre de fichero para las descargas, con los parametros del diseno.
// MISMA receta que el nombre de la leyenda y del guardado (ver abrirGuardar):
// circuito o nivel + cuerda + velocidad. Si los dos nombres divergieran, el
// fichero en disco dejaria de poder emparejarse con el diseno guardado.
function nombreFichero(){
  const o=LAST.inversa; if(!o) return '';
  const oa=o.objetivo_angulo||{};
  const base=(oa.circuito || ((oa.categoria||'design')+' downforce'));
  return (base+' '+Math.round(o.cuerda_mm)+'mm '+fmtV(velDis(o))+'kmh')
    .normalize('NFD').replace(/[\\u0300-\\u036f]/g,'')   // Monaco, no M_naco
    .replace(/[^A-Za-z0-9]+/g,'_').replace(/^_+|_+$/g,'');
}
function conNombre(url){
  const n=nombreFichero();
  return n ? (url+'?n='+encodeURIComponent(n)) : url;
}

function abrirGuardar(){
  const o=LAST.inversa; if(!o) return;
  const oa=o.objetivo_angulo||{};
  // la velocidad forma parte del nombre: mismo circuito y misma cuerda a 180 o a 250
  // son disenos DISTINTOS (distinto angulo, distintos KPIs) y sin ella se confundirian
  const nombre=(oa.circuito || ((oa.categoria||'design')+' downforce'))
               +' · '+Math.round(o.cuerda_mm)+'mm'
               +' · '+fmtV(velDis(o))+' km/h';
  document.getElementById('save-name').value=nombre;
  document.getElementById('save-msg').textContent='';
  reveal('save-row');
  document.getElementById('save-name').focus();
}

function guardarDiseno(){
  const o=LAST.inversa, g=LAST.optimo;
  if(!o){return;}
  const oa=o.objetivo_angulo||{};
  const nombre=(document.getElementById('save-name').value||'').trim()
               || ('design · '+Math.round(o.cuerda_mm)+'mm · '+fmtV(velDis(o))+' km/h');
  // Guardamos el RESULTADO YA CALCULADO (curvas y Cp incluidos) para que
  // recuperarlo sea instantaneo: no hay que reejecutar la inversa (~9s).
  const item={
    id:'d_'+Date.now()+'_'+Math.random().toString(36).slice(2,7),
    name:nombre, saved_at:new Date().toISOString(),
    circuito:oa.circuito||null, categoria:oa.categoria||null,
    banda:(oa.alpha_lo===oa.alpha_hi)?('|α| '+oa.alpha_lo+'°')
          :('|α| '+oa.alpha_lo+'–'+oa.alpha_hi+'°'),
    cuerda_mm:o.cuerda_mm, velocidad_kmh:o.velocidad_kmh, ld:Math.abs(o.LD_predicho),
    sigma:o.sigma, cd:o.CD_predicho, alpha_rec:o.alpha_recomendado_abs,
    franja:o.franja||null,              // rango del angulo (los guardados viejos no lo tienen)
    shape_params:o.shape_params,
    summary:LAST.summary||'',
    inversa:o, optimo:g||null,          // payloads completos (curvas + Cp)
    form:{modo:ST.modo, valor:ST.valor, cuerda:ST.cuerda, velocidad:ST.velocidad}
  };
  const arr=leerSaved(); arr.unshift(item);
  if(!escribirSaved(arr)){
    document.getElementById('save-msg').innerHTML=
      '<span style="color:{{p.k0}}">Could not save: browser storage is full. '
      +'Delete an older design and try again.</span>';
    return;
  }
  actualizarContador();
  document.getElementById('save-msg').innerHTML=
    '<span style="color:var(--teal)">Saved as “'+nombre+'”.</span>';
  setTimeout(()=>hide('save-row'), 900);
}

function borrarDiseno(id){
  escribirSaved(leerSaved().filter(d=>d.id!==id));
  actualizarContador(); pintarSaved();
}

function pintarSaved(){
  const arr=leerSaved(), box=document.getElementById('saved-list');
  if(!arr.length){
    box.innerHTML='<div class="empty">No saved designs yet. Run a design and use '
      +'<b>Save this design</b> to keep it here.</div>';
    return;
  }
  box.innerHTML='<div class="cards">'+arr.map(d=>{
    const f=new Date(d.saved_at);
    const fecha=f.toLocaleDateString()+' '+f.toLocaleTimeString().slice(0,5);
    const donde=d.circuito||((d.categoria||'')+' downforce');
    const on=SEL.indexOf(d.id)>=0;
    return '<div class="card'+(on?' sel':'')+'">'
      +'<label class="pick"><input type="checkbox" '+(on?'checked':'')
      +' onchange="toggleSel(&quot;'+d.id+'&quot;)"> Add to compare</label>'
      +'<div class="nm">'+esc(d.name)+'</div>'
      +'<div class="meta">'+esc(donde)+' · '+d.banda+' · chord '+Math.round(d.cuerda_mm)+' mm'
      +' · '+fmtV(velDis(d))+' km/h'+(velAsumida(d)?' †':'')+'<br>'+fecha+'</div>'
      +'<div class="ld">'+d.ld.toFixed(1)+'</div><div class="ldl">Predicted L/D (band mean)</div>'
      +'<div class="acts">'
      +'<button class="mini" onclick="verGuardado(&quot;'+d.id+'&quot;)">View</button>'
      +'<button class="mini del" onclick="borrarDiseno(&quot;'+d.id+'&quot;)">Delete</button>'
      +'</div></div>';
  }).join('')+'</div>';
  actualizarCmpBar();
}

// ---------- SELECCION para comparar (max 3) ----------
function toggleSel(id){
  const i=SEL.indexOf(id);
  const msg=document.getElementById('cmp-msg');
  if(i>=0){ SEL.splice(i,1); msg.textContent=''; }
  else{
    if(SEL.length>=3){
      msg.textContent='You can compare up to 3 designs. Unselect one first.';
      pintarSaved(); return;
    }
    SEL.push(id); msg.textContent='';
  }
  pintarSaved();
}
function limpiarSel(){ SEL=[]; document.getElementById('cmp-msg').textContent=''; pintarSaved(); }
function actualizarCmpBar(){
  const bar=document.getElementById('cmp-bar');
  if(!leerSaved().length){ hide('cmp-bar'); return; }
  reveal('cmp-bar');
  document.getElementById('cmp-count').innerHTML=
    SEL.length ? ('<b>'+SEL.length+'</b> selected'+(SEL.length<2?' — pick at least 2':''))
               : 'Select 2–3 designs to compare.';
}

// ---------- VISTA COMPARE (velocidad fija de referencia: 180 km/h) ----------
function compararSel(mantener){
  const arr=leerSaved(), ds=SEL.map(id=>arr.find(d=>d.id===id)).filter(Boolean);
  if(ds.length<2){
    document.getElementById('cmp-msg').textContent='Select at least 2 designs to compare.';
    return;
  }
  if(!mantener) irA('view-compare');
  // El Cp es el UNICO panel de Compare que no se repinta aqui (se pide a demanda con
  // el boton). Si no se vacia, el grafico del conjunto ANTERIOR sigue colgado en el
  // DOM bajo la tabla del conjunto nuevo: dos perfiles distintos presentados como si
  // fueran el mismo. Se vacia, no se re-pide: XFOIL tarda la primera vez y el Cp es
  // deliberadamente bajo demanda. El cache por (perfil, vel, alpha) del backend NO se
  // toca, asi que volver a un conjunto ya calculado sigue siendo instantaneo.
  document.getElementById('cmp-cp').innerHTML='';
  renderCmpTabla(ds, null);          // tabla ya visible; el |CL| llega con la respuesta
  const cur=document.getElementById('cmp-curvas');
  cur.innerHTML='<div style="font-size:15px"><span class="spin"></span>Building comparison…</div>';
  fetch('/api/comparar',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({disenos:ds.map(d=>({
      name:d.name, shape_params:d.shape_params, velocidad_kmh:velDis(d),
      banda_lo:(d.inversa&&d.inversa.objetivo_angulo)?d.inversa.objetivo_angulo.alpha_lo:null,
      banda_hi:(d.inversa&&d.inversa.objetivo_angulo)?d.inversa.objetivo_angulo.alpha_hi:null}))})})
  .then(r=>r.json()).then(o=>{
    if(o.error){cur.innerHTML='<div class="framing" style="border-color:{{p.k0}}">'+o.error+'</div>';return;}
    if(o.cl_banda) renderCmpTabla(ds, o.cl_banda);   // repinta con la fila de |CL|
    cur.innerHTML='<div id="cmp-curvas-plot"></div>';
    let l1=o.curvas.layout; l1.width=null; l1.autosize=true;
    Plotly.newPlot('cmp-curvas-plot', o.curvas.data, l1, {displayModeBar:false, responsive:true});
    document.getElementById('cmp-siluetas').innerHTML='<div id="cmp-sil-plot"></div>';
    // se anula el width para que siga al panel, pero NO el height: la grafica
    // conserva su altura de diseno y el CSS la centra en el panel estirado (ver
    // el comentario de .cgrid: estirarla descolocaba el titulo con 3 disenos)
    let l2=o.siluetas.layout; l2.width=null; l2.autosize=true;
    Plotly.newPlot('cmp-sil-plot', o.siluetas.data, l2, {displayModeBar:false, responsive:true});
  });
}

// Cp SUPERPUESTO — bajo demanda (XFOIL es lento; luego va de cache)
function compararCp(){
  const arr=leerSaved(), ds=SEL.map(id=>arr.find(d=>d.id===id)).filter(Boolean);
  const box=document.getElementById('cmp-cp');
  if(ds.length<2){box.innerHTML='<div class="framing" style="border-color:var(--amber)">'
    +'Select 2 or 3 designs first.</div>';return;}
  box.innerHTML='<div style="font-size:14px;color:var(--eje)"><span class="spin"></span>'
    +'Running XFOIL at each profile’s recommended angle…</div>';
  fetch('/api/comparar_cp',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({disenos:ds.map(d=>({
      name:d.name, shape_params:d.shape_params, alpha_rec:d.alpha_rec,
      velocidad_kmh:velDis(d)}))})})
  .then(r=>r.json()).then(o=>{
    if(o.error){box.innerHTML='<div class="framing" style="border-color:{{p.k0}}">'+o.error+'</div>';return;}
    // MODO WEB: mismo aviso que en Results, mismo estilo informativo. El boton
    // sigue visible a proposito: comunica que la capacidad existe, no aqui.
    if(o.no_disponible){
      box.innerHTML='<div class="framing"><b>Local version only.</b> '+esc(o.aviso)+'</div>';
      return;
    }
    box.innerHTML='<div id="cmp-cp-plot"></div>';
    const lay=o.cp.layout; lay.width=null; lay.autosize=true;
    Plotly.newPlot('cmp-cp-plot', o.cp.data, lay, {displayModeBar:false, responsive:true});
  });
}

function renderCmpTabla(ds, clBanda){
  const ld=ds.map(d=>d.ld), sg=ds.map(d=>d.sigma);
  const bLD=Math.max.apply(null,ld), bSG=Math.min.apply(null,sg);
  let h='<table class="cmp"><thead><tr><th>Attribute</th>';
  ds.forEach((d,i)=>{h+='<th><span class="swatch" style="background:'+CMPC[i%3]+'"></span>'+esc(d.name)+'</th>';});
  h+='</tr></thead><tbody>';
  const fila=(lab,vals,best)=>{
    let r='<tr><td>'+lab+'</td>';
    vals.forEach(v=>{r+='<td'+(best!==undefined&&v.raw===best?' class="best"':'')+'>'+v.txt+'</td>';});
    return r+'</tr>';
  };
  // velocidad de diseno por columna: los guardados ANTIGUOS no la tienen -> 180,
  // que es lo que se uso siempre antes de la feature C5 (no es una suposicion:
  // era la constante cableada)
  const vDis=ds.map(velDis);
  const vUnica=vDis.every(v=>v===vDis[0]);
  let algunaVelAsumida=false;
  h+=fila('Circuit / level', ds.map(d=>({txt:esc(d.circuito||((d.categoria||'')+' downforce'))})));
  h+=fila('Target band', ds.map(d=>({txt:d.banda})));
  h+=fila('Chord (mm)', ds.map(d=>({txt:Math.round(d.cuerda_mm)})));
  h+=fila('Design speed (km/h)', ds.map((d,i)=>{
    if(velAsumida(d)){ algunaVelAsumida=true;
      return {txt:fmtV(vDis[i])+'<span style="color:var(--eje)"> †</span>'}; }
    return {txt:fmtV(vDis[i])};
  }));
  // Verde SOLO en |L/D| (lo que optimiza la inversa) y σ (menor = mejor, sin ambiguedad).
  // CD y CL se miden en bandas distintas -> resaltarlos sugeriria una competicion que no existe.
  h+=fila('Predicted |L/D| (own band)', ds.map(d=>({txt:d.ld.toFixed(1), raw:d.ld})), bLD);
  if(clBanda && clBanda.length===ds.length && clBanda[0]!=null){
    // El CL se calcula ahora a la velocidad de CADA diseno, igual que L/D, CD y sigma
    // (antes iba a CMPVEL fija y la tabla mezclaba dos marcos).
    h+=fila('Predicted |CL| (own band)', clBanda.map(v=>({txt:v.toFixed(3)})));
  }
  h+=fila('Predicted CD (own band)', ds.map(d=>({txt:d.cd.toFixed(4)})));
  h+=fila('Uncertainty σ (own band)', ds.map(d=>({txt:'±'+d.sigma.toFixed(2), raw:d.sigma})), bSG);
  // ANGULO: franja por sigma si el guardado la trae; los guardados ANTIGUOS solo
  // tienen el punto, y se muestra como punto marcado, sin inventarles un rango.
  let algunoViejo=false;
  h+=fila('Recommended |α|', ds.map(d=>{
    const f=d.franja||(d.inversa&&d.inversa.franja)||null;
    if(!f){ algunoViejo=true;
      return {txt:d.alpha_rec+'°<span style="color:var(--eje)"> †</span>'}; }
    return {txt:f.texto};
  }));
  // Nota SINTETIZADA: 3 frases cortas en lineas propias en vez de un parrafo de 6
  // lineas que nadie lee. El detalle largo (por que no es like-for-like, que es la
  // franja del angulo) pasa al tooltip del "?": sigue estando, pero no estorba.
  const NL='\\n\\n';
  const detalle=
     'Why the columns are not directly comparable:'+NL
    +'• Each design is evaluated inside its OWN target band, so the numbers come from '
    +'different angles of attack. A low-angle design will always show less drag — that '
    +'is the band, not the quality of the shape.'+NL
    +(vUnica ? '• All designs share the same design speed ('+fmtV(vDis[0])+' km/h).'+NL
             : '• Each design is also evaluated at ITS OWN design speed, so part of the '
               +'gap between two columns is simply speed. Higher speed means higher '
               +'Reynolds and better L/D for the same shape.'+NL)
    +'• The recommended angle is a RANGE: every angle inside it sits within one sigma '
    +'of the best, so the model does not resolve between them.'+NL
    +'• Green marks only the best |L/D| and the lowest sigma. CD and CL are not '
    +'highlighted: measured in different bands, a winner would be meaningless.'
    +((algunoViejo||algunaVelAsumida)
      ? NL+'† Saved before this existed — '
        +(algunoViejo?'angle shown as a single value':'')
        +((algunoViejo&&algunaVelAsumida)?'; ':'')
        +(algunaVelAsumida?'speed taken as 180 km/h, the fixed value back then':'')+'.'
      : '');
  h+='</tbody></table><div style="font-size:12.5px;color:var(--eje);margin-top:12px;line-height:1.75">'
    +'<div><b style="color:var(--txt)">Not a like-for-like comparison.</b> Each design is '
    +'measured in its own target band'
    +(vUnica ? ' at '+fmtV(vDis[0])+' km/h' : ' <b style="color:var(--amber)">and at its own speed</b>')
    +' — so part of the gap is the setup, not the shape. '
    +'<span class="qmark" title="'+detalle.replace(/"/g,'&quot;')+'">?</span></div>'
    +'<div><b style="color:var(--txt)">Green</b> marks only the best |L/D| and the lowest σ.</div>'
    +'<div><b style="color:var(--txt)">The shapes below</b> are the one comparison that does not '
    +'depend on speed or angle at all.</div>'
    +'<div style="opacity:.8">Nothing was recalculated — all values come from the saved results.'
    +((algunoViejo||algunaVelAsumida)?' <b>†</b> older saves, see the note.':'')+'</div>'
    +'</div>';
  // los 7 parametros de forma NO se muestran (lenguaje interno del modelo)
  document.getElementById('cmp-table').innerHTML=h;
}

function esc(s){return String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}

// RESTAURAR un guardado: repinta la vista Results SIN recalcular (instantaneo)
function verGuardado(id){
  const d=leerSaved().find(x=>x.id===id); if(!d) return;
  LAST={inversa:d.inversa, optimo:d.optimo, summary:d.summary};
  if(d.form){ ST=Object.assign({}, ST, d.form); ST.design={summary:d.summary}; }
  document.getElementById('results-title').textContent=d.summary||d.name;
  hide('save-row');
  renderOptimo(d.inversa);
  if(d.optimo){ renderOptimoGeom(d.optimo); } else { hide('vecino'); }
  mostrarResults();
  // asegura que el .dat del guardado sigue disponible en el servidor (rapido)
  if(d.shape_params){
    fetch('/api/redat',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({shape_params:d.shape_params})}).catch(()=>{});
  }
}

// BOTON FINAL: cambia a la vista Results, corre la inversa (spinner) y pinta el optimo
function disenar(){
  mostrarResults();
  document.getElementById('results-title').textContent =
    (ST.design && ST.design.summary) ? ST.design.summary : '';
  hide('vecino'); hide('save-row'); hide('kpis'); LAST={};
  const box=document.getElementById('final');
  box.innerHTML='<div style="font-size:15px"><span class="spin"></span>Optimising your airfoil…</div>';
  reveal('final');
  fetch('/api/inversa',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify(ST)})
  .then(r=>r.json()).then(o=>{
    if(o.error){box.innerHTML='<div class="framing" style="border-color:{{p.k0}}">'+o.error+'</div>';return;}
    LAST.inversa=o; LAST.summary=(ST.design&&ST.design.summary)||'';
    renderOptimo(o);
    fetchOptimoGeom(o.shape_params, o.alpha_abs);
  });
}

// formato corto de velocidad: 180 y no 180.0, pero 187.5 se conserva
function fmtV(v){ const n=Number(v); return (n%1===0)? String(n) : String(n); }

// AVISOS DE DOMINIO + SIGMA, COMO UNA SOLA SEÑAL.
// Un aviso de velocidad y una sigma disparada no son dos hallazgos: son el mismo hecho
// visto desde dos sitios (el dominio dice "aqui no hay datos", el ensemble lo confirma
// con su dispersion). Presentarlos en cajas separadas obligaria al usuario a
// correlacionarlos, que es justo el trabajo que deberia hacer la interfaz.
function renderAvisos(o){
  const av=o.avisos||[];
  if(!av.length && !o.sigma_alta) return '';
  const velAv=av.filter(a=>a.etiqueta.indexOf('SPEED')>=0 || a.etiqueta.indexOf('REYNOLDS')>=0);
  const otros=av.filter(a=>velAv.indexOf(a)<0);
  let h='';
  if(velAv.length && o.sigma_alta){
    // CASO UNIFICADO: dominio y modelo dicen lo mismo
    h+='<div class="framing" style="border-color:var(--amber);margin-top:10px">'
      +'<b style="color:var(--amber)">Outside the evaluated range — and the model agrees.</b> '
      +'Two independent signals point the same way here. '
      +velAv.map(a=>a.mensaje).join(' ')
      +' <b>And the model\\'s own uncertainty confirms it:</b> σ = '+o.sigma.toFixed(2)
      +', above the 1.2 threshold. That threshold was calibrated on the earlier XFOIL '
      +'battery, where σ &gt; 1.2 meant ~17% measured error against ~2% below 0.6; on the '
      +'densified battery σ barely reaches 1.2 at all, so crossing it is now a rarer and '
      +'stronger signal. The domain guard says there is no data here; the ensemble, which '
      +'knows nothing about that guard, is spreading out for the same reason. Treat these '
      +'numbers as indicative and verify in XFOIL.'
      +'</div>';
  }else{
    velAv.forEach(a=>{ h+='<div class="framing" style="border-color:var(--amber);margin-top:10px">'
      +'<b style="color:var(--amber)">'+esc(a.etiqueta.replace(/^\\[!+\\]\\s*/,''))+'.</b> '
      +a.mensaje+'</div>'; });
    if(o.sigma_alta && !velAv.length){
      h+='<div class="framing" style="border-color:var(--amber);margin-top:10px">'
        +'<b style="color:var(--amber)">High uncertainty.</b> σ = '+o.sigma.toFixed(2)
        +' — the model has seen little evidence around this design. Verify in XFOIL.'
        +'</div>';
    }
  }
  otros.forEach(a=>{ h+='<div class="framing" style="border-color:var(--amber);margin-top:10px">'
    +'<b style="color:var(--amber)">'+esc(a.etiqueta.replace(/^\\[!+\\]\\s*/,''))+'.</b> '
    +a.mensaje+'</div>'; });
  return h;
}

// render del OPTIMO (reutilizable: sirve para calculo nuevo y para restaurar guardados)
function renderOptimo(o){
    const box=document.getElementById('final');
    const oa=o.objetivo_angulo, lo=oa.alpha_lo, hi=oa.alpha_hi;
    const band=(lo===hi)?('|α| = '+lo+'°'):('|α| '+lo+'–'+hi+'°');
    // VU = velocidad REALMENTE usada (viene del backend, no se asume 180)
    const VU=fmtV(o.velocidad_kmh), AT='mean over band · @'+VU+' km/h';
    const FR=o.franja||null;
    // El angulo se presenta como FRANJA, no como punto: dentro de ella el modelo no
    // distingue el L/D de forma significativa, asi que dar 1° seria fingir resolucion.
    // PLEGADA: explica el POR QUE del rango. El rango en si ya esta arriba en el KPI,
    // que es lo accionable; esto es el razonamiento que lo respalda.
    const rec=!FR ? '' :
      '<details class="fold"><summary><span class="qmark">?</span>'
      +(FR.es_punto ? 'How the recommended angle was chosen'
                    : 'Why a range, not a single angle')
      +'<span class="fold-hint"></span></summary><div class="fold-body">'
      +(FR.es_punto
        ? 'The recommended angle is where this optimum reaches its best L/D inside the '
          +lo+'–'+hi+'° band, evaluated at <b>'+VU+' km/h</b>.'
        : '<b>Why a range and not a single angle.</b> The best predicted L/D lands at '
          +'<b>'+FR.argmax+'°</b>, but every angle from <b>'+FR.lo+'° to '+FR.hi+'°</b> '
          +'sits within one σ of it: the ends of that range give up only '
          +'<b>'+FR.delta_extremos.toFixed(2)+'</b> in L/D, against the σ = '
          +FR.sigma_ref.toFixed(2)+' shown above — the model cannot rank them apart. '
          +'Quoting a single degree would claim a precision the model does not have. '
          +'Set up anywhere in this range and pick the end that suits the rest of the car.')
      +' Evaluated at <b>'+VU+' km/h</b> — your speed, and the one used for every headline '
      +'number below. At higher speed the best angle shifts to a more aggressive setting '
      +'(Reynolds effect). This is guidance derived from the circuit type, not a setup.'
      +'</div></details>';
    // KPIs: fila propia a todo lo ancho (incluye el angulo recomendado)
    document.getElementById('kpis').innerHTML=
      '<span class="badge" style="background:var(--teal)">THEORETICAL OPTIMUM (ML)</span>'
      +'<div class="kpis">'
      +'<div class="kpi"><div class="v">'+Math.abs(o.LD_predicho).toFixed(1)+'</div><div class="l">Predicted L/D<br><span class="at">'+AT+'</span></div></div>'
      +'<div class="kpi"><div class="v">±'+o.sigma.toFixed(2)+'</div><div class="l">Uncertainty (σ)<br><span class="at">'+AT+'</span></div></div>'
      +'<div class="kpi"><div class="v">'+o.CD_predicho.toFixed(4)+'</div><div class="l">Predicted CD<br><span class="at">'+AT+'</span></div></div>'
      +'<div class="kpi"><div class="v">'+band+'</div><div class="l">target band</div></div>'
      +'<div class="kpi"><div class="v" style="color:var(--amber)">'+VU+'</div><div class="l">design speed (km/h)<br><span class="at">Re '+_sci(o.reynolds)+'</span></div></div>'
      +(FR ? '<div class="kpi"><div class="v" style="color:var(--teal)">'+FR.texto+'</div><div class="l">'
        +(FR.es_punto?'recommended angle':'recommended angle range')
        +'<br><span class="at">'+(FR.es_punto?'best L/D in band':'within σ of the best')
        +' · @'+VU+' km/h</span></div></div>' : '')
      // "better than this share of EXISTING profiles" se leia como "un 90% mejor".
      // El numero es un PERCENTIL contra perfiles REALES medidos en XFOIL, y eso hay
      // que decirlo en la propia etiqueta: "real profiles" + la condicion de la
      // comparacion. El detalle completo va en la caja "Versus the catalogue".
      +(o.catalogo ? '<div class="kpi"><div class="v" style="color:var(--teal)">'
        +Math.round(o.catalogo.percentil)+'%</div><div class="l">better than this share of '
        +'<b>real</b><br>profiles tested at similar chord</div></div>' : '')
      +'</div>'
      +'<div id="conf-badge"></div>'
      // ORDEN DELIBERADO: primero lo ACCIONABLE (senales del modelo + avisos de
      // riesgo, siempre desplegados), despues lo plegable (validacion y explicacion).
      // renderAvisos incluye "High uncertainty" y el aviso unificado de dominio: no se
      // pliega NUNCA, es lo que protege al usuario de fiarse de un numero fragil.
      +renderAvisos(o)
      // PLEGADA: es validacion, no una decision que el usuario tenga que tomar ahora.
      // El dato accionable (el percentil) ya esta arriba como KPI; esto es el respaldo.
      +(o.catalogo ? '<details class="fold"><summary><span class="qmark">?</span>'
        +'How this compares to real profiles'
        +'<span class="fold-hint"></span></summary><div class="fold-body">'
        +'<b>What the '+Math.round(o.catalogo.percentil)+'% means.</b> It is a <b>ranking, '
        +'not a margin</b>: this optimum is predicted to beat '
        +Math.round(o.catalogo.percentil)+'% of real profiles on L/D — it is not '
        +Math.round(o.catalogo.percentil)+'% better than them. Those profiles were each '
        +'<b>built as geometry and measured in XFOIL</b>, so the yardstick is measured '
        +'reality, not theory. '
        +'This optimum sits in the <b style="color:var(--teal)">top '
        +Math.max(1,Math.round(100-o.catalogo.percentil))+'%</b> of the '+o.catalogo.n
        +' real profiles measured at a similar chord (±'+o.catalogo.tol_pct+'%) in this angle band'
        +(o.catalogo.vel_encajada
          ? ', <b>compared at '+fmtV(o.catalogo.vel_referencia)+' km/h (nearest measured speed)</b>'
            +' — the model predicts at your '+VU+' km/h, but the catalogue it is ranked '
            +'against holds XFOIL <i>measurements</i>, and those only exist at 110, 180 '
            +'and 290 km/h'
          : '')+': '
        +'<b style="color:var(--teal)">'+(o.catalogo.vs_mediana_pct>=0?'+':'')
        +Math.round(o.catalogo.vs_mediana_pct)+'%</b> vs the typical profile and '
        +'<b>'+(o.catalogo.vs_p90_pct>=0?'+':'')+Math.round(o.catalogo.vs_p90_pct)+'%</b> vs the top-10% ones. '
        +(o.catalogo.mejor_es_outlier
          ? 'The single best measurement in the catalogue reaches '+o.catalogo.mejor.toFixed(1)
            +', but that value is an outlier (unusually low drag for its shape), so it is not a fair target. '
          : 'The single best measurement reaches '+o.catalogo.mejor.toFixed(1)+'. ')
        +'Note the optimum\\'s figure is a <i>prediction</i>, the catalogue values are XFOIL <i>measurements</i>.'
        +'</div></details>' : '')
      +rec;
    reveal('kpis');
    // columna izquierda: curvas predichas + rendimiento vs velocidad
    // (los 7 parametros de forma NO se muestran: son lenguaje interno del modelo;
    //  viajan solo en el JSON de salida, bajo _internal_shape_params)
    box.innerHTML='<div id="curvas-plot"></div><div id="vel-plot" style="margin-top:14px"></div>'
      +renderCargas(o.cargas);
    reveal('final');
    // curvas predichas (Plotly), responsive dentro del panel
    if(o.curvas){
      const lay=o.curvas.layout; lay.width=null; lay.autosize=true;
      Plotly.newPlot('curvas-plot', o.curvas.data, lay,
                     {displayModeBar:false, responsive:true});
    }
    if(o.barrido){
      const l2=o.barrido.layout; l2.width=null; l2.autosize=true;
      Plotly.newPlot('vel-plot', o.barrido.data, l2,
                     {displayModeBar:false, responsive:true});
    }
}

// GEOMETRIA DEL OPTIMO REAL: .dat descargable + Cp (fallback vecino). Vecino = contexto.
function fetchOptimoGeom(sp, alpha_abs){
  const box=document.getElementById('vecino');
  box.innerHTML='<div style="font-size:15px"><span class="spin"></span>Computing the pressure distribution of your optimal profile…</div>';
  reveal('vecino');
  const inv=LAST.inversa||{};
  fetch('/api/optimo',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({shape_params:sp, alpha_abs:alpha_abs,
                         sigma:inv.sigma, nn_dist:inv.nn_dist})})
  .then(r=>r.json()).then(o=>{
    if(o.error){box.innerHTML='<div class="framing" style="border-color:{{p.k0}}">'+o.error+'</div>';return;}
    LAST.optimo=o;
    renderOptimoGeom(o);
  });
}

// Reynolds en notacion cientifica con 1 decimal: 6.2×10⁵ (el separador de miles
// local se leia mal en un dashboard en ingles: "620.396" parecia un decimal)
function _sci(v){
  if(!(v>0)) return '—';
  let e=Math.floor(Math.log10(v)), m=v/Math.pow(10,e);
  if(m.toFixed(1)==='10.0'){ m=1; e+=1; }          // 9.99e5 -> 1.0e6, no 10.0e5
  const sup={'0':'⁰','1':'¹','2':'²','3':'³','4':'⁴','5':'⁵','6':'⁶','7':'⁷','8':'⁸','9':'⁹','-':'⁻'};
  return m.toFixed(1)+'×10'+String(e).split('').map(c=>sup[c]||c).join('');
}

// TABLA DE CARGAS SECCIONALES (por unidad de envergadura, en el angulo recomendado)
function renderCargas(cg){
  if(!cg || !cg.length) return '';
  let r='', hayUser=false;
  cg.forEach(f=>{
    // la fila del usuario va destacada: es la UNICA coherente con el angulo
    // recomendado, que se decidio precisamente a esa velocidad
    const u=!!f.es_usuario; if(u) hayUser=true;
    const st=u?' style="color:var(--amber);font-weight:700"':'';
    r+='<tr'+st+'><td>'+f.V_kmh+(u?' ←':'')+'</td>'
      +'<td>'+_sci(f.reynolds)+'</td>'
      +'<td>'+f.downforce_N_por_m.toFixed(0)+'</td>'
      +'<td>'+f.drag_N_por_m.toFixed(1)+'</td></tr>';
  });
  return '<div class="cargas">'
    +'<div class="cargas-h">Sectional loads at the recommended angle'
    +(hayUser?' <span style="font-weight:400;color:var(--eje)">— <span style="color:var(--amber)">amber</span> is your design speed; the others are the dataset reference speeds</span>':'')
    +'</div>'
    +'<table class="cmp loads"><thead><tr>'
    +'<th>Speed (km/h)</th><th>Reynolds</th><th>Downforce (N/m)</th><th>Drag (N/m)</th>'
    +'</tr></thead><tbody>'+r+'</tbody></table>'
    +'<div class="cargas-n">2D estimate per unit span — does not include induced drag, '
    +'endplates, mounts, ground effect, wheels or car interaction.</div>'
    +'</div>';
}

// render de la GEOMETRIA + Cp del optimo (reutilizable para restaurar guardados)
function renderOptimoGeom(o){
    const box=document.getElementById('vecino');
    // CUATRO estados de cp_source, no dos. Antes era `fb = cp_source!=='optimum'`
    // y cualquier cosa que no fuera el optimo se anunciaba como "el Cp es de un
    // perfil cercano" — falso cuando no hay XFOIL ('unavailable') o cuando no se
    // pudo calcular ninguno ('failed'). El borde ambar se reserva para el unico
    // caso que es una salvedad sobre lo DIBUJADO: el vecino.
    const src = o.cp_source || 'optimum';
    const fb = (src === 'neighbour');
    const nota = fb
      ? 'Note: XFOIL did not converge on the optimal geometry, so the pressure distribution below is from the closest existing profile instead. The downloadable .dat is still your optimal geometry.'
      : (src === 'optimum')
      ? 'Downloadable geometry of your exact optimum — clean for CAD, real-thickness (blunt) trailing edge. Pressure distribution below is XFOIL on this optimal profile.'
      : 'Downloadable geometry of your exact optimum — clean for CAD, real-thickness (blunt) trailing edge.';
    const te = (LAST.inversa && LAST.inversa.te_entregado_mm!=null)
      ? '<div style="font-size:12.5px;color:var(--eje);margin-top:12px">TE rounded to <b style="color:var(--txt)">'
        +LAST.inversa.te_entregado_mm.toFixed(2)+' mm</b> (manufacturable increment of '
        +LAST.inversa.te_step_mm+' mm) — geometry, Cp and curves all use this value.</div>' : '';
    // RETIRADO de la UI: "Closest existing profile in the database — X% match".
    // No daba al usuario ninguna decision accionable: saber que su optimo se parece un
    // 78% a un perfil del catalogo no cambia nada de lo que va a hacer con el .dat.
    //
    // El CALCULO (vecino.encontrar_vecino) se mantiene y NO debe borrarse:
    //   - alimenta el FALLBACK del Cp (optimo_geom.cp_optimo): si XFOIL no converge
    //     sobre la geometria optima, el panel dibuja el Cp del vecino mas cercano;
    //   - lo sirve el endpoint /api/vecino;
    //   - cuesta 0.8 ms sobre 944 candidatos (medido) = 0.011% del tiempo de la
    //     inversa, asi que quitarlo no ahorraria nada.
    // El backend sigue devolviendo res["vecino"], solo que no se pinta.
    //
    // IDEA FUTURA, si se quisiera hacer accionable: un match BAJO significa que la
    // forma propuesta esta lejos de todo lo conocido, es decir, extrapolacion. Pero el
    // sitio natural para eso NO es un aviso nuevo, sino REFORZAR
    // `confianza.senales_modelo`, que ya lo hace con `nn_dist` (la misma distancia sin
    // normalizar) y con umbrales calibrados sobre el catalogo (0.33 mediana / 0.41 p90)
    // -> "within / near the edge of / outside the well-sampled region". Dos avisos
    // diciendo lo mismo con escalas distintas confundirian mas que el texto retirado.
    const ctx = '';
    // NOTA DEL ANGULO. Los tres ficheros salen a 0°, alineados con la cuerda, que
    // es el formato ESTANDAR de perfiles y ademas lo unico coherente con el
    // proyecto: el angulo de ataque lo aplica XFOIL, nunca la geometria
    // (project_to_chord_system neutraliza cualquier rotacion). Sin decirlo, es
    // facil suponer que el fichero "deberia" venir ya inclinado al angulo
    // recomendado y pensar que falta algo.
    //
    // NO se nombra un eje concreto a proposito: el .step va en el plano XZ y el
    // .csv en XY, asi que "gira sobre Z" seria correcto para uno y FALSO para el
    // otro. "En su plano" vale para los tres.
    const angTxt = (LAST.inversa && LAST.inversa.franja && LAST.inversa.franja.texto)
      ? LAST.inversa.franja.texto
      : ((LAST.inversa && LAST.inversa.alpha_recomendado_abs!=null)
          ? (LAST.inversa.alpha_recomendado_abs+'\\u00B0') : null);
    const ang = '<div style="font-size:12.5px;color:var(--eje);margin-top:10px">'
      +'Exported at <b style="color:var(--txt)">0\\u00B0</b>, aligned with the chord '
      +'\\u2014 the standard airfoil format.'
      +(angTxt ? (' To mount at the recommended angle (<b style="color:var(--txt)">'
                  +'|\\u03B1| = '+esc(angTxt)+'</b>), rotate the profile in its own '
                  +'plane in your CAD.')
               : ' To mount at the recommended angle, rotate the profile in its own '
                 +'plane in your CAD.')
      +' Keeping it at 0\\u00B0 lets you set any angle your setup needs.</div>';
    box.innerHTML=
      '<span class="badge" style="background:var(--teal)">YOUR OPTIMAL AIRFOIL</span>'
      +'<div class="framing" style="margin-top:12px'+(fb?';border-color:var(--amber)':'')+'">'+nota+'</div>'
      +'<div id="cp-optimo" style="margin-top:16px"></div>'
      +'<div style="display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-top:14px">'
      +'<a class="btn" href="'+conNombre(o.dat_url)+'" download style="margin-top:0;text-decoration:none">Download .dat — geometry</a>'
      // CSV: MISMOS puntos y MISMO orden que el .dat, escalados a mm reales por la
      // cuerda (el .dat es x/c). Para meterlo en CATIA como curva ya a escala.
      +(o.csv_url ? '<a class="btn" href="'+conNombre(o.csv_url)+'" download style="margin-top:0;'
        +'text-decoration:none">Download .csv — mm for CAD</a>' : '')
      // STEP: la MISMA curva que el .csv, ya como geometria CAD nativa (spline
      // cerrada en mm reales) para no tener que reconstruirla desde los puntos.
      +(o.step_url ? '<a class="btn" href="'+conNombre(o.step_url)+'" download style="margin-top:0;'
        +'text-decoration:none">Download .step — CAD curve</a>' : '')
      +'<button class="mini" onclick="descargarTxt()">Download summary (.txt)</button>'
      +'</div>'
      +ang+te+ctx;
    reveal('vecino');
    // MODO WEB: sin XFOIL no hay Cp. Aviso INFORMATIVO (borde teal, no ambar ni
    // rojo): no se ha roto nada, es una capacidad que vive en la version local.
    if(!o.cp && o.cp_aviso){
      // dos motivos distintos, dos encabezados distintos: falta la capacidad
      // (web sin XFOIL) o fallo el calculo sobre este perfil concreto
      const lead = (src === 'unavailable') ? 'Local version only.'
                                           : 'Cp unavailable for this profile.';
      document.getElementById('cp-optimo').innerHTML=
        '<div class="framing"><b>'+lead+'</b> '+esc(o.cp_aviso)+'</div>';
    }
    if(o.cp){const lay=o.cp.layout; lay.width=null; lay.autosize=true;
      Plotly.newPlot('cp-optimo', o.cp.data, lay, {displayModeBar:false, responsive:true});}
    if(o.senales) renderSenales(o.senales);
}

// ---------- FICHA DE SALIDA (JSON / TXT) ----------
// Se arma en el cliente con lo ya calculado: instantaneo y sirve tambien para guardados.
function _spec(){
  const inv=LAST.inversa||{}, opt=LAST.optimo||{};
  const oa=inv.objetivo_angulo||{}, cat=inv.catalogo||null, cf=opt.confianza||null;
  const sp=inv.shape_params||{};
  return {
    generated_at:new Date().toISOString(),
    design_target:{
      circuit:oa.circuito||null, downforce_level:oa.categoria||null,
      angle_band_deg:(oa.alpha_lo===oa.alpha_hi)?[oa.alpha_lo]:[oa.alpha_lo,oa.alpha_hi],
      recommended_angle_deg:inv.alpha_recomendado_abs,
      recommended_angle_range_deg:inv.franja?[inv.franja.lo,inv.franja.hi]:null,
      recommended_angle_range_note:inv.franja&&!inv.franja.es_punto
        ?"Angles within one sigma of the best predicted L/D — the model does not resolve between them."
        :null,
      chord_mm:inv.cuerda_mm
    },
    conditions:{
      evaluation_speed_kmh:inv.velocidad_kmh, reynolds:inv.reynolds,
      reference_speeds_kmh:[110,180,290],
      speed_directly_evaluated:[110,180,290].indexOf(Number(inv.velocidad_kmh))>=0,
      catalogue_compared_at_kmh:cat?cat.vel_referencia:null,
      note:"L/D, CD and sigma are band means at the evaluation speed."
    },
    domain_warnings:(inv.avisos||[]).map(a=>({label:a.etiqueta, message:a.mensaje})),
    predicted_performance:{
      LD_band_mean:inv.LD_predicho!=null?+Math.abs(inv.LD_predicho).toFixed(2):null,
      CD_band_mean:inv.CD_predicho!=null?+inv.CD_predicho.toFixed(5):null,
      uncertainty_sigma:inv.sigma!=null?+inv.sigma.toFixed(3):null,
      confidence_level:cf?cf.nivel:null,
      confidence_reasons:cf?cf.razones:null,
      data_coverage:cf?cf.zona:null,
      percentile_vs_catalogue:cat?+cat.percentil.toFixed(0):null,
      vs_typical_catalogue_pct:cat?+cat.vs_mediana_pct.toFixed(1):null,
      catalogue_profiles_compared:cat?cat.n:null
    },
    geometry:{
      trailing_edge_mm:inv.te_entregado_mm, te_rounding_step_mm:inv.te_step_mm,
      dat_file:"your_optimal_airfoil.dat", dat_normalised_by_chord:true,
      csv_file:"your_optimal_airfoil.csv", csv_units:"mm (x_mm,y_mm,z_mm; z=0)",
      cp_source:opt.cp_source||null
    },
    notes:[
      "The optimum is a MODEL PREDICTION, not a measurement. Verify in XFOIL/CFD before committing.",
      "Optimisation penalises model uncertainty (k=2) to avoid over-optimistic proposals.",
      "Trailing edge rounded to a manufacturable increment; geometry, Cp and curves all use that value.",
      "The .dat is normalised (x/c) — scale it to the chord above in your CAD.",
      "The .csv is the same points in the same order, already in mm (z=0) — import straight into CAD.",
      "Circuit-to-angle mapping is guidance from the circuit type, not a real setup."
    ],
    _internal_shape_params:Object.assign({
      _comment:"internal recipe for reproducibility — not needed for use"}, sp)
  };
}
function _bajar(nombre, texto, mime){
  const b=new Blob([texto],{type:mime}), u=URL.createObjectURL(b);
  const a=document.createElement('a'); a.href=u; a.download=nombre;
  document.body.appendChild(a); a.click(); document.body.removeChild(a);
  setTimeout(()=>URL.revokeObjectURL(u), 1500);
}
function descargarSpec(){
  const s=_spec();
  const base=(s.design_target.circuit||s.design_target.downforce_level||'airfoil')
             .toString().replace(/[^\\w-]+/g,'_')+'_'+Math.round(s.design_target.chord_mm||0)+'mm';
  _bajar(base+'_spec.json', JSON.stringify(s,null,2), 'application/json');
}
function descargarTxt(){
  const s=_spec(), p=s.predicted_performance, d=s.design_target;
  const L=[];
  L.push('INVERTED WING DESIGNER — design spec');
  L.push('generated: '+s.generated_at);
  L.push('');
  L.push('TARGET');
  L.push('  circuit / level      : '+(d.circuit||d.downforce_level||'-'));
  L.push('  angle band (|alpha|) : '+d.angle_band_deg.join('-')+' deg');
  L.push('  recommended angle    : ~'+d.recommended_angle_deg+' deg');
  L.push('  chord                : '+d.chord_mm+' mm');
  L.push('');
  L.push('PREDICTED PERFORMANCE (band mean @ '+s.conditions.evaluation_speed_kmh+' km/h, Re '+s.conditions.reynolds+')');
  L.push('  |L/D|                : '+p.LD_band_mean);
  L.push('  CD                   : '+p.CD_band_mean);
  L.push('  uncertainty (sigma)  : +/-'+p.uncertainty_sigma);
  L.push('  confidence           : '+p.confidence_level+(p.confidence_reasons?(' ('+p.confidence_reasons.join('; ')+')'):''));
  L.push('  vs catalogue         : better than '+p.percentile_vs_catalogue+'% of '+p.catalogue_profiles_compared+' real profiles ('+(p.vs_typical_catalogue_pct>=0?'+':'')+p.vs_typical_catalogue_pct+'% vs typical)');
  L.push('');
  L.push('GEOMETRY');
  L.push('  trailing edge        : '+s.geometry.trailing_edge_mm+' mm (rounded to '+s.geometry.te_rounding_step_mm+' mm)');
  L.push('  .dat                 : normalised x/c — scale to the chord above');
  L.push('  .csv                 : same points, already in mm (x_mm,y_mm,z_mm; z=0)');
  L.push('');
  L.push('NOTES');
  s.notes.forEach(n=>L.push('  - '+n));
  // mismo nombre que las otras tres descargas, para que los cuatro ficheros
  // de un mismo diseno queden juntos al ordenar la carpeta
  const base=nombreFichero()||'your_optimal_airfoil';
  _bajar(base+'_spec.txt', L.join('\\n'), 'text/plain');
}

// SEÑALES DEL MODELO — hechos, sin etiqueta de nivel (sigma + cobertura + solver)
function renderSenales(s){
  const el=document.getElementById('conf-badge'); if(!el) return;
  el.innerHTML='<div class="confbox">'
    +'<span class="signal"><b>Uncertainty '+s.sigma_txt+'</b> <span class="dim">(model\\'s own estimate)</span></span>'
    +'<span class="sep">·</span><span class="signal">'+s.cobertura+'</span>'
    +'<span class="sep">·</span><span class="signal">'+s.xfoil+'</span>'
    +'<div class="confnote">'+s.nota+'</div>'
    +'</div>';
}
</script>
</body></html>"""


@app.route("/")
def index():
    return render_template_string(PAGE, q=primera_pregunta(), p=PALETA,
                                  cmin=CUERDA_MIN, cmax=CUERDA_MAX,
                                  vmin=VELOCIDAD_MIN, vmax=VELOCIDAD_MAX,
                                  vdef=VELOCIDAD_DEFAULT, vrap=VELOCIDAD_RAPIDAS,
                                  m=_metodo_numeros())


@app.route("/favicon.ico")
def favicon():
    return ("", 204)   # evita peticiones colgadas del navegador


@app.route("/api/vecino", methods=["POST"])
def api_vecino():
    """VECINO FABRICABLE: dado el optimo (shape_params), devuelve el perfil real mas
    cercano + similitud + Cp (fig) + url de descarga del .dat."""
    body = request.get_json(silent=True) or {}
    try:
        v = encontrar_vecino(body.get("shape_params"))
        fig = fig_cp_vecino(v["run_id"], body.get("alpha_abs"))
        v["cp"] = json.loads(fig.to_json())
        v["dat_url"] = "/download/dat/" + v["run_id"]
        return jsonify(v)
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/optimo", methods=["POST"])
def api_optimo():
    """GEOMETRIA DEL OPTIMO REAL: .dat (generador arreglado) + Cp (XFOIL, fallback
    vecino). El vecino queda como referencia de contexto, no como la fuente."""
    body = request.get_json(silent=True) or {}
    try:
        sp = body.get("shape_params")
        res = cp_optimo(sp, body.get("alpha_abs"))
        res["dat_url"] = "/download/optimo/" + res["dat_hash"]
        # CSV en mm reales: se deriva del .dat que cp_optimo acaba de dejar en cache,
        # no dispara ningun recalculo (ver gen_csv_optimo)
        gen_csv_optimo(sp)
        res["csv_url"] = "/download/optimo_csv/" + res["dat_hash"]
        # STEP: se deriva del CSV que acaba de escribirse; tampoco recalcula nada
        gen_step_optimo(sp)
        res["step_url"] = "/download/optimo_step/" + res["dat_hash"]
        # CONFIANZA: sigma + cobertura de datos + convergencia de XFOIL (aqui ya se sabe)
        from confianza import senales_modelo
        if body.get("sigma") is not None and body.get("nn_dist") is not None:
            # None (no dos valores) cuando XFOIL no existe: no se ejecuto, asi que
            # no se puede afirmar ni que convergio ni que dejo de converger
            xok = None if res["cp_source"] == "unavailable" else \
                (res["cp_source"] == "optimum")
            res["senales"] = senales_modelo(float(body["sigma"]),
                                            float(body["nn_dist"]), xok)
        v = encontrar_vecino(sp)                 # solo contexto (referencia)
        res["vecino"] = {"short": v["run_id"].split("_")[0],
                         "similitud_pct": v["similitud_pct"],
                         "chord_mm": v["chord_mm"]}
        return jsonify(res)
    except Exception as e:
        return jsonify({"error": str(e)}), 400


_METODO = None
_METODO_NUM = None


def _metodo_numeros():
    """TODOS los numeros del texto de 'The Method', DERIVADOS de las dos baterias.

    Antes estaban escritos a mano en el HTML (21.5%, 3.8%, 36 of 38, 27.3%, rho 0.39,
    'the three points') y caducaron en silencio con la promocion densif: la vista
    escaparate seguia contando los resultados de julio. Calcularlos aqui es lo que
    evita que vuelva a pasar en la proxima promocion."""
    global _METODO_NUM
    if _METODO_NUM is not None:
        return _METODO_NUM
    import numpy as np
    from scipy import stats as _st
    from graficas_winner_curse import _carga, stats_bateria
    from graficas_winner_zona import _stats as _zona
    from graficas_sigma_error import _datos as _sig
    from graficas_barrido_velocidad import fig_barrido  # noqa: F401  (solo para coherencia)

    sj = stats_bateria(*_carga("julio"))
    sd = stats_bateria(*_carga("densif"))
    zj, zd = _zona("julio"), _zona("densif")
    xj, yj, _ = _sig("julio")
    xd, yd, _ = _sig("densif")
    rj, pj = _st.spearmanr(xj, yj)
    rd, pd_ = _st.spearmanr(xd, yd)

    # nº de velocidades medidas que se dibujan en la grafica 4
    import pandas as pd
    from graficas_barrido_velocidad import RUN_ID_DEFAULT, ALPHA_DEFAULT
    _base = os.path.dirname(os.path.abspath(__file__))
    _df = pd.read_csv(os.path.join(_base, "airfoil_dataset_densif_merged.csv"))
    n_med = len(_df[(_df.run_id == RUN_ID_DEFAULT) & (_df.status == "ok")
                    & (_df.alpha_deg == ALPHA_DEFAULT)])

    _METODO_NUM = {
        "n_casos": sd["n_casos"],
        "j0": f"{sj['k0']:.1f}", "j2": f"{sj['k2']:.1f}",
        "d0": f"{sd['k0']:.1f}", "d2": f"{sd['k2']:.1f}",
        "jfac": f"{sj['factor']:.1f}", "dfac": f"{sd['factor']:.1f}",
        "signos": sd["signos"], "n_signos": sd["n_signos"],
        "j_peor": f"{max(z['k0'] for z in zj.values()):.1f}",
        "d_peor": f"{max(z['k0'] for z in zd.values()):.1f}",
        "d_mejor": f"{min(z['k0'] for z in zd.values()):.1f}",
        "rho_j": f"{rj:.2f}", "p_j": f"{pj:.3f}",
        "rho_d": f"{rd:.2f}", "p_d": f"{pd_:.2f}",
        "sig_j": f"{xj.min():.2f}–{xj.max():.2f}",
        "sig_d": f"{xd.min():.2f}–{xd.max():.2f}",
        "n_medidas": n_med,
    }
    return _METODO_NUM


@app.route("/api/metodo")
def api_metodo():
    """THE METHOD: las 4 graficas de rigor del ML. Reutiliza las figuras ya hechas.
    Se construyen UNA vez y se cachean (son estaticas: bateria + dataset)."""
    global _METODO
    if _METODO is None:
        from graficas_winner_curse import fig_winner_curse, fig_evolucion, _carga
        from graficas_winner_zona import fig_winner_zona
        from graficas_sigma_error import fig_sigma_error
        from graficas_barrido_velocidad import fig_barrido
        k0, k2 = _carga()
        _METODO = {
            "winner": json.loads(fig_winner_curse(k0, k2).to_json()),
            "evolucion": json.loads(fig_evolucion().to_json()),
            "zona": json.loads(fig_winner_zona().to_json()),
            "sigma": json.loads(fig_sigma_error().to_json()),
            "barrido": json.loads(fig_barrido().to_json()),
        }
    return jsonify(_METODO)


@app.route("/api/comparar", methods=["POST"])
def api_comparar():
    """COMPARACION (nivel 2): {disenos:[{name, shape_params, banda_lo, banda_hi}], vel}
    -> curvas superpuestas + siluetas. Instantaneo: surrogate + geometria, SIN inversa."""
    body = request.get_json(silent=True) or {}
    try:
        from comparar import fig_comparar_curvas, fig_comparar_siluetas, cl_medio_banda
        ds = body.get("disenos") or []
        if not (2 <= len(ds) <= 3):
            return jsonify({"error": "Select 2 or 3 designs to compare."}), 400
        vel = int(body.get("vel") or 290)
        return jsonify({
            "curvas": json.loads(fig_comparar_curvas(ds, vel).to_json()),
            "siluetas": json.loads(fig_comparar_siluetas(ds).to_json()),
            "cl_banda": cl_medio_banda(ds),      # |CL| medio en banda (180 km/h)
            "vel": vel,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/comparar_cp", methods=["POST"])
def api_comparar_cp():
    """Cp SUPERPUESTO de los disenos seleccionados, cada uno en SU angulo recomendado.
    Bajo demanda (XFOIL es lento) y con cache por (perfil, velocidad, angulo)."""
    body = request.get_json(silent=True) or {}
    try:
        ds = body.get("disenos") or []
        if not (2 <= len(ds) <= 3):
            return jsonify({"error": "Select 2 or 3 designs to compare."}), 400
        # MODO WEB: no es un error, es una capacidad que aqui no existe. Se
        # responde 200 con un aviso informativo, no un 4xx/5xx: un error rojo
        # daria a entender que algo se ha roto.
        if not XFOIL_DISPONIBLE:
            return jsonify({"no_disponible": True, "aviso": MSG_CP})
        from comparar import fig_comparar_cp
        fig, fallos = fig_comparar_cp(ds)
        return jsonify({"cp": json.loads(fig.to_json()), "fallos": fallos})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/redat", methods=["POST"])
def api_redat():
    """Regenera (rapido, geometria pura) el .dat del optimo desde sus 7 params.
    Lo usan los disenos GUARDADOS para garantizar que su descarga sigue viva."""
    body = request.get_json(silent=True) or {}
    try:
        from optimo_geom import gen_dat_optimo
        _, h = gen_dat_optimo(body.get("shape_params"))
        return jsonify({"dat_hash": h, "dat_url": "/download/optimo/" + h})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


def _nombre_descarga(defecto="your_optimal_airfoil"):
    """Nombre de fichero pedido por el cliente en ?n=, SANEADO.

    El cliente manda el mismo texto que se ve en la leyenda y en el guardado
    ('Suzuka · 300mm · 180 km/h'). Aqui se sanea con LISTA BLANCA, no quitando
    lo malo: el valor acaba en la cabecera Content-Disposition, asi que un
    salto de linea o unas comillas permitirian inyectar cabeceras, y una barra
    o '..' jugar con la ruta. Solo sobreviven letras, digitos, punto, guion y
    guion bajo; la extension la pone SIEMPRE el servidor, nunca el cliente."""
    import unicodedata
    n = (request.args.get("n") or "").strip()
    n = unicodedata.normalize("NFKD", n).encode("ascii", "ignore").decode()
    n = re.sub(r"[^A-Za-z0-9._-]+", "_", n).strip("._-")
    n = re.sub(r"_{2,}", "_", n)[:80]
    return n or defecto


@app.route("/download/optimo/<h>")
def download_optimo(h):
    """Sirve el .dat del OPTIMO (generador arreglado), cacheado por hash."""
    if not re.fullmatch(r"[0-9a-f]{6,16}", h or ""):
        return ("bad id", 400)
    p = dat_path(h)
    if not p:
        return ("not found", 404)
    return send_file(p, as_attachment=True,
                     download_name=_nombre_descarga() + ".dat",
                     mimetype="text/plain")


@app.route("/download/optimo_csv/<h>")
def download_optimo_csv(h):
    """Sirve el CSV del OPTIMO en mm reales (x_mm,y_mm,z_mm), misma raiz de nombre
    que el .dat. Mismos puntos y mismo orden: el CSV se deriva del propio .dat."""
    if not re.fullmatch(r"[0-9a-f]{6,16}", h or ""):
        return ("bad id", 400)
    p = csv_path(h)
    if not p:
        return ("not found", 404)
    return send_file(p, as_attachment=True,
                     download_name=_nombre_descarga() + ".csv",
                     mimetype="text/csv")


@app.route("/download/optimo_step/<h>")
def download_optimo_step(h):
    """Sirve el STEP del OPTIMO: curva cerrada del contorno en mm reales, plano XY.
    Misma raiz de nombre que el .dat y el .csv; misma geometria (se deriva del CSV)."""
    if not re.fullmatch(r"[0-9a-f]{6,16}", h or ""):
        return ("bad id", 400)
    p = step_path(h)
    if not p:
        return ("not found", 404)
    return send_file(p, as_attachment=True,
                     download_name=_nombre_descarga() + ".step",
                     mimetype="application/step")


@app.route("/download/dat/<run_id>")
def download_dat(run_id):
    """Sirve el .dat TE-real (geometria limpia, TE romo real) del vecino, normalizado
    x/c (estandar de perfil; se escala a la cuerda deseada en el CAD)."""
    if not es_catalogo(run_id):                     # guard anti path-traversal
        return ("run_id no es del catalogo", 404)
    try:
        path = _dat_tereal(run_id)                  # regenera/lee el .dat TE-real limpio
        short = run_id.split("_")[0]
        return send_file(path, as_attachment=True,
                         download_name=f"airfoil_{short}_TEreal.dat", mimetype="text/plain")
    except Exception as e:
        return (str(e), 404)


@app.route("/api/circuitos")
def api_circuitos():
    """Circuitos agrupados por categoria (para el selector de la puerta A)."""
    rango = {"low": "0–5°", "medium": "5–9°", "high": "9–14°"}
    out = []
    for cat in ("low", "medium", "high"):
        cs = [{"nombre": c["nombre"], "pais": c["pais"], "nota": c["nota"]}
              for c in C.listar(cat)]
        out.append({"categoria": cat, "rango": rango[cat], "circuitos": cs})
    return jsonify(out)


@app.route("/api/resolver", methods=["POST"])
def api_resolver():
    """Recibe {modo, valor} de una de las tres puertas -> ObjetivoAngulo."""
    body = request.get_json(silent=True) or {}
    try:
        obj = resolver(body.get("modo"), body.get("valor"))
        return jsonify(obj.dict())
    except (ValueError, KeyError) as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/disenar", methods=["POST"])
def api_disenar():
    """PASO 2: {modo, valor, cuerda, prioridad} -> resumen (para mostrar antes del boton)."""
    body = request.get_json(silent=True) or {}
    try:
        obj = resolver(body.get("modo"), body.get("valor"))
        return jsonify(construir_diseno(obj, body.get("cuerda"), body.get("velocidad")))
    except (ValueError, KeyError) as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/inversa", methods=["POST"])
def api_inversa():
    """RESULTADOS (parte 1): corre la inversa (k=2) para la cuerda + angulo objetivo
    + prioridad. Devuelve los 7 parametros optimos, L/D predicho y sigma.
    Reutiliza inversa_service (mismos modelos, ensemble y objetivo que produccion)."""
    body = request.get_json(silent=True) or {}
    try:
        obj = resolver(body.get("modo"), body.get("valor"))
        cuerda = valida_cuerda(body.get("cuerda"))
        # VELOCIDAD DEL USUARIO (feature C5). Rechazo duro fuera de 95-330; None -> 180,
        # asi que un cliente antiguo que no mande el campo se comporta como siempre.
        vel = valida_velocidad(body.get("velocidad"))
        # OPTIMIZACION POR RANGO (validada): media del L/D sobre la banda del circuito.
        # Puerta C (angulo exacto): alpha_lo == alpha_hi -> rango nulo -> un solo angulo.
        r = optimizar(cuerda, -obj.alpha_hi, -obj.alpha_lo, v_kmh=vel)  # efficiency por defecto
        r["objetivo_angulo"] = obj.dict()
        # --- ENTREGA: redondear el TE al incremento fabricable (0.05 mm) ---
        # La inversa optimiza con el valor exacto; a partir de aqui TODO (KPIs, curvas,
        # Cp y .dat) usa el MISMO perfil redondeado, para que sea coherente.
        from optimo_geom import redondea_te, metricas_banda, franja_angulo, TE_STEP
        te_exacto = float(r["shape_params"]["trailing_edge_thickness_mm"])
        r["shape_params"] = redondea_te(r["shape_params"])
        r["te_exacto_mm"] = round(te_exacto, 3)
        r["te_entregado_mm"] = r["shape_params"]["trailing_edge_thickness_mm"]
        r["te_step_mm"] = TE_STEP
        m = metricas_banda(r["shape_params"], obj.alpha_lo, obj.alpha_hi, vel=vel)
        r["LD_predicho"], r["CD_predicho"] = m["LD"], m["CD"]
        r["sigma"], r["alpha_recomendado_abs"] = m["sigma"], m["alpha_rec_abs"]
        # contexto: donde cae el optimo frente a los perfiles REALES del catalogo.
        # OJO: aqui la velocidad se ENCAJA a la referencia medida mas cercana (el filtro
        # es igualdad exacta contra 110/180/290); el backend devuelve cual uso.
        from confianza import contexto_catalogo
        r["catalogo"] = contexto_catalogo(r["LD_predicho"], cuerda,
                                          obj.alpha_lo, obj.alpha_hi, vel=vel)
        # FRANJA DEL ANGULO: los angulos que el modelo no distingue del mejor (dentro de
        # una sigma). Se recorta a la banda por construccion (la rejilla ES la banda).
        # Puerta C (angulo exacto): la banda propia es un solo angulo, asi que se evalua
        # sobre la BANDA IMPLICITA de su categoria (low/medium/high, las mismas 0-5/5-9/
        # 9-14 de entrada_dashboard.RANGO). La OPTIMIZACION no cambia: sigue siendo el
        # angulo exacto pedido; la banda implicita solo define donde mirar la franja.
        if obj.alpha_lo == obj.alpha_hi:
            from entrada_dashboard import RANGO
            fb_lo, fb_hi = RANGO[obj.categoria]
        else:
            fb_lo, fb_hi = obj.alpha_lo, obj.alpha_hi
        r["franja"] = franja_angulo(r["shape_params"], fb_lo, fb_hi, vel=vel)
        # GUARDAS BLANDAS: zona de velocidad interpolada, angulo sin datos a esa V,
        # y esquina de Reynolds. Ninguna bloquea; el rechazo ya lo hizo valida_velocidad.
        from guardas_velocidad import avisos as _avisos, SIGMA_ALTA_REF
        r["avisos"] = _avisos(cuerda, vel, r["alpha_recomendado_abs"])
        r["sigma_alta"] = bool(r["sigma"] > SIGMA_ALTA_REF)
        # condicion para Cp/vecino/curvas = angulo RECOMENDADO (max |L/D| en la banda)
        r["alpha_abs"] = r["alpha_recomendado_abs"]
        r["curvas"] = json.loads(fig_curvas_optimo(
            r["shape_params"], r["alpha_recomendado_abs"], v_marca=vel,
            franja=(r["franja"]["lo"], r["franja"]["hi"]),
            ld_banda=r["LD_predicho"]).to_json())
        r["barrido"] = json.loads(fig_ld_vs_velocidad(
            r["shape_params"], r["alpha_recomendado_abs"], v_marca=vel).to_json())
        # cargas seccionales: las 3 de referencia + la del usuario, marcada
        from cargas import cargas_seccionales
        r["cargas"] = cargas_seccionales(r["shape_params"], r["alpha_recomendado_abs"],
                                         v_usuario=vel)
        return jsonify(r)
    except (ValueError, KeyError) as e:
        return jsonify({"error": str(e)}), 400


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=False, threaded=True)
