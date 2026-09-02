
"""
FASE 10U-G - CRIAÇÃO DE RODADAS | TIPO NÃO SUPORTADO

Alvo:
services/rodadas/criacao.py
└── _selecionar_candidatos()
    └── raise HTTP 400:
        "Tipo de próxima rodada não suportado: {tipo_proxima}"

Pré-requisito:
Fase 10U-F aplicada.

Mapeamento:
HTTP 400 -> BusinessRuleViolation

Esta fase altera SOMENTE o service.
A fronteira HTTP já foi adaptada nas fases 10U anteriores para
BusinessRuleViolation -> HTTP 400.

Depois:
- _selecionar_candidatos:
    2 BusinessRuleViolation
    5 HTTPException
- criacao.py:
    exatamente 5 HTTPException
- os 5 remanescentes pertencem ao fluxo gerencial
- FastAPI permanece temporariamente

Não altera:
- fluxo OFICIAL
- fluxo ROTATIVO
- fluxo GESTOR já migrado
- NOVA_RECONTAGEM
- SQL
- UoW
- commit/rollback
- sp_getapplock
"""

from pathlib import Path
from datetime import datetime
import ast
import py_compile
import shutil

ROOT = Path.cwd()

SERVICE = ROOT / "services" / "rodadas" / "criacao.py"
DOMAIN = ROOT / "domain" / "exceptions.py"

TARGET_FUNCTION = "_selecionar_candidatos"

PREREQ_CONFIG = "_carregar_configuracao_criacao"
PREREQ_SESSIONS = "_validar_sem_sessoes_abertas"
PREREQ_LOCK = "_serializar_criacao_r2_rotativo"
PREREQ_DIVERGENCIA = "_validar_candidatos_divergencia"
PREREQ_LOCALIZACOES = "_gerar_localizacoes_nova_rodada"

TARGET_STATUS = 400
TARGET_MARKER = "Tipo de próxima rodada não suportado"
TARGET_DYNAMIC = "tipo_proxima"

EXPECTED_HTTP_BEFORE = 6
EXPECTED_HTTP_AFTER = 5

# Os cinco HTTPException que DEVEM permanecer após esta fase.
REMAINING_MARKERS = (
    "divergente(s) sem decisão do gestor",
    "Todas as divergências foram",
    "Nenhum item foi marcado como",
    "A análise gerencial indica itens",
    "Inconsistência entre a análise",
)

CRITICAL_TOKENS = (
    "sys.sp_getapplock",
    "SGI:ROTATIVO:PROXIMA_RODADA:",
    "@LockMode = 'Exclusive'",
    "@LockOwner = 'Transaction'",
    "@LockTimeout = 10000",
)

