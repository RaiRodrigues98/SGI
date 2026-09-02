"""
Fase 9F - UoW em escopo, snapshot e configurações operacionais.

Arquivos:
- routers/escopo.py
- routers/snapshot.py
- routers/configuracoes_operacionais.py

Pré-requisito:
- Fases 9A a 9E aplicadas.

Execute:
python .\fase9f_unit_of_work_escopo_snapshot_config\aplicar_fase9f.py
"""

from pathlib import Path
from datetime import datetime
import ast
import py_compile
import shutil

ROOT = Path.cwd()

UOW = (
    ROOT
    / "infrastructure"
    / "database"
    / "unit_of_work.py"
)

TARGETS = {
    "escopo.py": {
        "path": ROOT / "routers" / "escopo.py",
        "connections": 4,
        "commits": 1,
        "rollbacks": 2,
        "write_functions": {
            "adicionar_localizacoes_escopo": (1, 2),
        },
        "read_functions": {
            "listar_estoque_candidatos",
            "listar_localizacoes_candidatas",
            "consultar_escopo_inventario",
        },
        "invariants": [
            "def listar_estoque_candidatos(",
            "def listar_localizacoes_candidatas(",
            "def adicionar_localizacoes_escopo(",
            "def consultar_escopo_inventario(",
            "InventarioEscopoLocalizacoes",
        ],
    },

    "snapshot.py": {
        "path": ROOT / "routers" / "snapshot.py",
        "connections": 1,
        "commits": 1,
        "rollbacks": 2,
        "write_functions": {
            "gerar_snapshot_inventario": (1, 2),
        },
        "read_functions": set(),
        "invariants": [
            "def gerar_snapshot_inventario(",
            "InventarioEstoqueSnapshot",
            "InventarioEscopoLocalizacoes",
            "CONFIGURACAO_EDITAR",
        ],
    },

    "configuracoes_operacionais.py": {
        "path": ROOT / "routers" / "configuracoes_operacionais.py",
        "connections": 2,
        "commits": 1,
        "rollbacks": 2,
        "write_functions": {
            "atualizar_configuracao": (1, 2),
        },
        "read_functions": {
            "consultar_configuracao",
        },
        "invariants": [
            "def consultar_configuracao(",
            "def atualizar_configuracao(",
            "CONFIGURACAO_VISUALIZAR",
            "CONFIGURACAO_EDITAR",
        ],
    },
}

PREVIOUS_PHASES = [
    ROOT / "routers" / "rodadas.py",
    ROOT / "routers" / "finalizacao.py",
    ROOT / "routers" / "inventarios.py",
    ROOT / "routers" / "rotativo.py",
    ROOT / "routers" / "gestor.py",
    ROOT / "routers" / "encaminhamento_gestor.py",
    ROOT / "routers" / "auth.py",
    ROOT / "routers" / "usuarios.py",
    ROOT / "routers" / "contagens.py",
]


def function_map(text):

    tree = ast.parse(text)
    lines = text.splitlines()
    result = {}

    for node in tree.body:

        if not isinstance(node, ast.FunctionDef):
            continue

        segment = "\n".join(
            lines[node.lineno - 1:node.end_lineno]
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
    }


def detectar_estado(text, p):

    d = diagnostico(text)
    n = p["connections"]

    legacy = (
        "from database import get_connection" in text
        and d["legacy_connections"] == n
        and d["legacy_commits"] == p["commits"]
        and d["legacy_rollbacks"] == p["rollbacks"]
        and d["legacy_cursor_close"] == n
        and d["legacy_conn_close"] == n
        and d["legacy_conn_none"] == n
        and d["legacy_cursor_none"] == n
    )

    uow = (
        "SqlServerUnitOfWork" in text
        and d["legacy_connections"] == 0
        and d["legacy_commits"] == 0
        and d["legacy_rollbacks"] == 0
        and d["legacy_cursor_close"] == 0
        and d["legacy_conn_close"] == 0
        and d["uow_ctor"] == n
        and d["uow_open"] == n
        and d["uow_commits"] == p["commits"]
        and d["uow_rollbacks"] == p["rollbacks"]
        and d["uow_close"] == n
        and d["uow_conn_alias"] == n
        and d["uow_cursor"] == n
    )

    if legacy:
        return "LEGADO", d

    if uow:
        return "UOW", d

    return "DESCONHECIDO", d


