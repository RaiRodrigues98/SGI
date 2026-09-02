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
        f"{arq.stem}_backup_ciclos_safe_v2_{timestamp}{arq.suffix}"
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


def find_transaction_wrapper(func_texto, nome):
    """
    Localiza o try/except transacional principal usando AST.
    Aceita linhas em branco livremente.
    """
    tree = ast.parse(func_texto)
    fn = tree.body[0]

    candidates = []
    for n in fn.body:
        if isinstance(n, ast.Try):
            for handler in n.handlers:
                if (
                    handler.type
                    and isinstance(handler.type, ast.Name)
                    and handler.type.id == "Exception"
                ):
                    candidates.append((n, handler))

    if len(candidates) != 1:
        raise RuntimeError(
            f"{nome}: esperado 1 try/except Exception de nível principal; "
            f"encontrados {len(candidates)}."
        )

    return candidates[0]


def remove_try_wrapper(func_texto, nome):
    """
    Remove o wrapper try/except Exception principal via AST/linhas.
    Preserva o corpo do try e ignora linhas em branco do except.
    """
    try_node, handler = find_transaction_wrapper(func_texto, nome)

    # O except deve conter rollback + raise.
    calls_rollback = 0
    bare_raise = 0

    for n in ast.walk(handler):
        if (
            isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and isinstance(n.func.value, ast.Name)
            and n.func.value.id == "conn"
            and n.func.attr == "rollback"
        ):
            calls_rollback += 1

        if isinstance(n, ast.Raise) and n.exc is None:
            bare_raise += 1

    if calls_rollback != 1 or bare_raise != 1:
        raise RuntimeError(
            f"{nome}: except transacional inesperado "
            f"(rollback={calls_rollback}, bare_raise={bare_raise})."
        )

    linhas = func_texto.splitlines(True)

    try_start = try_node.lineno - 1
    try_end = try_node.end_lineno

    body_start = try_node.body[0].lineno - 1
    body_end = try_node.body[-1].end_lineno

    body_lines = linhas[body_start:body_end]

    # Corpo do try está 8 espaços; remove 4 para voltar ao nível da função.
    novo_body = []
    for linha in body_lines:
        if linha.strip():
            if not linha.startswith("        "):
                raise RuntimeError(
                    f"{nome}: indentação inesperada no corpo do try: {linha!r}"
                )
            novo_body.append(linha[4:])
        else:
            novo_body.append(linha)

    return (
        "".join(linhas[:try_start])
        + "".join(novo_body)
        + "".join(linhas[try_end:])
    )


def endpoint_calling(texto, chamada):
    tree = ast.parse(texto)
    matches = []

    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        for n in ast.walk(fn):
            if (
                isinstance(n, ast.Call)
                and isinstance(n.func, ast.Name)
                and n.func.id == chamada
            ):
                matches.append(fn)
                break

    if len(matches) != 1:
        raise RuntimeError(
            f"Router: esperado 1 endpoint chamando {chamada}; "
            f"encontrados {len(matches)}."
        )
    return matches[0]


