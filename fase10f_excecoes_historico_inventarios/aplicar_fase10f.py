
"""
FASE 10F - DESACOPLAMENTO HTTP DE historico_inventarios

Escopo:
- services/historico_inventarios.py
- routers/historico.py

Instalador adaptativo:
- lê os 2 HTTPException reais do service;
- aceita apenas status 400, 404 ou 409;
- converte:
    400 -> BusinessRuleViolation
    404 -> NotFoundError
    409 -> ConflictError
- preserva exatamente a expressão detail;
- adapta somente o endpoint do router que chama
  consultar_historico_inventarios;
- não altera conexão, UoW, SQL, commit ou rollback;
- aborta se houver consumidores inesperados.

Execute na raiz do SGI:
python .\fase10f_excecoes_historico_inventarios\aplicar_fase10f.py
"""

from pathlib import Path
from datetime import datetime
import ast
import py_compile
import shutil

ROOT = Path.cwd()

DOMAIN = ROOT / "domain" / "exceptions.py"
SERVICE = ROOT / "services" / "historico_inventarios.py"
ROUTER = ROOT / "routers" / "historico.py"

PREV_SERVICES = [
    ROOT / "services" / "historico_itens.py",
    ROOT / "services" / "historico_localizacoes.py",
    ROOT / "services" / "historico_divergencias.py",
]

TARGET_SERVICE_FUNCTION = "consultar_historico_inventarios"

EXC_BY_STATUS = {
    400: "BusinessRuleViolation",
    404: "NotFoundError",
    409: "ConflictError",
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


def top_level_function(tree, name):
    for node in tree.body:
        if isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef),
        ) and node.name == name:
            return node

    return None


def service_http_raises(text):
    tree = parse(
        text,
        "services/historico_inventarios.py",
    )

    target_fn = top_level_function(
        tree,
        TARGET_SERVICE_FUNCTION,
    )

    if target_fn is None:
        raise RuntimeError(
            f"Função {TARGET_SERVICE_FUNCTION} não encontrada."
        )

    result = []

    for node in ast.walk(target_fn):
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
                "HTTPException sem status_code/detail reconhecível."
            )

        if not (
            isinstance(status_node, ast.Constant)
            and isinstance(status_node.value, int)
        ):
            raise RuntimeError(
                "status_code dinâmico não suportado nesta fase."
            )

        status = status_node.value

        detail_source = ast.get_source_segment(
            text,
            detail_node,
        )

        if not detail_source:
            raise RuntimeError(
                "Não foi possível recuperar o detail."
            )

        result.append(
            {
                "node": node,
                "status": status,
                "detail_source": detail_source,
            }
        )

    return result


def service_domain_raises(text):
    tree = parse(
        text,
        "services/historico_inventarios.py",
    )

    target_fn = top_level_function(
        tree,
        TARGET_SERVICE_FUNCTION,
    )

    if target_fn is None:
        raise RuntimeError(
            f"Função {TARGET_SERVICE_FUNCTION} não encontrada."
        )

    names = []

    for node in ast.walk(target_fn):
        if not isinstance(node, ast.Raise):
            continue

        if node.exc is None:
            continue

        name = raised_name(node.exc)

        if name in set(EXC_BY_STATUS.values()):
            names.append(name)

    return names


def service_state(text):
    http_import = (
        "from fastapi import HTTPException"
        in text
    )

    http_raises = service_http_raises(text)
    domain_raises = service_domain_raises(text)

    if (
        http_import
        and len(http_raises) == 2
        and len(domain_raises) == 0
    ):
        return "LEGADO", {
            "http_statuses": [
                item["status"]
                for item in http_raises
            ],
            "domain_raises": domain_raises,
        }

    if (
        not http_import
        and len(http_raises) == 0
        and len(domain_raises) == 2
    ):
        return "MIGRADO", {
            "http_statuses": [],
            "domain_raises": domain_raises,
        }

    return "DESCONHECIDO", {
        "http_import": http_import,
        "http_count": len(http_raises),
        "http_statuses": [
            item["status"]
            for item in http_raises
        ],
        "domain_raises": domain_raises,
    }


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


