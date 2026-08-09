"""
API REST de GENERACION DE GEOMETRIA (MVP).

⚠️ REQUIERE CATIA. Este servicio llama a `run_pipeline`, que construye la geometria
del perfil en CATIA (COM/win32com) -> puntos -> ASC -> DAT -> XFOIL. Por tanto:
  - NO es portable: solo funciona en la maquina con CATIA instalado y abierto.
  - NO es el backend del dashboard (el dashboard sirve las graficas ya calculadas,
    que si son portables). No mezclar ambas cosas en este fichero.

Contrato de /generate_airfoil (POST, JSON):
  - user_params: dict con los parametros de forma (obligatorio).
  - velocidad_kmh: numero o lista (OBLIGATORIO desde el refactor del Reynolds; el
    Reynolds se DERIVA de cuerda + velocidad, no se pasa).
  - alphas: lista de angulos (opcional).
"""
from flask import Flask, request, jsonify
from pipeline_airfoil_api import run_pipeline

app = Flask(__name__)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "message": "Airfoil API is running"
    })


@app.route("/generate_airfoil", methods=["POST"])
def generate_airfoil():
    try:
        config = request.get_json()

        if config is None:
            return jsonify({
                "status": "error",
                "message": "No JSON body received"
            }), 400

        # velocidad_kmh es OBLIGATORIA desde el refactor del Reynolds: el Reynolds
        # se deriva de la cuerda y la velocidad, no se pasa. Sin ella el pipeline
        # no sabe a que Reynolds correr XFOIL.
        vel = config.get("velocidad_kmh")
        if vel is None or (isinstance(vel, list) and len(vel) == 0):
            return jsonify({
                "status": "error",
                "stage": "config_validation",
                "message": "Falta 'velocidad_kmh' (numero o lista). Es obligatoria: "
                           "el Reynolds se deriva de la cuerda y la velocidad."
            }), 400

        result = run_pipeline(config)

        if result.get("status") == "ok":
            return jsonify(result), 200

        return jsonify(result), 500

    except Exception as e:
        return jsonify({
            "status": "error",
            "stage": "flask",
            "message": str(e)
        }), 500


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False
    )