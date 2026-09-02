
"""
FASE 10M - DESACOPLAMENTO HTTP DE analise_recontagem_rotativo

Escopo principal:
- services/analise_recontagem_rotativo.py

Baseline esperado pelo mapa 10A atual:
- 4 raise HTTPException
  - 1 técnico HTTP 500 em _resolver_coluna_quantidade
  - 1 HTTP 404 em _buscar_rodada
  - 2 HTTP 400 em analisar_recontagem_rotativo

Mapeamento:
- 400 -> domain.exceptions.BusinessRuleViolation
- 404 -> domain.exceptions.NotFoundError
- 500 -> application.exceptions.TechnicalConfigurationError

A exceção 500 NÃO é DomainError.
Ela representa inconsistência técnica/schema necessária para impedir
uma análise ROTATIVO potencialmente incorreta.

O instalador:
1. valida exatamente 4 HTTPException no arquivo local;
2. exige perfil 2x400 + 1x404 + 1x500;
3. preserva cada detail via AST;
4. cria application/exceptions.py de forma segura, se necessário;
5. remove FastAPI do service;
6. constrói grafo de chamadas cross-module;
7. rastreia callers transitivos até routers;
8. bloqueia service intermediário que transforme Exception em HTTPException;
9. adapta todas as fronteiras HTTP;
10. replica rollback/log do except HTTPException nos novos handlers;
11. auto-restaura todos os arquivos e novos artifacts em caso de falha.

Não altera SQL, classificação ROTATIVO, regras de R1/R2,
services intermediários, commits, conexão, rotas ou retornos de sucesso.

Execute:
python .\fase10m_excecoes_analise_recontagem_rotativo\aplicar_fase10m.py
"""

from pathlib import Path
from datetime import datetime
import ast
import py_compile
import shutil

ROOT = Path.cwd()

SERVICE = ROOT / "services" / "analise_recontagem_rotativo.py"
DOMAIN = ROOT / "domain" / "exceptions.py"
PREV = ROOT / "services" / "analise_recontagem.py"

APPLICATION_DIR = ROOT / "application"
APPLICATION_INIT = APPLICATION_DIR / "__init__.py"
APPLICATION_EXCEPTIONS = APPLICATION_DIR / "exceptions.py"

TARGET_MODULE = "services.analise_recontagem_rotativo"

EXC_BY_STATUS = {
    400: ("BusinessRuleViolation", "domain.exceptions"),
    404: ("NotFoundError", "domain.exceptions"),
    500: ("TechnicalConfigurationError", "application.exceptions"),
}

STATUS_BY_EXC = {
    class_name: status
    for status, (class_name, _) in EXC_BY_STATUS.items()
}

EXPECTED_STATUS_COUNTS = {
    400: 2,
    404: 1,
    500: 1,
}

