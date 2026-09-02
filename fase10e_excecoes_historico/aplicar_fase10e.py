
"""
FASE 10E - DESACOPLAMENTO HTTP DO HISTÓRICO (BAIXO RISCO)

Escopo:
- services/historico_itens.py
- services/historico_localizacoes.py
- services/historico_divergencias.py
- routers/historico.py

Mudanças:
- historico_itens: HTTP 400 -> BusinessRuleViolation
- historico_localizacoes: HTTP 400 -> BusinessRuleViolation
- historico_divergencias: remove import HTTPException não utilizado
- router: traduz BusinessRuleViolation -> HTTP 400 apenas nos endpoints
  consumidores dos dois services migrados

Não altera:
- SQL
- conexão/UoW
- cursor
- commit/rollback
- rotas
- respostas de sucesso

Execute:
python .\fase10e_excecoes_historico\aplicar_fase10e.py
"""

from pathlib import Path
from datetime import datetime
import ast
import py_compile
import shutil

ROOT = Path.cwd()

DOMAIN = ROOT / "domain" / "exceptions.py"
PREV_SERVICE = ROOT / "services" / "indicadores_operacionais.py"

ROUTER = ROOT / "routers" / "historico.py"

SERVICES = {
    "historico_itens": {
        "path": ROOT / "services" / "historico_itens.py",
        "function": "consultar_historico_item",
        "expected_status": 400,
        "expected_raises": 1,
        "message_tokens": [
            "O código do item é obrigatório.",
        ],
    },
    "historico_localizacoes": {
        "path": ROOT / "services" / "historico_localizacoes.py",
        "function": "consultar_historico_localizacao",
        "expected_status": 400,
        "expected_raises": 1,
        "message_tokens": [
            "A localização é obrigatória.",
        ],
    },
}

DIVERGENCIAS = ROOT / "services" / "historico_divergencias.py"

EXCLUDED_DIRS = {
    ".git", ".venv", "venv", "__pycache__",
    ".pytest_cache", ".mypy_cache", ".ruff_cache",
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


def service_state(text, config):
    http_import = (
        "from fastapi import HTTPException"
        in text
    )

    domain_import = (
        "from domain.exceptions import BusinessRuleViolation"
        in text
    )

    http_raises = count_raises(
        text,
        "HTTPException",
    )

    business_raises = count_raises(
        text,
        "BusinessRuleViolation",
    )

    expected = config["expected_raises"]

    if (
        http_import
        and http_raises == expected
        and business_raises == 0
    ):
        return "LEGADO", {
            "http_raises": http_raises,
            "business_raises": business_raises,
        }

    if (
        not http_import
        and domain_import
        and http_raises == 0
        and business_raises == expected
    ):
        return "MIGRADO", {
            "http_raises": http_raises,
            "business_raises": business_raises,
        }

    return "DESCONHECIDO", {
        "http_import": http_import,
        "domain_import": domain_import,
        "http_raises": http_raises,
        "business_raises": business_raises,
    }


def divergencias_state(text):
    http_import = (
        "from fastapi import HTTPException"
        in text
    )

    occurrences = text.count(
        "HTTPException"
    )

    if http_import and occurrences == 1:
        return "LEGADO", {
            "occurrences": occurrences,
        }

    if not http_import and occurrences == 0:
        return "MIGRADO", {
            "occurrences": occurrences,
        }

    return "DESCONHECIDO", {
        "http_import": http_import,
        "occurrences": occurrences,
    }


def imported_service_functions(tree):
    result = {}

    target_modules = {
        "services.historico_itens",
        "services.historico_localizacoes",
    }

    for node in tree.body:
        if not isinstance(node, ast.ImportFrom):
            continue

        module = node.module or ""

        if module not in target_modules:
            continue

        for alias in node.names:
            local = alias.asname or alias.name
            result[local] = {
                "module": module,
                "original": alias.name,
            }

    return result


def function_call_names(fn_node):
    result = set()

    for node in ast.walk(fn_node):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
        ):
            result.add(node.func.id)

    return result


