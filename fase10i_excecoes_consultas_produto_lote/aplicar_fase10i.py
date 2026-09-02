
"""
FASE 10I - CONSULTAS OPERACIONAIS | PRODUTO + LOTE

Escopo:
- services/consultas_operacionais.py
  - buscar_produto_contagem
  - validar_lote_contagem
- routers/consultas.py
  - endpoints direta/indiretamente afetados

Baseline esperado da Fase 10A:
- buscar_produto_contagem: 2 HTTPException
- validar_lote_contagem: 3 HTTPException
Total: 5

Mapeamento:
- HTTP 400 -> BusinessRuleViolation
- HTTP 404 -> NotFoundError
- HTTP 409 -> ConflictError

O instalador:
- lê status/detail reais via AST;
- preserva detail;
- monta grafo interno de chamadas;
- detecta endpoints afetados;
- reutiliza handlers já presentes das Fases 10G/10H;
- adiciona apenas handlers faltantes;
- bloqueia consumidores externos inesperados;
- não altera conexão/transação/SQL.

Execute:
python .\fase10i_excecoes_consultas_produto_lote\aplicar_fase10i.py
"""

from pathlib import Path
from datetime import datetime
import ast
import py_compile
import shutil

ROOT = Path.cwd()

DOMAIN = ROOT / "domain" / "exceptions.py"
SERVICE = ROOT / "services" / "consultas_operacionais.py"
ROUTER = ROOT / "routers" / "consultas.py"

TARGET_COUNTS = {
    "buscar_produto_contagem": 2,
    "validar_lote_contagem": 3,
}

SEEDS = set(TARGET_COUNTS)

EXC_BY_STATUS = {
    400: "BusinessRuleViolation",
    404: "NotFoundError",
    409: "ConflictError",
}

STATUS_BY_EXC = {
    value: key
    for key, value in EXC_BY_STATUS.items()
}

PROTECTED_TOKENS = [
    "get_connection()",
    "SqlServerUnitOfWork()",
    "uow.open()",
    "conn.cursor()",
    "uow.cursor",
    "cursor.close()",
    "conn.close()",
    "uow.close()",
    "conn.commit()",
    "conn.rollback()",
    "uow.commit()",
    "uow.rollback()",
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


def function_calls(fn_node):
    names = set()

    for node in ast.walk(fn_node):
        if (
            isinstance(node, ast.Call)
            and
            isinstance(node.func, ast.Name)
        ):
            names.add(
                node.func.id
            )

    return names


def get_function(text, name):
    tree = parse(
        text,
        "services/consultas_operacionais.py",
    )

    functions = top_functions(
        tree
    )

    fn = functions.get(
        name
    )

    if fn is None:
        raise RuntimeError(
            f"Função ausente: {name}"
        )

    return fn


def direct_http_raises(text, function_name):
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
            and
            isinstance(
                status_node.value,
                int,
            )
        ):
            raise RuntimeError(
                f"{function_name}: status dinâmico "
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
                f"{function_name}: detail não recuperado."
            )

        result.append(
            {
                "node": node,
                "status":
                    status_node.value,
                "detail":
                    detail,
            }
        )

    return result


def direct_domain_raises(text, function_name):
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
            result.append(
                name
            )

    return result


def validate_10h(text):
    """
    10H deve ter migrado os 5 HTTPException diretos de
    consultar_detalhe_localizacao.
    """
    http_count = len(
        direct_http_raises(
            text,
            "consultar_detalhe_localizacao",
        )
    )

    domain_count = len(
        direct_domain_raises(
            text,
            "consultar_detalhe_localizacao",
        )
    )

    return (
        http_count == 0
        and
        domain_count == 5
    ), {
        "http":
            http_count,
        "domain":
            domain_count,
    }


def target_state(text):
    diag = {}
    legacy = True
    migrated = True

    for name, expected in (
        TARGET_COUNTS.items()
    ):
        http_raises = (
            direct_http_raises(
                text,
                name,
            )
        )

        domain_raises = (
            direct_domain_raises(
                text,
                name,
            )
        )

        diag[name] = {
            "http_count":
                len(http_raises),

            "statuses":
                [
                    item["status"]
                    for item
                    in http_raises
                ],

            "domain_raises":
                domain_raises,
        }

        if not (
            len(http_raises)
            == expected
            and
            len(domain_raises)
            == 0
        ):
            legacy = False

        if not (
            len(http_raises)
            == 0
            and
            len(domain_raises)
            == expected
        ):
            migrated = False

    if legacy:
        return "LEGADO", diag

    if migrated:
        return "MIGRADO", diag

    return "DESCONHECIDO", diag


