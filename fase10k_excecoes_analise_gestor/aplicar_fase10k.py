
"""
FASE 10K - DESACOPLAMENTO HTTP DE analise_gestor

Escopo principal:
- services/analise_gestor.py
  - analisar_inventario_gestor()

Baseline esperado:
- 3 raise HTTPException
- 1 x HTTP 404
- 2 x HTTP 400

Mapeamento:
- 400 -> BusinessRuleViolation
- 404 -> NotFoundError

Diferencial:
analisar_inventario_gestor também pode ser consumida por outros
services (por exemplo, o fluxo de rodadas OFICIAL).

Por isso o instalador:
1. constrói um grafo de chamadas entre módulos de produção;
2. parte de services.analise_gestor.analisar_inventario_gestor;
3. encontra callers transitivos;
4. identifica todas as funções de router afetadas;
5. verifica se algum service intermediário captura Exception e
   converte o erro em HTTPException/500;
6. bloqueia qualquer caminho não resolvido;
7. adapta todas as fronteiras HTTP reconhecidas.

Nos routers, os novos handlers copiam o mesmo prefixo operacional
do `except HTTPException` atual (rollback/log, se houver), preservando
a semântica transacional por caminho.

Não altera:
- SQL
- regras da análise gerencial
- services consumidores
- commit
- abertura/fechamento de conexão
- rotas
- respostas de sucesso

Execute:
python .\fase10k_excecoes_analise_gestor\aplicar_fase10k.py
"""

from pathlib import Path
from datetime import datetime
import ast
import py_compile
import shutil

ROOT = Path.cwd()

SERVICE = ROOT / "services" / "analise_gestor.py"
DOMAIN = ROOT / "domain" / "exceptions.py"
PREV = ROOT / "services" / "consultas_operacionais.py"

TARGET_MODULE = "services.analise_gestor"
TARGET_FUNCTION = "analisar_inventario_gestor"
TARGET_NODE = (TARGET_MODULE, TARGET_FUNCTION)

EXC_BY_STATUS = {
    400: "BusinessRuleViolation",
    404: "NotFoundError",
}

STATUS_BY_EXC = {
    value: key
    for key, value in EXC_BY_STATUS.items()
}