def target_router_functions(text):
    tree = parse(
        text,
        "routers/historico.py",
    )

    imports = imported_service_functions(
        tree
    )

    expected_locals = {
        item["function"]
        for item in SERVICES.values()
    }

    available_originals = {
        data["original"]
        for data in imports.values()
    }

    missing = (
        expected_locals
        - available_originals
    )

    if missing:
        raise RuntimeError(
            "Router não importa funções esperadas: "
            f"{sorted(missing)}"
        )

    target_names = set(
        imports.keys()
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

        calls = function_call_names(
            node
        )

        used_local = sorted(
            calls.intersection(
                target_names
            )
        )

        if not used_local:
            continue

        originals = sorted(
            imports[name]["original"]
            for name in used_local
        )

        http_handlers = []
        business_handlers = []

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

            if name == "BusinessRuleViolation":
                business_handlers.append(
                    inner
                )

        result.append(
            {
                "node": node,
                "name": node.name,
                "line": node.lineno,
                "services": originals,
                "http_handlers": http_handlers,
                "business_handlers": business_handlers,
            }
        )

    if not result:
        raise RuntimeError(
            "Nenhum endpoint consumidor "
            "foi reconhecido no router."
        )

    found = {
        service_name
        for item in result
        for service_name in item["services"]
    }

    if found != expected_locals:
        raise RuntimeError(
            "Mapa de endpoints incompleto: "
            f"encontrado={sorted(found)} "
            f"esperado={sorted(expected_locals)}"
        )

    return result


def router_state(text):
    domain_import = (
        "from domain.exceptions import BusinessRuleViolation"
        in text
    )

    targets = target_router_functions(
        text
    )

    legacy = True
    migrated = True

    for item in targets:
        if (
            len(item["http_handlers"]) != 1
            or len(item["business_handlers"]) != 0
        ):
            legacy = False

        if (
            len(item["http_handlers"]) != 1
            or len(item["business_handlers"]) != 1
        ):
            migrated = False

    if not domain_import and legacy:
        return "LEGADO", {
            "count": len(targets),
            "targets": [
                {
                    "function": item["name"],
                    "services": item["services"],
                }
                for item in targets
            ],
        }

    if domain_import and migrated:
        return "MIGRADO", {
            "count": len(targets),
            "targets": [
                {
                    "function": item["name"],
                    "services": item["services"],
                }
                for item in targets
            ],
        }

    return "DESCONHECIDO", {
        "domain_import": domain_import,
        "targets": [
            {
                "function": item["name"],
                "http_handlers":
                    len(item["http_handlers"]),
                "business_handlers":
                    len(item["business_handlers"]),
                "services":
                    item["services"],
            }
            for item in targets
        ],
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


def module_consumers(module_name):
    consumers = []

    for path in ROOT.rglob("*.py"):
        if is_excluded(path):
            continue

        text = read_text(path)

        if module_name not in text:
            continue

        tree = parse(
            text,
            str(path),
        )

        found = False

        for node in ast.walk(tree):
            if (
                isinstance(node, ast.ImportFrom)
                and
                (node.module or "")
                == module_name
            ):
                found = True
                break

        if found:
            consumers.append(
                path.relative_to(ROOT)
            )

    return sorted(
        set(consumers),
        key=lambda p: str(p),
    )


def patch_service(text, config):
    state, diag = service_state(
        text,
        config,
    )

    if state != "LEGADO":
        raise RuntimeError(
            "Service não está legado: "
            f"{state} / {diag}"
        )

    for token in config[
        "message_tokens"
    ]:
        if token not in text:
            raise RuntimeError(
                "Mensagem esperada ausente: "
                + repr(token)
            )

    tree = parse(
        text,
        str(config["path"]),
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
            status.value
            == config["expected_status"]
        ):
            raise RuntimeError(
                "Status HTTP inesperado."
            )

        detail_source = (
            ast.get_source_segment(
                text,
                detail,
            )
        )

        if not detail_source:
            raise RuntimeError(
                "detail não recuperado."
            )

        indent = (
            " " * node.col_offset
        )

        replacement = (
            f"{indent}raise BusinessRuleViolation(\n"
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

    if (
        len(replacements)
        != config["expected_raises"]
    ):
        raise RuntimeError(
            "Quantidade de raises inesperada: "
            f"{len(replacements)}"
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

    result = result.replace(
        "from fastapi import HTTPException",
        (
            "from domain.exceptions import "
            "BusinessRuleViolation"
        ),
        1,
    )

    state2, diag2 = service_state(
        result,
        config,
    )

    if state2 != "MIGRADO":
        raise RuntimeError(
            "Service pós-patch inválido: "
            f"{state2} / {diag2}"
        )

    return result


def insert_domain_import(text):
    if (
        "from domain.exceptions import BusinessRuleViolation"
        in text
    ):
        return text

    tree = parse(
        text,
        "routers/historico.py",
    )

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
            "Import FastAPI não encontrado."
        )

    lines = text.splitlines()

    lines.insert(
        fastapi_import.end_lineno,
        (
            "from domain.exceptions import "
            "BusinessRuleViolation"
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
            "Router não está legado: "
            f"{state} / {diag}"
        )

    before_counts = {
        token: text.count(token)
        for token in PROTECTED_TOKENS
    }

    patched = insert_domain_import(
        text
    )

    targets = target_router_functions(
        patched
    )

    insertions = []

    for item in targets:
        if (
            len(item["http_handlers"])
            != 1
        ):
            raise RuntimeError(
                f"{item['name']}: esperado "
                "1 except HTTPException."
            )

        if item[
            "business_handlers"
        ]:
            raise RuntimeError(
                f"{item['name']}: "
                "BusinessRuleViolation já presente."
            )

        http_handler = (
            item["http_handlers"][0]
        )

        indent = (
            " " * http_handler.col_offset
        )

        block = (
            f"{indent}except BusinessRuleViolation as erro:\n\n"
            f"{indent}    raise HTTPException(\n"
            f"{indent}        status_code=400,\n"
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
        for token in PROTECTED_TOKENS
    }

    if (
        before_counts
        != after_counts
    ):
        differences = {
            token: (
                before_counts[token],
                after_counts[token],
            )
            for token in PROTECTED_TOKENS
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
    "[0/12] Validando pré-requisitos..."
)

for path in [
    DOMAIN,
    PREV_SERVICE,
    ROUTER,
    DIVERGENCIAS,
] + [
    item["path"]
    for item in SERVICES.values()
]:
    if not path.exists():
        raise SystemExit(
            f"[ERRO] Arquivo ausente: {path}"
        )

domain_text = read_text(
    DOMAIN
)

if (
    "class BusinessRuleViolation(DomainError)"
    not in domain_text
):
    raise SystemExit(
        "[ERRO] BusinessRuleViolation não reconhecida."
    )

prev_text = read_text(
    PREV_SERVICE
)

if (
    "NotFoundError"
    not in prev_text
    or
    "from fastapi import HTTPException"
    in prev_text
):
    raise SystemExit(
        "[ERRO] Fase 10D não reconhecida em "
        "services/indicadores_operacionais.py."
    )

print(
    "      [OK] Fases anteriores reconhecidas."
)


print(
    "[1/12] Verificando consumidores de historico_itens..."
)

cons_itens = module_consumers(
    "services.historico_itens"
)

for item in cons_itens:
    print(
        f"      - {item}"
    )

expected = [
    Path("routers") / "historico.py"
]

if cons_itens != expected:
    print(
        "[ERRO] Consumidor inesperado "
        "de historico_itens."
    )
    print(
        "[INFO] Nenhum arquivo foi alterado."
    )
    raise SystemExit(1)

print(
    "      [OK] consumidor único."
)


print(
    "[2/12] Verificando consumidores de historico_localizacoes..."
)

cons_loc = module_consumers(
    "services.historico_localizacoes"
)

for item in cons_loc:
    print(
        f"      - {item}"
    )

if cons_loc != expected:
    print(
        "[ERRO] Consumidor inesperado "
        "de historico_localizacoes."
    )
    print(
        "[INFO] Nenhum arquivo foi alterado."
    )
    raise SystemExit(1)

print(
    "      [OK] consumidor único."
)


print(
    "[3/12] Analisando services históricos..."
)

states = {}

for name, config in (
    SERVICES.items()
):
    text = read_text(
        config["path"]
    )

    state, diag = (
        service_state(
            text,
            config,
        )
    )

    states[name] = {
        "text": text,
        "state": state,
        "diag": diag,
    }

    print(
        f"      {name}: {state} | "
        f"HTTP={diag.get('http_raises', 0)} | "
        f"Business={diag.get('business_raises', 0)}"
    )

    if state == "DESCONHECIDO":
        raise SystemExit(
            f"[ERRO] Baseline desconhecida: "
            f"{name} / {diag}"
        )


print(
    "[4/12] Analisando historico_divergencias..."
)

div_text = read_text(
    DIVERGENCIAS
)

div_state, div_diag = (
    divergencias_state(
        div_text
    )
)

print(
    f"      Estado: {div_state} | "
    f"HTTPException occurrences="
    f"{div_diag.get('occurrences', 0)}"
)

if div_state == "DESCONHECIDO":
    raise SystemExit(
        "[ERRO] historico_divergencias possui "
        "uso de HTTPException além do import."
    )


print(
    "[5/12] Analisando router histórico..."
)

router_text = read_text(
    ROUTER
)

r_state, r_diag = (
    router_state(
        router_text
    )
)

print(
    f"      Estado: {r_state}"
)

for item in r_diag.get(
    "targets",
    []
):
    print(
        f"      - {item}"
    )

if r_state == "DESCONHECIDO":
    raise SystemExit(
        "[ERRO] Baseline do router "
        f"desconhecida: {r_diag}"
    )


all_migrated = (
    all(
        data["state"] == "MIGRADO"
        for data in states.values()
    )
    and
    div_state == "MIGRADO"
    and
    r_state == "MIGRADO"
)

if all_migrated:
    print(
        "[6/12] Fase 10E já aplicada."
    )
    print(
        "      [OK] nenhuma alteração necessária."
    )
    raise SystemExit(0)


all_legacy = (
    all(
        data["state"] == "LEGADO"
        for data in states.values()
    )
    and
    div_state == "LEGADO"
    and
    r_state == "LEGADO"
)

if not all_legacy:
    raise SystemExit(
        "[ERRO] Migração parcial detectada. "
        "Nenhum arquivo será alterado."
    )


print(
    "[6/12] Registrando conexão/transação..."
)

before_conn = {
    token: router_text.count(token)
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

backup_paths = {}

targets_to_backup = {
    "router": ROUTER,
    "divergencias": DIVERGENCIAS,
}

for name, config in SERVICES.items():
    targets_to_backup[name] = (
        config["path"]
    )


print(
    "[7/12] Criando backups..."
)

for name, path in (
    targets_to_backup.items()
):
    backup = (
        path.parent
        /
        (
            path.stem
            + "_backup_fase10e_"
            + timestamp
            + ".py"
        )
    )

    shutil.copy2(
        path,
        backup,
    )

    backup_paths[name] = backup

    print(
        f"      {path.name} -> "
        f"{backup.name}"
    )


try:
    print(
        "[8/12] Migrando historico_itens/localizacoes..."
    )

    for name, config in (
        SERVICES.items()
    ):
        patched = patch_service(
            states[name]["text"],
            config,
        )

        config["path"].write_text(
            patched,
            encoding="utf-8",
        )

        py_compile.compile(
            str(config["path"]),
            doraise=True,
        )

        print(
            f"      [OK] {name}: "
            "HTTP 400 -> BusinessRuleViolation."
        )


    print(
        "[9/12] Removendo import HTTP morto "
        "de historico_divergencias..."
    )

    final_div = div_text.replace(
        "from fastapi import HTTPException\n",
        "",
        1,
    )

    final_div = final_div.replace(
        "from fastapi import HTTPException\r\n",
        "",
        1,
    )

    state_div2, diag_div2 = (
        divergencias_state(
            final_div
        )
    )

    if state_div2 != "MIGRADO":
        raise RuntimeError(
            "Falha ao remover import morto: "
            f"{diag_div2}"
        )

    DIVERGENCIAS.write_text(
        final_div,
        encoding="utf-8",
    )

    py_compile.compile(
        str(DIVERGENCIAS),
        doraise=True,
    )

    print(
        "      [OK] FastAPI removido "
        "de historico_divergencias."
    )


    print(
        "[10/12] Adaptando endpoints do router..."
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

    r2, rd2 = router_state(
        patched_router
    )

    if r2 != "MIGRADO":
        raise RuntimeError(
            f"Router final inválido: {rd2}"
        )

    print(
        "      [OK] endpoints adaptados: "
        f"{rd2['count']}"
    )


    print(
        "[11/12] Validando contratos e conexão..."
    )

    final_router = read_text(
        ROUTER
    )

    after_conn = {
        token: final_router.count(token)
        for token in PROTECTED_TOKENS
    }

    if before_conn != after_conn:
        raise RuntimeError(
            "Conexão/transação foi alterada."
        )

    if (
        "status_code=400"
        not in final_router
        or
        "detail=str(erro)"
        not in final_router
    ):
        raise RuntimeError(
            "Tradução BusinessRuleViolation "
            "-> HTTP 400 ausente."
        )

    for name, config in (
        SERVICES.items()
    ):
        final_text = read_text(
            config["path"]
        )

        s2, sd2 = service_state(
            final_text,
            config,
        )

        if s2 != "MIGRADO":
            raise RuntimeError(
                f"{name} final inválido: {sd2}"
            )

        if "fastapi" in final_text.lower():
            raise RuntimeError(
                f"{name} ainda depende de FastAPI."
            )

        for token in config[
            "message_tokens"
        ]:
            if token not in final_text:
                raise RuntimeError(
                    f"{name}: mensagem perdida."
                )

    print(
        "      [OK] HTTP 400 preservado."
    )
    print(
        "      [OK] mensagens preservadas."
    )
    print(
        "      [OK] conexão/transação inalteradas."
    )


    print(
        "[12/12] Revalidando consumidores..."
    )

    if (
        module_consumers(
            "services.historico_itens"
        )
        != expected
    ):
        raise RuntimeError(
            "Consumidores de historico_itens mudaram."
        )

    if (
        module_consumers(
            "services.historico_localizacoes"
        )
        != expected
    ):
        raise RuntimeError(
            "Consumidores de historico_localizacoes mudaram."
        )

    print(
        "      [OK] consumidores preservados."
    )


except Exception:
    print()
    print(
        "[ERRO] Falha durante Fase 10E."
    )
    print(
        "[INFO] Restaurando arquivos..."
    )

    for name, backup in (
        backup_paths.items()
    ):
        shutil.copy2(
            backup,
            targets_to_backup[name],
        )

        print(
            f"      [OK] restaurado: "
            f"{targets_to_backup[name].name}"
        )

    raise


print()
print(
    "[OK] Fase 10E aplicada."
)
print(
    "[OK] historico_itens.py desacoplado de FastAPI."
)
print(
    "[OK] historico_localizacoes.py desacoplado de FastAPI."
)
print(
    "[OK] historico_divergencias.py sem import HTTP morto."
)
print(
    "[OK] routers/historico.py mantém HTTP 400."
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
