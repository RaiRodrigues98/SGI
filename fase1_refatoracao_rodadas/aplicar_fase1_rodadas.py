"""
Aplica a Fase 1 da refatoração de rodadas no SGI.

Execute NA RAIZ do projeto:
    python aplicar_fase1_rodadas.py

O script:
- valida a estrutura;
- faz backup do services/rodadas_service.py;
- cria services/rodadas/;
- copia os novos módulos;
- substitui rodadas_service.py;
- compila os arquivos;
- restaura o backup se a compilação falhar.
"""

from pathlib import Path
from datetime import datetime
import py_compile
import shutil
import sys

ROOT = Path.cwd()
PAYLOAD = Path(__file__).resolve().parent / "services"

target_service = ROOT / "services" / "rodadas_service.py"
target_pkg = ROOT / "services" / "rodadas"

if not target_service.exists():
    raise SystemExit(
        f"[ERRO] Execute na raiz do SGI. Não encontrado: {target_service}"
    )

payload_service = PAYLOAD / "rodadas_service.py"
payload_pkg = PAYLOAD / "rodadas"

for required in [
    payload_service,
    payload_pkg / "__init__.py",
    payload_pkg / "itens.py",
    payload_pkg / "localizacoes.py",
]:
    if not required.exists():
        raise SystemExit(f"[ERRO] Payload incompleto: {required}")

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup = ROOT / "services" / f"rodadas_service_backup_fase1_{timestamp}.py"

print("[1/5] Criando backup...")
shutil.copy2(target_service, backup)
print(f"      {backup}")

try:
    print("[2/5] Criando services/rodadas...")
    target_pkg.mkdir(parents=True, exist_ok=True)

    print("[3/5] Copiando módulos extraídos...")
    for name in ["__init__.py", "itens.py", "localizacoes.py"]:
        shutil.copy2(
            payload_pkg / name,
            target_pkg / name,
        )

    print("[4/5] Atualizando services/rodadas_service.py...")
    shutil.copy2(
        payload_service,
        target_service,
    )

    print("[5/5] Validando sintaxe...")
    for file in [
        target_service,
        target_pkg / "__init__.py",
        target_pkg / "itens.py",
        target_pkg / "localizacoes.py",
    ]:
        py_compile.compile(
            str(file),
            doraise=True,
        )
        print(f"      [OK] {file.relative_to(ROOT)}")

except Exception:
    print("[ERRO] Falha durante aplicação. Restaurando rodadas_service.py...")
    shutil.copy2(backup, target_service)
    raise

print()
print("[OK] Fase 1 aplicada.")
print("[OK] Backup preservado em:")
print(f"     {backup}")
print()
print("PRÓXIMO PASSO:")
print("python tests_e2e\\regressao_final_sgi.py")
