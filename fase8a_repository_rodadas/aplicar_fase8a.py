"""
Fase 8A - Repository de dbo.RodadasInventario.

Execute na raiz do SGI:

python .\fase8a_repository_rodadas\aplicar_fase8a.py
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

print("[0/9] Validando baseline da Fase 7...")

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
]

for file in required:
    if not file.exists():
        raise SystemExit(f"[ERRO] Baseline incompleta: {file}")

service_text = target_service.read_text(encoding="utf-8")
creation_text = (target_pkg / "criacao.py").read_text(encoding="utf-8")

for text in [
    "from services.rodadas.criacao import",
    "from services.rodadas.preview import",
]:
    if text not in service_text:
        raise SystemExit(
            f"[ERRO] rodadas_service.py não corresponde à Fase 7: {text}"
        )

for text in [
    "sys.sp_getapplock",
    "SGI:ROTATIVO:PROXIMA_RODADA",
    "INSERT INTO dbo.RodadasInventario",
]:
    if text not in creation_text:
        raise SystemExit(
            f"[ERRO] criacao.py não corresponde à Fase 7: {text}"
        )

print("      [OK] Fase 7 identificada.")

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup_service = ROOT / "services" / f"rodadas_service_backup_fase8a_{timestamp}.py"
backup_pkg = ROOT / "services" / f"rodadas_backup_fase8a_{timestamp}"

print("[1/9] Criando backup do rodadas_service.py...")
shutil.copy2(target_service, backup_service)
print(f"      {backup_service}")

print("[2/9] Criando backup de services/rodadas...")
if backup_pkg.exists():
    shutil.rmtree(backup_pkg)
shutil.copytree(target_pkg, backup_pkg)
print(f"      {backup_pkg}")


def unresolved_globals(module_source: str):
    st = symtable.symtable(module_source, "module.py", "exec")
    bound = set()

    for symbol in st.get_symbols():
        if (
            symbol.is_imported()
            or symbol.is_assigned()
            or symbol.is_namespace()
            or symbol.is_parameter()
        ):
            bound.add(symbol.get_name())

    builtin_names = set(dir(builtins))
    result = {}

    def walk(table):
        for child in table.get_children():
            if child.get_type() == "function":
                refs = {
                    s.get_name()
                    for s in child.get_symbols()
                    if s.is_global() and s.is_referenced()
                }
                missing = sorted(refs - bound - builtin_names)
                if missing:
                    result[child.get_name()] = missing
            walk(child)

    walk(st)
    return result


try:
    print("[3/9] Criando repositories...")
    target_repos.mkdir(parents=True, exist_ok=True)

    print("[4/9] Instalando rodada_repository.py...")
    shutil.copy2(
        PAYLOAD / "rodadas" / "repositories" / "__init__.py",
        target_repos / "__init__.py",
    )
    shutil.copy2(
        PAYLOAD / "rodadas" / "repositories" / "rodada_repository.py",
        target_repos / "rodada_repository.py",
    )

    print("[5/9] Atualizando lifecycle.py e localizacoes.py...")
    shutil.copy2(
        PAYLOAD / "rodadas" / "lifecycle.py",
        target_pkg / "lifecycle.py",
    )
    shutil.copy2(
        PAYLOAD / "rodadas" / "localizacoes.py",
        target_pkg / "localizacoes.py",
    )

    print("[6/9] Atualizando criacao.py...")
    shutil.copy2(
        PAYLOAD / "rodadas" / "criacao.py",
        target_pkg / "criacao.py",
    )

    print("[7/9] Atualizando finalizacao_rotativo.py e preview.py...")
    shutil.copy2(
        PAYLOAD / "rodadas" / "finalizacao_rotativo.py",
        target_pkg / "finalizacao_rotativo.py",
    )
    shutil.copy2(
        PAYLOAD / "rodadas" / "preview.py",
        target_pkg / "preview.py",
    )

    print("[8/9] Validando todos os módulos...")

    files = [
        target_service,
        *sorted(target_pkg.glob("*.py")),
        *sorted(target_repos.glob("*.py")),
    ]

    unresolved_all = {}

    for file in files:
        py_compile.compile(str(file), doraise=True)

        unresolved = unresolved_globals(
            file.read_text(encoding="utf-8")
        )

        if unresolved:
            unresolved_all[
                str(file.relative_to(ROOT))
            ] = unresolved

        print(f"      [OK] {file.relative_to(ROOT)}")

    if unresolved_all:
        raise RuntimeError(
            f"Globais não resolvidos: {unresolved_all}"
        )

    print("[9/9] Validando isolamento e invariantes...")

    direct_refs = {}

    for file in [
        target_service,
        *sorted(target_pkg.glob("*.py")),
    ]:
        text = file.read_text(encoding="utf-8")

        if "dbo.RodadasInventario" in text:
            direct_refs[str(file.relative_to(ROOT))] = [
                i + 1
                for i, line in enumerate(text.splitlines())
                if "dbo.RodadasInventario" in line
            ]

    if direct_refs:
        raise RuntimeError(
            "SQL direto de RodadasInventario fora do repository: "
            f"{direct_refs}"
        )

    repo = (
        target_repos / "rodada_repository.py"
    ).read_text(encoding="utf-8")

    for text in [
        "UPDATE dbo.RodadasInventario",
        "INSERT INTO dbo.RodadasInventario",
        "buscar_rodada_para_sincronizacao",
        "buscar_r1",
        "buscar_proxima_rodada_preview",
    ]:
        if text not in repo:
            raise RuntimeError(f"Repository incompleto: {text}")

    creation = (
        target_pkg / "criacao.py"
    ).read_text(encoding="utf-8")

    for text in [
        "sys.sp_getapplock",
        "SGI:ROTATIVO:PROXIMA_RODADA",
    ]:
        if text not in creation:
            raise RuntimeError(f"Concorrência perdida: {text}")

    for file in files:
        text = file.read_text(encoding="utf-8")
        if ".commit(" in text or ".rollback(" in text:
            raise RuntimeError(
                "Commit/rollback introduzido indevidamente em "
                f"{file.relative_to(ROOT)}"
            )

    print("      [OK] RodadasInventario isolado no repository.")
    print("      [OK] sp_getapplock preservado.")
    print("      [OK] nenhum commit/rollback introduzido.")
    print("      [OK] nenhum global não resolvido.")

except Exception:
    print()
    print("[ERRO] Falha. Restaurando Fase 7...")

    shutil.copy2(backup_service, target_service)

    if target_pkg.exists():
        shutil.rmtree(target_pkg)

    shutil.copytree(backup_pkg, target_pkg)

    print("[OK] Fase 7 restaurada.")
    raise

print()
print("[OK] Fase 8A aplicada.")
print("[OK] Repository de RodadasInventario criado.")
print("[OK] lifecycle.py corrigido para _normalizar_texto.")
print("[OK] SQL isolado sem alterar transações.")
print()
print("BACKUPS:")
print(f"  {backup_service}")
print(f"  {backup_pkg}")
print()
print("PRÓXIMO PASSO:")
print("1. Reinicie a API.")
print(r"2. python tests_e2e\regressao_final_sgi.py")
