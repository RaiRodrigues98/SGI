from pathlib import Path
import ast
import shutil
import py_compile
import re
from datetime import datetime

ROOT = Path.cwd()
service = ROOT / "services" / "ciclos_rotativo.py"
router = ROOT / "routers" / "rotativo_ciclos.py"

for arq in (service, router):
    if not arq.exists():
        raise FileNotFoundError(f"Não encontrado: {arq}")

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backups = {}
for arq in (service, router):
    backup = arq.with_name(f"{arq.stem}_backup_uow_{timestamp}{arq.suffix}")
    shutil.copy2(arq, backup)
    backups[arq] = backup


def defs_por_nome(texto, nome):
    tree = ast.parse(texto)
    return [
        n for n in tree.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        and n.name == nome
    ]


def substituir_funcao(texto, node, novo_trecho):
    linhas = texto.splitlines(True)
    ini = node.lineno - 1
    fim = node.end_lineno
    return "".join(linhas[:ini]) + novo_trecho + "".join(linhas[fim:])


def extrair_funcao(texto, node):
    linhas = texto.splitlines(True)
    return "".join(linhas[node.lineno - 1:node.end_lineno])


def remover_wrapper_transacional(func_texto, nome_funcao):
    padrao = re.compile(
        r"(?ms)^    try:\n"
        r"(?P<body>.*?)"
        r"^    except Exception:\n"
        r"        conn\.rollback\(\)\n"
        r"        raise\n"
    )
    matches = list(padrao.finditer(func_texto))
    if len(matches) != 1:
        raise RuntimeError(
            f"{nome_funcao}: esperado 1 wrapper try/except transacional; "
            f"encontrados {len(matches)}."
        )

    def repl(match):
        body = match.group("body")
        saida = []
        for linha in body.splitlines(True):
            if linha.startswith("        "):
                linha = linha[4:]
            saida.append(linha)
        return "".join(saida)

    return padrao.sub(repl, func_texto, count=1)


def localizar_funcao_router_por_chamada(texto, chamada):
    tree = ast.parse(texto)
    achadas = []
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for n in ast.walk(fn):
            if (
                isinstance(n, ast.Call)
                and isinstance(n.func, ast.Name)
                and n.func.id == chamada
            ):
                achadas.append(fn)
                break
    if len(achadas) != 1:
        raise RuntimeError(
            f"Router: esperada 1 função chamando {chamada}; "
            f"encontradas {len(achadas)}."
        )
    return achadas[0]


def transformar_endpoint(func_texto, chamada, ja_tem_resultado=False):
    # Remove conn=conn apenas da chamada alvo.
    padrao_call = re.compile(
        rf"(?ms)(?P<prefix>^[ \t]*(?:return |resultado = ){re.escape(chamada)}\(\n)"
        r"(?P<body>.*?)"
        r"(?P<close>^[ \t]*\)\n)"
    )
    m = padrao_call.search(func_texto)
    if not m:
        raise RuntimeError(f"Chamada {chamada} não localizada no endpoint.")

    bloco = m.group(0)
    if bloco.count("conn=conn,") != 1:
        raise RuntimeError(
            f"{chamada}: esperado exatamente 1 argumento conn=conn."
        )

    bloco_novo = bloco.replace("            conn=conn,\n", "", 1)

    if not ja_tem_resultado:
        bloco_novo = bloco_novo.replace(
            f"        return {chamada}(",
            f"        resultado = {chamada}(",
            1
        )

    # Commit deve ocorrer imediatamente após o service e antes do retorno.
    if ja_tem_resultado:
        alvo_retorno = "\n        return resultado"
        if alvo_retorno not in func_texto[m.end():]:
            raise RuntimeError(
                f"{chamada}: return resultado não encontrado após a chamada."
            )
        # Primeiro substitui a chamada.
        func_texto = func_texto[:m.start()] + bloco_novo + func_texto[m.end():]
        # Insere commit no primeiro return resultado posterior.
        pos_busca = func_texto.find("        return resultado", m.start())
        func_texto = (
            func_texto[:pos_busca]
            + "        uow.commit()\n\n"
            + func_texto[pos_busca:]
        )
    else:
        bloco_novo = bloco_novo.rstrip("\n") + "\n\n        uow.commit()\n        return resultado\n"
        func_texto = func_texto[:m.start()] + bloco_novo + func_texto[m.end():]

    # Contrato semântico 400 da Fase 11.
    if "except ValueError as erro:" not in func_texto:
        raise RuntimeError(
            f"{chamada}: except ValueError esperado não encontrado."
        )
    func_texto = func_texto.replace(
        "except ValueError as erro:",
        "except BusinessRuleViolation as erro:",
        1
    )

    # Rollback em todos os caminhos de exceção do endpoint.
    bloco_business = """    except BusinessRuleViolation as erro:
        raise HTTPException(
"""
    bloco_business_novo = """    except BusinessRuleViolation as erro:
        if conn:
            uow.rollback()

        raise HTTPException(
"""
    if bloco_business not in func_texto:
        raise RuntimeError(
            f"{chamada}: bloco BusinessRuleViolation não localizado."
        )
    func_texto = func_texto.replace(
        bloco_business, bloco_business_novo, 1
    )

    bloco_http = """    except HTTPException:
        raise
"""
    bloco_http_novo = """    except HTTPException:
        if conn:
            uow.rollback()

        raise
"""
    if bloco_http not in func_texto:
        raise RuntimeError(
            f"{chamada}: bloco HTTPException não localizado."
        )
    func_texto = func_texto.replace(bloco_http, bloco_http_novo, 1)

    bloco_exc = """    except Exception as erro:
        raise HTTPException(
"""
    bloco_exc_novo = """    except Exception as erro:
        if conn:
            uow.rollback()

        raise HTTPException(
"""
    if bloco_exc not in func_texto:
        raise RuntimeError(
            f"{chamada}: bloco Exception não localizado."
        )
    func_texto = func_texto.replace(bloco_exc, bloco_exc_novo, 1)

    return func_texto


