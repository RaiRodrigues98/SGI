
"""
FASE 10U-A - CRIAÇÃO DE RODADAS | CONFIGURAÇÃO

Alvo:
- services/rodadas/criacao.py
- _carregar_configuracao_criacao()

Recorte deliberadamente parcial.

Baseline esperado no arquivo:
- 14 raise HTTPException no total
- 3 no alvo _carregar_configuracao_criacao()
- 11 permanecem FORA do escopo desta fase

Perfil do alvo:
- 3 x HTTP 400

Regras:
1. número da próxima rodada excede max_rodadas;
2. fluxo configurado retornou FINALIZADO;
3. próxima rodada está NAO_CONFIGURADA.

Mapeamento:
- HTTP 400 -> BusinessRuleViolation

Ao final:
- alvo: 0 HTTPException + 3 BusinessRuleViolation
- arquivo: exatamente 11 HTTPException remanescentes
- FastAPI permanece, pois ainda é usado pelos próximos recortes
- nenhum raise das outras funções é alterado

Execute:
python .\fase10u_a_excecoes_criacao_configuracao\aplicar_fase10u_a.py
"""

from pathlib import Path
from datetime import datetime
import ast
import py_compile
import shutil

ROOT = Path.cwd()

SERVICE = ROOT / "services" / "rodadas" / "criacao.py"
DOMAIN = ROOT / "domain" / "exceptions.py"
PREV_LOCALIZACOES = ROOT / "services" / "rodadas" / "localizacoes.py"
PREV_LIFECYCLE = ROOT / "services" / "rodadas" / "lifecycle.py"
PREV_CAND_ROTATIVO = ROOT / "services" / "rodadas" / "candidatos_rotativo.py"
PREV_CAND_OFICIAL = ROOT / "services" / "rodadas" / "candidatos_oficial.py"

TARGET_MODULE = "services.rodadas.criacao"
TARGET_FUNCTION = "_carregar_configuracao_criacao"
TARGET_NODE = (TARGET_MODULE, TARGET_FUNCTION)

EXPECTED_TARGET_HTTP = 3
EXPECTED_TARGET_STATUS = {400: 3}

EXPECTED_REMAINING_HTTP_LOCATIONS = {
    "_validar_sem_sessoes_abertas": 1,
    "_serializar_criacao_r2_rotativo": 1,
    "_selecionar_candidatos": 7,
    "_validar_candidatos_divergencia": 1,
    "_gerar_localizacoes_nova_rodada": 1,
}
EXPECTED_REMAINING_TOTAL = sum(
    EXPECTED_REMAINING_HTTP_LOCATIONS.values()
)
EXPECTED_TOTAL_BEFORE = (
    EXPECTED_TARGET_HTTP
    + EXPECTED_REMAINING_TOTAL
)

DETAIL_MARKERS = (
    "número máximo",
    "Não existe próxima rodada configurada",
    "A próxima rodada não está configurada",
)

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
]


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


def get_function(text, function_name):
    tree = parse(
        text,
        "services/rodadas/criacao.py",
    )
    fn = top_functions(tree).get(
        function_name
    )
    if fn is None:
        raise RuntimeError(
            f"Função ausente: {function_name}"
        )
    return fn


def http_raises_in_function(
    text,
    function_name,
):
    fn = get_function(
        text,
        function_name,
    )
    result = []

    for node in ast.walk(fn):
        if not isinstance(
            node,
            ast.Raise,
        ):
            continue

        if node.exc is None:
            continue

        if not (
            isinstance(
                node.exc,
                ast.Call,
            )
            and
            raised_name(
                node.exc
            )
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
            or
            detail_node is None
        ):
            raise RuntimeError(
                f"{function_name}: HTTPException "
                "sem status/detail."
            )

        if not (
            isinstance(
                status_node,
                ast.Constant,
            )
            and isinstance(
                status_node.value,
                int,
            )
        ):
            raise RuntimeError(
                f"{function_name}: status_code "
                "dinâmico não suportado."
            )

        detail_source = ast.get_source_segment(
            text,
            detail_node,
        )

        if not detail_source:
            raise RuntimeError(
                f"{function_name}: detail não "
                "recuperado via AST."
            )

        result.append({
            "node": node,
            "status": status_node.value,
            "detail_source": detail_source,
        })

    return result


