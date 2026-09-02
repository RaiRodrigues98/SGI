
"""
FASE 10N - ANALISE ROTATIVO | ANÁLISE DE SESSÃO

Escopo:
- services/analise_rotativo.py
  - analisar_sessao_rotativo()

Baseline atual confirmado pela auditoria 10A:
- analisar_sessao_rotativo: 8 HTTPException
  - 5 x HTTP 400
  - 3 x HTTP 404
- analisar_inventario_rotativo: 3 HTTPException
  - FORA DO ESCOPO desta fase; ficam para a 10O.

Mapeamento:
- HTTP 400 -> BusinessRuleViolation
- HTTP 404 -> NotFoundError

Migração PARCIAL intencional:
- services/analise_rotativo.py continuará importando HTTPException
  porque analisar_inventario_rotativo ainda possui 3 raises.
- a 10N adiciona imports de domínio e converte SOMENTE os 8 raises
  de analisar_sessao_rotativo.

Segurança:
- exige exatamente 11 HTTPException no arquivo antes da migração;
- exige exatamente 8 no alvo + 3 em analisar_inventario_rotativo;
- exige perfil do alvo 5x400 + 3x404;
- após migração exige exatamente 3 HTTPException remanescentes,
  todos em analisar_inventario_rotativo;
- rastreia callers transitivos com suporte a facades/reexports;
- adapta todas as fronteiras HTTP atingidas;
- reutiliza handlers semânticos já existentes;
- replica rollback/log do except HTTPException;
- preserva SQL, UoW, commit, conexões e retornos;
- auto-restore multi-arquivo em qualquer falha.

Execute:
python .\fase10n_excecoes_analise_rotativo_sessao\aplicar_fase10n.py
"""

from pathlib import Path
from datetime import datetime
import ast
import py_compile
import shutil

ROOT = Path.cwd()

SERVICE = ROOT / "services" / "analise_rotativo.py"
DOMAIN = ROOT / "domain" / "exceptions.py"
PREV = ROOT / "services" / "analise_recontagem_rotativo.py"
APPLICATION_EXCEPTIONS = ROOT / "application" / "exceptions.py"

TARGET_MODULE = "services.analise_rotativo"
TARGET_FUNCTION = "analisar_sessao_rotativo"
REMAINING_FUNCTION = "analisar_inventario_rotativo"
TARGET_NODE = (TARGET_MODULE, TARGET_FUNCTION)

EXC_BY_STATUS = {
    400: "BusinessRuleViolation",
    404: "NotFoundError",
}
STATUS_BY_EXC = {
    value: key
    for key, value in EXC_BY_STATUS.items()
}

EXPECTED_TARGET_STATUS_COUNTS = {
    400: 5,
    404: 3,
}
EXPECTED_TARGET_HTTP = 8
EXPECTED_REMAINING_HTTP = 3
EXPECTED_TOTAL_HTTP_BEFORE = 11

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

# Rollback é deliberadamente replicado nos novos handlers.
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


def get_function(text, name):
    tree = parse(
        text,
        "services/analise_rotativo.py",
    )
    fn = top_functions(tree).get(name)
    if fn is None:
        raise RuntimeError(
            f"Função ausente: {name}"
        )
    return fn


def http_raises_in_function(text, function_name):
    fn = get_function(
        text,
        function_name,
    )
    result = []

    for node in ast.walk(fn):
        if not isinstance(node, ast.Raise):
            continue
        if node.exc is None:
            continue
        if not (
            isinstance(node.exc, ast.Call)
            and
            raised_name(node.exc)
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
                f"{function_name}: status dinâmico "
                "não suportado."
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
            "detail": detail_source,
        })

    return result


def semantic_raises_in_function(text, function_name):
    fn = get_function(
        text,
        function_name,
    )
    allowed = set(
        EXC_BY_STATUS.values()
    )
    result = []

    for node in ast.walk(fn):
        if not isinstance(node, ast.Raise):
            continue
        if node.exc is None:
            continue

        name = raised_name(
            node.exc
        )
        if name in allowed:
            result.append(name)

    return result


