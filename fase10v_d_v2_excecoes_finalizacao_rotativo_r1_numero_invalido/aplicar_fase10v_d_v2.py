
"""
FASE 10V-D v2 - RODADAS / FINALIZAÇÃO ROTATIVO
Recorte: encerramento pela R1 chamado fora da primeira rodada

CORREÇÃO DA v1
--------------
A v1 exigia detalhes de implementação como "SessoesContagem",
"DecisoesRotativo" e "OcorrenciasDivergencia" dentro do service.
Isso é incompatível com o estado refatorado, onde persistência/
consultas podem ter sido movidas para repositories/helpers.

A v2 valida CONTRATO e SEMÂNTICA, não detalhes internos:
- função alvo existe;
- 10V-A/B/C estão migradas;
- erro alvo existe exatamente uma vez;
- HTTP 400 preservado;
- total HTTP cai exatamente em 1;
- SQL existente não muda;
- chamadas existentes não mudam;
- UoW/commit/rollback/conexão não mudam.

Alvo:
services/rodadas/finalizacao_rotativo.py
└── _encerrar_inventario_rotativo_apos_r1_sem_recontagem()

Erro:
HTTP 400
"Encerramento ROTATIVO pela R1 disponível somente para a primeira rodada."

Mapeamento:
HTTP 400 -> BusinessRuleViolation
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

R1_FUNCTION = "_encerrar_inventario_rotativo_apos_r1_sem_recontagem"
R2_FUNCTION = "_encerrar_inventario_rotativo_apos_r2"

PREREQ_A = (
    "A R2 do inventário ROTATIVO ainda não foi "
    "concluída operacionalmente. Encerre todas as "
    "sessões e conclua todas as localizações previstas."
)

PREREQ_B = (
    "Não foi possível localizar a R1 "
    "do inventário ROTATIVO."
)

PREREQ_C = (
    "Não foi possível finalizar "
    "o inventário ROTATIVO."
)

TARGET_DETAIL = (
    "Encerramento ROTATIVO pela R1 disponível "
    "somente para a primeira rodada."
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


def top_functions(text):
    tree = parse(text, str(SERVICE))
    return {
        n.name: n
        for n in tree.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def get_function(text, name):
    fn = top_functions(text).get(name)
    if fn is None:
        raise RuntimeError(f"Função ausente: {name}")
    return fn


def http_raises(text, fn_name=None):
    root = get_function(text, fn_name) if fn_name else parse(text, str(SERVICE))
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


def find_http(text, fn_name, detail):
    return [
        item
        for item in http_raises(text, fn_name)
        if item["status"] == 400 and item["detail_value"] == detail
    ]


def find_business(text, fn_name, detail):
    return [
        item
        for item in semantic_raises(
            text,
            fn_name,
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
    total = 0

    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if (
                module == "fastapi"
                or module.startswith("fastapi.")
                or module == "starlette"
                or module.startswith("starlette.")
            ):
                total += 1
        elif isinstance(node, ast.Import):
            if any(
                alias.name == "fastapi"
                or alias.name.startswith("fastapi.")
                or alias.name == "starlette"
                or alias.name.startswith("starlette.")
                for alias in node.names
            ):
                total += 1

    return total


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

        # A troca HTTPException -> BusinessRuleViolation não conta
        # como alteração de fluxo/chamada de negócio.
        if name in {"HTTPException", "BusinessRuleViolation"}:
            continue

        if name:
            counter[name] += 1

    return counter


def transaction_counts(text):
    return {
        token: text.count(token)
        for token in TRANSACTION_TOKENS
    }


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
            f"Service possui {total} except HTTPException; "
            "baseline não suportado."
        )


def validate_function_contract(text):
    # Não exige banco/repository/helper específico.
    r1 = get_function(text, R1_FUNCTION)
    r2 = get_function(text, R2_FUNCTION)

    r1_source = ast.get_source_segment(text, r1) or ""
    r2_source = ast.get_source_segment(text, r2) or ""

    # O alvo deve continuar semanticamente ligado ao número da rodada.
    if "NumeroRodada" not in r1_source:
        raise RuntimeError(
            "Contrato da função R1 inesperado: "
            "não foi encontrado uso de NumeroRodada."
        )

    # R2 precisa continuar sendo um fluxo real, mas sem exigir
    # implementação SQL/repository específica.
    required_r2 = (
        "consolidar_resultado_final_rotativo",
        "_finalizar_rodada_atual",
    )

    missing = [
        token
        for token in required_r2
        if token not in r2_source
    ]

    if missing:
        raise RuntimeError(
            f"Contrato R2 inesperado; chamadas ausentes: {missing}"
        )


def state(text):
    validate_no_http_handlers(text)
    validate_function_contract(text)

    prereqs = {
        "10V_A": (
            len(find_http(text, R2_FUNCTION, PREREQ_A)),
            len(find_business(text, R2_FUNCTION, PREREQ_A)),
        ),
        "10V_B": (
            len(find_http(text, R2_FUNCTION, PREREQ_B)),
            len(find_business(text, R2_FUNCTION, PREREQ_B)),
        ),
        "10V_C": (
            len(find_http(text, R2_FUNCTION, PREREQ_C)),
            len(find_business(text, R2_FUNCTION, PREREQ_C)),
        ),
    }

    for phase in ("10V_A", "10V_B", "10V_C"):
        if prereqs[phase] != (0, 1):
            return f"PREREQUISITO_{phase}_AUSENTE", {
                "prereqs": prereqs,
                "http_total": len(http_raises(text)),
            }

    target_http = find_http(
        text,
        R1_FUNCTION,
        TARGET_DETAIL,
    )

    target_brv = find_business(
        text,
        R1_FUNCTION,
        TARGET_DETAIL,
    )

    total_http = len(http_raises(text))

    if (
        len(target_http) == 1
        and len(target_brv) == 0
        and has_import(text, "fastapi", "HTTPException")
        and has_import(
            text,
            "domain.exceptions",
            "BusinessRuleViolation",
        )
    ):
        return "LEGADO_10V_D_V2", {
            "prereqs": prereqs,
            "http_total": total_http,
            "target_http": 1,
            "target_brv": 0,
            "fastapi_imports": fastapi_import_count(text),
        }

    if (
        len(target_http) == 0
        and len(target_brv) == 1
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

        return "MIGRADO_10V_D_V2", {
            "prereqs": prereqs,
            "http_total": total_http,
            "target_http": 0,
            "target_brv": 1,
            "fastapi_imports": fastapi_import_count(text),
        }

    return "DESCONHECIDO", {
        "prereqs": prereqs,
        "http_total": total_http,
        "target_http": len(target_http),
        "target_brv": len(target_brv),
        "http_details": [
            {
                "status": item["status"],
                "detail": item["detail_value"],
                "detail_source": item["detail_source"],
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
            "Esperado exatamente 1 import FastAPI contendo HTTPException."
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
                alias.name
                if alias.asname is None
                else f"{alias.name} as {alias.asname}"
                for alias in remaining_aliases
            )
        )
        lines[node.lineno - 1:node.end_lineno] = [rebuilt]
    else:
        lines[node.lineno - 1:node.end_lineno] = []

    result = "\n".join(lines)

    if text.endswith("\n"):
        result += "\n"

    return result


def patch(text):
    current_state, diag = state(text)

    if current_state != "LEGADO_10V_D_V2":
        raise RuntimeError(
            "Baseline 10V-D v2 não reconhecido: "
            f"{current_state} / {diag}"
        )

    before_sql = sql_literals(text)
    before_calls = call_counter(text)
    before_tx = transaction_counts(text)
    before_http = len(http_raises(text))

    item = find_http(
        text,
        R1_FUNCTION,
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
    lines[node.lineno - 1:node.end_lineno] = replacement.splitlines()

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
            "SQL literal foi alterado."
        )

    if call_counter(result) != before_calls:
        raise RuntimeError(
            "Chamadas de negócio/repository/helper foram alteradas."
        )

    if transaction_counts(result) != before_tx:
        raise RuntimeError(
            "Conexão/UoW/commit/rollback foi alterado."
        )

    final_state, final_diag = state(result)

    if final_state != "MIGRADO_10V_D_V2":
        raise RuntimeError(
            f"Estado pós-patch inválido: {final_diag}"
        )

    return result


print("[0/10] Validando arquivos e exceções...")

for path in (SERVICE, DOMAIN, CRIACAO):
    if not path.exists():
        raise SystemExit(
            f"[ERRO] Arquivo ausente: {path}"
        )

domain_text = read_text(DOMAIN)

if "class BusinessRuleViolation(DomainError)" not in domain_text:
    raise SystemExit(
        "[ERRO] BusinessRuleViolation ausente."
    )

print("      [OK] arquivos-base presentes.")


print("[1/10] Validando pré-requisito 10U-H...")

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


print("[2/10] Validando 10V-A/B/C e baseline real...")

service_text = read_text(SERVICE)

try:
    current_state, diag = state(service_text)
except Exception as exc:
    raise SystemExit(
        f"[ERRO] Baseline não suportado: {exc}"
    )

print(f"      Estado: {current_state}")
print(f"      diagnóstico: {diag}")

if current_state.startswith("PREREQUISITO_"):
    raise SystemExit(
        f"[ERRO] {current_state}. Nenhum arquivo foi alterado."
    )

if current_state == "DESCONHECIDO":
    raise SystemExit(
        "[ERRO] Baseline desconhecido. Nenhum arquivo foi alterado."
    )

if current_state == "MIGRADO_10V_D_V2":
    print()
    print("[OK] Fase 10V-D v2 já aplicada.")
    raise SystemExit(0)

print("      [OK] 10V-A/B/C reconhecidas.")


print("[3/10] Confirmando alvo da R1...")

item = find_http(
    service_text,
    R1_FUNCTION,
    TARGET_DETAIL,
)[0]

print(
    f"      HTTP {item['status']} -> BusinessRuleViolation"
)
print(
    f"      detail: {item['detail_value']}"
)
print(
    f"      HTTPException totais antes: "
    f"{len(http_raises(service_text))}"
)


print("[4/10] Listando raises preservados...")

others = [
    x
    for x in http_raises(service_text)
    if x["node"].lineno != item["node"].lineno
]

print(
    f"      [OK] {len(others)} HTTPException fora do escopo."
)

for idx, other in enumerate(others, 1):
    print(
        f"      {idx}. HTTP {other['status']} | "
        f"{other['detail_value'] or other['detail_source']}"
    )


print("[5/10] Criando fingerprints independentes da implementação...")

before_sql = sql_literals(service_text)
before_calls = call_counter(service_text)
before_tx = transaction_counts(service_text)

print(
    f"      SQL literals presentes/protegidos: {len(before_sql)}"
)
print(
    f"      chamadas AST protegidas: {sum(before_calls.values())}"
)
print(
    "      [OK] não exige SessoesContagem/DecisoesRotativo/"
    "OcorrenciasDivergencia no service."
)


print("[6/10] Criando backup...")

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

backup = (
    SERVICE.parent
    / (
        SERVICE.stem
        + "_backup_fase10v_d_v2_"
        + timestamp
        + ".py"
    )
)

shutil.copy2(SERVICE, backup)

print(
    f"      {SERVICE.relative_to(ROOT)} -> {backup.name}"
)


try:
    print("[7/10] Aplicando conversão...")

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
        "      [OK] NumeroRodada incompatível com "
        "encerramento R1 -> BusinessRuleViolation."
    )


    print("[8/10] Revalidando estado...")

    final_text = read_text(SERVICE)

    final_state, final_diag = state(final_text)

    if final_state != "MIGRADO_10V_D_V2":
        raise RuntimeError(
            f"Estado final inválido: {final_diag}"
        )

    print(
        f"      [OK] HTTPException: "
        f"{len(http_raises(service_text))} -> "
        f"{len(http_raises(final_text))}"
    )


    print("[9/10] Revalidando fingerprints...")

    if sql_literals(final_text) != before_sql:
        raise RuntimeError("SQL foi alterado.")

    if call_counter(final_text) != before_calls:
        raise RuntimeError(
            "Chamadas de negócio/repository/helper foram alteradas."
        )

    if transaction_counts(final_text) != before_tx:
        raise RuntimeError(
            "Conexão/UoW/transações foram alteradas."
        )

    print(
        "      [OK] SQL/chamadas/UoW/transações inalterados."
    )


    print("[10/10] Confirmando escopo parcial...")

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
        "      [OK] FastAPI permanece somente enquanto necessário."
    )


except Exception:
    print()
    print("[ERRO] Falha durante Fase 10V-D v2.")
    print("[INFO] Restaurando backup...")

    shutil.copy2(backup, SERVICE)

    print(
        f"      [OK] restaurado: {SERVICE.relative_to(ROOT)}"
    )

    raise


print()
print("[OK] Fase 10V-D v2 aplicada.")
print(
    "[OK] encerramento R1 fora da primeira rodada "
    "-> BusinessRuleViolation / HTTP 400."
)
print(
    "[OK] implementação via SQL/repository/helper preservada."
)
print(
    "[OK] demais HTTPException intactas."
)
print()
print("PRÓXIMO PASSO:")
print("1. Reinicie a API.")
print(r"2. python tests_e2e\regressao_final_sgi.py")
print(r"3. python .\fase10a_auditoria_excecoes_dominio\auditar_fase10a.py")
