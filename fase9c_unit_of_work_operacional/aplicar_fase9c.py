"""
Fase 9C - Unit of Work no núcleo operacional.

Routers:
- inventarios.py
- rotativo.py
- gestor.py
- encaminhamento_gestor.py

Pré-requisito:
- Fase 9A instalada;
- Fase 9B aplicada/validada.

Execute na raiz do SGI:

python .\fase9c_unit_of_work_operacional\aplicar_fase9c.py
"""

from pathlib import Path
from datetime import datetime
import ast
import py_compile
import shutil

ROOT = Path.cwd()

target_uow = (
    ROOT
    / "infrastructure"
    / "database"
    / "unit_of_work.py"
)

target_rodadas = ROOT / "routers" / "rodadas.py"
target_finalizacao = ROOT / "routers" / "finalizacao.py"

TARGETS = {
    "inventarios.py": {
        "path": ROOT / "routers" / "inventarios.py",
        "invariants": [
            '"/inventarios"',
            '"INVENTARIO_CRIAR"',
            "criar_inventario(",
        ],
    },

    "rotativo.py": {
        "path": ROOT / "routers" / "rotativo.py",
        "invariants": [
            '"/inventarios/{id_inventario}/decisoes-rotativo"',
            '"INVENTARIO_ROTATIVO_DECIDIR"',
            "registrar_decisao_rotativo(",
        ],
    },

    "gestor.py": {
        "path": ROOT / "routers" / "gestor.py",
        "invariants": [
            '"/inventarios/{id_inventario}/decisoes-gestor"',
            '"GESTOR_DECIDIR"',
        ],
    },

    "encaminhamento_gestor.py": {
        "path": ROOT / "routers" / "encaminhamento_gestor.py",
        "invariants": [
            '"/inventarios/{id_inventario}/encaminhar-gestor"',
            '"GESTOR_DECIDIR"',
            "encaminhar_inventario_para_gestor(",
        ],
    },
}


def diagnostico(text):

    return {
        "get_connection":
            text.count("get_connection()"),

        "conn_commit":
            text.count("conn.commit()"),

        "conn_rollback":
            text.count("conn.rollback()"),

        "conn_close":
            text.count("conn.close()"),

        "cursor_close":
            text.count("cursor.close()"),

        "uow_ctor":
            text.count("SqlServerUnitOfWork()"),

        "uow_open":
            text.count("uow.open()"),

        "uow_commit":
            text.count("uow.commit()"),

        "uow_rollback":
            text.count("uow.rollback()"),

        "uow_close":
            text.count("uow.close()"),

        "uow_connection":
            text.count("conn = uow.connection"),

        "uow_cursor":
            text.count("cursor = uow.cursor"),
    }


def detectar_estado(text):

    d = diagnostico(text)

    legado = (
        "from database import get_connection" in text
        and
        d["get_connection"] == 1
        and
        d["conn_commit"] == 1
        and
        d["conn_rollback"] >= 1
        and
        d["conn_close"] == 1
        and
        d["cursor_close"] == 1
    )

    uow = (
        "SqlServerUnitOfWork" in text
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
        and
        d["uow_ctor"] == 1
        and
        d["uow_open"] == 1
        and
        d["uow_commit"] == 1
        and
        d["uow_rollback"] >= 1
        and
        d["uow_close"] == 1
        and
        d["uow_cursor"] == 1
    )

    if legado:
        return "LEGADO", d

    if uow:
        return "UOW", d

    return "DESCONHECIDO", d


def validar_invariantes(
    name,
    text,
    expected
):

    missing = [
        token
        for token in expected
        if token not in text
    ]

    if missing:
        raise RuntimeError(
            f"{name}: invariantes ausentes: {missing}"
        )


def patch_legado(
    name,
    text
):

    estado, before = detectar_estado(text)

    if estado != "LEGADO":
        raise RuntimeError(
            f"{name}: patch solicitado para estado {estado}."
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
        1,
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
        1,
    )

    # Preserva exatamente os pontos de transação.
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

    if patched.count(old_finally) != 1:
        raise RuntimeError(
            f"{name}: bloco finally não localizado "
            "de forma única."
        )

    patched = patched.replace(
        old_finally,
        (
            "        if uow:\n"
            "            uow.close()"
        ),
        1,
    )

    ast.parse(patched)

    final_estado, after = detectar_estado(
        patched
    )

    if final_estado != "UOW":
        raise RuntimeError(
            f"{name}: estado pós-patch inválido: "
            f"{final_estado} / {after}"
        )

    if (
        after["uow_commit"]
        != before["conn_commit"]
    ):
        raise RuntimeError(
            f"{name}: quantidade de commits mudou."
        )

    if (
        after["uow_rollback"]
        != before["conn_rollback"]
    ):
        raise RuntimeError(
            f"{name}: quantidade de rollbacks mudou."
        )

    return patched, before, after


