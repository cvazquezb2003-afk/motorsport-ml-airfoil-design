"""
FASE A — Prueba de viabilidad: ¿genera un .dat con TE REAL (sin el corte del 0.03)
que XFOIL CONVERJA? Portable, NO toca CATIA ni asc_to_dat.py ni el pipeline.

Conversor TE-real: parte del .asc archivado, reutiliza project_to_chord_system de
asc_to_dat (misma normalizacion), pero:
  - NO aplica order_le_chain_for_xfoil (el corte del 0.03).
  - Usa las coordenadas reales de te_norm (10 pts del TE) como cierre romo,
    en vez de la recta amputada de append_te_block_closure.
Luego corre XFOIL sobre el .dat TE-real y sobre el .dat amputado (dataset_runs)
en las mismas condiciones y compara CL/CD/LD.
"""
import os, subprocess
import numpy as np
import pandas as pd
# funciones reutilizadas de asc_to_dat SIN modificarlo (import seguro: tiene guard __main__)
from asc_to_dat import (read_asc_points, project_to_chord_system,
                        remove_consecutive_duplicates, PLANE_MODE, N_LE, N_TE)

BASE = os.path.dirname(os.path.abspath(__file__))
from rutas import XFOIL_EXE as XFOIL   # fuente unica de la ruta a XFOIL (ver rutas.py)
SCRATCH = os.path.join(BASE, "_te_real_tmp")
os.makedirs(SCRATCH, exist_ok=True)


def genera_te_real(asc_path, out_dat):
    """Construye el .dat con TE romo REAL (contorno cerrado, orden de arco)."""
    points = read_asc_points(asc_path, plane_mode=PLANE_MODE)
    le_raw = points[:N_LE]
    te_raw = points[N_LE:N_LE + N_TE]
    if len(te_raw) > 0:
        te_raw = te_raw[::-1]                      # igual que asc_to_dat.main
    le_norm, te_norm, chord = project_to_chord_system(le_raw, te_raw)

    chain = remove_consecutive_duplicates(le_norm)   # perfil completo TE_up->LE->TE_lo
    # orientar: empezar arriba (y>0) como espera XFOIL
    if chain[0, 1] < chain[-1, 1]:
        chain = chain[::-1]
    up_corner = chain[0]     # TE superior real
    lo_corner = chain[-1]    # TE inferior real

    # cierre con los puntos REALES del TE (te_norm), orientados lo_corner -> up_corner
    te = remove_consecutive_duplicates(te_norm)
    if np.linalg.norm(te[0] - lo_corner) > np.linalg.norm(te[-1] - lo_corner):
        te = te[::-1]
    # quitar los extremos que coinciden con las esquinas (evita duplicados)
    face = [p for p in te if (np.linalg.norm(p - lo_corner) > 1e-6
                              and np.linalg.norm(p - up_corner) > 1e-6)]
    full = np.vstack([chain] + ([np.array(face)] if face else []))
    full = remove_consecutive_duplicates(full)
    # cerrar el contorno (primer == ultimo), como hace el pipeline amputado
    if np.linalg.norm(full[0] - full[-1]) > 1e-9:
        full = np.vstack([full, full[0]])
    full[:, 0] = np.clip(full[:, 0], 0.0, 1.0)

    with open(out_dat, "w") as f:
        f.write("TE_REAL\n")
        for x, y in full:
            f.write(f"{x:.6f} {y:.6f}\n")
    gap = float(np.linalg.norm(up_corner - lo_corner))   # espesor TE real (norm)
    return len(full), gap


