
"""
FASE 10V-A - RODADAS / FINALIZAÇÃO ROTATIVO
Recorte: R2 ainda não concluída operacionalmente

Alvo:
services/rodadas/finalizacao_rotativo.py
└── _encerrar_inventario_rotativo_apos_r2()

Erro alvo:
HTTP 400
"A R2 do inventário ROTATIVO ainda não foi concluída operacionalmente.
 Encerre todas as sessões e conclua todas as localizações previstas."

Mapeamento:
HTTP 400 -> BusinessRuleViolation

A fase é deliberadamente parcial:
- converte SOMENTE esse raise;
- mantém todas as demais HTTPException do módulo intactas;
- FastAPI permanece enquanto houver qualquer HTTPException restante.

Pré-requisito:
- Fase 10U-H aplicada:
  services/rodadas/criacao.py sem HTTPException/FastAPI.

Proteções:
- SQL literal idêntico;
- chamadas de negócio idênticas;
- analisar_recontagem_rotativo preservado;
- consolidar_resultado_final_rotativo preservado;
- _finalizar_rodada_atual preservado;
- UoW/commit/rollback/conexão inalterados;
- nenhum router é editado;
- exige que uma fronteira HTTP já traduza
  BusinessRuleViolation -> HTTP 400;
- backup + auto-restore.
"""

from pathlib import Path
from datetime import datetime
from collections import Counter
import ast
import shutil
import py_compile

ROOT = Path.cwd()

SERVICE = ROOT / "services" / "rodadas" / "finalizacao_rotativo.py"
DOMAIN = ROOT / "domain" / "exceptions.py"
CRIACAO = ROOT / "services" / "rodadas" / "criacao.py"

TARGET_FUNCTION = "_encerrar_inventario_rotativo_apos_r2"

EXPECTED_STATUS = 400
EXPECTED_DETAIL = (
    "A R2 do inventário ROTATIVO ainda não foi "
    "concluída operacionalmente. Encerre todas as "
    "sessões e conclua todas as localizações previstas."
)

BUSINESS_CALLS_REQUIRED = (
    "analisar_recontagem_rotativo",
    "consolidar_resultado_final_rotativo",
    "_finalizar_rodada_atual",
)

TRANSACTION_TOKENS = (
    "get_connection()",
    "SqlServerUnitOfWork()",
    "conn.commit()",
    "conn.rollback()",
    "uow.commit()",
    "uow.rollback()",
    "cursor.close()",
    "conn.close()",
)

EXCLUDED_DIRS = {
    ".git", ".venv", "venv", "__pycache__", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", "node_modules",
}


def read_text(path):
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1")


def parse(text, label):
    try:
        return ast.parse(text)
    except SyntaxError as exc:
        raise RuntimeError(f"{label}: sintaxe inválida: {exc}")


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


