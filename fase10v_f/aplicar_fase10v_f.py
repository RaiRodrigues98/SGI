# -*- coding: utf-8 -*-
"""Fase 10V-F - Conversao em massa HTTPException -> excecoes de dominio.

Converte 400->BusinessRuleViolation, 404->NotFoundError, 409->ConflictError
nos arquivos cujos routers ja possuem handlers equivalentes.

ADIA (nao converte): 401/403 (auth.py), 500 (erro tecnico) e
services/usuarios.py (routers/usuarios.py ainda SEM handlers de dominio).

Idempotente por arquivo. Backup (.bak_10vf) + py_compile + rollback em falha.
"""
import py_compile
import re
import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

# arquivo -> (esperado_400, esperado_404, esperado_409, esperado_500_restante)
ALVOS = {
    "services/configuracoes_operacionais.py": (9, 1, 0, 1),
    "services/decisoes_rotativo.py": (13, 2, 0, 0),
    "services/encaminhamento_gestor.py": (13, 2, 0, 0),
    "services/finalizacao_inventario.py": (12, 1, 0, 1),
    "services/finalizacao_rotativo.py": (14, 3, 0, 2),
    "services/ocorrencias_divergencia.py": (11, 3, 0, 0),
}

MAPA = {400: "BusinessRuleViolation", 404: "NotFoundError", 409: "ConflictError"}
NOMES = re.compile(r"\b(BusinessRuleViolation|NotFoundError|ConflictError|DomainError)\b")


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


def _processar_texto(texto):
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
            raise ValueError("parentese desbalanceado em raise HTTPException (pos %d)" % idx)
        bloco = texto[inicio_bloco:fim]
        m_status = re.search(r"status_code\s*=\s*(\d+)", bloco)
        if not m_status:
            raise ValueError("status_code ausente (pos %d)" % idx)
        status = int(m_status.group(1))
        m_detail = re.search(r"detail\s*=\s*(.*)", bloco, re.DOTALL)
        if not m_detail:
            raise ValueError("detail ausente (pos %d)" % idx)
        mensagem = "".join(re.findall(r'"([^"]*)"', m_detail.group(1)))
        classe = MAPA.get(status)
        if classe is None:
            resultado.append(texto[idx:fim + 1])
            pulados.append(status)
        else:
            resultado.append(
                "%sraise %s(\n%s    \"%s\"\n%s)" % (indent, classe, indent, mensagem, indent)
            )
            convertidos[status] += 1
        pos = fim + 1
    return "".join(resultado), convertidos, pulados


def _garantir_imports(texto, classes):
    m = re.search(r"from domain\.exceptions import ", texto)
    if m:
        inicio = m.start()
        fim_linha = texto.find("\n", inicio)
        if fim_linha == -1:
            fim_linha = len(texto)
        linha = texto[inicio:fim_linha]
        existentes = set(NOMES.findall(linha))
        if linha.rstrip().endswith("("):
            idx_abre = inicio + linha.rfind("(")
            fim_paren = _achar_fim(texto, idx_abre + 1)
            if fim_paren == -1:
                raise ValueError("import domain.exceptions multiline desbalanceado")
            existentes |= set(NOMES.findall(texto[inicio:fim_paren + 1]))
            faltantes = classes - existentes
            if not faltantes:
                return texto
            nova = "from domain.exceptions import " + ", ".join(sorted(existentes | classes))
            return texto[:inicio] + nova + texto[fim_paren + 1:]
        faltantes = classes - existentes
        if not faltantes:
            return texto
        nova = "from domain.exceptions import " + ", ".join(sorted(existentes | classes))
        return texto[:inicio] + nova + texto[fim_linha:]
    linha = "from domain.exceptions import " + ", ".join(sorted(classes))
    m2 = re.search(r"^from ", texto, re.MULTILINE)
    if m2:
        return texto[:m2.start()] + linha + "\n" + texto[m2.start():]
    return linha + "\n" + texto


def _processar_arquivo(caminho, esperado):
    p = RAIZ / caminho
    texto = p.read_text(encoding="utf-8-sig")
    if "raise HTTPException(" not in texto:
        return "MIGRADO", None
    if not re.search(r"status_code\s*=\s*(400|404|409)", texto):
        return "MIGRADO", None
    backup = p.with_name(p.name + ".bak_10vf")
    shutil.copy2(p, backup)
    try:
        novo, convertidos, pulados = _processar_texto(texto)
        exp400, exp404, exp409, _ = esperado
        if (convertidos[400], convertidos[404], convertidos[409]) != (exp400, exp404, exp409):
            raise ValueError(
                "contagem divergente: esperado 400=%d/404=%d/409=%d, obtido 400=%d/404=%d/409=%d"
                % (exp400, exp404, exp409, convertidos[400], convertidos[404], convertidos[409])
            )
        classes = set()
        if convertidos[400]:
            classes.add("BusinessRuleViolation")
        if convertidos[404]:
            classes.add("NotFoundError")
        if convertidos[409]:
            classes.add("ConflictError")
        if classes:
            novo = _garantir_imports(novo, classes)
        if "raise HTTPException" not in novo and "HTTPException" not in novo:
            novo = re.sub(r"^from fastapi import HTTPException[ \t]*\r?\n", "", novo, flags=re.MULTILINE)
        p.write_text(novo, encoding="utf-8")
        py_compile.compile(str(p), doraise=True)
        return "OK", (convertidos, pulados)
    except Exception as exc:
        shutil.copy2(backup, p)
        return "ERRO", str(exc)


def main():
    print("=" * 70)
    print("FASE 10V-F - CONVERSAO EM MASSA (400/404/409 -> dominio)")
    print("=" * 70)
    total_ok = 0
    total_conv = {400: 0, 404: 0, 409: 0}
    for caminho, esperado in ALVOS.items():
        estado, dados = _processar_arquivo(caminho, esperado)
        if estado == "OK":
            convertidos, pulados = dados
            total_ok += 1
            total_conv[400] += convertidos[400]
            total_conv[404] += convertidos[404]
            total_conv[409] += convertidos[409]
            print("[OK]  %s -> 400:%d 404:%d 409:%d  pulados:%s"
                  % (caminho, convertidos[400], convertidos[404], convertidos[409], pulados))
        elif estado == "MIGRADO":
            print("[SKIP] %s -> ja migrado" % caminho)
        else:
            print("[ERRO] %s -> %s" % (caminho, dados))
            sys.exit(3)
    print("-" * 70)
    print("Arquivos convertidos: %d/%d" % (total_ok, len(ALVOS)))
    print("Total convertido: 400:%d 404:%d 409:%d" % (total_conv[400], total_conv[404], total_conv[409]))
    print("[OK] Fase 10V-F aplicada.")


if __name__ == "__main__":
    main()
