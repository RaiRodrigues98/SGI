"""
Aplica a Fase 3 da refatoração de rodadas.

Pré-requisitos:
- Fase 1 aprovada;
- Fase 2 aprovada.

Execute na raiz do SGI:
    python .\fase3_refatoracao_rodadas\aplicar_fase3_rodadas.py
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

print("[0/6] Validando pré-requisito da Fase 2...")

required = [
    target_service,
    target_pkg / "__init__.py",
    target_pkg / "itens.py",
    target_pkg / "localizacoes.py",
    target_pkg / "candidatos_rotativo.py",
]
for f in required:
    if not f.exists():
        raise SystemExit(f"[ERRO] Fase 2 incompleta. Ausente: {f}")

current = target_service.read_text(encoding="utf-8")
for text in [
    "from services.rodadas.candidatos_rotativo import",
    "_buscar_candidatos_r2_rotativo(",
    "sp_getapplock",
    "SGI:ROTATIVO:PROXIMA_RODADA",
]:
    if text not in current:
        raise SystemExit(
            "[ERRO] Baseline esperada da Fase 2 não identificada. "
            f"Ausente: {text}"
        )

tree = ast.parse(current)
defs = {
    n.name
    for n in tree.body
    if isinstance(n, ast.FunctionDef)
}
expected_official = {
    "_buscar_candidatos_r3",
    "_buscar_candidatos_recontagem_anterior",
}
missing = expected_official - defs
if missing:
    raise SystemExit(
        "[ERRO] O rodadas_service.py não corresponde à Fase 2. "
        "Funções OFICIAL ausentes: " + ", ".join(sorted(missing))
    )

print("      [OK] Fase 2 identificada.")

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup_service = ROOT / "services" / f"rodadas_service_backup_fase3_{timestamp}.py"
backup_pkg = ROOT / "services" / f"rodadas_backup_fase3_{timestamp}"

print("[1/6] Criando backup do rodadas_service.py...")
shutil.copy2(target_service, backup_service)
print(f"      {backup_service}")

print("[2/6] Criando backup de services/rodadas...")
if backup_pkg.exists():
    shutil.rmtree(backup_pkg)
shutil.copytree(target_pkg, backup_pkg)
print(f"      {backup_pkg}")

try:
    print("[3/6] Instalando candidatos_oficial.py...")
    shutil.copy2(
        PAYLOAD / "rodadas" / "candidatos_oficial.py",
        target_pkg / "candidatos_oficial.py",
    )

    print("[4/6] Atualizando services/rodadas/__init__.py...")
    shutil.copy2(
        PAYLOAD / "rodadas" / "__init__.py",
        target_pkg / "__init__.py",
    )

    print("[5/6] Atualizando services/rodadas_service.py...")
    shutil.copy2(
        PAYLOAD / "rodadas_service.py",
        target_service,
    )

    print("[6/6] Validando sintaxe e estrutura...")
    files = [
        target_service,
        target_pkg / "__init__.py",
        target_pkg / "itens.py",
        target_pkg / "localizacoes.py",
        target_pkg / "candidatos_rotativo.py",
        target_pkg / "candidatos_oficial.py",
    ]
    for f in files:
        py_compile.compile(str(f), doraise=True)
        print(f"      [OK] {f.relative_to(ROOT)}")

    final = target_service.read_text(encoding="utf-8")
    final_tree = ast.parse(final)
    final_defs = {
        n.name
        for n in final_tree.body
        if isinstance(n, ast.FunctionDef)
    }

    remaining = expected_official & final_defs
    if remaining:
        raise RuntimeError(
            "Funções OFICIAL ainda presentes no service: "
            + ", ".join(sorted(remaining))
        )

    for text in [
        "_buscar_candidatos_r3(",
        "_buscar_candidatos_recontagem_anterior(",
        "_buscar_candidatos_r2_rotativo(",
        "sp_getapplock",
        "SGI:ROTATIVO:PROXIMA_RODADA",
        "_buscar_candidatos_gestor",
        "_encerrar_inventario_rotativo_apos_r2",
    ]:
        if text not in final:
            raise RuntimeError(f"Validação estrutural falhou: {text}")

except Exception:
    print()
    print("[ERRO] Falha. Restaurando Fase 2...")
    shutil.copy2(backup_service, target_service)

    if target_pkg.exists():
        shutil.rmtree(target_pkg)
    shutil.copytree(backup_pkg, target_pkg)

    print("[OK] Fase 2 restaurada.")
    raise

print()
print("[OK] Fase 3 aplicada.")
print("[OK] Candidatos OFICIAL extraídos.")
print("[OK] ROTATIVO preservado.")
print("[OK] Proteção de concorrência preservada.")
print()
print("BACKUPS:")
print(f"  {backup_service}")
print(f"  {backup_pkg}")
print()
print("PRÓXIMO PASSO:")
print("1. Reinicie a API.")
print(r"2. python tests_e2e\regressao_final_sgi.py")