def total_http_raises_file(text):
    tree = parse(
        text,
        "services/analise_rotativo.py",
    )
    return sum(
        1
        for node in ast.walk(tree)
        if (
            isinstance(node, ast.Raise)
            and node.exc is not None
            and raised_name(node.exc)
            == "HTTPException"
        )
    )


def total_http_handlers_file(text):
    tree = parse(
        text,
        "services/analise_rotativo.py",
    )
    return sum(
        1
        for node in ast.walk(tree)
        if (
            isinstance(node, ast.ExceptHandler)
            and handler_name(node)
            == "HTTPException"
        )
    )


def service_state(text):
    target_http = http_raises_in_function(
        text,
        TARGET_FUNCTION,
    )
    remaining_http = http_raises_in_function(
        text,
        REMAINING_FUNCTION,
    )
    target_semantic = semantic_raises_in_function(
        text,
        TARGET_FUNCTION,
    )
    remaining_semantic = semantic_raises_in_function(
        text,
        REMAINING_FUNCTION,
    )

    total_http = total_http_raises_file(
        text
    )
    total_handlers = total_http_handlers_file(
        text
    )

    statuses = [
        item["status"]
        for item in target_http
    ]
    status_counts = {
        status: statuses.count(status)
        for status in set(statuses)
    }

    fastapi_import = (
        "from fastapi import HTTPException"
        in text
    )

    # Também aceita import formatado em bloco? O service histórico usa
    # import simples, mas a checagem AST abaixo é a autoridade.
    tree = parse(
        text,
        "services/analise_rotativo.py",
    )
    fastapi_http_imported = False

    for node in tree.body:
        if not isinstance(
            node,
            ast.ImportFrom,
        ):
            continue
        if (
            (node.module or "")
            == "fastapi"
            and
            "HTTPException"
            in [
                alias.name
                for alias in node.names
            ]
        ):
            fastapi_http_imported = True

    if (
        len(target_http)
        == EXPECTED_TARGET_HTTP
        and
        status_counts
        == EXPECTED_TARGET_STATUS_COUNTS
        and
        len(remaining_http)
        == EXPECTED_REMAINING_HTTP
        and
        total_http
        == EXPECTED_TOTAL_HTTP_BEFORE
        and
        len(target_semantic) == 0
        and
        len(remaining_semantic) == 0
        and
        total_handlers == 0
        and
        fastapi_http_imported
    ):
        return "LEGADO", {
            "target_http":
                len(target_http),
            "target_statuses":
                status_counts,
            "remaining_http":
                len(remaining_http),
            "total_http":
                total_http,
        }

    expected_semantic = sorted(
        [
            "BusinessRuleViolation",
        ] * 5
        +
        [
            "NotFoundError",
        ] * 3
    )

    if (
        len(target_http) == 0
        and
        sorted(target_semantic)
        == expected_semantic
        and
        len(remaining_http)
        == EXPECTED_REMAINING_HTTP
        and
        len(remaining_semantic) == 0
        and
        total_http
        == EXPECTED_REMAINING_HTTP
        and
        total_handlers == 0
        and
        fastapi_http_imported
    ):
        return "MIGRADO", {
            "target_http": 0,
            "target_semantic":
                target_semantic,
            "remaining_http":
                len(remaining_http),
            "total_http":
                total_http,
        }

    return "DESCONHECIDO", {
        "target_http":
            len(target_http),
        "target_statuses":
            status_counts,
        "target_semantic":
            target_semantic,
        "remaining_http":
            len(remaining_http),
        "remaining_semantic":
            remaining_semantic,
        "total_http":
            total_http,
        "http_handlers":
            total_handlers,
        "fastapi_http_imported":
            fastapi_http_imported,
        "unused_simple_check":
            fastapi_import,
    }


