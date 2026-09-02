"""
Fase 9A - Unit of Work do router de Rodadas.

Pré-requisito:
- Fase 8D instalada e aprovada.

Execute na raiz do SGI:

python .\fase9a_unit_of_work_rodadas\aplicar_fase9a.py
"""

from pathlib import Path
from datetime import datetime
import ast
import py_compile
import shutil

ROOT = Path.cwd()
PAYLOAD = Path(__file__).resolve().parent

target_router = (
    ROOT / "routers" / "rodadas.py"
)

target_services = (
    ROOT / "services" / "rodadas"
)

target_uow = (
    ROOT
    / "infrastructure"
    / "database"
    / "unit_of_work.py"
)

print(
    "[0/10] Validando baseline da Fase 8D..."
)

required = [
    target_router,
    ROOT / "services" / "rodadas_service.py",
    target_services / "criacao.py",
    target_services / "preview.py",
    target_services / "finalizacao_rotativo.py",
    target_services / "repositories" / "inventario_repository.py",
    target_services / "repositories" / "rodada_repository.py",
    target_services / "repositories" / "sessao_repository.py",
    target_services / "repositories" / "item_repository.py",
    target_services / "repositories" / "localizacao_repository.py",
]

for file in required:

    if not file.exists():

        raise SystemExit(
            "[ERRO] Baseline incompleta: "
            f"{file}"
        )

creation = (
    target_services
    / "criacao.py"
).read_text(
    encoding="utf-8"
)

for token in [
    "sys.sp_getapplock",
    "SGI:ROTATIVO:PROXIMA_RODADA",
    "@LockOwner = 'Transaction'",
]:

    if token not in creation:

        raise SystemExit(
            "[ERRO] Proteção de concorrência "
            f"ausente: {token}"
        )

# A Fase 8D não deve ter commit/rollback nos services.
for file in target_services.rglob("*.py"):

    text = file.read_text(
        encoding="utf-8"
    )

    if (
        ".commit(" in text
        or ".rollback(" in text
    ):

        raise SystemExit(
            "[ERRO] Ownership transacional inesperado "
            f"em {file}"
        )

router_text = target_router.read_text(
    encoding="utf-8"
)

expected_counts = {
    "get_connection()": 6,
    "conn.commit()": 2,
    "conn.rollback()": 4,
    "cursor.close()": 6,
    "conn.close()": 6,
    "conn = None": 6,
    "cursor = None": 6,
}

for token, expected in expected_counts.items():

    actual = router_text.count(token)

    if actual != expected:

        raise SystemExit(
            "[ERRO] routers/rodadas.py não corresponde "
            "à baseline esperada. "
            f"{token}: esperado={expected}, atual={actual}"
        )

for token in [
    "from database import get_connection",
    '"RODADA_GERAR"',
    '"ANALISE_VISUALIZAR"',
    "criar_proxima_rodada(",
    "visualizar_proxima_rodada(",
]:

    if token not in router_text:

        raise SystemExit(
            "[ERRO] Router incompatível. "
            f"Ausente: {token}"
        )

print(
    "      [OK] Fase 8D / router identificados."
)

timestamp = datetime.now().strftime(
    "%Y%m%d_%H%M%S"
)

backup_router = (
    ROOT
    / "routers"
    / f"rodadas_backup_fase9a_{timestamp}.py"
)

backup_uow = None

print(
    "[1/10] Criando backup de routers/rodadas.py..."
)

shutil.copy2(
    target_router,
    backup_router,
)

print(
    f"      {backup_router}"
)

if target_uow.exists():

    backup_uow = (
        target_uow.parent
        / f"unit_of_work_backup_fase9a_{timestamp}.py"
    )

    print(
        "[2/10] UnitOfWork existente: criando backup..."
    )

    shutil.copy2(
        target_uow,
        backup_uow,
    )

    print(
        f"      {backup_uow}"
    )

else:

    print(
        "[2/10] Nenhum UnitOfWork anterior encontrado."
    )


def patch_router(text: str) -> str:

    patched = text

    patched = patched.replace(
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
    )

    patched = patched.replace(
        "        conn = get_connection()\n"
        "        cursor = conn.cursor()",
        (
            "        uow = SqlServerUnitOfWork()\n"
            "        uow.open()\n"
            "        cursor = uow.cursor"
        ),
    )

    patched = patched.replace(
        "        conn.commit()",
        "        uow.commit()",
    )

    patched = patched.replace(
        "        if conn:\n"
        "            conn.rollback()",
        (
            "        if uow:\n"
            "            uow.rollback()"
        ),
    )

    old_finally = (
        "        if cursor:\n"
        "            cursor.close()\n\n"
        "        if conn:\n"
        "            conn.close()"
    )

    if patched.count(
        old_finally
    ) != 6:

        raise RuntimeError(
            "Blocos finally esperados não encontrados."
        )

    patched = patched.replace(
        old_finally,
        (
            "        if uow:\n"
            "            uow.close()"
        ),
    )

    return patched


