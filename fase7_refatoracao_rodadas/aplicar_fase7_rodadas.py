"""
Aplica a Fase 7 da refatoração de rodadas.

Pré-requisito:
- Fase 6 instalada.

Objetivo:
- mover a criação para services/rodadas/criacao.py;
- transformar criar_proxima_rodada em orquestrador;
- manter services/rodadas_service.py como fachada compatível.

Execute na raiz do SGI:

    python .\fase7_refatoracao_rodadas\aplicar_fase7_rodadas.py
"""

from pathlib import Path
from datetime import datetime
import ast
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

print(
    "[0/8] Validando pré-requisito da Fase 6..."
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
]

for file in required:

    if not file.exists():

        raise SystemExit(
            "[ERRO] Fase 6 incompleta. "
            f"Ausente: {file}"
        )

current = target_service.read_text(
    encoding="utf-8"
)

for text in [
    "from services.rodadas.preview import",
    "def criar_proxima_rodada(",
    "sp_getapplock",
    "SGI:ROTATIVO:PROXIMA_RODADA",
]:

    if text not in current:

        raise SystemExit(
            "[ERRO] Baseline esperada da Fase 6 "
            "não identificada. "
            f"Ausente: {text}"
        )

print(
    "      [OK] Fase 6 identificada."
)

timestamp = datetime.now().strftime(
    "%Y%m%d_%H%M%S"
)

backup_service = (
    ROOT
    / "services"
    / (
        "rodadas_service_backup_fase7_"
        f"{timestamp}.py"
    )
)

backup_pkg = (
    ROOT
    / "services"
    / (
        "rodadas_backup_fase7_"
        f"{timestamp}"
    )
)

print(
    "[1/8] Criando backup do rodadas_service.py..."
)

shutil.copy2(
    target_service,
    backup_service,
)

print(
    f"      {backup_service}"
)

print(
    "[2/8] Criando backup de services/rodadas..."
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

    module_bound = set()

    for symbol in st.get_symbols():

        if (
            symbol.is_imported()
            or
            symbol.is_assigned()
            or
            symbol.is_namespace()
            or
            symbol.is_parameter()
        ):

            module_bound.add(
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
                        and
                        symbol.is_referenced()
                    )
                }

                missing = sorted(
                    refs
                    - module_bound
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
        "[3/8] Instalando criacao.py..."
    )

    shutil.copy2(
        PAYLOAD
        / "rodadas"
        / "criacao.py",
        target_pkg
        / "criacao.py",
    )

    print(
        "[4/8] Atualizando services/rodadas/__init__.py..."
    )

    shutil.copy2(
        PAYLOAD
        / "rodadas"
        / "__init__.py",
        target_pkg
        / "__init__.py",
    )

    print(
        "[5/8] Convertendo rodadas_service.py "
        "em fachada compatível..."
    )

    shutil.copy2(
        PAYLOAD
        / "rodadas_service.py",
        target_service,
    )

    print(
        "[6/8] Validando sintaxe..."
    )

    files = [
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
    ]

    for file in files:

        py_compile.compile(
            str(file),
            doraise=True,
        )

        print(
            "      [OK] "
            f"{file.relative_to(ROOT)}"
        )

    print(
        "[7/8] Validando referências globais..."
    )

    for file in [
        target_service,
        target_pkg / "criacao.py",
        target_pkg / "preview.py",
    ]:

        text = file.read_text(
            encoding="utf-8"
        )

        unresolved = (
            unresolved_globals(
                text
            )
        )

        if unresolved:

            raise RuntimeError(
                "Globais não resolvidos em "
                f"{file.name}: {unresolved}"
            )

        print(
            "      [OK] "
            f"{file.relative_to(ROOT)}"
        )

    print(
        "[8/8] Validando invariantes críticas..."
    )

    facade = target_service.read_text(
        encoding="utf-8"
    )

    creation = (
        target_pkg
        / "criacao.py"
    ).read_text(
        encoding="utf-8"
    )

    if (
        "def criar_proxima_rodada("
        in facade
    ):

        raise RuntimeError(
            "A implementação de criar_proxima_rodada "
            "ainda está no rodadas_service.py."
        )

    for text in [
        "from services.rodadas.criacao import",
        "criar_proxima_rodada",
        "visualizar_proxima_rodada",
    ]:

        if text not in facade:

            raise RuntimeError(
                "Fachada incompatível. "
                f"Ausente: {text}"
            )

    for text in [
        "def criar_proxima_rodada(",
        "sys.sp_getapplock",
        "SGI:ROTATIVO:PROXIMA_RODADA",
        "_encerrar_inventario_rotativo_apos_r2(",
        "_encerrar_inventario_rotativo_apos_r1_sem_recontagem(",
        "_buscar_candidatos_r2_rotativo(",
        "_buscar_candidatos_r3(",
        "_buscar_candidatos_recontagem_anterior(",
        "_buscar_candidatos_gestor(",
        "_finalizar_rodada_atual(",
        "INSERT INTO dbo.RodadasInventario",
        "UPDATE dbo.Inventarios",
    ]:

        if text not in creation:

            raise RuntimeError(
                "Invariante crítica perdida em criacao.py: "
                f"{text}"
            )

    creation_tree = ast.parse(
        creation
    )

    create_node = next(
        node
        for node in creation_tree.body
        if (
            isinstance(
                node,
                ast.FunctionDef,
            )
            and
            node.name
            == "criar_proxima_rodada"
        )
    )

    create_lines = (
        create_node.end_lineno
        - create_node.lineno
        + 1
    )

    if create_lines >= 300:

        raise RuntimeError(
            "Orquestrador ainda excessivamente grande: "
            f"{create_lines} linhas."
        )

    print(
        "      [OK] sp_getapplock preservado."
    )

    print(
        "      [OK] ROTATIVO terminal preservado."
    )

    print(
        "      [OK] candidatos ROTATIVO/OFICIAL preservados."
    )

    print(
        "      [OK] fachada pública preservada."
    )

    print(
        "      [OK] criar_proxima_rodada = "
        f"{create_lines} linhas."
    )

except Exception:

    print()

    print(
        "[ERRO] Falha. Restaurando Fase 6..."
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
        "[OK] Fase 6 restaurada."
    )

    raise


print()

print(
    "[OK] Fase 7 aplicada."
)

print(
    "[OK] criar_proxima_rodada agora é orquestrador."
)

print(
    "[OK] rodadas_service.py agora é fachada de compatibilidade."
)

print(
    "[OK] Regras, SQL e concorrência preservados."
)

print(
    "[OK] Nenhum commit/rollback foi introduzido."
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
