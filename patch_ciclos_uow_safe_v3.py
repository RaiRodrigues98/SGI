from pathlib import Path
import ast
import shutil
import py_compile
from datetime import datetime

ROOT = Path.cwd()
SERVICE = ROOT / "services" / "ciclos_rotativo.py"
ROUTER = ROOT / "routers" / "rotativo_ciclos.py"

for p in (SERVICE, ROUTER):
    if not p.exists():
        raise FileNotFoundError(p)

stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backups = {}
for p in (SERVICE, ROUTER):
    b = p.with_name(f"{p.stem}_backup_ciclos_v3_{stamp}{p.suffix}")
    shutil.copy2(p, b)
    backups[p] = b


def restore():
    for p, b in backups.items():
        shutil.copy2(b, p)


def compile_file(p):
    py_compile.compile(str(p), doraise=True)


def get_top_func(text, name):
    tree = ast.parse(text)
    found = [
        n for n in tree.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        and n.name == name
    ]
    if len(found) != 1:
        raise RuntimeError(f"{name}: defs={len(found)}, esperado=1")
    return found[0]


def extract(text, node):
    lines = text.splitlines(True)
    return "".join(lines[node.lineno - 1:node.end_lineno])


def replace_node(text, node, replacement):
    lines = text.splitlines(True)
    return (
        "".join(lines[:node.lineno - 1])
        + replacement
        + "".join(lines[node.end_lineno:])
    )


def ensure_brv_import(text, router=False):
    marker = "from domain.exceptions import BusinessRuleViolation"
    if marker in text:
        return text

    if router:
        uow = "from infrastructure.database.unit_of_work import SqlServerUnitOfWork\n"
        if uow not in text:
            raise RuntimeError("Router: import SqlServerUnitOfWork não encontrado.")
        return text.replace(
            uow,
            uow + "\nfrom domain.exceptions import BusinessRuleViolation\n",
            1,
        )

    return "from domain.exceptions import BusinessRuleViolation\n" + text


def unwrap_single_transaction_try(func_text, func_name):
    """
    Remove somente o try/except Exception de nível principal cuja exceção
    contém conn.rollback() + raise. Usa AST para localizar o bloco e linhas
    para preservar o restante da formatação/comentários.
    """
    tree = ast.parse(func_text)
    fn = tree.body[0]

    matches = []
    for stmt in fn.body:
        if not isinstance(stmt, ast.Try):
            continue

        for handler in stmt.handlers:
            is_exception = (
                isinstance(handler.type, ast.Name)
                and handler.type.id == "Exception"
            )
            if not is_exception:
                continue

            has_rollback = False
            has_bare_raise = False

            for n in ast.walk(handler):
                if (
                    isinstance(n, ast.Call)
                    and isinstance(n.func, ast.Attribute)
                    and isinstance(n.func.value, ast.Name)
                    and n.func.value.id == "conn"
                    and n.func.attr == "rollback"
                ):
                    has_rollback = True

                if isinstance(n, ast.Raise) and n.exc is None:
                    has_bare_raise = True

            if has_rollback and has_bare_raise:
                matches.append(stmt)

    if len(matches) != 1:
        raise RuntimeError(
            f"{func_name}: wrappers transacionais encontrados={len(matches)}, esperado=1."
        )

    node = matches[0]
    lines = func_text.splitlines(True)

    # Keep only the body of try, dedented one level.
    body_start = node.body[0].lineno - 1
    body_end = node.body[-1].end_lineno

    body = []
    for line in lines[body_start:body_end]:
        if line.strip():
            if not line.startswith("        "):
                raise RuntimeError(
                    f"{func_name}: indentação inesperada no corpo do try: {line!r}"
                )
            body.append(line[4:])
        else:
            body.append(line)

    return (
        "".join(lines[:node.lineno - 1])
        + "".join(body)
        + "".join(lines[node.end_lineno:])
    )


def remove_conn_transaction_calls(func_text, func_name, expected):
    """
    Remove statements diretos conn.commit()/conn.rollback() usando AST.
    Não depende de indentação nem linhas em branco.
    """
    tree = ast.parse(func_text)
    fn = tree.body[0]
    nodes = []

    for n in ast.walk(fn):
        if not isinstance(n, ast.Expr):
            continue
        call = n.value
        if not isinstance(call, ast.Call):
            continue
        if not isinstance(call.func, ast.Attribute):
            continue
        if not isinstance(call.func.value, ast.Name):
            continue
        if call.func.value.id != "conn":
            continue
        if call.func.attr not in ("commit", "rollback"):
            continue
        nodes.append(n)

    if len(nodes) != expected:
        detalhes = []
        for n in nodes:
            detalhes.append(f"linha {n.lineno}: {ast.unparse(n)}")
        raise RuntimeError(
            f"{func_name}: chamadas transaction={len(nodes)}, esperado={expected}. "
            + "; ".join(detalhes)
        )

    lines = func_text.splitlines(True)

    # Delete bottom-up to keep line indexes stable.
    for n in sorted(nodes, key=lambda x: x.lineno, reverse=True):
        start = n.lineno - 1
        end = n.end_lineno
        del lines[start:end]

    return "".join(lines)