EXPECTED_FUNCTION_COUNTS = {
    "_resolver_coluna_quantidade": {
        500: 1,
    },
    "_buscar_rodada": {
        404: 1,
    },
    "analisar_recontagem_rotativo": {
        400: 2,
    },
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

        if low.startswith(EXCLUDED_PREFIXES):
            return True

    if (
        rel.parts
        and
        rel.parts[0].lower()
        in {"tests", "tests_e2e", "test"}
    ):
        return True

    return False


def production_files():
    return sorted(
        p
        for p in ROOT.rglob("*.py")
        if not is_excluded(p)
    )


def module_name_from_path(path):
    return ".".join(
        path.relative_to(ROOT)
        .with_suffix("")
        .parts
    )


def package_of_module(module_name):
    return module_name.split(".")[:-1]


def resolve_import_module(current_module, node):
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


def top_import_map(tree, module_name):
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


def unsupported_target_module_imports(tree):
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
        text = read_text(path)

        try:
            tree = ast.parse(text)
        except SyntaxError as exc:
            syntax_errors.append(
                (path, exc)
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
            "unsupported_target_imports":
                unsupported_target_module_imports(
                    tree
                ),
        }

    if syntax_errors:
        details = "; ".join(
            f"{path.relative_to(ROOT)}: {exc}"
            for path, exc
            in syntax_errors
        )

        raise RuntimeError(
            "Arquivos de produção com "
            "sintaxe inválida: "
            + details
        )

    return modules


def build_call_graph(modules):
    graph = {}
    reverse = {}

    for module_name, info in (
        modules.items()
    ):
        local_functions = set(
            info["functions"]
        )

        imports = info[
            "imports"
        ]

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
                callee = None

                if (
                    called_name
                    in local_functions
                ):
                    callee = (
                        module_name,
                        called_name,
                    )

                elif (
                    called_name
                    in imports
                ):
                    (
                        imported_module,
                        imported_name,
                    ) = imports[
                        called_name
                    ]

                    if (
                        imported_module
                        in modules
                        and
                        imported_name
                        in modules[
                            imported_module
                        ][
                            "functions"
                        ]
                    ):
                        callee = (
                            imported_module,
                            imported_name,
                        )

                if callee is None:
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


def all_target_nodes(text):
    """
    As exceções podem nascer em helpers internos.
    Consideramos como seeds todas as funções do service
    que possuem raises semânticos/HTTP alvo.
    """
    tree = parse(
        text,
        "services/analise_recontagem_rotativo.py",
    )

    functions = top_functions(tree)

    seeds = set()

    for fn_name in (
        EXPECTED_FUNCTION_COUNTS
    ):
        if fn_name not in functions:
            raise RuntimeError(
                f"Função esperada ausente: "
                f"{fn_name}"
            )

        seeds.add(
            (
                TARGET_MODULE,
                fn_name,
            )
        )

    return seeds


def transitive_callers(reverse, seeds):
    affected = set(
        seeds
    )

    frontier = list(
        seeds
    )

    while frontier:
        current = frontier.pop()

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


def http_raises_by_function(text):
    tree = parse(
        text,
        "services/analise_recontagem_rotativo.py",
    )

    functions = top_functions(
        tree
    )

    result = {}

    for fn_name, fn in (
        functions.items()
    ):
        items = []

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

            status = None
            detail = None

            for kw in (
                node.exc.keywords
            ):
                if (
                    kw.arg
                    == "status_code"
                ):
                    status = kw.value

                elif (
                    kw.arg
                    == "detail"
                ):
                    detail = kw.value

            if (
                status is None
                or
                detail is None
            ):
                raise RuntimeError(
                    f"{fn_name}: HTTPException "
                    "sem status/detail."
                )

            if not (
                isinstance(
                    status,
                    ast.Constant,
                )
                and
                isinstance(
                    status.value,
                    int,
                )
            ):
                raise RuntimeError(
                    f"{fn_name}: status_code "
                    "dinâmico não suportado."
                )

            detail_source = (
                ast.get_source_segment(
                    text,
                    detail,
                )
            )

            if not detail_source:
                raise RuntimeError(
                    f"{fn_name}: detail "
                    "não recuperado."
                )

            items.append(
                {
                    "node": node,
                    "status":
                        status.value,
                    "detail":
                        detail_source,
                }
            )

        if items:
            result[
                fn_name
            ] = items

    return result


def domain_app_raises_by_function(text):
    tree = parse(
        text,
        "services/analise_recontagem_rotativo.py",
    )

    functions = top_functions(
        tree
    )

    allowed = {
        class_name
        for class_name, _
        in EXC_BY_STATUS.values()
    }

    result = {}

    for fn_name, fn in (
        functions.items()
    ):
        names = []

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
                names.append(
                    name
                )

        if names:
            result[
                fn_name
            ] = names

    return result


def total_http_handlers(text):
    tree = parse(
        text,
        "service",
    )

    return sum(
        1
        for node in ast.walk(
            tree
        )
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
    )


def fastapi_starlette_imports(text):
    tree = parse(
        text,
        "service",
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
            module
            in {
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
    http = (
        http_raises_by_function(
            text
        )
    )

    semantic = (
        domain_app_raises_by_function(
            text
        )
    )

    all_http_items = [
        item
        for items in http.values()
        for item in items
    ]

    statuses = [
        item["status"]
        for item
        in all_http_items
    ]

    status_counts = {
        status:
            statuses.count(
                status
            )
        for status
        in set(statuses)
    }

    function_counts = {}

    for fn_name, items in (
        http.items()
    ):
        counts = {}

        for item in items:
            counts[
                item["status"]
            ] = (
                counts.get(
                    item["status"],
                    0,
                )
                + 1
            )

        function_counts[
            fn_name
        ] = counts

    imports = (
        fastapi_starlette_imports(
            text
        )
    )

    handlers = (
        total_http_handlers(
            text
        )
    )

    if (
        len(all_http_items) == 4
        and
        status_counts
        == EXPECTED_STATUS_COUNTS
        and
        function_counts
        == EXPECTED_FUNCTION_COUNTS
        and
        not semantic
        and
        handlers == 0
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
            for alias in
            imports[0].names
        ]
        == ["HTTPException"]
    ):
        return "LEGADO", {
            "status_counts":
                status_counts,
            "function_counts":
                function_counts,
            "semantic":
                semantic,
        }

    expected_semantic = {
        "_resolver_coluna_quantidade": [
            "TechnicalConfigurationError",
        ],
        "_buscar_rodada": [
            "NotFoundError",
        ],
        "analisar_recontagem_rotativo": [
            "BusinessRuleViolation",
            "BusinessRuleViolation",
        ],
    }

    if (
        not http
        and
        {
            key: sorted(value)
            for key, value
            in semantic.items()
        }
        == {
            key: sorted(value)
            for key, value
            in expected_semantic.items()
        }
        and
        handlers == 0
        and
        len(imports) == 0
    ):
        return "MIGRADO", {
            "status_counts": {},
            "function_counts": {},
            "semantic":
                semantic,
        }

    return "DESCONHECIDO", {
        "http": {
            fn: [
                item["status"]
                for item in items
            ]
            for fn, items
            in http.items()
        },
        "semantic":
            semantic,
        "handlers":
            handlers,
        "imports": [
            (
                node.module,
                [
                    alias.name
                    for alias
                    in node.names
                ],
            )
            for node
            in imports
        ],
    }


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
            "exatamente 1 except "
            "HTTPException, encontrado "
            f"{len(handlers)}."
        )

    return handlers[0]


def handler_prefix_lines(text, handler):
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
            f"duplicado para {exc_name}."
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
                f"{fn.name}: {exc_name} "
                f"traduz HTTP "
                f"{actual_status}, "
                f"esperado "
                f"{expected_status}."
            )

    return (
        http_handler,
        prefix,
    )


