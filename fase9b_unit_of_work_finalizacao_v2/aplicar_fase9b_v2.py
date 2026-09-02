"""
Fase 9B v2 - Unit of Work no router de finalização.

Correção:
- reconhece router LEGADO com get_connection();
- reconhece router JÁ MIGRADO para SqlServerUnitOfWork;
- é idempotente: se já estiver correto, valida e encerra com sucesso;
- só altera o arquivo quando realmente encontra a baseline legada.

Execute na raiz do SGI:

python .\fase9b_unit_of_work_finalizacao_v2\aplicar_fase9b_v2.py
"""

from pathlib import Path
from datetime import datetime
import ast
import py_compile
import shutil

ROOT = Path.cwd()

target_router = ROOT / "routers" / "finalizacao.py"
target_rodadas_router = ROOT / "routers" / "rodadas.py"
target_uow = (
    ROOT
    / "infrastructure"
    / "database"
    / "unit_of_work.py"
)


def contar(text, token):
    return text.count(token)


def validar_invariantes_router(text):

    obrigatorios = [
        '"/inventarios/{id_inventario}/finalizar"',
        '"INVENTARIO_FINALIZAR"',
        "finalizar_inventario_oficial(",
        "finalizar_inventario_rotativo(",
        "sys.sp_getapplock",
        "@LockOwner = 'Transaction'",
        "SGI:INVENTARIO:",
        ":FINALIZAR",
    ]

    ausentes = [
        token
        for token in obrigatorios
        if token not in text
    ]

    if ausentes:
        raise RuntimeError(
            "Invariantes críticas ausentes no router: "
            f"{ausentes}"
        )


def diagnostico(text):

    return {
        "get_connection":
            contar(text, "get_connection()"),

        "conn_commit":
            contar(text, "conn.commit()"),

        "conn_rollback":
            contar(text, "conn.rollback()"),

        "conn_close":
            contar(text, "conn.close()"),

        "cursor_close":
            contar(text, "cursor.close()"),

        "uow_ctor":
            contar(text, "SqlServerUnitOfWork()"),

        "uow_open":
            contar(text, "uow.open()"),

        "uow_commit":
            contar(text, "uow.commit()"),

        "uow_rollback":
            contar(text, "uow.rollback()"),

        "uow_close":
            contar(text, "uow.close()"),

        "uow_cursor":
            contar(text, "cursor = uow.cursor"),

        "with_uow":
            contar(
                text,
                "with SqlServerUnitOfWork() as uow"
            ),
    }


def estado_router(text):

    d = diagnostico(text)

    legado = (
        d["get_connection"] == 1
        and
        d["conn_commit"] == 1
        and
        d["conn_rollback"] in (2, 3)
        and
        d["conn_close"] == 1
        and
        d["cursor_close"] == 1
    )

    uow_explicito = (
        "SqlServerUnitOfWork" in text
        and
        d["uow_ctor"] == 1
        and
        d["uow_open"] == 1
        and
        d["uow_commit"] == 1
        and
        d["uow_rollback"] in (2, 3)
        and
        d["uow_close"] == 1
        and
        d["uow_cursor"] == 1
        and
        d["get_connection"] == 0
        and
        d["conn_commit"] == 0
        and
        d["conn_rollback"] == 0
        and
        d["conn_close"] == 0
        and
        d["cursor_close"] == 0
    )

    uow_contexto = (
        "SqlServerUnitOfWork" in text
        and
        d["with_uow"] == 1
        and
        d["uow_commit"] == 1
        and
        d["uow_rollback"] in (2, 3)
        and
        d["get_connection"] == 0
        and
        d["conn_commit"] == 0
        and
        d["conn_rollback"] == 0
    )

    if legado:
        return "LEGADO", d

    if uow_explicito:
        return "UOW_EXPLICITO", d

    if uow_contexto:
        return "UOW_CONTEXTO", d

    return "DESCONHECIDO", d


