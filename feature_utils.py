"""
FUENTE UNICA de las features del modelo (base + derivadas fisicas).
Importado por el entrenamiento (eda_ml_filtrado150.py) y por la inversa
(inversa_ld_v2.py) para GARANTIZAR que las features derivadas se calculan
EXACTAMENTE igual en ambos lados. Si difieren, el modelo y la inversa no casan.

Derivadas:
  alpha_over_sqrtre = alpha_deg / sqrt(reynolds)   -> termino viscoso (bajo Re)
  te_rel            = trailing_edge_thickness_mm / chord_length_mm  -> TE relativo
"""
import numpy as np

SHAPE = ["chord_length_mm", "leading_edge_angle_deg", "leading_edge_thickness_level",
         "trailing_edge_angle_deg", "trailing_edge_thickness_mm",
         "te_upr_angle_deg", "te_lwr_angle_deg"]
BASE_FEAT = SHAPE + ["alpha_deg", "reynolds"]
# Orden CANONICO de las 11 features (el que espera el modelo). No reordenar.
FEATURES = BASE_FEAT + ["alpha_over_sqrtre", "te_rel"]


def f_alpha_over_sqrtre(alpha_deg, reynolds):
    """Termino viscoso; acepta escalares o arrays de numpy."""
    return alpha_deg / np.sqrt(reynolds)


def f_te_rel(te_thickness_mm, chord_mm):
    """Espesor de borde de salida relativo a la cuerda; escalar o array."""
    return te_thickness_mm / chord_mm


def add_derived(df):
    """Anade las columnas derivadas a un DataFrame (uso en entrenamiento)."""
    df = df.copy()
    df["alpha_over_sqrtre"] = f_alpha_over_sqrtre(df["alpha_deg"], df["reynolds"])
    df["te_rel"] = f_te_rel(df["trailing_edge_thickness_mm"], df["chord_length_mm"])
    return df