def add_router_imports(
    text,
    required_imports,
):
    tree = parse(
        text,
        "router",
    )

    existing = {}

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

        if module in {
            "domain.exceptions",
            "application.exceptions",
        }:
            existing.setdefault(
                module,
                set(),
            ).update(
                alias.name
                for alias
                in node.names
            )

    missing_by_module = {}

    for class_name, module in (
        required_imports.items()
    ):
        if (
            class_name
            not in existing.get(
                module,
                set(),
            )
        ):
            missing_by_module.setdefault(
                module,
                []
            ).append(
                class_name
            )

    if not missing_by_module:
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

    lines = (
        text.splitlines()
    )

    insert_at = (
        fastapi_import.end_lineno
    )

    new_lines = []

    for module in sorted(
        missing_by_module
    ):
        classes = sorted(
            missing_by_module[
                module
            ],
            key=lambda name:
                STATUS_BY_EXC[
                    name
                ],
        )

        new_lines.append(
            f"from {module} import "
            + ", ".join(classes)
        )

    lines[
        insert_at:
        insert_at
    ] = new_lines

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

    required_imports = {
        class_name:
            EXC_BY_STATUS[
                STATUS_BY_EXC[
                    class_name
                ]
            ][1]
        for class_name
        in required_classes
    }

    patched = add_router_imports(
        text,
        required_imports,
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
                "Função de router ausente: "
                f"{fn_name}"
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
            "alterado: "
            f"{differences}"
        )

    return result