def internal_call_graph(text):
    tree = parse(
        text,
        "services/consultas_operacionais.py",
    )

    functions = top_functions(
        tree
    )

    names = set(
        functions
    )

    graph = {}

    for name, fn in (
        functions.items()
    ):
        graph[name] = (
            function_calls(
                fn
            )
            .intersection(
                names
            )
        )

    return (
        functions,
        graph,
    )


def affected_service_functions(text):
    functions, graph = (
        internal_call_graph(
            text
        )
    )

    missing = (
        SEEDS
        - set(functions)
    )

    if missing:
        raise RuntimeError(
            "Funções alvo ausentes: "
            f"{sorted(missing)}"
        )

    affected = set(
        SEEDS
    )

    changed = True

    while changed:
        changed = False

        for caller, callees in (
            graph.items()
        ):
            if caller in affected:
                continue

            if callees.intersection(
                affected
            ):
                affected.add(
                    caller
                )
                changed = True

    return affected


def imported_aliases(
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

        if (
            (node.module or "")
            != module_name
        ):
            continue

        for alias in (
            node.names
        ):
            result[
                alias.asname
                or
                alias.name
            ] = alias.name

    return result


def affected_router_functions(
    router_text,
    service_text,
):
    affected_service = (
        affected_service_functions(
            service_text
        )
    )

    tree = parse(
        router_text,
        "routers/consultas.py",
    )

    imports = imported_aliases(
        tree,
        "services.consultas_operacionais",
    )

    affected_aliases = {
        local
        for local, original
        in imports.items()
        if original
        in affected_service
    }

    result = []

    for node in tree.body:
        if not isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        ):
            continue

        calls = (
            function_calls(
                node
            )
        )

        used = sorted(
            calls.intersection(
                affected_aliases
            )
        )

        if not used:
            continue

        handlers = {}

        for inner in ast.walk(
            node
        ):
            if not isinstance(
                inner,
                ast.ExceptHandler,
            ):
                continue

            name = handler_name(
                inner
            )

            if name:
                handlers.setdefault(
                    name,
                    []
                ).append(
                    inner
                )

        result.append(
            {
                "node":
                    node,

                "name":
                    node.name,

                "services":
                    sorted(
                        {
                            imports[
                                alias
                            ]
                            for alias
                            in used
                        }
                    ),

                "handlers":
                    handlers,
            }
        )

    return (
        result,
        affected_service,
    )


def is_excluded(path):
    rel = path.relative_to(
        ROOT
    )

    for part in (
        rel.parts
    ):
        low = (
            part.lower()
        )

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


def external_consumers():
    """
    Bloqueia imports das funções afetadas fora de routers/consultas.py.
    Chamadas internas no próprio service não entram aqui.
    """
    affected = (
        affected_service_functions(
            read_text(
                SERVICE
            )
        )
    )

    consumers = []

    for path in ROOT.rglob(
        "*.py"
    ):
        if is_excluded(
            path
        ):
            continue

        if path in {
            SERVICE,
            ROUTER,
        }:
            continue

        text = read_text(
            path
        )

        if (
            "services.consultas_operacionais"
            not in text
        ):
            continue

        tree = parse(
            text,
            str(path),
        )

        aliases = imported_aliases(
            tree,
            "services.consultas_operacionais",
        )

        imported_affected = sorted(
            {
                original
                for original
                in aliases.values()
                if original
                in affected
            }
        )

        if imported_affected:
            consumers.append(
                {
                    "path":
                        path.relative_to(
                            ROOT
                        ),
                    "functions":
                        imported_affected,
                }
            )

    return consumers


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


