"""
FASE 9I - UNIT OF WORK EM routers/analise.py

Objetivo:
- migrar 3 conexões legadas para SqlServerUnitOfWork;
- preservar 0 commits;
- preservar exatamente os 2 rollbacks de analisar_rodada;
- não alterar regras de análise ROTATIVO/OFICIAL;
- não alterar services.

Execute na raiz do SGI:

python .\fase9i_unit_of_work_analise\aplicar_fase9i.py
"""

from pathlib import Path
from datetime import datetime
import ast
import py_compile
import re
import shutil

ROOT = Path.cwd()

TARGET = ROOT / "routers" / "analise.py"
UOW_FILE = (
    ROOT
    / "infrastructure"
    / "database"
    / "unit_of_work.py"
)

TARGET_FUNCTIONS = {
    "analisar_sessao": (1, 0, 0),
    "analisar_rodada": (1, 0, 2),
    "consultar_analise_rotativo": (1, 0, 0),
}

INVARIANTS = [
    "def analisar_sessao(",
    "def analisar_rodada(",
    "def consultar_analise_rotativo(",
    "ANALISE_VISUALIZAR",
    "analisar_sessao_oficial(",
    "analisar_rodada_oficial(",
    "analisar_inventario_rotativo(",
    "validar_snapshot(",
]


def function_map(text):

    tree = ast.parse(text)
    lines = text.splitlines()
    out = {}

    for node in tree.body:

        if not isinstance(
            node,
            ast.FunctionDef,
        ):
            continue

        segment = "\n".join(
            lines[
                node.lineno - 1:
                node.end_lineno
            ]
        )

        out[node.name] = {
            "legacy_conn":
                segment.count("get_connection()"),

            "legacy_commit":
                segment.count("conn.commit()"),

            "legacy_rollback":
                segment.count("conn.rollback()"),

            "uow_ctor":
                segment.count("SqlServerUnitOfWork()"),

            "uow_commit":
                segment.count("uow.commit()"),

            "uow_rollback":
                segment.count("uow.rollback()"),
        }

    return out


def diagnostico(text):

    return {
        "legacy_conn": text.count("get_connection()"),
        "legacy_commit": text.count("conn.commit()"),
        "legacy_rollback": text.count("conn.rollback()"),
        "legacy_cursor_close": text.count("cursor.close()"),
        "legacy_conn_close": text.count("conn.close()"),
        "uow_ctor": text.count("SqlServerUnitOfWork()"),
        "uow_open": text.count("uow.open()"),
        "uow_commit": text.count("uow.commit()"),
        "uow_rollback": text.count("uow.rollback()"),
        "uow_close": text.count("uow.close()"),
        "uow_conn_alias": text.count("conn = uow.connection"),
        "uow_cursor": text.count("cursor = uow.cursor"),
    }


def detectar_estado(text):

    d = diagnostico(text)

    legado = (
        "from database import get_connection" in text
        and d["legacy_conn"] == 3
        and d["legacy_commit"] == 0
        and d["legacy_rollback"] == 2
        and d["legacy_cursor_close"] == 3
        and d["legacy_conn_close"] == 3
    )

    uow = (
        "SqlServerUnitOfWork" in text
        and d["legacy_conn"] == 0
        and d["legacy_commit"] == 0
        and d["legacy_rollback"] == 0
        and d["legacy_cursor_close"] == 0
        and d["legacy_conn_close"] == 0
        and d["uow_ctor"] == 3
        and d["uow_open"] == 3
        and d["uow_commit"] == 0
        and d["uow_rollback"] == 2
        and d["uow_close"] == 3
        and d["uow_conn_alias"] == 3
        and d["uow_cursor"] == 3
    )

    if legado:
        return "LEGADO", d

    if uow:
        return "UOW", d

    return "DESCONHECIDO", d


def validar_funcoes(
    text,
    modo
):

    fmap = function_map(text)

    for name, expected in (
        TARGET_FUNCTIONS.items()
    ):

        if name not in fmap:

            raise RuntimeError(
                f"Função ausente: {name}"
            )

        info = fmap[name]

        if modo == "LEGADO":

            atual = (
                info["legacy_conn"],
                info["legacy_commit"],
                info["legacy_rollback"],
            )

        else:

            atual = (
                info["uow_ctor"],
                info["uow_commit"],
                info["uow_rollback"],
            )

        if atual != expected:

            raise RuntimeError(
                f"{name}: "
                f"esperado={expected}, "
                f"encontrado={atual}"
            )


def is_close_call(
    node,
    obj_name
):

    return (
        isinstance(node, ast.Call)
        and
        isinstance(
            node.func,
            ast.Attribute
        )
        and
        node.func.attr == "close"
        and
        isinstance(
            node.func.value,
            ast.Name
        )
        and
        node.func.value.id == obj_name
    )


def stmt_has_close(
    stmt,
    obj_name
):

    return any(
        is_close_call(
            node,
            obj_name
        )
        for node in ast.walk(stmt)
    )


