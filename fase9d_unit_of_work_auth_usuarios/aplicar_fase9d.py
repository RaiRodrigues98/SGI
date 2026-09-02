"""
Fase 9D - Unit of Work em auth.py e usuarios.py.

Pré-requisitos:
- Fase 9A aplicada;
- Fase 9B aplicada;
- Fase 9C aplicada.

Execute na raiz do SGI:

python .\fase9d_unit_of_work_auth_usuarios\aplicar_fase9d.py
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

target_auth = ROOT / "routers" / "auth.py"
target_users = ROOT / "routers" / "usuarios.py"

phase9a_router = ROOT / "routers" / "rodadas.py"
phase9b_router = ROOT / "routers" / "finalizacao.py"

phase9c_routers = [
    ROOT / "routers" / "inventarios.py",
    ROOT / "routers" / "rotativo.py",
    ROOT / "routers" / "gestor.py",
    ROOT / "routers" / "encaminhamento_gestor.py",
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

        "uow_ctor":
            text.count("SqlServerUnitOfWork()"),

        "uow_open":
            text.count("uow.open()"),

        "uow_commits":
            text.count("uow.commit()"),

        "uow_rollbacks":
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
    expected_connections,
    expected_commits,
    expected_rollbacks,
):

    d = diagnostico(text)

    legacy = (
        "from database import get_connection" in text
        and
        d["legacy_connections"] == expected_connections
        and
        d["legacy_commits"] == expected_commits
        and
        d["legacy_rollbacks"] == expected_rollbacks
        and
        d["legacy_cursor_close"] == expected_connections
        and
        d["legacy_conn_close"] == expected_connections
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
        d["uow_commits"] == expected_commits
        and
        d["uow_rollbacks"] == expected_rollbacks
        and
        d["uow_close"] == expected_connections
        and
        d["uow_conn_alias"] == expected_connections
        and
        d["uow_cursor"] == expected_connections
    )

    if legacy:
        return "LEGADO", d

    if uow:
        return "UOW", d

    return "DESCONHECIDO", d


def patch_legacy(
    text,
    expected_connections,
    expected_commits,
    expected_rollbacks,
):

    estado, before = detectar_estado(
        text,
        expected_connections,
        expected_commits,
        expected_rollbacks,
    )

    if estado != "LEGADO":
        raise RuntimeError(
            "Patch solicitado para estado "
            f"{estado}: {before}"
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

    if patched.count(old_finally) != expected_connections:
        raise RuntimeError(
            "Quantidade de blocos finally inesperada: "
            f"{patched.count(old_finally)}"
        )

    patched = patched.replace(
        old_finally,
        (
            "        if uow:\n"
            "            uow.close()"
        ),
    )

    ast.parse(patched)

    final_estado, after = detectar_estado(
        patched,
        expected_connections,
        expected_commits,
        expected_rollbacks,
    )

    if final_estado != "UOW":
        raise RuntimeError(
            "Estado pós-patch inválido: "
            f"{final_estado} / {after}"
        )

    return patched


def function_map(text):

    tree = ast.parse(text)
    lines = text.splitlines()

    result = {}

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

        result[node.name] = {
            "uow_commit":
                segment.count(
                    "uow.commit()"
                ),

            "legacy_commit":
                segment.count(
                    "conn.commit()"
                ),

            "uow_rollback":
                segment.count(
                    "uow.rollback()"
                ),

            "legacy_rollback":
                segment.count(
                    "conn.rollback()"
                ),
        }

    return result


def validar_tokens(
    filename,
    text,
    tokens,
):

    missing = [
        token
        for token in tokens
        if token not in text
    ]

    if missing:
        raise RuntimeError(
            f"{filename}: invariantes ausentes: {missing}"
        )


# ============================================================
# PRÉ-REQUISITOS
# ============================================================

print(
    "[0/12] Validando arquivos necessários..."
)

required = [
    target_uow,
    target_auth,
    target_users,
    phase9a_router,
    phase9b_router,
    *phase9c_routers,
]

for file in required:

    if not file.exists():

        raise SystemExit(
            f"[ERRO] Arquivo necessário ausente: {file}"
        )


print(
    "[1/12] Validando SqlServerUnitOfWork..."
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
            "[ERRO] Unit of Work inválido: "
            f"{token}"
        )

if "self.commit()" in uow_text:

    raise SystemExit(
        "[ERRO] UoW possui auto-commit inesperado."
    )

print(
    "      [OK] UoW reconhecido."
)


print(
    "[2/12] Validando Fases 9A/9B/9C..."
)

checks = [
    (
        phase9a_router,
        [
            "SqlServerUnitOfWork",
            "uow.open()",
            "uow.commit()",
        ],
    ),
    (
        phase9b_router,
        [
            "SqlServerUnitOfWork",
            "sys.sp_getapplock",
            "@LockOwner = 'Transaction'",
        ],
    ),
]

for path in phase9c_routers:

    checks.append(
        (
            path,
            [
                "SqlServerUnitOfWork",
                "uow.open()",
                "uow.commit()",
            ],
        )
    )

for path, tokens in checks:

    content = path.read_text(
        encoding="utf-8"
    )

    for token in tokens:

        if token not in content:

            raise SystemExit(
                "[ERRO] Fase anterior não identificada "
                f"em {path.name}: {token}"
            )

print(
    "      [OK] Fases anteriores reconhecidas."
)


# ============================================================
# DETECTA AUTH / USUARIOS
# ============================================================

print(
    "[3/12] Detectando estado de auth.py..."
)

auth_text = target_auth.read_text(
    encoding="utf-8"
)

try:
    ast.parse(auth_text)

    validar_tokens(
        "auth.py",
        auth_text,
        [
            '"/login"',
            "autenticar_usuario(",
            "gerar_access_token(",
            "registrar_ultimo_login(",
        ],
    )
except Exception as exc:

    raise SystemExit(
        f"[ERRO] auth.py inválido: {exc}"
    )

auth_state, auth_diag = detectar_estado(
    auth_text,
    expected_connections=1,
    expected_commits=1,
    expected_rollbacks=2,
)

print(
    f"      Estado: {auth_state}"
)

print(
    f"      Commit: "
    f"{auth_diag['legacy_commits'] or auth_diag['uow_commits']} | "
    f"Rollbacks: "
    f"{auth_diag['legacy_rollbacks'] or auth_diag['uow_rollbacks']}"
)


print(
    "[4/12] Detectando estado de usuarios.py..."
)

users_text = target_users.read_text(
    encoding="utf-8"
)

try:
    ast.parse(users_text)

    validar_tokens(
        "usuarios.py",
        users_text,
        [
            '"USUARIO_GERENCIAR"',
            "criar_usuario(",
            "listar_usuarios(",
            "consultar_usuario(",
            "atualizar_usuario(",
            "alterar_senha_usuario(",
            "listar_perfis_usuario(",
            "vincular_perfil_usuario(",
            "remover_perfil_usuario(",
            "listar_permissoes_usuario(",
        ],
    )
except Exception as exc:

    raise SystemExit(
        f"[ERRO] usuarios.py inválido: {exc}"
    )

users_state, users_diag = detectar_estado(
    users_text,
    expected_connections=9,
    expected_commits=5,
    expected_rollbacks=10,
)

print(
    f"      Estado: {users_state}"
)

print(
    "      9 conexões | 5 commits | "
    "10 caminhos de rollback esperados."
)


if (
    auth_state == "DESCONHECIDO"
    or
    users_state == "DESCONHECIDO"
):

    print()
    print(
        "[ERRO] Estrutura não reconhecida."
    )

    print(
        "[INFO] Nenhum arquivo foi alterado."
    )

    print()
    print(
        "AUTH:"
    )

    for key, value in auth_diag.items():
        print(
            f"  {key}: {value}"
        )

    print()
    print(
        "USUARIOS:"
    )

    for key, value in users_diag.items():
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
    "[5/12] Criando backups necessários..."
)

if auth_state == "LEGADO":

    backup = (
        target_auth.parent
        / f"auth_backup_fase9d_{timestamp}.py"
    )

    shutil.copy2(
        target_auth,
        backup,
    )

    backups["auth"] = backup

    print(
        f"      auth.py -> {backup.name}"
    )

else:

    print(
        "      auth.py já usa UoW."
    )


if users_state == "LEGADO":

    backup = (
        target_users.parent
        / f"usuarios_backup_fase9d_{timestamp}.py"
    )

    shutil.copy2(
        target_users,
        backup,
    )

    backups["users"] = backup

    print(
        f"      usuarios.py -> {backup.name}"
    )

else:

    print(
        "      usuarios.py já usa UoW."
    )


# ============================================================
# APLICA
# ============================================================

try:

    print(
        "[6/12] Migrando auth.py..."
    )

    if auth_state == "LEGADO":

        target_auth.write_text(
            patch_legacy(
                auth_text,
                expected_connections=1,
                expected_commits=1,
                expected_rollbacks=2,
            ),
            encoding="utf-8",
        )

        print(
            "      [OK] migrado."
        )

    else:

        print(
            "      [OK] já estava migrado."
        )


    print(
        "[7/12] Migrando usuarios.py..."
    )

    if users_state == "LEGADO":

        target_users.write_text(
            patch_legacy(
                users_text,
                expected_connections=9,
                expected_commits=5,
                expected_rollbacks=10,
            ),
            encoding="utf-8",
        )

        print(
            "      [OK] migrado."
        )

    else:

        print(
            "      [OK] já estava migrado."
        )


    print(
        "[8/12] Validando sintaxe..."
    )

    for path in [
        target_auth,
        target_users,
    ]:

        py_compile.compile(
            str(path),
            doraise=True,
        )

        print(
            f"      [OK] {path.name}"
        )


    print(
        "[9/12] Validando login..."
    )

    auth_final = target_auth.read_text(
        encoding="utf-8"
    )

    final_auth_state, final_auth_diag = (
        detectar_estado(
            auth_final,
            expected_connections=1,
            expected_commits=1,
            expected_rollbacks=2,
        )
    )

    if final_auth_state != "UOW":

        raise RuntimeError(
            "auth.py não terminou em UOW: "
            f"{final_auth_state} / {final_auth_diag}"
        )

    auth_functions = function_map(
        auth_final
    )

    if (
        auth_functions["login"]["uow_commit"]
        != 1
    ):

        raise RuntimeError(
            "Login perdeu commit de UltimoLogin."
        )

    print(
        "      [OK] autenticação + UltimoLogin "
        "continuam na mesma transação."
    )


    print(
        "[10/12] Validando rotas de escrita de usuários..."
    )

    users_final = target_users.read_text(
        encoding="utf-8"
    )

    final_users_state, final_users_diag = (
        detectar_estado(
            users_final,
            expected_connections=9,
            expected_commits=5,
            expected_rollbacks=10,
        )
    )

    if final_users_state != "UOW":

        raise RuntimeError(
            "usuarios.py não terminou em UOW: "
            f"{final_users_state} / {final_users_diag}"
        )

    users_functions = function_map(
        users_final
    )

    write_functions = [
        "criar",
        "atualizar",
        "alterar_senha",
        "vincular_perfil",
        "remover_perfil",
    ]

    for function_name in write_functions:

        info = users_functions[
            function_name
        ]

        if info["uow_commit"] != 1:

            raise RuntimeError(
                f"{function_name}: commit inválido."
            )

        if info["uow_rollback"] != 2:

            raise RuntimeError(
                f"{function_name}: esperado 2 rollbacks, "
                f"encontrado {info['uow_rollback']}."
            )

        print(
            f"      [OK] {function_name}: "
            "1 commit / 2 rollbacks."
        )


    print(
        "[11/12] Validando rotas somente leitura..."
    )

    read_functions = [
        "listar",
        "consultar",
        "listar_perfis",
        "listar_permissoes",
    ]

    for function_name in read_functions:

        info = users_functions[
            function_name
        ]

        if info["uow_commit"] != 0:

            raise RuntimeError(
                f"{function_name}: commit foi introduzido "
                "em rota de leitura."
            )

        if info["uow_rollback"] != 0:

            raise RuntimeError(
                f"{function_name}: rollback foi introduzido "
                "em rota de leitura."
            )

        print(
            f"      [OK] {function_name}: "
            "sem commit/rollback."
        )


    print(
        "[12/12] Revalidando fases anteriores..."
    )

    for path, tokens in checks:

        content = path.read_text(
            encoding="utf-8"
        )

        for token in tokens:

            if token not in content:

                raise RuntimeError(
                    "Regressão de fase anterior em "
                    f"{path.name}: {token}"
                )

    print(
        "      [OK] Fases 9A/9B/9C preservadas."
    )


except Exception:

    print()
    print(
        "[ERRO] Falha durante a Fase 9D."
    )

    print(
        "[INFO] Restaurando arquivos alterados..."
    )

    if "auth" in backups:

        shutil.copy2(
            backups["auth"],
            target_auth,
        )

        print(
            "      [OK] auth.py restaurado."
        )

    if "users" in backups:

        shutil.copy2(
            backups["users"],
            target_users,
        )

        print(
            "      [OK] usuarios.py restaurado."
        )

    raise


print()
print(
    "[OK] Fase 9D aplicada."
)

print(
    "[OK] auth.py padronizado com UoW."
)

print(
    "[OK] usuarios.py padronizado com UoW."
)

print(
    "[OK] 5 rotas de escrita preservadas."
)

print(
    "[OK] 4 rotas de leitura continuam sem commit."
)

print(
    "[OK] Fases 9A/9B/9C preservadas."
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
