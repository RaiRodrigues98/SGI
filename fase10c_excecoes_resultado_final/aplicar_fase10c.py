
"""
FASE 10C - DESACOPLAMENTO HTTP DO RESULTADO FINAL

Escopo:
- services/resultado_final.py
- routers/resultado_final.py

Pré-requisito:
- Fase 10B aplicada
- domain/exceptions.py existente

Decisão:
- os 2 HTTPException do service são 404
- convertem para NotFoundError
- o router traduz NotFoundError -> HTTP 404
- conexão/transação do router NÃO é alterada
- consumidores inesperados bloqueiam a instalação
"""

from pathlib import Path
from datetime import datetime
import ast
import py_compile
import shutil

ROOT = Path.cwd()

SERVICE = ROOT / "services" / "resultado_final.py"
ROUTER = ROOT / "routers" / "resultado_final.py"
DOMAIN_EXCEPTIONS = ROOT / "domain" / "exceptions.py"
INVENTARIOS_SERVICE = ROOT / "services" / "inventarios.py"

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

EXPECTED_MESSAGES = [
    "Inventário não encontrado.",
    "O inventário ainda não possui ",
    "resultado final consolidado.",
]

EXPECTED_ROUTER_TOKENS = [
    '"/inventarios/{id_inventario}/resultado-final"',
    "consultar_resultado_final(",
    "HTTPException",
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


def count_raises(text, exc_name):
    tree = parse(text, "arquivo")

    return sum(
        1
        for node in ast.walk(tree)
        if isinstance(node, ast.Raise)
        and node.exc is not None
        and raised_name(node.exc) == exc_name
    )


def handler_count(text, exc_name):
    tree = parse(text, "router")
    total = 0

    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue

        if (
            isinstance(node.type, ast.Name)
            and node.type.id == exc_name
        ):
            total += 1

    return total


def service_state(text):
    http_import = (
        "from fastapi import HTTPException"
        in text
    )

    domain_import = (
        "from domain.exceptions import NotFoundError"
        in text
    )

    http_raises = count_raises(
        text,
        "HTTPException",
    )

    notfound_raises = count_raises(
        text,
        "NotFoundError",
    )

    if (
        http_import
        and http_raises == 2
        and notfound_raises == 0
    ):
        return "LEGADO", {
            "http_raises": http_raises,
            "notfound_raises": notfound_raises,
        }

    if (
        not http_import
        and domain_import
        and http_raises == 0
        and notfound_raises == 2
    ):
        return "MIGRADO", {
            "http_raises": http_raises,
            "notfound_raises": notfound_raises,
        }

    return "DESCONHECIDO", {
        "http_import": http_import,
        "domain_import": domain_import,
        "http_raises": http_raises,
        "notfound_raises": notfound_raises,
    }


def router_state(text):
    notfound_import = (
        "from domain.exceptions import NotFoundError"
        in text
    )

    notfound_handlers = handler_count(
        text,
        "NotFoundError",
    )

    http_handlers = handler_count(
        text,
        "HTTPException",
    )

    if (
        not notfound_import
        and notfound_handlers == 0
        and http_handlers >= 1
    ):
        return "LEGADO", {
            "notfound_handlers": 0,
            "http_handlers": http_handlers,
        }

    if (
        notfound_import
        and notfound_handlers == 1
        and http_handlers >= 1
    ):
        return "MIGRADO", {
            "notfound_handlers": notfound_handlers,
            "http_handlers": http_handlers,
        }

    return "DESCONHECIDO", {
        "notfound_import": notfound_import,
        "notfound_handlers": notfound_handlers,
        "http_handlers": http_handlers,
    }


def validate_messages(text):
    for token in EXPECTED_MESSAGES:
        if token not in text:
            raise RuntimeError(
                "Mensagem esperada ausente: "
                + repr(token)
            )


def validate_router_contract(text):
    for token in EXPECTED_ROUTER_TOKENS:
        if token not in text:
            raise RuntimeError(
                "Contrato esperado ausente em "
                "routers/resultado_final.py: "
                + repr(token)
            )

    # Esta fase não altera ownership de conexão/transação.
    if "conn.commit()" in text or "uow.commit()" in text:
        raise RuntimeError(
            "resultado_final é leitura, mas commit foi encontrado."
        )

    if "conn.rollback()" in text or "uow.rollback()" in text:
        raise RuntimeError(
            "resultado_final é leitura, mas rollback foi encontrado."
        )


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


def find_consumers():
    consumers = []

    for path in ROOT.rglob("*.py"):
        if is_excluded(path):
            continue

        if path == SERVICE:
            continue

        text = read_text(path)

        if (
            "services.resultado_final"
            not in text
            and "consultar_resultado_final"
            not in text
        ):
            continue

        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue

        imports_function = False
        calls_function = False

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if (
                    (node.module or "")
                    == "services.resultado_final"
                ):
                    for alias in node.names:
                        if (
                            alias.name
                            == "consultar_resultado_final"
                        ):
                            imports_function = True

            if isinstance(node, ast.Call):
                if (
                    isinstance(node.func, ast.Name)
                    and
                    node.func.id
                    == "consultar_resultado_final"
                ):
                    calls_function = True

        if imports_function or calls_function:
            consumers.append(
                path.relative_to(ROOT)
            )

    return sorted(
        set(consumers),
        key=lambda p: str(p),
    )


def patch_service(text):
    state, diag = service_state(text)

    if state != "LEGADO":
        raise RuntimeError(
            f"Service não está legado: {state} / {diag}"
        )

    validate_messages(text)

    tree = parse(
        text,
        "services/resultado_final.py",
    )

    lines = text.splitlines()
    replacements = []

    for node in ast.walk(tree):
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
                "HTTPException sem status/detail."
            )

        if not (
            isinstance(status_node, ast.Constant)
            and status_node.value == 404
        ):
            raise RuntimeError(
                "HTTPException com status diferente de 404 "
                "encontrado no service."
            )

        detail_source = ast.get_source_segment(
            text,
            detail_node,
        )

        if not detail_source:
            raise RuntimeError(
                "Não foi possível recuperar detail."
            )

        indent = " " * node.col_offset

        replacement = (
            f"{indent}raise NotFoundError(\n"
            f"{indent}    {detail_source}\n"
            f"{indent})"
        )

        replacements.append(
            (
                node.lineno,
                node.end_lineno,
                replacement,
            )
        )

    if len(replacements) != 2:
        raise RuntimeError(
            "Esperadas 2 conversões, "
            f"encontradas {len(replacements)}."
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

    patched = "\n".join(out)

    if text.endswith("\n"):
        patched += "\n"

    patched = patched.replace(
        "from fastapi import HTTPException",
        "from domain.exceptions import NotFoundError",
        1,
    )

    state2, diag2 = service_state(
        patched
    )

    if state2 != "MIGRADO":
        raise RuntimeError(
            "Service pós-patch inválido: "
            f"{state2} / {diag2}"
        )

    validate_messages(patched)

    return patched


def patch_router(text):
    state, diag = router_state(text)

    if state != "LEGADO":
        raise RuntimeError(
            f"Router não está legado: {state} / {diag}"
        )

    validate_router_contract(text)

    # Import sem tocar no mecanismo de conexão.
    service_anchor = (
        "from services.resultado_final import ("
    )

    single_anchor = (
        "from services.resultado_final import "
        "consultar_resultado_final"
    )

    if service_anchor in text:
        patched = text.replace(
            service_anchor,
            (
                "from domain.exceptions import "
                "NotFoundError\n\n"
                + service_anchor
            ),
            1,
        )

    elif single_anchor in text:
        patched = text.replace(
            single_anchor,
            (
                "from domain.exceptions import "
                "NotFoundError\n\n"
                + single_anchor
            ),
            1,
        )

    else:
        # Fallback seguro: depois do bloco/import FastAPI.
        marker = "from fastapi import"

        if marker not in text:
            raise RuntimeError(
                "Não foi possível posicionar import "
                "NotFoundError."
            )

        lines = text.splitlines()

        insert_at = None

        # Encontra o fim do primeiro import FastAPI.
        tree = parse(text, "router")

        for node in tree.body:
            if isinstance(node, ast.ImportFrom):
                if (
                    (node.module or "")
                    == "fastapi"
                ):
                    insert_at = node.end_lineno
                    break

        if insert_at is None:
            raise RuntimeError(
                "Import FastAPI não reconhecido."
            )

        lines.insert(
            insert_at,
            (
                "from domain.exceptions import "
                "NotFoundError"
            ),
        )

        patched = "\n".join(lines)

        if text.endswith("\n"):
            patched += "\n"

    marker = "    except HTTPException:"

    if patched.count(marker) != 1:
        raise RuntimeError(
            "Esperado exatamente 1 "
            "except HTTPException no router."
        )

    handler = (
        "    except NotFoundError as erro:\n\n"
        "        raise HTTPException(\n"
        "            status_code=404,\n"
        "            detail=str(erro)\n"
        "        )\n\n"
    )

    patched = patched.replace(
        marker,
        handler + marker,
        1,
    )

    state2, diag2 = router_state(
        patched
    )

    if state2 != "MIGRADO":
        raise RuntimeError(
            "Router pós-patch inválido: "
            f"{state2} / {diag2}"
        )

    validate_router_contract(patched)

    return patched


print(
    "[0/10] Validando pré-requisitos da Fase 10B..."
)

for path in [
    DOMAIN_EXCEPTIONS,
    INVENTARIOS_SERVICE,
    SERVICE,
    ROUTER,
]:
    if not path.exists():
        raise SystemExit(
            f"[ERRO] Arquivo ausente: {path}"
        )

domain_text = read_text(
    DOMAIN_EXCEPTIONS
)

for token in [
    "class DomainError(Exception)",
    "class BusinessRuleViolation(DomainError)",
    "class NotFoundError(DomainError)",
]:
    if token not in domain_text:
        raise SystemExit(
            "[ERRO] Fase 10B não reconhecida em "
            "domain/exceptions.py."
        )

inventarios_text = read_text(
    INVENTARIOS_SERVICE
)

if (
    "BusinessRuleViolation"
    not in inventarios_text
    or
    "from fastapi import HTTPException"
    in inventarios_text
):
    raise SystemExit(
        "[ERRO] Fase 10B não reconhecida em "
        "services/inventarios.py."
    )

print(
    "      [OK] Fase 10B reconhecida."
)


print(
    "[1/10] Verificando consumidores de consultar_resultado_final..."
)

consumers = find_consumers()

print(
    "      consumidores encontrados: "
    f"{len(consumers)}"
)

for consumer in consumers:
    print(
        f"        - {consumer}"
    )

expected_consumer = Path(
    "routers"
) / "resultado_final.py"

if consumers != [expected_consumer]:
    print()
    print(
        "[ERRO] Consumidores inesperados detectados."
    )
    print(
        "[INFO] Nenhum arquivo foi alterado."
    )
    raise SystemExit(1)

print(
    "      [OK] fluxo vertical isolado."
)


print(
    "[2/10] Analisando services/resultado_final.py..."
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
    "      HTTPException: "
    f"{s_diag.get('http_raises', 0)}"
)
print(
    "      NotFoundError: "
    f"{s_diag.get('notfound_raises', 0)}"
)

if s_state == "DESCONHECIDO":
    raise SystemExit(
        "[ERRO] Baseline do service desconhecida: "
        f"{s_diag}"
    )


print(
    "[3/10] Analisando routers/resultado_final.py..."
)

router_text = read_text(
    ROUTER
)

r_state, r_diag = router_state(
    router_text
)

print(
    f"      Estado: {r_state}"
)
print(
    "      NotFound handlers: "
    f"{r_diag.get('notfound_handlers', 0)}"
)
print(
    "      HTTPException handlers: "
    f"{r_diag.get('http_handlers', 0)}"
)

if r_state == "DESCONHECIDO":
    raise SystemExit(
        "[ERRO] Baseline do router desconhecida: "
        f"{r_diag}"
    )

validate_router_contract(
    router_text
)


if (
    s_state == "MIGRADO"
    and
    r_state == "MIGRADO"
):
    print(
        "[4/10] Fase 10C já aplicada."
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
    "[4/10] Validando statuses do service..."
)

tree = parse(
    service_text,
    "services/resultado_final.py",
)

statuses = []

for node in ast.walk(tree):
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
        if kw.arg == "status_code":
            if isinstance(
                kw.value,
                ast.Constant,
            ):
                statuses.append(
                    kw.value.value
                )

if statuses != [404, 404]:
    raise SystemExit(
        "[ERRO] Status HTTP inesperados "
        f"no service: {statuses}"
    )

print(
    "      [OK] 2 erros 404 confirmados."
)


timestamp = (
    datetime.now()
    .strftime(
        "%Y%m%d_%H%M%S"
    )
)

backups = {}

print(
    "[5/10] Criando backups..."
)

for key, path in [
    ("service", SERVICE),
    ("router", ROUTER),
]:
    backup = (
        path.parent
        / (
            path.stem
            + "_backup_fase10c_"
            + timestamp
            + ".py"
        )
    )

    shutil.copy2(
        path,
        backup,
    )

    backups[key] = backup

    print(
        f"      {path.name} -> "
        f"{backup.name}"
    )


try:
    print(
        "[6/10] Migrando services/resultado_final.py..."
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
        "      [OK] 2 HTTPException -> NotFoundError."
    )


    print(
        "[7/10] Adaptando routers/resultado_final.py..."
    )

    patched_router = patch_router(
        router_text
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
        "      [OK] NotFoundError -> HTTP 404."
    )


    print(
        "[8/10] Validando que conexão/transação não mudou..."
    )

    final_router = read_text(
        ROUTER
    )

    connection_tokens = [
        "get_connection()",
        "SqlServerUnitOfWork()",
        "uow.open()",
        "conn.cursor()",
        "uow.cursor",
        "cursor.close()",
        "conn.close()",
        "uow.close()",
    ]

    for token in connection_tokens:
        if (
            router_text.count(token)
            !=
            final_router.count(token)
        ):
            raise RuntimeError(
                "Ownership de conexão foi alterado: "
                f"{token}"
            )

    for token in [
        "conn.commit()",
        "conn.rollback()",
        "uow.commit()",
        "uow.rollback()",
    ]:
        if (
            router_text.count(token)
            !=
            final_router.count(token)
        ):
            raise RuntimeError(
                "Fronteira transacional foi alterada: "
                f"{token}"
            )

    print(
        "      [OK] ownership de conexão preservado."
    )
    print(
        "      [OK] 0 commit/rollback preservados."
    )


    print(
        "[9/10] Validando contratos HTTP..."
    )

    final_service = read_text(
        SERVICE
    )

    s2, sd2 = service_state(
        final_service
    )

    r2, rd2 = router_state(
        final_router
    )

    if s2 != "MIGRADO":
        raise RuntimeError(
            f"Service final inválido: {sd2}"
        )

    if r2 != "MIGRADO":
        raise RuntimeError(
            f"Router final inválido: {rd2}"
        )

    if "fastapi" in final_service.lower():
        raise RuntimeError(
            "Service ainda depende de FastAPI."
        )

    validate_messages(
        final_service
    )

    for token in [
        "status_code=404",
        "detail=str(erro)",
        '"/inventarios/{id_inventario}/resultado-final"',
    ]:
        if token not in final_router:
            raise RuntimeError(
                "Contrato HTTP perdido: "
                + repr(token)
            )

    print(
        "      [OK] HTTP 404 preservado."
    )
    print(
        "      [OK] mensagens preservadas."
    )
    print(
        "      [OK] rota preservada."
    )


    print(
        "[10/10] Revalidando consumidores..."
    )

    final_consumers = find_consumers()

    if final_consumers != [
        expected_consumer
    ]:
        raise RuntimeError(
            "Mapa de consumidores mudou: "
            f"{final_consumers}"
        )

    print(
        "      [OK] apenas router resultado_final consome o service."
    )


except Exception:
    print()
    print(
        "[ERRO] Falha durante a Fase 10C."
    )
    print(
        "[INFO] Restaurando arquivos..."
    )

    shutil.copy2(
        backups["service"],
        SERVICE,
    )

    shutil.copy2(
        backups["router"],
        ROUTER,
    )

    print(
        "[OK] Estado anterior restaurado."
    )

    raise


print()
print(
    "[OK] Fase 10C aplicada."
)
print(
    "[OK] services/resultado_final.py desacoplado de FastAPI."
)
print(
    "[OK] 2 erros migrados para NotFoundError."
)
print(
    "[OK] routers/resultado_final.py mantém HTTP 404."
)
print(
    "[OK] conexão/transação permaneceram inalteradas."
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
