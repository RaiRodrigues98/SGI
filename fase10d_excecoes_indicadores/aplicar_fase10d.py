
"""
FASE 10D - DESACOPLAMENTO HTTP DOS INDICADORES OPERACIONAIS

Escopo:
- services/indicadores_operacionais.py
- routers/indicadores.py

Regras:
- o único HTTPException do service deve ser 404;
- converte para NotFoundError;
- identifica automaticamente os endpoints do router que chamam
  funções importadas de services.indicadores_operacionais;
- traduz NotFoundError -> HTTP 404 somente nesses endpoints;
- não altera SQL, conexão, UoW, commit ou rollback;
- bloqueia se houver consumidores do service fora de routers/indicadores.py.

Execute:
python .\fase10d_excecoes_indicadores\aplicar_fase10d.py
"""

from pathlib import Path
from datetime import datetime
import ast
import py_compile
import shutil

ROOT = Path.cwd()

SERVICE = ROOT / "services" / "indicadores_operacionais.py"
ROUTER = ROOT / "routers" / "indicadores.py"
DOMAIN_EXCEPTIONS = ROOT / "domain" / "exceptions.py"
RESULTADO_SERVICE = ROOT / "services" / "resultado_final.py"

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

EXPECTED_DETAIL_TOKENS = [
    "Inventário ou rodada não encontrado.",
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


def handler_name(node):
    if node.type is None:
        return None

    if isinstance(node.type, ast.Name):
        return node.type.id

    if isinstance(node.type, ast.Attribute):
        return node.type.attr

    return None


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
        and http_raises == 1
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
        and notfound_raises == 1
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


def imported_service_functions(tree):
    result = {}

    for node in tree.body:
        if not isinstance(node, ast.ImportFrom):
            continue

        if (
            (node.module or "")
            != "services.indicadores_operacionais"
        ):
            continue

        for alias in node.names:
            local = alias.asname or alias.name
            result[local] = alias.name

    return result


def function_calls_names(fn_node):
    names = set()

    for node in ast.walk(fn_node):
        if not isinstance(node, ast.Call):
            continue

        if isinstance(node.func, ast.Name):
            names.add(node.func.id)

    return names


def target_router_functions(text):
    tree = parse(
        text,
        "routers/indicadores.py",
    )

    service_imports = imported_service_functions(
        tree
    )

    if not service_imports:
        raise RuntimeError(
            "Router não importa funções de "
            "services.indicadores_operacionais."
        )

    target_names = set(
        service_imports.keys()
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

        calls = function_calls_names(
            node
        )

        used = sorted(
            calls.intersection(
                target_names
            )
        )

        if not used:
            continue

        http_handlers = []
        notfound_handlers = []

        for inner in ast.walk(node):
            if not isinstance(
                inner,
                ast.ExceptHandler,
            ):
                continue

            name = handler_name(
                inner
            )

            if name == "HTTPException":
                http_handlers.append(
                    inner
                )

            if name == "NotFoundError":
                notfound_handlers.append(
                    inner
                )

        result.append(
            {
                "node": node,
                "name": node.name,
                "line": node.lineno,
                "used_services": used,
                "http_handlers": http_handlers,
                "notfound_handlers": notfound_handlers,
            }
        )

    if not result:
        raise RuntimeError(
            "Nenhum endpoint consumidor foi reconhecido."
        )

    return result


def router_state(text):
    domain_import = (
        "from domain.exceptions import NotFoundError"
        in text
    )

    targets = target_router_functions(
        text
    )

    legacy_ok = True
    migrated_ok = True

    for item in targets:
        if (
            len(item["http_handlers"]) != 1
            or
            len(item["notfound_handlers"]) != 0
        ):
            legacy_ok = False

        if (
            len(item["http_handlers"]) != 1
            or
            len(item["notfound_handlers"]) != 1
        ):
            migrated_ok = False

    if (
        not domain_import
        and legacy_ok
    ):
        return "LEGADO", {
            "targets": [
                item["name"]
                for item in targets
            ],
            "count": len(targets),
        }

    if (
        domain_import
        and migrated_ok
    ):
        return "MIGRADO", {
            "targets": [
                item["name"]
                for item in targets
            ],
            "count": len(targets),
        }

    return "DESCONHECIDO", {
        "domain_import": domain_import,
        "targets": [
            {
                "name": item["name"],
                "http_handlers":
                    len(item["http_handlers"]),
                "notfound_handlers":
                    len(item["notfound_handlers"]),
            }
            for item in targets
        ],
    }


def validate_service_detail(text):
    for token in EXPECTED_DETAIL_TOKENS:
        if token not in text:
            raise RuntimeError(
                "Mensagem esperada ausente: "
                + repr(token)
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


def find_module_consumers():
    consumers = []

    for path in ROOT.rglob("*.py"):
        if is_excluded(path):
            continue

        if path == SERVICE:
            continue

        text = read_text(path)

        if (
            "services.indicadores_operacionais"
            not in text
        ):
            continue

        tree = parse(
            text,
            str(path),
        )

        imports_module = False

        for node in ast.walk(tree):
            if (
                isinstance(node, ast.ImportFrom)
                and
                (node.module or "")
                == "services.indicadores_operacionais"
            ):
                imports_module = True
                break

        if imports_module:
            consumers.append(
                path.relative_to(ROOT)
            )

    return sorted(
        set(consumers),
        key=lambda p: str(p),
    )


def patch_service(text):
    state, diag = service_state(
        text
    )

    if state != "LEGADO":
        raise RuntimeError(
            "Service não está em baseline "
            f"legada: {state} / {diag}"
        )

    validate_service_detail(
        text
    )

    tree = parse(
        text,
        "services/indicadores_operacionais.py",
    )

    lines = text.splitlines()
    replacements = []

    for node in ast.walk(tree):
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
            isinstance(
                status,
                ast.Constant,
            )
            and
            status.value == 404
        ):
            raise RuntimeError(
                "HTTPException do service "
                "não é 404."
            )

        detail_source = (
            ast.get_source_segment(
                text,
                detail,
            )
        )

        if not detail_source:
            raise RuntimeError(
                "Não foi possível recuperar detail."
            )

        indent = (
            " " * node.col_offset
        )

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

    if len(replacements) != 1:
        raise RuntimeError(
            "Esperada exatamente 1 conversão, "
            f"encontradas {len(replacements)}."
        )

    start, end, replacement = (
        replacements[0]
    )

    out = []
    out.extend(
        lines[
            :start - 1
        ]
    )
    out.extend(
        replacement.splitlines()
    )
    out.extend(
        lines[
            end:
        ]
    )

    patched = "\n".join(
        out
    )

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

    validate_service_detail(
        patched
    )

    return patched


def insert_domain_import(text):
    if (
        "from domain.exceptions import NotFoundError"
        in text
    ):
        return text

    tree = parse(
        text,
        "routers/indicadores.py",
    )

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
            "Import FastAPI não encontrado."
        )

    lines = text.splitlines()

    lines.insert(
        fastapi_import.end_lineno,
        (
            "from domain.exceptions import "
            "NotFoundError"
        ),
    )

    result = "\n".join(
        lines
    )

    if text.endswith("\n"):
        result += "\n"

    return result


def patch_router(text):
    state, diag = router_state(
        text
    )

    if state != "LEGADO":
        raise RuntimeError(
            "Router não está em baseline "
            f"legada: {state} / {diag}"
        )

    # Guarda contadores de conexão/transação.
    protected_tokens = [
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

    before_counts = {
        token: text.count(token)
        for token in protected_tokens
    }

    patched = insert_domain_import(
        text
    )

    targets = target_router_functions(
        patched
    )

    # Após inserir import, linhas mudam em +1.
    # Reparse já ocorreu em target_router_functions,
    # então usamos os novos linenos.
    insertions = []

    for item in targets:
        if len(
            item["http_handlers"]
        ) != 1:
            raise RuntimeError(
                f"{item['name']}: esperado 1 "
                "except HTTPException."
            )

        if item[
            "notfound_handlers"
        ]:
            raise RuntimeError(
                f"{item['name']}: NotFoundError "
                "já presente de forma inesperada."
            )

        http_handler = (
            item["http_handlers"][0]
        )

        indent = (
            " " * http_handler.col_offset
        )

        block = (
            f"{indent}except NotFoundError as erro:\n\n"
            f"{indent}    raise HTTPException(\n"
            f"{indent}        status_code=404,\n"
            f"{indent}        detail=str(erro)\n"
            f"{indent}    )\n\n"
        )

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
        key=lambda x: x[0],
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

    state2, diag2 = router_state(
        result
    )

    if state2 != "MIGRADO":
        raise RuntimeError(
            "Router pós-patch inválido: "
            f"{state2} / {diag2}"
        )

    after_counts = {
        token: result.count(token)
        for token in protected_tokens
    }

    if before_counts != after_counts:
        differences = {
            token: (
                before_counts[token],
                after_counts[token],
            )
            for token in protected_tokens
            if (
                before_counts[token]
                != after_counts[token]
            )
        }

        raise RuntimeError(
            "Conexão/transação foi alterada: "
            f"{differences}"
        )

    return result


print(
    "[0/11] Validando pré-requisitos..."
)

for path in [
    DOMAIN_EXCEPTIONS,
    RESULTADO_SERVICE,
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

if (
    "class NotFoundError(DomainError)"
    not in domain_text
):
    raise SystemExit(
        "[ERRO] NotFoundError da Fase 10B "
        "não reconhecido."
    )

resultado_text = read_text(
    RESULTADO_SERVICE
)

if (
    "NotFoundError"
    not in resultado_text
    or
    "from fastapi import HTTPException"
    in resultado_text
):
    raise SystemExit(
        "[ERRO] Fase 10C não reconhecida em "
        "services/resultado_final.py."
    )

print(
    "      [OK] Fases 10B/10C reconhecidas."
)


print(
    "[1/11] Verificando consumidores do módulo..."
)

consumers = find_module_consumers()

for consumer in consumers:
    print(
        f"      - {consumer}"
    )

expected = [
    Path("routers") / "indicadores.py"
]

if consumers != expected:
    print()
    print(
        "[ERRO] Consumidores inesperados "
        "de services.indicadores_operacionais."
    )
    print(
        "[INFO] Nenhum arquivo foi alterado."
    )
    raise SystemExit(1)

print(
    "      [OK] módulo consumido somente "
    "por routers/indicadores.py."
)


print(
    "[2/11] Analisando service..."
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
        "[ERRO] Baseline do service "
        f"desconhecida: {s_diag}"
    )


print(
    "[3/11] Analisando router..."
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
    "      endpoints consumidores: "
    f"{r_diag.get('count', 0)}"
)

for name in r_diag.get(
    "targets",
    []
):
    if isinstance(name, str):
        print(
            f"        - {name}"
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
        "[4/11] Fase 10D já aplicada."
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
    "[4/11] Validando HTTP 404 do service..."
)

tree = parse(
    service_text,
    "services/indicadores_operacionais.py",
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
        if (
            kw.arg == "status_code"
            and
            isinstance(
                kw.value,
                ast.Constant,
            )
        ):
            statuses.append(
                kw.value.value
            )

if statuses != [404]:
    raise SystemExit(
        "[ERRO] Status inesperado: "
        f"{statuses}"
    )

validate_service_detail(
    service_text
)

print(
    "      [OK] único erro = HTTP 404."
)


print(
    "[5/11] Registrando fronteira "
    "de conexão/transação..."
)

protected_tokens = [
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

before_connection = {
    token: router_text.count(token)
    for token in protected_tokens
}

for token, count in (
    before_connection.items()
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

backups = {}

print(
    "[6/11] Criando backups..."
)

for key, path in [
    ("service", SERVICE),
    ("router", ROUTER),
]:
    backup = (
        path.parent
        /
        (
            path.stem
            + "_backup_fase10d_"
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
        "[7/11] Migrando service..."
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
        "      [OK] HTTPException -> NotFoundError."
    )


    print(
        "[8/11] Adaptando endpoints do router..."
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

    final_state, final_diag = (
        router_state(
            patched_router
        )
    )

    if final_state != "MIGRADO":
        raise RuntimeError(
            f"Router final inválido: {final_diag}"
        )

    print(
        "      [OK] endpoints adaptados: "
        f"{final_diag['count']}"
    )


    print(
        "[9/11] Validando contrato HTTP..."
    )

    final_service = read_text(
        SERVICE
    )

    final_router = read_text(
        ROUTER
    )

    s2, sd2 = service_state(
        final_service
    )

    if s2 != "MIGRADO":
        raise RuntimeError(
            f"Service final inválido: {sd2}"
        )

    if "fastapi" in final_service.lower():
        raise RuntimeError(
            "Service ainda depende de FastAPI."
        )

    if (
        "status_code=404"
        not in final_router
        or
        "detail=str(erro)"
        not in final_router
    ):
        raise RuntimeError(
            "Tradução HTTP 404 ausente."
        )

    validate_service_detail(
        final_service
    )

    print(
        "      [OK] HTTP 404 preservado."
    )
    print(
        "      [OK] mensagem preservada."
    )


    print(
        "[10/11] Validando conexão/transação..."
    )

    after_connection = {
        token: final_router.count(token)
        for token in protected_tokens
    }

    if (
        before_connection
        != after_connection
    ):
        raise RuntimeError(
            "Fronteira de conexão/transação "
            "foi modificada."
        )

    print(
        "      [OK] conexão/transação inalteradas."
    )


    print(
        "[11/11] Revalidando consumidores..."
    )

    final_consumers = (
        find_module_consumers()
    )

    if final_consumers != expected:
        raise RuntimeError(
            "Mapa de consumidores mudou: "
            f"{final_consumers}"
        )

    print(
        "      [OK] consumidor único preservado."
    )


except Exception:
    print()
    print(
        "[ERRO] Falha durante a Fase 10D."
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
    "[OK] Fase 10D aplicada."
)
print(
    "[OK] services/indicadores_operacionais.py "
    "desacoplado de FastAPI."
)
print(
    "[OK] NotFoundError traduzido para HTTP 404 "
    "nos endpoints consumidores."
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