def reescrever_cleanup(text):

    tree = ast.parse(text)

    cursor_stmts = []
    conn_stmts = []

    for node in ast.walk(tree):

        if not isinstance(
            node,
            ast.Try
        ):
            continue

        for stmt in node.finalbody:

            if stmt_has_close(
                stmt,
                "cursor"
            ):

                cursor_stmts.append(
                    stmt
                )

            if stmt_has_close(
                stmt,
                "conn"
            ):

                conn_stmts.append(
                    stmt
                )

    if (
        len(cursor_stmts) != 3
        or
        len(conn_stmts) != 3
    ):

        raise RuntimeError(
            "Cleanup inesperado: "
            f"cursor={len(cursor_stmts)}, "
            f"conn={len(conn_stmts)}"
        )

    lines = text.splitlines()

    replacements = []

    for stmt in cursor_stmts:

        replacements.append(
            (
                stmt.lineno,
                stmt.end_lineno,
                "",
            )
        )

    for stmt in conn_stmts:

        line = lines[
            stmt.lineno - 1
        ]

        indent = (
            line[
                :
                len(line)
                -
                len(
                    line.lstrip()
                )
            ]
        )

        replacements.append(
            (
                stmt.lineno,
                stmt.end_lineno,
                (
                    f"{indent}if uow:\n"
                    f"{indent}    uow.close()"
                ),
            )
        )

    replacements.sort(
        key=lambda x: (
            x[0],
            x[1],
        )
    )

    last_end = 0

    for start, end, _ in replacements:

        if start <= last_end:

            raise RuntimeError(
                "Cleanup sobreposto."
            )

        last_end = end

    out = []

    current = 1

    for (
        start,
        end,
        replacement
    ) in replacements:

        out.extend(
            lines[
                current - 1:
                start - 1
            ]
        )

        if replacement:

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

    return result


def patch_legado(text):

    state, before = (
        detectar_estado(text)
    )

    if state != "LEGADO":

        raise RuntimeError(
            "Patch solicitado para estado "
            f"{state}: {before}"
        )

    ast.parse(text)

    validar_funcoes(
        text,
        "LEGADO",
    )

    for token in INVARIANTS:

        if token not in text:

            raise RuntimeError(
                f"Invariante ausente: {token}"
            )

    patched = text.replace(
        "from database import get_connection",
        (
            "from infrastructure.database."
            "unit_of_work import "
            "SqlServerUnitOfWork"
        ),
        1,
    )

    init_pattern = re.compile(
        r"(?m)^"
        r"(?P<i>[ \t]*)"
        r"conn = None"
        r"[ \t]*\r?\n"
        r"(?P=i)"
        r"cursor = None"
        r"[ \t]*$"
    )

    def repl_init(match):

        i = match.group("i")

        return (
            f"{i}uow = None\n"
            f"{i}conn = None\n"
            f"{i}cursor = None"
        )

    patched, init_count = (
        init_pattern.subn(
            repl_init,
            patched,
        )
    )

    if init_count != 3:

        raise RuntimeError(
            "Esperados 3 blocos "
            "de inicialização, "
            f"encontrado={init_count}"
        )

    open_pattern = re.compile(
        r"(?m)^"
        r"(?P<i>[ \t]*)"
        r"conn = get_connection\(\)"
        r"[ \t]*\r?\n"
        r"(?P=i)"
        r"cursor = conn\.cursor\(\)"
        r"[ \t]*$"
    )

    def repl_open(match):

        i = match.group("i")

        return (
            f"{i}uow = "
            "SqlServerUnitOfWork()\n"
            f"{i}uow.open()\n"
            f"{i}conn = "
            "uow.connection\n"
            f"{i}cursor = "
            "uow.cursor"
        )

    patched, open_count = (
        open_pattern.subn(
            repl_open,
            patched,
        )
    )

    if open_count != 3:

        raise RuntimeError(
            "Esperadas 3 aberturas, "
            f"encontrado={open_count}"
        )

    # Preserva exatamente os 2 rollbacks
    # já existentes em analisar_rodada.
    patched = patched.replace(
        "conn.rollback()",
        "uow.rollback()",
    )

    patched = reescrever_cleanup(
        patched
    )

    state2, after = (
        detectar_estado(
            patched
        )
    )

    if state2 != "UOW":

        raise RuntimeError(
            "Estado pós-patch inválido: "
            f"{state2} / {after}"
        )

    validar_funcoes(
        patched,
        "UOW",
    )

    for token in INVARIANTS:

        if token not in patched:

            raise RuntimeError(
                f"Invariante perdida: {token}"
            )

    if "uow.commit()" in patched:

        raise RuntimeError(
            "Commit foi introduzido em "
            "analise.py."
        )

    return patched


# ============================================================
# PRÉ-REQUISITOS
# ============================================================

print(
    "[0/9] Validando arquivos..."
)

for path in [
    TARGET,
    UOW_FILE,
]:

    if not path.exists():

        raise SystemExit(
            f"[ERRO] Arquivo ausente: {path}"
        )


print(
    "[1/9] Validando SqlServerUnitOfWork..."
)

uow_text = UOW_FILE.read_text(
    encoding="utf-8"
)