def validar_semantica(name, text, p, modo):

    ast.parse(text)

    for token in p["invariants"]:

        if token not in text:

            raise RuntimeError(
                f"{name}: invariante ausente: {token}"
            )

    fmap = function_map(text)

    for fn, expected in p["write_functions"].items():

        if fn not in fmap:

            raise RuntimeError(
                f"{name}: função de escrita ausente: {fn}"
            )

        info = fmap[fn]

        if modo == "LEGADO":

            valores = (
                info["legacy_connection"],
                info["legacy_commit"],
                info["legacy_rollback"],
            )

        else:

            valores = (
                info["uow_ctor"],
                info["uow_commit"],
                info["uow_rollback"],
            )

        alvo = (
            1,
            expected[0],
            expected[1],
        )

        if valores != alvo:

            raise RuntimeError(
                f"{name}/{fn}: "
                f"esperado={alvo}, atual={valores}"
            )

    for fn in p["read_functions"]:

        if fn not in fmap:

            raise RuntimeError(
                f"{name}: função de leitura ausente: {fn}"
            )

        info = fmap[fn]

        if modo == "LEGADO":

            valores = (
                info["legacy_connection"],
                info["legacy_commit"],
                info["legacy_rollback"],
            )

        else:

            valores = (
                info["uow_ctor"],
                info["uow_commit"],
                info["uow_rollback"],
            )

        if valores != (1, 0, 0):

            raise RuntimeError(
                f"{name}/{fn}: leitura alterada "
                f"{valores}"
            )


def patch_legado(name, text, p):

    validar_semantica(
        name,
        text,
        p,
        "LEGADO",
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
        "    uow = None\n    conn = None\n    cursor = None",
    )

    patched = patched.replace(
        "        conn = get_connection()\n"
        "        cursor = conn.cursor()",
        (
            "        uow = SqlServerUnitOfWork()\n"
            "        uow.open()\n"
            "        conn = uow.connection\n"
            "        cursor = uow.cursor"
        ),
    )

    patched = patched.replace(
        "conn.commit()",
        "uow.commit()",
    )

    patched = patched.replace(
        "conn.rollback()",
        "uow.rollback()",
    )

    old_finally = (
        "        if cursor:\n"
        "            cursor.close()\n\n"
        "        if conn:\n"
        "            conn.close()"
    )

    if patched.count(old_finally) != p["connections"]:

        raise RuntimeError(
            f"{name}: expected {p['connections']} finally, "
            f"found {patched.count(old_finally)}"
        )

    patched = patched.replace(
        old_finally,
        "        if uow:\n            uow.close()",
    )

    state, d = detectar_estado(
        patched,
        p,
    )

    if state != "UOW":

        raise RuntimeError(
            f"{name}: estado pós-patch inválido: "
            f"{state} / {d}"
        )

    validar_semantica(
        name,
        patched,
        p,
        "UOW",
    )

    return patched


# ============================================================
# PRÉ-REQUISITOS
# ============================================================

print(
    "[0/10] Validando Unit of Work..."
)

if not UOW.exists():

    raise SystemExit(
        f"[ERRO] Unit of Work ausente: {UOW}"
    )

uow_text = UOW.read_text(
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
        "[ERRO] UoW possui auto-commit inesperado."
    )

print(
    "      [OK] Unit of Work reconhecido."
)


print(
    "[1/10] Validando Fases 9A-9E..."
)

for path in PREVIOUS_PHASES:

    if not path.exists():

        raise SystemExit(
            f"[ERRO] Fase anterior: arquivo ausente {path}"
        )

    content = path.read_text(
        encoding="utf-8"
    )

    if "SqlServerUnitOfWork" not in content:

        raise SystemExit(
            "[ERRO] Fase anterior não reconhecida em "
            f"{path.name}"
        )

print(
    "      [OK] Fases anteriores reconhecidas."
)


# ============================================================
# DETECTA OS 3 ARQUIVOS ANTES DE ALTERAR
# ============================================================

print(
    "[2/10] Detectando estado dos routers..."
)

states = {}

for name, p in TARGETS.items():

    path = p["path"]

    if not path.exists():

        raise SystemExit(
            f"[ERRO] Router ausente: {path}"
        )

    text = path.read_text(
        encoding="utf-8"
    )

    state, d = detectar_estado(
        text,
        p,
    )

    states[name] = {
        "state": state,
        "diag": d,
        "text": text,
    }

    print(
        f"      {name}: {state}"
    )

    print(
        "        "
        f"conn={p['connections']} | "
        f"commit={p['commits']} | "
        f"rollback={p['rollbacks']}"
    )

    if state == "LEGADO":

        try:
            validar_semantica(
                name,
                text,
                p,
                "LEGADO",
            )
        except Exception as exc:
            raise SystemExit(
                f"[ERRO] {name}: {exc}"
            )

    elif state == "UOW":

        try:
            validar_semantica(
                name,
                text,
                p,
                "UOW",
            )
        except Exception as exc:
            raise SystemExit(
                f"[ERRO] {name}: {exc}"
            )


unknown = [
    name
    for name, data in states.items()
    if data["state"] == "DESCONHECIDO"
]

