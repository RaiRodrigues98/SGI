"""
Aplica a Fase 5 da refatoração de rodadas.

Pré-requisito:
- Fase 4 instalada e aprovada.

Esta fase extrai:
- lifecycle de finalização da rodada;
- encerramentos terminais do inventário ROTATIVO.

Execute na raiz do SGI:

    python .\fase5_refatoracao_rodadas\aplicar_fase5_rodadas.py
"""

from pathlib import Path
from datetime import datetime
import ast
import py_compile
import shutil

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
    "[0/7] Validando pré-requisito da Fase 4..."
)

required = [
    target_service,
    target_pkg / "__init__.py",
    target_pkg / "itens.py",
    target_pkg / "localizacoes.py",
    target_pkg / "candidatos_rotativo.py",
    target_pkg / "candidatos_oficial.py",
    target_pkg / "gestor.py",
]

for file in required:
    if not file.exists():
        raise SystemExit(
            "[ERRO] Fase 4 incompleta. "
            f"Ausente: {file}"
        )

current = target_service.read_text(
    encoding="utf-8"
)

for text in [
    "from services.rodadas.candidatos_rotativo import",
    "from services.rodadas.candidatos_oficial import",
    "from services.rodadas.gestor import",
    "_buscar_candidatos_r2_rotativo(",
    "_buscar_candidatos_r3(",
    "_buscar_candidatos_gestor(",
    "sp_getapplock",
    "SGI:ROTATIVO:PROXIMA_RODADA",
]:
    if text not in current:
        raise SystemExit(
            "[ERRO] Baseline esperada da Fase 4 "
            "não identificada. "
            f"Ausente: {text}"
        )

tree = ast.parse(current)

defs = {
    node.name
    for node in tree.body
    if isinstance(
        node,
        ast.FunctionDef,
    )
}

expected = {
    "_finalizar_rodada_atual",
    "_encerrar_inventario_rotativo_apos_r1_sem_recontagem",
    "_encerrar_inventario_rotativo_apos_r2",
}

missing = expected - defs

if missing:
    raise SystemExit(
        "[ERRO] rodadas_service.py não corresponde "
        "à Fase 4. Funções ausentes: "
        + ", ".join(sorted(missing))
    )

print(
    "      [OK] Fase 4 identificada."
)

timestamp = datetime.now().strftime(
    "%Y%m%d_%H%M%S"
)

backup_service = (
    ROOT
    / "services"
    / (
        "rodadas_service_backup_fase5_"
        f"{timestamp}.py"
    )
)

backup_pkg = (
    ROOT
    / "services"
    / (
        "rodadas_backup_fase5_"
        f"{timestamp}"
    )
)

print(
    "[1/7] Criando backup do "
    "rodadas_service.py..."
)

shutil.copy2(
    target_service,
    backup_service,
)

print(
    f"      {backup_service}"
)

print(
    "[2/7] Criando backup de "
    "services/rodadas..."
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

try:

    print(
        "[3/7] Instalando lifecycle.py..."
    )

    shutil.copy2(
        PAYLOAD
        / "rodadas"
        / "lifecycle.py",
        target_pkg
        / "lifecycle.py",
    )

    print(
        "[4/7] Instalando "
        "finalizacao_rotativo.py..."
    )

    shutil.copy2(
        PAYLOAD
        / "rodadas"
        / "finalizacao_rotativo.py",
        target_pkg
        / "finalizacao_rotativo.py",
    )

    print(
        "[5/7] Atualizando "
        "services/rodadas/__init__.py..."
    )

    shutil.copy2(
        PAYLOAD
        / "rodadas"
        / "__init__.py",
        target_pkg
        / "__init__.py",
    )

    print(
        "[6/7] Atualizando "
        "services/rodadas_service.py..."
    )

    shutil.copy2(
        PAYLOAD
        / "rodadas_service.py",
        target_service,
    )

    print(
        "[7/7] Validando sintaxe "
        "e estrutura..."
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

    final = target_service.read_text(
        encoding="utf-8"
    )

    final_tree = ast.parse(
        final
    )

    final_defs = {
        node.name
        for node in final_tree.body
        if isinstance(
            node,
            ast.FunctionDef,
        )
    }

    remaining = (
        expected
        & final_defs
    )

    if remaining:
        raise RuntimeError(
            "Funções da Fase 5 ainda "
            "presentes no service: "
            + ", ".join(
                sorted(remaining)
            )
        )

    for text in [
        "from services.rodadas.lifecycle import",
        "from services.rodadas.finalizacao_rotativo import",
        "_finalizar_rodada_atual(",
        "_encerrar_inventario_rotativo_apos_r1_sem_recontagem(",
        "_encerrar_inventario_rotativo_apos_r2(",
        "_buscar_candidatos_r2_rotativo(",
        "_buscar_candidatos_r3(",
        "_buscar_candidatos_gestor(",
        "sp_getapplock",
        "SGI:ROTATIVO:PROXIMA_RODADA",
        "def criar_proxima_rodada(",
        "def visualizar_proxima_rodada(",
    ]:
        if text not in final:
            raise RuntimeError(
                "Validação estrutural falhou: "
                f"{text}"
            )

except Exception:

    print()
    print(
        "[ERRO] Falha. Restaurando Fase 4..."
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
        "[OK] Fase 4 restaurada."
    )

    raise

print()
print(
    "[OK] Fase 5 aplicada."
)
print(
    "[OK] Lifecycle de finalização extraído."
)
print(
    "[OK] Finalização ROTATIVO extraída."
)
print(
    "[OK] Fluxo OFICIAL preservado."
)
print(
    "[OK] Proteção de concorrência preservada."
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