try:

    print(
        "[3/10] Criando infrastructure/database..."
    )

    infra_root = (
        ROOT / "infrastructure"
    )

    infra_db = (
        infra_root / "database"
    )

    infra_db.mkdir(
        parents=True,
        exist_ok=True,
    )

    infra_init = (
        infra_root / "__init__.py"
    )

    db_init = (
        infra_db / "__init__.py"
    )

    # Não sobrescreve __init__.py já existente.
    if not infra_init.exists():

        infra_init.write_text(
            '"""Infraestrutura do SGI."""\n',
            encoding="utf-8",
        )

    if not db_init.exists():

        db_init.write_text(
            '"""Infraestrutura de banco de dados."""\n',
            encoding="utf-8",
        )

    print(
        "[4/10] Instalando unit_of_work.py..."
    )

    shutil.copy2(
        PAYLOAD
        / "infrastructure"
        / "database"
        / "unit_of_work.py",
        target_uow,
    )

    print(
        "[5/10] Aplicando Unit of Work ao router..."
    )

    current = target_router.read_text(
        encoding="utf-8"
    )

    patched = patch_router(
        current
    )

    target_router.write_text(
        patched,
        encoding="utf-8",
    )

    print(
        "[6/10] Validando sintaxe..."
    )

    py_compile.compile(
        str(target_uow),
        doraise=True,
    )

    py_compile.compile(
        str(target_router),
        doraise=True,
    )

    print(
        "      [OK] infrastructure/database/unit_of_work.py"
    )

    print(
        "      [OK] routers/rodadas.py"
    )

    print(
        "[7/10] Validando ownership transacional..."
    )

    final_router = target_router.read_text(
        encoding="utf-8"
    )

    forbidden = [
        "from database import get_connection",
        "get_connection()",
        "conn.commit()",
        "conn.rollback()",
        "cursor.close()",
        "conn.close()",
    ]

    for token in forbidden:

        if token in final_router:

            raise RuntimeError(
                "Ownership antigo permaneceu no router: "
                f"{token}"
            )

    expected_after = {
        "SqlServerUnitOfWork()": 6,
        "uow.open()": 6,
        "uow.commit()": 2,
        "uow.rollback()": 4,
        "uow.close()": 6,
        "cursor = uow.cursor": 6,
    }

    for token, expected in expected_after.items():

        actual = final_router.count(
            token
        )

        if actual != expected:

            raise RuntimeError(
                "Contagem UoW inválida: "
                f"{token} esperado={expected}, atual={actual}"
            )

    print(
        "      [OK] router controla decisão commit/rollback."
    )

    print(
        "      [OK] UoW controla conexão/cursor."
    )

    print(
        "[8/10] Validando contratos HTTP/RBAC..."
    )

    for token in [
        '"/inventarios/{id_inventario}/rodadas/proxima"',
        '"/inventarios/{id_inventario}/comparativo-rodadas"',
        '"/rodadas/{id_rodada}/sincronizar-localizacoes"',
        '"/rodadas/{id_rodada}/analise-recontagem"',
        '"/inventarios/{id_inventario}/analise-gestor"',
        '"/inventarios/{id_inventario}/rodadas/proxima-preview"',
        '"RODADA_GERAR"',
        '"ANALISE_VISUALIZAR"',
        "criar_proxima_rodada(",
        "sincronizar_localizacoes_recontagem(",
        "visualizar_proxima_rodada(",
    ]:

        if token not in final_router:

            raise RuntimeError(
                "Contrato/RBAC perdido: "
                f"{token}"
            )

    print(
        "      [OK] rotas e permissões preservadas."
    )

    print(
        "[9/10] Validando sp_getapplock..."
    )

    creation = (
        target_services
        / "criacao.py"
    ).read_text(
        encoding="utf-8"
    )

    for token in [
        "sys.sp_getapplock",
        "SGI:ROTATIVO:PROXIMA_RODADA",
        "@LockOwner = 'Transaction'",
    ]:

        if token not in creation:

            raise RuntimeError(
                "Concorrência perdida: "
                f"{token}"
            )

    print(
        "      [OK] lock transacional preservado."
    )

    print(
        "[10/10] Validando services sem commit/rollback..."
    )

    for file in target_services.rglob("*.py"):

        text = file.read_text(
            encoding="utf-8"
        )

        if (
            ".commit(" in text
            or ".rollback(" in text
        ):

            raise RuntimeError(
                "Commit/rollback vazou para services: "
                f"{file}"
            )

    print(
        "      [OK] services continuam transação-agnósticos."
    )

except Exception:

    print()

    print(
        "[ERRO] Falha. Restaurando estado anterior..."
    )

    shutil.copy2(
        backup_router,
        target_router,
    )

    if backup_uow is not None:

        shutil.copy2(
            backup_uow,
            target_uow,
        )

    elif target_uow.exists():

        target_uow.unlink()

    print(
        "[OK] Router restaurado."
    )

    raise


print()

print(
    "[OK] Fase 9A aplicada."
)

print(
    "[OK] Unit of Work instalado."
)

print(
    "[OK] Fronteira transacional preservada."
)

print(
    "[OK] Commit/rollback continuam decididos pelo router."
)

print(
    "[OK] sp_getapplock continua preso à mesma transação."
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