PROTECTED_TOKENS = (
    "get_connection()",
    "SqlServerUnitOfWork()",
    "uow.open()",
    "conn.cursor()",
    "uow.cursor",
    "cursor.close()",
    "conn.close()",
    "uow.close()",
    "conn.commit()",
    "uow.commit()",
    *CRITICAL_TOKENS,
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


def functions(text):
    tree = parse(text, str(SERVICE))
    return {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def function(text, name):
    fn = functions(text).get(name)
    if fn is None:
        raise RuntimeError(f"Função ausente: {name}")
    return fn


def raises_of(text, fn_name, exc_name):
    fn = function(text, fn_name)
    result = []

    for node in ast.walk(fn):
        if not isinstance(node, ast.Raise) or node.exc is None:
            continue

        if raised_name(node.exc) != exc_name:
            continue

        result.append(node)

    return result


def http_raises(text, fn_name):
    fn = function(text, fn_name)
    result = []

    for node in ast.walk(fn):
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
            raise RuntimeError(
                f"{fn_name}: HTTPException sem status/detail."
            )

        if not (
            isinstance(status_node, ast.Constant)
            and isinstance(status_node.value, int)
        ):
            raise RuntimeError(
                f"{fn_name}: status_code dinâmico não suportado."
            )

        detail_source = ast.get_source_segment(text, detail_node)

        if not detail_source:
            raise RuntimeError(
                f"{fn_name}: detail não recuperado via AST."
            )

        result.append({
            "node": node,
            "status": status_node.value,
            "detail_source": detail_source,
        })

    return sorted(result, key=lambda item: item["node"].lineno)


def count_http_total(text):
    tree = parse(text, str(SERVICE))
    return sum(
        1
        for node in ast.walk(tree)
        if (
            isinstance(node, ast.Raise)
            and node.exc is not None
            and raised_name(node.exc) == "HTTPException"
        )
    )


def import_has(text, module_name, symbol):
    tree = parse(text, str(SERVICE))

    return any(
        isinstance(node, ast.ImportFrom)
        and (node.module or "") == module_name
        and symbol in [alias.name for alias in node.names]
        for node in tree.body
    )


def protected_counts(text):
    return {
        token: text.count(token)
        for token in PROTECTED_TOKENS
    }


def validate_lock(text):
    counts = {
        token: text.count(token)
        for token in CRITICAL_TOKENS
    }

    invalid = {
        token: count
        for token, count in counts.items()
        if count != 1
    }

    if invalid:
        raise RuntimeError(
            f"Contrato sp_getapplock inesperado: {invalid}"
        )

    source = ast.get_source_segment(
        text,
        function(text, PREREQ_LOCK),
    ) or ""

    for token in CRITICAL_TOKENS:
        if token not in source:
            raise RuntimeError(
                f"Token crítico fora de {PREREQ_LOCK}: {token}"
            )

    return counts


def validate_previous_phases(text):
    checks = {
        "config_brv":
            len(raises_of(
                text,
                PREREQ_CONFIG,
                "BusinessRuleViolation",
            )),
        "config_http":
            len(http_raises(text, PREREQ_CONFIG)),

        "sessions_brv":
            len(raises_of(
                text,
                PREREQ_SESSIONS,
                "BusinessRuleViolation",
            )),
        "sessions_http":
            len(http_raises(text, PREREQ_SESSIONS)),

        "lock_conflict":
            len(raises_of(
                text,
                PREREQ_LOCK,
                "ConflictError",
            )),
        "lock_http":
            len(http_raises(text, PREREQ_LOCK)),

        "div_brv":
            len(raises_of(
                text,
                PREREQ_DIVERGENCIA,
                "BusinessRuleViolation",
            )),
        "div_http":
            len(http_raises(text, PREREQ_DIVERGENCIA)),

        "loc_brv":
            len(raises_of(
                text,
                PREREQ_LOCALIZACOES,
                "BusinessRuleViolation",
            )),
        "loc_http":
            len(http_raises(text, PREREQ_LOCALIZACOES)),
    }

    expected = {
        "config_brv": 3,
        "config_http": 0,
        "sessions_brv": 1,
        "sessions_http": 0,
        "lock_conflict": 1,
        "lock_http": 0,
        "div_brv": 1,
        "div_http": 0,
        "loc_brv": 1,
        "loc_http": 0,
    }

    if checks != expected:
        raise RuntimeError(
            "Pré-requisitos 10U-A..E não conferem: "
            f"{checks}"
        )

    # 10U-F deve ter introduzido 1 BRV dentro de _selecionar_candidatos.
    brv_selection = len(
        raises_of(
            text,
            TARGET_FUNCTION,
            "BusinessRuleViolation",
        )
    )

    if brv_selection not in (1, 2):
        raise RuntimeError(
            "Fase 10U-F não reconhecida em "
            f"{TARGET_FUNCTION}: "
            f"BusinessRuleViolation={brv_selection}"
        )

    return checks, brv_selection


def locate_target(items):
    matches = [
        item
        for item in items
        if (
            item["status"] == TARGET_STATUS
            and TARGET_MARKER in item["detail_source"]
            and TARGET_DYNAMIC in item["detail_source"]
        )
    ]

    if len(matches) != 1:
        raise RuntimeError(
            "Esperado exatamente 1 HTTPException de "
            f"tipo não suportado; encontrado {len(matches)}."
        )

    return matches[0]


def validate_remaining(items, exclude_line=None):
    remaining = [
        item
        for item in items
        if (
            exclude_line is None
            or item["node"].lineno != exclude_line
        )
    ]

    source = "\n".join(
        item["detail_source"]
        for item in remaining
    )

    missing = [
        marker
        for marker in REMAINING_MARKERS
        if marker not in source
    ]

    if missing:
        raise RuntimeError(
            "Perfil das validações gerenciais remanescentes mudou. "
            f"Marcadores ausentes: {missing}"
        )

    if any(item["status"] != 400 for item in remaining):
        raise RuntimeError(
            "Existe HTTPException gerencial com status diferente de 400."
        )

    return remaining


def state(text):
    validate_previous_phases(text)
    validate_lock(text)

    if not import_has(text, "fastapi", "HTTPException"):
        raise RuntimeError(
            "Import HTTPException deveria permanecer "
            "enquanto existirem raises em criacao.py."
        )

    if not import_has(
        text,
        "domain.exceptions",
        "BusinessRuleViolation",
    ):
        raise RuntimeError(
            "BusinessRuleViolation não importada."
        )

    if not import_has(
        text,
        "domain.exceptions",
        "ConflictError",
    ):
        raise RuntimeError(
            "ConflictError não importada."
        )

    items = http_raises(
        text,
        TARGET_FUNCTION,
    )

    total_http = count_http_total(text)

    brv_selection = len(
        raises_of(
            text,
            TARGET_FUNCTION,
            "BusinessRuleViolation",
        )
    )

    # Antes da 10U-G.
    if (
        len(items) == EXPECTED_HTTP_BEFORE
        and total_http == EXPECTED_HTTP_BEFORE
        and brv_selection == 1
    ):
        target = locate_target(items)
        remaining = validate_remaining(
            items,
            exclude_line=target["node"].lineno,
        )

        if len(remaining) != 5:
            raise RuntimeError(
                "Esperados 5 HTTPException gerenciais "
                f"remanescentes; encontrado {len(remaining)}."
            )

        return "LEGADO_10U_G", {
            "http_total": total_http,
            "selection_http": len(items),
            "selection_brv": brv_selection,
            "target_line": target["node"].lineno,
        }

    # Depois da 10U-G.
    if (
        len(items) == EXPECTED_HTTP_AFTER
        and total_http == EXPECTED_HTTP_AFTER
        and brv_selection == 2
    ):
        remaining = validate_remaining(items)

        if len(remaining) != 5:
            raise RuntimeError(
                "Esperados exatamente 5 HTTPException "
                "gerenciais após 10U-G."
            )

        return "MIGRADO_10U_G", {
            "http_total": total_http,
            "selection_http": len(items),
            "selection_brv": brv_selection,
        }

    return "DESCONHECIDO", {
        "http_total": total_http,
        "selection_http": len(items),
        "selection_brv": brv_selection,
        "details": [
            item["detail_source"]
            for item in items
        ],
    }


def patch(text):
    current_state, diag = state(text)

    if current_state != "LEGADO_10U_G":
        raise RuntimeError(
            "Baseline 10U-G não reconhecido: "
            f"{current_state} / {diag}"
        )

    before_protected = protected_counts(text)
    before_lock = validate_lock(text)

    items = http_raises(
        text,
        TARGET_FUNCTION,
    )

    target = locate_target(items)

    validate_remaining(
        items,
        exclude_line=target["node"].lineno,
    )

    node = target["node"]
    indent = " " * node.col_offset

    replacement = (
        f"{indent}raise BusinessRuleViolation(\n"
        f"{indent}    {target['detail_source']}\n"
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

    after_protected = protected_counts(result)

    if before_protected != after_protected:
        differences = {
            token: (
                before_protected[token],
                after_protected[token],
            )
            for token in PROTECTED_TOKENS
            if (
                before_protected[token]
                != after_protected[token]
            )
        }

        raise RuntimeError(
            "SQL/UoW/commit/applock alterado: "
            f"{differences}"
        )

    if validate_lock(result) != before_lock:
        raise RuntimeError(
            "Contrato sp_getapplock mudou."
        )

    final_state, final_diag = state(result)

    if final_state != "MIGRADO_10U_G":
        raise RuntimeError(
            "Estado pós-patch inválido: "
            f"{final_diag}"
        )

    return result


print("[0/10] Validando arquivos...")

for path in (SERVICE, DOMAIN):
    if not path.exists():
        raise SystemExit(
            f"[ERRO] Arquivo ausente: {path}"
        )

domain_text = read_text(DOMAIN)

for token in (
    "class BusinessRuleViolation(DomainError)",
    "class ConflictError(DomainError)",
):
    if token not in domain_text:
        raise SystemExit(
            f"[ERRO] Exceção de domínio ausente: {token}"
        )

print("      [OK] hierarquia de exceções disponível.")


print("[1/10] Validando baseline 10U-G...")

service_text = read_text(SERVICE)

try:
    current_state, diag = state(service_text)
except Exception as exc:
    raise SystemExit(
        f"[ERRO] Baseline não reconhecido: {exc}"
    )

print(f"      Estado: {current_state}")
print(f"      diagnóstico: {diag}")

if current_state == "MIGRADO_10U_G":
    print()
    print("[OK] Fase 10U-G já aplicada.")
    raise SystemExit(0)

if current_state != "LEGADO_10U_G":
    raise SystemExit(
        f"[ERRO] Estado inesperado: {current_state}"
    )


print("[2/10] Confirmando alvo dinâmico...")

items = http_raises(
    service_text,
    TARGET_FUNCTION,
)

target = locate_target(items)

print(
    f"      HTTP {target['status']} -> "
    "BusinessRuleViolation"
)
print(
    f"      detail source: "
    f"{target['detail_source']}"
)

remaining = validate_remaining(
    items,
    exclude_line=target["node"].lineno,
)

print(
    f"      [OK] 1 alvo + "
    f"{len(remaining)} validações gerenciais preservadas."
)


print("[3/10] Revalidando sp_getapplock...")

lock_before = validate_lock(
    service_text
)

for token, count in lock_before.items():
    print(
        f"      [OK] {token}: {count}"
    )


print("[4/10] Confirmando proteção estrutural...")

before_protected = protected_counts(
    service_text
)

print(
    "      [OK] SQL/UoW/commit/applock "
    "serão comparados por contagem exata."
)


print("[5/10] Criando backup...")

timestamp = datetime.now().strftime(
    "%Y%m%d_%H%M%S"
)

backup = (
    SERVICE.parent
    / (
        SERVICE.stem
        + "_backup_fase10u_g_"
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
    print("[6/10] Aplicando conversão...")

    patched = patch(
        service_text
    )

    SERVICE.write_text(
        patched,
        encoding="utf-8",
    )

    py_compile.compile(
        str(SERVICE),
        doraise=True,
    )

    print(
        "      [OK] HTTP 400 -> "
        "BusinessRuleViolation."
    )


    print("[7/10] Revalidando baseline pós-patch...")

    final_text = read_text(
        SERVICE
    )

    final_state, final_diag = state(
        final_text
    )

    if final_state != "MIGRADO_10U_G":
        raise RuntimeError(
            f"Estado final inválido: {final_diag}"
        )

    print(
        "      [OK] "
        "_selecionar_candidatos = "
        "2 BusinessRuleViolation."
    )

    print(
        "      [OK] "
        "_selecionar_candidatos = "
        "5 HTTPException."
    )


    print("[8/10] Revalidando os 5 raises gerenciais...")

    final_items = http_raises(
        final_text,
        TARGET_FUNCTION,
    )

    validate_remaining(
        final_items
    )

    print(
        "      [OK] cinco validações "
        "gerenciais permaneceram intactas."
    )


    print("[9/10] Revalidando contrato de concorrência...")

    if validate_lock(
        final_text
    ) != lock_before:
        raise RuntimeError(
            "Contrato sp_getapplock foi alterado."
        )

    print(
        "      [OK] Exclusive / Transaction / "
        "timeout 10000 preservados."
    )


    print("[10/10] Revalidando SQL/UoW/commit...")

    after_protected = protected_counts(
        final_text
    )

    if after_protected != before_protected:
        differences = {
            token: (
                before_protected[token],
                after_protected[token],
            )
            for token in PROTECTED_TOKENS
            if (
                before_protected[token]
                != after_protected[token]
            )
        }

        raise RuntimeError(
            f"Proteção estrutural falhou: {differences}"
        )

    print(
        "      [OK] SQL/UoW/commit/rollback "
        "e lock inalterados."
    )


except Exception:
    print()
    print("[ERRO] Falha durante Fase 10U-G.")
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
print("[OK] Fase 10U-G aplicada.")
print(
    "[OK] tipo de próxima rodada não suportado "
    "-> BusinessRuleViolation / HTTP 400."
)
print(
    "[OK] exatamente 5 HTTPException "
    "permaneceram em _selecionar_candidatos."
)
print(
    "[OK] todos pertencem ao fluxo gerencial "
    "de NOVA_RECONTAGEM."
)
print(
    "[OK] FastAPI permanece temporariamente "
    "em criacao.py."
)
print(
    "[OK] fluxo OFICIAL, ROTATIVO e "
    "sp_getapplock inalterados."
)

print()
print("PRÓXIMO PASSO:")
print("1. Reinicie a API.")
print(
    r"2. python tests_e2e\regressao_final_sgi.py"
)
print(
    r"3. python .\fase10a_auditoria_excecoes_dominio\auditar_fase10a.py"
)