try:
    # ========================================================
    # SERVICE: REPARO E OWNERSHIP
    # ========================================================
    texto = service.read_text(encoding="utf-8")

    # Fase 11: este arquivo tinha 9 ValueError migrados.
    qtd_value = texto.count("raise ValueError(")
    if qtd_value != 9:
        raise RuntimeError(
            f"ciclos_rotativo.py: esperados 9 ValueError da versão regredida; "
            f"encontrados {qtd_value}. Nenhuma alteração aplicada."
        )

    if "from domain.exceptions import BusinessRuleViolation" not in texto:
        # Mantém imports existentes e adiciona apenas o necessário.
        texto = "from domain.exceptions import BusinessRuleViolation\n" + texto

    texto = texto.replace("raise ValueError(", "raise BusinessRuleViolation(")

    # Remove a primeira definição duplicada de finalizar_ciclo_rotativo.
    finais = defs_por_nome(texto, "finalizar_ciclo_rotativo")
    if len(finais) != 2:
        raise RuntimeError(
            f"Esperadas 2 definições de finalizar_ciclo_rotativo; "
            f"encontradas {len(finais)}."
        )

    linhas = texto.splitlines(True)
    primeiro = finais[0]
    texto = (
        "".join(linhas[:primeiro.lineno - 1])
        + "".join(linhas[primeiro.end_lineno:])
    )

    # Reparse após remoção.
    finais = defs_por_nome(texto, "finalizar_ciclo_rotativo")
    aberturas = defs_por_nome(texto, "abrir_ciclo_rotativo")
    if len(finais) != 1 or len(aberturas) != 1:
        raise RuntimeError(
            "Estrutura após remoção da duplicidade ficou inesperada."
        )

    # Transformar ABRIR.
    node = aberturas[0]
    trecho = extrair_funcao(texto, node)

    sig = """def abrir_ciclo_rotativo(
    conn,
    cursor,"""
    if sig not in trecho:
        raise RuntimeError("Assinatura esperada de abrir_ciclo_rotativo não encontrada.")
    trecho = trecho.replace(
        sig,
        """def abrir_ciclo_rotativo(
    cursor,""",
        1
    )

    trecho = remover_wrapper_transacional(
        trecho, "abrir_ciclo_rotativo"
    )

    if trecho.count("conn.commit()") != 1:
        raise RuntimeError(
            "abrir_ciclo_rotativo: esperado 1 commit interno."
        )
    trecho = trecho.replace("    conn.commit()\n", "", 1)

    # Node original ainda vale para substituição neste texto.
    texto = substituir_funcao(texto, node, trecho)

    # Reparse antes da finalização.
    final_node = defs_por_nome(texto, "finalizar_ciclo_rotativo")[0]
    trecho = extrair_funcao(texto, final_node)

    sig = """def finalizar_ciclo_rotativo(
    conn,
    cursor,"""
    if sig not in trecho:
        raise RuntimeError(
            "Assinatura esperada de finalizar_ciclo_rotativo não encontrada."
        )
    trecho = trecho.replace(
        sig,
        """def finalizar_ciclo_rotativo(
    cursor,""",
        1
    )

    trecho = remover_wrapper_transacional(
        trecho, "finalizar_ciclo_rotativo"
    )

    # Após remover o wrapper, sobra o rollback concorrencial explícito.
    commits = trecho.count("conn.commit()")
    rollbacks = trecho.count("conn.rollback()")
    if commits != 1 or rollbacks != 1:
        raise RuntimeError(
            "finalizar_ciclo_rotativo: esperados 1 commit e 1 rollback "
            f"remanescentes; encontrados commit={commits}, rollback={rollbacks}."
        )

    trecho = trecho.replace("        conn.rollback()\n\n", "", 1)
    trecho = trecho.replace("    conn.commit()\n", "", 1)

    texto = substituir_funcao(texto, final_node, trecho)

    if texto.count("def finalizar_ciclo_rotativo(") != 1:
        raise RuntimeError("Duplicidade de finalizar_ciclo_rotativo ainda existe.")

    if "conn.commit()" in texto or "conn.rollback()" in texto:
        raise RuntimeError(
            "Ainda existe commit/rollback em services/ciclos_rotativo.py."
        )

    if "raise ValueError(" in texto:
        raise RuntimeError(
            "Ainda existe ValueError em services/ciclos_rotativo.py."
        )

    service.write_text(texto, encoding="utf-8")

    # ========================================================
    # ROUTER
    # ========================================================
    texto = router.read_text(encoding="utf-8")

    # Restaura contrato Fase 11 de todo este router.
    if "from domain.exceptions import BusinessRuleViolation" not in texto:
        marcador = (
            "from infrastructure.database.unit_of_work import "
            "SqlServerUnitOfWork\n"
        )
        if marcador not in texto:
            raise RuntimeError("Import do SqlServerUnitOfWork não encontrado.")
        texto = texto.replace(
            marcador,
            marcador + "\nfrom domain.exceptions import BusinessRuleViolation\n",
            1
        )

    # Todas as capturas ValueError deste router eram contrato 400.
    texto = texto.replace(
        "except ValueError as erro:",
        "except BusinessRuleViolation as erro:"
    )

    # Para transformar endpoints, temporariamente recoloca o marcador apenas
    # dentro deles para a rotina exigir/validar o ponto correto.
    # Endpoint abrir.
    fn = localizar_funcao_router_por_chamada(
        texto, "abrir_ciclo_rotativo"
    )
    trecho = extrair_funcao(texto, fn)

    # Como o replace global já ocorreu, a rotina espera ValueError.
    trecho = trecho.replace(
        "except BusinessRuleViolation as erro:",
        "except ValueError as erro:",
        1
    )
    trecho = transformar_endpoint(
        trecho,
        "abrir_ciclo_rotativo",
        ja_tem_resultado=False
    )
    texto = substituir_funcao(texto, fn, trecho)

    # Endpoint finalizar.
    fn = localizar_funcao_router_por_chamada(
        texto, "finalizar_ciclo_rotativo"
    )
    trecho = extrair_funcao(texto, fn)
    trecho = trecho.replace(
        "except BusinessRuleViolation as erro:",
        "except ValueError as erro:",
        1
    )
    trecho = transformar_endpoint(
        trecho,
        "finalizar_ciclo_rotativo",
        ja_tem_resultado=True
    )
    texto = substituir_funcao(texto, fn, trecho)

    # Nenhum ValueError catch deve restar neste router.
    if "except ValueError as erro:" in texto:
        raise RuntimeError(
            "Ainda existe except ValueError em routers/rotativo_ciclos.py."
        )

    # As duas chamadas não recebem mais conn.
    for chamada in ("abrir_ciclo_rotativo", "finalizar_ciclo_rotativo"):
        tree = ast.parse(texto)
        calls = [
            n for n in ast.walk(tree)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id == chamada
        ]
        if len(calls) != 1:
            raise RuntimeError(
                f"Esperada 1 chamada de {chamada}; encontradas {len(calls)}."
            )
        if any(kw.arg == "conn" for kw in calls[0].keywords):
            raise RuntimeError(
                f"{chamada}: argumento conn ainda presente no router."
            )

    router.write_text(texto, encoding="utf-8")

    # ========================================================
    # VALIDAÇÃO
    # ========================================================
    py_compile.compile(str(service), doraise=True)
    py_compile.compile(str(router), doraise=True)

    service_final = service.read_text(encoding="utf-8")
    router_final = router.read_text(encoding="utf-8")

    assert service_final.count("def finalizar_ciclo_rotativo(") == 1
    assert "raise ValueError(" not in service_final
    assert "conn.commit()" not in service_final
    assert "conn.rollback()" not in service_final
    assert router_final.count("uow.commit()") >= 2

except Exception:
    for arq, backup in backups.items():
        shutil.copy2(backup, arq)
    raise

print("APROVADO")
print()
print("services/ciclos_rotativo.py")
print("- primeira implementação duplicada de finalizar_ciclo_rotativo removida")
print("- 9 ValueError -> BusinessRuleViolation")
print("- conn removido de abrir_ciclo_rotativo/finalizar_ciclo_rotativo")
print("- commit/rollback removidos do service")
print()
print("routers/rotativo_ciclos.py")
print("- catches ValueError restaurados para BusinessRuleViolation")
print("- abertura do ciclo: commit no UoW")
print("- finalização do ciclo: commit no UoW")
print("- rollback em BusinessRuleViolation, HTTPException e Exception")
print("- chamadas dos services sem conn")
print()
print("py_compile: APROVADO")
print()
print("Backups:")
for backup in backups.values():
    print(backup)