def ensure_application_exception_files():
    """
    Retorna informações para possível rollback.
    Não sobrescreve conteúdo existente incompatível.
    """
    created_dir = False
    created_init = False
    created_exceptions = False

    if not APPLICATION_DIR.exists():
        APPLICATION_DIR.mkdir(
            parents=True,
            exist_ok=False,
        )
        created_dir = True

    if not APPLICATION_INIT.exists():
        APPLICATION_INIT.write_text(
            "",
            encoding="utf-8",
        )
        created_init = True

    expected_text = (
        'class ApplicationError(Exception):\n'
        '    """Base para erros da camada de aplicação."""\n'
        '    pass\n'
        '\n'
        '\n'
        'class TechnicalConfigurationError(ApplicationError):\n'
        '    """Falha técnica/configuração que impede execução segura."""\n'
        '    pass\n'
    )

    if not APPLICATION_EXCEPTIONS.exists():
        APPLICATION_EXCEPTIONS.write_text(
            expected_text,
            encoding="utf-8",
        )
        created_exceptions = True

    else:
        existing = read_text(
            APPLICATION_EXCEPTIONS
        )

        if (
            "class TechnicalConfigurationError("
            not in existing
        ):
            raise RuntimeError(
                "application/exceptions.py "
                "já existe sem "
                "TechnicalConfigurationError. "
                "Nenhum append automático "
                "será feito."
            )

    py_compile.compile(
        str(APPLICATION_EXCEPTIONS),
        doraise=True,
    )

    return {
        "created_dir":
            created_dir,
        "created_init":
            created_init,
        "created_exceptions":
            created_exceptions,
    }


def remove_created_application_files(
    creation_state,
):
    if creation_state.get(
        "created_exceptions"
    ):
        if APPLICATION_EXCEPTIONS.exists():
            APPLICATION_EXCEPTIONS.unlink()

    if creation_state.get(
        "created_init"
    ):
        if APPLICATION_INIT.exists():
            APPLICATION_INIT.unlink()

    if creation_state.get(
        "created_dir"
    ):
        try:
            APPLICATION_DIR.rmdir()
        except OSError:
            pass


def patch_service(text):
    state, diag = (
        service_state(
            text
        )
    )

    if state != "LEGADO":
        raise RuntimeError(
            "Service não está legado: "
            f"{state} / {diag}"
        )

    http = (
        http_raises_by_function(
            text
        )
    )

    replacements = []

    required_imports = {}

    for fn_name, items in (
        http.items()
    ):
        for item in items:
            status = item[
                "status"
            ]

            (
                exc_name,
                module,
            ) = EXC_BY_STATUS[
                status
            ]

            required_imports[
                exc_name
            ] = module

            node = item[
                "node"
            ]

            indent = (
                " "
                * node.col_offset
            )

            replacement = (
                f"{indent}raise {exc_name}(\n"
                f"{indent}    {item['detail']}\n"
                f"{indent})"
            )

            replacements.append(
                (
                    node.lineno,
                    node.end_lineno,
                    replacement,
                )
            )

    if len(replacements) != 4:
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

    tree = parse(
        result,
        "service após raises",
    )

    fastapi_imports = [
        node
        for node in tree.body
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
        )
    ]

    if len(fastapi_imports) != 1:
        raise RuntimeError(
            "Import FastAPI legado "
            "não encontrado no formato "
            "esperado."
        )

    import_node = (
        fastapi_imports[0]
    )

    import_lines = []

    by_module = {}

    for class_name, module in (
        required_imports.items()
    ):
        by_module.setdefault(
            module,
            []
        ).append(
            class_name
        )

    for module in sorted(
        by_module
    ):
        classes = sorted(
            by_module[module],
            key=lambda name:
                STATUS_BY_EXC[
                    name
                ],
        )

        import_lines.append(
            f"from {module} import "
            + ", ".join(classes)
        )

    result_lines = (
        result.splitlines()
    )

    result_lines[
        import_node.lineno - 1:
        import_node.end_lineno
    ] = import_lines

    final = "\n".join(
        result_lines
    )

    if text.endswith("\n"):
        final += "\n"

    state2, diag2 = (
        service_state(
            final
        )
    )

    if state2 != "MIGRADO":
        raise RuntimeError(
            "Service pós-patch "
            f"inválido: {diag2}"
        )

    return (
        final,
        sorted(
            required_imports,
            key=lambda name:
                STATUS_BY_EXC[
                    name
                ],
        ),
    )


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
            f"[ERRO] Arquivo ausente: {path}"
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
            "[ERRO] Hierarquia de domínio "
            f"incompleta: {token}"
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
        "[ERRO] Fase 10L não "
        "reconhecida em "
        "services/analise_recontagem.py."
    )