# ============================================================
# GRAFO CROSS-MODULE COM FACADES/REEXPORTS
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
                alias.name
                == TARGET_MODULE
                or
                alias.name.startswith(
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
        text = read_text(
            path
        )

        try:
            tree = ast.parse(
                text
            )
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
            "Arquivos de produção com "
            "sintaxe inválida: "
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
    visited.add(
        key
    )

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

    imports = info[
        "imports"
    ]

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


def build_call_graph(
    modules,
):
    graph = {}
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

            graph.setdefault(
                caller,
                set(),
            )

            for called_name in (
                call_names(fn)
            ):
                callee = resolve_symbol(
                    modules,
                    module_name,
                    called_name,
                )

                if callee is None:
                    continue

                if callee == caller:
                    continue

                graph[
                    caller
                ].add(
                    callee
                )

                reverse.setdefault(
                    callee,
                    set(),
                ).add(
                    caller
                )

    return graph, reverse


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
# VALIDAÇÃO DE PROPAGAÇÃO / ROUTERS
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
            f"encontrado {len(handlers)}."
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

    last = handler.body[
        -1
    ]

    if not (
        isinstance(
            last,
            ast.Raise,
        )
        and
        last.exc is None
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

    lines = (
        text.splitlines()
    )

    return lines[
        prefix_nodes[0].lineno
        - 1:
        prefix_nodes[-1].end_lineno
    ]


def handler_http_status(
    handler,
):
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

        for kw in (
            node.exc.keywords
        ):
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
                return (
                    kw.value.value
                )

    return None


def existing_semantic_handler(
    fn,
    exc_name,
):
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
            == exc_name
        )
    ]

    if len(handlers) > 1:
        raise RuntimeError(
            f"{fn.name}: handler "
            f"duplicado para "
            f"{exc_name}."
        )

    return (
        handlers[0]
        if handlers
        else None
    )


def validate_router_function(
    text,
    fn,
    required_classes,
    require_all,
):
    http_handler = (
        router_http_handler(
            fn
        )
    )

    prefix = (
        handler_prefix_lines(
            text,
            http_handler,
        )
    )

    for exc_name in (
        required_classes
    ):
        existing = (
            existing_semantic_handler(
                fn,
                exc_name,
            )
        )

        if existing is None:
            if require_all:
                raise RuntimeError(
                    f"{fn.name}: handler "
                    f"{exc_name} ausente."
                )
            continue

        actual_status = (
            handler_http_status(
                existing
            )
        )

        expected_status = (
            STATUS_BY_EXC[
                exc_name
            ]
        )

        if (
            actual_status
            != expected_status
        ):
            raise RuntimeError(
                f"{fn.name}: "
                f"{exc_name} traduz "
                f"HTTP {actual_status}, "
                f"esperado "
                f"{expected_status}."
            )

    return (
        http_handler,
        prefix,
    )


def add_router_domain_imports(
    text,
    required_classes,
):
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

    missing = [
        name
        for name
        in required_classes
        if name not in existing
    ]

    if not missing:
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
            fastapi_import = (
                node
            )
            break

    if fastapi_import is None:
        raise RuntimeError(
            "Router afetado sem "
            "import FastAPI reconhecido."
        )

    lines = (
        text.splitlines()
    )

    lines.insert(
        fastapi_import.end_lineno,
        (
            "from domain.exceptions import "
            + ", ".join(
                sorted(
                    missing,
                    key=lambda name:
                        STATUS_BY_EXC[
                            name
                        ],
                )
            )
        ),
    )

    result = "\n".join(
        lines
    )

    if text.endswith("\n"):
        result += "\n"

    return result


