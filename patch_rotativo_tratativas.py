from pathlib import Path
import shutil
import py_compile
from datetime import datetime

ROOT = Path.cwd()

service = ROOT / "services" / "rotativo_tratativas.py"
router = ROOT / "routers" / "rotativo_ciclos.py"

for arq in (service, router):
    if not arq.exists():
        raise FileNotFoundError(f"Não encontrado: {arq}")

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backups = {}

for arq in (service, router):
    backup = arq.with_name(
        f"{arq.stem}_backup_tratativas_{timestamp}{arq.suffix}"
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


def substituir_except_apos_chamada(
    texto,
    chamada,
    distancia_max=3000
):
    pos_chamada = texto.find(chamada)

    if pos_chamada == -1:
        raise RuntimeError(
            f"Chamada não encontrada no router: {chamada}"
        )

    pos_value = texto.find(
        "except ValueError as erro:",
        pos_chamada
    )

    pos_business = texto.find(
        "except BusinessRuleViolation as erro:",
        pos_chamada
    )

    if pos_value != -1 and (
        pos_business == -1
        or pos_value < pos_business
    ):
        if pos_value - pos_chamada > distancia_max:
            raise RuntimeError(
                f"Except ValueError distante demais de {chamada}"
            )

        texto = (
            texto[:pos_value]
            + texto[pos_value:].replace(
                "except ValueError as erro:",
                "except BusinessRuleViolation as erro:",
                1
            )
        )

        return texto

    if (
        pos_business != -1
        and pos_business - pos_chamada <= distancia_max
    ):
        return texto

    raise RuntimeError(
        f"Tratamento ValueError/BusinessRuleViolation "
        f"não encontrado após {chamada}"
    )


try:
    # ========================================================
    # SERVICE
    # ========================================================

    texto = service.read_text(encoding="utf-8")

    qtd = texto.count("raise ValueError")

    if qtd != 16:
        raise RuntimeError(
            f"Esperados exatamente 16 'raise ValueError' em "
            f"rotativo_tratativas.py; encontrados {qtd}."
        )

    texto = garantir_import(
        texto,
        "from domain.exceptions import BusinessRuleViolation"
    )

    texto = texto.replace(
        "raise ValueError",
        "raise BusinessRuleViolation"
    )

    service.write_text(
        texto,
        encoding="utf-8"
    )

    # ========================================================
    # ROUTER
    # ========================================================

    texto = router.read_text(
        encoding="utf-8"
    )

    texto = garantir_import(
        texto,
        "from domain.exceptions import BusinessRuleViolation"
    )

    texto = substituir_except_apos_chamada(
        texto,
        "return consultar_tratativas_rotativo("
    )

    texto = substituir_except_apos_chamada(
        texto,
        "return resolver_ocorrencia_rotativo("
    )

    router.write_text(
        texto,
        encoding="utf-8"
    )

    # ========================================================
    # VALIDAÇÃO
    # ========================================================

    py_compile.compile(
        str(service),
        doraise=True
    )

    py_compile.compile(
        str(router),
        doraise=True
    )

    service_final = service.read_text(
        encoding="utf-8"
    )

    router_final = router.read_text(
        encoding="utf-8"
    )

    if "raise ValueError" in service_final:
        raise RuntimeError(
            "Ainda existe raise ValueError "
            "em rotativo_tratativas.py."
        )

    if service_final.count(
        "raise BusinessRuleViolation"
    ) < 16:
        raise RuntimeError(
            "Nem todas as 16 ocorrências foram migradas."
        )

    for chamada in (
        "return consultar_tratativas_rotativo(",
        "return resolver_ocorrencia_rotativo("
    ):
        pos = router_final.find(chamada)

        pos_brv = router_final.find(
            "except BusinessRuleViolation as erro:",
            pos
        )

        if (
            pos == -1
            or pos_brv == -1
            or pos_brv - pos > 3000
        ):
            raise RuntimeError(
                f"Endpoint não trata BusinessRuleViolation: "
                f"{chamada}"
            )

except Exception:
    for arq, backup in backups.items():
        shutil.copy2(
            backup,
            arq
        )
    raise


print("APROVADO")
print()
print("Alterações:")
print(
    "- services/rotativo_tratativas.py: "
    "16 ValueError -> BusinessRuleViolation"
)
print(
    "- routers/rotativo_ciclos.py: "
    "consultar_tratativas_rotativo -> BusinessRuleViolation / HTTP 400"
)
print(
    "- routers/rotativo_ciclos.py: "
    "resolver_ocorrencia_rotativo -> BusinessRuleViolation / HTTP 400"
)
print(
    "- mensagens e contrato HTTP preservados"
)
print(
    "- backups criados"
)
print(
    "- py_compile aprovado"
)
print()
print("Backups:")
for backup in backups.values():
    print(backup)
