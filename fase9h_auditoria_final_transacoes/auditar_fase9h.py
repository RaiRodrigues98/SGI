"""
FASE 9H - AUDITORIA FINAL DE TRANSAÇÕES DO SGI

Esta etapa é SOMENTE LEITURA:
- não altera arquivos;
- não cria backup;
- não executa SQL;
- não conecta no banco;
- apenas analisa os arquivos Python do projeto.

Execute na raiz do SGI:

python .\fase9h_auditoria_final_transacoes\auditar_fase9h.py
"""

from pathlib import Path
import ast
import re
import sys

ROOT = Path.cwd()

EXCLUDED_DIR_NAMES = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
}

EXCLUDED_PREFIXES = (
    "fase1",
    "fase2",
    "fase3",
    "fase4",
    "fase5",
    "fase6",
    "fase7",
    "fase8",
    "fase9",
)

WRITE_SQL_RE = re.compile(
    r"\b("
    r"INSERT|UPDATE|DELETE|MERGE|TRUNCATE|"
    r"CREATE|ALTER|DROP|EXEC|EXECUTE"
    r")\b",
    re.IGNORECASE,
)

READ_SQL_RE = re.compile(
    r"\bSELECT\b",
    re.IGNORECASE,
)


def is_excluded(path: Path) -> bool:

    rel = path.relative_to(ROOT)

    for part in rel.parts:

        low = part.lower()

        if low in EXCLUDED_DIR_NAMES:
            return True

        if low.startswith("backup"):
            return True

        if "_backup_" in low:
            return True

        if low.startswith(EXCLUDED_PREFIXES):
            return True

    # Testes E2E não definem ownership de produção.
    if rel.parts and rel.parts[0].lower() in {
        "tests",
        "tests_e2e",
        "test",
    }:
        return True

    return False


def read_text(path: Path) -> str:

    try:
        return path.read_text(
            encoding="utf-8"
        )
    except UnicodeDecodeError:
        return path.read_text(
            encoding="latin-1"
        )


def python_files():

    files = []

    for path in ROOT.rglob("*.py"):

        if is_excluded(path):
            continue

        files.append(path)

    return sorted(files)


def function_segments(text: str):

    tree = ast.parse(text)
    lines = text.splitlines()

    result = []

    for node in ast.walk(tree):

        if not isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        ):
            continue

        segment = "\n".join(
            lines[
                node.lineno - 1:
                node.end_lineno
            ]
        )

        result.append(
            {
                "name": node.name,
                "lineno": node.lineno,
                "segment": segment,
            }
        )

    return result


def classify_function(segment: str):

    legacy_conn = segment.count(
        "get_connection()"
    )

    uow_ctor = segment.count(
        "SqlServerUnitOfWork()"
    )

    conn_commit = segment.count(
        "conn.commit()"
    )

    conn_rollback = segment.count(
        "conn.rollback()"
    )

    uow_commit = segment.count(
        "uow.commit()"
    )

    uow_rollback = segment.count(
        "uow.rollback()"
    )

    write_sql = len(
        WRITE_SQL_RE.findall(
            segment
        )
    )

    read_sql = len(
        READ_SQL_RE.findall(
            segment
        )
    )

    return {
        "legacy_conn": legacy_conn,
        "uow_ctor": uow_ctor,
        "conn_commit": conn_commit,
        "conn_rollback": conn_rollback,
        "uow_commit": uow_commit,
        "uow_rollback": uow_rollback,
        "write_sql": write_sql,
        "read_sql": read_sql,
    }


def rel(path: Path):

    return str(
        path.relative_to(ROOT)
    )


def is_router(path: Path):

    parts = [
        p.lower()
        for p in path.relative_to(ROOT).parts
    ]

    return (
        len(parts) >= 2
        and
        parts[0] == "routers"
    )


def is_service(path: Path):

    parts = [
        p.lower()
        for p in path.relative_to(ROOT).parts
    ]

    return (
        len(parts) >= 2
        and
        parts[0] == "services"
    )


def is_infrastructure(path: Path):

    parts = [
        p.lower()
        for p in path.relative_to(ROOT).parts
    ]

    return (
        "infrastructure" in parts
        or
        (
            len(parts) >= 1
            and
            parts[0] in {
                "database",
                "db",
            }
        )
    )


def line_count_token(text, token):

    lines = []

    for i, line in enumerate(
        text.splitlines(),
        start=1,
    ):

        if token in line:

            lines.append(i)

    return lines


print()
print("=" * 78)
print("FASE 9H - AUDITORIA FINAL DA CAMADA TRANSACIONAL")
print("=" * 78)
print()

files = python_files()

