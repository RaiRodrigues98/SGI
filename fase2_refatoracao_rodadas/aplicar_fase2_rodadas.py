"""
Aplica a Fase 2 da refatoração de rodadas no SGI.

Pré-requisito:
- Fase 1 já aplicada e aprovada.

Execute a partir da raiz do projeto:
    python .\fase2_refatoracao_rodadas\aplicar_fase2_rodadas.py

A Fase 2 extrai somente regras/candidatos do ROTATIVO.
"""

from pathlib import Path
from datetime import datetime
import ast
import py_compile
import shutil

ROOT = Path.cwd()
PAYLOAD = Path(__file__).resolve().parent / "services"

target_service = ROOT / "services" / "rodadas_service.py"
target_pkg = ROOT / "services" / "rodadas"

payload_service = PAYLOAD / "rodadas_service.py"
payload_pkg = PAYLOAD / "rodadas"

required_target_phase1 = [
    target_service,
    target_pkg / "__init__.py",
    target_pkg / "itens.py",
    target_pkg / "localizacoes.py",
]

print("[0/6] Validando pré-requisito da Fase 1...")

for required in required_target_phase1:
    if not required.exists():
        raise SystemExit(
            "[ERRO] A Fase 1 não está completa. "
            f"Arquivo ausente: {required}"
        )

current = target_service.read_text(
    encoding="utf-8",
)

for required_text in [
    "from services.rodadas import",
    "sp_getapplock",
    "SGI:ROTATIVO:PROXIMA_RODADA",
]:
    if required_text not in current:
        raise SystemExit(
            "[ERRO] Baseline esperada da Fase 1 não foi identificada. "
            f"Ausente: {required_text}"
        )

# Garante que as funções ainda estão no service antes da extração.
tree = ast.parse(current)

defs = {
    node.name
    for node in tree.body
    if isinstance(node, ast.FunctionDef)
}

expected_defs = {
    "_validar_divergencias_r1_rotativo_tratadas",
    "_buscar_colunas_tabela",
    "_resolver_coluna_quantidade_rotativo",
    "_buscar_candidatos_r2_rotativo",
}

missing_defs = expected_defs - defs

if missing_defs:
    raise SystemExit(
        "[ERRO] O rodadas_service.py não corresponde à baseline "
        "esperada da Fase 1. Funções ausentes: "
        + ", ".join(sorted(missing_defs))
    )

print("      [OK] Fase 1 identificada.")

timestamp = datetime.now().strftime(
    "%Y%m%d_%H%M%S"
)

backup_service = (
    ROOT
    / "services"
    / f"rodadas_service_backup_fase2_{timestamp}.py"
)

backup_pkg = (
    ROOT
    / "services"
    / f"rodadas_backup_fase2_{timestamp}"
)

print("[1/6] Criando backup do rodadas_service.py...")
shutil.copy2(
    target_service,
    backup_service,
)
print(f"      {backup_service}")

print("[2/6] Criando backup de services/rodadas...")
if backup_pkg.exists():
    shutil.rmtree(backup_pkg)

shutil.copytree(
    target_pkg,
    backup_pkg,
)
print(f"      {backup_pkg}")

try:
    print("[3/6] Instalando candidatos_rotativo.py...")
    shutil.copy2(
        payload_pkg / "candidatos_rotativo.py",
        target_pkg / "candidatos_rotativo.py",
    )

    print("[4/6] Atualizando services/rodadas/__init__.py...")
    shutil.copy2(
        payload_pkg / "__init__.py",
        target_pkg / "__init__.py",
    )

    print("[5/6] Atualizando services/rodadas_service.py...")
    shutil.copy2(
        payload_service,
        target_service,
    )

    print("[6/6] Validando sintaxe/importações estruturais...")

    files = [
        target_service,
        target_pkg / "__init__.py",
        target_pkg / "itens.py",
        target_pkg / "localizacoes.py",
        target_pkg / "candidatos_rotativo.py",
    ]

    for file in files:
        py_compile.compile(
            str(file),
            doraise=True,
        )
        print(
            f"      [OK] {file.relative_to(ROOT)}"
        )

    final_service = target_service.read_text(
        encoding="utf-8",
    )

    # Confirma que as implementações foram removidas do service,
    # mas as chamadas e proteção de concorrência permanecem.
    final_tree = ast.parse(final_service)

    final_defs = {
        node.name
        for node in final_tree.body
        if isinstance(node, ast.FunctionDef)
    }

    remaining = expected_defs & final_defs

    if remaining:
        raise RuntimeError(
            "Implementações ROTATIVO ainda presentes no service: "
            + ", ".join(sorted(remaining))
        )

    for required_text in [
        "_validar_divergencias_r1_rotativo_tratadas(",
        "_buscar_candidatos_r2_rotativo(",
        "sp_getapplock",
        "SGI:ROTATIVO:PROXIMA_RODADA",
        "_buscar_candidatos_r3",
        "_buscar_candidatos_recontagem_anterior",
    ]:
        if required_text not in final_service:
            raise RuntimeError(
                f"Validação estrutural falhou: {required_text}"
            )

except Exception:
    print()
    print("[ERRO] Falha na aplicação. Restaurando Fase 1...")

    shutil.copy2(
        backup_service,
        target_service,
    )

    if target_pkg.exists():
        shutil.rmtree(target_pkg)

    shutil.copytree(
        backup_pkg,
        target_pkg,
    )

    print("[OK] Fase 1 restaurada.")
    raise

print()
print("[OK] Fase 2 aplicada.")
print("[OK] Regras/candidatos ROTATIVO extraídos.")
print("[OK] Fluxo OFICIAL permaneceu no rodadas_service.py.")
print("[OK] Proteção de concorrência do Estágio 14 preservada.")
print()
print("BACKUPS:")
print(f"  {backup_service}")
print(f"  {backup_pkg}")
print()
print("PRÓXIMO PASSO:")
print("1. Reinicie a API.")
print("2. Execute:")
print(r"   python tests_e2e\regressao_final_sgi.py")
