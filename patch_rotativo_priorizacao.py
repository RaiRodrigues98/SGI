from pathlib import Path
import shutil
import py_compile
from datetime import datetime

ROOT = Path.cwd()
service = ROOT / "services" / "rotativo_priorizacao.py"
router = ROOT / "routers" / "rotativo_priorizacao.py"

for arq in (service, router):
    if not arq.exists():
        raise FileNotFoundError(f"Não encontrado: {arq}")

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backups = {}

for arq in (service, router):
    backup = arq.with_name(f"{arq.stem}_backup_priorizacao_{timestamp}{arq.suffix}")
    shutil.copy2(arq, backup)
    backups[arq] = backup

def garantir_import(texto, linha_import):
    if linha_import in texto:
        return texto
    linhas = texto.splitlines()
    insert_at = 0
    while insert_at < len(linhas):
        linha = linhas[insert_at].strip()
        if linha == "" or linha.startswith("#") or linha.startswith("from ") or linha.startswith("import "):
            insert_at += 1
            continue
        break
    linhas.insert(insert_at, linha_import)
    return "\n".join(linhas) + "\n"

try:
    texto = service.read_text(encoding="utf-8")
    qtd = texto.count("raise ValueError")
    if qtd != 4:
        raise RuntimeError(
            f"Esperados exatamente 4 'raise ValueError' em rotativo_priorizacao.py; encontrados {qtd}."
        )

    texto = garantir_import(texto, "from domain.exceptions import BusinessRuleViolation")
    texto = texto.replace("raise ValueError", "raise BusinessRuleViolation")
    service.write_text(texto, encoding="utf-8")

    texto = router.read_text(encoding="utf-8")
    texto = garantir_import(texto, "from domain.exceptions import BusinessRuleViolation")

    chamada = "return recalcular_priorizacao_rotativo("
    pos_chamada = texto.find(chamada)
    if pos_chamada == -1:
        raise RuntimeError("Chamada recalcular_priorizacao_rotativo não encontrada.")

    pos_except_value = texto.find("except ValueError as erro:", pos_chamada)
    pos_except_business = texto.find("except BusinessRuleViolation as erro:", pos_chamada)

    if pos_except_value != -1 and (pos_except_business == -1 or pos_except_value < pos_except_business):
        if pos_except_value - pos_chamada > 2500:
            raise RuntimeError("Except ValueError encontrado está distante demais do endpoint de priorização.")
        texto = (
            texto[:pos_except_value]
            + texto[pos_except_value:].replace(
                "except ValueError as erro:",
                "except BusinessRuleViolation as erro:",
                1
            )
        )
    elif pos_except_business == -1:
        raise RuntimeError(
            "Não encontrei tratamento ValueError/BusinessRuleViolation no endpoint de priorização."
        )

    router.write_text(texto, encoding="utf-8")

    py_compile.compile(str(service), doraise=True)
    py_compile.compile(str(router), doraise=True)

    service_final = service.read_text(encoding="utf-8")
    router_final = router.read_text(encoding="utf-8")

    if "raise ValueError" in service_final:
        raise RuntimeError("Ainda existe raise ValueError em rotativo_priorizacao.py.")

    pos_chamada = router_final.find(chamada)
    pos_except_business = router_final.find("except BusinessRuleViolation as erro:", pos_chamada)
    if pos_except_business == -1 or pos_except_business - pos_chamada > 2500:
        raise RuntimeError("Endpoint de priorização não trata BusinessRuleViolation corretamente.")

except Exception:
    for arq, backup in backups.items():
        shutil.copy2(backup, arq)
    raise

print("APROVADO")
print("- services/rotativo_priorizacao.py: 4 ValueError -> BusinessRuleViolation")
print("- routers/rotativo_priorizacao.py: endpoint de recálculo -> BusinessRuleViolation / HTTP 400")
print("- mensagens preservadas; backups criados; py_compile aprovado")
