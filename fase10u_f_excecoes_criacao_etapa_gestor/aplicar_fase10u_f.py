
"""
FASE 10U-F - CRIAÇÃO DE RODADAS | ETAPA GESTOR

Alvo parcial:
- services/rodadas/criacao.py
- somente o raise do ramo:
    elif tipo_proxima == "GESTOR"
  dentro de _selecionar_candidatos()

Pré-requisito:
- Fase 10U-E aplicada.

Baseline esperado após 10U-E:
- _carregar_configuracao_criacao:
    3 BusinessRuleViolation
- _validar_sem_sessoes_abertas:
    1 BusinessRuleViolation
- _serializar_criacao_r2_rotativo:
    1 ConflictError
- _validar_candidatos_divergencia:
    1 BusinessRuleViolation
- _gerar_localizacoes_nova_rodada:
    1 BusinessRuleViolation
- _selecionar_candidatos:
    exatamente 7 HTTPException

Erro alvo:
HTTP 400
"A próxima etapa configurada é GESTOR. "
"Não deve ser criada como rodada operacional. "
"Utilize a análise gerencial."

Mapeamento:
HTTP 400 -> BusinessRuleViolation

Ao final:
- o raise GESTOR vira BusinessRuleViolation
- _selecionar_candidatos:
    exatamente 6 HTTPException remanescentes
- criacao.py:
    exatamente 6 HTTPException no total
- FastAPI permanece temporariamente

Os 6 raises restantes ficam intocados:
- 5 validações internas do fluxo gerencial de NOVA_RECONTAGEM
- 1 tipo de próxima rodada não suportado

Não altera:
- análise gerencial;
- decisões NOVA_RECONTAGEM;
- candidatos OFICIAL;
- candidatos ROTATIVO;
- tipo COMPLETA;
- SQL;
- UoW;
- commit/rollback;
- sp_getapplock.

Execute:
python .\fase10u_f_excecoes_criacao_etapa_gestor\aplicar_fase10u_f.py
"""

from pathlib import Path
from datetime import datetime
import ast
import py_compile
import shutil

ROOT = Path.cwd()

SERVICE = ROOT / "services" / "rodadas" / "criacao.py"
DOMAIN = ROOT / "domain" / "exceptions.py"

TARGET_MODULE = "services.rodadas.criacao"
TARGET_FUNCTION = "_selecionar_candidatos"
TARGET_NODE = (TARGET_MODULE, TARGET_FUNCTION)

PREREQ_CONFIG = "_carregar_configuracao_criacao"
PREREQ_SESSIONS = "_validar_sem_sessoes_abertas"
PREREQ_LOCK = "_serializar_criacao_r2_rotativo"
PREREQ_DIVERGENCIA = "_validar_candidatos_divergencia"
PREREQ_LOCALIZACOES = "_gerar_localizacoes_nova_rodada"

EXPECTED_STATUS = 400
EXPECTED_DETAIL = (
    "A próxima etapa configurada é GESTOR. "
    "Não deve ser criada como rodada "
    "operacional. Utilize a análise gerencial."
)

EXPECTED_HTTP_BEFORE = 7
EXPECTED_HTTP_AFTER = 6

# Os outros seis erros são protegidos por marcadores sem alterar seus details.
REMAINING_DETAIL_MARKERS = (
    "divergente(s) sem decisão do gestor",
    "O inventário está apto",
    "Nenhum item foi marcado como",
    "registro NOVA_RECONTAGEM foi",
    "Inconsistência entre a análise",
    "Tipo de próxima rodada não suportado",
)

CRITICAL_LOCK_TOKENS = [
    "sys.sp_getapplock",
    "SGI:ROTATIVO:PROXIMA_RODADA:",
    "@LockMode = 'Exclusive'",
    "@LockOwner = 'Transaction'",
    "@LockTimeout = 10000",
]

PROTECTED_EXACT_TOKENS = [
    "get_connection()",
    "SqlServerUnitOfWork()",
    "uow.open()",
    "conn.cursor()",
    "uow.cursor",
    "cursor.close()",
    "conn.close()",
    "uow.close()",
    "conn.commit()",
    "uow.commit()",
    "sys.sp_getapplock",
    "SGI:ROTATIVO:PROXIMA_RODADA:",
    "@LockMode = 'Exclusive'",
    "@LockOwner = 'Transaction'",
    "@LockTimeout = 10000",
]

