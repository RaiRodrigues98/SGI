
"""
FASE 10G - CONSULTAS OPERACIONAIS | NÚCLEO DE INVENTÁRIO/RODADA

Escopo de domínio:
- services/consultas_operacionais.py
  - consultar_inventario
  - consultar_rodada_atual

Erros migrados:
- consultar_inventario:
    404 Inventário não encontrado.
- consultar_rodada_atual:
    404 Inventário não encontrado.
    404 Rodada atual não encontrada.

Todos viram NotFoundError.

IMPORTANTE:
Outras funções do mesmo service podem chamar essas funções.
Por isso o instalador cria um grafo de chamadas interno via AST
e adapta todos os endpoints de routers/consultas.py que chamem,
direta OU indiretamente, funções afetadas.

Não altera:
- demais HTTPException do service;
- SQL;
- conexão/UoW;
- cursor;
- commit/rollback;
- rotas;
- respostas de sucesso.

Execute:
python .\fase10g_excecoes_consultas_base\aplicar_fase10g.py
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
PREV = ROOT / "services" / "historico_inventarios.py"

SEED_FUNCTIONS = {
    "consultar_inventario",
    "consultar_rodada_atual",
}

EXPECTED_HTTP_RAISES = {
    "consultar_inventario": 1,
    "consultar_rodada_atual": 2,
}

EXPECTED_STATUS = 404

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
            (ast.FunctionDef, ast.AsyncFunctionDef),
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
    functions, graph = internal_call_graph(text)

    missing = SEED_FUNCTIONS - set(functions)
    if missing:
        raise RuntimeError(
            "Funções base ausentes: "
            f"{sorted(missing)}"
        )

    affected = set(SEED_FUNCTIONS)

    changed = True
    while changed:
        changed = False

        for caller, callees in graph.items():
            if caller in affected:
                continue

            if callees.intersection(affected):
                affected.add(caller)
                changed = True

    return affected


def http_raises_in_function(text, function_name):
    tree = parse(
        text,
        "services/consultas_operacionais.py",
    )
    functions = top_functions(tree)

    fn = functions.get(function_name)

    if fn is None:
        raise RuntimeError(
            f"Função ausente: {function_name}"
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
            and isinstance(status_node.value, int)
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


def count_domain_raises_in_function(text, function_name):
    tree = parse(
        text,
        "services/consultas_operacionais.py",
    )
    functions = top_functions(tree)

    fn = functions.get(function_name)

    if fn is None:
        raise RuntimeError(
            f"Função ausente: {function_name}"
        )

    total = 0

    for node in ast.walk(fn):
        if not isinstance(node, ast.Raise):
            continue

        if node.exc is None:
            continue

        if raised_name(node.exc) == "NotFoundError":
            total += 1

    return total


def service_state(text):
    legacy_ok = True
    migrated_ok = True
    diag = {}

    for fn_name, expected in EXPECTED_HTTP_RAISES.items():
        http_raises = http_raises_in_function(
            text,
            fn_name,
        )

        domain_count = count_domain_raises_in_function(
            text,
            fn_name,
        )

        statuses = [
            item["status"]
            for item in http_raises
        ]

        diag[fn_name] = {
            "http_count": len(http_raises),
            "statuses": statuses,
            "notfound_count": domain_count,
        }

        if not (
            len(http_raises) == expected
            and domain_count == 0
        ):
            legacy_ok = False

        if not (
            len(http_raises) == 0
            and domain_count == expected
        ):
            migrated_ok = False

    if legacy_ok:
        return "LEGADO", diag

    if migrated_ok:
        return "MIGRADO", diag

    return "DESCONHECIDO", diag


def imported_service_aliases(tree):
    result = {}

    for node in tree.body:
        if not isinstance(node, ast.ImportFrom):
            continue

        if (
            (node.module or "")
            != "services.consultas_operacionais"
        ):
            continue

        for alias in node.names:
            result[
                alias.asname or alias.name
            ] = alias.name

    return result


def affected_router_functions(router_text, service_text):
    affected_service = affected_service_functions(
        service_text
    )

    tree = parse(
        router_text,
        "routers/consultas.py",
    )

    imports = imported_service_aliases(
        tree
    )

    if not imports:
        raise RuntimeError(
            "Router não importa services.consultas_operacionais."
        )

    affected_local_aliases = {
        local_name
        for local_name, original_name in imports.items()
        if original_name in affected_service
    }

    if not affected_local_aliases:
        raise RuntimeError(
            "Nenhuma função afetada importada no router."
        )

    result = []

    for node in tree.body:
        if not isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef),
        ):
            continue

        calls = function_calls(node)

        used = sorted(
            calls.intersection(
                affected_local_aliases
            )
        )

        if not used:
            continue

        originals = sorted(
            {
                imports[name]
                for name in used
            }
        )

        http_handlers = []
        notfound_handlers = []

        for inner in ast.walk(node):
            if not isinstance(
                inner,
                ast.ExceptHandler,
            ):
                continue

            name = handler_name(inner)

            if name == "HTTPException":
                http_handlers.append(inner)

            if name == "NotFoundError":
                notfound_handlers.append(inner)

        result.append(
            {
                "node": node,
                "name": node.name,
                "line": node.lineno,
                "services": originals,
                "http_handlers": http_handlers,
                "notfound_handlers": notfound_handlers,
            }
        )

    if not result:
        raise RuntimeError(
            "Nenhum endpoint afetado encontrado."
        )

    return result, affected_service


def router_state(router_text, service_text):
    domain_import = (
        "from domain.exceptions import NotFoundError"
        in router_text
    )

    targets, affected_service = affected_router_functions(
        router_text,
        service_text,
    )

    legacy = True
    migrated = True

    for item in targets:
        if not (
            len(item["http_handlers"]) == 1
            and
            len(item["notfound_handlers"]) == 0
        ):
            legacy = False

        if not (
            len(item["http_handlers"]) == 1
            and
            len(item["notfound_handlers"]) == 1
        ):
            migrated = False

    if legacy:
        return "LEGADO", {
            "targets": [
                {
                    "endpoint": item["name"],
                    "services": item["services"],
                }
                for item in targets
            ],
            "affected_service_functions":
                sorted(affected_service),
        }

    if domain_import and migrated:
        return "MIGRADO", {
            "targets": [
                {
                    "endpoint": item["name"],
                    "services": item["services"],
                }
                for item in targets
            ],
            "affected_service_functions":
                sorted(affected_service),
        }

    return "DESCONHECIDO", {
        "domain_import": domain_import,
        "targets": [
            {
                "endpoint": item["name"],
                "http_handlers":
                    len(item["http_handlers"]),
                "notfound_handlers":
                    len(item["notfound_handlers"]),
                "services":
                    item["services"],
            }
            for item in targets
        ],
        "affected_service_functions":
            sorted(affected_service),
    }


def patch_service(text):
    state, diag = service_state(text)

    if state != "LEGADO":
        raise RuntimeError(
            f"Service não está legado: {state} / {diag}"
        )

    replacements = []

    for fn_name, expected in EXPECTED_HTTP_RAISES.items():
        raises = http_raises_in_function(
            text,
            fn_name,
        )

        if len(raises) != expected:
            raise RuntimeError(
                f"{fn_name}: quantidade de HTTPException inesperada."
            )

        for item in raises:
            if item["status"] != EXPECTED_STATUS:
                raise RuntimeError(
                    f"{fn_name}: status {item['status']} "
                    "fora do escopo da 10G."
                )

            node = item["node"]
            indent = " " * node.col_offset

            replacement = (
                f"{indent}raise NotFoundError(\n"
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

    if len(replacements) != 3:
        raise RuntimeError(
            f"Esperadas 3 conversões; encontradas {len(replacements)}."
        )

    lines = text.splitlines()

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

    # O arquivo continua usando HTTPException em outras funções.
    # Portanto NÃO removemos FastAPI.
    if (
        "from domain.exceptions import NotFoundError"
        not in result
    ):
        tree = parse(
            result,
            "service pós-patch",
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
                "Import FastAPI não encontrado para inserir NotFoundError."
            )

        lines = result.splitlines()

        lines.insert(
            fastapi_import.end_lineno,
            "from domain.exceptions import NotFoundError",
        )

        result = "\n".join(lines)

        if text.endswith("\n"):
            result += "\n"

    state2, diag2 = service_state(result)

    if state2 != "MIGRADO":
        raise RuntimeError(
            f"Service pós-patch inválido: {diag2}"
        )

    return result


def insert_router_domain_import(text):
    if (
        "from domain.exceptions import NotFoundError"
        in text
    ):
        return text

    tree = parse(
        text,
        "routers/consultas.py",
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
            "Import FastAPI não encontrado no router."
        )

    lines = text.splitlines()

    lines.insert(
        fastapi_import.end_lineno,
        "from domain.exceptions import NotFoundError",
    )

    result = "\n".join(lines)

    if text.endswith("\n"):
        result += "\n"

    return result


def patch_router(router_text, patched_service):
    before_counts = {
        token: router_text.count(token)
        for token in PROTECTED_TOKENS
    }

    state, diag = router_state(
        router_text,
        patched_service.replace(
            "raise NotFoundError",
            "raise HTTPException",
        )
        if False else
        # para detectar baseline do router, basta usar
        # service atual: o grafo é independente das exceções.
        patched_service
    )

    # Após o service ser patchado, o grafo continua igual.
    # Router ainda deve estar sem handlers NotFoundError.
    if state not in {
        "LEGADO",
        "DESCONHECIDO",
    }:
        raise RuntimeError(
            f"Router em estado inesperado: {state}"
        )

    # Reavalia manualmente garantindo baseline dos endpoints.
    targets, _ = affected_router_functions(
        router_text,
        patched_service,
    )

    for item in targets:
        if (
            len(item["http_handlers"]) != 1
            or
            len(item["notfound_handlers"]) != 0
        ):
            raise RuntimeError(
                f"{item['name']}: baseline de handlers inesperada."
            )

    patched = insert_router_domain_import(
        router_text
    )

    targets2, _ = affected_router_functions(
        patched,
        patched_service,
    )

    insertions = []

    for item in targets2:
        http_handler = item[
            "http_handlers"
        ][0]

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

    result = "\n".join(lines)

    if patched.endswith("\n"):
        result += "\n"

    final_state, final_diag = router_state(
        result,
        patched_service,
    )

    if final_state != "MIGRADO":
        raise RuntimeError(
            f"Router pós-patch inválido: {final_diag}"
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
    DOMAIN,
    SERVICE,
    ROUTER,
    PREV,
]:
    if not path.exists():
        raise SystemExit(
            f"[ERRO] Arquivo ausente: {path}"
        )

domain_text = read_text(DOMAIN)

if (
    "class NotFoundError(DomainError)"
    not in domain_text
):
    raise SystemExit(
        "[ERRO] NotFoundError não reconhecida."
    )

prev_text = read_text(PREV)

if (
    "from fastapi import HTTPException"
    in prev_text
):
    raise SystemExit(
        "[ERRO] Fase 10F não reconhecida em "
        "historico_inventarios.py."
    )

print(
    "      [OK] Fase 10F reconhecida."
)


print(
    "[1/11] Analisando núcleo do service..."
)

service_text = read_text(SERVICE)

s_state, s_diag = service_state(
    service_text
)

print(
    f"      Estado: {s_state}"
)

for fn_name, info in s_diag.items():
    print(
        f"      {fn_name}: "
        f"HTTP={info['http_count']} "
        f"statuses={info['statuses']} "
        f"NotFound={info['notfound_count']}"
    )

if s_state == "DESCONHECIDO":
    raise SystemExit(
        "[ERRO] Baseline do núcleo "
        f"desconhecida: {s_diag}"
    )


print(
    "[2/11] Montando grafo de chamadas do service..."
)

affected = affected_service_functions(
    service_text
)

print(
    "      funções afetadas por propagação:"
)

for name in sorted(affected):
    print(
        f"        - {name}"
    )


print(
    "[3/11] Mapeando endpoints afetados..."
)

router_text = read_text(ROUTER)

targets, _ = affected_router_functions(
    router_text,
    service_text,
)

for item in targets:
    print(
        f"      {item['name']} <- "
        f"{', '.join(item['services'])}"
    )

print(
    f"      total endpoints: {len(targets)}"
)


if s_state == "MIGRADO":
    r_state, r_diag = router_state(
        router_text,
        service_text,
    )

    if r_state == "MIGRADO":
        print(
            "[4/11] Fase 10G já aplicada."
        )
        print(
            "      [OK] nenhuma alteração necessária."
        )
        raise SystemExit(0)

    raise SystemExit(
        "[ERRO] Service migrado, mas router "
        f"não está consistente: {r_diag}"
    )


print(
    "[4/11] Validando os 3 HTTP 404..."
)

for fn_name, expected in EXPECTED_HTTP_RAISES.items():
    raises = http_raises_in_function(
        service_text,
        fn_name,
    )

    if len(raises) != expected:
        raise SystemExit(
            f"[ERRO] {fn_name}: quantidade inesperada."
        )

    for item in raises:
        if item["status"] != 404:
            raise SystemExit(
                f"[ERRO] {fn_name}: "
                f"status {item['status']} fora do escopo."
            )

print(
    "      [OK] 3 erros 404 confirmados."
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
        + "_backup_fase10g_"
        + timestamp
        + ".py"
    )
)

router_backup = (
    ROUTER.parent
    / (
        ROUTER.stem
        + "_backup_fase10g_"
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
        "[7/11] Migrando núcleo do service..."
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
        "      [OK] 3 HTTPException 404 "
        "-> NotFoundError."
    )
    print(
        "      [OK] demais HTTPException do "
        "service permaneceram intactos."
    )


    print(
        "[8/11] Adaptando endpoints afetados..."
    )

    patched_router = patch_router(
        router_text,
        patched_service,
    )

    ROUTER.write_text(
        patched_router,
        encoding="utf-8",
    )

    py_compile.compile(
        str(ROUTER),
        doraise=True,
    )

    final_router_state, final_router_diag = (
        router_state(
            patched_router,
            patched_service,
        )
    )

    if final_router_state != "MIGRADO":
        raise RuntimeError(
            f"Router final inválido: {final_router_diag}"
        )

    print(
        "      [OK] endpoints adaptados: "
        f"{len(final_router_diag['targets'])}"
    )


    print(
        "[9/11] Validando contratos HTTP..."
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

    final_router = read_text(
        ROUTER
    )

    if (
        "status_code=404"
        not in final_router
        or
        "detail=str(erro)"
        not in final_router
    ):
        raise RuntimeError(
            "Tradução NotFoundError -> HTTP 404 ausente."
        )

    print(
        "      [OK] HTTP 404 preservado."
    )


    print(
        "[10/11] Validando conexão/transação..."
    )

    after_conn = {
        token: final_router.count(token)
        for token in PROTECTED_TOKENS
    }

    if before_conn != after_conn:
        raise RuntimeError(
            "Conexão/transação foi alterada."
        )

    print(
        "      [OK] conexão/transação inalteradas."
    )


    print(
        "[11/11] Validando escopo da migração..."
    )

    # Garante que FastAPI continua no service se ainda houver
    # HTTPException fora das duas funções alvo.
    tree = parse(
        final_service,
        "service final",
    )

    remaining_http = 0

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

    if remaining_http > 0:
        if (
            "from fastapi import HTTPException"
            not in final_service
        ):
            raise RuntimeError(
                "Import FastAPI removido apesar de "
                "HTTPException remanescentes."
            )

    print(
        f"      [OK] HTTPException remanescentes "
        f"fora do escopo: {remaining_http}"
    )
    print(
        "      [OK] migração parcial controlada."
    )


except Exception:
    print()
    print(
        "[ERRO] Falha durante Fase 10G."
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
    "[OK] Fase 10G aplicada."
)
print(
    "[OK] consultar_inventario desacoplado de HTTP."
)
print(
    "[OK] consultar_rodada_atual desacoplado de HTTP."
)
print(
    "[OK] propagação indireta mapeada via AST."
)
print(
    "[OK] endpoints afetados mantêm HTTP 404."
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