for token in [
    "class SqlServerUnitOfWork",
    "def open(",
    "def rollback(",
    "def close(",
]:

    if token not in uow_text:

        raise SystemExit(
            f"[ERRO] UoW inválido: {token}"
        )

print(
    "      [OK] UoW reconhecido."
)


print(
    "[2/9] Detectando estado de analise.py..."
)

current = TARGET.read_text(
    encoding="utf-8"
)

try:
    ast.parse(current)
except SyntaxError as exc:
    raise SystemExit(
        f"[ERRO] Sintaxe inválida: {exc}"
    )

state, before = (
    detectar_estado(
        current
    )
)

print(
    f"      Estado: {state}"
)

print(
    "      conexões: "
    f"{before['legacy_conn'] or before['uow_ctor']}"
)

print(
    "      commits: "
    f"{before['legacy_commit'] or before['uow_commit']}"
)

print(
    "      rollbacks: "
    f"{before['legacy_rollback'] or before['uow_rollback']}"
)


if state == "DESCONHECIDO":

    print()
    print(
        "[ERRO] Baseline de analise.py "
        "não reconhecida."
    )

    print(
        "[INFO] Nenhum arquivo foi alterado."
    )

    print(
        f"[INFO] Diagnóstico: {before}"
    )

    raise SystemExit(1)


try:

    validar_funcoes(
        current,
        (
            "LEGADO"
            if state == "LEGADO"
            else "UOW"
        ),
    )

except Exception as exc:

    raise SystemExit(
        f"[ERRO] Mapa de funções: {exc}"
    )


if state == "UOW":

    print(
        "[3/9] analise.py já usa UoW."
    )

    print(
        "      Nenhuma alteração necessária."
    )

    print()
    print(
        "[OK] Fase 9I considerada aplicada."
    )

    raise SystemExit(0)


# ============================================================
# BACKUP + PATCH
# ============================================================

timestamp = datetime.now().strftime(
    "%Y%m%d_%H%M%S"
)

backup = (
    TARGET.parent
    /
    (
        "analise_backup_fase9i_"
        f"{timestamp}.py"
    )
)

print(
    "[3/9] Criando backup..."
)

shutil.copy2(
    TARGET,
    backup,
)

print(
    f"      {backup}"
)


try:

    print(
        "[4/9] Aplicando UoW..."
    )

    patched = patch_legado(
        current
    )

    TARGET.write_text(
        patched,
        encoding="utf-8",
    )

    print(
        "      [OK] patch aplicado."
    )


    print(
        "[5/9] Validando sintaxe..."
    )

    py_compile.compile(
        str(TARGET),
        doraise=True,
    )

    print(
        "      [OK] sintaxe válida."
    )


    print(
        "[6/9] Validando fronteira por função..."
    )

    final_text = TARGET.read_text(
        encoding="utf-8"
    )

    state2, after = (
        detectar_estado(
            final_text
        )
    )

    if state2 != "UOW":

        raise RuntimeError(
            f"Estado final inválido: "
            f"{state2} / {after}"
        )

    validar_funcoes(
        final_text,
        "UOW",
    )

    print(
        "      [OK] analisar_sessao: "
        "1 UoW / 0 commit / 0 rollback."
    )

    print(
        "      [OK] analisar_rodada: "
        "1 UoW / 0 commit / 2 rollbacks."
    )

    print(
        "      [OK] consultar_analise_rotativo: "
        "1 UoW / 0 commit / 0 rollback."
    )


    print(
        "[7/9] Validando ausência de commit..."
    )

    if "uow.commit()" in final_text:

        raise RuntimeError(
            "Commit indevido introduzido."
        )

    print(
        "      [OK] 0 commits."
    )


    print(
        "[8/9] Validando contratos..."
    )

    for token in INVARIANTS:

        if token not in final_text:

            raise RuntimeError(
                f"Invariante perdida: {token}"
            )

    print(
        "      [OK] ROTATIVO/OFICIAL preservados."
    )

    print(
        "      [OK] ANALISE_VISUALIZAR preservado."
    )


    print(
        "[9/9] Validando ownership legado removido..."
    )

    for token in [
        "from database import get_connection",
        "get_connection()",
        "conn.rollback()",
        "cursor.close()",
        "conn.close()",
    ]:

        if token in final_text:

            raise RuntimeError(
                "Ownership legado permaneceu: "
                f"{token}"
            )

    print(
        "      [OK] analise.py usa somente UoW "
        "para conexão/cursor."
    )


except Exception:

    print()
    print(
        "[ERRO] Falha durante Fase 9I."
    )

    print(
        "[INFO] Restaurando analise.py..."
    )

    shutil.copy2(
        backup,
        TARGET,
    )

    print(
        "[OK] Estado anterior restaurado."
    )

    raise


print()
print(
    "[OK] Fase 9I aplicada."
)

print(
    "[OK] 3 conexões migradas para UoW."
)

print(
    "[OK] 0 commits preservados."
)

print(
    "[OK] 2 rollbacks de analisar_rodada preservados."
)

print()
print(
    "BACKUP:"
)

print(
    f"  {backup}"
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