def find_endpoint(text, called_name):
    tree = ast.parse(text)
    found = []

    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        for n in ast.walk(fn):
            if (
                isinstance(n, ast.Call)
                and isinstance(n.func, ast.Name)
                and n.func.id == called_name
            ):
                found.append(fn)
                break

    if len(found) != 1:
        raise RuntimeError(
            f"Router: endpoint que chama {called_name}: {len(found)}, esperado=1."
        )

    return found[0]


def patch_router_endpoint(func_text, called_name):
    lines = func_text.splitlines(True)

    call_start = None
    for i, line in enumerate(lines):
        if f"{called_name}(" in line:
            call_start = i
            break

    if call_start is None:
        raise RuntimeError(f"{called_name}: chamada não encontrada no endpoint.")

    balance = 0
    call_end = None
    for i in range(call_start, len(lines)):
        balance += lines[i].count("(") - lines[i].count(")")
        if i > call_start and balance == 0:
            call_end = i
            break

    if call_end is None:
        raise RuntimeError(f"{called_name}: fechamento da chamada não encontrado.")

    block = lines[call_start:call_end + 1]

    conn_idx = [i for i, line in enumerate(block) if "conn=conn," in line]
    if len(conn_idx) != 1:
        raise RuntimeError(
            f"{called_name}: conn=conn encontrados={len(conn_idx)}, esperado=1."
        )
    del block[conn_idx[0]]

    direct_return = f"return {called_name}(" in block[0]
    if direct_return:
        block[0] = block[0].replace(
            f"return {called_name}(",
            f"resultado = {called_name}(",
            1,
        )

    lines = lines[:call_start] + block + lines[call_end + 1:]

    if direct_return:
        pos = call_start + len(block)
        lines[pos:pos] = [
            "\n",
            "        uow.commit()\n",
            "        return resultado\n",
        ]
    else:
        # Find existing return resultado.
        ret = None
        for i in range(call_start + len(block), len(lines)):
            if lines[i].strip() == "return resultado":
                ret = i
                break
        if ret is None:
            raise RuntimeError(f"{called_name}: return resultado não encontrado.")

        before = "".join(lines[call_start:ret])
        if "uow.commit()" not in before:
            lines[ret:ret] = ["        uow.commit()\n\n"]

    text = "".join(lines)

    text = text.replace(
        "except ValueError as erro:",
        "except BusinessRuleViolation as erro:",
    )

    # Add rollback only when missing.
    old = """    except BusinessRuleViolation as erro:
        raise HTTPException(
"""
    new = """    except BusinessRuleViolation as erro:
        if conn:
            uow.rollback()

        raise HTTPException(
"""
    if old in text:
        text = text.replace(old, new, 1)

    old = """    except HTTPException:
        raise
"""
    new = """    except HTTPException:
        if conn:
            uow.rollback()

        raise
"""
    if old in text:
        text = text.replace(old, new, 1)

    old = """    except Exception as erro:
        raise HTTPException(
"""
    new = """    except Exception as erro:
        if conn:
            uow.rollback()

        raise HTTPException(
"""
    if old in text:
        text = text.replace(old, new, 1)

    return text


