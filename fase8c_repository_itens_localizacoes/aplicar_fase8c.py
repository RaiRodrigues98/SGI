"""
Fase 8C - Repositories de RodadaItens e RodadaLocalizacoes.

Execute na raiz do SGI:

python .\fase8c_repository_itens_localizacoes\aplicar_fase8c.py
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

print("[0/9] Validando baseline da Fase 8B...")

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
]
for f in required:
    if not f.exists():
        raise SystemExit(f"[ERRO] Baseline incompleta: {f}")

loc_text = (target_pkg / "localizacoes.py").read_text(encoding="utf-8")
creation_text = (target_pkg / "criacao.py").read_text(encoding="utf-8")

for text in [
    "from services.rodadas.repositories.sessao_repository import",
    "dbo.RodadaItens",
    "dbo.RodadaLocalizacoes",
]:
    if text not in loc_text:
        raise SystemExit(
            "[ERRO] localizacoes.py não corresponde à Fase 8B. "
            f"Ausente: {text}"
        )

for text in ["sys.sp_getapplock", "SGI:ROTATIVO:PROXIMA_RODADA"]:
    if text not in creation_text:
        raise SystemExit(f"[ERRO] Concorrência ausente: {text}")

print("      [OK] Fase 8B identificada.")

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup_service = ROOT / "services" / f"rodadas_service_backup_fase8c_{timestamp}.py"
backup_pkg = ROOT / "services" / f"rodadas_backup_fase8c_{timestamp}"

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
    print("[3/9] Instalando item_repository.py...")
    shutil.copy2(
        PAYLOAD / "rodadas" / "repositories" / "item_repository.py",
        target_repos / "item_repository.py",
    )

    print("[4/9] Instalando localizacao_repository.py...")
    shutil.copy2(
        PAYLOAD / "rodadas" / "repositories" / "localizacao_repository.py",
        target_repos / "localizacao_repository.py",
    )

    print("[5/9] Atualizando itens.py...")
    shutil.copy2(
        PAYLOAD / "rodadas" / "itens.py",
        target_pkg / "itens.py",
    )

    print("[6/9] Atualizando localizacoes.py...")
    shutil.copy2(
        PAYLOAD / "rodadas" / "localizacoes.py",
        target_pkg / "localizacoes.py",
    )

    print("[7/9] Validando sintaxe e referências globais...")
    files = [
        target_service,
        *sorted(target_pkg.glob("*.py")),
        *sorted(target_repos.glob("*.py")),
    ]
    unresolved_all = {}
    for f in files:
        py_compile.compile(str(f), doraise=True)
        issues = unresolved_globals(f.read_text(encoding="utf-8"))
        if issues:
            unresolved_all[str(f.relative_to(ROOT))] = issues
        print(f"      [OK] {f.relative_to(ROOT)}")

    if unresolved_all:
        raise RuntimeError(f"Globais não resolvidos: {unresolved_all}")

    print("[8/9] Validando isolamento de tabelas...")
    for table in [
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
                    i + 1 for i, line in enumerate(text.splitlines()) if table in line
                ]
        if offenders:
            raise RuntimeError(f"{table} fora de repositories: {offenders}")

    print("[9/9] Validando invariantes críticas...")
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

    print("      [OK] RodadaItens isolada.")
    print("      [OK] RodadaLocalizacoes isolada.")
    print("      [OK] isolamentos 8A/8B preservados.")
    print("      [OK] sp_getapplock preservado.")
    print("      [OK] nenhum commit/rollback introduzido.")

except Exception:
    print()
    print("[ERRO] Falha. Restaurando Fase 8B...")
    shutil.copy2(backup_service, target_service)
    if target_pkg.exists():
        shutil.rmtree(target_pkg)
    shutil.copytree(backup_pkg, target_pkg)
    print("[OK] Fase 8B restaurada.")
    raise

print()
print("[OK] Fase 8C aplicada.")
print("[OK] Repository de RodadaItens criado.")
print("[OK] Repository de RodadaLocalizacoes criado.")
print("[OK] Normalizações permaneceram na aplicação.")
print("[OK] Transações preservadas.")
print()
print("PRÓXIMO PASSO:")
print("1. Reinicie a API.")
print(r"2. python tests_e2e\regressao_final_sgi.py")
