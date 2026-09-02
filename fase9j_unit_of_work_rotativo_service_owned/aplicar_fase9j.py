"""
FASE 9J - UoW NOS ROUTERS ROTATIVOS COM TRANSAÇÃO DELEGADA AO SERVICE

Arquivos:
- routers/rotativo_ciclos.py
- routers/rotativo_cobertura.py
- routers/rotativo_fluxo.py
- routers/rotativo_priorizacao.py

Regra:
- router NÃO assume commit/rollback;
- SqlServerUnitOfWork é somente adaptador de conexão/cursor;
- services continuam donos da transação quando aplicável.

Baseline comprovada pela Fase 9H do projeto:
- rotativo_ciclos.py      = 10 blocos
- rotativo_cobertura.py   = 1 bloco
- rotativo_fluxo.py       = 2 blocos
- rotativo_priorizacao.py = 1 bloco

Total = 14.

Execute na raiz do SGI:

python .\fase9j_unit_of_work_rotativo_service_owned\aplicar_fase9j.py
"""

from pathlib import Path
from datetime import datetime
import ast
import py_compile
import re
import shutil

ROOT = Path.cwd()

UOW_FILE = (
    ROOT
    / "infrastructure"
    / "database"
    / "unit_of_work.py"
)

TARGETS = {
    "rotativo_ciclos.py": {
        "path":
            ROOT / "routers" / "rotativo_ciclos.py",

        "expected_connections":
            10,

        "required_functions": {
            "criar_ciclo_rotativo",
            "obter_ciclo_atual",
            "obter_sugestoes_rotativo",
            "obter_painel_rotativo",
            "obter_tendencias_rotativo",
            "obter_tratativas_rotativo",
            "finalizar_ciclo",
            "resolver_tratativa_rotativo",
            "obter_contexto_localizacao_rotativo",
            "recalcular_inteligencia_rotativo",
        },
    },

    "rotativo_cobertura.py": {
        "path":
            ROOT / "routers" / "rotativo_cobertura.py",

        "expected_connections":
            1,

        "required_functions": {
            "concluir_localizacao_rotativo",
        },
    },

    "rotativo_fluxo.py": {
        "path":
            ROOT / "routers" / "rotativo_fluxo.py",

        "expected_connections":
            2,

        "required_functions": {
            "iniciar_localizacao",
            "ignorar_localizacao",
        },
    },

    "rotativo_priorizacao.py": {
        "path":
            ROOT / "routers" / "rotativo_priorizacao.py",

        "expected_connections":
            1,

        "required_functions": {
            "recalcular_priorizacao",
        },
    },
}

SERVICES_TO_PRESERVE = [
    ROOT / "services" / "ciclos_rotativo.py",
    ROOT / "services" / "rotativo_cobertura.py",
    ROOT / "services" / "rotativo_fluxo.py",
    ROOT / "services" / "rotativo_priorizacao.py",
    ROOT / "services" / "rotativo_tratativas.py",
]

PREVIOUS_UOW_FILES = [
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
    ROOT / "routers" / "analise.py",
]


def read_text(path):

    try:
        return path.read_text(
            encoding="utf-8"
        )
    except UnicodeDecodeError:
        return path.read_text(
            encoding="latin-1"
        )


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


def top_level_functions(text):

    tree = ast.parse(text)

    return {
        node.name
        for node in tree.body
        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        )
    }


def detectar_estado(
    text,
    expected_connections
):

    d = diagnostico(text)

    legado = (
        "from database import get_connection"
        in text

        and
        d["legacy_connections"]
        == expected_connections

        and
        d["legacy_commits"] == 0

        and
        d["legacy_rollbacks"] == 0

        and
        d["legacy_cursor_close"]
        == expected_connections

        and
        d["legacy_conn_close"]
        == expected_connections

        and
        d["legacy_conn_none"]
        == expected_connections

        and
        d["legacy_cursor_none"]
        == expected_connections
    )

    uow = (
        "SqlServerUnitOfWork"
        in text

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
        d["uow_ctor"]
        == expected_connections

        and
        d["uow_open"]
        == expected_connections

        and
        d["uow_commit"] == 0

        and
        d["uow_rollback"] == 0

        and
        d["uow_close"]
        == expected_connections

        and
        d["uow_conn_alias"]
        == expected_connections

        and
        d["uow_cursor"]
        == expected_connections
    )

    if legado:
        return "LEGADO", d

    if uow:
        return "UOW", d

    return "DESCONHECIDO", d


