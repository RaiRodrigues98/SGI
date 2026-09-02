"""
Fase 8B - Repository de SessoesContagem e read model ROTATIVO.

Pré-requisito:
- Fase 8A instalada.

Execute na raiz do SGI:

python .\fase8b_repository_sessoes\aplicar_fase8b.py
"""

from pathlib import Path
from datetime import datetime
import builtins
import py_compile
import shutil
import symtable

ROOT = Path.cwd()

PAYLOAD = (
    Path(__file__).resolve().parent
    / "services"
)

target_service = (
    ROOT
    / "services"
    / "rodadas_service.py"
)

target_pkg = (
    ROOT
    / "services"
    / "rodadas"
)

target_repos = (
    target_pkg
    / "repositories"
)

print(
    "[0/10] Validando baseline da Fase 8A..."
)

required = [
    target_service,
    target_pkg / "__init__.py",
    target_pkg / "itens.py",
    target_pkg / "localizacoes.py",
    target_pkg / "candidatos_rotativo.py",
    target_pkg / "candidatos_oficial.py",
    target_pkg / "gestor.py",
    target_pkg / "lifecycle.py",
    target_pkg / "finalizacao_rotativo.py",
    target_pkg / "preview.py",
    target_pkg / "criacao.py",
    target_repos / "__init__.py",
    target_repos / "rodada_repository.py",
]

for file in required:

    if not file.exists():

        raise SystemExit(
            "[ERRO] Baseline da Fase 8A incompleta: "
            f"{file}"
        )

current_creation = (
    target_pkg / "criacao.py"
).read_text(
    encoding="utf-8"
)

current_repo = (
    target_repos
    / "rodada_repository.py"
).read_text(
    encoding="utf-8"
)

for text in [
    "from services.rodadas.repositories.rodada_repository import",
    "sys.sp_getapplock",
    "SGI:ROTATIVO:PROXIMA_RODADA",
]:

    if text not in current_creation:

        raise SystemExit(
            "[ERRO] criacao.py não corresponde "
            "à Fase 8A. Ausente: "
            f"{text}"
        )

for text in [
    "INSERT INTO dbo.RodadasInventario",
    "UPDATE dbo.RodadasInventario",
]:

    if text not in current_repo:

        raise SystemExit(
            "[ERRO] rodada_repository.py não corresponde "
            "à Fase 8A. Ausente: "
            f"{text}"
        )

print(
    "      [OK] Fase 8A identificada."
)

timestamp = datetime.now().strftime(
    "%Y%m%d_%H%M%S"
)

backup_service = (
    ROOT
    / "services"
    / (
        "rodadas_service_backup_fase8b_"
        f"{timestamp}.py"
    )
)

backup_pkg = (
    ROOT
    / "services"
    / (
        "rodadas_backup_fase8b_"
        f"{timestamp}"
    )
)

print(
    "[1/10] Criando backup do rodadas_service.py..."
)

shutil.copy2(
    target_service,
    backup_service,
)

print(
    f"      {backup_service}"
)

print(
    "[2/10] Criando backup de services/rodadas..."
)

if backup_pkg.exists():
    shutil.rmtree(
        backup_pkg
    )

shutil.copytree(
    target_pkg,
    backup_pkg,
)

print(
    f"      {backup_pkg}"
)


def unresolved_globals(
    module_source: str
):

    st = symtable.symtable(
        module_source,
        "module.py",
        "exec",
    )

    bound = set()

    for symbol in st.get_symbols():

        if (
            symbol.is_imported()
            or symbol.is_assigned()
            or symbol.is_namespace()
            or symbol.is_parameter()
        ):

            bound.add(
                symbol.get_name()
            )

    builtin_names = set(
        dir(builtins)
    )

    result = {}

    def walk(table):

        for child in table.get_children():

            if (
                child.get_type()
                == "function"
            ):

                refs = {
                    symbol.get_name()
                    for symbol
                    in child.get_symbols()
                    if (
                        symbol.is_global()
                        and symbol.is_referenced()
                    )
                }

                missing = sorted(
                    refs
                    - bound
                    - builtin_names
                )

                if missing:

                    result[
                        child.get_name()
                    ] = missing

            walk(
                child
            )

    walk(
        st
    )

    return result


