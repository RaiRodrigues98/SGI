
"""
FASE 10P - CONFIGURAÇÕES DO INVENTÁRIO

Alvo:
- services/configuracoes_inventario.py

Raises diretos esperados:
- obter_configuracao_inventario:
    2 x HTTP 400
- obter_configuracao_por_inventario:
    1 x HTTP 404
    1 x HTTP 400

Total:
- 4 HTTPException
- perfil: 3 x 400 + 1 x 404

Mapeamento:
- HTTP 400 -> BusinessRuleViolation
- HTTP 404 -> NotFoundError

Este service é cross-cutting.
O instalador usa grafo cross-module com facades/reexports para
encontrar todos os callers transitivos até as fronteiras HTTP.

Bloqueia antes da escrita se:
- existir HTTPException fora das duas funções seed;
- o perfil não for exatamente 3x400 + 1x404;
- surgir caller fora de services/routers;
- um service intermediário capturar Exception e gerar HTTPException;
- uma fronteira HTTP não tiver padrão seguro de except HTTPException.

Depois da migração:
- 0 raise HTTPException no service
- 0 except HTTPException no service
- 0 import FastAPI/Starlette no service
- todos os detalhes/mensagens preservados

Não altera:
- SQL
- sequência/configuração de rodadas
- regras de contagem
- UoW
- commits
- conexão
- services intermediários
- rotas
- retornos de sucesso

Execute:
python .\fase10p_excecoes_configuracoes_inventario\aplicar_fase10p.py
"""

from pathlib import Path
from datetime import datetime
import ast
import py_compile
import shutil

ROOT = Path.cwd()

SERVICE = ROOT / "services" / "configuracoes_inventario.py"
DOMAIN = ROOT / "domain" / "exceptions.py"
PREV = ROOT / "services" / "analise_rotativo.py"

TARGET_MODULE = "services.configuracoes_inventario"

SEED_FUNCTIONS = {
    "obter_configuracao_inventario": {
        400: 2,
    },
    "obter_configuracao_por_inventario": {
        400: 1,
        404: 1,
    },
}

SEED_NODES = {
    (
        TARGET_MODULE,
        function_name,
    )
    for function_name
    in SEED_FUNCTIONS
}

EXC_BY_STATUS = {
    400: "BusinessRuleViolation",
    404: "NotFoundError",
}

STATUS_BY_EXC = {
    value: key
    for key, value
    in EXC_BY_STATUS.items()
}

EXPECTED_TOTAL = 4
EXPECTED_TOTAL_STATUSES = {
    400: 3,
    404: 1,
}

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

# rollback pode ser replicado deliberadamente.
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
        return path.read_text(
            encoding="utf-8"
        )
    except UnicodeDecodeError:
        return path.read_text(
            encoding="latin-1"
        )


def parse(text, name):
    try:
        return ast.parse(text)
    except SyntaxError as exc:
        raise RuntimeError(
            f"{name}: sintaxe inválida: "
            f"{exc}"
        )


def raised_name(expr):
    if isinstance(expr, ast.Name):
        return expr.id

    if isinstance(expr, ast.Call):
        return raised_name(
            expr.func
        )

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