if unknown:

    print()
    print(
        "[ERRO] Estrutura desconhecida detectada."
    )

    print(
        "[INFO] Nenhum arquivo foi alterado."
    )

    for name in unknown:

        print()
        print(
            f"DIAGNÓSTICO — {name}"
        )

        for key, value in (
            states[name]["diag"].items()
        ):

            print(
                f"  {key}: {value}"
            )

    raise SystemExit(1)


# ============================================================
# BACKUPS
# ============================================================

timestamp = datetime.now().strftime(
    "%Y%m%d_%H%M%S"
)

backups = {}

print(
    "[3/10] Criando backups dos arquivos legados..."
)

for name, data in states.items():

    if data["state"] != "LEGADO":

        print(
            f"      {name}: já usa UoW."
        )

        continue

    path = TARGETS[name]["path"]

    backup = (
        path.parent
        / (
            path.stem
            + "_backup_fase9f_"
            + timestamp
            + ".py"
        )
    )

    shutil.copy2(
        path,
        backup,
    )

    backups[name] = backup

    print(
        f"      {name} -> {backup.name}"
    )


try:

    print(
        "[4/10] Migrando escopo.py..."
    )

    name = "escopo.py"

    if states[name]["state"] == "LEGADO":

        TARGETS[name]["path"].write_text(
            patch_legado(
                name,
                states[name]["text"],
                TARGETS[name],
            ),
            encoding="utf-8",
        )

        print(
            "      [OK] migrado."
        )

    else:

        print(
            "      [OK] já estava em UoW."
        )


    print(
        "[5/10] Migrando snapshot.py..."
    )

    name = "snapshot.py"

    if states[name]["state"] == "LEGADO":

        TARGETS[name]["path"].write_text(
            patch_legado(
                name,
                states[name]["text"],
                TARGETS[name],
            ),
            encoding="utf-8",
        )

        print(
            "      [OK] migrado."
        )

    else:

        print(
            "      [OK] já estava em UoW."
        )


    print(
        "[6/10] Migrando configuracoes_operacionais.py..."
    )

    name = "configuracoes_operacionais.py"

    if states[name]["state"] == "LEGADO":

        TARGETS[name]["path"].write_text(
            patch_legado(
                name,
                states[name]["text"],
                TARGETS[name],
            ),
            encoding="utf-8",
        )

        print(
            "      [OK] migrado."
        )

    else:

        print(
            "      [OK] já estava em UoW."
        )


    print(
        "[7/10] Validando sintaxe..."
    )

    for name, p in TARGETS.items():

        py_compile.compile(
            str(p["path"]),
            doraise=True,
        )

        print(
            f"      [OK] {name}"
        )


    print(
        "[8/10] Validando fronteiras finais..."
    )

    for name, p in TARGETS.items():

        final_text = p["path"].read_text(
            encoding="utf-8"
        )

        state, d = detectar_estado(
            final_text,
            p,
        )

        if state != "UOW":

            raise RuntimeError(
                f"{name}: estado final {state}: {d}"
            )

        validar_semantica(
            name,
            final_text,
            p,
            "UOW",
        )

        print(
            f"      [OK] {name}: "
            f"{p['commits']} commit | "
            f"{p['rollbacks']} rollback(s)"
        )


    print(
        "[9/10] Validando rotas de leitura sem commit..."
    )

    for name, p in TARGETS.items():

        fmap = function_map(
            p["path"].read_text(
                encoding="utf-8"
            )
        )

        for fn in p["read_functions"]:

            info = fmap[fn]

            if (
                info["uow_commit"] != 0
                or info["uow_rollback"] != 0
            ):

                raise RuntimeError(
                    f"{name}/{fn}: transação "
                    "introduzida indevidamente."
                )

            print(
                f"      [OK] {name}/{fn}: leitura pura."
            )


    print(
        "[10/10] Revalidando Fases 9A-9E..."
    )

    for path in PREVIOUS_PHASES:

        content = path.read_text(
            encoding="utf-8"
        )

        if "SqlServerUnitOfWork" not in content:

            raise RuntimeError(
                "Regressão de fase anterior em "
                f"{path.name}"
            )

    print(
        "      [OK] Fases anteriores preservadas."
    )


except Exception:

    print()
    print(
        "[ERRO] Falha durante Fase 9F."
    )

    print(
        "[INFO] Restaurando arquivos alterados..."
    )

    for name, backup in backups.items():

        shutil.copy2(
            backup,
            TARGETS[name]["path"],
        )

        print(
            f"      [OK] restaurado: {name}"
        )

    raise


print()
print(
    "[OK] Fase 9F aplicada."
)

print(
    "[OK] Escopo, Snapshot e Configurações usam UoW."
)

print(
    "[OK] Rotas de leitura continuam sem commit."
)

print(
    "[OK] Fases 9A-9E preservadas."
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