def build_translation_handler(
    exc_name,
    status,
    http_handler,
    prefix_lines,
):
    handler_indent = (
        " "
        * http_handler.col_offset
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
            f"{exc_name} as erro:"
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
            f"status_code={status},"
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
    required_classes,
):
    before_exact = {
        token:
            text.count(token)
        for token in
        PROTECTED_EXACT_TOKENS
    }

    patched = (
        add_router_domain_imports(
            text,
            required_classes,
        )
    )

    tree = parse(
        patched,
        "router após imports",
    )

    functions = top_functions(
        tree
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
                "Função de router "
                f"ausente: {fn_name}"
            )

        (
            http_handler,
            prefix_lines,
        ) = validate_router_function(
            patched,
            fn,
            required_classes,
            require_all=False,
        )

        blocks = []

        for exc_name in (
            required_classes
        ):
            if (
                existing_semantic_handler(
                    fn,
                    exc_name,
                )
                is not None
            ):
                continue

            blocks.extend(
                build_translation_handler(
                    exc_name,
                    STATUS_BY_EXC[
                        exc_name
                    ],
                    http_handler,
                    prefix_lines,
                )
            )

        if blocks:
            insertions.append(
                (
                    http_handler.lineno,
                    blocks,
                )
            )

    lines = (
        patched.splitlines()
    )

    for line_no, block_lines in sorted(
        insertions,
        key=lambda item:
            item[0],
        reverse=True,
    ):
        lines[
            line_no - 1:
            line_no - 1
        ] = block_lines

    result = "\n".join(
        lines
    )

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
            required_classes,
            require_all=True,
        )

    after_exact = {
        token:
            result.count(token)
        for token in
        PROTECTED_EXACT_TOKENS
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
            "Commit/conexão foi "
            f"alterado: {differences}"
        )

    return result


# ============================================================
# PATCH PARCIAL DO SERVICE
# ============================================================

def add_service_domain_imports(
    text,
    required_classes,
):
    tree = parse(
        text,
        "services/analise_rotativo.py",
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
                for alias in node.names
            )

    missing = [
        name
        for name in required_classes
        if name not in existing
    ]

    if not missing:
        return text

    # Não removemos FastAPI: ainda será usado pela função consolidada.
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
                for alias in node.names
            ]
        ):
            fastapi_import = (
                node
            )
            break

    if fastapi_import is None:
        raise RuntimeError(
            "Import HTTPException do "
            "service não encontrado."
        )

    lines = (
        text.splitlines()
    )

    lines.insert(
        fastapi_import.end_lineno,
        (
            "from domain.exceptions import "
            + ", ".join(
                sorted(
                    missing,
                    key=lambda name:
                        STATUS_BY_EXC[
                            name
                        ],
                )
            )
        ),
    )

    result = "\n".join(
        lines
    )

    if text.endswith("\n"):
        result += "\n"

    return result


def patch_service(
    text,
):
    state, diag = (
        service_state(
            text
        )
    )

    if state != "LEGADO":
        raise RuntimeError(
            "Service não está "
            f"legado: {state} / "
            f"{diag}"
        )

    raises = (
        http_raises_in_function(
            text,
            TARGET_FUNCTION,
        )
    )

    if (
        len(raises)
        != EXPECTED_TARGET_HTTP
    ):
        raise RuntimeError(
            "Esperados exatamente "
            "8 HTTPException no alvo."
        )

    replacements = []
    required_classes = set()

    for item in raises:
        status = item[
            "status"
        ]

        if status not in (
            EXC_BY_STATUS
        ):
            raise RuntimeError(
                f"Status HTTP {status} "
                "fora do escopo da 10N."
            )

        exc_name = (
            EXC_BY_STATUS[
                status
            ]
        )
        required_classes.add(
            exc_name
        )

        node = item[
            "node"
        ]
        indent = (
            " " * node.col_offset
        )

        replacement = (
            f"{indent}raise "
            f"{exc_name}(\n"
            f"{indent}    "
            f"{item['detail']}\n"
            f"{indent})"
        )

        replacements.append(
            (
                node.lineno,
                node.end_lineno,
                replacement,
            )
        )

    lines = (
        text.splitlines()
    )

    replacements.sort(
        key=lambda item:
            item[0]
    )

    out = []
    current = 1

    for start, end, replacement in (
        replacements
    ):
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

    result = "\n".join(
        out
    )

    if text.endswith("\n"):
        result += "\n"

    result = (
        add_service_domain_imports(
            result,
            required_classes,
        )
    )

    state2, diag2 = (
        service_state(
            result
        )
    )

    if state2 != "MIGRADO":
        raise RuntimeError(
            "Service pós-patch "
            f"inválido: {diag2}"
        )

    return (
        result,
        sorted(
            required_classes,
            key=lambda name:
                STATUS_BY_EXC[
                    name
                ],
        ),
    )