def required_classes_from_target(
    text,
):
    classes = set()

    state, diag = (
        target_state(
            text
        )
    )

    if state == "LEGADO":
        for info in (
            diag.values()
        ):
            for status in (
                info[
                    "statuses"
                ]
            ):
                if (
                    status
                    not in
                    EXC_BY_STATUS
                ):
                    raise RuntimeError(
                        "Status fora do escopo: "
                        f"{status}"
                    )

                classes.add(
                    EXC_BY_STATUS[
                        status
                    ]
                )

    elif state == "MIGRADO":
        for info in (
            diag.values()
        ):
            classes.update(
                info[
                    "domain_raises"
                ]
            )

    else:
        raise RuntimeError(
            f"Baseline alvo inválida: {diag}"
        )

    return sorted(
        classes,
        key=lambda name:
            STATUS_BY_EXC[
                name
            ],
    )


def validate_router_handlers(
    router_text,
    service_text,
    required_classes,
    require_all=False,
):
    targets, _ = (
        affected_router_functions(
            router_text,
            service_text,
        )
    )

    # É válido um target não estar exposto no router.
    # Mas qualquer endpoint afetado existente precisa manter
    # o handler legado HTTPException e não pode ter handlers
    # semânticos incorretos.
    for item in targets:
        handlers = (
            item["handlers"]
        )

        if len(
            handlers.get(
                "HTTPException",
                []
            )
        ) != 1:
            raise RuntimeError(
                f"{item['name']}: esperado "
                "1 except HTTPException."
            )

        for exc_name in (
            required_classes
        ):
            existing = (
                handlers.get(
                    exc_name,
                    []
                )
            )

            if len(
                existing
            ) > 1:
                raise RuntimeError(
                    f"{item['name']}: "
                    f"handler duplicado {exc_name}."
                )

            if existing:
                actual = (
                    handler_http_status(
                        existing[0]
                    )
                )

                expected = (
                    STATUS_BY_EXC[
                        exc_name
                    ]
                )

                if (
                    actual
                    != expected
                ):
                    raise RuntimeError(
                        f"{item['name']}: "
                        f"{exc_name} traduz para "
                        f"HTTP {actual}, esperado "
                        f"{expected}."
                    )

            elif require_all:
                raise RuntimeError(
                    f"{item['name']}: "
                    f"handler {exc_name} ausente."
                )

    return targets