def patch_endpoint(func_texto, chamada):
    """
    Remove conn=conn da chamada, garante resultado/uow.commit/return,
    troca ValueError por BRV e adiciona rollbacks.
    """
    linhas = func_texto.splitlines(True)

    call_idx = None
    for i, linha in enumerate(linhas):
        if f"{chamada}(" in linha:
            call_idx = i
            break

    if call_idx is None:
        raise RuntimeError(f"{chamada}: chamada não encontrada.")

    # Fecha chamada por balanço de parênteses.
    bal = 0
    close_idx = None
    for i in range(call_idx, len(linhas)):
        bal += linhas[i].count("(") - linhas[i].count(")")
        if i > call_idx and bal == 0:
            close_idx = i
            break

    if close_idx is None:
        raise RuntimeError(f"{chamada}: fechamento da chamada não encontrado.")

    bloco = linhas[call_idx:close_idx + 1]

    # Remove conn=conn.
    conn_positions = [
        i for i, linha in enumerate(bloco)
        if "conn=conn," in linha
    ]
    if len(conn_positions) != 1:
        raise RuntimeError(
            f"{chamada}: esperado 1 conn=conn; encontrados {len(conn_positions)}."
        )
    del bloco[conn_positions[0]]

    # return chamada -> resultado = chamada
    if f"return {chamada}(" in bloco[0]:
        bloco[0] = bloco[0].replace(
            f"return {chamada}(",
            f"resultado = {chamada}(",
            1,
        )
        precisa_return = True
    else:
        precisa_return = False

    linhas = linhas[:call_idx] + bloco + linhas[close_idx + 1:]

    if precisa_return:
        insert_at = call_idx + len(bloco)
        linhas[insert_at:insert_at] = [
            "\n",
            "        uow.commit()\n",
            "        return resultado\n",
        ]
    else:
        # Localiza return resultado já existente e insere commit.
        ret_idx = None
        for i in range(call_idx + len(bloco), len(linhas)):
            if linhas[i].strip() == "return resultado":
                ret_idx = i
                break

        if ret_idx is None:
            raise RuntimeError(
                f"{chamada}: não existe return resultado após a chamada."
            )

        if not any(
            "uow.commit()" in linha
            for linha in linhas[call_idx:ret_idx]
        ):
            linhas[ret_idx:ret_idx] = ["        uow.commit()\n\n"]

    texto = "".join(linhas)

    texto = texto.replace(
        "except ValueError as erro:",
        "except BusinessRuleViolation as erro:",
    )

    # Rollback nas exceções sem duplicar.
    texto = texto.replace(
        """    except BusinessRuleViolation as erro:
        raise HTTPException(
""",
        """    except BusinessRuleViolation as erro:
        if conn:
            uow.rollback()

        raise HTTPException(
""",
        1,
    )

    texto = texto.replace(
        """    except HTTPException:
        raise
""",
        """    except HTTPException:
        if conn:
            uow.rollback()

        raise
""",
        1,
    )

    texto = texto.replace(
        """    except Exception as erro:
        raise HTTPException(
""",
        """    except Exception as erro:
        if conn:
            uow.rollback()

        raise HTTPException(
""",
        1,
    )

    return texto


