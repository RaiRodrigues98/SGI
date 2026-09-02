from pathlib import Path
import shutil
import py_compile
from datetime import datetime

ROOT = Path.cwd()
service = ROOT / "services" / "rotativo_cobertura.py"
router = ROOT / "routers" / "rotativo_cobertura.py"

for arq in (service, router):
    if not arq.exists():
        raise FileNotFoundError(f"Não encontrado: {arq}")

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backups = {}

for arq in (service, router):
    backup = arq.with_name(
        f"{arq.stem}_backup_cobertura_{timestamp}{arq.suffix}"
    )
    shutil.copy2(arq, backup)
    backups[arq] = backup

try:
    # ========================================================
    # SERVICE
    # ========================================================
    texto = service.read_text(encoding="utf-8")

    qtd_value = texto.count("raise ValueError(")
    qtd_commit = texto.count("conn.commit()")
    qtd_rollback = texto.count("conn.rollback()")

    if qtd_value != 7:
        raise RuntimeError(
            "rotativo_cobertura.py: esperados exatamente "
            f"7 'raise ValueError('; encontrados {qtd_value}."
        )

    if qtd_commit != 1 or qtd_rollback != 1:
        raise RuntimeError(
            "Fronteira transacional inesperada em rotativo_cobertura.py: "
            f"commit={qtd_commit}, rollback={qtd_rollback}."
        )

    if "from domain.exceptions import BusinessRuleViolation" not in texto:
        texto = (
            "from domain.exceptions import BusinessRuleViolation\n"
            + texto
        )

    texto = texto.replace(
        "raise ValueError(",
        "raise BusinessRuleViolation("
    )

    # Preservar exatamente a fronteira operacional atual.
    if texto.count("conn.commit()") != 1:
        raise RuntimeError("Commit operacional foi alterado indevidamente.")

    if texto.count("conn.rollback()") != 1:
        raise RuntimeError("Rollback operacional foi alterado indevidamente.")

    # Garantir que a ordem estrutural continue:
    # commit -> etapa 5 inteligência
    pos_commit = texto.find("conn.commit()")
    pos_inteligencia = texto.find("# 5. ATUALIZAR INTELIGÊNCIA DO ROTATIVO")

    if pos_commit == -1 or pos_inteligencia == -1:
        raise RuntimeError(
            "Não foi possível validar a fronteira commit -> inteligência."
        )

    if pos_commit >= pos_inteligencia:
        raise RuntimeError(
            "A ordem commit operacional -> inteligência foi alterada."
        )

    service.write_text(texto, encoding="utf-8")

    # ========================================================
    # ROUTER
    # ========================================================
    texto = router.read_text(encoding="utf-8")

    if "from domain.exceptions import BusinessRuleViolation" not in texto:
        marcador = (
            "from infrastructure.database.unit_of_work import "
            "SqlServerUnitOfWork\n"
        )

        if marcador not in texto:
            raise RuntimeError(
                "Import SqlServerUnitOfWork não localizado no router."
            )

        texto = texto.replace(
            marcador,
            marcador + "\nfrom domain.exceptions import BusinessRuleViolation\n",
            1
        )

    qtd_catch = texto.count("except ValueError as erro:")

    if qtd_catch != 1:
        raise RuntimeError(
            "rotativo_cobertura.py router: esperado 1 "
            f"except ValueError; encontrado {qtd_catch}."
        )

    texto = texto.replace(
        "except ValueError as erro:",
        "except BusinessRuleViolation as erro:",
        1
    )

    router.write_text(texto, encoding="utf-8")

    # ========================================================
    # VALIDAÇÃO FINAL
    # ========================================================
    py_compile.compile(str(service), doraise=True)
    py_compile.compile(str(router), doraise=True)

    final_service = service.read_text(encoding="utf-8")
    final_router = router.read_text(encoding="utf-8")

    if "raise ValueError(" in final_service:
        raise RuntimeError(
            "Ainda existe raise ValueError no service."
        )

    if final_service.count("raise BusinessRuleViolation(") < 7:
        raise RuntimeError(
            "BusinessRuleViolation esperado não encontrado."
        )

    if final_service.count("conn.commit()") != 1:
        raise RuntimeError(
            "Validação final do commit falhou."
        )

    if final_service.count("conn.rollback()") != 1:
        raise RuntimeError(
            "Validação final do rollback falhou."
        )

    if "except ValueError as erro:" in final_router:
        raise RuntimeError(
            "Ainda existe except ValueError no router."
        )

except Exception:
    for arq, backup in backups.items():
        shutil.copy2(backup, arq)
    raise

print("APROVADO")
print()
print("services/rotativo_cobertura.py")
print("- 7 ValueError -> BusinessRuleViolation")
print("- 1 commit operacional preservado")
print("- 1 rollback operacional preservado")
print("- commit permanece ANTES da inteligência")
print()
print("routers/rotativo_cobertura.py")
print("- BusinessRuleViolation -> HTTP 400")
print()
print("Classificação:")
print("- rotativo_cobertura = INTENTIONAL BOUNDARY")
print("- motivo: commit operacional precede inteligência pós-conclusão")
print()
print("py_compile: APROVADO")
print()
print("Backups:")
for backup in backups.values():
    print(backup)
