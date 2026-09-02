# -*- coding: utf-8 -*-
"""Diagnostico Fase 10V-F: status codes por arquivo + handlers de dominio."""
import re
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

ARQUIVOS = [
    "services/auth.py",
    "services/configuracoes_operacionais.py",
    "services/decisoes_rotativo.py",
    "services/encaminhamento_gestor.py",
    "services/finalizacao_inventario.py",
    "services/finalizacao_rotativo.py",
    "services/ocorrencias_divergencia.py",
    "services/usuarios.py",
]

print("=" * 70)
print("DIAGNOSTICO 10V-F - STATUS CODES POR ARQUIVO")
print("=" * 70)

total_geral = Counter()
for arq in ARQUIVOS:
    p = RAIZ / arq
    if not p.exists():
        print("[MISSING] " + arq)
        continue
    texto = p.read_text(encoding="utf-8-sig")
    blocos = texto.split("raise HTTPException")[1:]
    c = Counter()
    for b in blocos:
        m = re.search(r"status_code\s*=\s*(\d+)", b)
        if m:
            c[int(m.group(1))] += 1
        else:
            c["?"] += 1
    total_geral.update(c)
    print(arq)
    print("  raises=" + str(sum(c.values())) + " | " + str(dict(sorted(c.items()))))

print("=" * 70)
print("TOTAL GERAL:", dict(sorted(total_geral.items())))
print("=" * 70)

print("[2/2] Handlers de dominio nos routers...")
routers_dir = RAIZ / "routers"
achou = False
if routers_dir.exists():
    for rp in sorted(routers_dir.rglob("*.py")):
        t = rp.read_text(encoding="utf-8-sig")
        hits = []
        for padrao in ["add_exception_handler", "exception_handler", "DomainError", "BusinessRuleViolation", "NotFoundError", "ConflictError"]:
            if padrao in t:
                hits.append(padrao)
        if hits:
            achou = True
            print("  " + str(rp.relative_to(RAIZ)) + ": " + ", ".join(hits))
if not achou:
    print("  NENHUM handler de dominio nos routers (RISCO: excecao de dominio vira 500).")

print("[FIM]")