EXCLUDED_DIRS = {
    ".git", ".venv", "venv", "__pycache__", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", "node_modules",
}
EXCLUDED_PREFIXES = tuple(f"fase{i}" for i in range(1, 11))


def read_text(path):
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1")


def parse(text, name):
    try:
        return ast.parse(text)
    except SyntaxError as exc:
        raise RuntimeError(f"{name}: sintaxe inválida: {exc}")


def raised_name(expr):
    if isinstance(expr, ast.Name):
        return expr.id
    if isinstance(expr, ast.Call):
        return raised_name(expr.func)
    if isinstance(expr, ast.Attribute):
        return expr.attr
    return None


def handler_name(node):
    if node.type is None:
        return None
    if isinstance(node.type, ast.Name):
        return node.type.id
    if isinstance(node.type, ast.Attribute):
        return node.type.attr
    return None


def top_functions(tree):
    return {
        n.name: n for n in tree.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def get_function(text, name):
    fn = top_functions(parse(text, "services/rodadas/criacao.py")).get(name)
    if fn is None:
        raise RuntimeError(f"Função ausente: {name}")
    return fn


def http_raises_in_function(text, name):
    fn = get_function(text, name)
    result = []

    for node in ast.walk(fn):
        if not isinstance(node, ast.Raise) or node.exc is None:
            continue
        if not (
            isinstance(node.exc, ast.Call)
            and raised_name(node.exc) == "HTTPException"
        ):
            continue

        status_node = None
        detail_node = None
        for kw in node.exc.keywords:
            if kw.arg == "status_code":
                status_node = kw.value
            elif kw.arg == "detail":
                detail_node = kw.value

        if status_node is None or detail_node is None:
            raise RuntimeError(f"{name}: HTTPException sem status/detail.")

        if not (
            isinstance(status_node, ast.Constant)
            and isinstance(status_node.value, int)
        ):
            raise RuntimeError(f"{name}: status dinâmico não suportado.")

        detail_source = ast.get_source_segment(text, detail_node)
        if not detail_source:
            raise RuntimeError(f"{name}: detail não recuperado.")

        try:
            detail_value = ast.literal_eval(detail_node)
        except Exception:
            detail_value = None

        result.append({
            "node": node,
            "status": status_node.value,
            "detail_source": detail_source,
            "detail_value": detail_value,
        })

    return sorted(result, key=lambda item: item["node"].lineno)


def semantic_count(text, function_name, exception_name):
    fn = get_function(text, function_name)
    count = 0

    for node in ast.walk(fn):
        if (
            isinstance(node, ast.Raise)
            and node.exc is not None
            and raised_name(node.exc) == exception_name
        ):
            count += 1

    return count


def all_http_locations(text):
    tree = parse(text, "services/rodadas/criacao.py")
    result = {}

    for fn_name, fn in top_functions(tree).items():
        count = sum(
            1
            for node in ast.walk(fn)
            if (
                isinstance(node, ast.Raise)
                and node.exc is not None
                and raised_name(node.exc) == "HTTPException"
            )
        )
        if count:
            result[fn_name] = count

    return result


def total_http_usage(text):
    tree = parse(text, "services/rodadas/criacao.py")
    raises = 0
    handlers = 0

    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Raise)
            and node.exc is not None
            and raised_name(node.exc) == "HTTPException"
        ):
            raises += 1
        if (
            isinstance(node, ast.ExceptHandler)
            and handler_name(node) == "HTTPException"
        ):
            handlers += 1

    return {"raises": raises, "handlers": handlers}


def import_present(text, module, symbol):
    tree = parse(text, "services/rodadas/criacao.py")
    return any(
        isinstance(node, ast.ImportFrom)
        and (node.module or "") == module
        and symbol in [a.name for a in node.names]
        for node in tree.body
    )


def validate_lock_contract(text):
    counts = {token: text.count(token) for token in CRITICAL_LOCK_TOKENS}
    invalid = {token: count for token, count in counts.items() if count != 1}

    if invalid:
        raise RuntimeError(
            f"Contrato de concorrência R2 inesperado: {invalid}"
        )

    fn_text = ast.get_source_segment(
        text,
        get_function(text, PREREQ_LOCK),
    ) or ""

    for token in CRITICAL_LOCK_TOKENS:
        if token not in fn_text:
            raise RuntimeError(
                f"Token crítico fora de {PREREQ_LOCK}: {token}"
            )

    return counts


def protected_counts(text):
    return {token: text.count(token) for token in PROTECTED_EXACT_TOKENS}