def module_consumers():
    consumers = []

    for path in ROOT.rglob("*.py"):
        if is_excluded(path):
            continue

        if path == SERVICE:
            continue

        text = read_text(path)

        if "services.historico_inventarios" not in text:
            continue

        tree = parse(
            text,
            str(path),
        )

        imported = False

        for node in ast.walk(tree):
            if (
                isinstance(node, ast.ImportFrom)
                and
                (node.module or "")
                == "services.historico_inventarios"
            ):
                imported = True
                break

        if imported:
            consumers.append(
                path.relative_to(ROOT)
            )

    return sorted(
        set(consumers),
        key=lambda x: str(x),
    )


def imported_service_aliases(tree):
    result = set()

    for node in tree.body:
        if not isinstance(node, ast.ImportFrom):
            continue

        if (
            (node.module or "")
            != "services.historico_inventarios"
        ):
            continue

        for alias in node.names:
            if alias.name == TARGET_SERVICE_FUNCTION:
                result.add(
                    alias.asname or alias.name
                )

    return result


def function_calls_alias(fn_node, aliases):
    for node in ast.walk(fn_node):
        if not isinstance(node, ast.Call):
            continue

        if (
            isinstance(node.func, ast.Name)
            and node.func.id in aliases
        ):
            return True

    return False


def target_router_function(text):
    tree = parse(
        text,
        "routers/historico.py",
    )

    aliases = imported_service_aliases(
        tree
    )

    if not aliases:
        raise RuntimeError(
            "Router não importa consultar_historico_inventarios."
        )

    matches = []

    for node in tree.body:
        if not isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef),
        ):
            continue

        if function_calls_alias(
            node,
            aliases,
        ):
            matches.append(node)

    if len(matches) != 1:
        raise RuntimeError(
            "Esperado exatamente 1 endpoint consumidor; "
            f"encontrados {len(matches)}."
        )

    return matches[0]


def router_handler_counts(text):
    fn = target_router_function(
        text
    )

    counts = {
        "HTTPException": 0,
        "BusinessRuleViolation": 0,
        "NotFoundError": 0,
        "ConflictError": 0,
    }

    for node in ast.walk(fn):
        if not isinstance(node, ast.ExceptHandler):
            continue

        name = handler_name(node)

        if name in counts:
            counts[name] += 1

    return counts


def router_state(text, required_exceptions=None):
    required_exceptions = (
        set(required_exceptions or [])
    )

    counts = router_handler_counts(
        text
    )

    legacy = (
        counts["HTTPException"] == 1
        and
        all(
            counts[name] == 0
            for name in {
                "BusinessRuleViolation",
                "NotFoundError",
                "ConflictError",
            }
        )
    )

    migrated = (
        counts["HTTPException"] == 1
        and
        all(
            counts[name] == 1
            for name in required_exceptions
        )
        and
        all(
            counts[name] == 0
            for name in (
                {
                    "BusinessRuleViolation",
                    "NotFoundError",
                    "ConflictError",
                }
                - required_exceptions
            )
        )
    )

    if legacy:
        return "LEGADO", counts

    if required_exceptions and migrated:
        return "MIGRADO", counts

    return "DESCONHECIDO", counts


