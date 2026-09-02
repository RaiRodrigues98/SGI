# -*- coding: utf-8 -*-
"""Fase 10V-G - Destravar usuarios.py (router + service).

Parte 1 (router): adiciona handlers de dominio (BRV->400, NF->404, CF->409)
                   em routers/usuarios.py, preservando rollback por rota.
Parte 2 (service): converte 400/404/409 -> dominio em services/usuarios.py.
                   Mantem o 500 (f-string) como HTTPException.

Ordem: router PRIMEIRO, service DEPOIS (evita janela sem handler).
Idempotente. Backup + py_compile + rollback em falha.
"""
import py_compile
import re
import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ROUTER = RAIZ / "routers" / "usuarios.py"
SERVICE = RAIZ / "services" / "usuarios.py"

# ---------------- Parte 1: Router ----------------

WRITE_OLD = (
    "    except HTTPException:\n"
    "\n"
    "        if conn:\n"
    "            uow.rollback()\n"
    "\n"
    "        raise\n"
)

READ_OLD = (
    "    except HTTPException:\n"
    "        raise\n"
)


def _handler(status, cls, com_rollback):
    bloco = "    except %s as erro:\n\n" % cls
    if com_rollback:
        bloco += "        if conn:\n            uow.rollback()\n\n"
    bloco += (
        "        raise HTTPException(\n"
        "            status_code=%d,\n"
        "            detail=str(erro)\n"
        "        )\n\n" % status
    )
    return bloco


WRITE_NEW = (
    _handler(400, "BusinessRuleViolation", True)
    + _handler(404, "NotFoundError", True)
    + _handler(409, "ConflictError", True)
    + WRITE_OLD
)

READ_NEW = (
    _handler(400, "BusinessRuleViolation", False)
    + _handler(404, "NotFoundError", False)
    + _handler(409, "ConflictError", False)
    + READ_OLD
)


def _migrar_router():
    texto = ROUTER.read_text(encoding="utf-8-sig")
    if "except BusinessRuleViolation as erro" in texto:
        return "MIGRADO"
    n_write = texto.count(WRITE_OLD)
    n_read = texto.count(READ_OLD)
    if n_write == 0 and n_read == 0:
        return "DESCONHECIDO"
    if n_write != 5 or n_read != 4:
        return "DESCONHECIDO (write=%d read=%d)" % (n_write, n_read)
    backup = ROUTER.with_name(ROUTER.name + ".bak_10vg")
    shutil.copy2(ROUTER, backup)
    try:
        novo = texto.replace(WRITE_OLD, WRITE_NEW)
        novo = novo.replace(READ_OLD, READ_NEW)
        ancora = "from infrastructure.database.unit_of_work import SqlServerUnitOfWork\n"
        if ancora not in novo:
            raise ValueError("ancora de import nao encontrada no router")
        novo = novo.replace(
            ancora,
            "from domain.exceptions import BusinessRuleViolation, ConflictError, NotFoundError\n\n" + ancora,
            1,
        )
        if novo.count("except BusinessRuleViolation as erro") != 9:
            raise ValueError("esperados 9 handlers BRV, obtido %d" % novo.count("except BusinessRuleViolation as erro"))
        ROUTER.write_text(novo, encoding="utf-8")
        py_compile.compile(str(ROUTER), doraise=True)
        return "OK (9 rotas tratadas)"
    except Exception as exc:
        shutil.copy2(backup, ROUTER)
        return "ERRO:" + str(exc)


# ---------------- Parte 2: Service ----------------

MAPA = {400: "BusinessRuleViolation", 404: "NotFoundError", 409: "ConflictError"}


def _achar_fim(texto, inicio):
    nivel = 1
    i = inicio
    n = len(texto)
    em_string = False
    aspas = None
    while i < n:
        c = texto[i]
        if em_string:
            if c == aspas:
                em_string = False
                aspas = None
        elif c in ('"', "'"):
            em_string = True
            aspas = c
        elif c == "(":
            nivel += 1
        elif c == ")":
            nivel -= 1
            if nivel == 0:
                return i
        i += 1
    return -1


def _mensagem(detail_body):
    if re.search(r'f["\']|\{', detail_body):
        raise ValueError("f-string/expressao em detail que seria convertido")
    return "".join(re.findall(r'"([^"]*)"', detail_body))


def _processar_servico(texto):
    resultado = []
    pos = 0
    convertidos = {400: 0, 404: 0, 409: 0}
    pulados = []
    while True:
        idx = texto.find("raise HTTPException(", pos)
        if idx == -1:
            resultado.append(texto[pos:])
            break
        linha_inicio = texto.rfind("\n", 0, idx) + 1
        indent = texto[linha_inicio:idx]
        if indent.strip() != "":
            indent = ""
        resultado.append(texto[pos:idx])
        inicio_bloco = idx + len("raise HTTPException(")
        fim = _achar_fim(texto, inicio_bloco)
        if fim == -1:
            raise ValueError("parentese desbalanceado (pos %d)" % idx)
        bloco = texto[inicio_bloco:fim]
        m_status = re.search(r"status_code\s*=\s*(\d+)", bloco)
        if not m_status:
            raise ValueError("status_code ausente (pos %d)" % idx)
        status = int(m_status.group(1))
        m_detail = re.search(r"detail\s*=\s*(.*)", bloco, re.DOTALL)
        if not m_detail:
            raise ValueError("detail ausente (pos %d)" % idx)
        classe = MAPA.get(status)
        if classe is None:
            resultado.append(texto[idx:fim + 1])
            pulados.append(status)
        else:
            mensagem = _mensagem(m_detail.group(1))
            resultado.append("%sraise %s(\n%s    \"%s\"\n%s)" % (indent, classe, indent, mensagem, indent))
            convertidos[status] += 1
        pos = fim + 1
    return "".join(resultado), convertidos, pulados


def _migrar_servico():
    texto = SERVICE.read_text(encoding="utf-8-sig")
    if "raise BusinessRuleViolation" in texto:
        return "MIGRADO"
    backup = SERVICE.with_name(SERVICE.name + ".bak_10vg")
    shutil.copy2(SERVICE, backup)
    try:
        novo, convertidos, pulados = _processar_servico(texto)
        if (convertidos[400], convertidos[404], convertidos[409]) != (12, 5, 3):
            raise ValueError("contagem divergente: %s" % convertidos)
        if pulados != [500]:
            raise ValueError("pulados inesperados: %s" % pulados)
        novo = novo.replace(
            "from fastapi import HTTPException\n",
            "from fastapi import HTTPException\nfrom domain.exceptions import BusinessRuleViolation, ConflictError, NotFoundError\n",
            1,
        )
        SERVICE.write_text(novo, encoding="utf-8")
        py_compile.compile(str(SERVICE), doraise=True)
        return "OK (400:%d 404:%d 409:%d 500:pulou)" % (convertidos[400], convertidos[404], convertidos[409])
    except Exception as exc:
        shutil.copy2(backup, SERVICE)
        return "ERRO:" + str(exc)


def main():
    print("=" * 70)
    print("FASE 10V-G - usuarios.py (router + service)")
    print("=" * 70)
    r = _migrar_router()
    print("[ROUTER ] " + r)
    if r.startswith("ERRO") or r.startswith("DESCONHECIDO"):
        sys.exit(3)
    s = _migrar_servico()
    print("[SERVICE] " + s)
    if s.startswith("ERRO"):
        sys.exit(3)
    print("[OK] Fase 10V-G concluida.")


if __name__ == "__main__":
    main()