def validate_prerequisites(text):
    values = {
        "config_brv": semantic_count(text, PREREQ_CONFIG, "BusinessRuleViolation"),
        "config_http": len(http_raises_in_function(text, PREREQ_CONFIG)),
        "sessions_brv": semantic_count(text, PREREQ_SESSIONS, "BusinessRuleViolation"),
        "sessions_http": len(http_raises_in_function(text, PREREQ_SESSIONS)),
        "lock_conflict": semantic_count(text, PREREQ_LOCK, "ConflictError"),
        "lock_http": len(http_raises_in_function(text, PREREQ_LOCK)),
        "div_brv": semantic_count(text, PREREQ_DIVERGENCIA, "BusinessRuleViolation"),
        "div_http": len(http_raises_in_function(text, PREREQ_DIVERGENCIA)),
        "loc_brv": semantic_count(text, PREREQ_LOCALIZACOES, "BusinessRuleViolation"),
        "loc_http": len(http_raises_in_function(text, PREREQ_LOCALIZACOES)),
    }

    ok = (
        values["config_brv"] == 3 and values["config_http"] == 0
        and values["sessions_brv"] == 1 and values["sessions_http"] == 0
        and values["lock_conflict"] == 1 and values["lock_http"] == 0
        and values["div_brv"] == 1 and values["div_http"] == 0
        and values["loc_brv"] == 1 and values["loc_http"] == 0
    )
    return ok, values


def target_raise(items):
    matches = [
        item for item in items
        if (
            item["status"] == EXPECTED_STATUS
            and item["detail_value"] == EXPECTED_DETAIL
        )
    ]

    if len(matches) != 1:
        raise RuntimeError(
            f"Esperado 1 raise GESTOR exato, encontrado {len(matches)}."
        )

    return matches[0]


def validate_remaining_markers(items):
    non_target = [
        item for item in items
        if item["detail_value"] != EXPECTED_DETAIL
    ]

    source = "\n".join(item["detail_source"] for item in non_target)

    missing = [
        marker for marker in REMAINING_DETAIL_MARKERS
        if marker not in source
    ]

    if missing:
        raise RuntimeError(
            f"Perfil dos raises restantes mudou. Marcadores ausentes: {missing}"
        )

    return non_target


def service_state(text):
    prereq_ok, prereq = validate_prerequisites(text)
    validate_lock_contract(text)

    items = http_raises_in_function(text, TARGET_FUNCTION)
    usage = total_http_usage(text)
    locations = all_http_locations(text)

    target_brv = semantic_count(
        text,
        TARGET_FUNCTION,
        "BusinessRuleViolation",
    )

    imports_ok = (
        import_present(text, "fastapi", "HTTPException")
        and import_present(text, "domain.exceptions", "BusinessRuleViolation")
        and import_present(text, "domain.exceptions", "ConflictError")
    )

    # Estado legado 10U-F: 7 HTTP, incluindo exatamente o alvo GESTOR.
    if prereq_ok and len(items) == EXPECTED_HTTP_BEFORE:
        try:
            target_raise(items)
            remaining = validate_remaining_markers(items)
        except Exception:
            remaining = None

        if (
            remaining is not None
            and len(remaining) == 6
            and target_brv == 0
            and locations == {TARGET_FUNCTION: EXPECTED_HTTP_BEFORE}
            and usage["raises"] == EXPECTED_HTTP_BEFORE
            and usage["handlers"] == 0
            and imports_ok
        ):
            return "LEGADO_10U_F", {
                "prereq": prereq,
                "target_http": 1,
                "remaining_http": 6,
                "total_http": usage["raises"],
            }

    # Estado migrado 10U-F: 6 HTTP restantes + 1 BRV dentro da função.
    if prereq_ok and len(items) == EXPECTED_HTTP_AFTER:
        remaining_source = "\n".join(item["detail_source"] for item in items)
        markers_ok = all(
            marker in remaining_source
            for marker in REMAINING_DETAIL_MARKERS
        )

        if (
            markers_ok
            and target_brv == 1
            and locations == {TARGET_FUNCTION: EXPECTED_HTTP_AFTER}
            and usage["raises"] == EXPECTED_HTTP_AFTER
            and usage["handlers"] == 0
            and imports_ok
        ):
            return "MIGRADO_10U_F", {
                "prereq": prereq,
                "target_brv": 1,
                "remaining_http": 6,
                "total_http": usage["raises"],
            }

    return "DESCONHECIDO", {
        "prereq_ok": prereq_ok,
        "prereq": prereq,
        "selection_http": len(items),
        "target_brv": target_brv,
        "locations": locations,
        "usage": usage,
        "details": [item["detail_value"] for item in items],
        "fastapi": import_present(text, "fastapi", "HTTPException"),
        "business_import": import_present(
            text, "domain.exceptions", "BusinessRuleViolation"
        ),
        "conflict_import": import_present(
            text, "domain.exceptions", "ConflictError"
        ),
    }


