
"""
FASE 10H - CONSULTAS OPERACIONAIS | DETALHE DA LOCALIZAÇÃO

Escopo:
- services/consultas_operacionais.py
  - consultar_detalhe_localizacao
- routers/consultas.py
  - endpoints direta ou indiretamente afetados

A Fase 10A encontrou 5 HTTPException em
consultar_detalhe_localizacao().

O instalador lê os 5 status reais do arquivo local e aceita:
- 400 -> BusinessRuleViolation
- 404 -> NotFoundError
- 409 -> ConflictError

Os details são preservados via AST.

Compatibilidade com a 10G:
- o endpoint de detalhe pode JÁ possuir NotFoundError handler,
  porque consultar_detalhe_localizacao chama consultar_inventario;
- o instalador reconhece handlers já existentes e não duplica.

Não altera:
- outros HTTPException do service
- SQL
- conexão/UoW
- cursor
- commit/rollback
- rotas
- retornos de sucesso

Execute:
python .\fase10h_excecoes_consultas_detalhe_localizacao\aplicar_fase10h.py
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

TARGET_FUNCTION = "consultar_detalhe_localizacao"
EXPECTED_HTTP_COUNT = 5

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
    result = set()

    for node in ast.walk(fn_node):
        if not isinstance(node, ast.Call):
            continue

        if isinstance(node.func, ast.Name):
            result.add(node.func.id)

    return result


def get_function(text, name):
    tree = parse(
        text,
        "services/consultas_operacionais.py",
    )

    functions = top_functions(tree)

    fn = functions.get(name)

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

        if status_node is None or detail_node is None:
            raise RuntimeError(
                f"{function_name}: HTTPException sem status/detail."
            )

        if not (
            isinstance(status_node, ast.Constant)
            and
            isinstance(status_node.value, int)
        ):
            raise RuntimeError(
                f"{function_name}: status dinâmico não suportado."
            )

        detail_source = ast.get_source_segment(
            text,
            detail_node,
        )

        if not detail_source:
            raise RuntimeError(
                f"{function_name}: detail não recuperado."
            )

        result.append(
            {
                "node": node,
                "status": status_node.value,
                "detail": detail_source,
            }
        )

    return result


def direct_domain_raises(text, function_name):
    fn = get_function(
        text,
        function_name,
    )

    result = []

    allowed = set(
        EXC_BY_STATUS.values()
    )

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


def pre_req_10g(text):
    """
    A 10G migra:
    consultar_inventario: 1 NotFoundError
    consultar_rodada_atual: 2 NotFoundError
    """
    checks = {
        "consultar_inventario": 1,
        "consultar_rodada_atual": 2,
    }

    details = {}

    for name, expected_domain in checks.items():
        http_count = len(
            direct_http_raises(
                text,
                name,
            )
        )

        domain_names = direct_domain_raises(
            text,
            name,
        )

        notfound_count = sum(
            1
            for item in domain_names
            if item == "NotFoundError"
        )

        details[name] = {
            "http": http_count,
            "notfound": notfound_count,
        }

        if (
            http_count != 0
            or
            notfound_count != expected_domain
        ):
            return False, details

    return True, details


def service_state(text):
    http_raises = direct_http_raises(
        text,
        TARGET_FUNCTION,
    )

    domain_raises = direct_domain_raises(
        text,
        TARGET_FUNCTION,
    )

    if (
        len(http_raises) == EXPECTED_HTTP_COUNT
        and
        len(domain_raises) == 0
    ):
        return "LEGADO", {
            "http_count": len(http_raises),
            "statuses": [
                item["status"]
                for item in http_raises
            ],
            "domain_raises": domain_raises,
        }

    if (
        len(http_raises) == 0
        and
        len(domain_raises) == EXPECTED_HTTP_COUNT
    ):
        return "MIGRADO", {
            "http_count": 0,
            "statuses": [],
            "domain_raises": domain_raises,
        }

    return "DESCONHECIDO", {
        "http_count": len(http_raises),
        "statuses": [
            item["status"]
            for item in http_raises
        ],
        "domain_raises": domain_raises,
    }


def internal_call_graph(text):
    tree = parse(
        text,
        "services/consultas_operacionais.py",
    )

    functions = top_functions(tree)
    names = set(functions)

    graph = {}

    for name, fn in functions.items():
        graph[name] = (
            function_calls(fn)
            .intersection(names)
        )

    return functions, graph


def affected_service_functions(text):
    functions, graph = internal_call_graph(
        text
    )

    if TARGET_FUNCTION not in functions:
        raise RuntimeError(
            f"{TARGET_FUNCTION} ausente."
        )

    affected = {
        TARGET_FUNCTION
    }

    changed = True

    while changed:
        changed = False

        for caller, callees in graph.items():
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


def imported_service_aliases(tree):
    result = {}

    for node in tree.body:
        if not isinstance(
            node,
            ast.ImportFrom,
        ):
            continue

        if (
            (node.module or "")
            != "services.consultas_operacionais"
        ):
            continue

        for alias in node.names:
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

    imports = imported_service_aliases(
        tree
    )

    affected_aliases = {
        local
        for local, original
        in imports.items()
        if original in affected_service
    }

    if not affected_aliases:
        raise RuntimeError(
            "Nenhuma função afetada importada no router."
        )

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

        calls = function_calls(
            node
        )

        used_aliases = sorted(
            calls.intersection(
                affected_aliases
            )
        )

        if not used_aliases:
            continue

        originals = sorted(
            {
                imports[name]
                for name in used_aliases
            }
        )

        handlers = {}

        for inner in ast.walk(node):
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
                "node": node,
                "name": node.name,
                "services": originals,
                "handlers": handlers,
            }
        )

    if not result:
        raise RuntimeError(
            "Nenhum endpoint afetado encontrado."
        )

    return (
        result,
        affected_service,
    )


def exception_handler_status(handler):
    """
    Tenta descobrir status_code literal dentro de:
    except X:
        raise HTTPException(status_code=..., ...)
    """
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


def required_classes_from_statuses(
    statuses,
):
    return {
        EXC_BY_STATUS[
            status
        ]
        for status in statuses
    }


def validate_existing_handlers(
    router_text,
    service_text,
    required_classes,
):
    targets, _ = (
        affected_router_functions(
            router_text,
            service_text,
        )
    )

    for item in targets:
        handlers = item[
            "handlers"
        ]

        http_handlers = handlers.get(
            "HTTPException",
            []
        )

        if len(http_handlers) != 1:
            raise RuntimeError(
                f"{item['name']}: esperado "
                "1 except HTTPException."
            )

        for exc_name in required_classes:
            existing = handlers.get(
                exc_name,
                []
            )

            if len(existing) > 1:
                raise RuntimeError(
                    f"{item['name']}: handler "
                    f"duplicado para {exc_name}."
                )

            if len(existing) == 1:
                expected_status = (
                    STATUS_BY_EXC[
                        exc_name
                    ]
                )

                actual_status = (
                    exception_handler_status(
                        existing[0]
                    )
                )

                if (
                    actual_status
                    != expected_status
                ):
                    raise RuntimeError(
                        f"{item['name']}: "
                        f"{exc_name} já existe "
                        f"com HTTP {actual_status}, "
                        f"esperado {expected_status}."
                    )

    return targets


def patch_service(text):
    state, diag = service_state(
        text
    )

    if state != "LEGADO":
        raise RuntimeError(
            f"Service não está legado: "
            f"{state} / {diag}"
        )

    raises = direct_http_raises(
        text,
        TARGET_FUNCTION,
    )

    statuses = [
        item["status"]
        for item in raises
    ]

    unsupported = [
        status
        for status in statuses
        if status not in EXC_BY_STATUS
    ]

    if unsupported:
        raise RuntimeError(
            "Status fora do escopo da 10H: "
            f"{unsupported}"
        )

    lines = text.splitlines()
    replacements = []

    for item in raises:
        node = item["node"]

        exc_name = EXC_BY_STATUS[
            item["status"]
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

    required_classes = sorted(
        required_classes_from_statuses(
            statuses
        )
    )

    tree = parse(
        result,
        "service após troca",
    )

    existing_domain_imports = set()

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
            for alias in node.names:
                existing_domain_imports.add(
                    alias.name
                )

    missing = [
        name
        for name in required_classes
        if name not in existing_domain_imports
    ]

    if missing:
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
                "Import FastAPI não encontrado "
                "para inserir exceções de domínio."
            )

        result_lines = (
            result.splitlines()
        )

        result_lines.insert(
            fastapi_import.end_lineno,
            (
                "from domain.exceptions import "
                + ", ".join(
                    missing
                )
            ),
        )

        result = "\n".join(
            result_lines
        )

        if text.endswith("\n"):
            result += "\n"

    state2, diag2 = service_state(
        result
    )

    if state2 != "MIGRADO":
        raise RuntimeError(
            "Service pós-patch inválido: "
            f"{diag2}"
        )

    return (
        result,
        statuses,
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
            "Import FastAPI não encontrado no router."
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

    result = "\n".join(
        lines
    )

    if text.endswith("\n"):
        result += "\n"

    return result


def patch_router(
    router_text,
    service_text,
    statuses,
    required_classes,
):
    before_counts = {
        token: router_text.count(
            token
        )
        for token in PROTECTED_TOKENS
    }

    validate_existing_handlers(
        router_text,
        service_text,
        set(required_classes),
    )

    patched = insert_router_imports(
        router_text,
        required_classes,
    )

    targets, _ = (
        affected_router_functions(
            patched,
            service_text,
        )
    )

    insertions = []

    for item in targets:
        handlers = item[
            "handlers"
        ]

        http_handler = handlers[
            "HTTPException"
        ][0]

        missing_for_endpoint = [
            exc_name
            for exc_name in required_classes
            if not handlers.get(
                exc_name
            )
        ]

        if not missing_for_endpoint:
            continue

        indent = (
            " " * http_handler.col_offset
        )

        blocks = []

        for exc_name in sorted(
            missing_for_endpoint,
            key=lambda name:
                STATUS_BY_EXC[name],
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

        block = "\n".join(
            blocks
        ) + "\n"

        insertions.append(
            (
                http_handler.lineno,
                block,
                item["name"],
            )
        )

    lines = patched.splitlines()

    for line_no, block, _ in sorted(
        insertions,
        key=lambda item: item[0],
        reverse=True,
    ):
        lines[
            line_no - 1:
            line_no - 1
        ] = block.splitlines()

    result = "\n".join(
        lines
    )

    if patched.endswith("\n"):
        result += "\n"

    # Valida handlers finais.
    validate_existing_handlers(
        result,
        service_text,
        set(required_classes),
    )

    final_targets, _ = (
        affected_router_functions(
            result,
            service_text,
        )
    )

    for item in final_targets:
        handlers = item[
            "handlers"
        ]

        for exc_name in required_classes:
            if len(
                handlers.get(
                    exc_name,
                    []
                )
            ) != 1:
                raise RuntimeError(
                    f"{item['name']}: "
                    f"{exc_name} não consolidado."
                )

    after_counts = {
        token: result.count(
            token
        )
        for token in PROTECTED_TOKENS
    }

    if before_counts != after_counts:
        differences = {
            token: (
                before_counts[token],
                after_counts[token],
            )
            for token in PROTECTED_TOKENS
            if before_counts[token]
            != after_counts[token]
        }

        raise RuntimeError(
            "Conexão/transação foi alterada: "
            f"{differences}"
        )

    return result


print(
    "[0/12] Validando arquivos..."
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

domain_text = read_text(
    DOMAIN
)

for token in [
    "class BusinessRuleViolation(DomainError)",
    "class NotFoundError(DomainError)",
    "class ConflictError(DomainError)",
]:
    if token not in domain_text:
        raise SystemExit(
            "[ERRO] Hierarquia de domínio "
            f"incompleta: {token}"
        )

print(
    "      [OK] hierarchy reconhecida."
)


print(
    "[1/12] Validando pré-requisito 10G..."
)

service_text = read_text(
    SERVICE
)

ok_10g, diag_10g = (
    pre_req_10g(
        service_text
    )
)

for name, info in (
    diag_10g.items()
):
    print(
        f"      {name}: "
        f"HTTP={info['http']} "
        f"NotFound={info['notfound']}"
    )

if not ok_10g:
    raise SystemExit(
        "[ERRO] Fase 10G não reconhecida."
    )

print(
    "      [OK] Fase 10G reconhecida."
)


print(
    "[2/12] Analisando consultar_detalhe_localizacao..."
)

state, diag = service_state(
    service_text
)

print(
    f"      Estado: {state}"
)
print(
    "      HTTPException diretos: "
    f"{diag['http_count']}"
)
print(
    "      statuses: "
    f"{diag['statuses']}"
)
print(
    "      domain raises: "
    f"{diag['domain_raises']}"
)

if state == "DESCONHECIDO":
    raise SystemExit(
        "[ERRO] Baseline da função alvo "
        f"desconhecida: {diag}"
    )


if state == "LEGADO":
    unsupported = [
        status
        for status in diag[
            "statuses"
        ]
        if status
        not in EXC_BY_STATUS
    ]

    if unsupported:
        raise SystemExit(
            "[ERRO] Status fora do escopo "
            f"da 10H: {unsupported}"
        )

    statuses = diag[
        "statuses"
    ]

    required_classes = sorted(
        required_classes_from_statuses(
            statuses
        )
    )

else:
    required_classes = sorted(
        set(
            diag[
                "domain_raises"
            ]
        )
    )

    statuses = [
        STATUS_BY_EXC[name]
        for name in required_classes
    ]


print(
    "[3/12] Mapeando propagação interna..."
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
    "[4/12] Mapeando endpoints afetados..."
)

router_text = read_text(
    ROUTER
)

targets, _ = (
    affected_router_functions(
        router_text,
        service_text,
    )
)

for item in targets:
    print(
        f"      {item['name']} <- "
        f"{', '.join(item['services'])}"
    )

print(
    f"      total: {len(targets)}"
)


if state == "MIGRADO":
    try:
        validate_existing_handlers(
            router_text,
            service_text,
            set(required_classes),
        )

        for item in (
            affected_router_functions(
                router_text,
                service_text,
            )[0]
        ):
            for exc_name in (
                required_classes
            ):
                if len(
                    item[
                        "handlers"
                    ].get(
                        exc_name,
                        []
                    )
                ) != 1:
                    raise RuntimeError(
                        f"{item['name']}: "
                        f"{exc_name} ausente."
                    )

    except Exception as exc:
        raise SystemExit(
            "[ERRO] Service migrado, "
            "router inconsistente: "
            f"{exc}"
        )

    print(
        "[5/12] Fase 10H já aplicada."
    )
    print(
        "      [OK] nenhuma alteração necessária."
    )
    raise SystemExit(0)


print(
    "[5/12] Validando os 5 HTTPException..."
)

raises = direct_http_raises(
    service_text,
    TARGET_FUNCTION,
)

if len(raises) != 5:
    raise SystemExit(
        "[ERRO] Esperados 5 HTTPException."
    )

for item in raises:
    if item["status"] not in EXC_BY_STATUS:
        raise SystemExit(
            "[ERRO] Status não suportado: "
            f"{item['status']}"
        )

    print(
        f"      HTTP {item['status']} -> "
        f"{EXC_BY_STATUS[item['status']]}"
    )

print(
    "      [OK] todos mapeáveis."
)


print(
    "[6/12] Validando handlers existentes do router..."
)

validate_existing_handlers(
    router_text,
    service_text,
    set(required_classes),
)

for item in targets:
    existing = [
        name
        for name in (
            required_classes
        )
        if item[
            "handlers"
        ].get(
            name
        )
    ]

    print(
        f"      {item['name']}: "
        f"já possui {existing}"
    )

print(
    "      [OK] sem conflitos."
)


print(
    "[7/12] Registrando conexão/transação..."
)

before_conn = {
    token: router_text.count(
        token
    )
    for token in PROTECTED_TOKENS
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
    /
    (
        SERVICE.stem
        + "_backup_fase10h_"
        + timestamp
        + ".py"
    )
)

router_backup = (
    ROUTER.parent
    /
    (
        ROUTER.stem
        + "_backup_fase10h_"
        + timestamp
        + ".py"
    )
)


print(
    "[8/12] Criando backups..."
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
        "[9/12] Migrando função do service..."
    )

    (
        patched_service,
        statuses,
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
        "[10/12] Adaptando endpoints afetados..."
    )

    patched_router = patch_router(
        router_text,
        patched_service,
        statuses,
        required_classes,
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
        "      [OK] endpoints consolidados: "
        f"{len(final_targets)}"
    )


    print(
        "[11/12] Validando escopo e contratos..."
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

    # Service ainda pode ter HTTPException
    # em outras funções, então FastAPI deve permanecer.
    remaining_http = 0

    tree = parse(
        final_service,
        "service final",
    )

    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Raise)
            and
            node.exc is not None
            and
            raised_name(node.exc)
            == "HTTPException"
        ):
            remaining_http += 1

    if (
        remaining_http > 0
        and
        "from fastapi import HTTPException"
        not in final_service
    ):
        raise RuntimeError(
            "FastAPI removido apesar de "
            "HTTPException remanescentes."
        )

    print(
        f"      [OK] HTTPException fora "
        f"do escopo preservados: {remaining_http}"
    )


    print(
        "[12/12] Validando conexão/transação..."
    )

    final_router = read_text(
        ROUTER
    )

    after_conn = {
        token: final_router.count(
            token
        )
        for token in PROTECTED_TOKENS
    }

    if before_conn != after_conn:
        raise RuntimeError(
            "Conexão/transação foi alterada."
        )

    print(
        "      [OK] conexão/transação inalteradas."
    )


except Exception:
    print()
    print(
        "[ERRO] Falha durante Fase 10H."
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
    "[OK] Fase 10H aplicada."
)
print(
    "[OK] consultar_detalhe_localizacao "
    "desacoplado de HTTP."
)
print(
    "[OK] 5 HTTPException migrados "
    "para exceções semânticas."
)
print(
    "[OK] handlers já criados pela 10G "
    "foram reutilizados sem duplicação."
)
print(
    "[OK] mesmos status HTTP preservados no router."
)
print(
    "[OK] demais regras de consultas_operacionais intactas."
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
