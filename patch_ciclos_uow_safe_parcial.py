from pathlib import Path
import ast
import shutil
import py_compile
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
    backup = arq.with_name(
        f"{arq.stem}_backup_ciclos_safe_{timestamp}{arq.suffix}"
    )
    shutil.copy2(arq, backup)
    backups[arq] = backup


def restaurar():
    for arq, backup in backups.items():
        shutil.copy2(backup, arq)


def top_def(texto, nome):
    tree = ast.parse(texto)
    defs = [
        n for n in tree.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        and n.name == nome
    ]
    if len(defs) != 1:
        raise RuntimeError(
            f"{nome}: esperada exatamente 1 definição; encontradas {len(defs)}."
        )
    return defs[0]


def extrair(texto, node):
    linhas = texto.splitlines(True)
    return "".join(linhas[node.lineno - 1:node.end_lineno])


def substituir(texto, node, novo):
    linhas = texto.splitlines(True)
    return (
        "".join(linhas[:node.lineno - 1])
        + novo
        + "".join(linhas[node.end_lineno:])
    )


def unwrap_transaction(func_texto, nome):
    """
    Remove exatamente:
        try:
            ...
        except Exception:
            conn.rollback()
            raise
    no nível da função, sem regex.
    """
    linhas = func_texto.splitlines(True)
    try_idx = None
    except_idx = None

    for i, linha in enumerate(linhas):
        if linha == "    try:\n":
            if try_idx is not None:
                raise RuntimeError(f"{nome}: mais de um try de nível principal.")
            try_idx = i

    if try_idx is None:
        raise RuntimeError(f"{nome}: wrapper try transacional não encontrado.")

    for j in range(try_idx + 1, len(linhas)):
        if linhas[j] == "    except Exception:\n":
            if (
                j + 2 < len(linhas)
                and linhas[j + 1] == "        conn.rollback()\n"
                and linhas[j + 2] == "        raise\n"
            ):
                except_idx = j
                break

    if except_idx is None:
        raise RuntimeError(
            f"{nome}: except Exception/rollback/raise transacional não encontrado."
        )

    body = linhas[try_idx + 1:except_idx]

    for linha in body:
        if linha.strip() and not linha.startswith("        "):
            raise RuntimeError(
                f"{nome}: corpo do try possui indentação inesperada: {linha!r}"
            )

    novo_body = []
    for linha in body:
        if linha.startswith("        "):
            novo_body.append(linha[4:])
        else:
            novo_body.append(linha)

    return (
        "".join(linhas[:try_idx])
        + "".join(novo_body)
        + "".join(linhas[except_idx + 3:])
    )


def ensure_brv_import(texto, router_mode=False):
    if "from domain.exceptions import BusinessRuleViolation" in texto:
        return texto

    if router_mode:
        marker = (
            "from infrastructure.database.unit_of_work import "
            "SqlServerUnitOfWork\n"
        )
        if marker not in texto:
            raise RuntimeError(
                "Router: import SqlServerUnitOfWork não encontrado."
            )
        return texto.replace(
            marker,
            marker + "\nfrom domain.exceptions import BusinessRuleViolation\n",
            1,
        )

    return "from domain.exceptions import BusinessRuleViolation\n" + texto


def localizar_endpoint(texto, chamada):
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