# ============================================================
# PRÉ-REQUISITOS 9A / 9B
# ============================================================

print(
    "[0/12] Validando Unit of Work..."
)

for file in [
    target_uow,
    target_rodadas,
    target_finalizacao,
]:

    if not file.exists():

        raise SystemExit(
            f"[ERRO] Pré-requisito ausente: {file}"
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
            "[ERRO] SqlServerUnitOfWork inválido. "
            f"Ausente: {token}"
        )

if "self.commit()" in uow_text:

    raise SystemExit(
        "[ERRO] UoW possui auto-commit inesperado."
    )

print(
    "      [OK] SqlServerUnitOfWork reconhecido."
)

print(
    "[1/12] Validando Fase 9A..."
)

rodadas_text = target_rodadas.read_text(
    encoding="utf-8"
)

for token in [
    "SqlServerUnitOfWork",
    "uow.open()",
    "uow.commit()",
]:

    if token not in rodadas_text:

        raise SystemExit(
            "[ERRO] Fase 9A não identificada: "
            f"{token}"
        )

print(
    "      [OK] Fase 9A reconhecida."
)

print(
    "[2/12] Validando Fase 9B..."
)

finalizacao_text = target_finalizacao.read_text(
    encoding="utf-8"
)

for token in [
    "SqlServerUnitOfWork",
    "sys.sp_getapplock",
    "@LockOwner = 'Transaction'",
    '"INVENTARIO_FINALIZAR"',
]:

    if token not in finalizacao_text:

        raise SystemExit(
            "[ERRO] Fase 9B não identificada/validada: "
            f"{token}"
        )

print(
    "      [OK] Fase 9B reconhecida."
)

# ============================================================
# DETECTA TODOS ANTES DE ALTERAR QUALQUER UM
# ============================================================

print(
    "[3/12] Detectando estado dos routers operacionais..."
)

states = {}

for name, config in TARGETS.items():

    path = config["path"]

    if not path.exists():

        raise SystemExit(
            f"[ERRO] Router ausente: {path}"
        )

    text = path.read_text(
        encoding="utf-8"
    )

    try:
        ast.parse(text)
        validar_invariantes(
            name,
            text,
            config["invariants"],
        )
    except Exception as exc:
        raise SystemExit(
            f"[ERRO] {name}: {exc}"
        )

    state, diag = detectar_estado(
        text
    )

    states[name] = {
        "state": state,
        "diag": diag,
        "text": text,
    }

    print(
        f"      {name}: {state}"
    )

    print(
        "        "
        f"commit={diag['conn_commit'] or diag['uow_commit']} | "
        f"rollback={diag['conn_rollback'] or diag['uow_rollback']}"
    )

unknown = [
    name
    for name, data in states.items()
    if data["state"] == "DESCONHECIDO"
]

