
"""
FASE 10T - LOCALIZAÇÕES DE RECONTAGEM

Alvo:
- services/rodadas/localizacoes.py
- sincronizar_localizacoes_recontagem()

Baseline esperado:
- exatamente 1 raise HTTPException no módulo
- HTTP 404
- detail:
  "Rodada não encontrada para este inventário."

Mapeamento:
- HTTP 404 -> domain.exceptions.NotFoundError

Ao final:
- 0 raise HTTPException no módulo
- 0 except HTTPException no módulo
- 0 import FastAPI/Starlette no módulo

O instalador:
- valida o erro único e seu detail;
- rastreia callers transitivos;
- resolve imports, aliases e facades/reexports;
- adapta routers diretos e indiretos;
- reutiliza handler NotFoundError já existente;
- replica rollback/log do except HTTPException;
- bloqueia wrappers inseguros em services;
- preserva SQL, geração de localizações, UoW, commit e conexão;
- auto-restaura todos os arquivos em caso de falha.

Execute:
python .\fase10t_excecoes_localizacoes_rodadas\aplicar_fase10t.py
"""

from pathlib import Path
from datetime import datetime
import ast
import py_compile
import shutil

ROOT = Path.cwd()

SERVICE = ROOT / "services" / "rodadas" / "localizacoes.py"
DOMAIN = ROOT / "domain" / "exceptions.py"
PREV = ROOT / "services" / "rodadas" / "lifecycle.py"

TARGET_MODULE = "services.rodadas.localizacoes"
TARGET_FUNCTION = "sincronizar_localizacoes_recontagem"
TARGET_NODE = (TARGET_MODULE, TARGET_FUNCTION)

EXPECTED_STATUS = 404
EXPECTED_DETAIL = "Rodada não encontrada para este inventário."

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
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def get_target_function(text):
    tree = parse(text, "services/rodadas/localizacoes.py")
    fn = top_functions(tree).get(TARGET_FUNCTION)

    if fn is None:
        raise RuntimeError(
            f"Função ausente: {TARGET_FUNCTION}"
        )

    return fn


def target_http_raises(text):
    fn = get_target_function(text)
    result = []

    for node in ast.walk(fn):
        if not isinstance(node, ast.Raise):
            continue

        if node.exc is None:
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
            raise RuntimeError(
                "HTTPException alvo sem status/detail."
            )

        if not (
            isinstance(status_node, ast.Constant)
            and isinstance(status_node.value, int)
        ):
            raise RuntimeError(
                "status_code dinâmico não suportado."
            )

        detail_source = ast.get_source_segment(
            text,
            detail_node,
        )

        if not detail_source:
            raise RuntimeError(
                "detail não recuperado via AST."
            )

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

    return result


def target_semantic_raises(text):
    fn = get_target_function(text)
    result = []

    for node in ast.walk(fn):
        if not isinstance(node, ast.Raise):
            continue

        if node.exc is None:
            continue

        if raised_name(node.exc) == "NotFoundError":
            result.append("NotFoundError")

    return result


def all_http_raise_locations(text):
    tree = parse(
        text,
        "services/rodadas/localizacoes.py",
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
        "services/rodadas/localizacoes.py",
    )

    raises = 0
    handlers = 0
    loads = 0

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

        if (
            isinstance(node, ast.Name)
            and node.id == "HTTPException"
            and isinstance(node.ctx, ast.Load)
        ):
            loads += 1

    return {
        "raises": raises,
        "handlers": handlers,
        "loads": loads,
    }


def fastapi_starlette_imports(text):
    tree = parse(
        text,
        "services/rodadas/localizacoes.py",
    )

    result = []

    for node in tree.body:
        if not isinstance(node, ast.ImportFrom):
            continue

        module = node.module or ""

        if (
            module in {"fastapi", "starlette"}
            or module.startswith("fastapi.")
            or module.startswith("starlette.")
        ):
            result.append(node)

    return result


def service_state(text):
    target = target_http_raises(text)
    semantic = target_semantic_raises(text)
    locations = all_http_raise_locations(text)
    usage = total_http_usage(text)
    imports = fastapi_starlette_imports(text)

    if (
        len(target) == 1
        and target[0]["status"] == EXPECTED_STATUS
        and target[0]["detail_value"] == EXPECTED_DETAIL
        and semantic == []
        and locations == {TARGET_FUNCTION: 1}
        and usage["raises"] == 1
        and usage["handlers"] == 0
        and len(imports) == 1
        and (imports[0].module or "") == "fastapi"
        and [alias.name for alias in imports[0].names]
        == ["HTTPException"]
    ):
        return "LEGADO", {
            "status": target[0]["status"],
            "detail": target[0]["detail_value"],
            "locations": locations,
            "usage": usage,
        }

    if (
        len(target) == 0
        and semantic == ["NotFoundError"]
        and not locations
        and usage["raises"] == 0
        and usage["handlers"] == 0
        and usage["loads"] == 0
        and len(imports) == 0
    ):
        return "MIGRADO", {
            "semantic": semantic,
            "usage": usage,
        }

    return "DESCONHECIDO", {
        "target_count": len(target),
        "target_statuses": [
            item["status"]
            for item in target
        ],
        "target_details": [
            item["detail_value"]
            for item in target
        ],
        "semantic": semantic,
        "locations": locations,
        "usage": usage,
        "imports": [
            (
                node.module,
                [
                    alias.name
                    for alias in node.names
                ],
            )
            for node in imports
        ],
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

    package = package_of_module(current_module)
    ascend = node.level - 1

    if ascend > len(package):
        return None

    base = package[
        :len(package) - ascend
    ]

    if module:
        base += module.split(".")

    return ".".join(base)


def top_import_map(tree, module_name):
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
                alias.asname or alias.name
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
                and isinstance(node.targets[0], ast.Name)
                and isinstance(node.value, ast.Name)
            ):
                result[
                    node.targets[0].id
                ] = node.value.id

        elif isinstance(node, ast.AnnAssign):
            if (
                isinstance(node.target, ast.Name)
                and isinstance(node.value, ast.Name)
            ):
                result[
                    node.target.id
                ] = node.value.id

    return result


