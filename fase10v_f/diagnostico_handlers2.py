# -*- coding: utf-8 -*-
from pathlib import Path
RAIZ = Path.cwd()

ALVOS = [
    "routers/rodadas.py",
    "routers/finalizacao.py",
    "routers/encaminhamento_gestor.py",
    "routers/usuarios.py",
    "routers/configuracoes_operacionais.py",
]

for arq in ALVOS:
    p = RAIZ / arq
    if not p.exists():
        print("=== " + arq + " (NAO EXISTE)")
        continue
    linhas = p.read_text(encoding="utf-8-sig").splitlines()
    print("=" * 70)
    print(arq)
    print("=" * 70)
    # importa as excecoes de dominio?
    for i, l in enumerate(linhas):
        if "from domain.exceptions" in l or "import DomainError" in l:
            print("  IMPORT %4d: %s" % (i + 1, l.strip()))
    # blocos except que traduzem para HTTP
    for i, l in enumerate(linhas):
        if "except" in l and any(x in l for x in ["DomainError", "BusinessRuleViolation", "NotFoundError", "ConflictError"]):
            for j in range(max(0, i), min(len(linhas), i + 10)):
                print("  %4d: %s" % (j + 1, linhas[j]))
            print("  ---")
    # se nao achou except, mostra qualquer ocorrencia das excecoes
    if not any("except" in l and any(x in l for x in ["DomainError", "BusinessRuleViolation", "NotFoundError", "ConflictError"]) for l in linhas):
        for i, l in enumerate(linhas):
            if any(x in l for x in ["BusinessRuleViolation", "NotFoundError", "ConflictError"]):
                print("  REF %4d: %s" % (i + 1, l.strip()))
