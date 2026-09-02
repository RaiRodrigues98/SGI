from pathlib import Path
import shutil
import py_compile
from datetime import datetime

ROOT = Path.cwd()
contexto = ROOT / "services" / "rotativo_contexto.py"
orquestrador = ROOT / "services" / "rotativo_orquestrador.py"
router = ROOT / "routers" / "rotativo_ciclos.py"
arquivos = [contexto, orquestrador, router]

for arq in arquivos:
    if not arq.exists():
        raise FileNotFoundError(f"Não encontrado: {arq}")

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backups = {}
for arq in arquivos:
    backup = arq.with_name(f"{arq.stem}_backup_contexto_{timestamp}{arq.suffix}")
    shutil.copy2(arq, backup)
    backups[arq] = backup

def add_import(texto, import_line):
    if import_line in texto:
        return texto
    linhas = texto.splitlines()
    insert_at = 0
    while insert_at < len(linhas):
        linha = linhas[insert_at].strip()
        if linha.startswith("from ") or linha.startswith("import ") or linha == "" or linha.startswith("#"):
            insert_at += 1
            continue
        break
    linhas.insert(insert_at, import_line)
    return "\n".join(linhas) + "\n"

try:
    # 1) CONTEXTO
    texto = contexto.read_text(encoding="utf-8")
    qtd = texto.count("raise ValueError")
    if qtd != 5:
        raise RuntimeError(f"Esperados 5 raise ValueError em rotativo_contexto.py; encontrados {qtd}.")
    texto = add_import(texto, "from domain.exceptions import BusinessRuleViolation")
    texto = texto.replace("raise ValueError", "raise BusinessRuleViolation")
    contexto.write_text(texto, encoding="utf-8")

    # 2) ORQUESTRADOR - somente o catch da etapa de contexto
    texto = orquestrador.read_text(encoding="utf-8")
    texto = add_import(texto, "from domain.exceptions import BusinessRuleViolation")
    marcador = '"CONTEXTO_LOCALIZACAO"'
    pos_etapa = texto.find(marcador)
    if pos_etapa == -1:
        raise RuntimeError("Etapa CONTEXTO_LOCALIZACAO não encontrada no orquestrador.")
    pos_except = texto.rfind("except ValueError as erro:", 0, pos_etapa)
    if pos_except == -1 or pos_etapa - pos_except > 800:
        raise RuntimeError("Catch ValueError específico do contexto não localizado com segurança.")
    texto = texto[:pos_except] + texto[pos_except:].replace("except ValueError as erro:", "except (ValueError, BusinessRuleViolation) as erro:", 1)
    orquestrador.write_text(texto, encoding="utf-8")

    # 3) ROUTER - somente endpoint que chama montar_contexto_localizacao_rotativo
    texto = router.read_text(encoding="utf-8")
    texto = add_import(texto, "from domain.exceptions import BusinessRuleViolation")
    chamada = "montar_contexto_localizacao_rotativo("
    pos_chamada = texto.find(chamada)
    if pos_chamada == -1:
        raise RuntimeError("Chamada montar_contexto_localizacao_rotativo não encontrada no router.")
    pos_except = texto.find("except ValueError as erro:", pos_chamada)
    if pos_except == -1 or pos_except - pos_chamada > 2500:
        raise RuntimeError("Except ValueError do endpoint de contexto não localizado com segurança.")
    texto = texto[:pos_except] + texto[pos_except:].replace("except ValueError as erro:", "except BusinessRuleViolation as erro:", 1)
    router.write_text(texto, encoding="utf-8")

    # 4) COMPILAÇÃO
    for arq in arquivos:
        py_compile.compile(str(arq), doraise=True)

    if "raise ValueError" in contexto.read_text(encoding="utf-8"):
        raise RuntimeError("Ainda existe raise ValueError em rotativo_contexto.py.")
    if "except (ValueError, BusinessRuleViolation) as erro:" not in orquestrador.read_text(encoding="utf-8"):
        raise RuntimeError("Catch combinado não aplicado no orquestrador.")

except Exception:
    for arq, backup in backups.items():
        shutil.copy2(backup, arq)
    raise

print("APROVADO")
print("- rotativo_contexto.py: 5 ValueError -> BusinessRuleViolation")
print("- rotativo_orquestrador.py: catch específico do contexto atualizado")
print("- rotativo_ciclos.py: endpoint de contexto atualizado para HTTP 400 via BusinessRuleViolation")
print("- demais ValueError preservados")
print("Backups:")
for backup in backups.values():
    print(backup)
