"""
Driver de medición de tiempos. NO modifica la lógica del pipeline:
solo envuelve pipeline_airfoil_api.run_step para cronometrar cada Step.
"""
import time
import json
import pipeline_airfoil_api as pipe

timings = []
_orig_run_step = pipe.run_step


def timed_run_step(step_name, cmd, timeout=None):
    t0 = time.perf_counter()
    try:
        return _orig_run_step(step_name, cmd, timeout=timeout)
    finally:
        dt = time.perf_counter() - t0
        timings.append((step_name, dt))


pipe.run_step = timed_run_step

result = pipe.run_pipeline(None)  # parametros por defecto

print("\n" + "=" * 60)
print("TIEMPOS POR STEP (segundos)")
print("=" * 60)
for name, dt in timings:
    print(f"{dt:8.2f} s   {name}")
total = sum(dt for _, dt in timings)
print("-" * 60)
print(f"{total:8.2f} s   TOTAL (suma de los 7 Steps)")
print(f"STATUS FINAL: {result.get('status')}")

with open("diag_timing.json", "w", encoding="utf-8") as f:
    json.dump(
        {"status": result.get("status"),
         "steps": [{"step": n, "seconds": round(d, 3)} for n, d in timings],
         "total_seconds": round(total, 3)},
        f, indent=2, ensure_ascii=False)
