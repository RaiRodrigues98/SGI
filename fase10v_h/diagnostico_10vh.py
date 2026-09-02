# -*- coding: utf-8 -*-
from pathlib import Path
RAIZ = Path.cwd()

print("=" * 70)
print("1) ONDE auth.py e chamado (dependencies + routers)")
print("=" * 70)
for caminho in ["dependencies/auth.py", "dependencies/__init__.py"]:
    p = RAIZ / caminho
    if not p.exists():
        print("--- " + caminho + " (NAO EXISTE)")
        continue
    t = p.read_text(encoding="utf-8-sig")
    print("=== " + caminho + " (%d linhas)" % len(t.splitlines()))
    for i, l in enumerate(t.splitlines()):
        if any(x in l for x in ["autenticar_usuario", "decodificar_token", "exigir_permissao", "from services.auth", "import auth"]):
            print("  %4d: %s" % (i + 1, l.strip()))

print("=" * 70)
print("2) routers que usam exigir_permissao / decodificar_token")
print("=" * 70)
routers = RAIZ / "routers"
for rp in sorted(routers.glob("*.py")):
    if "backup" in rp.name.lower():
        continue
    t = rp.read_text(encoding="utf-8-sig")
    usos = [x.strip() for x in ["autenticar_usuario", "decodificar_token", "exigir_permissao"] if x in t]
    if usos:
        print("  " + rp.name + ": " + ", ".join(usos))

print("=" * 70)
print("3) auth.py - estrutura dos 8 raises (401/403)")
print("=" * 70)
p = RAIZ / "services/auth.py"
linhas = p.read_text(encoding="utf-8-sig").splitlines()
for i, l in enumerate(linhas):
    if "raise HTTPException" in l:
        for j in range(i, min(len(linhas), i + 8)):
            print("  %4d: %s" % (j + 1, linhas[j]))
        print("  ---")