# ============================================================
# EXECUÇÃO
# ============================================================

print(
    "[0/15] Validando arquivos e pré-requisitos..."
)

for path in [
    SERVICE,
    DOMAIN,
    PREV,
    APPLICATION_EXCEPTIONS,
]:
    if not path.exists():
        raise SystemExit(
            f"[ERRO] Arquivo ausente: "
            f"{path}"
        )

domain_text = read_text(
    DOMAIN
)

for token in [
    "class BusinessRuleViolation(DomainError)",
    "class NotFoundError(DomainError)",
]:
    if token not in domain_text:
        raise SystemExit(
            "[ERRO] Hierarquia de "
            f"domínio incompleta: "
            f"{token}"
        )

app_text = read_text(
    APPLICATION_EXCEPTIONS
)

if (
    "class TechnicalConfigurationError("
    not in app_text
):
    raise SystemExit(
        "[ERRO] Fase 10M v2 não "
        "reconhecida: exceção técnica "
        "ausente."
    )

prev_text = read_text(
    PREV
)

if (
    "from fastapi import HTTPException"
    in prev_text
    or
    "raise HTTPException"
    in prev_text
):
    raise SystemExit(
        "[ERRO] Fase 10M v2 não "
        "reconhecida em "
        "analise_recontagem_rotativo.py."
    )

print(
    "      [OK] Fase 10M v2 reconhecida."
)


print(
    "[1/15] Analisando baseline 10N..."
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
    f"      Estado: {s_state}"
)
print(
    f"      alvo HTTP: "
    f"{s_diag.get('target_http', 0)}"
)
print(
    f"      alvo statuses: "
    f"{s_diag.get('target_statuses', {})}"
)
print(
    f"      inventário HTTP "
    f"fora do escopo: "
    f"{s_diag.get('remaining_http', 0)}"
)
print(
    f"      total HTTP no arquivo: "
    f"{s_diag.get('total_http', 0)}"
)

if s_state == "DESCONHECIDO":
    raise SystemExit(
        "[ERRO] Baseline de "
        "analise_rotativo.py "
        f"desconhecida: {s_diag}"
    )


print(
    "[2/15] Confirmando recorte 8 + 3..."
)

if s_state == "LEGADO":
    if (
        s_diag[
            "target_http"
        ]
        != 8
        or
        s_diag[
            "remaining_http"
        ]
        != 3
        or
        s_diag[
            "total_http"
        ]
        != 11
    ):
        raise SystemExit(
            "[ERRO] Recorte esperado "
            "8 + 3 não confirmado."
        )

    print(
        "      [OK] "
        "analisar_sessao_rotativo = 8."
    )
    print(
        "      [OK] "
        "analisar_inventario_rotativo = 3."
    )


print(
    "[3/15] Indexando módulos de produção..."
)

modules = build_project_index()

print(
    f"      módulos analisados: "
    f"{len(modules)}"
)

if TARGET_MODULE not in modules:
    raise SystemExit(
        "[ERRO] Módulo alvo não indexado."
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
    "      [OK] imports/reexports compatíveis."
)


print(
    "[4/15] Construindo grafo de callers..."
)

_, reverse = build_call_graph(
    modules
)

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
        f"      - {module_name}."
        f"{fn_name}"
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
    f"      services intermediários: "
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
        "[ERRO] Caller fora das "
        "camadas services/routers."
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
            "[ERRO] DomainError seria "
            "embrulhado em service "
            "intermediário."
        )

    print(
        f"      [OK] "
        f"{module_name}.{fn_name}"
    )