def functions(text):
    tree = parse(text, str(SERVICE))
    return {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def get_function(text, name):
    fn = functions(text).get(name)
    if fn is None:
        raise RuntimeError(f"Função ausente: {name}")
    return fn


def http_raises(text, fn_name=None):
    tree_or_fn = (
        get_function(text, fn_name)
        if fn_name
        else parse(text, str(SERVICE))
    )
    result = []

    for node in ast.walk(tree_or_fn):
        if not isinstance(node, ast.Raise) or node.exc is None:
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
            raise RuntimeError("HTTPException sem status/detail.")

        if not (
            isinstance(status_node, ast.Constant)
            and isinstance(status_node.value, int)
        ):
            raise RuntimeError("status_code dinâmico não suportado.")

        detail_source = ast.get_source_segment(text, detail_node)
        if not detail_source:
            raise RuntimeError("detail não recuperado via AST.")

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

    return sorted(result, key=lambda item: item["node"].lineno)


def semantic_raises(text, fn_name, exc_name):
    fn = get_function(text, fn_name)
    result = []

    for node in ast.walk(fn):
        if not isinstance(node, ast.Raise) or node.exc is None:
            continue
        if raised_name(node.exc) != exc_name:
            continue

        detail_source = None
        detail_value = None

        if isinstance(node.exc, ast.Call) and node.exc.args:
            detail_node = node.exc.args[0]
            detail_source = ast.get_source_segment(text, detail_node)
            try:
                detail_value = ast.literal_eval(detail_node)
            except Exception:
                pass

        result.append({
            "node": node,
            "detail_source": detail_source,
            "detail_value": detail_value,
        })

    return result


def target_http(text):
    matches = [
        item
        for item in http_raises(text, TARGET_FUNCTION)
        if (
            item["status"] == EXPECTED_STATUS
            and item["detail_value"] == EXPECTED_DETAIL
        )
    ]

    if len(matches) > 1:
        raise RuntimeError(
            f"Raise alvo duplicado: {len(matches)} ocorrências."
        )

    return matches


def target_business(text):
    matches = [
        item
        for item in semantic_raises(
            text,
            TARGET_FUNCTION,
            "BusinessRuleViolation",
        )
        if item["detail_value"] == EXPECTED_DETAIL
    ]

    if len(matches) > 1:
        raise RuntimeError(
            f"BusinessRuleViolation alvo duplicada: {len(matches)}."
        )

    return matches


def fastapi_starlette_imports(text):
    tree = parse(text, str(SERVICE))
    found = []

    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if (
                module == "fastapi"
                or module.startswith("fastapi.")
                or module == "starlette"
                or module.startswith("starlette.")
            ):
                found.append(node)

        elif isinstance(node, ast.Import):
            for alias in node.names:
                if (
                    alias.name == "fastapi"
                    or alias.name.startswith("fastapi.")
                    or alias.name == "starlette"
                    or alias.name.startswith("starlette.")
                ):
                    found.append(node)
                    break

    return found


def has_import(text, module_name, symbol):
    tree = parse(text, str(SERVICE))
    return any(
        isinstance(node, ast.ImportFrom)
        and (node.module or "") == module_name
        and symbol in [alias.name for alias in node.names]
        for node in tree.body
    )


def sql_literals(text):
    tree = parse(text, str(SERVICE))
    result = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant):
            continue
        if not isinstance(node.value, str):
            continue

        value = node.value
        normalized = value.upper()

        if any(
            keyword in normalized
            for keyword in (
                "SELECT ",
                "UPDATE ",
                "INSERT ",
                "DELETE ",
                "MERGE ",
                "EXEC ",
                "FROM DBO.",
                "INTO DBO.",
            )
        ):
            result.append(value)

    return result


def call_counter(text):
    tree = parse(text, str(SERVICE))
    counter = Counter()

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        name = raised_name(node.func)

        if name in {
            "HTTPException",
            "BusinessRuleViolation",
        }:
            continue

        if name:
            counter[name] += 1

    return counter


def transaction_counts(text):
    return {
        token: text.count(token)
        for token in TRANSACTION_TOKENS
    }


def validate_required_business_calls(text):
    fn_source = ast.get_source_segment(
        text,
        get_function(text, TARGET_FUNCTION),
    ) or ""

    missing = [
        name
        for name in BUSINESS_CALLS_REQUIRED
        if name not in fn_source
    ]

    if missing:
        raise RuntimeError(
            "Fluxo de encerramento R2 inesperado. "
            f"Chamadas ausentes: {missing}"
        )


def state(text):
    validate_required_business_calls(text)

    target_h = target_http(text)
    target_b = target_business(text)

    total_http = len(http_raises(text))
    handlers = sum(
        1
        for node in ast.walk(parse(text, str(SERVICE)))
        if (
            isinstance(node, ast.ExceptHandler)
            and handler_name(node) == "HTTPException"
        )
    )

    if handlers != 0:
        raise RuntimeError(
            f"Service possui {handlers} except HTTPException; "
            "baseline não suportado."
        )

    if (
        len(target_h) == 1
        and len(target_b) == 0
        and total_http >= 1
        and has_import(text, "fastapi", "HTTPException")
    ):
        return "LEGADO_10V_A", {
            "http_total": total_http,
            "target_http": 1,
            "target_business": 0,
            "fastapi_imports":
                len(fastapi_starlette_imports(text)),
        }

    if (
        len(target_h) == 0
        and len(target_b) == 1
        and has_import(
            text,
            "domain.exceptions",
            "BusinessRuleViolation",
        )
    ):
        # FastAPI deve permanecer apenas se outros HTTPException restarem.
        expected_fastapi = total_http > 0
        actual_fastapi = (
            len(fastapi_starlette_imports(text)) > 0
        )

        if expected_fastapi != actual_fastapi:
            raise RuntimeError(
                "Estado migrado inconsistente: "
                f"http_total={total_http}, "
                f"fastapi_import={actual_fastapi}"
            )

        return "MIGRADO_10V_A", {
            "http_total": total_http,
            "target_http": 0,
            "target_business": 1,
            "fastapi_imports":
                len(fastapi_starlette_imports(text)),
        }

    return "DESCONHECIDO", {
        "http_total": total_http,
        "target_http": len(target_h),
        "target_business": len(target_b),
        "fastapi_imports":
            len(fastapi_starlette_imports(text)),
        "http_details": [
            {
                "status": item["status"],
                "detail": item["detail_value"],
            }
            for item in http_raises(text)
        ],
    }