def xfoil_una(dat, Re, alpha, tag):
    # XFOIL trunca rutas largas en sus prompts -> usar nombres CORTOS relativos
    # dentro de cwd=SCRATCH (copiar el .dat a la carpeta de trabajo).
    import shutil
    geom = os.path.join(SCRATCH, "geom.dat")
    shutil.copy2(dat, geom)
    pol_rel = f"pol_{tag}.txt"
    pol = os.path.join(SCRATCH, pol_rel)
    if os.path.exists(pol):
        os.remove(pol)
    cmds = f"LOAD geom.dat\n\nPANE\nOPER\nVISC {int(Re)}\nITER 200\nPACC\n{pol_rel}\n\nALFA {alpha}\nPACC\n\nQUIT\n"
    try:
        subprocess.run([XFOIL], input=cmds, text=True, capture_output=True,
                       cwd=SCRATCH, timeout=90)
    except Exception:
        pass
    if os.path.exists(pol):
        for ln in open(pol, encoding="utf-8", errors="ignore"):
            p = ln.split()
            if len(p) >= 3:
                try:
                    a, cl, cd = float(p[0]), float(p[1]), float(p[2])
                    if abs(a - alpha) < 0.5:
                        return cl, cd
                except ValueError:
                    pass
    return None


if __name__ == "__main__":
    df = pd.read_csv(os.path.join(BASE, "airfoil_dataset.csv"))
    TESTS = [
        ("0001_20260712_224010", 180, -6),   # bajo 169mm
        ("0014_20260711_193032", 180, -6),   # centro 274mm
        ("0001_20260628_221136", 180, -6),   # centro 281mm
        ("0002_20260628_221225", 180, -6),   # centro 343mm
        ("0002_20260712_214345", 180, -6),   # alto 465mm
    ]
    filas = []
    for rid, v, a in TESTS:
        g = df[(df.run_id == rid) & (df.velocidad_kmh == v) & (df.alpha_deg == a) & (df.status == "ok")]
        if g.empty:
            print(f"[SKIP] {rid} sin fila ok en v{v} a{a}"); continue
        Re = int(g.reynolds.iloc[0]); chord = g.chord_length_mm.iloc[0]
        asc = os.path.join(BASE, "dataset_runs", rid, "auto_export.asc")
        amp = os.path.join(BASE, "dataset_runs", rid, "airfoil_v4.dat")   # el amputado archivado
        real_dat = os.path.join(SCRATCH, f"{rid}_tereal.dat")
        npts, gap = genera_te_real(asc, real_dat)
        print(f"\n### {rid} cuerda={chord:.0f} v{v} a{a} Re={Re} | TE-real: {npts} pts, gap={gap:.4f}")
        r_amp = xfoil_una(amp, Re, a, "amp")
        r_real = xfoil_una(real_dat, Re, a, "real")
        print(f"   amputado: {r_amp}   TE-real: {r_real}")
        filas.append(dict(rid=rid, chord=round(chord), v=v, a=a, Re=Re,
                          amp=r_amp, real=r_real))

    print("\n" + "=" * 96)
    print("TABLA — amputado vs TE-real")
    print("=" * 96)
    print(f"{'perfil':22s}{'c':>5s}{'conv':>6s}{'CL_amp':>9s}{'CL_real':>9s}{'dCL%':>7s}"
          f"{'CD_amp':>9s}{'CD_real':>9s}{'dCD%':>7s}{'LD_amp':>8s}{'LD_real':>8s}{'dLD%':>7s}")
    for f in filas:
        conv = "SI" if f["real"] else "NO"
        if f["amp"] and f["real"]:
            cla, cda = f["amp"]; clr, cdr = f["real"]
            lda, ldr = cla/cda, clr/cdr
            dcl = (clr-cla)/abs(cla)*100; dcd = (cdr-cda)/abs(cda)*100; dld = (ldr-lda)/abs(lda)*100
            print(f"{f['rid']:22s}{f['chord']:>5d}{conv:>6s}{cla:9.4f}{clr:9.4f}{dcl:6.1f}%"
                  f"{cda:9.5f}{cdr:9.5f}{dcd:6.1f}%{lda:8.2f}{ldr:8.2f}{dld:6.1f}%")
        else:
            print(f"{f['rid']:22s}{f['chord']:>5d}{conv:>6s}   amp={f['amp']} real={f['real']}")