if not files:

    raise SystemExit(
        "[ERRO] Nenhum arquivo Python de produção encontrado."
    )

print(
    f"Arquivos Python analisados: {len(files)}"
)
print()

# ============================================================
# INVENTÁRIO GLOBAL
# ============================================================

legacy_files = []
uow_files = []
commit_files = []
rollback_files = []

syntax_errors = []

for path in files:

    text = read_text(path)

    try:
        ast.parse(text)
    except SyntaxError as exc:
        syntax_errors.append(
            (path, exc)
        )
        continue

    if "get_connection()" in text:
        legacy_files.append(path)

    if "SqlServerUnitOfWork" in text:
        uow_files.append(path)

    if (
        "conn.commit()" in text
        or
        "uow.commit()" in text
    ):
        commit_files.append(path)

    if (
        "conn.rollback()" in text
        or
        "uow.rollback()" in text
    ):
        rollback_files.append(path)


if syntax_errors:

    print(
        "[ERRO] Existem arquivos de produção "
        "com erro de sintaxe:"
    )

    for path, exc in syntax_errors:

        print(
            f"  - {rel(path)}: {exc}"
        )

    raise SystemExit(2)


print("[1/7] Uso global de conexão")
print(
    f"      arquivos com get_connection(): "
    f"{len(legacy_files)}"
)
print(
    f"      arquivos com SqlServerUnitOfWork: "
    f"{len(uow_files)}"
)
print()


# ============================================================
# ROUTERS
# ============================================================

print("[2/7] Auditando routers...")

router_blockers = []
router_reads_legacy = []
router_uow = []
router_service_owned = []
router_unknown = []

for path in files:

    if not is_router(path):
        continue

    text = read_text(path)
    funcs = function_segments(text)

    for fn in funcs:

        info = classify_function(
            fn["segment"]
        )

        has_legacy = (
            info["legacy_conn"] > 0
        )

        has_uow = (
            info["uow_ctor"] > 0
        )

        router_commit = (
            info["conn_commit"]
            + info["uow_commit"]
        )

        router_rollback = (
            info["conn_rollback"]
            + info["uow_rollback"]
        )

        write_sql = (
            info["write_sql"] > 0
        )

        item = {
            "path": path,
            "function": fn["name"],
            "line": fn["lineno"],
            **info,
        }

        if has_legacy:

            # Legacy + commit/rollback ou SQL de escrita =
            # ownership transacional ainda não padronizado.
            if (
                router_commit > 0
                or
                router_rollback > 0
                or
                write_sql
            ):

                router_blockers.append(
                    item
                )

            else:

                # Conexão direta sem escrita/commit:
                # leitura simples tolerada nesta fase.
                router_reads_legacy.append(
                    item
                )

        elif has_uow:

            if (
                router_commit == 0
                and
                router_rollback == 0
            ):

                # Pode ser leitura UoW ou router que delega
                # ownership ao service.
                router_service_owned.append(
                    item
                )

            else:

                router_uow.append(
                    item
                )

        else:

            # Função sem ownership de conexão não interessa
            # para o fechamento da Fase 9.
            pass


print(
    f"      blockers transacionais legados: "
    f"{len(router_blockers)}"
)

print(
    f"      leituras ainda com get_connection(): "
    f"{len(router_reads_legacy)}"
)

print(
    f"      funções com UoW + commit/rollback no router: "
    f"{len(router_uow)}"
)

print(
    f"      funções UoW sem commit/rollback no router: "
    f"{len(router_service_owned)}"
)
print()


# ============================================================
# SERVICES
# ============================================================

print("[3/7] Auditando ownership transacional em services...")

service_transaction_owners = []

for path in files:

    if not is_service(path):
        continue

    text = read_text(path)

    for fn in function_segments(text):

        info = classify_function(
            fn["segment"]
        )

        commits = (
            info["conn_commit"]
            + info["uow_commit"]
        )

        rollbacks = (
            info["conn_rollback"]
            + info["uow_rollback"]
        )

        if (
            commits > 0
            or
            rollbacks > 0
        ):

            service_transaction_owners.append(
                {
                    "path": path,
                    "function": fn["name"],
                    "line": fn["lineno"],
                    "commits": commits,
                    "rollbacks": rollbacks,
                    "legacy_conn":
                        info["legacy_conn"],
                    "uow_ctor":
                        info["uow_ctor"],
                }
            )


print(
    f"      services com commit/rollback explícito: "
    f"{len(service_transaction_owners)}"
)
print()


# ============================================================
# COMMIT/ROLLBACK FORA DE ROUTER/SERVICE/INFRA
# ============================================================

print(
    "[4/7] Procurando commit/rollback em camadas inesperadas..."
)

unexpected_transaction_owners = []