print(
    "      [OK] Fase 10L reconhecida."
)


print(
    "[1/15] Analisando baseline 10M..."
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
    f"      HTTP por status: "
    f"{s_diag.get('status_counts', {})}"
)

print(
    f"      HTTP por função: "
    f"{s_diag.get('function_counts', s_diag.get('http', {}))}"
)

if s_state == "DESCONHECIDO":
    raise SystemExit(
        "[ERRO] Baseline de "
        "analise_recontagem_rotativo "
        f"desconhecida: {s_diag}"
    )


print(
    "[2/15] Validando/criando exceção técnica..."
)

creation_state = {
    "created_dir": False,
    "created_init": False,
    "created_exceptions": False,
}

try:
    creation_state = (
        ensure_application_exception_files()
    )

    app_text = read_text(
        APPLICATION_EXCEPTIONS
    )

    if (
        "class TechnicalConfigurationError("
        not in app_text
    ):
        raise RuntimeError(
            "TechnicalConfigurationError "
            "não encontrada."
        )

    print(
        "      [OK] "
        "TechnicalConfigurationError "
        "disponível."
    )

except Exception:
    remove_created_application_files(
        creation_state
    )
    raise


print(
    "[3/15] Indexando módulos de produção..."
)

try:
    modules = (
        build_project_index()
    )
except Exception:
    remove_created_application_files(
        creation_state
    )
    raise

print(
    f"      módulos analisados: "
    f"{len(modules)}"
)

if TARGET_MODULE not in modules:
    remove_created_application_files(
        creation_state
    )
    raise SystemExit(
        f"[ERRO] Módulo "
        f"{TARGET_MODULE} "
        "não indexado."
    )

for module_name, info in (
    modules.items()
):
    if info[
        "unsupported_target_imports"
    ]:
        remove_created_application_files(
            creation_state
        )

        raise SystemExit(
            "[ERRO] Import de módulo "
            "não suportado em "
            f"{info['path'].relative_to(ROOT)}: "
            f"{info['unsupported_target_imports']}. "
            "Nenhum arquivo de produção "
            "foi alterado."
        )

print(
    "      [OK] imports compatíveis."
)


print(
    "[4/15] Construindo grafo de chamadas..."
)

_, reverse = build_call_graph(
    modules
)

seeds = all_target_nodes(
    service_text
)

affected = (
    transitive_callers(
        reverse,
        seeds,
    )
)

print(
    f"      seeds internos: "
    f"{len(seeds)}"
)

for node in sorted(
    seeds
):
    print(
        f"        - "
        f"{node[0]}.{node[1]}"
    )

print(
    f"      funções afetadas totais: "
    f"{len(affected)}"
)


print(
    "[5/15] Classificando caminhos..."
)