# ============================================================
# GRAFO CROSS-MODULE / FACADES
# ============================================================

def is_excluded(path):
    rel = path.relative_to(ROOT)

    for part in rel.parts:
        low = part.lower()
        if low in EXCLUDED_DIRS:
            return True
        if "_backup_" in low or low.startswith("backup"):
            return True
        if low.startswith(EXCLUDED_PREFIXES):
            return True

    if rel.parts and rel.parts[0].lower() in {"tests", "tests_e2e", "test"}:
        return True

    return False


def production_files():
    return sorted(
        p for p in ROOT.rglob("*.py")
        if not is_excluded(p)
    )


def module_name_from_path(path):
    return ".".join(path.relative_to(ROOT).with_suffix("").parts)


def package_of_module(module_name):
    return module_name.split(".")[:-1]


def resolve_import_module(current_module, node):
    module = node.module or ""

    if node.level == 0:
        return module

    package = package_of_module(current_module)
    ascend = node.level - 1

    if ascend > len(package):
        return None

    base = package[:len(package) - ascend]
    if module:
        base += module.split(".")

    return ".".join(base)


def top_import_map(tree, module_name):
    result = {}

    for node in tree.body:
        if not isinstance(node, ast.ImportFrom):
            continue

        resolved = resolve_import_module(module_name, node)
        if not resolved:
            continue

        for alias in node.names:
            if alias.name == "*":
                continue
            result[alias.asname or alias.name] = (resolved, alias.name)

    return result


def top_alias_assignments(tree):
    result = {}

    for node in tree.body:
        if isinstance(node, ast.Assign):
            if (
                len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and isinstance(node.value, ast.Name)
            ):
                result[node.targets[0].id] = node.value.id

        elif isinstance(node, ast.AnnAssign):
            if (
                isinstance(node.target, ast.Name)
                and isinstance(node.value, ast.Name)
            ):
                result[node.target.id] = node.value.id

    return result


def unsupported_target_module_imports(tree):
    result = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Import):
            continue
        for alias in node.names:
            if (
                alias.name == TARGET_MODULE
                or alias.name.startswith(TARGET_MODULE + ".")
            ):
                result.append((alias.name, node.lineno))

    return result


def call_names(fn):
    return {
        node.func.id
        for node in ast.walk(fn)
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
        )
    }


def build_project_index():
    modules = {}
    syntax_errors = []

    for path in production_files():
        text = read_text(path)
        try:
            tree = ast.parse(text)
        except SyntaxError as exc:
            syntax_errors.append((path, exc))
            continue

        module_name = module_name_from_path(path)

        modules[module_name] = {
            "path": path,
            "text": text,
            "tree": tree,
            "functions": top_functions(tree),
            "imports": top_import_map(tree, module_name),
            "aliases": top_alias_assignments(tree),
            "unsupported_target_imports":
                unsupported_target_module_imports(tree),
        }

    if syntax_errors:
        details = "; ".join(
            f"{path.relative_to(ROOT)}: {exc}"
            for path, exc in syntax_errors
        )
        raise RuntimeError(
            "Arquivos de produção com sintaxe inválida: " + details
        )

    return modules


def resolve_symbol(modules, module_name, symbol_name, visited=None):
    if visited is None:
        visited = set()

    key = (module_name, symbol_name)
    if key in visited:
        return None

    visited = set(visited)
    visited.add(key)

    info = modules.get(module_name)
    if info is None:
        return None

    if symbol_name in info["functions"]:
        return (module_name, symbol_name)

    aliases = info.get("aliases", {})
    if symbol_name in aliases:
        return resolve_symbol(
            modules, module_name, aliases[symbol_name], visited
        )

    imports = info["imports"]
    if symbol_name in imports:
        imported_module, imported_name = imports[symbol_name]
        return resolve_symbol(
            modules, imported_module, imported_name, visited
        )

    return None