for path in files:

    if (
        is_router(path)
        or
        is_service(path)
        or
        is_infrastructure(path)
    ):
        continue

    text = read_text(path)

    if (
        "conn.commit()" in text
        or
        "conn.rollback()" in text
        or
        "uow.commit()" in text
        or
        "uow.rollback()" in text
    ):

        unexpected_transaction_owners.append(
            path
        )


print(
    f"      arquivos inesperados: "
    f"{len(unexpected_transaction_owners)}"
)
print()


# ============================================================
# MAIN.PY / TESTE BANCO
# ============================================================

print("[5/7] Verificando main.py...")

main_path = ROOT / "main.py"

main_legacy_read = False
main_write_risk = False

if main_path.exists():

    main_text = read_text(
        main_path
    )

    if "get_connection()" in main_text:

        main_legacy_read = True

        if WRITE_SQL_RE.search(
            main_text
        ):

            main_write_risk = True

        print(
            "      main.py ainda usa get_connection()."
        )

        if main_write_risk:

            print(
                "      [ATENÇÃO] Foram encontrados "
                "tokens SQL de escrita em main.py."
            )

        else:

            print(
                "      [OK] uso aparenta ser somente leitura/"
                "diagnóstico; não bloqueia Fase 9."
            )

    else:

        print(
            "      [OK] main.py sem get_connection()."
        )

else:

    print(
        "      main.py não encontrado."
    )

print()


# ============================================================
# RELATÓRIO DETALHADO
# ============================================================

print("[6/7] Relatório detalhado")
print()

if router_blockers:

    print(
        "BLOQUEADORES - ROUTERS LEGADOS COM ESCRITA/TRANSAÇÃO"
    )

    for item in router_blockers:

        print(
            "  - "
            f"{rel(item['path'])}:"
            f"{item['line']} "
            f"{item['function']} | "
            f"legacy_conn={item['legacy_conn']} | "
            f"commit="
            f"{item['conn_commit'] + item['uow_commit']} | "
            f"rollback="
            f"{item['conn_rollback'] + item['uow_rollback']} | "
            f"write_sql={item['write_sql']}"
        )

    print()


if router_reads_legacy:

    print(
        "LEITURAS LEGADAS PERMITIDAS NESTA FASE"
    )

    for item in router_reads_legacy:

        print(
            "  - "
            f"{rel(item['path'])}:"
            f"{item['line']} "
            f"{item['function']}"
        )

    print()


if service_transaction_owners:

    print(
        "OWNERSHIP TRANSACIONAL INTENCIONAL EM SERVICES"
    )

    for item in service_transaction_owners:

        print(
            "  - "
            f"{rel(item['path'])}:"
            f"{item['line']} "
            f"{item['function']} | "
            f"commit={item['commits']} | "
            f"rollback={item['rollbacks']}"
        )

    print()


if unexpected_transaction_owners:

    print(
        "TRANSAÇÕES FORA DAS CAMADAS ESPERADAS"
    )

    for path in unexpected_transaction_owners:

        print(
            f"  - {rel(path)}"
        )

    print()


# ============================================================
# CRITÉRIO FINAL
# ============================================================

print("[7/7] Resultado")
print()

blocking = False

if router_blockers:
    blocking = True

if unexpected_transaction_owners:
    blocking = True

if main_write_risk:
    blocking = True


if blocking:

    print(
        "RESULTADO FASE 9H: PENDÊNCIAS ENCONTRADAS"
    )

    print()
    print(
        "A Fase 9 ainda NÃO deve ser declarada concluída."
    )

    print(
        "Corrija apenas os bloqueadores listados acima "
        "e execute esta auditoria novamente."
    )

    sys.exit(1)


print(
    "RESULTADO FASE 9H: APROVADO"
)

print()
print(
    "Critérios atendidos:"
)

print(
    "  [OK] nenhum router legado restante controla "
    "transação de escrita;"
)

print(
    "  [OK] get_connection remanescente em router "
    "é somente leitura;"
)

print(
    "  [OK] ownership transacional em services foi "
    "explicitamente identificado;"
)

print(
    "  [OK] nenhuma transação inesperada fora das "
    "camadas previstas;"
)

if main_legacy_read:

    print(
        "  [OK] main.py possui conexão direta apenas "
        "para diagnóstico/leitura."
    )

print()
print(
    "FASE 9 - UNIT OF WORK / TRANSAÇÕES:"
)

print(
    "APTA PARA ENCERRAMENTO, condicionada à regressão "
    "final do SGI permanecer verde."
)

print()
print(
    "PRÓXIMO PASSO:"
)

print(
    r"python tests_e2e\regressao_final_sgi.py"
)