affected_services = sorted(
    node
    for node in affected
    if (
        node[0].startswith(
            "services."
        )
        and
        node[0]
        != TARGET_MODULE
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
    remove_created_application_files(
        creation_state
    )

    for node in unexpected:
        print(
            f"      [BLOQUEIO] "
            f"{node[0]}.{node[1]}"
        )

    raise SystemExit(
        "[ERRO] Caller fora de "
        "services/routers. "
        "Nenhum arquivo de produção "
        "foi alterado."
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
        remove_created_application_files(
            creation_state
        )

        print(
            f"      [BLOQUEIO] "
            f"{module_name}.{fn_name} "
            "captura Exception e gera "
            "HTTPException."
        )

        raise SystemExit(
            "[ERRO] Exceção semântica/"
            "técnica seria embrulhada "
            "por service intermediário. "
            "Nenhum arquivo de produção "
            "foi alterado."
        )

    print(
        f"      [OK] "
        f"{module_name}.{fn_name}"
    )


if not affected_routers:
    remove_created_application_files(
        creation_state
    )

    raise SystemExit(
        "[ERRO] Nenhuma fronteira HTTP "
        "foi alcançada pelo grafo."
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
    "TechnicalConfigurationError",
]


print(
    "[8/15] Validando handlers atuais..."
)

try:
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

except Exception:
    remove_created_application_files(
        creation_state
    )
    raise


if s_state == "MIGRADO":
    print(
        "[9/15] Fase 10M já aplicada."
    )
    print(
        "      [OK] service e "
        "fronteiras HTTP consistentes."
    )
    raise SystemExit(0)


print(
    "[9/15] Confirmando perfil 2x400 + 1x404 + 1x500..."
)

http = (
    http_raises_by_function(
        service_text
    )
)

for fn_name in sorted(
    http
):
    for item in (
        http[fn_name]
    ):
        status = item[
            "status"
        ]

        exc_name = (
            EXC_BY_STATUS[
                status
            ][0]
        )

        print(
            f"      {fn_name}: "
            f"HTTP {status} -> "
            f"{exc_name}"
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
            + "_backup_fase10m_"
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
        "analise_recontagem_rotativo.py..."
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
        "      [OK] "
        "4 HTTPException migrados."
    )

    print(
        "      [OK] "
        "FastAPI removido do service."
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
            read_text(
                path
            )
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
        "[13/15] Revalidando service..."
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

    print(
        "      [OK] service sem "
        "FastAPI/HTTPException."
    )


    print(
        "[14/15] Revalidando grafo e handlers..."
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
            final_reverse,
            seeds,
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
                required_classes,
                require_all=True,
            )

    print(
        "      [OK] fronteiras "
        "traduzem 400/404/500."
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
                "exceções."
            )

    print(
        "      [OK] propagação "
        "permanece segura."
    )


except Exception:
    print()
    print(
        "[ERRO] Falha durante Fase 10M."
    )
    print(
        "[INFO] Restaurando arquivos..."
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

    remove_created_application_files(
        creation_state
    )

    print(
        "[OK] Estado anterior restaurado."
    )

    raise


print()
print(
    "[OK] Fase 10M aplicada."
)
print(
    "[OK] services/analise_recontagem_rotativo.py "
    "desacoplado de FastAPI."
)
print(
    "[OK] HTTP 400 -> BusinessRuleViolation."
)
print(
    "[OK] HTTP 404 -> NotFoundError."
)
print(
    "[OK] HTTP 500 técnico -> "
    "TechnicalConfigurationError."
)
print(
    "[OK] falha técnica não foi misturada "
    "com DomainError."
)
print(
    "[OK] callers transitivos rastreados."
)
print(
    "[OK] fronteiras HTTP preservam 400/404/500."
)
print(
    "[OK] rollback/log dos routers preservado "
    "por caminho."
)
print(
    "[OK] SQL e regras ROTATIVO não alterados."
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