try:
    texto = service.read_text(encoding="utf-8")

    state = (
        texto.count("raise ValueError("),
        texto.count("def finalizar_ciclo_rotativo("),
        texto.count("conn.commit()"),
        texto.count("conn.rollback()"),
    )

    if state != (6, 1, 2, 3):
        raise RuntimeError(
            f"Estado atual {state}; esperado exatamente (6, 1, 2, 3)."
        )

    texto = ensure_brv_import(texto)
    texto = texto.replace(
        "raise ValueError(",
        "raise BusinessRuleViolation("
    )

    # ---------------- ABRIR ----------------
    node = top_def(texto, "abrir_ciclo_rotativo")
    trecho = extrair(texto, node)

    old_sig = """def abrir_ciclo_rotativo(
    conn,
    cursor,"""
    new_sig = """def abrir_ciclo_rotativo(
    cursor,"""

    if old_sig not in trecho:
        raise RuntimeError("Assinatura antiga de abrir não encontrada.")
    trecho = trecho.replace(old_sig, new_sig, 1)

    trecho = remove_try_wrapper(trecho, "abrir_ciclo_rotativo")

    if trecho.count("conn.commit()") != 1:
        raise RuntimeError("abrir: esperado 1 commit.")
    trecho = trecho.replace("    conn.commit()\n", "", 1)

    texto = substituir(texto, node, trecho)

    # ---------------- FINALIZAR ----------------
    node = top_def(texto, "finalizar_ciclo_rotativo")
    trecho = extrair(texto, node)

    old_sig = """def finalizar_ciclo_rotativo(
    conn,
    cursor,"""
    new_sig = """def finalizar_ciclo_rotativo(
    cursor,"""

    if old_sig not in trecho:
        raise RuntimeError("Assinatura antiga de finalizar não encontrada.")
    trecho = trecho.replace(old_sig, new_sig, 1)

    trecho = remove_try_wrapper(trecho, "finalizar_ciclo_rotativo")

    if trecho.count("conn.commit()") != 1:
        raise RuntimeError("finalizar: esperado 1 commit.")

    if trecho.count("conn.rollback()") != 1:
        raise RuntimeError(
            "finalizar: esperado 1 rollback concorrencial após remover wrapper."
        )

    # Remove rollback concorrencial e commit do service.
    trecho = trecho.replace("            conn.rollback()\n", "", 1)
    trecho = trecho.replace("        conn.commit()\n", "", 1)

    texto = substituir(texto, node, trecho)

    if "conn.commit()" in texto or "conn.rollback()" in texto:
        raise RuntimeError("Service ainda possui commit/rollback.")

    if texto.count("raise ValueError(") != 0:
        raise RuntimeError("Service ainda possui ValueError.")

    if texto.count("def finalizar_ciclo_rotativo(") != 1:
        raise RuntimeError("Service perdeu unicidade do finalizador.")

    service.write_text(texto, encoding="utf-8")

    # ---------------- ROUTER ----------------
    texto = router.read_text(encoding="utf-8")
    texto = ensure_brv_import(texto, router_mode=True)

    # Contrato 400 preservado para catches antigos.
    texto = texto.replace(
        "except ValueError as erro:",
        "except BusinessRuleViolation as erro:",
    )

    node = endpoint_calling(texto, "abrir_ciclo_rotativo")
    trecho = extrair(texto, node)
    trecho = patch_endpoint(trecho, "abrir_ciclo_rotativo")
    texto = substituir(texto, node, trecho)

    node = endpoint_calling(texto, "finalizar_ciclo_rotativo")
    trecho = extrair(texto, node)
    trecho = patch_endpoint(trecho, "finalizar_ciclo_rotativo")
    texto = substituir(texto, node, trecho)

    router.write_text(texto, encoding="utf-8")

    # ---------------- VALIDAÇÃO ----------------
    sf = service.read_text(encoding="utf-8")
    rf = router.read_text(encoding="utf-8")

    if sf.count("raise BusinessRuleViolation(") < 6:
        raise RuntimeError("BRVs incompletos.")
    if "conn.commit()" in sf or "conn.rollback()" in sf:
        raise RuntimeError("Transação ainda presente no service.")
    if sf.count("def finalizar_ciclo_rotativo(") != 1:
        raise RuntimeError("Finalizador duplicado/ausente.")
    if "except ValueError as erro:" in rf:
        raise RuntimeError("Router ainda possui catch ValueError.")

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
                f"{chamada}: esperado 1 call no router; encontrado {len(calls)}."
            )
        if any(kw.arg == "conn" for kw in calls[0].keywords):
            raise RuntimeError(f"{chamada}: conn ainda está sendo passado.")

    if rf.count("uow.commit()") < 2:
        raise RuntimeError(
            f"Router possui somente {rf.count('uow.commit()')} commits UoW."
        )

    py_compile.compile(str(service), doraise=True)
    py_compile.compile(str(router), doraise=True)

except BaseException:
    restaurar()
    print("REPROVADO: arquivos restaurados.")
    raise

print()
print("APROVADO")
print("- ciclos_rotativo corrigido a partir do estado parcial real")
print("- 6 ValueError -> BusinessRuleViolation")
print("- 1 finalizar_ciclo_rotativo preservado")
print("- commit/rollback removidos do service")
print("- UoW/router assume a transação de abrir/finalizar")
print("- proteção cursor.rowcount == 0 preservada")
print("- py_compile aprovado")
print()
print("Backups:")
for backup in backups.values():
    print(backup)