EXPECTED_STATUS_COUNTS = {
    400: 2,
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
        and rel.parts[0].lower()
        in {"tests", "tests_e2e", "test"}
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
    rel = path.relative_to(ROOT).with_suffix("")
    return ".".join(rel.parts)


def package_of_module(module_name):
    parts = module_name.split(".")
    return parts[:-1]


def resolve_import_module(current_module, node):
    module = node.module or ""

    if node.level == 0:
        return module

    package = package_of_module(current_module)

    # level=1 => pacote atual
    ascend = node.level - 1

    if ascend > len(package):
        return None

    base = package[: len(package) - ascend]

    if module:
        base += module.split(".")

    return ".".join(base)


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


def top_import_map(tree, module_name):
    """
    local_name -> (module, original_name)
    """
    result = {}

    for node in tree.body:
        if not isinstance(node, ast.ImportFrom):
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
    """
    Bloqueia `import services.analise_gestor` porque o grafo desta fase
    resolve deliberadamente apenas `from ... import função`.
    """
    result = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Import):
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
            and isinstance(node.func, ast.Name)
        ):
            result.add(node.func.id)

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

        module_name = module_name_from_path(path)

        modules[module_name] = {
            "path": path,
            "text": text,
            "tree": tree,
            "functions": top_functions(tree),
            "imports": top_import_map(
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
            for path, exc in syntax_errors
        )

        raise RuntimeError(
            "Arquivos de produção com sintaxe inválida: "
            + details
        )

    return modules


def build_call_graph(modules):
    graph = {}
    reverse = {}

    for module_name, info in modules.items():
        local_functions = set(
            info["functions"]
        )

        imports = info["imports"]

        for fn_name, fn in info["functions"].items():
            caller = (
                module_name,
                fn_name,
            )

            graph.setdefault(
                caller,
                set(),
            )

            for called_name in call_names(fn):
                callee = None

                if called_name in local_functions:
                    callee = (
                        module_name,
                        called_name,
                    )

                elif called_name in imports:
                    imported_module, imported_name = (
                        imports[
                            called_name
                        ]
                    )

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

            affected.add(
                caller
            )

            frontier.append(
                caller
            )

    return affected


def target_http_raises(text):
    tree = parse(
        text,
        "services/analise_gestor.py",
    )

    functions = top_functions(tree)

    fn = functions.get(
        TARGET_FUNCTION
    )

    if fn is None:
        raise RuntimeError(
            f"{TARGET_FUNCTION} não encontrada."
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

        status = None
        detail = None

        for kw in node.exc.keywords:
            if kw.arg == "status_code":
                status = kw.value

            elif kw.arg == "detail":
                detail = kw.value

        if status is None or detail is None:
            raise RuntimeError(
                "HTTPException sem status/detail."
            )

        if not (
            isinstance(status, ast.Constant)
            and isinstance(status.value, int)
        ):
            raise RuntimeError(
                "status_code dinâmico não suportado."
            )

        detail_source = ast.get_source_segment(
            text,
            detail,
        )

        if not detail_source:
            raise RuntimeError(
                "detail não recuperado via AST."
            )

        result.append(
            {
                "node": node,
                "status": status.value,
                "detail": detail_source,
            }
        )

    return result


def target_domain_raises(text):
    tree = parse(
        text,
        "services/analise_gestor.py",
    )

    functions = top_functions(tree)
    fn = functions.get(
        TARGET_FUNCTION
    )

    if fn is None:
        raise RuntimeError(
            f"{TARGET_FUNCTION} não encontrada."
        )

    result = []

    for node in ast.walk(fn):
        if not isinstance(node, ast.Raise):
            continue

        if node.exc is None:
            continue

        name = raised_name(node.exc)

        if name in set(
            EXC_BY_STATUS.values()
        ):
            result.append(name)

    return result


def total_http_raises_file(text):
    tree = parse(
        text,
        "services/analise_gestor.py",
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
        "services/analise_gestor.py",
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
    http_raises = target_http_raises(text)
    domain_raises = target_domain_raises(text)

    total_http = total_http_raises_file(text)
    total_handlers = total_http_handlers_file(text)

    statuses = [
        item["status"]
        for item in http_raises
    ]

    status_counts = {
        status: statuses.count(status)
        for status in set(statuses)
    }

    has_fastapi = (
        "from fastapi import HTTPException"
        in text
    )

    if (
        len(http_raises) == 3
        and
        len(domain_raises) == 0
        and
        total_http == 3
        and
        total_handlers == 0
        and
        status_counts == EXPECTED_STATUS_COUNTS
        and
        has_fastapi
    ):
        return "LEGADO", {
            "statuses": statuses,
            "domain": domain_raises,
            "total_http": total_http,
        }

    expected_domain = sorted(
        [
            "BusinessRuleViolation",
            "BusinessRuleViolation",
            "NotFoundError",
        ]
    )

    if (
        len(http_raises) == 0
        and
        sorted(domain_raises) == expected_domain
        and
        total_http == 0
        and
        total_handlers == 0
        and
        "fastapi" not in text.lower()
        and
        "starlette" not in text.lower()
    ):
        return "MIGRADO", {
            "statuses": [],
            "domain": domain_raises,
            "total_http": 0,
        }

    return "DESCONHECIDO", {
        "statuses": statuses,
        "domain": domain_raises,
        "total_http": total_http,
        "total_handlers": total_handlers,
        "has_fastapi_import": has_fastapi,
    }


def has_generic_http_wrapper(fn):
    """
    Bloqueia service intermediário que capturaria DomainError
    como Exception e o embrulharia em HTTPException.
    """
    for handler in [
        node
        for node in ast.walk(fn)
        if isinstance(node, ast.ExceptHandler)
    ]:
        if handler_name(handler) != "Exception":
            continue

        for inner in ast.walk(handler):
            if not isinstance(inner, ast.Raise):
                continue

            if (
                isinstance(inner.exc, ast.Call)
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
            isinstance(node, ast.ExceptHandler)
            and
            handler_name(node)
            == "HTTPException"
        )
    ]

    if len(handlers) != 1:
        raise RuntimeError(
            f"{fn.name}: esperado exatamente "
            f"1 except HTTPException, encontrado "
            f"{len(handlers)}."
        )

    return handlers[0]


def handler_prefix_lines(text, handler):
    """
    Retorna as linhas do corpo do except HTTPException,
    excluindo o último `raise` nu.

    Isso preserva rollback/log antes de traduzir a nova exceção.
    """
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
            "except HTTPException não termina "
            "com `raise` nu; baseline não segura."
        )

    prefix_nodes = handler.body[:-1]

    if not prefix_nodes:
        return []

    lines = text.splitlines()

    start = prefix_nodes[0].lineno
    end = prefix_nodes[-1].end_lineno

    return lines[
        start - 1:
        end
    ]


def handler_http_status(handler):
    for node in ast.walk(handler):
        if not isinstance(node, ast.Raise):
            continue

        if not (
            isinstance(node.exc, ast.Call)
            and
            raised_name(node.exc)
            == "HTTPException"
        ):
            continue

        for kw in node.exc.keywords:
            if (
                kw.arg == "status_code"
                and
                isinstance(kw.value, ast.Constant)
                and
                isinstance(kw.value.value, int)
            ):
                return kw.value.value

    return None


def router_existing_semantic_handler(fn, exc_name):
    handlers = [
        node
        for node in ast.walk(fn)
        if (
            isinstance(node, ast.ExceptHandler)
            and
            handler_name(node)
            == exc_name
        )
    ]

    if len(handlers) > 1:
        raise RuntimeError(
            f"{fn.name}: handler duplicado "
            f"para {exc_name}."
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
    http_handler = router_http_handler(
        fn
    )

    prefix = handler_prefix_lines(
        text,
        http_handler,
    )

    for exc_name in required_classes:
        existing = router_existing_semantic_handler(
            fn,
            exc_name,
        )

        if existing is None:
            if require_all:
                raise RuntimeError(
                    f"{fn.name}: handler "
                    f"{exc_name} ausente."
                )

            continue

        expected_status = STATUS_BY_EXC[
            exc_name
        ]

        actual_status = handler_http_status(
            existing
        )

        if actual_status != expected_status:
            raise RuntimeError(
                f"{fn.name}: {exc_name} traduz "
                f"HTTP {actual_status}, esperado "
                f"{expected_status}."
            )

    return (
        http_handler,
        prefix,
    )


def add_domain_imports(
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
            isinstance(node, ast.ImportFrom)
            and
            (node.module or "")
            == "domain.exceptions"
        ):
            for alias in node.names:
                existing.add(
                    alias.name
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
            isinstance(node, ast.ImportFrom)
            and
            (node.module or "")
            == "fastapi"
        ):
            fastapi_import = node
            break

    if fastapi_import is None:
        raise RuntimeError(
            "Router afetado sem import FastAPI reconhecido."
        )

    lines = text.splitlines()

    lines.insert(
        fastapi_import.end_lineno,
        (
            "from domain.exceptions import "
            + ", ".join(
                missing
            )
        ),
    )

    result = "\n".join(lines)

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
            f"{exc_name} as erro:"
        ),
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
        token: text.count(token)
        for token in PROTECTED_EXACT_TOKENS
    }

    patched = add_domain_imports(
        text,
        required_classes,
    )

    tree = parse(
        patched,
        "router após import",
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
                f"Função de router ausente: {fn_name}"
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

        for exc_name in required_classes:
            existing = router_existing_semantic_handler(
                fn,
                exc_name,
            )

            if existing is not None:
                continue

            blocks.extend(
                build_translation_handler(
                    exc_name=exc_name,
                    status=STATUS_BY_EXC[
                        exc_name
                    ],
                    http_handler=http_handler,
                    prefix_lines=prefix_lines,
                )
            )

        if not blocks:
            continue

        insertions.append(
            (
                http_handler.lineno,
                blocks,
            )
        )

    lines = patched.splitlines()

    for line_no, block_lines in sorted(
        insertions,
        key=lambda item: item[0],
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

    # Validação final dos handlers.
    final_tree = parse(
        result,
        "router final",
    )

    final_functions = top_functions(
        final_tree
    )

    for fn_name in affected_function_names:
        validate_router_function(
            result,
            final_functions[
                fn_name
            ],
            required_classes,
            require_all=True,
        )

    after_exact = {
        token: result.count(token)
        for token in PROTECTED_EXACT_TOKENS
    }

    if before_exact != after_exact:
        differences = {
            token: (
                before_exact[token],
                after_exact[token],
            )
            for token in PROTECTED_EXACT_TOKENS
            if (
                before_exact[token]
                != after_exact[token]
            )
        }

        raise RuntimeError(
            "Commit/conexão foi alterado: "
            f"{differences}"
        )

    return result


def patch_service(text):
    state, diag = service_state(
        text
    )

    if state != "LEGADO":
        raise RuntimeError(
            f"Service não está legado: "
            f"{state} / {diag}"
        )

    raises = target_http_raises(
        text
    )

    if len(raises) != 3:
        raise RuntimeError(
            "Esperados 3 HTTPException."
        )

    lines = text.splitlines()
    replacements = []

    for item in raises:
        status = item[
            "status"
        ]

        if status not in EXC_BY_STATUS:
            raise RuntimeError(
                f"Status {status} fora do escopo."
            )

        exc_name = EXC_BY_STATUS[
            status
        ]

        node = item[
            "node"
        ]

        indent = (
            " " * node.col_offset
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

    replacements.sort(
        key=lambda item: item[0]
    )

    out = []
    current = 1

    for start, end, replacement in replacements:
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

    # Substitui o único import HTTP pelo import de domínio.
    if (
        result.count(
            "from fastapi import HTTPException"
        )
        != 1
    ):
        raise RuntimeError(
            "Import FastAPI legado não está "
            "no formato esperado."
        )

    result = result.replace(
        "from fastapi import HTTPException",
        (
            "from domain.exceptions import "
            "BusinessRuleViolation, NotFoundError"
        ),
        1,
    )

    state2, diag2 = service_state(
        result
    )

    if state2 != "MIGRADO":
        raise RuntimeError(
            "Service pós-patch inválido: "
            f"{diag2}"
        )

    return result


print(
    "[0/14] Validando arquivos e pré-requisitos..."
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
            "[ERRO] Hierarquia de domínio incompleta: "
            f"{token}"
        )

prev_text = read_text(
    PREV
)

if (
    "fastapi" in prev_text.lower()
    or
    "HTTPException" in prev_text
):
    raise SystemExit(
        "[ERRO] Fase 10J não reconhecida em "
        "services/consultas_operacionais.py."
    )

print(
    "      [OK] Fase 10J reconhecida."
)


print(
    "[1/14] Analisando baseline de analise_gestor..."
)

service_text = read_text(
    SERVICE
)

s_state, s_diag = service_state(
    service_text
)

print(
    f"      Estado: {s_state}"
)
print(
    f"      statuses: {s_diag.get('statuses', [])}"
)
print(
    f"      domain: {s_diag.get('domain', [])}"
)
print(
    f"      total HTTP raises: "
    f"{s_diag.get('total_http', 0)}"
)

if s_state == "DESCONHECIDO":
    raise SystemExit(
        "[ERRO] Baseline de analise_gestor "
        f"desconhecida: {s_diag}"
    )


print(
    "[2/14] Indexando módulos de produção..."
)

modules = build_project_index()

print(
    f"      módulos analisados: {len(modules)}"
)

if TARGET_MODULE not in modules:
    raise SystemExit(
        f"[ERRO] Módulo {TARGET_MODULE} não indexado."
    )

for module_name, info in modules.items():
    if info[
        "unsupported_target_imports"
    ]:
        details = info[
            "unsupported_target_imports"
        ]

        raise SystemExit(
            "[ERRO] Import de módulo não suportado "
            f"em {info['path'].relative_to(ROOT)}: "
            f"{details}. Use `from ... import função` "
            "ou revise manualmente."
        )

print(
    "      [OK] imports compatíveis com análise estática."
)


print(
    "[3/14] Construindo grafo de chamadas..."
)

graph, reverse = build_call_graph(
    modules
)

affected = transitive_callers(
    reverse
)

print(
    f"      funções afetadas: {len(affected)}"
)

for module_name, fn_name in sorted(
    affected
):
    print(
        f"      - {module_name}.{fn_name}"
    )


print(
    "[4/14] Classificando caminhos afetados..."
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
    if node[
        0
    ].startswith(
        "routers."
    )
)

unexpected_layers = sorted(
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

if unexpected_layers:
    print(
        "      [BLOQUEIO] callers fora de "
        "services/routers:"
    )

    for node in unexpected_layers:
        print(
            f"        - {node[0]}.{node[1]}"
        )

    raise SystemExit(
        "[ERRO] Caminho fora das camadas "
        "mapeadas. Nenhum arquivo alterado."
    )


print(
    "[5/14] Verificando services intermediários..."
)

for module_name, fn_name in affected_services:
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
            "captura Exception e gera HTTPException."
        )

        raise SystemExit(
            "[ERRO] DomainError seria embrulhado "
            "por um service intermediário. "
            "Nenhum arquivo alterado."
        )

    print(
        f"      [OK] "
        f"{module_name}.{fn_name} "
        "permite propagação."
    )


if not affected_routers:
    raise SystemExit(
        "[ERRO] Nenhuma fronteira HTTP foi "
        "alcançada pelo grafo."
    )


print(
    "[6/14] Agrupando fronteiras HTTP..."
)

router_groups = {}

for module_name, fn_name in affected_routers:
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
    "[7/14] Validando handlers atuais dos routers..."
)

for module_name, function_names in router_groups.items():
    info = modules[
        module_name
    ]

    for fn_name in function_names:
        fn = info[
            "functions"
        ][
            fn_name
        ]

        validate_router_function(
            info["text"],
            fn,
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
        "[8/14] Fase 10K já aplicada."
    )
    print(
        "      [OK] service e fronteiras "
        "HTTP já estão consistentes."
    )
    raise SystemExit(0)


print(
    "[8/14] Confirmando 1x404 + 2x400..."
)

raises = target_http_raises(
    service_text
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
            f"[ERRO] HTTP {status} fora do escopo."
        )

    counts[
        status
    ] += 1

    print(
        f"      HTTP {status} -> "
        f"{EXC_BY_STATUS[status]}"
    )

if counts != EXPECTED_STATUS_COUNTS:
    raise SystemExit(
        "[ERRO] Perfil HTTP diferente do esperado: "
        f"{counts}"
    )

print(
    "      [OK] perfil confirmado."
)


print(
    "[9/14] Preparando backups..."
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
    ][
        "path"
    ]

backups = {}

for module_name, path in paths_to_edit.items():
    backup = (
        path.parent
        / (
            path.stem
            + "_backup_fase10k_"
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
        f"      {path.relative_to(ROOT)} "
        f"-> {backup.name}"
    )


try:
    print(
        "[10/14] Migrando analise_gestor.py..."
    )

    patched_service = patch_service(
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
        "      [OK] 3 HTTPException -> "
        "exceções semânticas."
    )
    print(
        "      [OK] import FastAPI removido."
    )


    print(
        "[11/14] Adaptando fronteiras HTTP..."
    )

    edited_routers = {}

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

        patched_router = patch_router_file(
            original_text,
            affected_function_names=
                function_names,
            required_classes=
                required_classes,
        )

        path.write_text(
            patched_router,
            encoding="utf-8",
        )

        py_compile.compile(
            str(path),
            doraise=True,
        )

        edited_routers[
            module_name
        ] = patched_router

        print(
            f"      [OK] {module_name}: "
            f"{sorted(function_names)}"
        )


    print(
        "[12/14] Revalidando service..."
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
        "      [OK] analise_gestor sem "
        "FastAPI/HTTPException."
    )


    print(
        "[13/14] Revalidando grafo e handlers..."
    )

    final_modules = build_project_index()
    _, final_reverse = build_call_graph(
        final_modules
    )

    final_affected = transitive_callers(
        final_reverse
    )

    if final_affected != affected:
        raise RuntimeError(
            "Grafo de consumidores mudou durante "
            "a migração."
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
        "      [OK] todas as fronteiras "
        "traduzem 400/404."
    )


    print(
        "[14/14] Validando services intermediários..."
    )

    for module_name, fn_name in affected_services:
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
                f"{module_name}.{fn_name} passou "
                "a bloquear DomainError."
            )

    print(
        "      [OK] propagação transitive "
        "permanece segura."
    )


except Exception:
    print()
    print(
        "[ERRO] Falha durante Fase 10K."
    )
    print(
        "[INFO] Restaurando todos os arquivos..."
    )

    for module_name, path in paths_to_edit.items():
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

    raise


print()
print(
    "[OK] Fase 10K aplicada."
)
print(
    "[OK] services/analise_gestor.py "
    "desacoplado de FastAPI."
)
print(
    "[OK] 3 HTTPException migrados:"
)
print(
    "     2 -> BusinessRuleViolation / HTTP 400"
)
print(
    "     1 -> NotFoundError / HTTP 404"
)
print(
    "[OK] todos os callers transitivos foram "
    "rastreados."
)
print(
    "[OK] todas as fronteiras HTTP reconhecidas "
    "foram adaptadas."
)
print(
    "[OK] rollback/log dos routers foi preservado "
    "por caminho."
)
print(
    "[OK] services intermediários não foram alterados."
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
