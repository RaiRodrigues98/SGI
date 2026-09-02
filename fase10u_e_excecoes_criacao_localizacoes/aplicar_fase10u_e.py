
"""
FASE 10U-E - CRIAÇÃO DE RODADAS | LOCALIZAÇÕES DA RECONTAGEM

Alvo:
- services/rodadas/criacao.py
- _gerar_localizacoes_nova_rodada()

Pré-requisito:
- Fase 10U-D aplicada.

Baseline esperado após 10U-D:
- _carregar_configuracao_criacao:
    3 BusinessRuleViolation
- _validar_sem_sessoes_abertas:
    1 BusinessRuleViolation
- _serializar_criacao_r2_rotativo:
    1 ConflictError
- _validar_candidatos_divergencia:
    1 BusinessRuleViolation
- _gerar_localizacoes_nova_rodada:
    1 HTTPException 400
- _selecionar_candidatos:
    7 HTTPException
- criacao.py:
    exatamente 8 HTTPException

Erro alvo:
HTTP 400
"Foram encontrados itens para recontagem, porém nenhuma localização
foi encontrada no snapshot ou no histórico de contagens."

Mapeamento:
HTTP 400 -> BusinessRuleViolation

Ao final:
- _gerar_localizacoes_nova_rodada:
    0 HTTPException
    1 BusinessRuleViolation
- criacao.py:
    exatamente 7 HTTPException remanescentes
- os 7 remanescentes ficam exclusivamente em _selecionar_candidatos
- FastAPI permanece temporariamente

Não altera:
- geração de localizações ROTATIVO;
- sincronização de localizações OFICIAL;
- RodadaLocalizacoes;
- RodadaItens;
- SQL;
- UoW;
- commit/rollback;
- sp_getapplock;
- seleção de candidatos.

Execute:
python .\fase10u_e_excecoes_criacao_localizacoes\aplicar_fase10u_e.py
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
TARGET_FUNCTION = "_gerar_localizacoes_nova_rodada"
TARGET_NODE = (TARGET_MODULE, TARGET_FUNCTION)

PREREQ_CONFIG = "_carregar_configuracao_criacao"
PREREQ_SESSIONS = "_validar_sem_sessoes_abertas"
PREREQ_LOCK = "_serializar_criacao_r2_rotativo"
PREREQ_CANDIDATE_VALIDATION = "_validar_candidatos_divergencia"

EXPECTED_STATUS = 400
EXPECTED_DETAIL = (
    "Foram encontrados itens para "
    "recontagem, porém nenhuma localização "
    "foi encontrada no snapshot ou "
    "no histórico de contagens."
)

EXPECTED_BEFORE_LOCATIONS = {
    "_selecionar_candidatos": 7,
    TARGET_FUNCTION: 1,
}

EXPECTED_AFTER_LOCATIONS = {
    "_selecionar_candidatos": 7,
}

EXPECTED_BEFORE_TOTAL = 8
EXPECTED_AFTER_TOTAL = 7

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
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
}

EXCLUDED_PREFIXES = tuple(
    f"fase{i}"
    for i in range(1, 11)
)


def read_text(path):
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1")


def parse(text, name):
    try:
        return ast.parse(text)
    except SyntaxError as exc:
        raise RuntimeError(
            f"{name}: sintaxe inválida: {exc}"
        )


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
        node.name: node
        for node in tree.body
        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        )
    }


def get_function(text, name):
    tree = parse(
        text,
        "services/rodadas/criacao.py",
    )
    fn = top_functions(tree).get(name)

    if fn is None:
        raise RuntimeError(
            f"Função ausente: {name}"
        )

    return fn


def http_raises_in_function(text, name):
    fn = get_function(text, name)
    result = []

    for node in ast.walk(fn):
        if not isinstance(node, ast.Raise):
            continue

        if node.exc is None:
            continue

        if not (
            isinstance(node.exc, ast.Call)
            and raised_name(node.exc)
            == "HTTPException"
        ):
            continue

        status_node = None
        detail_node = None

        for kw in node.exc.keywords:
            if kw.arg == "status_code":
                status_node = kw.value
            elif kw.arg == "detail":
                detail_node = kw.value

        if (
            status_node is None
            or detail_node is None
        ):
            raise RuntimeError(
                f"{name}: HTTPException sem status/detail."
            )

        if not (
            isinstance(status_node, ast.Constant)
            and isinstance(status_node.value, int)
        ):
            raise RuntimeError(
                f"{name}: status_code dinâmico não suportado."
            )

        detail_source = ast.get_source_segment(
            text,
            detail_node,
        )

        if not detail_source:
            raise RuntimeError(
                f"{name}: detail não recuperado via AST."
            )

        try:
            detail_value = ast.literal_eval(
                detail_node
            )
        except Exception:
            detail_value = None

        result.append({
            "node": node,
            "status": status_node.value,
            "detail_source": detail_source,
            "detail_value": detail_value,
        })

    return result


def semantic_count(
    text,
    function_name,
    exception_name,
):
    fn = get_function(
        text,
        function_name,
    )
    count = 0

    for node in ast.walk(fn):
        if not isinstance(node, ast.Raise):
            continue

        if node.exc is None:
            continue

        if raised_name(node.exc) == exception_name:
            count += 1

    return count


def all_http_locations(text):
    tree = parse(
        text,
        "services/rodadas/criacao.py",
    )
    result = {}

    for fn_name, fn in top_functions(tree).items():
        count = 0

        for node in ast.walk(fn):
            if (
                isinstance(node, ast.Raise)
                and node.exc is not None
                and raised_name(node.exc)
                == "HTTPException"
            ):
                count += 1

        if count:
            result[fn_name] = count

    return result


def total_http_usage(text):
    tree = parse(
        text,
        "services/rodadas/criacao.py",
    )

    raises = 0
    handlers = 0

    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Raise)
            and node.exc is not None
            and raised_name(node.exc)
            == "HTTPException"
        ):
            raises += 1

        if (
            isinstance(node, ast.ExceptHandler)
            and handler_name(node)
            == "HTTPException"
        ):
            handlers += 1

    return {
        "raises": raises,
        "handlers": handlers,
    }


def import_present(
    text,
    module,
    symbol,
):
    tree = parse(
        text,
        "services/rodadas/criacao.py",
    )

    for node in tree.body:
        if (
            isinstance(node, ast.ImportFrom)
            and (node.module or "") == module
            and symbol in [
                alias.name
                for alias in node.names
            ]
        ):
            return True

    return False


def protected_counts(text):
    return {
        token: text.count(token)
        for token in PROTECTED_EXACT_TOKENS
    }


def validate_lock_contract(text):
    counts = {
        token: text.count(token)
        for token in CRITICAL_LOCK_TOKENS
    }

    invalid = {
        token: count
        for token, count in counts.items()
        if count != 1
    }

    if invalid:
        raise RuntimeError(
            "Contrato de concorrência R2 inesperado: "
            f"{invalid}"
        )

    lock_fn = get_function(
        text,
        PREREQ_LOCK,
    )

    lock_text = (
        ast.get_source_segment(
            text,
            lock_fn,
        )
        or ""
    )

    for token in CRITICAL_LOCK_TOKENS:
        if token not in lock_text:
            raise RuntimeError(
                f"Token crítico fora de "
                f"{PREREQ_LOCK}: {token}"
            )

    return counts


def validate_prerequisites(text):
    checks = {
        "config_business":
            semantic_count(
                text,
                PREREQ_CONFIG,
                "BusinessRuleViolation",
            ),
        "config_http":
            len(
                http_raises_in_function(
                    text,
                    PREREQ_CONFIG,
                )
            ),
        "sessions_business":
            semantic_count(
                text,
                PREREQ_SESSIONS,
                "BusinessRuleViolation",
            ),
        "sessions_http":
            len(
                http_raises_in_function(
                    text,
                    PREREQ_SESSIONS,
                )
            ),
        "lock_conflict":
            semantic_count(
                text,
                PREREQ_LOCK,
                "ConflictError",
            ),
        "lock_http":
            len(
                http_raises_in_function(
                    text,
                    PREREQ_LOCK,
                )
            ),
        "candidate_validation_business":
            semantic_count(
                text,
                PREREQ_CANDIDATE_VALIDATION,
                "BusinessRuleViolation",
            ),
        "candidate_validation_http":
            len(
                http_raises_in_function(
                    text,
                    PREREQ_CANDIDATE_VALIDATION,
                )
            ),
    }

    ok = (
        checks["config_business"] == 3
        and checks["config_http"] == 0
        and checks["sessions_business"] == 1
        and checks["sessions_http"] == 0
        and checks["lock_conflict"] == 1
        and checks["lock_http"] == 0
        and checks[
            "candidate_validation_business"
        ] == 1
        and checks[
            "candidate_validation_http"
        ] == 0
    )

    return ok, checks


def service_state(text):
    prereq_ok, prereq = (
        validate_prerequisites(text)
    )

    validate_lock_contract(text)

    target_http = (
        http_raises_in_function(
            text,
            TARGET_FUNCTION,
        )
    )

    target_business = semantic_count(
        text,
        TARGET_FUNCTION,
        "BusinessRuleViolation",
    )

    locations = all_http_locations(text)
    usage = total_http_usage(text)

    imports_ok = (
        import_present(
            text,
            "fastapi",
            "HTTPException",
        )
        and import_present(
            text,
            "domain.exceptions",
            "BusinessRuleViolation",
        )
        and import_present(
            text,
            "domain.exceptions",
            "ConflictError",
        )
    )

    if (
        prereq_ok
        and len(target_http) == 1
        and target_http[0]["status"]
        == EXPECTED_STATUS
        and target_http[0]["detail_value"]
        == EXPECTED_DETAIL
        and target_business == 0
        and locations
        == EXPECTED_BEFORE_LOCATIONS
        and usage["raises"]
        == EXPECTED_BEFORE_TOTAL
        and usage["handlers"] == 0
        and imports_ok
    ):
        return "LEGADO_10U_E", {
            "prereq": prereq,
            "target_http": 1,
            "target_status":
                target_http[0]["status"],
            "target_detail":
                target_http[0]["detail_value"],
            "locations": locations,
            "total_http":
                usage["raises"],
        }

    if (
        prereq_ok
        and len(target_http) == 0
        and target_business == 1
        and locations
        == EXPECTED_AFTER_LOCATIONS
        and usage["raises"]
        == EXPECTED_AFTER_TOTAL
        and usage["handlers"] == 0
        and imports_ok
    ):
        return "MIGRADO_10U_E", {
            "prereq": prereq,
            "target_business": 1,
            "locations": locations,
            "total_http":
                usage["raises"],
        }

    return "DESCONHECIDO", {
        "prereq_ok": prereq_ok,
        "prereq": prereq,
        "target_http":
            len(target_http),
        "target_statuses": [
            item["status"]
            for item in target_http
        ],
        "target_details": [
            item["detail_value"]
            for item in target_http
        ],
        "target_business":
            target_business,
        "locations":
            locations,
        "usage":
            usage,
        "fastapi_http":
            import_present(
                text,
                "fastapi",
                "HTTPException",
            ),
        "business_import":
            import_present(
                text,
                "domain.exceptions",
                "BusinessRuleViolation",
            ),
        "conflict_import":
            import_present(
                text,
                "domain.exceptions",
                "ConflictError",
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

        if "_backup_" in low:
            return True

        if low.startswith("backup"):
            return True

        if low.startswith(
            EXCLUDED_PREFIXES
        ):
            return True

    if (
        rel.parts
        and rel.parts[0].lower()
        in {
            "tests",
            "tests_e2e",
            "test",
        }
    ):
        return True

    return False


def production_files():
    return sorted(
        path
        for path in ROOT.rglob("*.py")
        if not is_excluded(path)
    )


def module_name_from_path(path):
    return ".".join(
        path.relative_to(ROOT)
        .with_suffix("")
        .parts
    )


def package_of_module(module_name):
    return module_name.split(".")[:-1]


def resolve_import_module(
    current_module,
    node,
):
    module = node.module or ""

    if node.level == 0:
        return module

    package = package_of_module(
        current_module
    )
    ascend = node.level - 1

    if ascend > len(package):
        return None

    base = package[
        :len(package) - ascend
    ]

    if module:
        base += module.split(".")

    return ".".join(base)


def top_import_map(
    tree,
    module_name,
):
    result = {}

    for node in tree.body:
        if not isinstance(
            node,
            ast.ImportFrom,
        ):
            continue

        resolved = resolve_import_module(
            module_name,
            node,
        )

        if not resolved:
            continue

        for alias in node.names:
            if alias.name == "*":
                continue

            result[
                alias.asname
                or alias.name
            ] = (
                resolved,
                alias.name,
            )

    return result


def top_alias_assignments(tree):
    result = {}

    for node in tree.body:
        if isinstance(node, ast.Assign):
            if (
                len(node.targets) == 1
                and isinstance(
                    node.targets[0],
                    ast.Name,
                )
                and isinstance(
                    node.value,
                    ast.Name,
                )
            ):
                result[
                    node.targets[0].id
                ] = node.value.id

        elif isinstance(
            node,
            ast.AnnAssign,
        ):
            if (
                isinstance(
                    node.target,
                    ast.Name,
                )
                and isinstance(
                    node.value,
                    ast.Name,
                )
            ):
                result[
                    node.target.id
                ] = node.value.id

    return result


def unsupported_target_module_imports(
    tree,
):
    result = []

    for node in ast.walk(tree):
        if not isinstance(
            node,
            ast.Import,
        ):
            continue

        for alias in node.names:
            if (
                alias.name == TARGET_MODULE
                or alias.name.startswith(
                    TARGET_MODULE + "."
                )
            ):
                result.append(
                    (
                        alias.name,
                        node.lineno,
                    )
                )

    return result


def call_names(fn):
    result = set()

    for node in ast.walk(fn):
        if (
            isinstance(node, ast.Call)
            and isinstance(
                node.func,
                ast.Name,
            )
        ):
            result.add(
                node.func.id
            )

    return result


def build_project_index():
    modules = {}
    syntax_errors = []

    for path in production_files():
        text = read_text(path)

        try:
            tree = ast.parse(text)
        except SyntaxError as exc:
            syntax_errors.append(
                (
                    path,
                    exc,
                )
            )
            continue

        module_name = (
            module_name_from_path(
                path
            )
        )

        modules[module_name] = {
            "path": path,
            "text": text,
            "tree": tree,
            "functions":
                top_functions(tree),
            "imports":
                top_import_map(
                    tree,
                    module_name,
                ),
            "aliases":
                top_alias_assignments(
                    tree
                ),
            "unsupported_target_imports":
                unsupported_target_module_imports(
                    tree
                ),
        }

    if syntax_errors:
        details = "; ".join(
            f"{path.relative_to(ROOT)}: "
            f"{exc}"
            for path, exc
            in syntax_errors
        )

        raise RuntimeError(
            "Arquivos de produção "
            "com sintaxe inválida: "
            + details
        )

    return modules


def resolve_symbol(
    modules,
    module_name,
    symbol_name,
    visited=None,
):
    if visited is None:
        visited = set()

    key = (
        module_name,
        symbol_name,
    )

    if key in visited:
        return None

    visited = set(visited)
    visited.add(key)

    info = modules.get(module_name)

    if info is None:
        return None

    if symbol_name in info["functions"]:
        return (
            module_name,
            symbol_name,
        )

    aliases = info.get(
        "aliases",
        {},
    )

    if symbol_name in aliases:
        return resolve_symbol(
            modules,
            module_name,
            aliases[symbol_name],
            visited,
        )

    imports = info["imports"]

    if symbol_name in imports:
        (
            imported_module,
            imported_name,
        ) = imports[
            symbol_name
        ]

        return resolve_symbol(
            modules,
            imported_module,
            imported_name,
            visited,
        )

    return None


def build_call_graph(modules):
    reverse = {}

    for module_name, info in (
        modules.items()
    ):
        for fn_name, fn in (
            info["functions"].items()
        ):
            caller = (
                module_name,
                fn_name,
            )

            for called_name in (
                call_names(fn)
            ):
                callee = resolve_symbol(
                    modules,
                    module_name,
                    called_name,
                )

                if (
                    callee is None
                    or callee == caller
                ):
                    continue

                reverse.setdefault(
                    callee,
                    set(),
                ).add(caller)

    return reverse


def transitive_callers(reverse):
    affected = {
        TARGET_NODE
    }
    frontier = [
        TARGET_NODE
    ]

    while frontier:
        current = frontier.pop()

        for caller in reverse.get(
            current,
            set(),
        ):
            if caller in affected:
                continue

            affected.add(caller)
            frontier.append(caller)

    return affected


# ============================================================
# PROPAGAÇÃO / ROUTERS
# ============================================================

def has_generic_http_wrapper(fn):
    for handler in [
        node
        for node in ast.walk(fn)
        if isinstance(
            node,
            ast.ExceptHandler,
        )
    ]:
        if (
            handler_name(handler)
            != "Exception"
        ):
            continue

        for inner in ast.walk(handler):
            if not isinstance(
                inner,
                ast.Raise,
            ):
                continue

            if (
                isinstance(
                    inner.exc,
                    ast.Call,
                )
                and
                raised_name(inner.exc)
                == "HTTPException"
            ):
                return True

    return False


def router_http_handler(fn):
    handlers = [
        node
        for node in ast.walk(fn)
        if (
            isinstance(
                node,
                ast.ExceptHandler,
            )
            and
            handler_name(node)
            == "HTTPException"
        )
    ]

    if len(handlers) != 1:
        raise RuntimeError(
            f"{fn.name}: esperado "
            "exatamente 1 except "
            f"HTTPException, encontrado "
            f"{len(handlers)}."
        )

    return handlers[0]


def handler_prefix_lines(
    text,
    handler,
):
    if not handler.body:
        raise RuntimeError(
            "except HTTPException vazio."
        )

    last = handler.body[-1]

    if not (
        isinstance(last, ast.Raise)
        and last.exc is None
    ):
        raise RuntimeError(
            "except HTTPException não "
            "termina com `raise` nu."
        )

    prefix_nodes = (
        handler.body[:-1]
    )

    if not prefix_nodes:
        return []

    lines = text.splitlines()

    return lines[
        prefix_nodes[0].lineno - 1:
        prefix_nodes[-1].end_lineno
    ]


def existing_business_handler(fn):
    handlers = [
        node
        for node in ast.walk(fn)
        if (
            isinstance(
                node,
                ast.ExceptHandler,
            )
            and
            handler_name(node)
            == "BusinessRuleViolation"
        )
    ]

    if len(handlers) > 1:
        raise RuntimeError(
            f"{fn.name}: handler "
            "BusinessRuleViolation duplicado."
        )

    return handlers[0] if handlers else None


def handler_http_status(handler):
    for node in ast.walk(handler):
        if not isinstance(
            node,
            ast.Raise,
        ):
            continue

        if not (
            isinstance(
                node.exc,
                ast.Call,
            )
            and
            raised_name(node.exc)
            == "HTTPException"
        ):
            continue

        for kw in node.exc.keywords:
            if (
                kw.arg == "status_code"
                and isinstance(
                    kw.value,
                    ast.Constant,
                )
                and isinstance(
                    kw.value.value,
                    int,
                )
            ):
                return kw.value.value

    return None


def validate_router_function(
    text,
    fn,
    require_business,
):
    http_handler = (
        router_http_handler(fn)
    )

    prefix = handler_prefix_lines(
        text,
        http_handler,
    )

    existing = existing_business_handler(
        fn
    )

    if existing is None:
        if require_business:
            raise RuntimeError(
                f"{fn.name}: "
                "BusinessRuleViolation "
                "não tratado."
            )
    else:
        status = handler_http_status(
            existing
        )

        if status != 400:
            raise RuntimeError(
                f"{fn.name}: "
                "BusinessRuleViolation "
                f"traduz HTTP {status}, "
                "esperado 400."
            )

    return (
        http_handler,
        prefix,
    )


def add_business_import(text):
    tree = parse(text, "router")
    existing = set()

    for node in tree.body:
        if (
            isinstance(
                node,
                ast.ImportFrom,
            )
            and
            (node.module or "")
            == "domain.exceptions"
        ):
            existing.update(
                alias.name
                for alias in node.names
            )

    if (
        "BusinessRuleViolation"
        in existing
    ):
        return text

    fastapi_import = None

    for node in tree.body:
        if (
            isinstance(
                node,
                ast.ImportFrom,
            )
            and
            (node.module or "")
            == "fastapi"
        ):
            fastapi_import = node
            break

    if fastapi_import is None:
        raise RuntimeError(
            "Router afetado sem "
            "import FastAPI reconhecido."
        )

    lines = text.splitlines()

    lines.insert(
        fastapi_import.end_lineno,
        (
            "from domain.exceptions "
            "import BusinessRuleViolation"
        ),
    )

    result = "\n".join(lines)

    if text.endswith("\n"):
        result += "\n"

    return result


def build_business_handler(
    http_handler,
    prefix_lines,
):
    handler_indent = (
        " " * http_handler.col_offset
    )
    body_indent = (
        " " * (
            http_handler.col_offset
            + 4
        )
    )

    block = [
        (
            f"{handler_indent}except "
            "BusinessRuleViolation "
            "as erro:"
        )
    ]

    if prefix_lines:
        block.extend(prefix_lines)
        block.append("")

    block.extend([
        (
            f"{body_indent}"
            "raise HTTPException("
        ),
        (
            f"{body_indent}    "
            "status_code=400,"
        ),
        (
            f"{body_indent}    "
            "detail=str(erro)"
        ),
        (
            f"{body_indent})"
        ),
        "",
    ])

    return block


def patch_router_file(
    text,
    affected_function_names,
):
    before_exact = {
        token: text.count(token)
        for token
        in PROTECTED_EXACT_TOKENS
    }

    patched = add_business_import(
        text
    )

    tree = parse(
        patched,
        "router após import",
    )
    functions = top_functions(tree)
    insertions = []

    for fn_name in sorted(
        affected_function_names
    ):
        fn = functions.get(fn_name)

        if fn is None:
            raise RuntimeError(
                f"Função de router "
                f"ausente: {fn_name}"
            )

        (
            http_handler,
            prefix,
        ) = validate_router_function(
            patched,
            fn,
            require_business=False,
        )

        if (
            existing_business_handler(fn)
            is not None
        ):
            continue

        insertions.append(
            (
                http_handler.lineno,
                build_business_handler(
                    http_handler,
                    prefix,
                ),
            )
        )

    lines = patched.splitlines()

    for line_no, block in sorted(
        insertions,
        key=lambda item: item[0],
        reverse=True,
    ):
        lines[
            line_no - 1:
            line_no - 1
        ] = block

    result = "\n".join(lines)

    if patched.endswith("\n"):
        result += "\n"

    final_tree = parse(
        result,
        "router final",
    )
    final_functions = top_functions(
        final_tree
    )

    for fn_name in (
        affected_function_names
    ):
        validate_router_function(
            result,
            final_functions[fn_name],
            require_business=True,
        )

    after_exact = {
        token: result.count(token)
        for token
        in PROTECTED_EXACT_TOKENS
    }

    if before_exact != after_exact:
        diffs = {
            token: (
                before_exact[token],
                after_exact[token],
            )
            for token
            in PROTECTED_EXACT_TOKENS
            if (
                before_exact[token]
                != after_exact[token]
            )
        }

        raise RuntimeError(
            "UoW/commit/applock "
            f"alterado no router: {diffs}"
        )

    return result


# ============================================================
# PATCH PARCIAL DO SERVICE
# ============================================================

def patch_service(text):
    state, diag = service_state(text)

    if state != "LEGADO_10U_E":
        raise RuntimeError(
            "Service não está no "
            f"baseline 10U-E: "
            f"{state} / {diag}"
        )

    before_protected = protected_counts(
        text
    )
    before_lock = validate_lock_contract(
        text
    )

    target = http_raises_in_function(
        text,
        TARGET_FUNCTION,
    )

    if len(target) != 1:
        raise RuntimeError(
            "Esperado exatamente "
            "1 HTTPException no alvo."
        )

    item = target[0]

    if item["status"] != EXPECTED_STATUS:
        raise RuntimeError(
            f"HTTP {item['status']} "
            "fora do escopo."
        )

    if (
        item["detail_value"]
        != EXPECTED_DETAIL
    ):
        raise RuntimeError(
            "Detail da validação "
            "de localizações não confere."
        )

    node = item["node"]
    indent = (
        " " * node.col_offset
    )

    replacement = (
        f"{indent}raise "
        "BusinessRuleViolation(\n"
        f"{indent}    "
        f"{item['detail_source']}\n"
        f"{indent})"
    )

    lines = text.splitlines()

    lines[
        node.lineno - 1:
        node.end_lineno
    ] = replacement.splitlines()

    result = "\n".join(lines)

    if text.endswith("\n"):
        result += "\n"

    after_protected = protected_counts(
        result
    )

    if (
        before_protected
        != after_protected
    ):
        diffs = {
            token: (
                before_protected[token],
                after_protected[token],
            )
            for token
            in PROTECTED_EXACT_TOKENS
            if (
                before_protected[token]
                != after_protected[token]
            )
        }

        raise RuntimeError(
            "UoW/commit/applock "
            f"alterado: {diffs}"
        )

    after_lock = validate_lock_contract(
        result
    )

    if before_lock != after_lock:
        raise RuntimeError(
            "Contrato sp_getapplock "
            "mudou durante 10U-E."
        )

    final_state, final_diag = (
        service_state(result)
    )

    if (
        final_state
        != "MIGRADO_10U_E"
    ):
        raise RuntimeError(
            "Service pós-patch "
            f"inválido: {final_diag}"
        )

    return result


# ============================================================
# EXECUÇÃO
# ============================================================

print(
    "[0/16] Validando arquivos e hierarquia..."
)

for path in [
    SERVICE,
    DOMAIN,
]:
    if not path.exists():
        raise SystemExit(
            f"[ERRO] Arquivo "
            f"ausente: {path}"
        )

domain_text = read_text(DOMAIN)

for token in [
    "class BusinessRuleViolation(DomainError)",
    "class ConflictError(DomainError)",
]:
    if token not in domain_text:
        raise SystemExit(
            "[ERRO] Hierarquia "
            f"incompleta: {token}"
        )

print(
    "      [OK] exceções "
    "de domínio disponíveis."
)


print(
    "[1/16] Validando pré-requisito 10U-D..."
)

service_text = read_text(SERVICE)

s_state, s_diag = service_state(
    service_text
)

print(
    f"      Estado: {s_state}"
)
print(
    f"      pré-requisitos: "
    f"{s_diag.get('prereq', {})}"
)
print(
    f"      target HTTP: "
    f"{s_diag.get('target_http', 0)}"
)
print(
    f"      total HTTP: "
    f"{s_diag.get('total_http', s_diag.get('usage', {}))}"
)

if s_state == "DESCONHECIDO":
    raise SystemExit(
        "[ERRO] Fase 10U-D "
        "não reconhecida ou "
        f"baseline inesperado: {s_diag}"
    )

if s_state == "MIGRADO_10U_E":
    print(
        "[2/16] Fase 10U-E "
        "já aplicada."
    )
    print(
        "      [OK] target "
        "já está semântico."
    )
    raise SystemExit(0)

print(
    "      [OK] Fase 10U-D "
    "reconhecida."
)


print(
    "[2/16] Revalidando sp_getapplock..."
)

lock_before = validate_lock_contract(
    service_text
)

for token, count in (
    lock_before.items()
):
    print(
        f"      [OK] {token}: {count}"
    )


print(
    "[3/16] Confirmando HTTP 400 "
    "de ausência de localizações..."
)

item = http_raises_in_function(
    service_text,
    TARGET_FUNCTION,
)[0]

print(
    f"      HTTP {item['status']} "
    "-> BusinessRuleViolation"
)
print(
    f"      detail: "
    f"{item['detail_value']}"
)

if (
    item["status"] != 400
    or
    item["detail_value"]
    != EXPECTED_DETAIL
):
    raise SystemExit(
        "[ERRO] Perfil alvo "
        "não confirmado."
    )

print(
    "      [OK] perfil "
    "exato confirmado."
)


print(
    "[4/16] Indexando módulos de produção..."
)

modules = build_project_index()

print(
    f"      módulos analisados: "
    f"{len(modules)}"
)

if TARGET_MODULE not in modules:
    raise SystemExit(
        "[ERRO] Módulo alvo "
        "não indexado."
    )

for module_name, info in (
    modules.items()
):
    if info[
        "unsupported_target_imports"
    ]:
        raise SystemExit(
            "[ERRO] Import de módulo "
            "não suportado em "
            f"{info['path'].relative_to(ROOT)}: "
            f"{info['unsupported_target_imports']}."
        )

print(
    "      [OK] imports/reexports "
    "compatíveis."
)


print(
    "[5/16] Construindo grafo de consumidores..."
)

reverse = build_call_graph(modules)

affected = transitive_callers(
    reverse
)

print(
    f"      funções afetadas: "
    f"{len(affected)}"
)

for module_name, fn_name in sorted(
    affected
):
    print(
        f"      - "
        f"{module_name}.{fn_name}"
    )


print(
    "[6/16] Classificando caminhos..."
)

affected_services = sorted(
    node
    for node in affected
    if (
        node != TARGET_NODE
        and
        node[0].startswith(
            "services."
        )
    )
)

affected_routers = sorted(
    node
    for node in affected
    if node[0].startswith(
        "routers."
    )
)

unexpected = sorted(
    node
    for node in affected
    if (
        node != TARGET_NODE
        and
        not node[0].startswith(
            "services."
        )
        and
        not node[0].startswith(
            "routers."
        )
    )
)

print(
    f"      services "
    f"intermediários: "
    f"{len(affected_services)}"
)
print(
    f"      funções "
    f"de router: "
    f"{len(affected_routers)}"
)

if unexpected:
    for node in unexpected:
        print(
            f"      [BLOQUEIO] "
            f"{node[0]}.{node[1]}"
        )

    raise SystemExit(
        "[ERRO] Caller fora "
        "de services/routers."
    )


print(
    "[7/16] Verificando services intermediários..."
)

for module_name, fn_name in (
    affected_services
):
    fn = modules[
        module_name
    ]["functions"][fn_name]

    if has_generic_http_wrapper(
        fn
    ):
        print(
            f"      [BLOQUEIO] "
            f"{module_name}.{fn_name} "
            "captura Exception "
            "e gera HTTPException."
        )

        raise SystemExit(
            "[ERRO] "
            "BusinessRuleViolation "
            "seria embrulhada por "
            "service intermediário."
        )

    print(
        f"      [OK] "
        f"{module_name}.{fn_name}"
    )

if not affected_routers:
    raise SystemExit(
        "[ERRO] Nenhuma "
        "fronteira HTTP alcançada."
    )


print(
    "[8/16] Agrupando fronteiras HTTP..."
)

router_groups = {}

for module_name, fn_name in (
    affected_routers
):
    router_groups.setdefault(
        module_name,
        set(),
    ).add(fn_name)

for module_name, functions in sorted(
    router_groups.items()
):
    print(
        f"      {module_name}: "
        f"{sorted(functions)}"
    )


print(
    "[9/16] Validando handlers atuais..."
)

for module_name, function_names in (
    router_groups.items()
):
    info = modules[module_name]

    for fn_name in function_names:
        validate_router_function(
            info["text"],
            info["functions"][fn_name],
            require_business=False,
        )

        print(
            f"      [OK] "
            f"{module_name}.{fn_name}"
        )


print(
    "[10/16] Confirmando proteção "
    "dos 7 raises restantes..."
)

locations = all_http_locations(
    service_text
)

if (
    locations
    != EXPECTED_BEFORE_LOCATIONS
):
    raise SystemExit(
        "[ERRO] Distribuição HTTP "
        f"inesperada: {locations}"
    )

print(
    "      [OK] 8 HTTP atuais = "
    "1 alvo + 7 preservados."
)

print(
    "      [OK] os 7 preservados "
    "estão exclusivamente em "
    "_selecionar_candidatos."
)


print(
    "[11/16] Preparando backups..."
)

timestamp = (
    datetime.now()
    .strftime(
        "%Y%m%d_%H%M%S"
    )
)

paths_to_edit = {
    TARGET_MODULE: SERVICE,
}

for module_name in router_groups:
    paths_to_edit[
        module_name
    ] = modules[
        module_name
    ]["path"]

backups = {}

for module_name, path in (
    paths_to_edit.items()
):
    backup = (
        path.parent
        / (
            path.stem
            + "_backup_fase10u_e_"
            + timestamp
            + ".py"
        )
    )

    shutil.copy2(
        path,
        backup,
    )

    backups[module_name] = backup

    print(
        f"      "
        f"{path.relative_to(ROOT)} "
        f"-> {backup.name}"
    )


try:
    print(
        "[12/16] Migrando "
        "_gerar_localizacoes_nova_rodada..."
    )

    patched_service = (
        patch_service(
            service_text
        )
    )

    SERVICE.write_text(
        patched_service,
        encoding="utf-8",
    )

    py_compile.compile(
        str(SERVICE),
        doraise=True,
    )

    print(
        "      [OK] HTTP 400 -> "
        "BusinessRuleViolation."
    )
    print(
        "      [OK] FastAPI "
        "permanece pelos 7 "
        "raises restantes."
    )


    print(
        "[13/16] Adaptando fronteiras HTTP..."
    )

    for module_name, function_names in (
        router_groups.items()
    ):
        path = modules[
            module_name
        ]["path"]

        original_text = read_text(
            path
        )

        patched_router = (
            patch_router_file(
                original_text,
                function_names,
            )
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
            f"      [OK] "
            f"{module_name}: "
            f"{sorted(function_names)}"
        )


    print(
        "[14/16] Revalidando recorte parcial..."
    )

    final_service = read_text(
        SERVICE
    )

    final_state, final_diag = (
        service_state(
            final_service
        )
    )

    if (
        final_state
        != "MIGRADO_10U_E"
    ):
        raise RuntimeError(
            "Service final inválido: "
            f"{final_diag}"
        )

    if (
        validate_lock_contract(
            final_service
        )
        != lock_before
    ):
        raise RuntimeError(
            "Contrato sp_getapplock "
            "mudou durante 10U-E."
        )

    print(
        "      [OK] target = "
        "1 BusinessRuleViolation."
    )
    print(
        "      [OK] arquivo = "
        "exatamente 7 "
        "HTTPException remanescentes."
    )
    print(
        "      [OK] todos os "
        "7 remanescentes estão em "
        "_selecionar_candidatos."
    )


    print(
        "[15/16] Revalidando grafo e handlers..."
    )

    final_modules = (
        build_project_index()
    )

    final_reverse = (
        build_call_graph(
            final_modules
        )
    )

    final_affected = (
        transitive_callers(
            final_reverse
        )
    )

    if final_affected != affected:
        raise RuntimeError(
            "Grafo de consumidores "
            "mudou durante migração."
        )

    for module_name, function_names in (
        router_groups.items()
    ):
        info = final_modules[
            module_name
        ]

        for fn_name in function_names:
            validate_router_function(
                info["text"],
                info["functions"][fn_name],
                require_business=True,
            )

    print(
        "      [OK] fronteiras "
        "preservam HTTP 400."
    )


    print(
        "[16/16] Revalidando services intermediários..."
    )

    for module_name, fn_name in (
        affected_services
    ):
        fn = final_modules[
            module_name
        ]["functions"][fn_name]

        if has_generic_http_wrapper(
            fn
        ):
            raise RuntimeError(
                f"{module_name}.{fn_name} "
                "passou a bloquear "
                "BusinessRuleViolation."
            )

    print(
        "      [OK] propagação "
        "permanece segura."
    )


except Exception:
    print()
    print(
        "[ERRO] Falha durante "
        "Fase 10U-E."
    )
    print(
        "[INFO] Restaurando "
        "todos os arquivos..."
    )

    for module_name, path in (
        paths_to_edit.items()
    ):
        shutil.copy2(
            backups[module_name],
            path,
        )

        print(
            f"      [OK] restaurado: "
            f"{path.relative_to(ROOT)}"
        )

    print(
        "[OK] Estado anterior "
        "restaurado."
    )
    raise


print()
print(
    "[OK] Fase 10U-E aplicada."
)
print(
    "[OK] _gerar_localizacoes_nova_rodada "
    "desacoplada de HTTP."
)
print(
    "[OK] HTTP 400 -> "
    "BusinessRuleViolation."
)
print(
    "[OK] regra de itens de "
    "recontagem sem localização preservada."
)
print(
    "[OK] geração ROTATIVO e "
    "sincronização OFICIAL não alteradas."
)
print(
    "[OK] exatamente 7 "
    "HTTPException permaneceram "
    "fora do escopo."
)
print(
    "[OK] os 7 remanescentes "
    "estão exclusivamente em "
    "_selecionar_candidatos."
)
print(
    "[OK] sp_getapplock, SQL, UoW, "
    "commit e rollback inalterados."
)

print()
print(
    "PRÓXIMO PASSO:"
)
print(
    "1. Reinicie a API."
)
print(
    r"2. python tests_e2e\regressao_final_sgi.py"
)
print(
    r"3. python .\fase10a_auditoria_excecoes_dominio\auditar_fase10a.py"
)
