# -*- coding: utf-8 -*-
"""Fase 10V-H - Desacoplar auth.py (401/403 -> dominio).

1. domain/exceptions.py : cria AuthenticationError(401) e AuthorizationError(403).
2. services/auth.py      : 7x401->AuthenticationError, 1x403->AuthorizationError.
3. routers/auth.py       : handlers 401/403 no login (com rollback).
4. dependencies/auth.py  : protege decodificar_token (AuthenticationError->401).

Ordem: dominio -> service -> router -> dependency. Idempotente. Backup + py_compile.
"""
import py_compile
import re
import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DOMINIO = RAIZ / "domain" / "exceptions.py"
SERVICE = RAIZ / "services" / "auth.py"
ROUTER = RAIZ / "routers" / "auth.py"
DEPEND = RAIZ / "dependencies" / "auth.py"


def _backup(p):
    return p.with_name(p.name + ".bak_10vh")


# ---------------- Passo 1: domain/exceptions.py ----------------

def _passo_dominio():
    texto = DOMINIO.read_text(encoding="utf-8-sig")
    tem_auth = "class AuthenticationError" in texto
    tem_authz = "class AuthorizationError" in texto
    if tem_auth and tem_authz:
        return "MIGRADO"
    if tem_auth or tem_authz:
        return "DESCONHECIDO (parcial)"
    backup = _backup(DOMINIO)
    shutil.copy2(DOMINIO, backup)
    try:
        novo = texto
        if not novo.endswith("\n"):
            novo += "\n"
        novo += (
            "\n"
            "\n"
            "class AuthenticationError(DomainError):\n"
            '    """Falha de autenticacao (credenciais invalidas ou token ausente/expirado) -> HTTP 401."""\n'
            "\n"
            "    pass\n"
            "\n"
            "\n"
            "class AuthorizationError(DomainError):\n"
            '    """Usuario autenticado sem permissao para a acao -> HTTP 403."""\n'
            "\n"
            "    pass\n"
        )
        DOMINIO.write_text(novo, encoding="utf-8")
        py_compile.compile(str(DOMINIO), doraise=True)
        return "OK (AuthenticationError + AuthorizationError)"
    except Exception as exc:
        shutil.copy2(backup, DOMINIO)
        return "ERRO:" + str(exc)


# ---------------- Passo 2: services/auth.py ----------------

MAPA = {401: "AuthenticationError", 403: "AuthorizationError"}


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
    achados = re.findall(r'"([^"]*)"', detail_body)
    if len(achados) != 1:
        raise ValueError("detail inesperado: %r" % detail_body)
    return achados[0]


def _passo_servico():
    texto = SERVICE.read_text(encoding="utf-8-sig")
    if "raise AuthenticationError" in texto:
        return "MIGRADO"
    backup = _backup(SERVICE)
    shutil.copy2(SERVICE, backup)
    try:
        resultado = []
        pos = 0
        convertidos = {401: 0, 403: 0}
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
                raise ValueError("status inesperado %d (pos %d)" % (status, idx))
            mensagem = _mensagem(m_detail.group(1))
            resultado.append("%sraise %s(\n%s    \"%s\"\n%s)" % (indent, classe, indent, mensagem, indent))
            convertidos[status] += 1
            pos = fim + 1
        novo = "".join(resultado)
        if (convertidos[401], convertidos[403]) != (7, 1):
            raise ValueError("contagem divergente: %s" % convertidos)
        if "HTTPException" not in novo:
            novo = re.sub(r"^from fastapi import HTTPException[ \t]*\r?\n", "", novo, flags=re.MULTILINE)
        novo = re.sub(
            r"(from fastapi import HTTPException[ \t]*\r?\n)",
            r"\1from domain.exceptions import AuthenticationError, AuthorizationError\n",
            novo,
            count=1,
        )
        SERVICE.write_text(novo, encoding="utf-8")
        py_compile.compile(str(SERVICE), doraise=True)
        return "OK (401:%d 403:%d)" % (convertidos[401], convertidos[403])
    except Exception as exc:
        shutil.copy2(backup, SERVICE)
        return "ERRO:" + str(exc)


# ---------------- Passo 3: routers/auth.py ----------------

ROUTER_OLD = (
    "    except HTTPException:\n"
    "\n"
    "        if conn:\n"
    "            uow.rollback()\n"
    "\n"
    "        raise\n"
)

