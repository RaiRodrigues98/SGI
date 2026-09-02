# -*- coding: utf-8 -*-
"""Fase 10V-E v3 - Fechamento de services/rodadas/finalizacao_rotativo.py.

Converte os 3 HTTPException restantes (status 400) para BusinessRuleViolation,
preservando o status HTTP 400 original (principio: preservar comportamento).

Idempotente (MIGRADO / LEGADO / DESCONHECIDO). Restaura backup em falha.
"""

import py_compile
import re
import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ARQUIVO = RAIZ / "services" / "rodadas" / "finalizacao_rotativo.py"
BACKUP = ARQUIVO.with_name(ARQUIVO.name + ".bak_10ve_v3")

IMPORT_FASTAPI = re.compile(r"from fastapi import HTTPException\r?\n")

PATTERN = re.compile(
    r"(\s*)raise\s+HTTPException\(\s*"
    r"status_code=400,\s*"
    r"detail=\(\s*"
    r"(.*?)"
    r"\)\s*\)",
    re.DOTALL,
)


def _mensagem(detail_body):
    return "".join(re.findall(r'"([^"]*)"', detail_body))


def _repor(match):
    indent = match.group(1)
    msg = _mensagem(match.group(2))
    return f'{indent}raise BusinessRuleViolation(\n{indent}    "{msg}"\n{indent})'


def _estado(texto):
    tem_fastapi = "from fastapi import HTTPException" in texto
    tem_raise_http = "raise HTTPException" in texto
    if not tem_fastapi and not tem_raise_http:
        return "MIGRADO"
    if tem_fastapi and tem_raise_http:
        return "LEGADO"
    return "DESCONHECIDO"


def main():
    if not ARQUIVO.exists():
        print("[ERRO] Arquivo alvo nao encontrado:", ARQUIVO)
        sys.exit(1)

    texto = ARQUIVO.read_text(encoding="utf-8-sig")
    estado = _estado(texto)

    if estado == "MIGRADO":
        print("[0/3] Estado: MIGRADO_10V_E_V3")
        print("[OK] Fase 10V-E v3 ja aplicada.")
        return

    if estado == "DESCONHECIDO":
        print("[ABORT] Estado DESCONHECIDO - abortando antes da mutacao.")
        sys.exit(2)

    print("[0/3] Estado: LEGADO - prosseguindo com a migracao.")
    shutil.copy2(ARQUIVO, BACKUP)
    print("[1/3] Backup criado:", BACKUP.name)

    try:
        novo, n = PATTERN.subn(_repor, texto)
        if n != 3:
            print("[ABORT] Esperados 3 raises HTTPException; encontrados %d." % n)
            shutil.copy2(BACKUP, ARQUIVO)
            sys.exit(2)

        if "from domain.exceptions import BusinessRuleViolation" not in novo:
            raise RuntimeError("Import de BusinessRuleViolation ausente apos a conversao.")

        if "raise HTTPException" not in novo:
            novo = IMPORT_FASTAPI.sub("", novo)

        ARQUIVO.write_text(novo, encoding="utf-8")
        print("[2/3] 3 raises HTTPException convertidos para BusinessRuleViolation.")
    except Exception as exc:
        shutil.copy2(BACKUP, ARQUIVO)
        print("[ERRO] Falha pos-mutacao - backup restaurado:", exc)
        sys.exit(3)

    try:
        py_compile.compile(str(ARQUIVO), doraise=True)
        print("[3/3] Sintaxe validada com sucesso.")
    except Exception as exc:
        shutil.copy2(BACKUP, ARQUIVO)
        print("[ERRO] Falha de sintaxe - backup restaurado:", exc)
        sys.exit(3)

    print("[OK] Fase 10V-E v3 aplicada. Estado: MIGRADO_10V_E_V3")


if __name__ == "__main__":
    main()