if unknown:

    print()
    print(
        "[ERRO] Existem routers em estrutura desconhecida."
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
# BACKUP DOS LEGADOS
# ============================================================

timestamp = datetime.now().strftime(
    "%Y%m%d_%H%M%S"
)

legacy_names = [
    name
    for name, data in states.items()
    if data["state"] == "LEGADO"
]

backups = {}

print(
    "[4/12] Criando backups..."
)

for name in legacy_names:

    path = TARGETS[name]["path"]

    backup = (
        path.parent
        / (
            path.stem
            + "_backup_fase9c_"
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

if not legacy_names:

    print(
        "      Todos os routers já utilizam UoW."
    )

# ============================================================
# APLICA
# ============================================================

try:

    print(
        "[5/12] Migrando inventarios.py..."
    )

    if states["inventarios.py"]["state"] == "LEGADO":

        patched, _, _ = patch_legado(
            "inventarios.py",
            states["inventarios.py"]["text"],
        )

        TARGETS["inventarios.py"]["path"].write_text(
            patched,
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
        "[6/12] Migrando rotativo.py..."
    )

    if states["rotativo.py"]["state"] == "LEGADO":

        patched, _, _ = patch_legado(
            "rotativo.py",
            states["rotativo.py"]["text"],
        )

        # Se existe inteligência pós-commit que usa conn=conn,
        # ela deve continuar recebendo a mesma conexão.
        if (
            "executar_orquestracao_rotativo("
            in states["rotativo.py"]["text"]
        ):

            if "conn=conn" not in patched:

                raise RuntimeError(
                    "rotativo.py perdeu conn=conn "
                    "da inteligência pós-commit."
                )

            if (
                "conn = uow.connection"
                not in patched
            ):

                raise RuntimeError(
                    "rotativo.py perdeu alias da conexão UoW."
                )

        TARGETS["rotativo.py"]["path"].write_text(
            patched,
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
        "[7/12] Migrando gestor.py..."
    )

    if states["gestor.py"]["state"] == "LEGADO":

        patched, _, _ = patch_legado(
            "gestor.py",
            states["gestor.py"]["text"],
        )

        TARGETS["gestor.py"]["path"].write_text(
            patched,
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
        "[8/12] Migrando encaminhamento_gestor.py..."
    )

    if (
        states["encaminhamento_gestor.py"]["state"]
        == "LEGADO"
    ):

        patched, _, _ = patch_legado(
            "encaminhamento_gestor.py",
            states[
                "encaminhamento_gestor.py"
            ]["text"],
        )

        TARGETS[
            "encaminhamento_gestor.py"
        ]["path"].write_text(
            patched,
            encoding="utf-8",
        )

        print(
            "      [OK] migrado."
        )

    else:

        print(
            "      [OK] já estava em UoW."
        )

    # ========================================================
    # VALIDAÇÃO FINAL
    # ========================================================

    print(
        "[9/12] Validando sintaxe..."
    )

    for name, config in TARGETS.items():

        py_compile.compile(
            str(config["path"]),
            doraise=True,
        )

        print(
            f"      [OK] {name}"
        )

    print(
        "[10/12] Validando fronteiras transacionais..."
    )

    final_states = {}

    for name, config in TARGETS.items():

        text = config["path"].read_text(
            encoding="utf-8"
        )

        validar_invariantes(
            name,
            text,
            config["invariants"],
        )

        state, diag = detectar_estado(
            text
        )

        if state != "UOW":

            raise RuntimeError(
                f"{name}: estado final não é UOW: "
                f"{state} / {diag}"
            )

        before = states[name]["diag"]

        commit_antes = (
            before["conn_commit"]
            if states[name]["state"] == "LEGADO"
            else before["uow_commit"]
        )

        rollback_antes = (
            before["conn_rollback"]
            if states[name]["state"] == "LEGADO"
            else before["uow_rollback"]
        )

        if diag["uow_commit"] != commit_antes:

            raise RuntimeError(
                f"{name}: commits mudaram "
                f"{commit_antes} -> {diag['uow_commit']}"
            )

        if diag["uow_rollback"] != rollback_antes:

            raise RuntimeError(
                f"{name}: rollbacks mudaram "
                f"{rollback_antes} -> {diag['uow_rollback']}"
            )

        final_states[name] = diag

        print(
            f"      [OK] {name}: "
            f"{diag['uow_commit']} commit | "
            f"{diag['uow_rollback']} rollback(s)"
        )

    print(
        "[11/12] Validando rotativo pós-commit..."
    )

    rotativo_final = (
        TARGETS["rotativo.py"]["path"]
        .read_text(
            encoding="utf-8"
        )
    )

    if (
        "executar_orquestracao_rotativo("
        in rotativo_final
    ):

        for token in [
            "conn = uow.connection",
            "conn=conn",
            "uow.commit()",
        ]:

            if token not in rotativo_final:

                raise RuntimeError(
                    "Integração pós-commit ROTATIVO "
                    f"não preservada: {token}"
                )

        print(
            "      [OK] conexão UoW continua disponível "
            "para inteligência pós-commit."
        )

    else:

        print(
            "      [OK] router não possui inteligência "
            "pós-commit nesta versão."
        )

    print(
        "[12/12] Revalidando Fases 9A e 9B..."
    )

    for path, tokens in [
        (
            target_rodadas,
            [
                "SqlServerUnitOfWork",
                "uow.open()",
                "uow.commit()",
            ],
        ),
        (
            target_finalizacao,
            [
                "SqlServerUnitOfWork",
                "sys.sp_getapplock",
                "@LockOwner = 'Transaction'",
            ],
        ),
    ]:

        text = path.read_text(
            encoding="utf-8"
        )

        for token in tokens:

            if token not in text:

                raise RuntimeError(
                    "Regressão de fase anterior em "
                    f"{path}: {token}"
                )

    print(
        "      [OK] Fases 9A/9B preservadas."
    )

except Exception:

    print()
    print(
        "[ERRO] Falha durante Fase 9C."
    )

    print(
        "[INFO] Restaurando todos os routers alterados..."
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
    "[OK] Fase 9C aplicada."
)

print(
    "[OK] Núcleo operacional padronizado com "
    "SqlServerUnitOfWork."
)

print(
    "[OK] Commits e rollbacks preservados."
)

print(
    "[OK] Rotativo pós-commit preservado."
)

print(
    "[OK] Fases 9A e 9B preservadas."
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