def patch_legado(text):

    before_rollbacks = contar(
        text,
        "conn.rollback()"
    )

    patched = text.replace(
        "from database import get_connection",
        (
            "from infrastructure.database.unit_of_work "
            "import SqlServerUnitOfWork"
        ),
        1,
    )

    patched = patched.replace(
        "    conn = None\n    cursor = None",
        "    uow = None\n    cursor = None",
        1,
    )

    patched = patched.replace(
        "        conn = get_connection()\n"
        "        cursor = conn.cursor()",
        (
            "        uow = SqlServerUnitOfWork()\n"
            "        uow.open()\n"
            "        cursor = uow.cursor"
        ),
        1,
    )

    # Mantém exatamente as posições transacionais.
    patched = patched.replace(
        "conn.commit()",
        "uow.commit()",
    )

    patched = patched.replace(
        "conn.rollback()",
        "uow.rollback()",
    )

    patched = patched.replace(
        "if conn:",
        "if uow:",
    )

    old_finally = (
        "        if cursor:\n"
        "            cursor.close()\n\n"
        "        if uow:\n"
        "            conn.close()"
    )

    if patched.count(old_finally) != 1:
        raise RuntimeError(
            "Não foi possível localizar de forma segura "
            "o bloco finally legado."
        )

    patched = patched.replace(
        old_finally,
        (
            "        if uow:\n"
            "            uow.close()"
        ),
        1,
    )

    # Validação pós-patch.
    estado, d = estado_router(
        patched
    )

    if estado != "UOW_EXPLICITO":
        raise RuntimeError(
            "O patch foi gerado, mas a estrutura final "
            f"não passou na validação. Diagnóstico: {d}"
        )

    if d["uow_rollback"] != before_rollbacks:
        raise RuntimeError(
            "Quantidade de rollbacks foi alterada."
        )

    validar_invariantes_router(
        patched
    )

    return patched


print(
    "[0/8] Validando arquivos necessários..."
)

for file in [
    target_router,
    target_rodadas_router,
    target_uow,
]:

    if not file.exists():
        raise SystemExit(
            f"[ERRO] Arquivo necessário ausente: {file}"
        )

# ------------------------------------------------------------
# Unit of Work da 9A
# ------------------------------------------------------------

print(
    "[1/8] Validando SqlServerUnitOfWork..."
)

uow_text = target_uow.read_text(
    encoding="utf-8"
)

for token in [
    "class SqlServerUnitOfWork",
    "def open(",
    "def commit(",
    "def rollback(",
    "def close(",
]:

    if token not in uow_text:
        raise SystemExit(
            "[ERRO] Unit of Work não reconhecido. "
            f"Ausente: {token}"
        )

if "self.commit()" in uow_text:
    raise SystemExit(
        "[ERRO] UnitOfWork possui auto-commit, "
        "o que não é permitido nesta fase."
    )

print(
    "      [OK] Unit of Work reconhecido."
)

# ------------------------------------------------------------
# Fase 9A
# ------------------------------------------------------------

print(
    "[2/8] Validando Fase 9A em routers/rodadas.py..."
)

rodadas_text = target_rodadas_router.read_text(
    encoding="utf-8"
)

for token in [
    "SqlServerUnitOfWork",
    "uow.open()",
    "uow.commit()",
]:

    if token not in rodadas_text:
        raise SystemExit(
            "[ERRO] Fase 9A não identificada. "
            f"Ausente em routers/rodadas.py: {token}"
        )

print(
    "      [OK] Fase 9A preservada."
)

# ------------------------------------------------------------
# Detecta estado atual
# ------------------------------------------------------------

print(
    "[3/8] Detectando estado atual de routers/finalizacao.py..."
)

current = target_router.read_text(
    encoding="utf-8"
)

try:
    ast.parse(current)
except SyntaxError as exc:
    raise SystemExit(
        "[ERRO] routers/finalizacao.py possui erro de sintaxe "
        f"antes da Fase 9B: {exc}"
    )

try:
    validar_invariantes_router(
        current
    )
except RuntimeError as exc:
    raise SystemExit(
        f"[ERRO] {exc}"
    )

estado, diag = estado_router(
    current
)

print(
    f"      Estado detectado: {estado}"
)

print(
    "      Diagnóstico:"
)

for chave, valor in diag.items():
    print(
        f"        {chave}: {valor}"
    )