def patch_service(text):
    state, diag = service_state(
        text
    )

    if state != "LEGADO":
        raise RuntimeError(
            f"Service não está legado: {state} / {diag}"
        )

    raises = service_http_raises(
        text
    )

    if len(raises) != 2:
        raise RuntimeError(
            "Esperados exatamente 2 HTTPException."
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
            "Status não suportado na Fase 10F: "
            f"{unsupported}"
        )

    tree = parse(
        text,
        "services/historico_inventarios.py",
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
            f"{indent}    {item['detail_source']}\n"
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
        key=lambda x: x[0]
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

    result = "\n".join(out)

    if text.endswith("\n"):
        result += "\n"

    required_classes = sorted(
        {
            EXC_BY_STATUS[status]
            for status in statuses
        }
    )

    import_line = (
        "from domain.exceptions import "
        + ", ".join(required_classes)
    )

    result = result.replace(
        "from fastapi import HTTPException",
        import_line,
        1,
    )

    state2, diag2 = service_state(
        result
    )

    if state2 != "MIGRADO":
        raise RuntimeError(
            "Service pós-patch inválido: "
            f"{state2} / {diag2}"
        )

    return result, statuses, required_classes


def insert_domain_imports(text, required_classes):
    tree = parse(
        text,
        "routers/historico.py",
    )

    existing_imports = set()

    for node in tree.body:
        if not isinstance(node, ast.ImportFrom):
            continue

        if (
            (node.module or "")
            == "domain.exceptions"
        ):
            for alias in node.names:
                existing_imports.add(
                    alias.name
                )

    missing = [
        name
        for name in required_classes
        if name not in existing_imports
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
            "Import FastAPI não encontrado no router."
        )

    lines = text.splitlines()

    lines.insert(
        fastapi_import.end_lineno,
        (
            "from domain.exceptions import "
            + ", ".join(missing)
        ),
    )

    result = "\n".join(lines)

    if text.endswith("\n"):
        result += "\n"

    return result


def patch_router(text, statuses, required_classes):
    state, diag = router_state(
        text
    )

    if state != "LEGADO":
        raise RuntimeError(
            f"Router não está legado: {state} / {diag}"
        )

    before_counts = {
        token: text.count(token)
        for token in PROTECTED_TOKENS
    }

    patched = insert_domain_imports(
        text,
        required_classes,
    )

    fn = target_router_function(
        patched
    )

    http_handlers = [
        node
        for node in ast.walk(fn)
        if (
            isinstance(node, ast.ExceptHandler)
            and
            handler_name(node)
            == "HTTPException"
        )
    ]

    if len(http_handlers) != 1:
        raise RuntimeError(
            "Esperado 1 except HTTPException "
            "no endpoint de histórico de inventários."
        )

    http_handler = http_handlers[0]
    indent = " " * http_handler.col_offset

    status_by_exc = {
        EXC_BY_STATUS[status]: status
        for status in statuses
    }

    blocks = []

    for exc_name in sorted(
        required_classes,
        key=lambda name: status_by_exc[name],
    ):
        status = status_by_exc[
            exc_name
        ]

        blocks.append(
            (
                f"{indent}except {exc_name} as erro:\n\n"
                f"{indent}    raise HTTPException(\n"
                f"{indent}        status_code={status},\n"
                f"{indent}        detail=str(erro)\n"
                f"{indent}    )\n"
            )
        )

    block = "\n".join(blocks) + "\n"

    lines = patched.splitlines()

    lines[
        http_handler.lineno - 1:
        http_handler.lineno - 1
    ] = block.splitlines()

    result = "\n".join(lines)

    if patched.endswith("\n"):
        result += "\n"

    required = set(
        required_classes
    )

    state2, diag2 = router_state(
        result,
        required_exceptions=required,
    )

    if state2 != "MIGRADO":
        raise RuntimeError(
            "Router pós-patch inválido: "
            f"{state2} / {diag2}"
        )

    after_counts = {
        token: result.count(token)
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
    "[0/11] Validando pré-requisitos..."
)

for path in (
    [DOMAIN, SERVICE, ROUTER]
    + PREV_SERVICES
):
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
            "[ERRO] Hierarquia da Fase 10B "
            f"incompleta: {token}"
        )

for path in PREV_SERVICES:
    text = read_text(path)

    if (
        "from fastapi import HTTPException"
        in text
    ):
        raise SystemExit(
            "[ERRO] Fase 10E não reconhecida em "
            f"{path.name}"
        )

print(
    "      [OK] Fase 10E reconhecida."
)


print(
    "[1/11] Verificando consumidores do service..."
)

consumers = module_consumers()

for consumer in consumers:
    print(
        f"      - {consumer}"
    )

expected_consumers = [
    Path("routers") / "historico.py"
]

if consumers != expected_consumers:
    print()
    print(
        "[ERRO] Consumidores inesperados de "
        "services.historico_inventarios."
    )
    print(
        "[INFO] Nenhum arquivo foi alterado."
    )
    raise SystemExit(1)

print(
    "      [OK] consumidor único."
)


print(
    "[2/11] Analisando service real..."
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
    "      statuses HTTP encontrados: "
    f"{s_diag.get('http_statuses', [])}"
)
print(
    "      domain raises encontrados: "
    f"{s_diag.get('domain_raises', [])}"
)

if s_state == "DESCONHECIDO":
    raise SystemExit(
        "[ERRO] Baseline do service "
        f"desconhecida: {s_diag}"
    )


if s_state == "LEGADO":
    statuses = s_diag[
        "http_statuses"
    ]

    unsupported = [
        status
        for status in statuses
        if status not in EXC_BY_STATUS
    ]

    if unsupported:
        raise SystemExit(
            "[ERRO] Status fora do escopo "
            f"da 10F: {unsupported}"
        )

    required_classes = sorted(
        {
            EXC_BY_STATUS[status]
            for status in statuses
        }
    )