def transformar_endpoint(func_texto, chamada):
    linhas = func_texto.splitlines(True)

    # Localiza linha inicial da chamada alvo.
    call_idx = None
    for i, linha in enumerate(linhas):
        if (
            f"return {chamada}(" in linha
            or f"resultado = {chamada}(" in linha
        ):
            if call_idx is not None:
                raise RuntimeError(f"{chamada}: mais de uma chamada no endpoint.")
            call_idx = i

    if call_idx is None:
        raise RuntimeError(f"{chamada}: chamada não encontrada.")

    # Localiza fechamento da chamada por balanço simples de parênteses.
    balance = 0
    close_idx = None
    for i in range(call_idx, len(linhas)):
        balance += linhas[i].count("(") - linhas[i].count(")")
        if i > call_idx and balance == 0:
            close_idx = i
            break

    if close_idx is None:
        raise RuntimeError(f"{chamada}: fechamento da chamada não encontrado.")

    bloco = linhas[call_idx:close_idx + 1]

    conn_linhas = [
        k for k, linha in enumerate(bloco)
        if "conn=conn," in linha
    ]
    if len(conn_linhas) != 1:
        raise RuntimeError(
            f"{chamada}: esperado 1 argumento conn=conn; "
            f"encontrados {len(conn_linhas)}."
        )
    del bloco[conn_linhas[0]]

    # Se era return direto, converte para resultado.
    if f"return {chamada}(" in bloco[0]:
        bloco[0] = bloco[0].replace(
            f"return {chamada}(",
            f"resultado = {chamada}(",
            1,
        )

    # Substitui chamada.
    linhas = linhas[:call_idx] + bloco + linhas[close_idx + 1:]

    # Localiza o primeiro return resultado após a chamada.
    ret_idx = None
    for i in range(call_idx + len(bloco), len(linhas)):
        if linhas[i] == "        return resultado\n":
            ret_idx = i
            break

    if ret_idx is None:
        # Se era return direto, não havia return resultado; cria logo após chamada.
        insert_at = call_idx + len(bloco)
        linhas[insert_at:insert_at] = [
            "\n",
            "        uow.commit()\n",
            "        return resultado\n",
        ]
    else:
        # Insere commit imediatamente antes do return existente, se ainda não houver.
        if ret_idx == 0 or linhas[ret_idx - 1] != "        uow.commit()\n":
            linhas[ret_idx:ret_idx] = ["        uow.commit()\n\n"]

    texto = "".join(linhas)

    # Contrato semântico.
    texto = texto.replace(
        "except ValueError as erro:",
        "except BusinessRuleViolation as erro:",
    )

    # Rollback BusinessRuleViolation.
    old = """    except BusinessRuleViolation as erro:
        raise HTTPException(
"""
    new = """    except BusinessRuleViolation as erro:
        if conn:
            uow.rollback()

        raise HTTPException(
"""
    if old in texto:
        texto = texto.replace(old, new, 1)

    # Rollback HTTPException.
    old = """    except HTTPException:
        raise
"""
    new = """    except HTTPException:
        if conn:
            uow.rollback()

        raise
"""
    if old in texto:
        texto = texto.replace(old, new, 1)

    # Rollback generic.
    old = """    except Exception as erro:
        raise HTTPException(
"""
    new = """    except Exception as erro:
        if conn:
            uow.rollback()

        raise HTTPException(
"""
    if old in texto:
        texto = texto.replace(old, new, 1)

    return texto