# ------------------------------------------------------------
# Já migrado
# ------------------------------------------------------------

if estado in (
    "UOW_EXPLICITO",
    "UOW_CONTEXTO",
):

    print()
    print(
        "[OK] routers/finalizacao.py já utiliza "
        "SqlServerUnitOfWork."
    )

    print(
        "[OK] Nenhuma alteração foi necessária."
    )

    print(
        "[OK] Lock transacional preservado."
    )

    print(
        "[OK] INVENTARIO_FINALIZAR preservado."
    )

    print(
        "[OK] Dispatch OFICIAL/ROTATIVO preservado."
    )

    print(
        "[OK] Fase 9B considerada aplicada."
    )

    print()
    print(
        "PRÓXIMO PASSO:"
    )

    print(
        "1. Reinicie a API, se ainda não reiniciou."
    )

    print(
        r"2. python tests_e2e\regressao_final_sgi.py"
    )

    raise SystemExit(0)

# ------------------------------------------------------------
# Estado desconhecido
# ------------------------------------------------------------

if estado == "DESCONHECIDO":

    print()
    print(
        "[ERRO] O router não está no formato legado "
        "nem em um formato UoW reconhecido."
    )

    print(
        "[INFO] Nenhum arquivo foi alterado."
    )

    print()
    print(
        "DIAGNÓSTICO PARA ANÁLISE:"
    )

    for chave, valor in diag.items():
        print(
            f"  {chave}: {valor}"
        )

    print()
    print(
        "Envie esta saída junto com o conteúdo atual "
        "de routers/finalizacao.py se for necessário "
        "um patch específico."
    )

    raise SystemExit(1)

# ------------------------------------------------------------
# Migração LEGADO -> UOW
# ------------------------------------------------------------

print(
    "[4/8] Baseline legada reconhecida."
)

timestamp = datetime.now().strftime(
    "%Y%m%d_%H%M%S"
)

backup_router = (
    ROOT
    / "routers"
    / f"finalizacao_backup_fase9b_{timestamp}.py"
)

print(
    "[5/8] Criando backup..."
)

shutil.copy2(
    target_router,
    backup_router,
)

print(
    f"      {backup_router}"
)

try:

    print(
        "[6/8] Aplicando SqlServerUnitOfWork..."
    )

    patched = patch_legado(
        current
    )

    target_router.write_text(
        patched,
        encoding="utf-8",
    )

    print(
        "[7/8] Validando sintaxe e invariantes..."
    )

    py_compile.compile(
        str(target_router),
        doraise=True,
    )

    final_text = target_router.read_text(
        encoding="utf-8"
    )

    final_estado, final_diag = estado_router(
        final_text
    )

    if final_estado != "UOW_EXPLICITO":
        raise RuntimeError(
            "Estado final inesperado: "
            f"{final_estado} / {final_diag}"
        )

    validar_invariantes_router(
        final_text
    )

    print(
        "      [OK] UoW explícito reconhecido."
    )

    print(
        "[8/8] Validando quantidade de rollbacks..."
    )

    if (
        final_diag["uow_rollback"]
        != diag["conn_rollback"]
    ):
        raise RuntimeError(
            "Quantidade de rollbacks mudou: "
            f"antes={diag['conn_rollback']} "
            f"depois={final_diag['uow_rollback']}"
        )

    print(
        "      [OK] "
        f"{final_diag['uow_rollback']} rollbacks preservados."
    )

except Exception:

    print()
    print(
        "[ERRO] Falha durante aplicação."
    )

    print(
        "[INFO] Restaurando backup..."
    )

    shutil.copy2(
        backup_router,
        target_router,
    )

    print(
        "[OK] Estado anterior restaurado."
    )

    raise


print()
print(
    "[OK] Fase 9B aplicada."
)

print(
    "[OK] Finalização agora usa SqlServerUnitOfWork."
)

print(
    "[OK] Commit/rollback continuam no mesmo ponto lógico."
)

print(
    "[OK] sp_getapplock permanece LockOwner='Transaction'."
)

print()
print(
    "BACKUP:"
)

print(
    f"  {backup_router}"
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