def build_call_graph(modules):
    reverse = {}

    for module_name, info in modules.items():
        for fn_name, fn in info["functions"].items():
            caller = (module_name, fn_name)

            for called_name in call_names(fn):
                callee = resolve_symbol(
                    modules, module_name, called_name
                )

                if callee is None or callee == caller:
                    continue

                reverse.setdefault(callee, set()).add(caller)

    return reverse


def transitive_callers(reverse):
    affected = {TARGET_NODE}
    frontier = [TARGET_NODE]

    while frontier:
        current = frontier.pop()
        for caller in reverse.get(current, set()):
            if caller in affected:
                continue
            affected.add(caller)
            frontier.append(caller)

    return affected


# ============================================================
# ROUTERS
# ============================================================

def has_generic_http_wrapper(fn):
    for handler in [
        n for n in ast.walk(fn)
        if isinstance(n, ast.ExceptHandler)
    ]:
        if handler_name(handler) != "Exception":
            continue

        for inner in ast.walk(handler):
            if (
                isinstance(inner, ast.Raise)
                and isinstance(inner.exc, ast.Call)
                and raised_name(inner.exc) == "HTTPException"
            ):
                return True

    return False


def router_http_handler(fn):
    handlers = [
        n for n in ast.walk(fn)
        if (
            isinstance(n, ast.ExceptHandler)
            and handler_name(n) == "HTTPException"
        )
    ]

    if len(handlers) != 1:
        raise RuntimeError(
            f"{fn.name}: esperado exatamente 1 except HTTPException, "
            f"encontrado {len(handlers)}."
        )

    return handlers[0]


def handler_prefix_lines(text, handler):
    if not handler.body:
        raise RuntimeError("except HTTPException vazio.")

    last = handler.body[-1]
    if not (isinstance(last, ast.Raise) and last.exc is None):
        raise RuntimeError(
            "except HTTPException não termina com `raise` nu."
        )

    prefix_nodes = handler.body[:-1]
    if not prefix_nodes:
        return []

    lines = text.splitlines()
    return lines[
        prefix_nodes[0].lineno - 1:
        prefix_nodes[-1].end_lineno
    ]


def existing_business_handler(fn):
    handlers = [
        n for n in ast.walk(fn)
        if (
            isinstance(n, ast.ExceptHandler)
            and handler_name(n) == "BusinessRuleViolation"
        )
    ]

    if len(handlers) > 1:
        raise RuntimeError(
            f"{fn.name}: BusinessRuleViolation duplicado."
        )

    return handlers[0] if handlers else None


def handler_http_status(handler):
    for node in ast.walk(handler):
        if not (
            isinstance(node, ast.Raise)
            and isinstance(node.exc, ast.Call)
            and raised_name(node.exc) == "HTTPException"
        ):
            continue

        for kw in node.exc.keywords:
            if (
                kw.arg == "status_code"
                and isinstance(kw.value, ast.Constant)
                and isinstance(kw.value.value, int)
            ):
                return kw.value.value

    return None


def validate_router_function(text, fn, require_business):
    http_handler = router_http_handler(fn)
    prefix = handler_prefix_lines(text, http_handler)
    existing = existing_business_handler(fn)

    if existing is None:
        if require_business:
            raise RuntimeError(
                f"{fn.name}: BusinessRuleViolation não tratado."
            )
    else:
        status = handler_http_status(existing)
        if status != 400:
            raise RuntimeError(
                f"{fn.name}: BusinessRuleViolation traduz "
                f"HTTP {status}, esperado 400."
            )

    return http_handler, prefix


def add_business_import(text):
    tree = parse(text, "router")

    if any(
        isinstance(node, ast.ImportFrom)
        and (node.module or "") == "domain.exceptions"
        and "BusinessRuleViolation" in [a.name for a in node.names]
        for node in tree.body
    ):
        return text

    fastapi_import = next(
        (
            node for node in tree.body
            if (
                isinstance(node, ast.ImportFrom)
                and (node.module or "") == "fastapi"
            )
        ),
        None,
    )

    if fastapi_import is None:
        raise RuntimeError(
            "Router afetado sem import FastAPI reconhecido."
        )

    lines = text.splitlines()
    lines.insert(
        fastapi_import.end_lineno,
        "from domain.exceptions import BusinessRuleViolation",
    )

    result = "\n".join(lines)
    if text.endswith("\n"):
        result += "\n"

    return result


