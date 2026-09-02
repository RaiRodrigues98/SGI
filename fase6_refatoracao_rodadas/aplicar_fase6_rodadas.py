"""
Aplica a Fase 6 da refatoração de rodadas.

Pré-requisito:
- Fase 5 instalada.

Objetivo:
- extrair visualizar_proxima_rodada para services/rodadas/preview.py;
- preservar o contrato público de services.rodadas_service;
- validar referências globais além da compilação sintática.

Execute na raiz do SGI:

    python .\fase6_refatoracao_rodadas\aplicar_fase6_rodadas.py
"""

from pathlib import Path
from datetime import datetime
import ast
import builtins
import py_compile
import shutil
import symtable

ROOT = Path.cwd()
PAYLOAD = Path(__file__).resolve().parent / "services"

target_service = ROOT / "services" / "rodadas_service.py"
target_pkg = ROOT / "services" / "rodadas"

print("[0/7] Validando pré-requisito da Fase 5...")

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
]

for file in required:
    if not file.exists():
        raise SystemExit(
            f"[ERRO] Fase 5 incompleta. Ausente: {file}"
        )

current = target_service.read_text(encoding="utf-8")

for text in [
    "from services.rodadas.lifecycle import",
    "from services.rodadas.finalizacao_rotativo import",
    "def visualizar_proxima_rodada(",
    "def criar_proxima_rodada(",
    "sp_getapplock",
    "SGI:ROTATIVO:PROXIMA_RODADA",
]:
    if text not in current:
        raise SystemExit(
            "[ERRO] Baseline esperada da Fase 5 não identificada. "
            f"Ausente: {text}"
        )

print("      [OK] Fase 5 identificada.")

# Alerta controlado: detecta exatamente o problema conhecido.
if (
    "analisar_recontagem_oficial(" in current
    and "from services.analise_recontagem import" not in current
):
    print(
        "      [INFO] Import ausente de analisar_recontagem_oficial "
        "detectado no preview atual."
    )
    print(
        "      [INFO] A Fase 6 corrige isso ao mover o preview "
        "para um módulo com dependências explícitas."
    )

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

backup_service = (
    ROOT / "services"
    / f"rodadas_service_backup_fase6_{timestamp}.py"
)

backup_pkg = (
    ROOT / "services"
    / f"rodadas_backup_fase6_{timestamp}"
)

print("[1/7] Criando backup do rodadas_service.py...")
shutil.copy2(target_service, backup_service)
print(f"      {backup_service}")

print("[2/7] Criando backup de services/rodadas...")
if backup_pkg.exists():
    shutil.rmtree(backup_pkg)
shutil.copytree(target_pkg, backup_pkg)
print(f"      {backup_pkg}")

def unresolved_globals(module_source: str):
    st = symtable.symtable(module_source, "module.py", "exec")
    module_bound = set()

    for symbol in st.get_symbols():
        if (
            symbol.is_imported()
            or symbol.is_assigned()
            or symbol.is_namespace()
            or symbol.is_parameter()
        ):
            module_bound.add(symbol.get_name())

    builtin_names = set(dir(builtins))
    result = {}

    for child in st.get_children():
        if child.get_type() != "function":
            continue

        refs = {
            s.get_name()
            for s in child.get_symbols()
            if s.is_global() and s.is_referenced()
        }

        missing = sorted(refs - module_bound - builtin_names)

        if missing:
            result[child.get_name()] = missing

    return result

try:
    print("[3/7] Instalando preview.py...")
    shutil.copy2(
        PAYLOAD / "rodadas" / "preview.py",
        target_pkg / "preview.py",
    )

    print("[4/7] Atualizando services/rodadas/__init__.py...")
    shutil.copy2(
        PAYLOAD / "rodadas" / "__init__.py",
        target_pkg / "__init__.py",
    )

    print("[5/7] Atualizando services/rodadas_service.py...")
    shutil.copy2(
        PAYLOAD / "rodadas_service.py",
        target_service,
    )

    print("[6/7] Validando sintaxe...")
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
    ]

    for file in files:
        py_compile.compile(str(file), doraise=True)
        print(f"      [OK] {file.relative_to(ROOT)}")

    print("[7/7] Validando referências globais...")

    final_service = target_service.read_text(encoding="utf-8")
    final_preview = (target_pkg / "preview.py").read_text(encoding="utf-8")

    unresolved_service = unresolved_globals(final_service)
    unresolved_preview = unresolved_globals(final_preview)

    if unresolved_service:
        raise RuntimeError(
            "Globais não resolvidos no rodadas_service.py: "
            f"{unresolved_service}"
        )

    if unresolved_preview:
        raise RuntimeError(
            "Globais não resolvidos no preview.py: "
            f"{unresolved_preview}"
        )

    tree = ast.parse(final_service)
    defs = {
        n.name
        for n in tree.body
        if isinstance(n, ast.FunctionDef)
    }

    if "visualizar_proxima_rodada" in defs:
        raise RuntimeError(
            "visualizar_proxima_rodada ainda está implementada "
            "no rodadas_service.py."
        )

    for text in [
        "from services.rodadas.preview import",
        "def criar_proxima_rodada(",
        "sp_getapplock",
        "SGI:ROTATIVO:PROXIMA_RODADA",
    ]:
        if text not in final_service:
            raise RuntimeError(
                f"Validação estrutural falhou: {text}"
            )

    if "def visualizar_proxima_rodada(" not in final_preview:
        raise RuntimeError(
            "Função de preview ausente do novo módulo."
        )

    print("      [OK] Nenhum global não resolvido.")

except Exception:
    print()
    print("[ERRO] Falha. Restaurando Fase 5...")

    shutil.copy2(backup_service, target_service)

    if target_pkg.exists():
        shutil.rmtree(target_pkg)

    shutil.copytree(backup_pkg, target_pkg)

    print("[OK] Fase 5 restaurada.")
    raise

print()
print("[OK] Fase 6 aplicada.")
print("[OK] Preview extraído para services/rodadas/preview.py.")
print("[OK] Contrato público preservado em rodadas_service.py.")
print("[OK] Referências globais validadas.")
print("[OK] Fluxo de criação não foi refatorado nesta fase.")
print("[OK] Proteção de concorrência preservada.")
print()
print("BACKUPS:")
print(f"  {backup_service}")
print(f"  {backup_pkg}")
print()
print("PRÓXIMO PASSO:")
print("1. Reinicie a API.")
print(r"2. python tests_e2e\regressao_final_sgi.py")
