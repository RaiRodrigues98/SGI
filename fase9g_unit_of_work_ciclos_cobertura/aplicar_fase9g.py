"""
Fase 9G - UoW como adaptador de conexão em Ciclos/Cobertura ROTATIVO.

Importante:
- NÃO move commit/rollback dos services para o router.
- Apenas substitui get_connection/cursor/close por SqlServerUnitOfWork.
- Mantém conn = uow.connection e cursor = uow.cursor.
- Services continuam donos da transação.

Arquivos:
- routers/rotativo_ciclos.py
- routers/rotativo_cobertura.py

Execute:
python .\fase9g_unit_of_work_ciclos_cobertura\aplicar_fase9g.py
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

TARGETS = {
    "rotativo_ciclos.py": {
        "path": ROOT / "routers" / "rotativo_ciclos.py",
        "connections": 3,
        "tokens": [
            '"/ciclos"',
            '"/ciclos/atual"',
            "abrir_ciclo_rotativo(",
            "consultar_ciclo_atual(",
        ],
    },

    "rotativo_cobertura.py": {
        "path": ROOT / "routers" / "rotativo_cobertura.py",
        "connections": 1,
        "tokens": [
            '"/ciclos/localizacoes/concluir"',
            "registrar_conclusao_localizacao_rotativo(",
            "conn=conn",
            "cursor=cursor",
        ],
    },
}

SERVICES = {
    "ciclos_rotativo.py":
        ROOT / "services" / "ciclos_rotativo.py",

    "rotativo_cobertura.py":
        ROOT / "services" / "rotativo_cobertura.py",
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
    ROOT / "routers" / "escopo.py",
    ROOT / "routers" / "snapshot.py",
    ROOT / "routers" / "configuracoes_operacionais.py",
]


def diagnostico(text):

    return {
        "legacy_connections":
            text.count("get_connection()"),

        "legacy_commits":
            text.count("conn.commit()"),

        "legacy_rollbacks":
            text.count("conn.rollback()"),

        "legacy_cursor_close":
            text.count("cursor.close()"),

        "legacy_conn_close":
            text.count("conn.close()"),

        "legacy_conn_none":
            text.count("conn = None"),

        "legacy_cursor_none":
            text.count("cursor = None"),

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

        "uow_conn_alias":
            text.count("conn = uow.connection"),

        "uow_cursor":
            text.count("cursor = uow.cursor"),
    }


def detectar_estado(
    text,
    expected_connections
):

    d = diagnostico(text)

    legado = (
        "from database import get_connection" in text
        and
        d["legacy_connections"] == expected_connections
        and
        d["legacy_commits"] == 0
        and
        d["legacy_rollbacks"] == 0
        and
        d["legacy_cursor_close"] == expected_connections
        and
        d["legacy_conn_close"] == expected_connections
        and
        d["legacy_conn_none"] == expected_connections
        and
        d["legacy_cursor_none"] == expected_connections
    )

    uow = (
        "SqlServerUnitOfWork" in text
        and
        d["legacy_connections"] == 0
        and
        d["legacy_commits"] == 0
        and
        d["legacy_rollbacks"] == 0
        and
        d["legacy_cursor_close"] == 0
        and
        d["legacy_conn_close"] == 0
        and
        d["uow_ctor"] == expected_connections
        and
        d["uow_open"] == expected_connections
        and
        d["uow_commit"] == 0
        and
        d["uow_rollback"] == 0
        and
        d["uow_close"] == expected_connections
        and
        d["uow_conn_alias"] == expected_connections
        and
        d["uow_cursor"] == expected_connections
    )

    if legado:
        return "LEGADO", d

    if uow:
        return "UOW", d

    return "DESCONHECIDO", d


def is_close_call(
    node,
    obj_name
):

    return (
        isinstance(
            node,
            ast.Call
        )
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


def stmt_contains_close(
    stmt,
    obj_name
):

    return any(
        is_close_call(
            node,
            obj_name
        )
        for node in ast.walk(
            stmt
        )
    )


def localizar_cleanup(
    text
):

    tree = ast.parse(
        text
    )

    cursor_stmts = []
    conn_stmts = []

    for node in ast.walk(
        tree
    ):

        if not isinstance(
            node,
            ast.Try
        ):
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


def reescrever_cleanup(
    text,
    expected_connections
):

    (
        cursor_stmts,
        conn_stmts,
    ) = localizar_cleanup(
        text
    )

    if (
        len(cursor_stmts)
        != expected_connections
    ):

        raise RuntimeError(
            "cursor.close em finally: "
            f"esperado={expected_connections}, "
            f"encontrado={len(cursor_stmts)}"
        )

    if (
        len(conn_stmts)
        != expected_connections
    ):

        raise RuntimeError(
            "conn.close em finally: "
            f"esperado={expected_connections}, "
            f"encontrado={len(conn_stmts)}"
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
                -
                len(
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
        key=lambda x: (
            x[0],
            x[1],
        )
    )

    last_end = 0

    for start, end, _ in replacements:

        if start <= last_end:

            raise RuntimeError(
                "Statements de cleanup sobrepostos."
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

    result = "\n".join(
        out
    )

    if text.endswith("\n"):
        result += "\n"

    return result


def substituir_abertura(
    text,
    expected_connections
):

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

    if (
        count_init
        != expected_connections
    ):

        raise RuntimeError(
            "Blocos conn/cursor None: "
            f"esperado={expected_connections}, "
            f"encontrado={count_init}"
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

    if (
        count_open
        != expected_connections
    ):

        raise RuntimeError(
            "Aberturas conn/cursor: "
            f"esperado={expected_connections}, "
            f"encontrado={count_open}"
        )

    return text


def patch_legado(
    name,
    text,
    config
):

    state, d = detectar_estado(
        text,
        config["connections"],
    )

    if state != "LEGADO":

        raise RuntimeError(
            f"{name}: patch solicitado "
            f"para estado {state}: {d}"
        )

    for token in config["tokens"]:

        if token not in text:

            raise RuntimeError(
                f"{name}: contrato ausente: "
                f"{token}"
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

    patched = substituir_abertura(
        patched,
        config["connections"],
    )

    patched = reescrever_cleanup(
        patched,
        config["connections"],
    )

    state2, d2 = detectar_estado(
        patched,
        config["connections"],
    )

    if state2 != "UOW":

        raise RuntimeError(
            f"{name}: estado final inválido: "
            f"{state2} / {d2}"
        )

    for token in config["tokens"]:

        if token not in patched:

            raise RuntimeError(
                f"{name}: contrato perdido: "
                f"{token}"
            )

    # CRÍTICO:
    # router não assume a transação do service.
    if (
        "uow.commit()" in patched
        or
        "uow.rollback()" in patched
    ):

        raise RuntimeError(
            f"{name}: commit/rollback "
            "foi introduzido no router."
        )

    return patched


# ============================================================
# PRÉ-REQUISITOS
# ============================================================

print(
    "[0/10] Validando Unit of Work..."
)

if not target_uow.exists():

    raise SystemExit(
        f"[ERRO] UoW ausente: {target_uow}"
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
    "[1/10] Validando Fases 9A-9F..."
)

for path in PREVIOUS_PHASES:

    if not path.exists():

        raise SystemExit(
            "[ERRO] Fase anterior: "
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
            "[ERRO] Fase anterior "
            f"não reconhecida em {path.name}"
        )

print(
    "      [OK] Fases anteriores reconhecidas."
)


# ============================================================
# VALIDA OWNERSHIP NOS SERVICES
# ============================================================

print(
    "[2/10] Validando ownership transacional nos services..."
)

service_baselines = {}

for name, path in SERVICES.items():

    if not path.exists():

        raise SystemExit(
            f"[ERRO] Service ausente: {path}"
        )

    text = path.read_text(
        encoding="utf-8"
    )

    commits = text.count(
        "conn.commit()"
    )

    rollbacks = text.count(
        "conn.rollback()"
    )

    if (
        commits <= 0
        or
        rollbacks <= 0
    ):

        raise SystemExit(
            "[ERRO] Ownership transacional "
            f"não comprovado em {name}: "
            f"commit={commits}, "
            f"rollback={rollbacks}"
        )

    service_baselines[name] = {
        "text": text,
        "commits": commits,
        "rollbacks": rollbacks,
    }

    print(
        f"      [OK] {name}: "
        f"{commits} commit(s) | "
        f"{rollbacks} rollback(s)"
    )


# Cobertura precisa confirmar operação ANTES da inteligência.
coverage_service = (
    service_baselines[
        "rotativo_cobertura.py"
    ]["text"]
)

commit_pos = coverage_service.find(
    "conn.commit()"
)

intelligence_pos = coverage_service.find(
    "_executar_inteligencia_pos_conclusao(",
    commit_pos + 1,
)

if (
    commit_pos < 0
    or
    intelligence_pos < 0
    or
    intelligence_pos <= commit_pos
):

    raise SystemExit(
        "[ERRO] Não foi comprovada a ordem "
        "commit operacional -> inteligência "
        "em rotativo_cobertura.py."
    )

print(
    "      [OK] cobertura: "
    "commit operacional ocorre antes "
    "da inteligência pós-conclusão."
)


# ============================================================
# DETECTA ROUTERS ANTES DE ALTERAR
# ============================================================

print(
    "[3/10] Detectando estado dos routers..."
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
    except SyntaxError as exc:
        raise SystemExit(
            f"[ERRO] {name}: sintaxe inválida: {exc}"
        )

    for token in config["tokens"]:

        if token not in text:

            raise SystemExit(
                f"[ERRO] {name}: "
                f"contrato ausente: {token}"
            )

    state, d = detectar_estado(
        text,
        config["connections"],
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
        "        conexões: "
        f"{d['legacy_connections'] or d['uow_ctor']}"
    )

    print(
        "        commit no router: 0"
    )

    print(
        "        rollback no router: 0"
    )


unknown = [
    name
    for name, data in states.items()
    if data["state"] == "DESCONHECIDO"
]

if unknown:

    print()
    print(
        "[ERRO] Router em estrutura desconhecida."
    )

    print(
        "[INFO] Nenhum arquivo foi alterado."
    )

    for name in unknown:

        print(
            f"  {name}: {states[name]['diag']}"
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
    "[4/10] Criando backups dos routers legados..."
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
            + "_backup_fase9g_"
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
        "[5/10] Migrando rotativo_ciclos.py..."
    )

    name = "rotativo_ciclos.py"

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
        "[6/10] Migrando rotativo_cobertura.py..."
    )

    name = "rotativo_cobertura.py"

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
        "[7/10] Validando sintaxe e ownership dos routers..."
    )

    for name, config in TARGETS.items():

        path = config["path"]

        py_compile.compile(
            str(path),
            doraise=True,
        )

        text = path.read_text(
            encoding="utf-8"
        )

        state, d = detectar_estado(
            text,
            config["connections"],
        )

        if state != "UOW":

            raise RuntimeError(
                f"{name}: estado final "
                f"{state} / {d}"
            )

        if (
            "uow.commit()" in text
            or
            "uow.rollback()" in text
        ):

            raise RuntimeError(
                f"{name}: router assumiu "
                "commit/rollback indevidamente."
            )

        print(
            f"      [OK] {name}: "
            f"{config['connections']} UoW, "
            "0 commit/rollback no router."
        )


    print(
        "[8/10] Revalidando services intactos..."
    )

    for name, path in SERVICES.items():

        text = path.read_text(
            encoding="utf-8"
        )

        baseline = (
            service_baselines[name]
        )

        if (
            text.count("conn.commit()")
            != baseline["commits"]
        ):

            raise RuntimeError(
                f"{name}: commits do service mudaram."
            )

        if (
            text.count("conn.rollback()")
            != baseline["rollbacks"]
        ):

            raise RuntimeError(
                f"{name}: rollbacks do service mudaram."
            )

        print(
            f"      [OK] {name}: "
            "ownership transacional preservado."
        )


    print(
        "[9/10] Validando aliases conn/cursor..."
    )

    for name, config in TARGETS.items():

        text = config["path"].read_text(
            encoding="utf-8"
        )

        if (
            text.count(
                "conn = uow.connection"
            )
            != config["connections"]
        ):

            raise RuntimeError(
                f"{name}: alias conn inválido."
            )

        if (
            text.count(
                "cursor = uow.cursor"
            )
            != config["connections"]
        ):

            raise RuntimeError(
                f"{name}: alias cursor inválido."
            )

        print(
            f"      [OK] {name}: "
            "services recebem conexão/cursor do UoW."
        )


    print(
        "[10/10] Revalidando Fases 9A-9F..."
    )

    for path in PREVIOUS_PHASES:

        text = path.read_text(
            encoding="utf-8"
        )

        if (
            "SqlServerUnitOfWork"
            not in text
        ):

            raise RuntimeError(
                "Regressão de fase anterior em "
                f"{path.name}"
            )

    print(
        "      [OK] fases anteriores preservadas."
    )


except Exception:

    print()
    print(
        "[ERRO] Falha durante Fase 9G."
    )

    print(
        "[INFO] Restaurando routers alterados..."
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
    "[OK] Fase 9G aplicada."
)

print(
    "[OK] Ciclos/Cobertura usam UoW para conexão/cursor."
)

print(
    "[OK] Commit/rollback continuam nos services."
)

print(
    "[OK] Cobertura mantém commit antes da inteligência."
)

print(
    "[OK] Fases 9A-9F preservadas."
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