try:
    # ============================================================
    # SERVICE - exact known partial state
    # ============================================================
    text = SERVICE.read_text(encoding="utf-8")

    state = (
        text.count("raise ValueError("),
        text.count("def finalizar_ciclo_rotativo("),
        text.count("conn.commit()"),
        text.count("conn.rollback()"),
    )

    if state != (6, 1, 2, 3):
        raise RuntimeError(
            f"Estado atual={state}; esperado=(6, 1, 2, 3). Nenhuma alteração aplicada."
        )

    text = ensure_brv_import(text)
    text = text.replace("raise ValueError(", "raise BusinessRuleViolation(")

    # ---------- abrir_ciclo_rotativo ----------
    node = get_top_func(text, "abrir_ciclo_rotativo")
    func = extract(text, node)

    old_sig = """def abrir_ciclo_rotativo(
    conn,
    cursor,"""
    new_sig = """def abrir_ciclo_rotativo(
    cursor,"""

    if old_sig not in func:
        raise RuntimeError("abrir_ciclo_rotativo: assinatura antiga não encontrada.")

    func = func.replace(old_sig, new_sig, 1)
    func = unwrap_single_transaction_try(func, "abrir_ciclo_rotativo")

    # After unwrapping, only the commit in the body remains.
    func = remove_conn_transaction_calls(
        func,
        "abrir_ciclo_rotativo",
        expected=1,
    )

    text = replace_node(text, node, func)

    # ---------- finalizar_ciclo_rotativo ----------
    node = get_top_func(text, "finalizar_ciclo_rotativo")
    func = extract(text, node)

    old_sig = """def finalizar_ciclo_rotativo(
    conn,
    cursor,"""
    new_sig = """def finalizar_ciclo_rotativo(
    cursor,"""

    if old_sig not in func:
        raise RuntimeError("finalizar_ciclo_rotativo: assinatura antiga não encontrada.")

    func = func.replace(old_sig, new_sig, 1)
    func = unwrap_single_transaction_try(func, "finalizar_ciclo_rotativo")

    # After unwrapping there are exactly:
    # - rollback on optimistic-concurrency failure
    # - commit on success
    func = remove_conn_transaction_calls(
        func,
        "finalizar_ciclo_rotativo",
        expected=2,
    )

    text = replace_node(text, node, func)

    SERVICE.write_text(text, encoding="utf-8")

    # ============================================================
    # ROUTER
    # ============================================================
    text = ROUTER.read_text(encoding="utf-8")
    text = ensure_brv_import(text, router=True)

    # All remaining ValueError catches in this router represent old HTTP 400 contract.
    text = text.replace(
        "except ValueError as erro:",
        "except BusinessRuleViolation as erro:",
    )

    node = find_endpoint(text, "abrir_ciclo_rotativo")
    func = extract(text, node)
    func = patch_router_endpoint(func, "abrir_ciclo_rotativo")
    text = replace_node(text, node, func)

    node = find_endpoint(text, "finalizar_ciclo_rotativo")
    func = extract(text, node)
    func = patch_router_endpoint(func, "finalizar_ciclo_rotativo")
    text = replace_node(text, node, func)

    ROUTER.write_text(text, encoding="utf-8")

    # ============================================================
    # FINAL VALIDATION
    # ============================================================
    s = SERVICE.read_text(encoding="utf-8")
    r = ROUTER.read_text(encoding="utf-8")

    if s.count("raise ValueError(") != 0:
        raise RuntimeError("Service: ValueError remanescente.")
    if s.count("raise BusinessRuleViolation(") < 6:
        raise RuntimeError("Service: BRV incompleto.")
    if s.count("def finalizar_ciclo_rotativo(") != 1:
        raise RuntimeError("Service: finalizar_ciclo_rotativo != 1.")
    if "conn.commit()" in s or "conn.rollback()" in s:
        raise RuntimeError("Service: commit/rollback remanescente.")
    if "def abrir_ciclo_rotativo(\n    conn," in s:
        raise RuntimeError("Service: conn ainda na assinatura abrir.")
    if "def finalizar_ciclo_rotativo(\n    conn," in s:
        raise RuntimeError("Service: conn ainda na assinatura finalizar.")

    rt = ast.parse(r)
    for called in ("abrir_ciclo_rotativo", "finalizar_ciclo_rotativo"):
        calls = [
            n for n in ast.walk(rt)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id == called
        ]
        if len(calls) != 1:
            raise RuntimeError(f"Router: {called} calls={len(calls)}, esperado=1.")
        if any(kw.arg == "conn" for kw in calls[0].keywords):
            raise RuntimeError(f"Router: {called} ainda recebe conn.")

    if "except ValueError as erro:" in r:
        raise RuntimeError("Router: catch ValueError remanescente.")

    # Ensure both endpoints have commit.
    if r.count("uow.commit()") < 2:
        raise RuntimeError(
            f"Router: uow.commit={r.count('uow.commit()')}, esperado pelo menos 2."
        )

    compile_file(SERVICE)
    compile_file(ROUTER)

except BaseException:
    restore()
    print("REPROVADO: arquivos restaurados.")
    raise

print()
print("APROVADO")
print("- ciclos_rotativo migrado do estado parcial (6,1,2,3)")
print("- transações removidas via AST, sem depender de indentação")
print("- abrir/finalizar agora usam UoW/router")
print("- 6 ValueError -> BusinessRuleViolation")
print("- proteção rowcount preservada como regra de conflito")
print("- exatamente 1 finalizar_ciclo_rotativo")
print("- py_compile aprovado")
print()
print("Backups:")
for b in backups.values():
    print(b)