if not affected_routers:
    raise SystemExit(
        "[ERRO] Nenhuma fronteira HTTP "
        "alcançada pelo grafo."
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

required_classes = [
    "BusinessRuleViolation",
    "NotFoundError",
]


print(
    "[8/15] Validando handlers atuais..."
)

for module_name, function_names in (
    router_groups.items()
):
    info = modules[
        module_name
    ]

    for fn_name in function_names:
        validate_router_function(
            info[
                "text"
            ],
            info[
                "functions"
            ][
                fn_name
            ],
            required_classes,
            require_all=(
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
        "[9/15] Fase 10N "
        "já aplicada."
    )
    print(
        "      [OK] service e "
        "fronteiras consistentes."
    )
    raise SystemExit(0)


print(
    "[9/15] Confirmando perfil "
    "5x400 + 3x404..."
)

raises = http_raises_in_function(
    service_text,
    TARGET_FUNCTION,
)

counts = {
    400: 0,
    404: 0,
}

for item in raises:
    status = item[
        "status"
    ]

    if status not in counts:
        raise SystemExit(
            f"[ERRO] HTTP {status} "
            "fora do escopo."
        )

    counts[
        status
    ] += 1

    print(
        f"      HTTP {status} -> "
        f"{EXC_BY_STATUS[status]} | "
        f"detail={item['detail']}"
    )

if (
    counts
    != EXPECTED_TARGET_STATUS_COUNTS
):
    raise SystemExit(
        "[ERRO] Perfil do alvo "
        f"inesperado: {counts}"
    )

print(
    "      [OK] perfil confirmado."
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
            + "_backup_fase10n_"
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
        "analisar_sessao_rotativo..."
    )

    (
        patched_service,
        required_classes,
    ) = patch_service(
        service_text
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
        "      [OK] 8 "
        "HTTPException migrados."
    )
    print(
        "      [OK] FastAPI mantido "
        "para os 3 erros da 10O."
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

        original_text = read_text(
            path
        )

        patched_router = (
            patch_router_file(
                original_text,
                affected_function_names=
                    function_names,
                required_classes=
                    required_classes,
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
        "[13/15] Validando recorte pós-migração..."
    )

    final_service = read_text(
        SERVICE
    )

    final_state, final_diag = (
        service_state(
            final_service
        )
    )

    if final_state != "MIGRADO":
        raise RuntimeError(
            "Service final inválido: "
            f"{final_diag}"
        )

    if (
        final_diag[
            "remaining_http"
        ]
        != 3
        or
        final_diag[
            "total_http"
        ]
        != 3
    ):
        raise RuntimeError(
            "Os 3 HTTPException da "
            "10O não foram preservados "
            "exatamente."
        )

    print(
        "      [OK] alvo = "
        "0 HTTPException."
    )
    print(
        "      [OK] restante para "
        "10O = exatamente 3."
    )


    print(
        "[14/15] Revalidando grafo e handlers..."
    )

    final_modules = build_project_index()

    _, final_reverse = (
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
            "mudou durante a migração."
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
                required_classes,
                require_all=True,
            )

    print(
        "      [OK] fronteiras "
        "traduzem 400/404."
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
                "DomainError."
            )

    print(
        "      [OK] propagação "
        "permanece segura."
    )


except Exception:
    print()
    print(
        "[ERRO] Falha durante "
        "Fase 10N."
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
    "[OK] Fase 10N aplicada."
)
print(
    "[OK] analisar_sessao_rotativo "
    "desacoplado de HTTP."
)
print(
    "[OK] 5 HTTP 400 -> "
    "BusinessRuleViolation."
)
print(
    "[OK] 3 HTTP 404 -> "
    "NotFoundError."
)
print(
    "[OK] exatamente 3 "
    "HTTPException permaneceram em "
    "analisar_inventario_rotativo "
    "para a Fase 10O."
)
print(
    "[OK] FastAPI mantido no "
    "service somente por causa do "
    "bloco ainda não migrado."
)
print(
    "[OK] callers transitivos e "
    "facades/reexports rastreados."
)
print(
    "[OK] fronteiras HTTP "
    "preservam 400/404."
)
print(
    "[OK] SQL, UoW, conexão e "
    "regras ROTATIVO inalterados."
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