def semantic_raises_in_function(
    text,
    function_name,
):
    fn = get_function(
        text,
        function_name,
    )
    result = []

    for node in ast.walk(fn):
        if not isinstance(
            node,
            ast.Raise,
        ):
            continue

        if node.exc is None:
            continue

        if (
            raised_name(node.exc)
            == "BusinessRuleViolation"
        ):
            result.append(
                "BusinessRuleViolation"
            )

    return result


def all_http_raise_locations(text):
    tree = parse(
        text,
        "services/rodadas/criacao.py",
    )
    result = {}

    for fn_name, fn in (
        top_functions(tree).items()
    ):
        count = 0

        for node in ast.walk(fn):
            if (
                isinstance(
                    node,
                    ast.Raise,
                )
                and
                node.exc is not None
                and
                raised_name(node.exc)
                == "HTTPException"
            ):
                count += 1

        if count:
            result[
                fn_name
            ] = count

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
            isinstance(
                node,
                ast.Raise,
            )
            and
            node.exc is not None
            and
            raised_name(node.exc)
            == "HTTPException"
        ):
            raises += 1

        if (
            isinstance(
                node,
                ast.ExceptHandler,
            )
            and
            handler_name(node)
            == "HTTPException"
        ):
            handlers += 1

    return {
        "raises": raises,
        "handlers": handlers,
    }


def fastapi_http_imported(text):
    tree = parse(
        text,
        "services/rodadas/criacao.py",
    )

    for node in tree.body:
        if (
            isinstance(
                node,
                ast.ImportFrom,
            )
            and
            (
                node.module
                or ""
            )
            == "fastapi"
            and
            "HTTPException"
            in [
                alias.name
                for alias in node.names
            ]
        ):
            return True

    return False


def domain_business_imported(text):
    tree = parse(
        text,
        "services/rodadas/criacao.py",
    )

    for node in tree.body:
        if (
            isinstance(
                node,
                ast.ImportFrom,
            )
            and
            (
                node.module
                or ""
            )
            == "domain.exceptions"
            and
            "BusinessRuleViolation"
            in [
                alias.name
                for alias in node.names
            ]
        ):
            return True

    return False


def service_state(text):
    target_http = (
        http_raises_in_function(
            text,
            TARGET_FUNCTION,
        )
    )
    target_semantic = (
        semantic_raises_in_function(
            text,
            TARGET_FUNCTION,
        )
    )
    locations = all_http_raise_locations(
        text
    )
    usage = total_http_usage(
        text
    )

    statuses = [
        item["status"]
        for item in target_http
    ]
    status_counts = {
        status:
            statuses.count(status)
        for status in set(statuses)
    }

    target_details_text = "\n".join(
        item["detail_source"]
        for item in target_http
    )

    expected_before_locations = {
        TARGET_FUNCTION:
            EXPECTED_TARGET_HTTP,
        **EXPECTED_REMAINING_HTTP_LOCATIONS,
    }

    if (
        len(target_http)
        == EXPECTED_TARGET_HTTP
        and
        status_counts
        == EXPECTED_TARGET_STATUS
        and
        all(
            marker
            in target_details_text
            for marker in DETAIL_MARKERS
        )
        and
        len(target_semantic) == 0
        and
        locations
        == expected_before_locations
        and
        usage["raises"]
        == EXPECTED_TOTAL_BEFORE
        and
        usage["handlers"] == 0
        and
        fastapi_http_imported(text)
    ):
        return "LEGADO", {
            "target_http":
                len(target_http),
            "target_statuses":
                status_counts,
            "remaining":
                EXPECTED_REMAINING_HTTP_LOCATIONS,
            "total_http":
                usage["raises"],
        }

    if (
        len(target_http) == 0
        and
        target_semantic
        == [
            "BusinessRuleViolation",
            "BusinessRuleViolation",
            "BusinessRuleViolation",
        ]
        and
        locations
        == EXPECTED_REMAINING_HTTP_LOCATIONS
        and
        usage["raises"]
        == EXPECTED_REMAINING_TOTAL
        and
        usage["handlers"] == 0
        and
        fastapi_http_imported(text)
        and
        domain_business_imported(text)
    ):
        return "MIGRADO", {
            "target_http": 0,
            "target_semantic":
                target_semantic,
            "remaining":
                locations,
            "total_http":
                usage["raises"],
        }

    return "DESCONHECIDO", {
        "target_http":
            len(target_http),
        "target_statuses":
            status_counts,
        "target_semantic":
            target_semantic,
        "locations":
            locations,
        "total_http":
            usage,
        "fastapi_http":
            fastapi_http_imported(
                text
            ),
        "business_import":
            domain_business_imported(
                text
            ),
    }