def unsupported_target_module_imports(tree):
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
            and isinstance(
                node.func,
                ast.Name,
            )
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

        module_name = (
            module_name_from_path(path)
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

    info = modules.get(
        module_name
    )

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
        ) = imports[symbol_name]

        return resolve_symbol(
            modules,
            imported_module,
            imported_name,
            visited,
        )

    return None


def build_call_graph(modules):
    reverse = {}

    for module_name, info in modules.items():
        for fn_name, fn in (
            info["functions"].items()
        ):
            caller = (
                module_name,
                fn_name,
            )

            for called_name in call_names(fn):
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
    affected = {TARGET_NODE}
    frontier = [TARGET_NODE]

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
                and raised_name(
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
            and handler_name(node)
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
            and raised_name(
                node.exc
            )
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


def existing_not_found_handler(fn):
    handlers = [
        node
        for node in ast.walk(fn)
        if (
            isinstance(
                node,
                ast.ExceptHandler,
            )
            and handler_name(node)
            == "NotFoundError"
        )
    ]

    if len(handlers) > 1:
        raise RuntimeError(
            f"{fn.name}: handler duplicado "
            "para NotFoundError."
        )

    return (
        handlers[0]
        if handlers
        else None
    )


def validate_router_function(
    text,
    fn,
    require_not_found,
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
        existing_not_found_handler(fn)
    )

    if existing is None:
        if require_not_found:
            raise RuntimeError(
                f"{fn.name}: handler "
                "NotFoundError ausente."
            )
    else:
        status = (
            handler_http_status(
                existing
            )
        )

        if status != 404:
            raise RuntimeError(
                f"{fn.name}: NotFoundError "
                f"traduz HTTP {status}, "
                "esperado 404."
            )

    return (
        http_handler,
        prefix,
    )


def add_not_found_import(text):
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
            and (
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

    if "NotFoundError" in existing:
        return text

    fastapi_import = None

    for node in tree.body:
        if (
            isinstance(
                node,
                ast.ImportFrom,
            )
            and (
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
            "from domain.exceptions import "
            "NotFoundError"
        ),
    )

    result = "\n".join(lines)

    if text.endswith("\n"):
        result += "\n"

    return result


def build_not_found_handler(
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
            "NotFoundError as erro:"
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
            "status_code=404,"
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
        add_not_found_import(text)
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
                f"Função de router ausente: "
                f"{fn_name}"
            )

        (
            http_handler,
            prefix,
        ) = validate_router_function(
            patched,
            fn,
            require_not_found=False,
        )

        if (
            existing_not_found_handler(fn)
            is not None
        ):
            continue

        insertions.append(
            (
                http_handler.lineno,
                build_not_found_handler(
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
        top_functions(final_tree)
    )

    for fn_name in (
        affected_function_names
    ):
        validate_router_function(
            result,
            final_functions[fn_name],
            require_not_found=True,
        )

    after_exact = {
        token:
            result.count(token)
        for token
        in PROTECTED_EXACT_TOKENS
    }

    if before_exact != after_exact:
        diffs = {
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
            f"alterado: {diffs}"
        )

    return result


# ============================================================
# PATCH SERVICE
# ============================================================

def patch_service(text):
    state, diag = (
        service_state(text)
    )

    if state != "LEGADO":
        raise RuntimeError(
            f"Service não está legado: "
            f"{state} / {diag}"
        )

    item = target_http_raises(
        text
    )[0]

    node = item["node"]
    indent = (
        " " * node.col_offset
    )

    replacement = (
        f"{indent}raise NotFoundError(\n"
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

    usage = total_http_usage(
        result
    )

    if (
        usage["raises"] != 0
        or usage["handlers"] != 0
    ):
        raise RuntimeError(
            "Uso funcional HTTP "
            f"remanescente: {usage}"
        )

    tree = parse(
        result,
        "service após raise",
    )

    fastapi_imports = [
        node
        for node in tree.body
        if (
            isinstance(
                node,
                ast.ImportFrom,
            )
            and (
                node.module
                or ""
            )
            == "fastapi"
            and [
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
            "não está no formato esperado."
        )

    import_node = (
        fastapi_imports[0]
    )

    lines = result.splitlines()

    lines[
        import_node.lineno - 1:
        import_node.end_lineno
    ] = [
        (
            "from domain.exceptions "
            "import NotFoundError"
        )
    ]

    final = "\n".join(lines)

    if result.endswith("\n"):
        final += "\n"

    final_state, final_diag = (
        service_state(final)
    )

    if final_state != "MIGRADO":
        raise RuntimeError(
            "Service pós-patch inválido: "
            f"{final_diag}"
        )

    return final


# ============================================================
# EXECUÇÃO
# ============================================================

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
            f"[ERRO] Arquivo ausente: "
            f"{path}"
        )

domain_text = read_text(
    DOMAIN
)

if (
    "class NotFoundError(DomainError)"
    not in domain_text
):
    raise SystemExit(
        "[ERRO] NotFoundError "
        "não encontrada."
    )

prev_text = read_text(
    PREV
)

if (
    "HTTPException"
    in prev_text
    or "fastapi"
    in prev_text.lower()
    or "starlette"
    in prev_text.lower()
):
    raise SystemExit(
        "[ERRO] Fase 10S não "
        "reconhecida em "
        "services/rodadas/lifecycle.py."
    )

print(
    "      [OK] Fase 10S reconhecida."
)


print(
    "[1/14] Analisando baseline 10T..."
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
    f"      diagnóstico: {s_diag}"
)

if s_state == "DESCONHECIDO":
    raise SystemExit(
        "[ERRO] Baseline de "
        "localizacoes.py "
        f"desconhecida: {s_diag}"
    )


print(
    "[2/14] Confirmando erro único HTTP 404..."
)

if s_state == "LEGADO":
    item = (
        target_http_raises(
            service_text
        )[0]
    )

    print(
        f"      {TARGET_FUNCTION}: "
        f"HTTP {item['status']} | "
        f"detail="
        f"{item['detail_value']}"
    )

print(
    "      [OK] perfil confirmado."
)


print(
    "[3/14] Indexando módulos de produção..."
)

modules = (
    build_project_index()
)

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
    "[4/14] Construindo grafo de consumidores..."
)

reverse = build_call_graph(
    modules
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
    "[5/14] Classificando caminhos..."
)

affected_services = sorted(
    node
    for node in affected
    if (
        node != TARGET_NODE
        and node[0].startswith(
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
        and not node[0].startswith(
            "services."
        )
        and not node[0].startswith(
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
        "[ERRO] Caller fora "
        "de services/routers."
    )


print(
    "[6/14] Verificando services intermediários..."
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
            "[ERRO] NotFoundError seria "
            "embrulhada por service "
            "intermediário."
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
    "[7/14] Agrupando fronteiras HTTP..."
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
    "[8/14] Validando handlers atuais..."
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
            require_not_found=(
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
        "[9/14] Fase 10T "
        "já aplicada."
    )

    print(
        "      [OK] service e "
        "fronteiras consistentes."
    )

    raise SystemExit(0)


print(
    "[9/14] Confirmando exclusividade do raise..."
)

locations = (
    all_http_raise_locations(
        service_text
    )
)

if locations != {
    TARGET_FUNCTION: 1
}:
    raise SystemExit(
        "[ERRO] HTTPException "
        "fora do escopo: "
        f"{locations}"
    )

print(
    "      [OK] único "
    "HTTPException pertence "
    "a sincronizar_localizacoes_recontagem."
)


print(
    "[10/14] Preparando backups..."
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

for module_name, path in (
    paths_to_edit.items()
):
    backup = (
        path.parent
        / (
            path.stem
            + "_backup_fase10t_"
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
        "[11/14] Migrando localizacoes.py..."
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
        "      [OK] HTTP 404 -> "
        "NotFoundError."
    )

    print(
        "      [OK] FastAPI "
        "removido do módulo."
    )


    print(
        "[12/14] Adaptando fronteiras HTTP..."
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
        "[13/14] Revalidando service/grafo..."
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
                info[
                    "functions"
                ][
                    fn_name
                ],
                require_not_found=True,
            )

    print(
        "      [OK] 0 "
        "HTTPException/FastAPI "
        "no módulo."
    )

    print(
        "      [OK] fronteiras "
        "preservam HTTP 404."
    )


    print(
        "[14/14] Revalidando services intermediários..."
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
                "NotFoundError."
            )

    print(
        "      [OK] propagação "
        "permanece segura."
    )


except Exception:
    print()
    print(
        "[ERRO] Falha durante "
        "Fase 10T."
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
    "[OK] Fase 10T aplicada."
)

print(
    "[OK] services/rodadas/localizacoes.py "
    "desacoplado de FastAPI."
)

print(
    "[OK] HTTP 404 -> "
    "NotFoundError."
)

print(
    "[OK] sincronização direta "
    "e criação de rodadas "
    "continuam preservando HTTP 404."
)

print(
    "[OK] callers transitivos e "
    "facades/reexports rastreados."
)

print(
    "[OK] SQL, geração de "
    "localizações, UoW, conexão "
    "e commit inalterados."
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