def patch_service(
    text,
):
    state, diag = (
        target_state(
            text
        )
    )

    if state != "LEGADO":
        raise RuntimeError(
            "Target não está legado: "
            f"{state} / {diag}"
        )

    replacements = []
    statuses = []

    for name, expected in (
        TARGET_COUNTS.items()
    ):
        raises = (
            direct_http_raises(
                text,
                name,
            )
        )

        if len(
            raises
        ) != expected:
            raise RuntimeError(
                f"{name}: esperado {expected} "
                "HTTPException."
            )

        for item in raises:
            status = (
                item["status"]
            )

            if (
                status
                not in
                EXC_BY_STATUS
            ):
                raise RuntimeError(
                    f"{name}: status "
                    f"{status} fora do escopo."
                )

            exc_name = (
                EXC_BY_STATUS[
                    status
                ]
            )

            node = (
                item["node"]
            )

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

            statuses.append(
                status
            )

    if len(
        replacements
    ) != 5:
        raise RuntimeError(
            "Esperadas 5 conversões; "
            f"encontradas {len(replacements)}."
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

    for start, end, repl in (
        replacements
    ):
        out.extend(
            lines[
                current - 1:
                start - 1
            ]
        )

        out.extend(
            repl.splitlines()
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

    if text.endswith(
        "\n"
    ):
        result += "\n"

    required_classes = sorted(
        {
            EXC_BY_STATUS[
                status
            ]
            for status
            in statuses
        },
        key=lambda name:
            STATUS_BY_EXC[
                name
            ],
    )

    tree = parse(
        result,
        "service após patch",
    )

    existing = set()

    for node in (
        tree.body
    ):
        if (
            isinstance(
                node,
                ast.ImportFrom,
            )
            and
            (node.module or "")
            == "domain.exceptions"
        ):
            for alias in (
                node.names
            ):
                existing.add(
                    alias.name
                )

    missing = [
        name
        for name
        in required_classes
        if name
        not in existing
    ]

    if missing:
        fastapi_import = None

        for node in (
            tree.body
        ):
            if (
                isinstance(
                    node,
                    ast.ImportFrom,
                )
                and
                (node.module or "")
                == "fastapi"
            ):
                fastapi_import = (
                    node
                )
                break

        if (
            fastapi_import
            is None
        ):
            raise RuntimeError(
                "Import FastAPI não encontrado "
                "para inserir exceções."
            )

        lines2 = (
            result.splitlines()
        )

        lines2.insert(
            fastapi_import.end_lineno,
            (
                "from domain.exceptions import "
                + ", ".join(
                    missing
                )
            ),
        )

        result = "\n".join(
            lines2
        )

        if text.endswith(
            "\n"
        ):
            result += "\n"

    state2, diag2 = (
        target_state(
            result
        )
    )

    if state2 != "MIGRADO":
        raise RuntimeError(
            "Service pós-patch inválido: "
            f"{diag2}"
        )

    return (
        result,
        required_classes,
    )


def insert_router_imports(
    text,
    required_classes,
):
    tree = parse(
        text,
        "routers/consultas.py",
    )

    existing = set()

    for node in (
        tree.body
    ):
        if (
            isinstance(
                node,
                ast.ImportFrom,
            )
            and
            (node.module or "")
            == "domain.exceptions"
        ):
            for alias in (
                node.names
            ):
                existing.add(
                    alias.name
                )

    missing = [
        name
        for name
        in required_classes
        if name
        not in existing
    ]

    if not missing:
        return text

    fastapi_import = None

    for node in (
        tree.body
    ):
        if (
            isinstance(
                node,
                ast.ImportFrom,
            )
            and
            (node.module or "")
            == "fastapi"
        ):
            fastapi_import = (
                node
            )
            break

    if (
        fastapi_import
        is None
    ):
        raise RuntimeError(
            "Import FastAPI não encontrado "
            "no router."
        )

    lines = (
        text.splitlines()
    )

    lines.insert(
        fastapi_import.end_lineno,
        (
            "from domain.exceptions import "
            + ", ".join(
                missing
            )
        ),
    )

    result = "\n".join(
        lines
    )

    if text.endswith(
        "\n"
    ):
        result += "\n"

    return result


def patch_router(
    router_text,
    service_text,
    required_classes,
):
    before = {
        token:
            router_text.count(
                token
            )
        for token
        in PROTECTED_TOKENS
    }

    validate_router_handlers(
        router_text,
        service_text,
        required_classes,
        require_all=False,
    )

    patched = (
        insert_router_imports(
            router_text,
            required_classes,
        )
    )

    targets, _ = (
        affected_router_functions(
            patched,
            service_text,
        )
    )

    insertions = []

    for item in targets:
        handlers = (
            item["handlers"]
        )

        http_handler = (
            handlers[
                "HTTPException"
            ][0]
        )

        missing = [
            exc_name
            for exc_name
            in required_classes
            if not handlers.get(
                exc_name
            )
        ]

        if not missing:
            continue

        indent = (
            " "
            * http_handler.col_offset
        )

        blocks = []

        for exc_name in (
            missing
        ):
            status = (
                STATUS_BY_EXC[
                    exc_name
                ]
            )

            blocks.append(
                (
                    f"{indent}except {exc_name} as erro:\n\n"
                    f"{indent}    raise HTTPException(\n"
                    f"{indent}        status_code={status},\n"
                    f"{indent}        detail=str(erro)\n"
                    f"{indent}    )\n"
                )
            )

        insertions.append(
            (
                http_handler.lineno,
                "\n".join(
                    blocks
                ) + "\n",
            )
        )

    lines = (
        patched.splitlines()
    )

    for line_no, block in sorted(
        insertions,
        key=lambda item:
            item[0],
        reverse=True,
    ):
        lines[
            line_no - 1:
            line_no - 1
        ] = (
            block.splitlines()
        )

    result = "\n".join(
        lines
    )

    if patched.endswith(
        "\n"
    ):
        result += "\n"

    validate_router_handlers(
        result,
        service_text,
        required_classes,
        require_all=True,
    )

    after = {
        token:
            result.count(
                token
            )
        for token
        in PROTECTED_TOKENS
    }

    if before != after:
        differences = {
            token: (
                before[token],
                after[token],
            )
            for token
            in PROTECTED_TOKENS
            if before[token]
            != after[token]
        }

        raise RuntimeError(
            "Conexão/transação foi alterada: "
            f"{differences}"
        )

    return result


print(
    "[0/13] Validando arquivos e hierarchy..."
)

for path in [
    DOMAIN,
    SERVICE,
    ROUTER,
]:
    if not path.exists():
        raise SystemExit(
            f"[ERRO] Arquivo ausente: {path}"
        )

domain_text = (
    read_text(
        DOMAIN
    )
)

for token in [
    "class BusinessRuleViolation(DomainError)",
    "class NotFoundError(DomainError)",
    "class ConflictError(DomainError)",
]:
    if token not in domain_text:
        raise SystemExit(
            "[ERRO] Hierarquia incompleta: "
            f"{token}"
        )

print(
    "      [OK] hierarchy reconhecida."
)


print(
    "[1/13] Validando pré-requisito 10H..."
)

service_text = (
    read_text(
        SERVICE
    )
)

ok_10h, diag_10h = (
    validate_10h(
        service_text
    )
)

print(
    f"      detalhe_localizacao: "
    f"HTTP={diag_10h['http']} "
    f"domain={diag_10h['domain']}"
)

if not ok_10h:
    raise SystemExit(
        "[ERRO] Fase 10H não reconhecida."
    )

print(
    "      [OK] Fase 10H reconhecida."
)


print(
    "[2/13] Analisando funções alvo..."
)

state, diag = (
    target_state(
        service_text
    )
)

print(
    f"      Estado: {state}"
)

for name, info in (
    diag.items()
):
    print(
        f"      {name}: "
        f"HTTP={info['http_count']} "
        f"statuses={info['statuses']} "
        f"domain={info['domain_raises']}"
    )

if state == "DESCONHECIDO":
    raise SystemExit(
        "[ERRO] Baseline alvo desconhecida: "
        f"{diag}"
    )


print(
    "[3/13] Validando consumidores externos..."
)

external = (
    external_consumers()
)

if external:
    for item in external:
        print(
            f"      [BLOQUEIO] "
            f"{item['path']} -> "
            f"{item['functions']}"
        )

    print(
        "[INFO] Nenhum arquivo foi alterado."
    )

    raise SystemExit(
        "[ERRO] Consumidor externo inesperado."
    )

print(
    "      [OK] sem consumidores externos inesperados."
)


print(
    "[4/13] Mapeando propagação interna..."
)

affected = (
    affected_service_functions(
        service_text
    )
)

for name in sorted(
    affected
):
    print(
        f"      - {name}"
    )


print(
    "[5/13] Mapeando endpoints afetados..."
)

router_text = (
    read_text(
        ROUTER
    )
)

targets, _ = (
    affected_router_functions(
        router_text,
        service_text,
    )
)

if targets:
    for item in targets:
        print(
            f"      {item['name']} <- "
            f"{', '.join(item['services'])}"
        )
else:
    print(
        "      [INFO] Nenhum endpoint direto "
        "atualmente expõe essas funções."
    )

print(
    f"      total endpoints: {len(targets)}"
)


required_classes = (
    required_classes_from_target(
        service_text
    )
)

print(
    "[6/13] Exceções semânticas necessárias..."
)

for name in required_classes:
    print(
        f"      {name} -> "
        f"HTTP {STATUS_BY_EXC[name]}"
    )


if state == "MIGRADO":
    try:
        validate_router_handlers(
            router_text,
            service_text,
            required_classes,
            require_all=True,
        )

    except Exception as exc:
        raise SystemExit(
            "[ERRO] Service já migrado, "
            "router inconsistente: "
            f"{exc}"
        )

    print(
        "[7/13] Fase 10I já aplicada."
    )
    print(
        "      [OK] nenhuma alteração necessária."
    )
    raise SystemExit(0)


print(
    "[7/13] Validando exatamente 2 + 3 HTTPException..."
)

for name, expected in (
    TARGET_COUNTS.items()
):
    raises = (
        direct_http_raises(
            service_text,
            name,
        )
    )

    if len(
        raises
    ) != expected:
        raise SystemExit(
            f"[ERRO] {name}: esperado "
            f"{expected}, encontrado "
            f"{len(raises)}."
        )

    for item in raises:
        if (
            item["status"]
            not in
            EXC_BY_STATUS
        ):
            raise SystemExit(
                f"[ERRO] {name}: status "
                f"{item['status']} fora do escopo."
            )

        print(
            f"      {name}: "
            f"HTTP {item['status']} -> "
            f"{EXC_BY_STATUS[item['status']]}"
        )

print(
    "      [OK] total = 5."
)


print(
    "[8/13] Validando handlers existentes..."
)

validate_router_handlers(
    router_text,
    service_text,
    required_classes,
    require_all=False,
)

print(
    "      [OK] handlers anteriores "
    "são compatíveis."
)


print(
    "[9/13] Registrando conexão/transação..."
)

before_conn = {
    token:
        router_text.count(
            token
        )
    for token
    in PROTECTED_TOKENS
}

for token, count in (
    before_conn.items()
):
    if count:
        print(
            f"      {token}: {count}"
        )

print(
    "      [OK] baseline registrada."
)


timestamp = (
    datetime.now()
    .strftime(
        "%Y%m%d_%H%M%S"
    )
)

service_backup = (
    SERVICE.parent
    / (
        SERVICE.stem
        + "_backup_fase10i_"
        + timestamp
        + ".py"
    )
)

router_backup = (
    ROUTER.parent
    / (
        ROUTER.stem
        + "_backup_fase10i_"
        + timestamp
        + ".py"
    )
)

print(
    "[10/13] Criando backups..."
)

shutil.copy2(
    SERVICE,
    service_backup,
)

shutil.copy2(
    ROUTER,
    router_backup,
)

print(
    f"      {service_backup.name}"
)
print(
    f"      {router_backup.name}"
)


try:
    print(
        "[11/13] Migrando produto/lote no service..."
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
        "      [OK] 5 HTTPException "
        "-> exceções semânticas."
    )


    print(
        "[12/13] Adaptando endpoints afetados..."
    )

    patched_router = (
        patch_router(
            router_text,
            patched_service,
            required_classes,
        )
    )

    ROUTER.write_text(
        patched_router,
        encoding="utf-8",
    )

    py_compile.compile(
        str(ROUTER),
        doraise=True,
    )

    final_targets, _ = (
        affected_router_functions(
            patched_router,
            patched_service,
        )
    )

    print(
        f"      [OK] endpoints consolidados: "
        f"{len(final_targets)}"
    )


    print(
        "[13/13] Validação final..."
    )

    final_service = (
        read_text(
            SERVICE
        )
    )

    final_state, final_diag = (
        target_state(
            final_service
        )
    )

    if (
        final_state
        != "MIGRADO"
    ):
        raise RuntimeError(
            "Service final inválido: "
            f"{final_diag}"
        )

    final_router = (
        read_text(
            ROUTER
        )
    )

    validate_router_handlers(
        final_router,
        final_service,
        required_classes,
        require_all=True,
    )

    after_conn = {
        token:
            final_router.count(
                token
            )
        for token
        in PROTECTED_TOKENS
    }

    if before_conn != after_conn:
        raise RuntimeError(
            "Conexão/transação foi alterada."
        )

    # O service ainda pode conter HTTPException
    # em outras funções. Não remover FastAPI.
    tree = parse(
        final_service,
        "service final",
    )

    remaining_http = sum(
        1
        for node in ast.walk(
            tree
        )
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
        )
    )

    if (
        remaining_http > 0
        and
        "from fastapi import HTTPException"
        not in final_service
    ):
        raise RuntimeError(
            "Import FastAPI removido "
            "com HTTPException remanescentes."
        )

    print(
        "      [OK] contratos HTTP preservados."
    )
    print(
        "      [OK] conexão/transação inalteradas."
    )
    print(
        f"      [OK] HTTPException fora "
        f"do escopo preservados: "
        f"{remaining_http}"
    )


except Exception:
    print()
    print(
        "[ERRO] Falha durante Fase 10I."
    )
    print(
        "[INFO] Restaurando arquivos..."
    )

    shutil.copy2(
        service_backup,
        SERVICE,
    )

    shutil.copy2(
        router_backup,
        ROUTER,
    )

    print(
        "[OK] Estado anterior restaurado."
    )

    raise


print()
print(
    "[OK] Fase 10I aplicada."
)
print(
    "[OK] buscar_produto_contagem "
    "desacoplado de HTTP."
)
print(
    "[OK] validar_lote_contagem "
    "desacoplado de HTTP."
)
print(
    "[OK] 5 HTTPException migrados."
)
print(
    "[OK] handlers das fases anteriores "
    "reutilizados sem duplicação."
)
print(
    "[OK] mesmos status HTTP preservados."
)
print(
    "[OK] demais regras de "
    "consultas_operacionais intactas."
)
print(
    "[OK] conexão/transação inalteradas."
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