# ============================================================
# GRAFO CROSS-MODULE COM FACADES / REEXPORTS
# ============================================================

def is_excluded(path):
    rel = path.relative_to(ROOT)

    for part in rel.parts:
        low = part.lower()

        if low in EXCLUDED_DIRS:
            return True

        if (
            "_backup_" in low
            or
            low.startswith(
                "backup"
            )
        ):
            return True

        if low.startswith(
            EXCLUDED_PREFIXES
        ):
            return True

    if (
        rel.parts
        and
        rel.parts[0].lower()
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
        for path in ROOT.rglob(
            "*.py"
        )
        if not is_excluded(
            path
        )
    )


def module_name_from_path(path):
    return ".".join(
        path.relative_to(ROOT)
        .with_suffix("")
        .parts
    )


def package_of_module(
    module_name,
):
    return module_name.split(
        "."
    )[:-1]


def resolve_import_module(
    current_module,
    node,
):
    module = (
        node.module
        or ""
    )

    if node.level == 0:
        return module

    package = package_of_module(
        current_module
    )

    ascend = (
        node.level - 1
    )

    if ascend > len(
        package
    ):
        return None

    base = package[
        :len(package) - ascend
    ]

    if module:
        base += module.split(
            "."
        )

    return ".".join(
        base
    )


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

        resolved = (
            resolve_import_module(
                module_name,
                node,
            )
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
        if isinstance(
            node,
            ast.Assign,
        ):
            if (
                len(
                    node.targets
                )
                == 1
                and
                isinstance(
                    node.targets[0],
                    ast.Name,
                )
                and
                isinstance(
                    node.value,
                    ast.Name,
                )
            ):
                result[
                    node.targets[0].id
                ] = (
                    node.value.id
                )

        elif isinstance(
            node,
            ast.AnnAssign,
        ):
            if (
                isinstance(
                    node.target,
                    ast.Name,
                )
                and
                isinstance(
                    node.value,
                    ast.Name,
                )
            ):
                result[
                    node.target.id
                ] = (
                    node.value.id
                )

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
                alias.name
                == TARGET_MODULE
                or
                alias.name.startswith(
                    TARGET_MODULE
                    + "."
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
            isinstance(
                node,
                ast.Call,
            )
            and
            isinstance(
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

        modules[
            module_name
        ] = {
            "path":
                path,
            "text":
                text,
            "tree":
                tree,
            "functions":
                top_functions(
                    tree
                ),
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

    visited = set(
        visited
    )
    visited.add(key)

    info = modules.get(
        module_name
    )

    if info is None:
        return None

    if (
        symbol_name
        in info["functions"]
    ):
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
            aliases[
                symbol_name
            ],
            visited,
        )

    imports = (
        info["imports"]
    )

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
            info["functions"]
            .items()
        ):
            caller = (
                module_name,
                fn_name,
            )

            for called_name in (
                call_names(fn)
            ):
                callee = (
                    resolve_symbol(
                        modules,
                        module_name,
                        called_name,
                    )
                )

                if (
                    callee is None
                    or
                    callee == caller
                ):
                    continue

                reverse.setdefault(
                    callee,
                    set(),
                ).add(
                    caller
                )

    return reverse


def transitive_callers(
    reverse,
):
    affected = {
        TARGET_NODE
    }

    frontier = [
        TARGET_NODE
    ]

    while frontier:
        current = (
            frontier.pop()
        )

        for caller in reverse.get(
            current,
            set(),
        ):
            if caller in affected:
                continue

            affected.add(
                caller
            )
            frontier.append(
                caller
            )

    return affected


# ============================================================
# SERVICES INTERMEDIÁRIOS / ROUTERS
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
            handler_name(
                handler
            )
            != "Exception"
        ):
            continue

        for inner in ast.walk(
            handler
        ):
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
                raised_name(
                    inner.exc
                )
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
            handler_name(
                node
            )
            == "HTTPException"
        )
    ]

    if len(handlers) != 1:
        raise RuntimeError(
            f"{fn.name}: esperado "
            "exatamente 1 "
            "except HTTPException, "
            f"encontrado "
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

    last = (
        handler.body[-1]
    )

    if not (
        isinstance(
            last,
            ast.Raise,
        )
        and
        last.exc is None
    ):
        raise RuntimeError(
            "except HTTPException "
            "não termina com "
            "`raise` nu."
        )

    prefix_nodes = (
        handler.body[:-1]
    )

    if not prefix_nodes:
        return []

    lines = (
        text.splitlines()
    )

    return lines[
        prefix_nodes[0].lineno
        - 1:
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
            handler_name(
                node
            )
            == "BusinessRuleViolation"
        )
    ]

    if len(handlers) > 1:
        raise RuntimeError(
            f"{fn.name}: handler "
            "duplicado para "
            "BusinessRuleViolation."
        )

    return (
        handlers[0]
        if handlers
        else None
    )


