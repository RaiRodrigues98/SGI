
"""
FASE 10V-B - RODADAS / FINALIZAÇÃO ROTATIVO
Recorte: R2 existe, mas a R1 não foi localizada

Alvo:
services/rodadas/finalizacao_rotativo.py
└── _encerrar_inventario_rotativo_apos_r2()

Erro alvo legado:
HTTP 400
"Não foi possível localizar a R1 do inventário ROTATIVO."

Mapeamento:
HTTP 400 -> BusinessRuleViolation

Racional:
No fluxo ROTATIVO após R2, a R1 é um pré-requisito estrutural.
Se a R2 está sendo encerrada e a R1 não existe, o estado do
inventário está inconsistente. Para preservar o contrato atual,
o erro continua externamente HTTP 400.

Pré-requisito:
- Fase 10V-A aplicada:
  o erro "R2 ainda não concluída operacionalmente" já deve estar
  como BusinessRuleViolation.

A fase:
- altera somente 1 raise;
- não altera SQL;
- não altera consolidar_resultado_final_rotativo();
- não altera _finalizar_rodada_atual();
- não altera UoW/commit/rollback/conexão;
- não edita routers;
- mantém FastAPI enquanto restarem HTTPException;
- cria backup e auto-restaura em qualquer falha pós-mudança.
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

PREREQ_DETAIL = (
    "A R2 do inventário ROTATIVO ainda não foi "
    "concluída operacionalmente. Encerre todas as "
    "sessões e conclua todas as localizações previstas."
)

TARGET_STATUS = 400
TARGET_DETAIL = (
    "Não foi possível localizar a R1 "
    "do inventário ROTATIVO."
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
    root = (
        get_function(text, fn_name)
        if fn_name
        else parse(text, str(SERVICE))
    )

    result = []

    for node in ast.walk(root):
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


def find_http_by_detail(text, detail):
    return [
        item
        for item in http_raises(text, TARGET_FUNCTION)
        if (
            item["status"] == 400
            and item["detail_value"] == detail
        )
    ]


def find_business_by_detail(text, detail):
    return [
        item
        for item in semantic_raises(
            text,
            TARGET_FUNCTION,
            "BusinessRuleViolation",
        )
        if item["detail_value"] == detail
    ]


def has_import(text, module_name, symbol):
    tree = parse(text, str(SERVICE))

    return any(
        isinstance(node, ast.ImportFrom)
        and (node.module or "") == module_name
        and symbol in [alias.name for alias in node.names]
        for node in tree.body
    )


def fastapi_import_count(text):
    tree = parse(text, str(SERVICE))
    count = 0

    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if (
                module == "fastapi"
                or module.startswith("fastapi.")
                or module == "starlette"
                or module.startswith("starlette.")
            ):
                count += 1

        elif isinstance(node, ast.Import):
            if any(
                alias.name == "fastapi"
                or alias.name.startswith("fastapi.")
                or alias.name == "starlette"
                or alias.name.startswith("starlette.")
                for alias in node.names
            ):
                count += 1

    return count


def sql_literals(text):
    tree = parse(text, str(SERVICE))
    result = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant):
            continue

        if not isinstance(node.value, str):
            continue

        value = node.value
        upper = value.upper()

        if any(
            marker in upper
            for marker in (
                "SELECT ",
                "UPDATE ",
                "INSERT ",
                "DELETE ",
                "MERGE ",
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


def validate_required_calls(text):
    source = (
        ast.get_source_segment(
            text,
            get_function(text, TARGET_FUNCTION),
        )
        or ""
    )

    missing = [
        name
        for name in BUSINESS_CALLS_REQUIRED
        if name not in source
    ]

    if missing:
        raise RuntimeError(
            f"Chamadas críticas ausentes: {missing}"
        )


def validate_no_http_handlers(text):
    tree = parse(text, str(SERVICE))

    total = sum(
        1
        for node in ast.walk(tree)
        if (
            isinstance(node, ast.ExceptHandler)
            and handler_name(node) == "HTTPException"
        )
    )

    if total != 0:
        raise RuntimeError(
            f"Service possui {total} except HTTPException."
        )


def state(text):
    validate_required_calls(text)
    validate_no_http_handlers(text)

    prereq_http = find_http_by_detail(
        text,
        PREREQ_DETAIL,
    )

    prereq_business = find_business_by_detail(
        text,
        PREREQ_DETAIL,
    )

    target_http = find_http_by_detail(
        text,
        TARGET_DETAIL,
    )

    target_business = find_business_by_detail(
        text,
        TARGET_DETAIL,
    )

    total_http = len(http_raises(text))

    # Exige 10V-A aplicada.
    if (
        len(prereq_http) != 0
        or len(prereq_business) != 1
    ):
        return "PREREQUISITO_10V_A_AUSENTE", {
            "prereq_http": len(prereq_http),
            "prereq_business": len(prereq_business),
            "target_http": len(target_http),
            "target_business": len(target_business),
            "http_total": total_http,
        }

    if (
        len(target_http) == 1
        and len(target_business) == 0
        and has_import(text, "fastapi", "HTTPException")
        and has_import(
            text,
            "domain.exceptions",
            "BusinessRuleViolation",
        )
    ):
        return "LEGADO_10V_B", {
            "http_total": total_http,
            "target_http": 1,
            "target_business": 0,
            "fastapi_imports": fastapi_import_count(text),
        }

    if (
        len(target_http) == 0
        and len(target_business) == 1
        and has_import(
            text,
            "domain.exceptions",
            "BusinessRuleViolation",
        )
    ):
        expected_fastapi = total_http > 0
        actual_fastapi = fastapi_import_count(text) > 0

        if expected_fastapi != actual_fastapi:
            raise RuntimeError(
                "FastAPI inconsistente com HTTPException restantes: "
                f"http_total={total_http}, fastapi={actual_fastapi}"
            )

        return "MIGRADO_10V_B", {
            "http_total": total_http,
            "target_http": 0,
            "target_business": 1,
            "fastapi_imports": fastapi_import_count(text),
        }

    return "DESCONHECIDO", {
        "prereq_http": len(prereq_http),
        "prereq_business": len(prereq_business),
        "target_http": len(target_http),
        "target_business": len(target_business),
        "http_total": total_http,
        "http_details": [
            {
                "status": item["status"],
                "detail": item["detail_value"],
            }
            for item in http_raises(text)
        ],
    }


def remove_http_import_if_unused(text):
    if len(http_raises(text)) > 0:
        return text

    tree = parse(text, str(SERVICE))

    targets = [
        node
        for node in tree.body
        if (
            isinstance(node, ast.ImportFrom)
            and (node.module or "") == "fastapi"
            and "HTTPException"
            in [alias.name for alias in node.names]
        )
    ]

    if len(targets) != 1:
        raise RuntimeError(
            "Esperado exatamente 1 import FastAPI "
            "contendo HTTPException."
        )

    node = targets[0]

    remaining_aliases = [
        alias
        for alias in node.names
        if alias.name != "HTTPException"
    ]

    lines = text.splitlines()

    if remaining_aliases:
        rebuilt = (
            "from fastapi import "
            + ", ".join(
                (
                    alias.name
                    if alias.asname is None
                    else f"{alias.name} as {alias.asname}"
                )
                for alias in remaining_aliases
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

    if current_state != "LEGADO_10V_B":
        raise RuntimeError(
            f"Baseline 10V-B não reconhecido: "
            f"{current_state} / {diag}"
        )

    before_sql = sql_literals(text)
    before_calls = call_counter(text)
    before_tx = transaction_counts(text)
    before_http = len(http_raises(text))

    item = find_http_by_detail(
        text,
        TARGET_DETAIL,
    )[0]

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

    result = remove_http_import_if_unused(result)

    after_http = len(http_raises(result))

    if after_http != before_http - 1:
        raise RuntimeError(
            "HTTPException total não caiu exatamente em 1: "
            f"{before_http} -> {after_http}"
        )

    if sql_literals(result) != before_sql:
        raise RuntimeError(
            "SQL foi alterado."
        )

    if call_counter(result) != before_calls:
        raise RuntimeError(
            "Chamadas de negócio foram alteradas."
        )

    if transaction_counts(result) != before_tx:
        raise RuntimeError(
            "Conexão/transação foi alterada."
        )

    final_state, final_diag = state(result)

    if final_state != "MIGRADO_10V_B":
        raise RuntimeError(
            f"Estado pós-patch inválido: {final_diag}"
        )

    return result


print("[0/11] Validando arquivos...")

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


print("[1/11] Validando 10U-H...")

criacao_text = read_text(CRIACAO)

if (
    "HTTPException" in criacao_text
    or "fastapi" in criacao_text.lower()
    or "starlette" in criacao_text.lower()
):
    raise SystemExit(
        "[ERRO] 10U-H não reconhecida: "
        "criacao.py ainda possui acoplamento HTTP."
    )

print("      [OK] 10U-H reconhecida.")


print("[2/11] Validando 10V-A e baseline 10V-B...")

service_text = read_text(SERVICE)

current_state, diag = state(service_text)

print(f"      Estado: {current_state}")
print(f"      diagnóstico: {diag}")

if current_state == "PREREQUISITO_10V_A_AUSENTE":
    raise SystemExit(
        "[ERRO] 10V-A ainda não está aplicada. "
        "Nenhum arquivo foi alterado."
    )

if current_state == "DESCONHECIDO":
    raise SystemExit(
        "[ERRO] Baseline desconhecido. "
        "Nenhum arquivo foi alterado."
    )

if current_state == "MIGRADO_10V_B":
    print()
    print("[OK] Fase 10V-B já aplicada.")
    raise SystemExit(0)


print("[3/11] Confirmando erro alvo...")

item = find_http_by_detail(
    service_text,
    TARGET_DETAIL,
)[0]

print(
    f"      HTTP {item['status']} "
    "-> BusinessRuleViolation"
)

print(
    f"      detail: {item['detail_value']}"
)

print(
    f"      HTTPException totais antes: "
    f"{len(http_raises(service_text))}"
)


print("[4/11] Listando exceções fora do escopo...")

others = [
    item
    for item in http_raises(service_text)
    if item["detail_value"] != TARGET_DETAIL
]

print(
    f"      [OK] {len(others)} "
    "HTTPException permanecerão intactas."
)

for index, other in enumerate(others, start=1):
    print(
        f"      {index}. HTTP {other['status']} | "
        f"{other['detail_value'] or other['detail_source']}"
    )


print("[5/11] Validando fluxo crítico R2...")

validate_required_calls(service_text)

for call in BUSINESS_CALLS_REQUIRED:
    print(f"      [OK] {call}")


print("[6/11] Criando fingerprints...")

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


print("[7/11] Criando backup...")

timestamp = datetime.now().strftime(
    "%Y%m%d_%H%M%S"
)

backup = (
    SERVICE.parent
    / (
        SERVICE.stem
        + "_backup_fase10v_b_"
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
    print("[8/11] Aplicando conversão...")

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
        "      [OK] R1 ausente "
        "-> BusinessRuleViolation."
    )


    print("[9/11] Revalidando estado pós-patch...")

    final_text = read_text(SERVICE)
    final_state, final_diag = state(final_text)

    if final_state != "MIGRADO_10V_B":
        raise RuntimeError(
            f"Estado final inválido: {final_diag}"
        )

    print(
        f"      [OK] HTTPException: "
        f"{len(http_raises(service_text))} -> "
        f"{len(http_raises(final_text))}"
    )


    print("[10/11] Revalidando fingerprints...")

    if sql_literals(final_text) != before_sql:
        raise RuntimeError("SQL alterado.")

    if call_counter(final_text) != before_calls:
        raise RuntimeError(
            "Chamadas de negócio alteradas."
        )

    if transaction_counts(final_text) != before_tx:
        raise RuntimeError(
            "Conexão/transação alterada."
        )

    print(
        "      [OK] SQL, chamadas e "
        "transações inalterados."
    )


    print("[11/11] Confirmando escopo parcial...")

    remaining = http_raises(final_text)

    print(
        f"      [OK] {len(remaining)} "
        "HTTPException permanecem no módulo."
    )

    if remaining and not has_import(
        final_text,
        "fastapi",
        "HTTPException",
    ):
        raise RuntimeError(
            "FastAPI removido antes da hora."
        )

    print(
        "      [OK] FastAPI permanece apenas "
        "enquanto houver HTTPException."
    )


except Exception:
    print()
    print("[ERRO] Falha durante Fase 10V-B.")
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
print("[OK] Fase 10V-B aplicada.")
print(
    "[OK] ausência da R1 durante encerramento R2 "
    "-> BusinessRuleViolation / HTTP 400."
)
print(
    "[OK] demais HTTPException permaneceram intactas."
)
print(
    "[OK] SQL, consolidação final, lifecycle e "
    "transações inalterados."
)

print()
print("PRÓXIMO PASSO:")
print("1. Reinicie a API.")
print(r"2. python tests_e2e\regressao_final_sgi.py")
print(r"3. python .\fase10a_auditoria_excecoes_dominio\auditar_fase10a.py")
