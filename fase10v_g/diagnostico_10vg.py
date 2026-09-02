# -*- coding: utf-8 -*-
from pathlib import Path
RAIZ = Path.cwd()

print("=" * 70)
print("1) routers/usuarios.py - ESTRUTURA COMPLETA")
print("=" * 70)
p = RAIZ / "routers/usuarios.py"
linhas = p.read_text(encoding="utf-8-sig").splitlines()
for i, l in enumerate(linhas):
    print("%4d: %s" % (i + 1, l))

print("=" * 70)
print("2) services/usuarios.py - IMPORTS + RAISE 500")
print("=" * 70)
p2 = RAIZ / "services/usuarios.py"
l2 = p2.read_text(encoding="utf-8-sig").splitlines()
for i, l in enumerate(l2):
    if l.strip().startswith("from ") or l.strip().startswith("import "):
        print("%4d: %s" % (i + 1, l))
for i, l in enumerate(l2):
    if "status_code=500" in l or "status_code = 500" in l:
        for j in range(max(0, i - 2), min(len(l2), i + 8)):
            print("  %4d: %s" % (j + 1, l2[j]))
        print("  ---")
