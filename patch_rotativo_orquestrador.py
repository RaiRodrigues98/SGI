from pathlib import Path
import shutil
import py_compile
from datetime import datetime

ROOT = Path.cwd()

service = ROOT / "services" / "rotativo_orquestrador.py"
router = ROOT / "routers" / "rotativo_ciclos.py"

for arq in (service, router):
    if not arq.exists():
        raise FileNotFoundError(f"Não encontrado: {arq}")

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

backups = {}
for arq in (service, router):
    backup = arq.with_name(
        f"{arq.stem}_backup_orquestrador_{timestamp}{arq.suffix}"
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

    qtd_raises = texto.count("raise ValueError")

    if qtd_raises != 5:
        raise RuntimeError(
            f"Esperados exatamente 5 'raise ValueError' em "
            f"rotativo_orquestrador.py; encontrados {qtd_raises}."
        )

    texto = garantir_import(
        texto,
        "from domain.exceptions import BusinessRuleViolation"
    )

    # Migra somente os 5 raises próprios.
    texto = texto.replace(
        "raise ValueError",
        "raise BusinessRuleViolation"
    )

    # Corrige a captura interna do contexto.
    if "except (ValueError, BusinessRuleViolation) as erro:" not in texto:
        if "except ValueError as erro:" not in texto:
            raise RuntimeError(
                "Não encontrei o except ValueError da etapa "
                "CONTEXTO_LOCALIZACAO."
            )

        pos_etapa = texto.find('"CONTEXTO_LOCALIZACAO"')

        if pos_etapa == -1:
            raise RuntimeError(
                "Marcador CONTEXTO_LOCALIZACAO não encontrado."
            )

        pos_except = texto.rfind(
            "except ValueError as erro:",
            0,
            pos_etapa
        )

        if pos_except == -1:
            raise RuntimeError(
                "Except ValueError específico da etapa de contexto "
                "não localizado."
            )

        if pos_etapa - pos_except > 1000:
            raise RuntimeError(
                "Except encontrado está distante demais da etapa "
                "CONTEXTO_LOCALIZACAO."
            )

        texto = (
            texto[:pos_except]
            + texto[pos_except:].replace(
                "except ValueError as erro:",
                "except (ValueError, BusinessRuleViolation) as erro:",
                1
            )
        )

    service.write_text(texto, encoding="utf-8")

    # ========================================================
    # ROUTER
    # ========================================================

    texto = router.read_text(encoding="utf-8")

    texto = garantir_import(
        texto,
        "from domain.exceptions import BusinessRuleViolation"
    )

    chamada = "return executar_orquestracao_rotativo("

    pos_chamada = texto.find(chamada)

    if pos_chamada == -1:
        raise RuntimeError(
            "Chamada executar_orquestracao_rotativo não encontrada."
        )

    pos_except = texto.find(
        "except ValueError as erro:",
        pos_chamada
    )

    # Caso o router já tenha sido parcialmente migrado, aceita.
    pos_business = texto.find(
        "except BusinessRuleViolation as erro:",
        pos_chamada
    )

    if pos_except != -1 and (
        pos_business == -1 or pos_except < pos_business
    ):
        if pos_except - pos_chamada > 2500:
            raise RuntimeError(
                "Except ValueError encontrado está distante demais "
                "do endpoint de orquestração."
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
            "Não encontrei o tratamento do endpoint de orquestração."
        )

    router.write_text(texto, encoding="utf-8")

    # ========================================================
    # VALIDAÇÕES
    # ========================================================

    py_compile.compile(str(service), doraise=True)
    py_compile.compile(str(router), doraise=True)

    service_final = service.read_text(encoding="utf-8")
    router_final = router.read_text(encoding="utf-8")

    if "raise ValueError" in service_final:
        raise RuntimeError(
            "Ainda existe 'raise ValueError' em rotativo_orquestrador.py."
        )

    if (
        "except (ValueError, BusinessRuleViolation) as erro:"
        not in service_final
    ):
        raise RuntimeError(
            "Captura combinada da etapa CONTEXTO_LOCALIZACAO "
            "não foi aplicada."
        )

    pos_chamada = router_final.find(
        "return executar_orquestracao_rotativo("
    )
    pos_business = router_final.find(
        "except BusinessRuleViolation as erro:",
        pos_chamada
    )

    if pos_business == -1 or pos_business - pos_chamada > 2500:
        raise RuntimeError(
            "Endpoint de orquestração não está tratando "
            "BusinessRuleViolation."
        )

except Exception:
    for arq, backup in backups.items():
        shutil.copy2(backup, arq)
    raise


print("APROVADO")
print()
print("Alterações:")
print("- services/rotativo_orquestrador.py:")
print("  5 raise ValueError -> BusinessRuleViolation")
print("  CONTEXTO_LOCALIZACAO captura ValueError + BusinessRuleViolation")
print("- routers/rotativo_ciclos.py:")
print("  endpoint executar_orquestracao_rotativo captura")
print("  BusinessRuleViolation -> HTTP 400")
print("- mensagens e status HTTP preservados")
print()
print("Backups:")
for backup in backups.values():
    print(backup)