def ensure_domain_import(text):
    if has_import(
        text,
        "domain.exceptions",
        "BusinessRuleViolation",
    ):
        return text

    tree = parse(text, str(SERVICE))

    fastapi_import = next(
        (
            node
            for node in tree.body
            if (
                isinstance(node, ast.ImportFrom)
                and (node.module or "") == "fastapi"
            )
        ),
        None,
    )

    if fastapi_import is None:
        raise RuntimeError(
            "Import FastAPI legado não encontrado."
        )

    lines = text.splitlines()

    lines.insert(
        fastapi_import.end_lineno,
        (
            "from domain.exceptions import "
            "BusinessRuleViolation"
        ),
    )

    result = "\n".join(lines)

    if text.endswith("\n"):
        result += "\n"

    return result


def remove_http_import_if_unused(text):
    if len(http_raises(text)) > 0:
        return text

    tree = parse(text, str(SERVICE))
    targets = []

    for node in tree.body:
        if (
            isinstance(node, ast.ImportFrom)
            and (node.module or "") == "fastapi"
            and "HTTPException"
            in [alias.name for alias in node.names]
        ):
            targets.append(node)

    if len(targets) != 1:
        raise RuntimeError(
            "Esperado exatamente um import FastAPI "
            "contendo HTTPException."
        )

    node = targets[0]

    remaining = [
        alias
        for alias in node.names
        if alias.name != "HTTPException"
    ]

    lines = text.splitlines()

    if remaining:
        rebuilt = (
            "from fastapi import "
            + ", ".join(
                (
                    alias.name
                    if alias.asname is None
                    else f"{alias.name} as {alias.asname}"
                )
                for alias in remaining
            )
        )
        lines[
            node.lineno - 1:
            node.end_lineno
        ] = [rebuilt]
    else:
        lines[
            node.lineno - 1:
            node.end_lineno
        ] = []

    result = "\n".join(lines)

    if text.endswith("\n"):
        result += "\n"

    return result


