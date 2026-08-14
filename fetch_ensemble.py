"""Fetch the validated uncertainty ensemble, and refuse anything else.

`ensemble_ld_sigma.joblib` is 106 MiB, over GitHub's file limit, so it cannot be
committed. It used to be retrained inside the Docker image instead -- and that was wrong:
retraining does not reproduce the artefact, it produces a different one. Measured on
2026-08-14, same 11-feature input, container vs local:

    mu     -57.2348   vs  -57.4397
    sigma    0.35393  vs    0.27786      +27.4 %

Sigma is what the k=2 penalty is built on, so a different ensemble means a different
argmin: the deployed app was returning a different geometry from the validated code for
the same circuit. The committed models are fine -- their predictions are byte-identical
across platforms; only the retrained ensemble drifts, because the trees do not come out
the same on Linux.

So the ensemble is now published as a GitHub release asset and downloaded, pinned by
SHA-256. The hash is the point: it does not check that *an* ensemble is present, it checks
that this is **the** one the 40-case battery was measured with.

    python fetch_ensemble.py            # download and verify
    python fetch_ensemble.py --force    # overwrite a local ensemble that differs

--- NO FALLBACK, ON PURPOSE ---
If the download or the hash check fails, this exits non-zero and the Docker build dies.
There is deliberately no `|| python build_ensemble.py` anywhere: a silent fallback to
retraining is exactly the bug this replaces, and it would reintroduce it without a word in
the log. A build that fails loudly is cheap; a deployment quietly serving a different
model is what cost us two days of measurements.

--- RELATION TO build_ensemble.py ---
That script is how the artefact was *made*, and it is the disaster recovery path if the
release is ever lost. It reproduces this file byte for byte on the same environment
(verified: md5 444cf10b...), but only there. The release asset, not the script, is the
source of truth.
"""
import argparse
import hashlib
import os
import sys
import time
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))

URL = ("https://github.com/cvazquezb2003-afk/motorsport-ml-airfoil-design"
       "/releases/download/ensemble-densif-v1/ensemble_ld_sigma.joblib")
SHA256 = "4d25eaf77ec8b9bdd8b2ff060f0dc1dff4d41e6ec68e5c24f5714f353d48fc7c"
BYTES = 110989020

DESTINO = os.path.join(BASE, "ensemble_ld_sigma.joblib")
PARCIAL = DESTINO + ".part"
INTENTOS = 3


def sha256_de(ruta):
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def descarga():
    """Download to a .part file. Never leaves a truncated file at the real name:
    build_ensemble.py skips when the destination exists, so a half-written ensemble
    there would be silently accepted by a later run."""
    req = urllib.request.Request(URL, headers={"User-Agent": "fetch_ensemble"})
    for intento in range(1, INTENTOS + 1):
        try:
            t0 = time.perf_counter()
            with urllib.request.urlopen(req, timeout=900) as r, open(PARCIAL, "wb") as f:
                total = int(r.headers.get("Content-Length") or 0)
                hecho = 0
                while True:
                    bloque = r.read(1 << 20)
                    if not bloque:
                        break
                    f.write(bloque)
                    hecho += len(bloque)
                    if total:
                        print("\r[ENSEMBLE] %5.1f %%  (%d / %d bytes)"
                              % (100 * hecho / total, hecho, total), end="", flush=True)
            print("\r[ENSEMBLE] descargado en %.1f s%20s" % (time.perf_counter() - t0, ""))
            return
        except Exception as e:
            if os.path.exists(PARCIAL):
                os.remove(PARCIAL)
            if intento == INTENTOS:
                raise
            print("[ENSEMBLE] intento %d/%d fallo (%s); reintentando"
                  % (intento, INTENTOS, type(e).__name__), flush=True)
            time.sleep(5 * intento)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--force", action="store_true",
                    help="overwrite an existing ensemble whose hash does not match")
    args = ap.parse_args()

    print("[ENSEMBLE] destino : %s" % DESTINO)
    print("[ENSEMBLE] origen  : %s" % URL)
    print("[ENSEMBLE] sha256  : %s" % SHA256)

    if os.path.exists(DESTINO):
        actual = sha256_de(DESTINO)
        if actual == SHA256:
            print("[ENSEMBLE] ya presente y VERIFICADO (sha256 coincide). Nada que hacer.")
            return 0
        print("[ENSEMBLE] ya existe un fichero con OTRO contenido:")
        print("           sha256 en disco : %s" % actual)
        print("           sha256 esperado : %s" % SHA256)
        if not args.force:
            print("[ENSEMBLE] NO se sobrescribe sin --force. Si lo generaste con "
                  "build_ensemble.py\n"
                  "           es un ensemble EQUIVALENTE pero no identico al validado; "
                  "usa --force\n"
                  "           para reemplazarlo por el de la release.", file=sys.stderr)
            return 1
        print("[ENSEMBLE] --force: se reemplaza por el artefacto de la release.")

    descarga()

    # Se verifica LEYENDO DEL DISCO, no el buffer en memoria: asi la comprobacion
    # cubre tambien una escritura truncada o un disco lleno.
    n = os.path.getsize(PARCIAL)
    sha = sha256_de(PARCIAL)
    print("[ENSEMBLE] bytes  : %d" % n)
    print("[ENSEMBLE] sha256 : %s" % sha)

    if n != BYTES:
        os.remove(PARCIAL)
        sys.exit("[ENSEMBLE] TAMANO INCORRECTO: esperado %d, obtenido %d. Build abortado."
                 % (BYTES, n))
    if sha != SHA256:
        os.remove(PARCIAL)
        sys.exit("[ENSEMBLE] SHA256 INCORRECTO.\n"
                 "           esperado %s\n"
                 "           obtenido %s\n"
                 "           Este NO es el ensemble con el que se midio la bateria. "
                 "Build abortado." % (SHA256, sha))

    os.replace(PARCIAL, DESTINO)
    print("[ENSEMBLE] VERIFICADO: es el artefacto validado (bateria de 40 casos, k=2).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
