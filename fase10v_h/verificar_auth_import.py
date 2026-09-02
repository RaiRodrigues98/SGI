# -*- coding: utf-8 -*-
from pathlib import Path
RAIZ = Path.cwd()
p = RAIZ / "services" / "auth.py"
linhas = p.read_text(encoding="utf-8-sig").splitlines()
print("services/auth.py - imports e usos de excecoes:")
for i, l in enumerate(linhas):
    if any(x in l for x in ["import", "HTTPException", "AuthenticationError", "AuthorizationError"]):
        print("%4d: %s" % (i + 1, l))