try:
    # ============================================================
    # SERVICE
    # ============================================================
    texto = service.read_text(encoding="utf-8")

    valueerrors = texto.count("raise ValueError(")
    finalizers = texto.count("def finalizar_ciclo_rotativo(")
    commits = texto.count("conn.commit()")
    rollbacks = texto.count("conn.rollback()")

    if not (
        valueerrors == 6
        and finalizers == 1
        and commits == 2
        and rollbacks == 3
    ):
        raise RuntimeError(
            "Estado esperado não confere. "
            f"ValueError={valueerrors}, finalizers={finalizers}, "
            f"commit={commits}, rollback={rollbacks}. "
            "Esperado: 6, 1, 2, 3."
        )

    texto = ensure_brv_import(texto)
    texto = texto.replace(
        "raise ValueError(",
        "raise BusinessRuleViolation("
    )

    # ABRIR
    node = top_def(texto, "abrir_ciclo_rotativo")
    trecho = extrair(texto, node)

    sig_old = """def abrir_ciclo_rotativo(
    conn,
    cursor,"""
    sig_new = """def abrir_ciclo_rotativo(
    cursor,"""

    if sig_old not in trecho:
        raise RuntimeError(
            "abrir_ciclo_rotativo: assinatura com conn não encontrada."
        )
    trecho = trecho.replace(sig_old, sig_new, 1)
    trecho = unwrap_transaction(trecho, "abrir_ciclo_rotativo")

    if trecho.count("conn.commit()") != 1:
        raise RuntimeError(
            "abrir_ciclo_rotativo: esperado 1 commit após unwrap."
        )
    trecho = trecho.replace("    conn.commit()\n", "", 1)

    texto = substituir(texto, node, trecho)

    # FINALIZAR
    node = top_def(texto, "finalizar_ciclo_rotativo")
    trecho = extrair(texto, node)

    sig_old = """def finalizar_ciclo_rotativo(
    conn,
    cursor,"""
    sig_new = """def finalizar_ciclo_rotativo(
    cursor,"""

    if sig_old not in trecho:
        raise RuntimeError(
            "finalizar_ciclo_rotativo: assinatura com conn não encontrada."
        )
    trecho = trecho.replace(sig_old, sig_new, 1)
    trecho = unwrap_transaction(trecho, "finalizar_ciclo_rotativo")

    if trecho.count("conn.commit()") != 1:
        raise RuntimeError(
            "finalizar_ciclo_rotativo: esperado 1 commit após unwrap."
        )
    if trecho.count("conn.rollback()") != 1:
        raise RuntimeError(
            "finalizar_ciclo_rotativo: esperado 1 rollback concorrencial após unwrap."
        )

    # Remove rollback concorrencial explícito: UoW/router fará rollback.
    trecho = trecho.replace("        conn.rollback()\n\n", "", 1)
    trecho = trecho.replace("    conn.commit()\n", "", 1)

    texto = substituir(texto, node, trecho)

    if texto.count("raise ValueError(") != 0:
        raise RuntimeError("Ainda existe ValueError no service.")
    if texto.count("def finalizar_ciclo_rotativo(") != 1:
        raise RuntimeError("Quantidade de finalizadores mudou indevidamente.")
    if "conn.commit()" in texto or "conn.rollback()" in texto:
        raise RuntimeError("Ainda existe transação interna no service.")
    if "def abrir_ciclo_rotativo(\n    conn," in texto:
        raise RuntimeError("conn ainda está na assinatura de abrir.")
    if "def finalizar_ciclo_rotativo(\n    conn," in texto:
        raise RuntimeError("conn ainda está na assinatura de finalizar.")

    service.write_text(texto, encoding="utf-8")

    # ============================================================
    # ROUTER
    # ============================================================
    texto = router.read_text(encoding="utf-8")
    texto = ensure_brv_import(texto, router_mode=True)

    # Todos os ValueError catches remanescentes deste router eram contrato 400.
    texto = texto.replace(
        "except ValueError as erro:",
        "except BusinessRuleViolation as erro:"
    )

    # Abrir
    node = localizar_endpoint(texto, "abrir_ciclo_rotativo")
    trecho = extrair(texto, node)
    trecho = transformar_endpoint(trecho, "abrir_ciclo_rotativo")
    texto = substituir(texto, node, trecho)

    # Finalizar
    node = localizar_endpoint(texto, "finalizar_ciclo_rotativo")
    trecho = extrair(texto, node)
    trecho = transformar_endpoint(trecho, "finalizar_ciclo_rotativo")
    texto = substituir(texto, node, trecho)

    router.write_text(texto, encoding="utf-8")

    # ============================================================
    # VALIDAÇÃO
    # ============================================================
    sf = service.read_text(encoding="utf-8")
    rf = router.read_text(encoding="utf-8")

    if sf.count("raise BusinessRuleViolation(") < 6:
        raise RuntimeError("BRVs esperados não foram preservados.")
    if sf.count("def finalizar_ciclo_rotativo(") != 1:
        raise RuntimeError("Service não possui exatamente 1 finalizador.")
    if "conn.commit()" in sf or "conn.rollback()" in sf:
        raise RuntimeError("Service ainda possui commit/rollback.")

    tree = ast.parse(rf)
    for chamada in ("abrir_ciclo_rotativo", "finalizar_ciclo_rotativo"):
        calls = [
            n for n in ast.walk(tree)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id == chamada
        ]
        if len(calls) != 1:
            raise RuntimeError(
                f"Router: {chamada} deveria possuir exatamente 1 chamada."
            )
        if any(kw.arg == "conn" for kw in calls[0].keywords):
            raise RuntimeError(
                f"Router: argumento conn ainda presente em {chamada}."
            )

    if "except ValueError as erro:" in rf:
        raise RuntimeError("Router ainda possui catch ValueError.")

    # Pelo menos os endpoints abrir/finalizar devem ter commit/rollback UoW.
    if rf.count("uow.commit()") < 2:
        raise RuntimeError(
            f"Router possui somente {rf.count('uow.commit()')} uow.commit()."
        )
    if rf.count("uow.rollback()") < 6:
        raise RuntimeError(
            f"Router possui somente {rf.count('uow.rollback()')} uow.rollback()."
        )

    py_compile.compile(str(service), doraise=True)
    py_compile.compile(str(router), doraise=True)

except BaseException:
    restaurar()
    print("REPROVADO: ciclos_rotativo e router restaurados.")
    raise

print()
print("APROVADO")
print("- estado parcial 6/1/2/3 corrigido")
print("- 6 ValueError -> BusinessRuleViolation")
print("- abrir_ciclo_rotativo sem conn e sem transação interna")
print("- finalizar_ciclo_rotativo sem conn e sem transação interna")
print("- exatamente 1 finalizar_ciclo_rotativo")
print("- commit/rollback transferidos para UoW/router")
print("- py_compile aprovado")
print()
print("Backups:")
for backup in backups.values():
    print(backup)