def get_function(
    text,
    function_name,
):
    tree = parse(
        text,
        "services/configuracoes_inventario.py",
    )

    fn = top_functions(
        tree
    ).get(
        function_name
    )

    if fn is None:
        raise RuntimeError(
            f"Função ausente: "
            f"{function_name}"
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

        for kw in (
            node.exc.keywords
        ):
            if (
                kw.arg
                == "status_code"
            ):
                status_node = (
                    kw.value
                )

            elif kw.arg == "detail":
                detail_node = (
                    kw.value
                )

        if (
            status_node is None
            or
            detail_node is None
        ):
            raise RuntimeError(
                f"{function_name}: "
                "HTTPException sem "
                "status/detail."
            )

        if not (
            isinstance(
                status_node,
                ast.Constant,
            )
            and
            isinstance(
                status_node.value,
                int,
            )
        ):
            raise RuntimeError(
                f"{function_name}: "
                "status dinâmico "
                "não suportado."
            )

        detail = (
            ast.get_source_segment(
                text,
                detail_node,
            )
        )

        if not detail:
            raise RuntimeError(
                f"{function_name}: detail "
                "não recuperado."
            )

        result.append(
            {
                "node":
                    node,
                "status":
                    status_node.value,
                "detail":
                    detail,
            }
        )

    return result


def semantic_raises_in_function(
    text,
    function_name,
):
    fn = get_function(
        text,
        function_name,
    )

    allowed = set(
        EXC_BY_STATUS.values()
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

        name = raised_name(
            node.exc
        )

        if name in allowed:
            result.append(name)

    return result


def all_http_raise_locations(text):
    tree = parse(
        text,
        "services/configuracoes_inventario.py",
    )

    functions = top_functions(
        tree
    )

    result = {}

    for fn_name, fn in (
        functions.items()
    ):
        count = 0

        for node in ast.walk(fn):
            if not isinstance(
                node,
                ast.Raise,
            ):
                continue

            if node.exc is None:
                continue

            if (
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
                count += 1

        if count:
            result[
                fn_name
            ] = count

    return result


def total_http_usage(text):
    tree = parse(
        text,
        "services/configuracoes_inventario.py",
    )

    raises = 0
    handlers = 0
    name_loads = 0

    for node in ast.walk(tree):
        if (
            isinstance(
                node,
                ast.Raise,
            )
            and
            node.exc is not None
            and
            raised_name(
                node.exc
            )
            == "HTTPException"
        ):
            raises += 1

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
        ):
            handlers += 1

        if (
            isinstance(
                node,
                ast.Name,
            )
            and
            node.id
            == "HTTPException"
            and
            isinstance(
                node.ctx,
                ast.Load,
            )
        ):
            name_loads += 1

    return {
        "raises": raises,
        "handlers": handlers,
        "name_loads": name_loads,
    }


def fastapi_starlette_imports(text):
    tree = parse(
        text,
        "services/configuracoes_inventario.py",
    )

    result = []

    for node in tree.body:
        if not isinstance(
            node,
            ast.ImportFrom,
        ):
            continue

        module = (
            node.module
            or ""
        )

        if (
            module in {
                "fastapi",
                "starlette",
            }
            or
            module.startswith(
                "fastapi."
            )
            or
            module.startswith(
                "starlette."
            )
        ):
            result.append(
                node
            )

    return result


def service_state(text):
    locations = (
        all_http_raise_locations(
            text
        )
    )

    seed_http = {}
    seed_semantic = {}

    all_statuses = []

    for function_name in (
        SEED_FUNCTIONS
    ):
        raises = (
            http_raises_in_function(
                text,
                function_name,
            )
        )

        semantic = (
            semantic_raises_in_function(
                text,
                function_name,
            )
        )

        counts = {}

        for item in raises:
            status = item[
                "status"
            ]

            counts[
                status
            ] = (
                counts.get(
                    status,
                    0,
                )
                + 1
            )

            all_statuses.append(
                status
            )

        seed_http[
            function_name
        ] = counts

        seed_semantic[
            function_name
        ] = semantic

    total_statuses = {
        status:
            all_statuses.count(
                status
            )
        for status
        in set(all_statuses)
    }

    total = total_http_usage(
        text
    )

    imports = (
        fastapi_starlette_imports(
            text
        )
    )

    expected_locations = {
        function_name:
            sum(
                counts.values()
            )
        for function_name, counts
        in SEED_FUNCTIONS.items()
    }

    if (
        locations
        == expected_locations
        and
        seed_http
        == SEED_FUNCTIONS
        and
        total_statuses
        == EXPECTED_TOTAL_STATUSES
        and
        all(
            not values
            for values
            in seed_semantic.values()
        )
        and
        total["raises"]
        == EXPECTED_TOTAL
        and
        total["handlers"] == 0
        and
        len(imports) == 1
        and
        (
            imports[0].module
            or ""
        )
        == "fastapi"
        and
        [
            alias.name
            for alias
            in imports[0].names
        ]
        == ["HTTPException"]
    ):
        return "LEGADO", {
            "locations":
                locations,
            "seed_http":
                seed_http,
            "total_statuses":
                total_statuses,
            "total":
                total,
        }

    expected_semantic = {
        "obter_configuracao_inventario":
            sorted(
                [
                    "BusinessRuleViolation",
                    "BusinessRuleViolation",
                ]
            ),
        "obter_configuracao_por_inventario":
            sorted(
                [
                    "BusinessRuleViolation",
                    "NotFoundError",
                ]
            ),
    }

    if (
        not locations
        and
        all(
            seed_http[
                function_name
            ]
            == {}
            for function_name
            in SEED_FUNCTIONS
        )
        and
        {
            function_name:
                sorted(values)
            for function_name, values
            in seed_semantic.items()
        }
        == expected_semantic
        and
        total["raises"] == 0
        and
        total["handlers"] == 0
        and
        total["name_loads"] == 0
        and
        len(imports) == 0
    ):
        return "MIGRADO", {
            "locations": {},
            "seed_http":
                seed_http,
            "seed_semantic":
                seed_semantic,
            "total":
                total,
        }

    return "DESCONHECIDO", {
        "locations":
            locations,
        "seed_http":
            seed_http,
        "seed_semantic":
            seed_semantic,
        "total_statuses":
            total_statuses,
        "total":
            total,
        "imports": [
            (
                node.module,
                [
                    alias.name
                    for alias
                    in node.names
                ],
            )
            for node in imports
        ],
    }


# ============================================================
# GRAFO CROSS-MODULE / FACADES
# ============================================================

def is_excluded(path):
    rel = path.relative_to(
        ROOT
    )

    for part in rel.parts:
        low = part.lower()

        if low in EXCLUDED_DIRS:
            return True

        if "_backup_" in low:
            return True

        if low.startswith(
            "backup"
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
        path.relative_to(
            ROOT
        )
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

    package = (
        package_of_module(
            current_module
        )
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

        for alias in (
            node.names
        ):
            if alias.name == "*":
                continue

            result[
                alias.asname
                or
                alias.name
            ] = (
                resolved,
                alias.name,
            )

    return result


def top_alias_assignments(
    tree,
):
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

    for node in ast.walk(
        tree
    ):
        if not isinstance(
            node,
            ast.Import,
        ):
            continue

        for alias in (
            node.names
        ):
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

    for node in ast.walk(
        fn
    ):
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

    for path in (
        production_files()
    ):
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
                call_names(
                    fn
                )
            ):
                callee = (
                    resolve_symbol(
                        modules,
                        module_name,
                        called_name,
                    )
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

    return (
        graph,
        reverse,
    )


def transitive_callers(
    reverse,
):
    affected = set(
        SEED_NODES
    )

    frontier = list(
        SEED_NODES
    )

    while frontier:
        current = (
            frontier.pop()
        )

        for caller in (
            reverse.get(
                current,
                set(),
            )
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
# PROPAGAÇÃO / ROUTER
# ============================================================

def has_generic_http_wrapper(
    fn,
):
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

    if len(
        handlers
    ) != 1:
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

    if len(
        handlers
    ) > 1:
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

        expected_status = (
            STATUS_BY_EXC[
                exc_name
            ]
        )

        actual_status = (
            handler_http_status(
                existing
            )
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
        for name in required_classes
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
            "import FastAPI "
            "reconhecido."
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

    block.extend(
        [
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
        ]
    )

    return block


def patch_router_file(
    text,
    affected_function_names,
    required_classes,
):
    before_exact = {
        token:
            text.count(token)
        for token
        in PROTECTED_EXACT_TOKENS
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

    functions = (
        top_functions(
            tree
        )
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

    for line_no, block_lines in (
        sorted(
            insertions,
            key=lambda item:
                item[0],
            reverse=True,
        )
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
        for token
        in PROTECTED_EXACT_TOKENS
    }

    if before_exact != after_exact:
        differences = {
            token: (
                before_exact[token],
                after_exact[token],
            )
            for token in
            PROTECTED_EXACT_TOKENS
            if (
                before_exact[token]
                != after_exact[token]
            )
        }

        raise RuntimeError(
            "Commit/conexão foi "
            f"alterado: "
            f"{differences}"
        )

    return result


# ============================================================
# PATCH SERVICE
# ============================================================

def replace_fastapi_import_with_domain(
    text,
    required_classes,
):
    tree = parse(
        text,
        "service",
    )

    candidates = []

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
            [
                alias.name
                for alias
                in node.names
            ]
            == ["HTTPException"]
        ):
            candidates.append(
                node
            )

    if len(candidates) != 1:
        raise RuntimeError(
            "Import legado FastAPI "
            "não está no formato "
            "esperado."
        )

    node = candidates[0]

    lines = (
        text.splitlines()
    )

    replacement = (
        "from domain.exceptions import "
        + ", ".join(
            sorted(
                required_classes,
                key=lambda name:
                    STATUS_BY_EXC[
                        name
                    ],
            )
        )
    )

    lines[
        node.lineno - 1:
        node.end_lineno
    ] = [
        replacement
    ]

    result = "\n".join(
        lines
    )

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
            "Service não está "
            f"legado: "
            f"{state} / {diag}"
        )

    replacements = []
    required_classes = set()

    for function_name in (
        SEED_FUNCTIONS
    ):
        raises = (
            http_raises_in_function(
                text,
                function_name,
            )
        )

        for item in raises:
            status = item[
                "status"
            ]

            if (
                status
                not in EXC_BY_STATUS
            ):
                raise RuntimeError(
                    f"HTTP {status} "
                    "fora do escopo."
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
                " "
                * node.col_offset
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

    if len(
        replacements
    ) != EXPECTED_TOTAL:
        raise RuntimeError(
            "Esperadas exatamente "
            "4 conversões."
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

        current = (
            end + 1
        )

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

    usage = (
        total_http_usage(
            result
        )
    )

    if (
        usage["raises"] != 0
        or
        usage["handlers"] != 0
    ):
        raise RuntimeError(
            "Uso funcional HTTP "
            "remanescente antes da "
            f"limpeza do import: "
            f"{usage}"
        )

    result = (
        replace_fastapi_import_with_domain(
            result,
            required_classes,
        )
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
]:
    if not path.exists():
        raise SystemExit(
            f"[ERRO] Arquivo "
            f"ausente: {path}"
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
            "[ERRO] Hierarquia "
            f"de domínio incompleta: "
            f"{token}"
        )

prev_text = read_text(
    PREV
)

if (
    "HTTPException"
    in prev_text
    or
    "fastapi"
    in prev_text.lower()
    or
    "starlette"
    in prev_text.lower()
):
    raise SystemExit(
        "[ERRO] Fase 10O não "
        "reconhecida em "
        "services/analise_rotativo.py."
    )

print(
    "      [OK] Fase 10O "
    "reconhecida."
)


print(
    "[1/15] Analisando baseline 10P..."
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
    f"      raises por função: "
    f"{s_diag.get('locations', {})}"
)

print(
    f"      perfil: "
    f"{s_diag.get('total_statuses', {})}"
)

if s_state == "DESCONHECIDO":
    raise SystemExit(
        "[ERRO] Baseline de "
        "configuracoes_inventario.py "
        f"desconhecida: "
        f"{s_diag}"
    )


print(
    "[2/15] Confirmando 3x400 + 1x404..."
)

if s_state == "LEGADO":
    for function_name in (
        SEED_FUNCTIONS
    ):
        raises = (
            http_raises_in_function(
                service_text,
                function_name,
            )
        )

        for item in raises:
            print(
                f"      "
                f"{function_name}: "
                f"HTTP "
                f"{item['status']} -> "
                f"{EXC_BY_STATUS[item['status']]} "
                f"| detail="
                f"{item['detail']}"
            )

    print(
        "      [OK] perfil "
        "exato confirmado."
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
            "[ERRO] Import de "
            "módulo não suportado em "
            f"{info['path'].relative_to(ROOT)}: "
            f"{info['unsupported_target_imports']}."
        )

print(
    "      [OK] imports/reexports "
    "compatíveis."
)


print(
    "[4/15] Construindo grafo "
    "de consumidores..."
)

_, reverse = (
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
        f"{module_name}."
        f"{fn_name}"
    )


print(
    "[5/15] Classificando caminhos..."
)

internal_target = sorted(
    node
    for node in affected
    if (
        node[0]
        == TARGET_MODULE
    )
)

affected_services = sorted(
    node
    for node in affected
    if (
        node[0]
        != TARGET_MODULE
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
        node[0]
        != TARGET_MODULE
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
    f"      funções internas "
    f"do próprio service: "
    f"{len(internal_target)}"
)

print(
    f"      services "
    f"intermediários externos: "
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
            "captura Exception e "
            "gera HTTPException."
        )

        raise SystemExit(
            "[ERRO] DomainError seria "
            "embrulhado por service "
            "intermediário. "
            "Nenhum arquivo alterado."
        )

    print(
        f"      [OK] "
        f"{module_name}.{fn_name}"
    )

if not affected_routers:
    raise SystemExit(
        "[ERRO] Nenhuma fronteira "
        "HTTP alcançada pelo grafo."
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

for module_name, functions in (
    sorted(
        router_groups.items()
    )
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
            info["text"],
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
        "[9/15] Fase 10P "
        "já aplicada."
    )
    print(
        "      [OK] service e "
        "fronteiras HTTP "
        "consistentes."
    )
    raise SystemExit(0)


print(
    "[9/15] Confirmando que "
    "não existem outros "
    "HTTPException no service..."
)

locations = (
    all_http_raise_locations(
        service_text
    )
)

expected_locations = {
    function_name:
        sum(
            counts.values()
        )
    for function_name, counts
    in SEED_FUNCTIONS.items()
}

if locations != expected_locations:
    raise SystemExit(
        "[ERRO] HTTPException "
        "fora do escopo: "
        f"{locations}"
    )

print(
    "      [OK] os 4 raises "
    "são exatamente os seeds "
    "da Fase 10P."
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
            + "_backup_fase10p_"
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
        "configuracoes_inventario.py..."
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
        "      [OK] 4 "
        "HTTPException migrados."
    )

    print(
        "      [OK] FastAPI "
        "removido do service."
    )


    print(
        "[12/15] Adaptando "
        "fronteiras HTTP..."
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
        "[13/15] Revalidando "
        "service..."
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

    if (
        final_state
        != "MIGRADO"
    ):
        raise RuntimeError(
            "Service final "
            f"inválido: "
            f"{final_diag}"
        )

    print(
        "      [OK] 0 raise "
        "HTTPException."
    )

    print(
        "      [OK] 0 except "
        "HTTPException."
    )

    print(
        "      [OK] 0 import "
        "FastAPI/Starlette."
    )


    print(
        "[14/15] Revalidando "
        "grafo e handlers..."
    )

    final_modules = (
        build_project_index()
    )

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

        for fn_name in function_names:
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
        "      [OK] todas as "
        "fronteiras traduzem "
        "400/404."
    )


    print(
        "[15/15] Revalidando "
        "services intermediários..."
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
        "cross-cutting permanece "
        "segura."
    )


except Exception:
    print()
    print(
        "[ERRO] Falha durante "
        "Fase 10P."
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
    "[OK] Fase 10P aplicada."
)

print(
    "[OK] services/configuracoes_inventario.py "
    "desacoplado de FastAPI."
)

print(
    "[OK] 3 HTTP 400 -> "
    "BusinessRuleViolation."
)

print(
    "[OK] 1 HTTP 404 -> "
    "NotFoundError."
)

print(
    "[OK] configuração de "
    "inventário agora possui "
    "0 HTTPException."
)

print(
    "[OK] todos os consumidores "
    "transitivos foram rastreados."
)

print(
    "[OK] fronteiras HTTP "
    "preservam 400/404."
)

print(
    "[OK] SQL, configuração, "
    "UoW, conexão e commits "
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
