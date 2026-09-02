# -*- coding: utf-8 -*-
from pathlib import Path
RAIZ = Path.cwd()

for arq in ["routers/auth.py", "dependencies/auth.py"]:
    p = RAIZ / arq
    print("=" * 72)
    print(arq)
    print("=" * 72)
    linhas = p.read_text(encoding="utf-8-sig").splitlines()
    for i, l in enumerate(linhas):
        print("%4d: %s" % (i + 1, l))
    print()