def patch(text):
    current_state, diag = state(text)

    if current_state != "LEGADO_10V_A":
        raise RuntimeError(
            "Service não está no baseline 10V-A: "
            f"{current_state} / {diag}"
        )

    before_sql = sql_literals(text)
    before_calls = call_counter(text)
    before_tx = transaction_counts(text)
    before_http_total = len(http_raises(text))

    item = target_http(text)[0]
    node = item["node"]
    indent = " " * node.col_offset

    replacement = (
        f"{indent}raise BusinessRuleViolation(\n"
        f"{indent}    {item['detail_source']}\n"
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

    result = ensure_domain_import(result)
    result = remove_http_import_if_unused(result)

    after_http_total = len(http_raises(result))

    if after_http_total != before_http_total - 1:
        raise RuntimeError(
            "Quantidade global de HTTPException não caiu "
            f"exatamente em 1: {before_http_total} -> "
            f"{after_http_total}"
        )

    if sql_literals(result) != before_sql:
        raise RuntimeError(
            "SQL literal foi alterado durante a fase."
        )

    if call_counter(result) != before_calls:
        raise RuntimeError(
            "Chamadas de negócio foram alteradas."
        )

    if transaction_counts(result) != before_tx:
        raise RuntimeError(
            "Tokens de conexão/transação foram alterados."
        )

    final_state, final_diag = state(result)

    if final_state != "MIGRADO_10V_A":
        raise RuntimeError(
            "Estado pós-patch inválido: "
            f"{final_diag}"
        )

    return result


def is_excluded(path):
    rel = path.relative_to(ROOT)

    for part in rel.parts:
        low = part.lower()
        if low in EXCLUDED_DIRS:
            return True
        if "_backup_" in low or low.startswith("backup"):
            return True
        if low.startswith("fase10"):
            return True

    return False


def router_business_handlers():
    results = []

    for path in ROOT.rglob("routers/*.py"):
        if is_excluded(path):
            continue

        text = read_text(path)

        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue

        for fn in [
            node
            for node in tree.body
            if isinstance(
                node,
                (ast.FunctionDef, ast.AsyncFunctionDef),
            )
        ]:
            for handler in [
                node
                for node in ast.walk(fn)
                if isinstance(node, ast.ExceptHandler)
            ]:
                if handler_name(handler) != "BusinessRuleViolation":
                    continue

                status_400 = False

                for raise_node in ast.walk(handler):
                    if not isinstance(raise_node, ast.Raise):
                        continue
                    if not (
                        isinstance(raise_node.exc, ast.Call)
                        and raised_name(raise_node.exc)
                        == "HTTPException"
                    ):
                        continue

                    for kw in raise_node.exc.keywords:
                        if (
                            kw.arg == "status_code"
                            and isinstance(
                                kw.value,
                                ast.Constant,
                            )
                            and kw.value.value == 400
                        ):
                            status_400 = True

                if status_400:
                    results.append(
                        (
                            path.relative_to(ROOT),
                            fn.name,
                        )
                    )

    return results


print("[0/12] Validando arquivos...")

for path in (
    SERVICE,
    DOMAIN,
    CRIACAO,
):
    if not path.exists():
        raise SystemExit(
            f"[ERRO] Arquivo ausente: {path}"
        )

domain_text = read_text(DOMAIN)

if (
    "class BusinessRuleViolation(DomainError)"
    not in domain_text
):
    raise SystemExit(
        "[ERRO] BusinessRuleViolation ausente."
    )

print("      [OK] arquivos-base presentes.")


print("[1/12] Validando pré-requisito 10U-H...")

criacao_text = read_text(CRIACAO)

if (
    "HTTPException" in criacao_text
    or "fastapi" in criacao_text.lower()
    or "starlette" in criacao_text.lower()
):
    raise SystemExit(
        "[ERRO] Fase 10U-H não reconhecida: "
        "services/rodadas/criacao.py ainda possui "
        "acoplamento HTTP."
    )

print("      [OK] 10U-H reconhecida.")


print("[2/12] Analisando baseline do service...")

service_text = read_text(SERVICE)

try:
    current_state, diag = state(service_text)
except Exception as exc:
    raise SystemExit(
        f"[ERRO] Baseline não suportado: {exc}"
    )

print(f"      Estado: {current_state}")
print(f"      diagnóstico: {diag}")

if current_state == "DESCONHECIDO":
    raise SystemExit(
        "[ERRO] Baseline desconhecido. "
        "Nenhum arquivo foi alterado."
    )

if current_state == "MIGRADO_10V_A":
    print()
    print("[OK] Fase 10V-A já aplicada.")
    raise SystemExit(0)


print("[3/12] Confirmando erro alvo...")

item = target_http(service_text)[0]

print(
    f"      HTTP {item['status']} -> "
    "BusinessRuleViolation"
)

print(
    f"      detail: {item['detail_value']}"
)

print(
    f"      HTTPException totais antes: "
    f"{len(http_raises(service_text))}"
)


print("[4/12] Protegendo demais exceções...")

all_http = http_raises(service_text)

other_http = [
    item
    for item in all_http
    if not (
        item["status"] == EXPECTED_STATUS
        and item["detail_value"] == EXPECTED_DETAIL
    )
]

print(
    f"      [OK] {len(other_http)} "
    "HTTPException ficam fora do escopo."
)

for index, other in enumerate(other_http, start=1):
    print(
        f"      {index}. HTTP {other['status']} | "
        f"{other['detail_value'] or other['detail_source']}"
    )


print("[5/12] Validando chamadas críticas da R2...")

validate_required_business_calls(service_text)

for call in BUSINESS_CALLS_REQUIRED:
    print(f"      [OK] {call}")


print("[6/12] Validando fronteira HTTP existente...")

handlers = router_business_handlers()

if not handlers:
    raise SystemExit(
        "[ERRO] Nenhum router com "
        "BusinessRuleViolation -> HTTP 400 foi encontrado. "
        "Nenhum arquivo foi alterado."
    )

for path, fn_name in handlers:
    print(
        f"      [OK] {path}::{fn_name}"
    )


print("[7/12] Criando fingerprints estruturais...")

before_sql = sql_literals(service_text)
before_calls = call_counter(service_text)
before_tx = transaction_counts(service_text)

print(
    f"      SQL literals protegidos: {len(before_sql)}"
)

print(
    f"      chamadas AST protegidas: "
    f"{sum(before_calls.values())}"
)

print(
    "      [OK] conexão/transação protegidas."
)


print("[8/12] Criando backup...")

timestamp = datetime.now().strftime(
    "%Y%m%d_%H%M%S"
)

backup = (
    SERVICE.parent
    / (
        SERVICE.stem
        + "_backup_fase10v_a_"
        + timestamp
        + ".py"
    )
)

shutil.copy2(
    SERVICE,
    backup,
)

print(
    f"      {SERVICE.relative_to(ROOT)} "
    f"-> {backup.name}"
)


try:
    print("[9/12] Aplicando conversão...")

    patched = patch(service_text)

    SERVICE.write_text(
        patched,
        encoding="utf-8",
    )

    py_compile.compile(
        str(SERVICE),
        doraise=True,
    )

    print(
        "      [OK] R2 não concluída "
        "-> BusinessRuleViolation."
    )


    print("[10/12] Revalidando estado pós-patch...")

    final_text = read_text(SERVICE)
    final_state, final_diag = state(final_text)

    if final_state != "MIGRADO_10V_A":
        raise RuntimeError(
            f"Estado final inválido: {final_diag}"
        )

    print(
        f"      [OK] HTTPException: "
        f"{len(http_raises(service_text))} -> "
        f"{len(http_raises(final_text))}"
    )

    print(
        "      [OK] erro alvo preserva HTTP 400 "
        "na fronteira."
    )


    print("[11/12] Revalidando fingerprints...")

    if sql_literals(final_text) != before_sql:
        raise RuntimeError(
            "SQL alterado."
        )

    if call_counter(final_text) != before_calls:
        raise RuntimeError(
            "Chamadas de negócio alteradas."
        )

    if transaction_counts(final_text) != before_tx:
        raise RuntimeError(
            "Conexão/transação alterada."
        )

    print(
        "      [OK] SQL e chamadas de negócio "
        "inalterados."
    )

    print(
        "      [OK] UoW/commit/rollback/conexão "
        "inalterados."
    )


    print("[12/12] Confirmando escopo parcial...")

    remaining = http_raises(final_text)

    print(
        f"      [OK] {len(remaining)} "
        "HTTPException permanecem para "
        "as próximas subfases."
    )

    if remaining and not has_import(
        final_text,
        "fastapi",
        "HTTPException",
    ):
        raise RuntimeError(
            "FastAPI foi removido antes da hora."
        )

    print(
        "      [OK] FastAPI permanece somente "
        "porque ainda há HTTPException."
    )


except Exception:
    print()
    print("[ERRO] Falha durante Fase 10V-A.")
    print("[INFO] Restaurando backup...")

    shutil.copy2(
        backup,
        SERVICE,
    )

    print(
        f"      [OK] restaurado: "
        f"{SERVICE.relative_to(ROOT)}"
    )

    raise


print()
print("[OK] Fase 10V-A aplicada.")
print(
    "[OK] R2 não concluída operacionalmente "
    "-> BusinessRuleViolation / HTTP 400."
)
print(
    "[OK] demais HTTPException do módulo "
    "permaneceram intactas."
)
print(
    "[OK] SQL, análise R2, consolidação final, "
    "lifecycle e transações inalterados."
)

print()
print("PRÓXIMO PASSO:")
print("1. Reinicie a API.")
print(r"2. python tests_e2e\regressao_final_sgi.py")
print(r"3. python .\fase10a_auditoria_excecoes_dominio\auditar_fase10a.py")
