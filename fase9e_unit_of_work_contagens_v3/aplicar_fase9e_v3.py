"""
Fase 9E v3 - Unit of Work em routers/contagens.py.

Correção sobre a v2:
- não exige blocos finally textualmente idênticos;
- usa AST para localizar cursor.close() e conn.close()
  semanticamente dentro de cada finally;
- preserva qualquer código/comentário adicional do finally;
- preserva a quantidade REAL de UPDLOCK/HOLDLOCK/2601/2627.

Execute na raiz do SGI:

python .\fase9e_unit_of_work_contagens_v3\aplicar_fase9e_v3.py
"""

from pathlib import Path
from datetime import datetime
import ast
import py_compile
import re
import shutil

ROOT = Path.cwd()

target_uow = (
    ROOT
    / "infrastructure"
    / "database"
    / "unit_of_work.py"
)

target_contagens = (
    ROOT
    / "routers"
    / "contagens.py"
)

phase_checks = {
    "9A": ROOT / "routers" / "rodadas.py",
    "9B": ROOT / "routers" / "finalizacao.py",
    "9C-inventarios": ROOT / "routers" / "inventarios.py",
    "9C-rotativo": ROOT / "routers" / "rotativo.py",
    "9C-gestor": ROOT / "routers" / "gestor.py",
    "9C-encaminhamento": ROOT / "routers" / "encaminhamento_gestor.py",
    "9D-auth": ROOT / "routers" / "auth.py",
    "9D-usuarios": ROOT / "routers" / "usuarios.py",
}

WRITE_FUNCTIONS = {
    "iniciar_localizacao",
    "encerrar_localizacao",
    "salvar_contagem",
    "cancelar_contagem",
}

READ_FUNCTIONS = {
    "listar_contagens_sessao",
    "listar_sessoes",
}

EXPECTED_ROUTES = [
    '"/localizacoes/iniciar"',
    '"/localizacoes/encerrar"',
    '"/contagens"',
    '"/sessoes/{id_sessao}/contagens"',
    '"/contagens/{id_contagem}/cancelar"',
    '"/sessoes"',
]

EXPECTED_PERMISSIONS = [
    '"CONTAGEM_EXECUTAR"',
    '"CONTAGEM_CANCELAR"',
    '"ANALISE_VISUALIZAR"',
]