else:
    required_classes = sorted(
        set(
            s_diag[
                "domain_raises"
            ]
        )
    )

    status_from_class = {
        value: key
        for key, value in EXC_BY_STATUS.items()
    }

    statuses = [
        status_from_class[name]
        for name in required_classes
    ]


print(
    "[3/11] Analisando endpoint do router..."
)

router_text = read_text(
    ROUTER
)

if s_state == "LEGADO":
    r_state, r_diag = router_state(
        router_text
    )
else:
    r_state, r_diag = router_state(
        router_text,
        required_exceptions=set(
            required_classes
        ),
    )

print(
    f"      Estado: {r_state}"
)
print(
    f"      handlers: {r_diag}"
)

if r_state == "DESCONHECIDO":
    raise SystemExit(
        "[ERRO] Baseline do router "
        f"desconhecida: {r_diag}"
    )


if (
    s_state == "MIGRADO"
    and
    r_state == "MIGRADO"
):
    print(
        "[4/11] Fase 10F já aplicada."
    )
    print(
        "      [OK] nenhuma alteração necessária."
    )
    raise SystemExit(0)


if not (
    s_state == "LEGADO"
    and
    r_state == "LEGADO"
):
    raise SystemExit(
        "[ERRO] Migração parcial detectada. "
        "Nenhum arquivo será alterado."
    )


print(
    "[4/11] Mapeando exceções semânticas..."
)

for status in statuses:
    print(
        f"      HTTP {status} -> "
        f"{EXC_BY_STATUS[status]}"
    )

print(
    "      [OK] todos os statuses suportados."
)


print(
    "[5/11] Registrando conexão/transação..."
)

before_conn = {
    token: router_text.count(token)
    for token in PROTECTED_TOKENS
}

for token, count in before_conn.items():
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
        + "_backup_fase10f_"
        + timestamp
        + ".py"
    )
)

router_backup = (
    ROUTER.parent
    / (
        ROUTER.stem
        + "_backup_fase10f_"
        + timestamp
        + ".py"
    )
)

print(
    "[6/11] Criando backups..."
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
        "[7/11] Migrando service..."
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
        "      [OK] 2 HTTPException "
        "migrados preservando detail."
    )


    print(
        "[8/11] Adaptando endpoint do router..."
    )

    patched_router = patch_router(
        router_text,
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

    print(
        "      [OK] exceções traduzidas "
        "para os mesmos status HTTP."
    )


    print(
        "[9/11] Validando service final..."
    )

    final_service = read_text(
        SERVICE
    )

    s2, sd2 = service_state(
        final_service
    )

    if s2 != "MIGRADO":
        raise RuntimeError(
            f"Service final inválido: {sd2}"
        )

    if (
        "from fastapi import HTTPException"
        in final_service
    ):
        raise RuntimeError(
            "Service ainda importa FastAPI."
        )

    if len(
        sd2["domain_raises"]
    ) != 2:
        raise RuntimeError(
            "Esperados 2 raises de domínio."
        )

    print(
        "      [OK] service sem FastAPI."
    )


    print(
        "[10/11] Validando router e conexão..."
    )

    final_router = read_text(
        ROUTER
    )

    r2, rd2 = router_state(
        final_router,
        required_exceptions=set(
            required_classes
        ),
    )

    if r2 != "MIGRADO":
        raise RuntimeError(
            f"Router final inválido: {rd2}"
        )

    after_conn = {
        token: final_router.count(token)
        for token in PROTECTED_TOKENS
    }

    if before_conn != after_conn:
        raise RuntimeError(
            "Conexão/transação foi alterada."
        )

    for status in set(statuses):
        if (
            f"status_code={status}"
            not in final_router
        ):
            raise RuntimeError(
                f"Tradução HTTP {status} ausente."
            )

    print(
        "      [OK] status HTTP preservados."
    )
    print(
        "      [OK] conexão/transação inalteradas."
    )


    print(
        "[11/11] Revalidando consumidores..."
    )

    if module_consumers() != expected_consumers:
        raise RuntimeError(
            "Mapa de consumidores mudou."
        )

    print(
        "      [OK] consumidor único preservado."
    )


except Exception:
    print()
    print(
        "[ERRO] Falha durante Fase 10F."
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
    "[OK] Fase 10F aplicada."
)
print(
    "[OK] services/historico_inventarios.py "
    "desacoplado de FastAPI."
)
print(
    "[OK] 2 HTTPException migrados "
    "para exceções semânticas."
)
print(
    "[OK] mesmos status HTTP preservados no router."
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
