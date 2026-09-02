# -*- coding: utf-8 -*-
from pathlib import Path
RAIZ = Path.cwd()

print("=" * 70)
print("1) HANDLER MAPPING - routers/rodadas.py (status codes)")
print("=" * 70)
t = (RAIZ / "routers/rodadas.py").read_text(encoding="utf-8-sig")
lines = t.splitlines()
for i, line in enumerate(lines):
    if "exception_handler" in line:
        for j in range(max(0, i - 1), min(len(lines), i + 25)):
            print("%4d: %s" % (j + 1, lines[j]))
        print("-" * 60)

print("=" * 70)
print("2) FORMATOS DE RAISE (amostra por arquivo)")
print("=" * 70)
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
for arq in ARQUIVOS:
    p = RAIZ / arq
    if not p.exists():
        print("--- " + arq + " (MISSING)")
        continue
    linhas = p.read_text(encoding="utf-8-sig").splitlines()
    cont = 0
    print("--- " + arq)
    for i, line in enumerate(linhas):
        if "raise HTTPException" in line:
            cont += 1
            if cont <= 2:
                for j in range(max(0, i), min(len(linhas), i + 9)):
                    print("  %4d: %s" % (j + 1, linhas[j]))
                print("  ...")
    if cont == 0:
        print("  (nenhum raise HTTPException)")