def transaction_map(text):

    tree = ast.parse(text)
    lines = text.splitlines()
    result = {}

    for node in tree.body:

        if not isinstance(node, ast.FunctionDef):
            continue

        segment = "\n".join(
            lines[
                node.lineno - 1:
                node.end_lineno
            ]
        )

        result[node.name] = {
            "legacy_connection":
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

    return result


def diagnostico(text):

    return {
        "legacy_connections": text.count("get_connection()"),
        "legacy_commits": text.count("conn.commit()"),
        "legacy_rollbacks": text.count("conn.rollback()"),
        "legacy_cursor_close": text.count("cursor.close()"),
        "legacy_conn_close": text.count("conn.close()"),
        "legacy_conn_none": text.count("conn = None"),
        "legacy_cursor_none": text.count("cursor = None"),
        "uow_ctor": text.count("SqlServerUnitOfWork()"),
        "uow_open": text.count("uow.open()"),
        "uow_commits": text.count("uow.commit()"),
        "uow_rollbacks": text.count("uow.rollback()"),
        "uow_close": text.count("uow.close()"),
        "uow_conn_alias": text.count("conn = uow.connection"),
        "uow_cursor": text.count("cursor = uow.cursor"),
        "updlock": text.count("UPDLOCK"),
        "holdlock": text.count("HOLDLOCK"),
        "sql_2601": text.count("2601"),
        "sql_2627": text.count("2627"),
    }


def detectar_estado(text):

    d = diagnostico(text)

    legado = (
        "from database import get_connection" in text
        and d["legacy_connections"] == 6
        and d["legacy_commits"] == 4
        and d["legacy_rollbacks"] == 8
        and d["legacy_cursor_close"] == 6
        and d["legacy_conn_close"] == 6
        and d["legacy_conn_none"] == 6
        and d["legacy_cursor_none"] == 6
    )

    uow = (
        "SqlServerUnitOfWork" in text
        and d["legacy_connections"] == 0
        and d["legacy_commits"] == 0
        and d["legacy_rollbacks"] == 0
        and d["legacy_cursor_close"] == 0
        and d["legacy_conn_close"] == 0
        and d["uow_ctor"] == 6
        and d["uow_open"] == 6
        and d["uow_commits"] == 4
        and d["uow_rollbacks"] == 8
        and d["uow_close"] == 6
        and d["uow_conn_alias"] == 6
        and d["uow_cursor"] == 6
    )

    if legado:
        return "LEGADO", d

    if uow:
        return "UOW", d

    return "DESCONHECIDO", d


def validar_contratos(text):

    ast.parse(text)

    for token in EXPECTED_ROUTES:

        if token not in text:

            raise RuntimeError(
                f"Endpoint ausente: {token}"
            )

    for token in EXPECTED_PERMISSIONS:

        if token not in text:

            raise RuntimeError(
                f"Permissão ausente: {token}"
            )

    for token in [
        "def iniciar_localizacao(",
        "def encerrar_localizacao(",
        "def salvar_contagem(",
        "def listar_contagens_sessao(",
        "def cancelar_contagem(",
        "def listar_sessoes(",
    ]:

        if token not in text:

            raise RuntimeError(
                f"Função ausente: {token}"
            )


def validar_mapa(text, modo):

    mapa = transaction_map(text)

    missing = (
        WRITE_FUNCTIONS
        | READ_FUNCTIONS
    ) - set(mapa)

    if missing:

        raise RuntimeError(
            f"Funções ausentes: {sorted(missing)}"
        )

    for name in WRITE_FUNCTIONS:

        info = mapa[name]

        valores = (
            (
                info["legacy_connection"],
                info["legacy_commit"],
                info["legacy_rollback"],
            )
            if modo == "LEGADO"
            else (
                info["uow_ctor"],
                info["uow_commit"],
                info["uow_rollback"],
            )
        )

        if valores != (1, 1, 2):

            raise RuntimeError(
                f"{name}: esperado (1,1,2), "
                f"encontrado {valores}"
            )

    for name in READ_FUNCTIONS:

        info = mapa[name]

        valores = (
            (
                info["legacy_connection"],
                info["legacy_commit"],
                info["legacy_rollback"],
            )
            if modo == "LEGADO"
            else (
                info["uow_ctor"],
                info["uow_commit"],
                info["uow_rollback"],
            )
        )

        if valores != (1, 0, 0):

            raise RuntimeError(
                f"{name}: leitura esperava (1,0,0), "
                f"encontrado {valores}"
            )


def is_close_call(node, obj_name):

    return (
        isinstance(node, ast.Call)
        and
        isinstance(node.func, ast.Attribute)
        and
        node.func.attr == "close"
        and
        isinstance(node.func.value, ast.Name)
        and
        node.func.value.id == obj_name
    )


def stmt_contains_close(stmt, obj_name):

    return any(
        is_close_call(node, obj_name)
        for node in ast.walk(stmt)
    )


def localizar_cleanup_finally(text):

    tree = ast.parse(text)

    cursor_stmts = []
    conn_stmts = []

    for node in ast.walk(tree):

        if not isinstance(node, ast.Try):
            continue

        for stmt in node.finalbody:

            if stmt_contains_close(
                stmt,
                "cursor"
            ):

                cursor_stmts.append(
                    stmt
                )

            if stmt_contains_close(
                stmt,
                "conn"
            ):

                conn_stmts.append(
                    stmt
                )

    return (
        cursor_stmts,
        conn_stmts,
    )


def reescrever_cleanup_via_ast(text):

    (
        cursor_stmts,
        conn_stmts,
    ) = localizar_cleanup_finally(
        text
    )

    print(
        "      Cleanup AST detectado:"
    )

    print(
        "        cursor.close em finally: "
        f"{len(cursor_stmts)}"
    )

    print(
        "        conn.close em finally: "
        f"{len(conn_stmts)}"
    )

    if len(cursor_stmts) != 6:

        raise RuntimeError(
            "Esperados 6 cursor.close() dentro "
            f"de finally, encontrado {len(cursor_stmts)}."
        )

    if len(conn_stmts) != 6:

        raise RuntimeError(
            "Esperados 6 conn.close() dentro "
            f"de finally, encontrado {len(conn_stmts)}."
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

        source_line = (
            lines[
                stmt.lineno - 1
            ]
        )

        indent = (
            source_line[
                :
                len(source_line)
                - len(
                    source_line.lstrip()
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
        key=lambda item: (
            item[0],
            item[1],
        )
    )

    # Statements top-level do finalbody não podem se sobrepor.
    last_end = 0

    for start, end, _ in replacements:

        if start <= last_end:

            raise RuntimeError(
                "Statements de cleanup "
                "sobrepostos."
            )

        last_end = end

    out = []

    current_line = 1

    for (
        start,
        end,
        replacement
    ) in replacements:

        out.extend(
            lines[
                current_line - 1:
                start - 1
            ]
        )

        if replacement:

            out.extend(
                replacement.splitlines()
            )

        current_line = end + 1

    out.extend(
        lines[
            current_line - 1:
        ]
    )

    final = "\n".join(
        out
    )

    if text.endswith("\n"):
        final += "\n"

    return final


def substituir_abertura_recursos(text):

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

    text, count_init = (
        init_pattern.subn(
            repl_init,
            text,
        )
    )

    if count_init != 6:

        raise RuntimeError(
            "Esperados 6 blocos "
            "conn/cursor None, encontrado "
            f"{count_init}."
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

    text, count_open = (
        open_pattern.subn(
            repl_open,
            text,
        )
    )

    if count_open != 6:

        raise RuntimeError(
            "Esperadas 6 aberturas "
            "conn/cursor, encontrado "
            f"{count_open}."
        )

    return text


def patch_legado(
    text,
    before,
):

    validar_contratos(
        text
    )

    validar_mapa(
        text,
        "LEGADO",
    )

    for key in [
        "updlock",
        "holdlock",
        "sql_2601",
        "sql_2627",
    ]:

        if before[key] <= 0:

            raise RuntimeError(
                f"Proteção ausente: {key}"
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

    patched = (
        substituir_abertura_recursos(
            patched
        )
    )

    patched = patched.replace(
        "conn.commit()",
        "uow.commit()",
    )

    patched = patched.replace(
        "conn.rollback()",
        "uow.rollback()",
    )

    # Principal correção da v3:
    # cleanup localizado semanticamente pelo AST.
    patched = (
        reescrever_cleanup_via_ast(
            patched
        )
    )

    state, after = detectar_estado(
        patched
    )

    if state != "UOW":

        raise RuntimeError(
            "Estado pós-patch inválido: "
            f"{state} / {after}"
        )

    validar_mapa(
        patched,
        "UOW",
    )

    for key in [
        "updlock",
        "holdlock",
        "sql_2601",
        "sql_2627",
    ]:

        if (
            after[key]
            != before[key]
        ):

            raise RuntimeError(
                f"{key} alterado: "
                f"{before[key]} -> "
                f"{after[key]}"
            )

    return patched


# ============================================================
# PRÉ-REQUISITOS
# ============================================================

print(
    "[0/12] Validando arquivos..."
)

for file in [
    target_uow,
    target_contagens,
]:

    if not file.exists():

        raise SystemExit(
            f"[ERRO] Arquivo ausente: {file}"
        )


print(
    "[1/12] Validando Unit of Work..."
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
            f"[ERRO] UoW inválido: {token}"
        )

if "self.commit()" in uow_text:

    raise SystemExit(
        "[ERRO] UoW possui auto-commit."
    )

print(
    "      [OK] UoW reconhecido."
)


print(
    "[2/12] Validando Fases 9A-9D..."
)

for phase, path in (
    phase_checks.items()
):

    if not path.exists():

        raise SystemExit(
            f"[ERRO] {phase}: "
            f"arquivo ausente {path}"
        )

    text = path.read_text(
        encoding="utf-8"
    )

    if (
        "SqlServerUnitOfWork"
        not in text
    ):

        raise SystemExit(
            f"[ERRO] {phase} "
            f"não reconhecida em "
            f"{path.name}"
        )

print(
    "      [OK] Fases anteriores reconhecidas."
)


# ============================================================
# ANALISA ARQUIVO REAL
# ============================================================

print(
    "[3/12] Analisando routers/contagens.py..."
)

current = target_contagens.read_text(
    encoding="utf-8"
)

try:

    validar_contratos(
        current
    )

except Exception as exc:

    raise SystemExit(
        f"[ERRO] Contratos: {exc}"
    )

state, before = detectar_estado(
    current
)

print(
    f"      Estado: {state}"
)

print(
    "      Transação:"
)

print(
    "        conexões: "
    f"{before['legacy_connections'] or before['uow_ctor']}"
)

print(
    "        commits: "
    f"{before['legacy_commits'] or before['uow_commits']}"
)

print(
    "        rollbacks: "
    f"{before['legacy_rollbacks'] or before['uow_rollbacks']}"
)

print(
    "      Concorrência:"
)

print(
    f"        UPDLOCK: {before['updlock']}"
)

print(
    f"        HOLDLOCK: {before['holdlock']}"
)

print(
    f"        2601: {before['sql_2601']}"
)

print(
    f"        2627: {before['sql_2627']}"
)


if state == "DESCONHECIDO":

    print()
    print(
        "[ERRO] Estrutura transacional "
        "não reconhecida."
    )

    print(
        "[INFO] Nenhum arquivo foi alterado."
    )

    raise SystemExit(1)


try:

    validar_mapa(
        current,
        (
            "LEGADO"
            if state == "LEGADO"
            else "UOW"
        ),
    )

except Exception as exc:

    raise SystemExit(
        f"[ERRO] Mapa transacional: {exc}"
    )


# ============================================================
# JÁ MIGRADO
# ============================================================

if state == "UOW":

    print(
        "[4/12] contagens.py já usa UoW."
    )

    print(
        "      Nenhuma alteração necessária."
    )

    print()
    print(
        "[OK] Fase 9E considerada aplicada."
    )

    print()
    print(
        "PRÓXIMO PASSO:"
    )

    print(
        r"python tests_e2e\regressao_final_sgi.py"
    )

    raise SystemExit(0)


# ============================================================
# DIAGNÓSTICO DO CLEANUP REAL
# ============================================================

print(
    "[4/12] Analisando cleanup via AST..."
)

try:

    (
        cursor_cleanup,
        conn_cleanup,
    ) = localizar_cleanup_finally(
        current
    )

except Exception as exc:

    raise SystemExit(
        f"[ERRO] AST cleanup: {exc}"
    )

print(
    "      cursor.close() em finally: "
    f"{len(cursor_cleanup)}"
)

print(
    "      conn.close() em finally: "
    f"{len(conn_cleanup)}"
)

if (
    len(cursor_cleanup) != 6
    or
    len(conn_cleanup) != 6
):

    print()
    print(
        "[ERRO] Os 6 recursos existem no arquivo, "
        "mas nem todos estão em statements de finally "
        "reconhecíveis."
    )

    print(
        "[INFO] Nenhum arquivo foi alterado."
    )

    raise SystemExit(1)


# ============================================================
# BACKUP
# ============================================================

timestamp = datetime.now().strftime(
    "%Y%m%d_%H%M%S"
)

backup = (
    target_contagens.parent
    / (
        "contagens_backup_fase9e_v3_"
        f"{timestamp}.py"
    )
)

print(
    "[5/12] Criando backup..."
)

shutil.copy2(
    target_contagens,
    backup,
)

print(
    f"      {backup}"
)


try:

    print(
        "[6/12] Aplicando UoW..."
    )

    patched = patch_legado(
        current,
        before,
    )

    target_contagens.write_text(
        patched,
        encoding="utf-8",
    )

    print(
        "      [OK] patch aplicado."
    )


    print(
        "[7/12] Validando sintaxe..."
    )

    py_compile.compile(
        str(target_contagens),
        doraise=True,
    )

    print(
        "      [OK] sintaxe válida."
    )


    print(
        "[8/12] Validando fronteira..."
    )

    final_text = (
        target_contagens.read_text(
            encoding="utf-8"
        )
    )

    final_state, after = (
        detectar_estado(
            final_text
        )
    )

    if final_state != "UOW":

        raise RuntimeError(
            f"Estado final: {final_state} / {after}"
        )

    validar_mapa(
        final_text,
        "UOW",
    )

    print(
        "      [OK] 6 UoW."
    )

    print(
        "      [OK] 4 commits."
    )

    print(
        "      [OK] 8 rollbacks."
    )

    print(
        "      [OK] leituras sem commit."
    )


    print(
        "[9/12] Comparando concorrência..."
    )

    for key, label in [
        ("updlock", "UPDLOCK"),
        ("holdlock", "HOLDLOCK"),
        ("sql_2601", "2601"),
        ("sql_2627", "2627"),
    ]:

        if after[key] != before[key]:

            raise RuntimeError(
                f"{label}: "
                f"{before[key]} -> {after[key]}"
            )

        print(
            f"      [OK] {label}: "
            f"{after[key]}"
        )


    print(
        "[10/12] Validando cleanup final..."
    )

    if "cursor.close()" in final_text:

        raise RuntimeError(
            "cursor.close legado permaneceu."
        )

    if "conn.close()" in final_text:

        raise RuntimeError(
            "conn.close legado permaneceu."
        )

    if (
        final_text.count(
            "uow.close()"
        )
        != 6
    ):

        raise RuntimeError(
            "Esperados 6 uow.close(), "
            f"encontrado "
            f"{final_text.count('uow.close()')}."
        )

    print(
        "      [OK] 6 uow.close()."
    )


    print(
        "[11/12] Validando contratos..."
    )

    validar_contratos(
        final_text
    )

    print(
        "      [OK] endpoints/permissões preservados."
    )


    print(
        "[12/12] Revalidando Fases 9A-9D..."
    )

    for phase, path in (
        phase_checks.items()
    ):

        text = path.read_text(
            encoding="utf-8"
        )

        if (
            "SqlServerUnitOfWork"
            not in text
        ):

            raise RuntimeError(
                f"Regressão em {phase}"
            )

    print(
        "      [OK] fases anteriores preservadas."
    )


except Exception:

    print()
    print(
        "[ERRO] Falha durante a Fase 9E v3."
    )

    print(
        "[INFO] Restaurando contagens.py..."
    )

    shutil.copy2(
        backup,
        target_contagens,
    )

    print(
        "[OK] Estado anterior restaurado."
    )

    raise


print()
print(
    "[OK] Fase 9E v3 aplicada."
)

print(
    "[OK] Cleanup real foi migrado via AST."
)

print(
    "[OK] Concorrência existente preservada."
)

print(
    "[OK] 2601/2627 preservados."
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
