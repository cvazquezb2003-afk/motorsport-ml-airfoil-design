"""
Honest line count for this project — the tool behind the figures quoted in the README.

The dashboard's HTML, CSS and JavaScript are not separate files: they live inside
dashboard_app.py as an embedded string, so this script measures that block and
subtracts it from the Python total instead of counting the frontend twice.
It also separates docstrings from actual statements, which `wc -l` cannot do and
which matters here because most of the reasoning is documented in docstrings.
The file list comes from `git ls-files`, so the .gitignore is respected and
legacy/, backups and scratch files are excluded without a hand-kept list.

Usage:  python contar_lineas.py
"""
import io
import os
import re
import subprocess
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
CODIGO = {".py"}
FRONT = {".html", ".js", ".css"}
DATOS = {".csv", ".asc", ".dat"}
NOTAS = {".md"}


def ficheros_del_repo():
    """Lo que git considera parte del repo: seguidos + no ignorados."""
    r = subprocess.run(["git", "ls-files", "--cached", "--others",
                        "--exclude-standard"],
                       cwd=BASE, capture_output=True, text=True, encoding="utf-8")
    return sorted(x for x in r.stdout.split("\n") if x.strip())


def lineas_docstring(path):
    """Lineas ocupadas por docstrings de modulo, clase y funcion.

    Se miden aparte porque en este proyecto la documentacion vive sobre todo en
    docstrings largos, no en comentarios `#`. Contarlas como 'sentencias'
    hincharia la cifra y no aguantaria que alguien abriese el repo."""
    import ast
    try:
        arbol = ast.parse(io.open(path, encoding="utf-8", errors="ignore").read())
    except SyntaxError:
        return 0
    n = 0
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, (ast.Module, ast.ClassDef, ast.FunctionDef,
                                 ast.AsyncFunctionDef)):
            continue
        cuerpo = getattr(nodo, "body", None)
        if not cuerpo:
            continue
        p = cuerpo[0]
        if (isinstance(p, ast.Expr) and isinstance(p.value, ast.Constant)
                and isinstance(p.value.value, str)):
            n += (p.end_lineno or p.lineno) - p.lineno + 1
    return n


def clasifica_py(path):
    """(totales, en_blanco, comentario, docstring, sentencias) de un .py."""
    tot = vac = com = 0
    for ln in io.open(path, encoding="utf-8", errors="ignore"):
        tot += 1
        s = ln.strip()
        if not s:
            vac += 1
        elif s.startswith("#"):
            com += 1
    doc = lineas_docstring(path)
    return tot, vac, com, doc, tot - vac - com - doc


def frontend_embebido(path):
    """Lineas del bloque HTML/CSS/JS incrustado en dashboard_app.py.

    Se localiza por el string PAGE = \"\"\"...\"\"\" que contiene la pagina entera."""
    if not os.path.exists(path):
        return 0
    txt = io.open(path, encoding="utf-8", errors="ignore").read()
    m = re.search(r'^PAGE\s*=\s*"""', txt, re.M)
    if not m:
        return 0
    fin = txt.find('"""', m.end())
    if fin < 0:
        return 0
    return txt[m.end():fin].count("\n")


def main():
    rep = ficheros_del_repo()
    if not rep:
        print("git no devolvio ficheros: ¿hay repositorio aqui?", file=sys.stderr)
        return 1

    py = [f for f in rep if os.path.splitext(f)[1].lower() in CODIGO]
    fr = [f for f in rep if os.path.splitext(f)[1].lower() in FRONT]
    da = [f for f in rep if os.path.splitext(f)[1].lower() in DATOS]
    no = [f for f in rep if os.path.splitext(f)[1].lower() in NOTAS]

    tot = vac = com = doc = cod = 0
    for f in py:
        a, b, c, d, e = clasifica_py(os.path.join(BASE, f))
        tot += a; vac += b; com += c; doc += d; cod += e

    emb = frontend_embebido(os.path.join(BASE, "dashboard_app.py"))
    fr_lineas = sum(sum(1 for _ in io.open(os.path.join(BASE, f), encoding="utf-8",
                                           errors="ignore")) for f in fr)
    da_lineas = sum(sum(1 for _ in io.open(os.path.join(BASE, f), encoding="utf-8",
                                           errors="ignore")) for f in da)
    no_lineas = sum(sum(1 for _ in io.open(os.path.join(BASE, f), encoding="utf-8",
                                           errors="ignore")) for f in no)

    py_sin_front = tot - emb

    print("=" * 68)
    print("PYTHON  (%d ficheros .py)" % len(py))
    print("=" * 68)
    print("  lineas totales                      %8s" % f"{tot:,}")
    print("    en blanco                         %8s  (%4.1f%%)" % (f"{vac:,}", 100*vac/tot))
    print("    comentarios #                     %8s  (%4.1f%%)" % (f"{com:,}", 100*com/tot))
    print("    docstrings                        %8s  (%4.1f%%)" % (f"{doc:,}", 100*doc/tot))
    print("    sentencias                        %8s  (%4.1f%%)" % (f"{cod:,}", 100*cod/tot))
    print("    -> documentacion total            %8s  (%4.1f%%)"
          % (f"{com+doc:,}", 100*(com+doc)/tot))
    print()
    print("=" * 68)
    print("FRONTEND  (HTML + CSS + JS del dashboard)")
    print("=" * 68)
    print("  embebido en dashboard_app.py        %8s" % f"{emb:,}")
    print("  en ficheros .html/.js/.css sueltos  %8s  (%d ficheros)"
          % (f"{fr_lineas:,}", len(fr)))
    print("  TOTAL frontend                      %8s" % f"{emb + fr_lineas:,}")
    print()
    print("=" * 68)
    print("CODIGO REAL  (sin doble conteo)")
    print("=" * 68)
    print("  Python, descontando el frontend     %8s" % f"{py_sin_front:,}")
    print("  Frontend                            %8s" % f"{emb + fr_lineas:,}")
    print("  " + "-" * 50)
    print("  TOTAL                               %8s" % f"{py_sin_front + emb + fr_lineas:,}")
    print()
    print("=" * 68)
    print("SOLO COMO REFERENCIA — NO es codigo")
    print("=" * 68)
    print("  datos (.csv/.asc/.dat)  %10s lineas  (%d ficheros)"
          % (f"{da_lineas:,}", len(da)))
    print("  notas (.md)             %10s lineas  (%d ficheros)"
          % (f"{no_lineas:,}", len(no)))
    print()
    print("  el dataset es %.0fx el codigo: mezclarlos inflaria la cifra sin sentido"
          % (da_lineas / max(py_sin_front + emb + fr_lineas, 1)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