def build_business_handler(http_handler, prefix_lines):
    handler_indent = " " * http_handler.col_offset
    body_indent = " " * (http_handler.col_offset + 4)

    block = [
        f"{handler_indent}except BusinessRuleViolation as erro:"
    ]

    if prefix_lines:
        block.extend(prefix_lines)
        block.append("")

    block.extend([
        f"{body_indent}raise HTTPException(",
        f"{body_indent}    status_code=400,",
        f"{body_indent}    detail=str(erro)",
        f"{body_indent})",
        "",
    ])
    return block


def patch_router_file(text, affected_function_names):
    before = {t: text.count(t) for t in PROTECTED_EXACT_TOKENS}
    patched = add_business_import(text)

    tree = parse(patched, "router após import")
    functions = top_functions(tree)
    insertions = []

    for fn_name in sorted(affected_function_names):
        fn = functions.get(fn_name)
        if fn is None:
            raise RuntimeError(f"Função de router ausente: {fn_name}")

        http_handler, prefix = validate_router_function(
            patched, fn, require_business=False
        )

        if existing_business_handler(fn) is not None:
            continue

        insertions.append(
            (
                http_handler.lineno,
                build_business_handler(http_handler, prefix),
            )
        )

    lines = patched.splitlines()

    for line_no, block in sorted(
        insertions, key=lambda item: item[0], reverse=True
    ):
        lines[line_no - 1:line_no - 1] = block

    result = "\n".join(lines)
    if patched.endswith("\n"):
        result += "\n"

    final_tree = parse(result, "router final")
    final_functions = top_functions(final_tree)

    for fn_name in affected_function_names:
        validate_router_function(
            result, final_functions[fn_name], require_business=True
        )

    after = {t: result.count(t) for t in PROTECTED_EXACT_TOKENS}

    if before != after:
        diffs = {
            t: (before[t], after[t])
            for t in PROTECTED_EXACT_TOKENS
            if before[t] != after[t]
        }
        raise RuntimeError(
            f"UoW/commit/applock alterado no router: {diffs}"
        )

    return result


# ============================================================
# PATCH PARCIAL DO SERVICE
# ============================================================

def patch_service(text):
    state, diag = service_state(text)

    if state != "LEGADO_10U_F":
        raise RuntimeError(
            f"Service não está no baseline 10U-F: {state} / {diag}"
        )

    before_protected = protected_counts(text)
    before_lock = validate_lock_contract(text)

    items = http_raises_in_function(text, TARGET_FUNCTION)
    item = target_raise(items)
    validate_remaining_markers(items)

    node = item["node"]
    indent = " " * node.col_offset

    replacement = (
        f"{indent}raise BusinessRuleViolation(\n"
        f"{indent}    {item['detail_source']}\n"
        f"{indent})"
    )

    lines = text.splitlines()
    lines[node.lineno - 1:node.end_lineno] = replacement.splitlines()

    result = "\n".join(lines)
    if text.endswith("\n"):
        result += "\n"

    after_protected = protected_counts(result)
    if before_protected != after_protected:
        diffs = {
            t: (before_protected[t], after_protected[t])
            for t in PROTECTED_EXACT_TOKENS
            if before_protected[t] != after_protected[t]
        }
        raise RuntimeError(
            f"UoW/commit/applock alterado: {diffs}"
        )

    if validate_lock_contract(result) != before_lock:
        raise RuntimeError(
            "Contrato sp_getapplock mudou durante 10U-F."
        )

    final_state, final_diag = service_state(result)
    if final_state != "MIGRADO_10U_F":
        raise RuntimeError(
            f"Service pós-patch inválido: {final_diag}"
        )

    return result


# ============================================================
# EXECUÇÃO
# ============================================================

print("[0/16] Validando arquivos e hierarquia...")

for path in [SERVICE, DOMAIN]:
    if not path.exists():
        raise SystemExit(f"[ERRO] Arquivo ausente: {path}")

domain_text = read_text(DOMAIN)

for token in [
    "class BusinessRuleViolation(DomainError)",
    "class ConflictError(DomainError)",
]:
    if token not in domain_text:
        raise SystemExit(
            f"[ERRO] Hierarquia incompleta: {token}"
        )

print("      [OK] exceções de domínio disponíveis.")


print("[1/16] Validando pré-requisito 10U-E...")

service_text = read_text(SERVICE)
s_state, s_diag = service_state(service_text)

print(f"      Estado: {s_state}")
print(f"      pré-requisitos: {s_diag.get('prereq', {})}")
print(f"      HTTP em _selecionar_candidatos: "
      f"{s_diag.get('remaining_http', s_diag.get('selection_http', 0))}")
