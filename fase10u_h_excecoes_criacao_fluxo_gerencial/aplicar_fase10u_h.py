
"""
FASE 10U-H - CRIAÇÃO DE RODADAS | FECHAMENTO DO FLUXO GERENCIAL

Alvo:
services/rodadas/criacao.py
└── _selecionar_candidatos()
    └── os 5 HTTPException restantes do fluxo gerencial/NOVA_RECONTAGEM

Pré-requisito:
Fase 10U-G aplicada.

Baseline esperado após 10U-G:
- _selecionar_candidatos:
    2 BusinessRuleViolation
    5 HTTPException
- criacao.py:
    exatamente 5 HTTPException no total
- todos os 5 estão dentro de _selecionar_candidatos
- todos são HTTP 400

Os 5 erros gerenciais:
1. Existem itens divergentes sem decisão do gestor.
2. Todas as divergências foram tratadas e o inventário está apto para finalização.
3. Nenhum item foi marcado como NOVA_RECONTAGEM.
4. A análise gerencial indica itens para recontagem, porém nenhum registro
   NOVA_RECONTAGEM foi localizado.
5. Inconsistência entre a análise gerencial e as decisões NOVA_RECONTAGEM.

Mapeamento:
5 x HTTP 400 -> BusinessRuleViolation

Ao final:
- _selecionar_candidatos:
    7 BusinessRuleViolation
    0 HTTPException
- criacao.py:
    0 HTTPException
    0 import FastAPI/Starlette
- FastAPI removido completamente do módulo

Não altera:
- candidatos OFICIAL
- candidatos ROTATIVO
- decisões do gestor
- regra de finalização gerencial
- NOVA_RECONTAGEM
- SQL
- UoW
- commit/rollback
- sp_getapplock
- fluxo de sucesso
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

EXPECTED_HTTP_BEFORE = 5
EXPECTED_BRV_BEFORE_SELECTION = 2
EXPECTED_BRV_AFTER_SELECTION = 7

# Marcadores dos 5 erros gerenciais restantes.
# Alguns details são dinâmicos, então não usamos literal_eval como requisito.
GERENCIAL_MARKERS = (
    (
        "divergente(s) sem decisão do gestor",
    ),
    (
        "Todas as divergências foram",
        "apto",
        "finalização",
    ),
    (
        "Nenhum item foi marcado como",
        "NOVA_RECONTAGEM",
    ),
    (
        "A análise gerencial indica itens",
        "registro NOVA_RECONTAGEM",
        "localizado",
    ),
    (
        "Inconsistência entre a análise",
        "decisões de",
        "NOVA_RECONTAGEM",
    ),
)

CRITICAL_LOCK_TOKENS = (
    "sys.sp_getapplock",
    "SGI:ROTATIVO:PROXIMA_RODADA:",
    "@LockMode = 'Exclusive'",
    "@LockOwner = 'Transaction'",
    "@LockTimeout = 10000",
)

PROTECTED_EXACT_TOKENS = (
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
    *CRITICAL_LOCK_TOKENS,
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
        node.name: node
        for node in tree.body
        if isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef),
        )
    }


def get_function(text, name):
    fn = top_functions(text).get(name)

    if fn is None:
        raise RuntimeError(
            f"Função ausente: {name}"
        )

    return fn


def exception_raises(text, fn_name, exc_name):
    fn = get_function(text, fn_name)

    return [
        node
        for node in ast.walk(fn)
        if (
            isinstance(node, ast.Raise)
            and node.exc is not None
            and raised_name(node.exc) == exc_name
        )
    ]


def http_raises(text, fn_name):
    fn = get_function(text, fn_name)
    result = []

    for node in ast.walk(fn):
        if not isinstance(node, ast.Raise):
            continue

        if node.exc is None:
            continue

        if not (
            isinstance(node.exc, ast.Call)
            and raised_name(node.exc)
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

        if (
            status_node is None
            or detail_node is None
        ):
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

        detail_source = ast.get_source_segment(
            text,
            detail_node,
        )

        if not detail_source:
            raise RuntimeError(
                f"{fn_name}: detail não recuperado via AST."
            )

        result.append(
            {
                "node": node,
                "status": status_node.value,
                "detail_source": detail_source,
            }
        )

    return sorted(
        result,
        key=lambda item:
            item["node"].lineno,
    )


def count_http_total(text):
    tree = parse(
        text,
        str(SERVICE),
    )

    return sum(
        1
        for node in ast.walk(tree)
        if (
            isinstance(node, ast.Raise)
            and node.exc is not None
            and raised_name(node.exc)
            == "HTTPException"
        )
    )


def count_http_handlers(text):
    tree = parse(
        text,
        str(SERVICE),
    )

    return sum(
        1
        for node in ast.walk(tree)
        if (
            isinstance(node, ast.ExceptHandler)
            and handler_name(node)
            == "HTTPException"
        )
    )


def import_names(text, module_name):
    tree = parse(
        text,
        str(SERVICE),
    )

    result = []

    for node in tree.body:
        if (
            isinstance(node, ast.ImportFrom)
            and (node.module or "")
            == module_name
        ):
            result.append(
                (
                    node,
                    [
                        alias.name
                        for alias in node.names
                    ],
                )
            )

    return result


def has_import(text, module_name, symbol):
    return any(
        symbol in names
        for _, names
        in import_names(
            text,
            module_name,
        )
    )


def fastapi_starlette_imports(text):
    tree = parse(
        text,
        str(SERVICE),
    )

    result = []

    for node in tree.body:
        if not isinstance(
            node,
            (ast.Import, ast.ImportFrom),
        ):
            continue

        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if (
                module == "fastapi"
                or module.startswith("fastapi.")
                or module == "starlette"
                or module.startswith("starlette.")
            ):
                result.append(node)

        elif isinstance(node, ast.Import):
            for alias in node.names:
                if (
                    alias.name == "fastapi"
                    or alias.name.startswith("fastapi.")
                    or alias.name == "starlette"
                    or alias.name.startswith("starlette.")
                ):
                    result.append(node)
                    break

    return result


def protected_counts(text):
    return {
        token: text.count(token)
        for token
        in PROTECTED_EXACT_TOKENS
    }


def validate_lock_contract(text):
    counts = {
        token: text.count(token)
        for token
        in CRITICAL_LOCK_TOKENS
    }

    invalid = {
        token: count
        for token, count
        in counts.items()
        if count != 1
    }

    if invalid:
        raise RuntimeError(
            "Contrato sp_getapplock inesperado: "
            f"{invalid}"
        )

    source = (
        ast.get_source_segment(
            text,
            get_function(
                text,
                PREREQ_LOCK,
            ),
        )
        or ""
    )

    for token in CRITICAL_LOCK_TOKENS:
        if token not in source:
            raise RuntimeError(
                f"Token crítico fora de "
                f"{PREREQ_LOCK}: "
                f"{token}"
            )

    return counts


def validate_previous_phases(text):
    checks = {
        "config_brv":
            len(
                exception_raises(
                    text,
                    PREREQ_CONFIG,
                    "BusinessRuleViolation",
                )
            ),
        "config_http":
            len(
                http_raises(
                    text,
                    PREREQ_CONFIG,
                )
            ),

        "sessions_brv":
            len(
                exception_raises(
                    text,
                    PREREQ_SESSIONS,
                    "BusinessRuleViolation",
                )
            ),
        "sessions_http":
            len(
                http_raises(
                    text,
                    PREREQ_SESSIONS,
                )
            ),

        "lock_conflict":
            len(
                exception_raises(
                    text,
                    PREREQ_LOCK,
                    "ConflictError",
                )
            ),
        "lock_http":
            len(
                http_raises(
                    text,
                    PREREQ_LOCK,
                )
            ),

        "div_brv":
            len(
                exception_raises(
                    text,
                    PREREQ_DIVERGENCIA,
                    "BusinessRuleViolation",
                )
            ),
        "div_http":
            len(
                http_raises(
                    text,
                    PREREQ_DIVERGENCIA,
                )
            ),

        "loc_brv":
            len(
                exception_raises(
                    text,
                    PREREQ_LOCALIZACOES,
                    "BusinessRuleViolation",
                )
            ),
        "loc_http":
            len(
                http_raises(
                    text,
                    PREREQ_LOCALIZACOES,
                )
            ),
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
            "Pré-requisitos 10U-A..E "
            "não conferem: "
            f"{checks}"
        )

    return checks


def match_gerencial_groups(items):
    if len(items) != 5:
        raise RuntimeError(
            "Esperados exatamente 5 "
            f"HTTPException gerenciais; "
            f"encontrado {len(items)}."
        )

    if any(
        item["status"] != 400
        for item in items
    ):
        raise RuntimeError(
            "Todos os 5 erros gerenciais "
            "devem continuar HTTP 400."
        )

    assignments = []

    for group in GERENCIAL_MARKERS:
        matches = [
            item
            for item in items
            if all(
                marker
                in item["detail_source"]
                for marker in group
            )
        ]

        if len(matches) != 1:
            raise RuntimeError(
                "Não foi possível identificar "
                "unicamente um erro gerencial "
                f"pelos marcadores {group}. "
                f"Encontrados: {len(matches)}."
            )

        assignments.append(
            matches[0]
        )

    lines = {
        item["node"].lineno
        for item in assignments
    }

    if len(lines) != 5:
        raise RuntimeError(
            "Os cinco perfis gerenciais "
            "não apontam para cinco raises distintos."
        )

    return sorted(
        assignments,
        key=lambda item:
            item["node"].lineno,
    )


def service_state(text):
    validate_previous_phases(text)
    validate_lock_contract(text)

    total_http = count_http_total(text)
    http_handlers = count_http_handlers(text)

    selection_http = http_raises(
        text,
        TARGET_FUNCTION,
    )

    selection_brv = len(
        exception_raises(
            text,
            TARGET_FUNCTION,
            "BusinessRuleViolation",
        )
    )

    if not has_import(
        text,
        "domain.exceptions",
        "BusinessRuleViolation",
    ):
        raise RuntimeError(
            "BusinessRuleViolation não "
            "está importada no service."
        )

    if not has_import(
        text,
        "domain.exceptions",
        "ConflictError",
    ):
        raise RuntimeError(
            "ConflictError não está "
            "importada no service."
        )

    # Antes da 10U-H: 5 HTTP + 2 BRV.
    if (
        total_http
        == EXPECTED_HTTP_BEFORE
        and
        len(selection_http)
        == EXPECTED_HTTP_BEFORE
        and
        selection_brv
        == EXPECTED_BRV_BEFORE_SELECTION
        and
        http_handlers == 0
    ):
        match_gerencial_groups(
            selection_http
        )

        if not has_import(
            text,
            "fastapi",
            "HTTPException",
        ):
            raise RuntimeError(
                "HTTPException ainda deveria "
                "estar importada antes da 10U-H."
            )

        return "LEGADO_10U_H", {
            "http_total":
                total_http,
            "selection_http":
                len(selection_http),
            "selection_brv":
                selection_brv,
            "fastapi_imports":
                len(
                    fastapi_starlette_imports(
                        text
                    )
                ),
        }

    # Depois da 10U-H: 0 HTTP + 7 BRV + sem FastAPI.
    if (
        total_http == 0
        and
        len(selection_http) == 0
        and
        selection_brv
        == EXPECTED_BRV_AFTER_SELECTION
        and
        http_handlers == 0
        and
        len(
            fastapi_starlette_imports(
                text
            )
        ) == 0
    ):
        return "MIGRADO_10U_H", {
            "http_total":
                total_http,
            "selection_http": 0,
            "selection_brv":
                selection_brv,
            "fastapi_imports": 0,
        }

    return "DESCONHECIDO", {
        "http_total":
            total_http,
        "selection_http":
            len(selection_http),
        "selection_brv":
            selection_brv,
        "http_handlers":
            http_handlers,
        "fastapi_imports":
            len(
                fastapi_starlette_imports(
                    text
                )
            ),
        "details": [
            item["detail_source"]
            for item in selection_http
        ],
    }


def remove_http_exception_import(text):
    tree = parse(
        text,
        str(SERVICE),
    )

    target_nodes = []

    for node in tree.body:
        if not isinstance(
            node,
            ast.ImportFrom,
        ):
            continue

        if (
            node.module or ""
        ) != "fastapi":
            continue

        names = [
            alias.name
            for alias in node.names
        ]

        if "HTTPException" in names:
            target_nodes.append(
                node
            )

    if len(target_nodes) != 1:
        raise RuntimeError(
            "Esperado exatamente 1 "
            "import FastAPI contendo "
            "HTTPException."
        )

    node = target_nodes[0]

    remaining_aliases = [
        alias
        for alias in node.names
        if alias.name
        != "HTTPException"
    ]

    lines = text.splitlines()

    if remaining_aliases:
        rebuilt = (
            "from fastapi import "
            + ", ".join(
                (
                    alias.name
                    if alias.asname is None
                    else
                    f"{alias.name} as "
                    f"{alias.asname}"
                )
                for alias
                in remaining_aliases
            )
        )

        lines[
            node.lineno - 1:
            node.end_lineno
        ] = [
            rebuilt
        ]
    else:
        lines[
            node.lineno - 1:
            node.end_lineno
        ] = []

    result = "\n".join(
        lines
    )

    if text.endswith("\n"):
        result += "\n"

    return result


def patch_service(text):
    state, diag = service_state(
        text
    )

    if state != "LEGADO_10U_H":
        raise RuntimeError(
            "Baseline 10U-H não "
            f"reconhecido: "
            f"{state} / {diag}"
        )

    before_protected = (
        protected_counts(
            text
        )
    )

    before_lock = (
        validate_lock_contract(
            text
        )
    )

    items = http_raises(
        text,
        TARGET_FUNCTION,
    )

    targets = (
        match_gerencial_groups(
            items
        )
    )

    replacements = []

    for item in targets:
        node = item["node"]
        indent = (
            " "
            * node.col_offset
        )

        replacement = (
            f"{indent}raise "
            "BusinessRuleViolation(\n"
            f"{indent}    "
            f"{item['detail_source']}\n"
            f"{indent})"
        )

        replacements.append(
            (
                node.lineno,
                node.end_lineno,
                replacement,
            )
        )

    lines = text.splitlines()

    current = 1
    output = []

    for (
        start,
        end,
        replacement,
    ) in sorted(
        replacements,
        key=lambda item:
            item[0],
    ):
        output.extend(
            lines[
                current - 1:
                start - 1
            ]
        )

        output.extend(
            replacement.splitlines()
        )

        current = (
            end + 1
        )

    output.extend(
        lines[
            current - 1:
        ]
    )

    result = "\n".join(
        output
    )

    if text.endswith("\n"):
        result += "\n"

    if count_http_total(
        result
    ) != 0:
        raise RuntimeError(
            "Ainda existem HTTPException "
            "após converter os cinco "
            "erros gerenciais."
        )

    result = (
        remove_http_exception_import(
            result
        )
    )

    after_protected = (
        protected_counts(
            result
        )
    )

    if (
        before_protected
        != after_protected
    ):
        differences = {
            token: (
                before_protected[
                    token
                ],
                after_protected[
                    token
                ],
            )
            for token
            in PROTECTED_EXACT_TOKENS
            if (
                before_protected[
                    token
                ]
                !=
                after_protected[
                    token
                ]
            )
        }

        raise RuntimeError(
            "SQL/UoW/commit/applock "
            f"alterado: "
            f"{differences}"
        )

    if (
        validate_lock_contract(
            result
        )
        != before_lock
    ):
        raise RuntimeError(
            "Contrato sp_getapplock "
            "mudou durante 10U-H."
        )

    final_state, final_diag = (
        service_state(
            result
        )
    )

    if (
        final_state
        != "MIGRADO_10U_H"
    ):
        raise RuntimeError(
            "Estado pós-patch "
            f"inválido: "
            f"{final_diag}"
        )

    return result


print(
    "[0/11] Validando arquivos e hierarquia..."
)

for path in (
    SERVICE,
    DOMAIN,
):
    if not path.exists():
        raise SystemExit(
            f"[ERRO] Arquivo "
            f"ausente: "
            f"{path}"
        )

domain_text = read_text(
    DOMAIN
)

for token in (
    "class BusinessRuleViolation(DomainError)",
    "class ConflictError(DomainError)",
):
    if token not in domain_text:
        raise SystemExit(
            "[ERRO] Hierarquia "
            f"incompleta: "
            f"{token}"
        )

print(
    "      [OK] hierarquia "
    "de domínio reconhecida."
)


print(
    "[1/11] Validando baseline 10U-H..."
)

service_text = read_text(
    SERVICE
)

try:
    current_state, diag = (
        service_state(
            service_text
        )
    )
except Exception as exc:
    raise SystemExit(
        "[ERRO] Baseline "
        f"não reconhecido: "
        f"{exc}"
    )

print(
    f"      Estado: "
    f"{current_state}"
)

print(
    f"      diagnóstico: "
    f"{diag}"
)

if (
    current_state
    == "MIGRADO_10U_H"
):
    print()
    print(
        "[OK] Fase 10U-H "
        "já aplicada."
    )
    raise SystemExit(0)

if (
    current_state
    != "LEGADO_10U_H"
):
    raise SystemExit(
        "[ERRO] Estado "
        f"inesperado: "
        f"{current_state}"
    )


print(
    "[2/11] Confirmando 5 erros gerenciais..."
)

items = http_raises(
    service_text,
    TARGET_FUNCTION,
)

targets = (
    match_gerencial_groups(
        items
    )
)

for index, item in enumerate(
    targets,
    start=1,
):
    print(
        f"      {index}. "
        f"HTTP {item['status']} "
        "-> BusinessRuleViolation"
    )

    print(
        f"         "
        f"{item['detail_source']}"
    )

print(
    "      [OK] cinco "
    "validações distintas "
    "confirmadas."
)


print(
    "[3/11] Revalidando "
    "pré-requisitos 10U-A..G..."
)

checks = (
    validate_previous_phases(
        service_text
    )
)

print(
    f"      [OK] "
    f"{checks}"
)

selection_brv = len(
    exception_raises(
        service_text,
        TARGET_FUNCTION,
        "BusinessRuleViolation",
    )
)

if (
    selection_brv
    != 2
):
    raise SystemExit(
        "[ERRO] 10U-F/10U-G "
        "não reconhecidas: "
        f"BusinessRuleViolation "
        f"em _selecionar_candidatos "
        f"= {selection_brv}"
    )

print(
    "      [OK] 10U-F e "
    "10U-G reconhecidas."
)


print(
    "[4/11] Revalidando "
    "sp_getapplock..."
)

lock_before = (
    validate_lock_contract(
        service_text
    )
)

for token, count in (
    lock_before.items()
):
    print(
        f"      [OK] "
        f"{token}: "
        f"{count}"
    )


print(
    "[5/11] Confirmando que "
    "não existem outros HTTPException..."
)

if (
    count_http_total(
        service_text
    )
    != 5
):
    raise SystemExit(
        "[ERRO] O arquivo deveria "
        "conter exatamente 5 "
        "HTTPException antes da 10U-H."
    )

if (
    len(
        http_raises(
            service_text,
            TARGET_FUNCTION,
        )
    )
    != 5
):
    raise SystemExit(
        "[ERRO] Os cinco "
        "HTTPException deveriam "
        "estar exclusivamente em "
        "_selecionar_candidatos."
    )

print(
    "      [OK] exatamente "
    "5 HTTPException no arquivo, "
    "todos no alvo."
)


print(
    "[6/11] Preparando backup..."
)

timestamp = (
    datetime.now()
    .strftime(
        "%Y%m%d_%H%M%S"
    )
)

backup = (
    SERVICE.parent
    / (
        SERVICE.stem
        + "_backup_fase10u_h_"
        + timestamp
        + ".py"
    )
)

shutil.copy2(
    SERVICE,
    backup,
)

print(
    f"      "
    f"{SERVICE.relative_to(ROOT)} "
    f"-> "
    f"{backup.name}"
)


try:
    print(
        "[7/11] Convertendo "
        "os 5 erros gerenciais..."
    )

    patched = (
        patch_service(
            service_text
        )
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
        "      [OK] "
        "5 HTTP 400 -> "
        "BusinessRuleViolation."
    )


    print(
        "[8/11] Confirmando "
        "remoção completa do HTTP..."
    )

    final_text = read_text(
        SERVICE
    )

    if (
        count_http_total(
            final_text
        )
        != 0
    ):
        raise RuntimeError(
            "HTTPException "
            "remanescente."
        )

    if (
        count_http_handlers(
            final_text
        )
        != 0
    ):
        raise RuntimeError(
            "except HTTPException "
            "remanescente."
        )

    print(
        "      [OK] "
        "0 raise HTTPException."
    )

    print(
        "      [OK] "
        "0 except HTTPException."
    )


    print(
        "[9/11] Confirmando "
        "remoção do FastAPI..."
    )

    fastapi_imports = (
        fastapi_starlette_imports(
            final_text
        )
    )

    if fastapi_imports:
        raise RuntimeError(
            "FastAPI/Starlette "
            "ainda importado em "
            "criacao.py."
        )

    print(
        "      [OK] "
        "0 import FastAPI/Starlette."
    )


    print(
        "[10/11] Revalidando "
        "estado arquitetural..."
    )

    final_state, final_diag = (
        service_state(
            final_text
        )
    )

    if (
        final_state
        != "MIGRADO_10U_H"
    ):
        raise RuntimeError(
            "Estado final "
            f"inválido: "
            f"{final_diag}"
        )

    print(
        "      [OK] "
        "_selecionar_candidatos "
        "= 7 BusinessRuleViolation."
    )

    print(
        "      [OK] "
        "criacao.py totalmente "
        "desacoplado de HTTP."
    )


    print(
        "[11/11] Revalidando "
        "SQL/UoW/concorrência..."
    )

    if (
        validate_lock_contract(
            final_text
        )
        != lock_before
    ):
        raise RuntimeError(
            "Contrato sp_getapplock "
            "foi alterado."
        )

    before_protected = (
        protected_counts(
            service_text
        )
    )

    after_protected = (
        protected_counts(
            final_text
        )
    )

    if (
        before_protected
        != after_protected
    ):
        differences = {
            token: (
                before_protected[
                    token
                ],
                after_protected[
                    token
                ],
            )
            for token
            in PROTECTED_EXACT_TOKENS
            if (
                before_protected[
                    token
                ]
                !=
                after_protected[
                    token
                ]
            )
        }

        raise RuntimeError(
            "Proteção estrutural "
            f"falhou: "
            f"{differences}"
        )

    print(
        "      [OK] "
        "sp_getapplock preservado."
    )

    print(
        "      [OK] "
        "SQL/UoW/commit/rollback "
        "inalterados."
    )


except Exception:
    print()
    print(
        "[ERRO] Falha durante "
        "Fase 10U-H."
    )

    print(
        "[INFO] Restaurando "
        "backup..."
    )

    shutil.copy2(
        backup,
        SERVICE,
    )

    print(
        f"      [OK] "
        f"restaurado: "
        f"{SERVICE.relative_to(ROOT)}"
    )

    raise


print()
print(
    "[OK] Fase 10U-H aplicada."
)

print(
    "[OK] 5 erros gerenciais "
    "-> BusinessRuleViolation / "
    "HTTP 400."
)

print(
    "[OK] _selecionar_candidatos "
    "sem HTTPException."
)

print(
    "[OK] services/rodadas/criacao.py "
    "sem HTTPException."
)

print(
    "[OK] FastAPI removido "
    "completamente de criacao.py."
)

print(
    "[OK] regras NOVA_RECONTAGEM "
    "e análise gerencial preservadas."
)

print(
    "[OK] fluxos OFICIAL e "
    "ROTATIVO preservados."
)

print(
    "[OK] sp_getapplock, SQL, UoW, "
    "commit e rollback inalterados."
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