try:

    print(
        "[3/10] Instalando sessao_repository.py..."
    )

    shutil.copy2(
        PAYLOAD
        / "rodadas"
        / "repositories"
        / "sessao_repository.py",
        target_repos
        / "sessao_repository.py",
    )

    print(
        "[4/10] Instalando divergencia_rotativo_repository.py..."
    )

    shutil.copy2(
        PAYLOAD
        / "rodadas"
        / "repositories"
        / "divergencia_rotativo_repository.py",
        target_repos
        / "divergencia_rotativo_repository.py",
    )

    print(
        "[5/10] Atualizando criacao.py..."
    )

    shutil.copy2(
        PAYLOAD
        / "rodadas"
        / "criacao.py",
        target_pkg
        / "criacao.py",
    )

    print(
        "[6/10] Atualizando finalizacao_rotativo.py..."
    )

    shutil.copy2(
        PAYLOAD
        / "rodadas"
        / "finalizacao_rotativo.py",
        target_pkg
        / "finalizacao_rotativo.py",
    )

    print(
        "[7/10] Atualizando preview.py..."
    )

    shutil.copy2(
        PAYLOAD
        / "rodadas"
        / "preview.py",
        target_pkg
        / "preview.py",
    )

    print(
        "[8/10] Atualizando localizacoes.py..."
    )

    shutil.copy2(
        PAYLOAD
        / "rodadas"
        / "localizacoes.py",
        target_pkg
        / "localizacoes.py",
    )

    print(
        "[9/10] Atualizando candidatos_rotativo.py..."
    )

    shutil.copy2(
        PAYLOAD
        / "rodadas"
        / "candidatos_rotativo.py",
        target_pkg
        / "candidatos_rotativo.py",
    )

    print(
        "[10/10] Validando arquitetura e sintaxe..."
    )

    files = [
        target_service,
        *sorted(
            target_pkg.glob("*.py")
        ),
        *sorted(
            target_repos.glob("*.py")
        ),
    ]

    unresolved_all = {}

    for file in files:

        py_compile.compile(
            str(file),
            doraise=True,
        )

        unresolved = (
            unresolved_globals(
                file.read_text(
                    encoding="utf-8"
                )
            )
        )

        if unresolved:

            unresolved_all[
                str(
                    file.relative_to(
                        ROOT
                    )
                )
            ] = unresolved

        print(
            "      [OK] "
            f"{file.relative_to(ROOT)}"
        )

    if unresolved_all:

        raise RuntimeError(
            "Globais não resolvidos: "
            f"{unresolved_all}"
        )

    # SessoesContagem não pode mais aparecer na camada
    # de aplicação.
    direct_session_refs = {}

    for file in [
        target_service,
        *sorted(
            target_pkg.glob("*.py")
        ),
    ]:

        text = file.read_text(
            encoding="utf-8"
        )

        if (
            "dbo.SessoesContagem"
            in text
        ):

            direct_session_refs[
                str(
                    file.relative_to(
                        ROOT
                    )
                )
            ] = [
                i + 1
                for i, line
                in enumerate(
                    text.splitlines()
                )
                if (
                    "dbo.SessoesContagem"
                    in line
                )
            ]

    if direct_session_refs:

        raise RuntimeError(
            "SessoesContagem ainda acessada fora "
            "da camada repository: "
            f"{direct_session_refs}"
        )

    # RodadasInventario deve continuar isolado desde 8A.
    direct_rodada_refs = {}

    for file in [
        target_service,
        *sorted(
            target_pkg.glob("*.py")
        ),
    ]:

        text = file.read_text(
            encoding="utf-8"
        )

        if (
            "dbo.RodadasInventario"
            in text
        ):

            direct_rodada_refs[
                str(
                    file.relative_to(
                        ROOT
                    )
                )
            ] = [
                i + 1
                for i, line
                in enumerate(
                    text.splitlines()
                )
                if (
                    "dbo.RodadasInventario"
                    in line
                )
            ]

    if direct_rodada_refs:

        raise RuntimeError(
            "Regressão arquitetural em RodadasInventario: "
            f"{direct_rodada_refs}"
        )

    creation = (
        target_pkg
        / "criacao.py"
    ).read_text(
        encoding="utf-8"
    )

    for text in [
        "sys.sp_getapplock",
        "SGI:ROTATIVO:PROXIMA_RODADA",
    ]:

        if text not in creation:

            raise RuntimeError(
                "Proteção de concorrência perdida: "
                f"{text}"
            )

    for file in files:

        text = file.read_text(
            encoding="utf-8"
        )

        if (
            ".commit(" in text
            or ".rollback(" in text
        ):

            raise RuntimeError(
                "Commit/rollback introduzido em "
                f"{file.relative_to(ROOT)}"
            )

    print(
        "      [OK] SessoesContagem isolada em repositories."
    )

    print(
        "      [OK] RodadasInventario continua isolada."
    )

    print(
        "      [OK] sp_getapplock preservado."
    )

    print(
        "      [OK] nenhum commit/rollback introduzido."
    )

    print(
        "      [OK] nenhum global não resolvido."
    )

except Exception:

    print()

    print(
        "[ERRO] Falha. Restaurando Fase 8A..."
    )

    shutil.copy2(
        backup_service,
        target_service,
    )

    if target_pkg.exists():

        shutil.rmtree(
            target_pkg
        )

    shutil.copytree(
        backup_pkg,
        target_pkg,
    )

    print(
        "[OK] Fase 8A restaurada."
    )

    raise


print()

print(
    "[OK] Fase 8B aplicada."
)

print(
    "[OK] sessao_repository.py criado."
)

print(
    "[OK] read model ROTATIVO movido para repository."
)

print(
    "[OK] SQL de SessoesContagem removido da camada de aplicação."
)

print(
    "[OK] Transações preservadas."
)

print()

print(
    "BACKUPS:"
)

print(
    f"  {backup_service}"
)

print(
    f"  {backup_pkg}"
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
