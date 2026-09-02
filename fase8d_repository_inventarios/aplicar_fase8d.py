"""
Fase 8D - Repository de dbo.Inventarios.

Execute na raiz do SGI:

python .\fase8d_repository_inventarios\aplicar_fase8d.py
"""

from pathlib import Path
from datetime import datetime
import builtins
import py_compile
import shutil
import symtable

ROOT = Path.cwd()
PAYLOAD = Path(__file__).resolve().parent / "services"

target_service = ROOT / "services" / "rodadas_service.py"
target_pkg = ROOT / "services" / "rodadas"
target_repos = target_pkg / "repositories"

print("[0/9] Validando baseline da Fase 8C...")

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
    target_repos / "sessao_repository.py",
    target_repos / "divergencia_rotativo_repository.py",
    target_repos / "item_repository.py",
    target_repos / "localizacao_repository.py",
]
for f in required:
    if not f.exists():
        raise SystemExit(f"[ERRO] Baseline 8C incompleta: {f}")

creation = (target_pkg / "criacao.py").read_text(encoding="utf-8")
finalizacao = (target_pkg / "finalizacao_rotativo.py").read_text(encoding="utf-8")

for text in ["dbo.Inventarios", "sys.sp_getapplock", "SGI:ROTATIVO:PROXIMA_RODADA"]:
    if text not in creation:
        raise SystemExit(f"[ERRO] criacao.py não corresponde à Fase 8C: {text}")

if finalizacao.count("dbo.Inventarios") < 2:
    raise SystemExit("[ERRO] finalizacao_rotativo.py não corresponde à Fase 8C.")

print("      [OK] Fase 8C identificada.")

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup_service = ROOT / "services" / f"rodadas_service_backup_fase8d_{timestamp}.py"
backup_pkg = ROOT / "services" / f"rodadas_backup_fase8d_{timestamp}"

print("[1/9] Criando backup do rodadas_service.py...")
shutil.copy2(target_service, backup_service)
print(f"      {backup_service}")

print("[2/9] Criando backup de services/rodadas...")
if backup_pkg.exists():
    shutil.rmtree(backup_pkg)
shutil.copytree(target_pkg, backup_pkg)
print(f"      {backup_pkg}")

def unresolved_globals(src: str):
    st = symtable.symtable(src, "module.py", "exec")
    bound = {
        s.get_name()
        for s in st.get_symbols()
        if s.is_imported() or s.is_assigned() or s.is_namespace() or s.is_parameter()
    }
    builtins_set = set(dir(builtins))
    result = {}
    def walk(table):
        for child in table.get_children():
            if child.get_type() == "function":
                refs = {
                    s.get_name()
                    for s in child.get_symbols()
                    if s.is_global() and s.is_referenced()
                }
                missing = sorted(refs - bound - builtins_set)
                if missing:
                    result[child.get_name()] = missing
            walk(child)
    walk(st)
    return result

try:
    print("[3/9] Instalando inventario_repository.py...")
    shutil.copy2(
        PAYLOAD / "rodadas" / "repositories" / "inventario_repository.py",
        target_repos / "inventario_repository.py",
    )

    print("[4/9] Atualizando criacao.py...")
    shutil.copy2(
        PAYLOAD / "rodadas" / "criacao.py",
        target_pkg / "criacao.py",
    )

    print("[5/9] Atualizando finalizacao_rotativo.py...")
    shutil.copy2(
        PAYLOAD / "rodadas" / "finalizacao_rotativo.py",
        target_pkg / "finalizacao_rotativo.py",
    )

    print("[6/9] Validando sintaxe...")
    files = [
        target_service,
        *sorted(target_pkg.glob("*.py")),
        *sorted(target_repos.glob("*.py")),
    ]
    for f in files:
        py_compile.compile(str(f), doraise=True)
        print(f"      [OK] {f.relative_to(ROOT)}")

    print("[7/9] Validando referências globais...")
    unresolved_all = {}
    for f in files:
        issues = unresolved_globals(f.read_text(encoding="utf-8"))
        if issues:
            unresolved_all[str(f.relative_to(ROOT))] = issues
    if unresolved_all:
        raise RuntimeError(f"Globais não resolvidos: {unresolved_all}")
    print("      [OK] nenhum global não resolvido.")

    print("[8/9] Validando isolamento das tabelas...")
    for table in [
        "dbo.Inventarios",
        "dbo.RodadaItens",
        "dbo.RodadaLocalizacoes",
        "dbo.RodadasInventario",
        "dbo.SessoesContagem",
    ]:
        offenders = {}
        for f in [target_service, *sorted(target_pkg.glob("*.py"))]:
            text = f.read_text(encoding="utf-8")
            if table in text:
                offenders[str(f.relative_to(ROOT))] = [
                    i + 1
                    for i, line in enumerate(text.splitlines())
                    if table in line
                ]
        if offenders:
            raise RuntimeError(f"{table} fora de repositories: {offenders}")
    print("      [OK] tabelas 8A-8D isoladas.")

    print("[9/9] Validando invariantes críticas...")
    repo = (target_repos / "inventario_repository.py").read_text(encoding="utf-8")
    for text in [
        "RodadaAtual = ?",
        "RodadaAtual = 1",
        "RodadaAtual = 2",
        "def atualizar_rodada_atual(",
        "def finalizar_rotativo_pela_r1(",
        "def finalizar_rotativo_pela_r2(",
    ]:
        if text not in repo:
            raise RuntimeError(f"inventario_repository incompleto: {text}")

    creation = (target_pkg / "criacao.py").read_text(encoding="utf-8")
    for text in ["sys.sp_getapplock", "SGI:ROTATIVO:PROXIMA_RODADA"]:
        if text not in creation:
            raise RuntimeError(f"Concorrência perdida: {text}")

    for f in files:
        text = f.read_text(encoding="utf-8")
        if ".commit(" in text or ".rollback(" in text:
            raise RuntimeError(
                f"Commit/rollback introduzido em {f.relative_to(ROOT)}"
            )

    print("      [OK] RodadaAtual preservada.")
    print("      [OK] finalização R1 preservada.")
    print("      [OK] finalização R2 preservada.")
    print("      [OK] sp_getapplock preservado.")
    print("      [OK] nenhum commit/rollback introduzido.")

except Exception:
    print()
    print("[ERRO] Falha. Restaurando Fase 8C...")
    shutil.copy2(backup_service, target_service)
    if target_pkg.exists():
        shutil.rmtree(target_pkg)
    shutil.copytree(backup_pkg, target_pkg)
    print("[OK] Fase 8C restaurada.")
    raise

print()
print("[OK] Fase 8D aplicada.")
print("[OK] Repository de Inventarios criado.")
print("[OK] SQL de Inventarios removido da aplicação.")
print("[OK] Fases 8A/8B/8C preservadas.")
print("[OK] Transações preservadas.")
print()
print("PRÓXIMO PASSO:")
print("1. Reinicie a API.")
print(r"2. python tests_e2e\regressao_final_sgi.py")