def handler_http_status(handler):
    for node in ast.walk(
        handler
    ):
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
            raised_name(
                node.exc
            )
            == "HTTPException"
        ):
            continue

        for kw in node.exc.keywords:
            if (
                kw.arg
                == "status_code"
                and
                isinstance(
                    kw.value,
                    ast.Constant,
                )
                and
                isinstance(
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

    prefix = (
        handler_prefix_lines(
            text,
            http_handler,
        )
    )

    existing = (
        existing_business_handler(
            fn
        )
    )

    if existing is None:
        if require_business:
            raise RuntimeError(
                f"{fn.name}: handler "
                "BusinessRuleViolation "
                "ausente."
            )
    else:
        status = (
            handler_http_status(
                existing
            )
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
    tree = parse(
        text,
        "router",
    )

    existing = set()

    for node in tree.body:
        if (
            isinstance(
                node,
                ast.ImportFrom,
            )
            and
            (
                node.module
                or ""
            )
            == "domain.exceptions"
        ):
            existing.update(
                alias.name
                for alias
                in node.names
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
            (
                node.module
                or ""
            )
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
        " "
        * (
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
        block.extend(
            prefix_lines
        )
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
        token:
            text.count(token)
        for token
        in PROTECTED_EXACT_TOKENS
    }

    patched = (
        add_business_import(
            text
        )
    )

    tree = parse(
        patched,
        "router após import",
    )

    functions = (
        top_functions(tree)
    )

    insertions = []

    for fn_name in sorted(
        affected_function_names
    ):
        fn = functions.get(
            fn_name
        )

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
            existing_business_handler(
                fn
            )
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
        key=lambda item:
            item[0],
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

    final_functions = (
        top_functions(
            final_tree
        )
    )

    for fn_name in (
        affected_function_names
    ):
        validate_router_function(
            result,
            final_functions[
                fn_name
            ],
            require_business=True,
        )

    after_exact = {
        token:
            result.count(token)
        for token
        in PROTECTED_EXACT_TOKENS
    }

    if (
        before_exact
        != after_exact
    ):
        differences = {
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
            "Commit/conexão "
            f"foi alterado: "
            f"{differences}"
        )

    return result


# ============================================================
# PATCH PARCIAL DO SERVICE
# ============================================================

def ensure_business_import(text):
    if domain_business_imported(
        text
    ):
        return text

    tree = parse(
        text,
        "service",
    )

    fastapi_import = None

    for node in tree.body:
        if (
            isinstance(
                node,
                ast.ImportFrom,
            )
            and
            (
                node.module
                or ""
            )
            == "fastapi"
            and
            "HTTPException"
            in [
                alias.name
                for alias
                in node.names
            ]
        ):
            fastapi_import = node
            break

    if fastapi_import is None:
        raise RuntimeError(
            "Import HTTPException "
            "do service não encontrado."
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


def patch_service(text):
    state, diag = (
        service_state(
            text
        )
    )

    if state != "LEGADO":
        raise RuntimeError(
            "Service não está no "
            f"baseline 10U-A: "
            f"{state} / {diag}"
        )

    raises = (
        http_raises_in_function(
            text,
            TARGET_FUNCTION,
        )
    )

    if len(raises) != 3:
        raise RuntimeError(
            "Esperados exatamente "
            "3 HTTPException no alvo."
        )

    replacements = []

    for item in raises:
        if item["status"] != 400:
            raise RuntimeError(
                f"HTTP {item['status']} "
                "fora do escopo."
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

        replacements.append(
            (
                node.lineno,
                node.end_lineno,
                replacement,
            )
        )

    lines = text.splitlines()

    replacements.sort(
        key=lambda item:
            item[0]
    )

    out = []
    current = 1

    for (
        start,
        end,
        replacement,
    ) in replacements:
        out.extend(
            lines[
                current - 1:
                start - 1
            ]
        )
        out.extend(
            replacement.splitlines()
        )
        current = end + 1

    out.extend(
        lines[
            current - 1:
        ]
    )

    result = "\n".join(out)

    if text.endswith("\n"):
        result += "\n"

    result = ensure_business_import(
        result
    )

    final_state, final_diag = (
        service_state(
            result
        )
    )

    if final_state != "MIGRADO":
        raise RuntimeError(
            "Service pós-patch "
            f"inválido: "
            f"{final_diag}"
        )

    return result


# ============================================================
# EXECUÇÃO
# ============================================================

print(
    "[0/15] Validando arquivos e pré-requisitos..."
)

for path in [
    SERVICE,
    DOMAIN,
    PREV_LOCALIZACOES,
    PREV_LIFECYCLE,
    PREV_CAND_ROTATIVO,
    PREV_CAND_OFICIAL,
]:
    if not path.exists():
        raise SystemExit(
            f"[ERRO] Arquivo "
            f"ausente: {path}"
        )

domain_text = read_text(
    DOMAIN
)

if (
    "class BusinessRuleViolation(DomainError)"
    not in domain_text
):
    raise SystemExit(
        "[ERRO] BusinessRuleViolation "
        "não encontrada."
    )

for label, path in [
    ("10T", PREV_LOCALIZACOES),
    ("10S", PREV_LIFECYCLE),
    ("10R", PREV_CAND_ROTATIVO),
    ("10Q", PREV_CAND_OFICIAL),
]:
    previous_text = read_text(
        path
    )

    if (
        "HTTPException"
        in previous_text
        or
        "fastapi"
        in previous_text.lower()
        or
        "starlette"
        in previous_text.lower()
    ):
        raise SystemExit(
            f"[ERRO] Fase {label} "
            f"não reconhecida em "
            f"{path.relative_to(ROOT)}."
        )

print(
    "      [OK] Fases "
    "10Q/10R/10S/10T reconhecidas."
)


print(
    "[1/15] Analisando baseline 10U-A..."
)

service_text = read_text(
    SERVICE
)

s_state, s_diag = (
    service_state(
        service_text
    )
)

print(
    f"      Estado: "
    f"{s_state}"
)

print(
    f"      target HTTP: "
    f"{s_diag.get('target_http', 0)}"
)

print(
    f"      target statuses: "
    f"{s_diag.get('target_statuses', {})}"
)

print(
    f"      HTTP restantes: "
    f"{s_diag.get('remaining', {})}"
)

print(
    f"      total HTTP no arquivo: "
    f"{s_diag.get('total_http', {})}"
)

if s_state == "DESCONHECIDO":
    raise SystemExit(
        "[ERRO] Baseline de "
        "services/rodadas/criacao.py "
        f"desconhecida: {s_diag}"
    )


print(
    "[2/15] Confirmando recorte "
    "3 alvo + 11 restantes..."
)

if s_state == "LEGADO":
    if (
        s_diag[
            "target_http"
        ]
        != 3
        or
        s_diag[
            "total_http"
        ]
        != 14
    ):
        raise SystemExit(
            "[ERRO] Recorte "
            "3 + 11 não confirmado."
        )

    for item in (
        http_raises_in_function(
            service_text,
            TARGET_FUNCTION,
        )
    ):
        print(
            f"      HTTP "
            f"{item['status']} -> "
            "BusinessRuleViolation | "
            f"detail="
            f"{item['detail_source']}"
        )

    print(
        "      [OK] somente "
        "_carregar_configuracao_criacao "
        "será migrada."
    )


print(
    "[3/15] Indexando módulos de produção..."
)

modules = (
    build_project_index()
)

print(
    f"      módulos analisados: "
    f"{len(modules)}"
)

if (
    TARGET_MODULE
    not in modules
):
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
    "[4/15] Construindo grafo de consumidores..."
)

reverse = (
    build_call_graph(
        modules
    )
)

affected = (
    transitive_callers(
        reverse
    )
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
    "[5/15] Classificando caminhos..."
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
    f"      funções de router: "
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
    "[6/15] Verificando services intermediários..."
)

for module_name, fn_name in (
    affected_services
):
    fn = modules[
        module_name
    ][
        "functions"
    ][
        fn_name
    ]

    if has_generic_http_wrapper(
        fn
    ):
        print(
            f"      [BLOQUEIO] "
            f"{module_name}.{fn_name} "
            "captura Exception e gera "
            "HTTPException."
        )

        raise SystemExit(
            "[ERRO] BusinessRuleViolation "
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
    "[7/15] Agrupando fronteiras HTTP..."
)

router_groups = {}

for module_name, fn_name in (
    affected_routers
):
    router_groups.setdefault(
        module_name,
        set(),
    ).add(
        fn_name
    )

for module_name, functions in sorted(
    router_groups.items()
):
    print(
        f"      {module_name}: "
        f"{sorted(functions)}"
    )


print(
    "[8/15] Validando handlers atuais..."
)

for module_name, function_names in (
    router_groups.items()
):
    info = modules[
        module_name
    ]

    for fn_name in (
        function_names
    ):
        validate_router_function(
            info["text"],
            info[
                "functions"
            ][
                fn_name
            ],
            require_business=(
                s_state
                == "MIGRADO"
            ),
        )

        print(
            f"      [OK] "
            f"{module_name}.{fn_name}"
        )


if s_state == "MIGRADO":
    print(
        "[9/15] Fase 10U-A "
        "já aplicada."
    )

    print(
        "      [OK] target e "
        "fronteiras consistentes."
    )

    raise SystemExit(0)


print(
    "[9/15] Confirmando que os "
    "11 raises restantes não serão tocados..."
)

locations = (
    all_http_raise_locations(
        service_text
    )
)

expected_locations = {
    TARGET_FUNCTION:
        3,
    **EXPECTED_REMAINING_HTTP_LOCATIONS,
}

if locations != expected_locations:
    raise SystemExit(
        "[ERRO] Distribuição de "
        "HTTPException diferente "
        f"do baseline: {locations}"
    )

print(
    "      [OK] distribuição "
    "14 = 3 alvo + 11 remanescentes."
)


print(
    "[10/15] Preparando backups..."
)

timestamp = (
    datetime.now()
    .strftime(
        "%Y%m%d_%H%M%S"
    )
)

paths_to_edit = {
    TARGET_MODULE:
        SERVICE,
}

for module_name in (
    router_groups
):
    paths_to_edit[
        module_name
    ] = modules[
        module_name
    ][
        "path"
    ]

backups = {}

for module_name, path in (
    paths_to_edit.items()
):
    backup = (
        path.parent
        / (
            path.stem
            + "_backup_fase10u_a_"
            + timestamp
            + ".py"
        )
    )

    shutil.copy2(
        path,
        backup,
    )

    backups[
        module_name
    ] = backup

    print(
        f"      "
        f"{path.relative_to(ROOT)} "
        f"-> {backup.name}"
    )


try:
    print(
        "[11/15] Migrando "
        "_carregar_configuracao_criacao..."
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
        "      [OK] 3 HTTP 400 "
        "-> BusinessRuleViolation."
    )

    print(
        "      [OK] FastAPI "
        "mantido para os "
        "11 raises restantes."
    )


    print(
        "[12/15] Adaptando fronteiras HTTP..."
    )

    for module_name, function_names in (
        router_groups.items()
    ):
        path = modules[
            module_name
        ][
            "path"
        ]

        original_text = (
            read_text(path)
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
        "[13/15] Revalidando recorte parcial..."
    )

    final_service = (
        read_text(
            SERVICE
        )
    )

    final_state, final_diag = (
        service_state(
            final_service
        )
    )

    if final_state != "MIGRADO":
        raise RuntimeError(
            "Service final "
            f"inválido: "
            f"{final_diag}"
        )

    print(
        "      [OK] target "
        "= 0 HTTPException."
    )

    print(
        "      [OK] target "
        "= 3 BusinessRuleViolation."
    )

    print(
        "      [OK] arquivo "
        "= exatamente 11 "
        "HTTPException remanescentes."
    )


    print(
        "[14/15] Revalidando grafo e handlers..."
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

    if (
        final_affected
        != affected
    ):
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

        for fn_name in (
            function_names
        ):
            validate_router_function(
                info["text"],
                info[
                    "functions"
                ][
                    fn_name
                ],
                require_business=True,
            )

    print(
        "      [OK] fronteiras "
        "preservam HTTP 400."
    )


    print(
        "[15/15] Revalidando services intermediários..."
    )

    for module_name, fn_name in (
        affected_services
    ):
        fn = final_modules[
            module_name
        ][
            "functions"
        ][
            fn_name
        ]

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
        "Fase 10U-A."
    )

    print(
        "[INFO] Restaurando "
        "todos os arquivos..."
    )

    for module_name, path in (
        paths_to_edit.items()
    ):
        shutil.copy2(
            backups[
                module_name
            ],
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
    "[OK] Fase 10U-A aplicada."
)

print(
    "[OK] _carregar_configuracao_criacao "
    "desacoplada de HTTP."
)

print(
    "[OK] 3 HTTP 400 -> "
    "BusinessRuleViolation."
)

print(
    "[OK] max_rodadas, FINALIZADO e "
    "NAO_CONFIGURADA preservados."
)

print(
    "[OK] exatamente 11 "
    "HTTPException permaneceram "
    "fora do escopo."
)

print(
    "[OK] FastAPI permanece "
    "temporariamente em criacao.py."
)

print(
    "[OK] callers transitivos e "
    "facades/reexports rastreados."
)

print(
    "[OK] SQL, UoW, conexão, "
    "commit e fluxos OFICIAL/ROTATIVO "
    "inalterados."
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