print(f"      total HTTP: {s_diag.get('total_http', s_diag.get('usage', {}))}")

if s_state == "DESCONHECIDO":
    raise SystemExit(
        "[ERRO] Fase 10U-E não reconhecida ou "
        f"baseline 10U-F inesperado: {s_diag}"
    )

if s_state == "MIGRADO_10U_F":
    print("[2/16] Fase 10U-F já aplicada.")
    print("      [OK] ramo GESTOR já está semântico.")
    raise SystemExit(0)

print("      [OK] Fase 10U-E reconhecida.")


print("[2/16] Revalidando sp_getapplock...")
lock_before = validate_lock_contract(service_text)

for token, count in lock_before.items():
    print(f"      [OK] {token}: {count}")


print("[3/16] Confirmando raise GESTOR HTTP 400...")
items = http_raises_in_function(service_text, TARGET_FUNCTION)
item = target_raise(items)
remaining = validate_remaining_markers(items)

print(f"      HTTP {item['status']} -> BusinessRuleViolation")
print(f"      detail: {item['detail_value']}")
print(f"      raises preservados: {len(remaining)}")

if len(items) != 7 or len(remaining) != 6:
    raise SystemExit(
        "[ERRO] Distribuição 7 = 1 alvo + 6 restantes não confirmada."
    )

print("      [OK] perfil exato confirmado.")


print("[4/16] Indexando módulos de produção...")
modules = build_project_index()

print(f"      módulos analisados: {len(modules)}")

if TARGET_MODULE not in modules:
    raise SystemExit("[ERRO] Módulo alvo não indexado.")

for module_name, info in modules.items():
    if info["unsupported_target_imports"]:
        raise SystemExit(
            "[ERRO] Import de módulo não suportado em "
            f"{info['path'].relative_to(ROOT)}: "
            f"{info['unsupported_target_imports']}."
        )

print("      [OK] imports/reexports compatíveis.")


print("[5/16] Construindo grafo de consumidores...")
reverse = build_call_graph(modules)
affected = transitive_callers(reverse)

print(f"      funções afetadas: {len(affected)}")

for module_name, fn_name in sorted(affected):
    print(f"      - {module_name}.{fn_name}")


print("[6/16] Classificando caminhos...")
affected_services = sorted(
    node for node in affected
    if (
        node != TARGET_NODE
        and node[0].startswith("services.")
    )
)

affected_routers = sorted(
    node for node in affected
    if node[0].startswith("routers.")
)

unexpected = sorted(
    node for node in affected
    if (
        node != TARGET_NODE
        and not node[0].startswith("services.")
        and not node[0].startswith("routers.")
    )
)

print(f"      services intermediários: {len(affected_services)}")
print(f"      funções de router: {len(affected_routers)}")

if unexpected:
    for node in unexpected:
        print(f"      [BLOQUEIO] {node[0]}.{node[1]}")
    raise SystemExit(
        "[ERRO] Caller fora de services/routers."
    )


print("[7/16] Verificando services intermediários...")
for module_name, fn_name in affected_services:
    fn = modules[module_name]["functions"][fn_name]

    if has_generic_http_wrapper(fn):
        print(
            f"      [BLOQUEIO] {module_name}.{fn_name} "
            "captura Exception e gera HTTPException."
        )
        raise SystemExit(
            "[ERRO] BusinessRuleViolation seria embrulhada "
            "por service intermediário."
        )

    print(f"      [OK] {module_name}.{fn_name}")

if not affected_routers:
    raise SystemExit(
        "[ERRO] Nenhuma fronteira HTTP alcançada."
    )


print("[8/16] Agrupando fronteiras HTTP...")
router_groups = {}

for module_name, fn_name in affected_routers:
    router_groups.setdefault(module_name, set()).add(fn_name)

for module_name, functions in sorted(router_groups.items()):
    print(f"      {module_name}: {sorted(functions)}")


print("[9/16] Validando handlers atuais...")
for module_name, function_names in router_groups.items():
    info = modules[module_name]

    for fn_name in function_names:
        validate_router_function(
            info["text"],
            info["functions"][fn_name],
            require_business=False,
        )
        print(f"      [OK] {module_name}.{fn_name}")


print("[10/16] Confirmando proteção dos 6 raises restantes...")
locations = all_http_locations(service_text)

if locations != {TARGET_FUNCTION: 7}:
    raise SystemExit(
        f"[ERRO] HTTPException fora do perfil esperado: {locations}"
    )