def validar_funcoes(
    name,
    text,
    config
):

    funcoes = top_level_functions(
        text
    )

    ausentes = sorted(
        config[
            "required_functions"
        ]
        - funcoes
    )

    if ausentes:

        raise RuntimeError(
            f"{name}: funções esperadas "
            f"ausentes: {ausentes}"
        )


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
        node.func.value.id
        == obj_name
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
        for node
        in ast.walk(stmt)
    )


def localizar_cleanup_finally(
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
    ) = localizar_cleanup_finally(
        text
    )

    if (
        len(cursor_stmts)
        != expected_connections
    ):

        raise RuntimeError(
            "cursor.close() em finally: "
            f"esperado="
            f"{expected_connections}, "
            f"encontrado="
            f"{len(cursor_stmts)}"
        )

    if (
        len(conn_stmts)
        != expected_connections
    ):

        raise RuntimeError(
            "conn.close() em finally: "
            f"esperado="
            f"{expected_connections}, "
            f"encontrado="
            f"{len(conn_stmts)}"
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
        key=lambda item: (
            item[0],
            item[1],
        )
    )

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

    def repl_init(
        match
    ):

        i = match.group(
            "i"
        )

        return (
            f"{i}uow = None\n"
            f"{i}conn = None\n"
            f"{i}cursor = None"
        )

    (
        text,
        count_init,
    ) = init_pattern.subn(
        repl_init,
        text,
    )

    if (
        count_init
        != expected_connections
    ):

        raise RuntimeError(
            "Blocos conn/cursor None: "
            f"esperado="
            f"{expected_connections}, "
            f"encontrado="
            f"{count_init}"
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

    def repl_open(
        match
    ):

        i = match.group(
            "i"
        )

        return (
            f"{i}uow = "
            "SqlServerUnitOfWork()\n"
            f"{i}uow.open()\n"
            f"{i}conn = "
            "uow.connection\n"
            f"{i}cursor = "
            "uow.cursor"
        )

    (
        text,
        count_open,
    ) = open_pattern.subn(
        repl_open,
        text,
    )

    if (
        count_open
        != expected_connections
    ):

        raise RuntimeError(
            "Aberturas conn/cursor: "
            f"esperado="
            f"{expected_connections}, "
            f"encontrado="
            f"{count_open}"
        )

    return text


def patch_legado(
    name,
    text,
    config
):

    expected = config[
        "expected_connections"
    ]

    state, before = (
        detectar_estado(
            text,
            expected,
        )
    )

    if state != "LEGADO":

        raise RuntimeError(
            f"{name}: patch solicitado "
            f"para estado {state}: "
            f"{before}"
        )

    ast.parse(text)

    validar_funcoes(
        name,
        text,
        config,
    )

    # Nenhum desses routers pode
    # ser dono do commit/rollback.
    if (
        "conn.commit()" in text
        or
        "conn.rollback()" in text
    ):

        raise RuntimeError(
            f"{name}: commit/rollback "
            "encontrado no router. "
            "A Fase 9J não pode mover "
            "essa fronteira automaticamente."
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
        expected,
    )

    patched = reescrever_cleanup(
        patched,
        expected,
    )

    state2, after = (
        detectar_estado(
            patched,
            expected,
        )
    )

    if state2 != "UOW":

        raise RuntimeError(
            f"{name}: estado pós-patch "
            f"inválido: {state2} / "
            f"{after}"
        )

    validar_funcoes(
        name,
        patched,
        config,
    )

    if (
        "uow.commit()" in patched
        or
        "uow.rollback()" in patched
    ):

        raise RuntimeError(
            f"{name}: UoW assumiu "
            "commit/rollback indevidamente."
        )

    return patched


# ============================================================
# PRÉ-REQUISITOS
# ============================================================

print(
    "[0/12] Validando Unit of Work..."
)

if not UOW_FILE.exists():

    raise SystemExit(
        f"[ERRO] UoW ausente: "
        f"{UOW_FILE}"
    )

uow_text = read_text(
    UOW_FILE
)

for token in [
    "class SqlServerUnitOfWork",
    "def open(",
    "def close(",
]:

    if token not in uow_text:

        raise SystemExit(
            f"[ERRO] UoW inválido: "
            f"{token}"
        )

if "self.commit()" in uow_text:

    raise SystemExit(
        "[ERRO] UoW possui "
        "auto-commit inesperado."
    )

print(
    "      [OK] UoW reconhecido."
)


print(
    "[1/12] Validando fases anteriores..."
)

for path in PREVIOUS_UOW_FILES:

    if not path.exists():

        raise SystemExit(
            "[ERRO] Fase anterior: "
            f"arquivo ausente {path}"
        )

    text = read_text(
        path
    )

    if (
        "SqlServerUnitOfWork"
        not in text
    ):

        raise SystemExit(
            "[ERRO] Fase anterior "
            "não reconhecida em "
            f"{path.name}"
        )

print(
    "      [OK] Fases anteriores "
    "reconhecidas."
)


# ============================================================
# SERVICES - APENAS BASELINE / NÃO SERÃO EDITADOS
# ============================================================

print(
    "[2/12] Registrando baseline dos services..."
)

service_baselines = {}

for path in SERVICES_TO_PRESERVE:

    if not path.exists():

        # Nem toda versão do SGI
        # precisa ter todos os services.
        print(
            f"      [INFO] ausente: "
            f"{path.name}"
        )

        continue

    text = read_text(
        path
    )

    service_baselines[
        str(path)
    ] = text

    commits = text.count(
        "conn.commit()"
    )

    rollbacks = text.count(
        "conn.rollback()"
    )

    print(
        f"      {path.name}: "
        f"{commits} commit(s) | "
        f"{rollbacks} rollback(s)"
    )


# ============================================================
# DETECTA TODOS ANTES DE ALTERAR
# ============================================================

print(
    "[3/12] Detectando estado dos 4 routers..."
)

states = {}

for name, config in TARGETS.items():

    path = config[
        "path"
    ]

    if not path.exists():

        raise SystemExit(
            f"[ERRO] Router ausente: "
            f"{path}"
        )

    text = read_text(
        path
    )

    try:
        ast.parse(text)
        validar_funcoes(
            name,
            text,
            config,
        )
    except Exception as exc:

        raise SystemExit(
            f"[ERRO] {name}: "
            f"{exc}"
        )

    expected = config[
        "expected_connections"
    ]

    state, d = (
        detectar_estado(
            text,
            expected,
        )
    )

    states[name] = {
        "state":
            state,

        "diag":
            d,

        "text":
            text,
    }

    print(
        f"      {name}: {state}"
    )

    print(
        "        conexões: "
        f"{d['legacy_connections'] or d['uow_ctor']}"
    )

    print(
        "        commit no router: "
        f"{d['legacy_commits'] or d['uow_commit']}"
    )

    print(
        "        rollback no router: "
        f"{d['legacy_rollbacks'] or d['uow_rollback']}"
    )


unknown = [
    name
    for name, data
    in states.items()
    if data["state"]
    == "DESCONHECIDO"
]

if unknown:

    print()
    print(
        "[ERRO] Estrutura "
        "desconhecida detectada."
    )

    print(
        "[INFO] Nenhum arquivo "
        "foi alterado."
    )

    for name in unknown:

        print(
            f"  {name}: "
            f"{states[name]['diag']}"
        )

    raise SystemExit(1)


# ============================================================
# GARANTE QUE OS ROUTERS NÃO CONTROLAM TRANSAÇÃO
# ============================================================

print(
    "[4/12] Validando ownership "
    "transacional dos routers..."
)

for name, data in states.items():

    text = data[
        "text"
    ]

    if (
        "conn.commit()" in text
        or
        "conn.rollback()" in text
        or
        "uow.commit()" in text
        or
        "uow.rollback()" in text
    ):

        raise SystemExit(
            "[ERRO] "
            f"{name} possui "
            "commit/rollback próprio. "
            "Nenhum arquivo foi alterado."
        )

    print(
        f"      [OK] {name}: "
        "0 commit / 0 rollback."
    )


# ============================================================
# BACKUPS
# ============================================================

timestamp = (
    datetime.now()
    .strftime(
        "%Y%m%d_%H%M%S"
    )
)

backups = {}

print(
    "[5/12] Criando backups "
    "dos routers legados..."
)

for name, data in states.items():

    if data["state"] != "LEGADO":

        print(
            f"      {name}: "
            "já usa UoW."
        )

        continue

    path = TARGETS[
        name
    ]["path"]

    backup = (
        path.parent
        /
        (
            path.stem
            + "_backup_fase9j_"
            + timestamp
            + ".py"
        )
    )

    shutil.copy2(
        path,
        backup,
    )

    backups[
        name
    ] = backup

    print(
        f"      {name} -> "
        f"{backup.name}"
    )


try:

    # ========================================================
    # APLICA
    # ========================================================

    print(
        "[6/12] Migrando "
        "rotativo_ciclos.py..."
    )

    name = "rotativo_ciclos.py"

    if (
        states[name]["state"]
        == "LEGADO"
    ):

        TARGETS[name][
            "path"
        ].write_text(
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
            "      [OK] já estava "
            "em UoW."
        )


    print(
        "[7/12] Migrando "
        "rotativo_cobertura.py..."
    )

    name = "rotativo_cobertura.py"

    if (
        states[name]["state"]
        == "LEGADO"
    ):

        TARGETS[name][
            "path"
        ].write_text(
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
            "      [OK] já estava "
            "em UoW."
        )


    print(
        "[8/12] Migrando "
        "rotativo_fluxo.py..."
    )

    name = "rotativo_fluxo.py"

    if (
        states[name]["state"]
        == "LEGADO"
    ):

        TARGETS[name][
            "path"
        ].write_text(
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
            "      [OK] já estava "
            "em UoW."
        )


    print(
        "[9/12] Migrando "
        "rotativo_priorizacao.py..."
    )

    name = "rotativo_priorizacao.py"

    if (
        states[name]["state"]
        == "LEGADO"
    ):

        TARGETS[name][
            "path"
        ].write_text(
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
            "      [OK] já estava "
            "em UoW."
        )


    # ========================================================
    # VALIDAÇÃO FINAL
    # ========================================================

    print(
        "[10/12] Validando "
        "sintaxe e fronteiras..."
    )

    total_uow = 0

    for name, config in (
        TARGETS.items()
    ):

        path = config[
            "path"
        ]

        py_compile.compile(
            str(path),
            doraise=True,
        )

        text = read_text(
            path
        )

        state, d = (
            detectar_estado(
                text,
                config[
                    "expected_connections"
                ],
            )
        )

        if state != "UOW":

            raise RuntimeError(
                f"{name}: "
                f"estado final "
                f"{state} / {d}"
            )

        validar_funcoes(
            name,
            text,
            config,
        )

        if (
            "uow.commit()" in text
            or
            "uow.rollback()" in text
            or
            "conn.commit()" in text
            or
            "conn.rollback()" in text
        ):

            raise RuntimeError(
                f"{name}: "
                "router assumiu "
                "ownership transacional."
            )

        total_uow += d[
            "uow_ctor"
        ]

        print(
            f"      [OK] {name}: "
            f"{d['uow_ctor']} UoW | "
            "0 commit/rollback."
        )


    if total_uow != 14:

        raise RuntimeError(
            "Total de UoW inesperado: "
            f"{total_uow} "
            "(esperado 14)."
        )

    print(
        "      [OK] total: "
        "14 blocos UoW."
    )


    print(
        "[11/12] Confirmando "
        "services intactos..."
    )

    for path_string, before_text in (
        service_baselines.items()
    ):

        path = Path(
            path_string
        )

        after_text = read_text(
            path
        )

        if after_text != before_text:

            raise RuntimeError(
                "Service foi alterado "
                "indevidamente: "
                f"{path}"
            )

        print(
            f"      [OK] "
            f"{path.name}"
        )


    print(
        "[12/12] Confirmando aliases "
        "para os services..."
    )

    for name, config in (
        TARGETS.items()
    ):

        text = read_text(
            config["path"]
        )

        expected = config[
            "expected_connections"
        ]

        if (
            text.count(
                "conn = uow.connection"
            )
            != expected
        ):

            raise RuntimeError(
                f"{name}: "
                "alias conn inválido."
            )

        if (
            text.count(
                "cursor = uow.cursor"
            )
            != expected
        ):

            raise RuntimeError(
                f"{name}: "
                "alias cursor inválido."
            )

        print(
            f"      [OK] {name}: "
            "conn/cursor fornecidos "
            "pelo UoW."
        )


except Exception:

    print()
    print(
        "[ERRO] Falha durante "
        "a Fase 9J."
    )

    print(
        "[INFO] Restaurando "
        "routers alterados..."
    )

    for name, backup in (
        backups.items()
    ):

        shutil.copy2(
            backup,
            TARGETS[name][
                "path"
            ],
        )

        print(
            f"      [OK] "
            f"restaurado: {name}"
        )

    raise


print()
print(
    "[OK] Fase 9J aplicada."
)

print(
    "[OK] 14 blocos de conexão "
    "migrados para UoW."
)

print(
    "[OK] Routers continuam "
    "com 0 commit/rollback."
)

print(
    "[OK] Services permaneceram "
    "inalterados."
)

print(
    "[OK] Ownership transacional "
    "delegado foi preservado."
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
    "3. Execute a auditoria 9H v2 "
    "(próxima etapa)."
)
