"""
ETAPA 1 — Regenera los 965 perfiles con TE-real. Reutiliza los 100 del piloto.
Reanudable: si airfoil_dataset_TEreal.csv ya tiene run_ids, los salta.
NO toca airfoil_dataset.csv ni nada de produccion.
"""
import os, sys, csv
import numpy as np
import pandas as pd
# reutiliza el conversor y el harness ya validados (import seguro: guard __main__)
from piloto_tereal import genera_tereal, xfoil_sweep, SHAPE, COLS, SCRATCH

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "airfoil_dataset_TEreal.csv")
PILOT = os.path.join(BASE, "airfoil_dataset_TEreal_piloto.csv")

df = pd.read_csv(os.path.join(BASE, "airfoil_dataset.csv"))
# objetivo: run_ids con .asc archivado Y en el CSV
targets = [r for r in df.run_id.unique()
           if os.path.exists(os.path.join(BASE, "dataset_runs", r, "auto_export.asc"))]
print(f"[INFO] objetivo: {len(targets)} perfiles con .asc")

# --- inicializar OUT: cabecera + copiar los 100 del piloto (reuso) ---
done = set()
if not os.path.exists(OUT):
    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS); w.writeheader()
        if os.path.exists(PILOT):
            pil = pd.read_csv(PILOT)
            pil = pil.reindex(columns=COLS)
            for _, r in pil.iterrows():
                w.writerow({c: ("" if pd.isna(r[c]) else r[c]) for c in COLS})
            done = set(pil.run_id.unique())
    print(f"[INFO] reutilizados del piloto: {len(done)} perfiles")
else:
    done = set(pd.read_csv(OUT).run_id.unique())
    print(f"[INFO] OUT ya existe con {len(done)} perfiles hechos -> reanudo")

pend = [r for r in targets if r not in done]
print(f"[INFO] pendientes: {len(pend)}\n"); sys.stdout.flush()

with open(OUT, "a", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=COLS)
    tot_ok = tot = 0
    for k, rid in enumerate(pend, 1):
        g = df[df.run_id == rid]; base = g.iloc[0]
        asc = os.path.join(BASE, "dataset_runs", rid, "auto_export.asc")
        dat = os.path.join(SCRATCH, "e1.dat")
        try:
            genera_tereal(asc, dat)
        except Exception as e:
            print(f"  [{k}/{len(pend)}] {rid} FALLO genera: {e}"); sys.stdout.flush(); continue
        p_ok = p_tot = 0
        for v in sorted(g.velocidad_kmh.unique()):
            gv = g[g.velocidad_kmh == v]
            alphas = sorted(gv.alpha_deg.tolist(), reverse=True)
            Re = int(gv.reynolds.iloc[0])
            pol = xfoil_sweep(dat, Re, alphas)
            for a in alphas:
                p_tot += 1; tot += 1
                row = {c: base[c] for c in ["run_id", "timestamp", "source"] + SHAPE}
                row.update({"alpha_deg": a, "velocidad_kmh": v, "reynolds": Re})
                if a in pol:
                    cl, cd, cm = pol[a]; ld = cl / cd if cd else ""
                    row.update({"CL": cl, "CD": cd, "CM": cm, "LD": ld,
                                "status": "ok", "error_detail": ""})
                    p_ok += 1; tot_ok += 1
                else:
                    row.update({"CL": "", "CD": "", "CM": "", "LD": "",
                                "status": "error_xfoil_no_converge",
                                "error_detail": f"TE-real no converge a{a} v{v}"})
                w.writerow(row)
        fh.flush()
        if k % 5 == 0 or k <= 5:
            print(f"  [{k}/{len(pend)}] {rid} c={base['chord_length_mm']:.0f} | "
                  f"nuevos {tot_ok}/{tot} ({100*tot_ok/max(tot,1):.0f}%)")
            sys.stdout.flush()

print(f"\n[OK] ETAPA 1 completada -> {OUT}")