print("      [OK] todos os 7 HTTPException atuais estão em _selecionar_candidatos.")
print("      [OK] somente 1 será convertido nesta fase.")


print("[11/16] Preparando backups...")
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

paths_to_edit = {TARGET_MODULE: SERVICE}

for module_name in router_groups:
    paths_to_edit[module_name] = modules[module_name]["path"]

backups = {}

for module_name, path in paths_to_edit.items():
    backup = (
        path.parent
        / (path.stem + "_backup_fase10u_f_" + timestamp + ".py")
    )
    shutil.copy2(path, backup)
    backups[module_name] = backup

    print(
        f"      {path.relative_to(ROOT)} -> {backup.name}"
    )


try:
    print("[12/16] Migrando somente o ramo GESTOR...")
    patched_service = patch_service(service_text)

    SERVICE.write_text(
        patched_service,
        encoding="utf-8",
    )
    py_compile.compile(
        str(SERVICE),
        doraise=True,
    )

    print("      [OK] HTTP 400 -> BusinessRuleViolation.")
    print("      [OK] 6 HTTPException restantes intocados.")
    print("      [OK] FastAPI permanece temporariamente.")


    print("[13/16] Adaptando fronteiras HTTP...")
    for module_name, function_names in router_groups.items():
        path = modules[module_name]["path"]
        original_text = read_text(path)

        patched_router = patch_router_file(
            original_text,
            function_names,
        )

        path.write_text(
            patched_router,
            encoding="utf-8",
        )
        py_compile.compile(
            str(path),
            doraise=True,
        )

        print(
            f"      [OK] {module_name}: {sorted(function_names)}"
        )


    print("[14/16] Revalidando recorte parcial...")
    final_service = read_text(SERVICE)
    final_state, final_diag = service_state(final_service)

    if final_state != "MIGRADO_10U_F":
        raise RuntimeError(
            f"Service final inválido: {final_diag}"
        )

    if validate_lock_contract(final_service) != lock_before:
        raise RuntimeError(
            "Contrato sp_getapplock mudou durante 10U-F."
        )

    print("      [OK] ramo GESTOR = 1 BusinessRuleViolation.")
    print("      [OK] _selecionar_candidatos = 6 HTTPException restantes.")
    print("      [OK] criacao.py = 6 HTTPException no total.")


    print("[15/16] Revalidando grafo e handlers...")
    final_modules = build_project_index()
    final_reverse = build_call_graph(final_modules)
    final_affected = transitive_callers(final_reverse)

    if final_affected != affected:
        raise RuntimeError(
            "Grafo de consumidores mudou durante a migração."
        )

    for module_name, function_names in router_groups.items():
        info = final_modules[module_name]
        for fn_name in function_names:
            validate_router_function(
                info["text"],
                info["functions"][fn_name],
                require_business=True,
            )

    print("      [OK] fronteiras preservam HTTP 400.")


    print("[16/16] Revalidando services intermediários...")
    for module_name, fn_name in affected_services:
        fn = final_modules[module_name]["functions"][fn_name]

        if has_generic_http_wrapper(fn):
            raise RuntimeError(
                f"{module_name}.{fn_name} passou a bloquear "
                "BusinessRuleViolation."
            )

    print("      [OK] propagação permanece segura.")


except Exception:
    print()
    print("[ERRO] Falha durante Fase 10U-F.")
    print("[INFO] Restaurando todos os arquivos...")

    for module_name, path in paths_to_edit.items():
        shutil.copy2(backups[module_name], path)
        print(
            f"      [OK] restaurado: {path.relative_to(ROOT)}"
        )

    print("[OK] Estado anterior restaurado.")
    raise


print()
print("[OK] Fase 10U-F aplicada.")
print("[OK] ramo tipo_proxima == GESTOR desacoplado de HTTP.")
print("[OK] HTTP 400 -> BusinessRuleViolation.")
print("[OK] etapa GESTOR continua impedida de virar rodada operacional.")
print("[OK] fluxo de análise gerencial permanece inalterado.")
print("[OK] exatamente 6 HTTPException permaneceram em _selecionar_candidatos.")
print("[OK] candidatos OFICIAL/ROTATIVO não alterados.")
print("[OK] sp_getapplock, SQL, UoW, commit e rollback inalterados.")

print()
print("PRÓXIMO PASSO:")
print("1. Reinicie a API.")
print(r"2. python tests_e2e\regressao_final_sgi.py")
print(r"3. python .\fase10a_auditoria_excecoes_dominio\auditar_fase10a.py")
