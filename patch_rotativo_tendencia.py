from pathlib import Path
import shutil
import py_compile
from datetime import datetime

ROOT = Path.cwd()

service = ROOT / "services" / "rotativo_tendencia.py"
router = ROOT / "routers" / "rotativo_ciclos.py"

for arq in (service, router):
    if not arq.exists():
        raise FileNotFoundError(f"Não encontrado: {arq}")

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

backups = {}
for arq in (service, router):
    backup = arq.with_name(
        f"{arq.stem}_backup_tendencia_{timestamp}{arq.suffix}"
    )
    shutil.copy2(arq, backup)
    backups[arq] = backup


def garantir_import(texto, linha_import):
    if linha_import in texto:
        return texto

    linhas = texto.splitlines()
    insert_at = 0

    while insert_at < len(linhas):
        linha = linhas[insert_at].strip()

        if (
            linha == ""
            or linha.startswith("#")
            or linha.startswith("from ")
            or linha.startswith("import ")
        ):
            insert_at += 1
            continue

        break

    linhas.insert(insert_at, linha_import)
    return "\n".join(linhas) + "\n"


try:
    # ========================================================
    # SERVICE
    # ========================================================

    texto = service.read_text(encoding="utf-8")

    qtd = texto.count("raise ValueError")

    if qtd != 3:
        raise RuntimeError(
            f"Esperados exatamente 3 'raise ValueError' em "
            f"rotativo_tendencia.py; encontrados {qtd}."
        )

    texto = garantir_import(
        texto,
        "from domain.exceptions import BusinessRuleViolation"
    )

    texto = texto.replace(
        "raise ValueError",
        "raise BusinessRuleViolation"
    )

    service.write_text(texto, encoding="utf-8")

    # ========================================================
    # ROUTER - somente endpoint consultar_tendencias_rotativo
    # ========================================================

    texto = router.read_text(encoding="utf-8")

    texto = garantir_import(
        texto,
        "from domain.exceptions import BusinessRuleViolation"
    )

    chamada = "return consultar_tendencias_rotativo("

    pos_chamada = texto.find(chamada)

    if pos_chamada == -1:
        raise RuntimeError(
            "Chamada consultar_tendencias_rotativo não encontrada."
        )

    pos_except = texto.find(
        "except ValueError as erro:",
        pos_chamada
    )

    pos_business = texto.find(
        "except BusinessRuleViolation as erro:",
        pos_chamada
    )

    if pos_except != -1 and (
        pos_business == -1 or pos_except < pos_business
    ):
        if pos_except - pos_chamada > 2000:
            raise RuntimeError(
                "Except ValueError encontrado está distante demais "
                "do endpoint de tendências."
            )

        texto = (
            texto[:pos_except]
            + texto[pos_except:].replace(
                "except ValueError as erro:",
                "except BusinessRuleViolation as erro:",
                1
            )
        )

    elif pos_business == -1:
        raise RuntimeError(
            "Não encontrei o tratamento do endpoint de tendências."
        )

    router.write_text(texto, encoding="utf-8")

    # ========================================================
    # VALIDAÇÃO
    # ========================================================

    py_compile.compile(str(service), doraise=True)
    py_compile.compile(str(router), doraise=True)

    if "raise ValueError" in service.read_text(encoding="utf-8"):
        raise RuntimeError(
            "Ainda existe raise ValueError em rotativo_tendencia.py."
        )

except Exception:
    for arq, backup in backups.items():
        shutil.copy2(backup, arq)
    raise


print("APROVADO")
print()
print("Alterações:")
print("- services/rotativo_tendencia.py: 3 ValueError -> BusinessRuleViolation")
print("- routers/rotativo_ciclos.py: endpoint consultar_tendencias_rotativo")
print("  captura BusinessRuleViolation -> HTTP 400")
print("- mensagens e contrato HTTP preservados")
print()
print("Backups:")
for backup in backups.values():
    print(backup)