ROUTER_NEW = (
    "    except AuthenticationError as erro:\n"
    "\n"
    "        if conn:\n"
    "            uow.rollback()\n"
    "\n"
    "        raise HTTPException(\n"
    "            status_code=401,\n"
    "            detail=str(erro)\n"
    "        )\n"
    "\n"
    "    except AuthorizationError as erro:\n"
    "\n"
    "        if conn:\n"
    "            uow.rollback()\n"
    "\n"
    "        raise HTTPException(\n"
    "            status_code=403,\n"
    "            detail=str(erro)\n"
    "        )\n"
    "\n"
    + ROUTER_OLD
)


def _passo_router():
    texto = ROUTER.read_text(encoding="utf-8-sig")
    if "except AuthenticationError as erro" in texto:
        return "MIGRADO"
    if texto.count(ROUTER_OLD) != 1:
        return "DESCONHECIDO (bloco except=%d)" % texto.count(ROUTER_OLD)
    backup = _backup(ROUTER)
    shutil.copy2(ROUTER, backup)
    try:
        novo = texto.replace(ROUTER_OLD, ROUTER_NEW, 1)
        ancora = "from infrastructure.database.unit_of_work import SqlServerUnitOfWork\n"
        if ancora not in novo:
            raise ValueError("ancora de import nao encontrada")
        novo = novo.replace(
            ancora,
            "from domain.exceptions import AuthenticationError, AuthorizationError\n\n" + ancora,
            1,
        )
        ROUTER.write_text(novo, encoding="utf-8")
        py_compile.compile(str(ROUTER), doraise=True)
        return "OK (login com handlers 401/403)"
    except Exception as exc:
        shutil.copy2(backup, ROUTER)
        return "ERRO:" + str(exc)


# ---------------- Passo 4: dependencies/auth.py ----------------

DEPEND_OLD = (
    "    dados_token = decodificar_token(\n"
    "        credenciais.credentials\n"
    "    )\n"
)

DEPEND_NEW = (
    "    try:\n"
    "\n"
    "        dados_token = decodificar_token(\n"
    "            credenciais.credentials\n"
    "        )\n"
    "\n"
    "    except AuthenticationError as erro:\n"
    "\n"
    "        raise HTTPException(\n"
    "            status_code=status.HTTP_401_UNAUTHORIZED,\n"
    "            detail=str(erro),\n"
    "            headers={\n"
    '                "WWW-Authenticate":\n'
    '                    "Bearer"\n'
    "            }\n"
    "        )\n"
)


def _passo_dependencia():
    texto = DEPEND.read_text(encoding="utf-8-sig")
    if "except AuthenticationError as erro" in texto:
        return "MIGRADO"
    if texto.count(DEPEND_OLD) != 1:
        return "DESCONHECIDO (bloco=%d)" % texto.count(DEPEND_OLD)
    backup = _backup(DEPEND)
    shutil.copy2(DEPEND, backup)
    try:
        novo = texto.replace(DEPEND_OLD, DEPEND_NEW, 1)
        ancora = "from services.auth import (\n    decodificar_token,\n)\n"
        if ancora not in novo:
            raise ValueError("ancora de import nao encontrada")
        novo = novo.replace(
            ancora,
            ancora + "\nfrom domain.exceptions import AuthenticationError\n",
            1,
        )
        DEPEND.write_text(novo, encoding="utf-8")
        py_compile.compile(str(DEPEND), doraise=True)
        return "OK (decodificar_token protegido)"
    except Exception as exc:
        shutil.copy2(backup, DEPEND)
        return "ERRO:" + str(exc)


def main():
    print("=" * 70)
    print("FASE 10V-H - auth.py (401/403 -> dominio)")
    print("=" * 70)
    resultados = [
        ("[DOMINIO ]", _passo_dominio()),
        ("[SERVICE ]", _passo_servico()),
        ("[ROUTER  ]", _passo_router()),
        ("[DEPEND  ]", _passo_dependencia()),
    ]
    for rotulo, r in resultados:
        print(rotulo, r)
        if r.startswith("ERRO") or r.startswith("DESCONHECIDO"):
            sys.exit(3)
    print("[OK] Fase 10V-H concluida.")


if __name__ == "__main__":
    main()
