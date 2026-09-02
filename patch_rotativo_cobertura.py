from pathlib import Path
import shutil
import py_compile
from datetime import datetime

ROOT = Path.cwd()

service = ROOT / "services" / "rotativo_cobertura.py"
router = ROOT / "routers" / "rotativo_cobertura.py"

if not service.exists():
    raise FileNotFoundError(f"Não encontrado: {service}")

if not router.exists():
    raise FileNotFoundError(f"Não encontrado: {router}")

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

service_backup = service.with_name(
    f"{service.stem}_backup_valueerror_{timestamp}{service.suffix}"
)
router_backup = router.with_name(
    f"{router.stem}_backup_valueerror_{timestamp}{router.suffix}"
)

shutil.copy2(service, service_backup)
shutil.copy2(router, router_backup)

# ============================================================
# SERVICE
# ============================================================

service_text = service.read_text(encoding="utf-8")

# Adiciona import apenas se ainda não existir.
if "from domain.exceptions import BusinessRuleViolation" not in service_text:
    lines = service_text.splitlines()

    insert_at = 0
    while insert_at < len(lines):
        line = lines[insert_at].strip()
        if (
            line.startswith("from ")
            or line.startswith("import ")
            or line == ""
        ):
            insert_at += 1
            continue
        break

    lines.insert(
        insert_at,
        "from domain.exceptions import BusinessRuleViolation"
    )

    service_text = "\n".join(lines) + "\n"

qtd_service = service_text.count("raise ValueError")

if qtd_service != 7:
    raise RuntimeError(
        f"Esperados 7 'raise ValueError' em rotativo_cobertura.py, "
        f"mas foram encontrados {qtd_service}. "
        "Nenhuma alteração foi gravada."
    )

service_text = service_text.replace(
    "raise ValueError",
    "raise BusinessRuleViolation"
)

# ============================================================
# ROUTER
# ============================================================

router_text = router.read_text(encoding="utf-8")

if "from domain.exceptions import BusinessRuleViolation" not in router_text:
    alvo = (
        "from infrastructure.database.unit_of_work "
        "import SqlServerUnitOfWork"
    )

    if alvo not in router_text:
        raise RuntimeError(
            "Não encontrei o ponto esperado para inserir "
            "BusinessRuleViolation no router."
        )

    router_text = router_text.replace(
        alvo,
        alvo + "\nfrom domain.exceptions import BusinessRuleViolation",
        1
    )

if "except ValueError as erro:" not in router_text:
    raise RuntimeError(
        "Não encontrei 'except ValueError as erro:' no router. "
        "Nenhuma alteração foi gravada."
    )

router_text = router_text.replace(
    "except ValueError as erro:",
    "except BusinessRuleViolation as erro:",
    1
)

# ============================================================
# GRAVAÇÃO
# ============================================================

service.write_text(service_text, encoding="utf-8")
router.write_text(router_text, encoding="utf-8")

# ============================================================
# VALIDAÇÃO
# ============================================================

try:
    py_compile.compile(str(service), doraise=True)
    py_compile.compile(str(router), doraise=True)
except Exception:
    shutil.copy2(service_backup, service)
    shutil.copy2(router_backup, router)
    raise

restantes = service.read_text(encoding="utf-8").count(
    "raise ValueError"
)

if restantes != 0:
    shutil.copy2(service_backup, service)
    shutil.copy2(router_backup, router)
    raise RuntimeError(
        f"Ainda restaram {restantes} ValueError no service. "
        "Arquivos restaurados."
    )

print("APROVADO")
print()
print("Alterações:")
print("- services/rotativo_cobertura.py: 7 ValueError -> BusinessRuleViolation")
print("- routers/rotativo_cobertura.py: captura BusinessRuleViolation -> HTTP 400")
print("- Contrato HTTP preservado")
print()
print("Backups:")
print(service_backup)
print(router_backup)
