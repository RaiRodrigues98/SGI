from pathlib import Path
import shutil
import py_compile
import re
from datetime import datetime

ROOT = Path.cwd()
service = ROOT / "services" / "rotativo_fluxo.py"
router = ROOT / "routers" / "rotativo_fluxo.py"

for arq in (service, router):
    if not arq.exists():
        raise FileNotFoundError(f"Não encontrado: {arq}")

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backups = {}

for arq in (service, router):
    backup = arq.with_name(f"{arq.stem}_backup_uow_{timestamp}{arq.suffix}")
    shutil.copy2(arq, backup)
    backups[arq] = backup

try:
    texto = service.read_text(encoding="utf-8")

    qtd_value_error = texto.count("raise ValueError(")
    if qtd_value_error != 9:
        raise RuntimeError(
            f"rotativo_fluxo.py: esperados 9 ValueError; encontrados {qtd_value_error}."
        )

    if "from domain.exceptions import BusinessRuleViolation" not in texto:
        texto = "from domain.exceptions import BusinessRuleViolation\n" + texto

    texto = texto.replace("raise ValueError(", "raise BusinessRuleViolation(")

    texto, n1 = re.subn(
        r"def iniciar_localizacao_rotativo\(\n    conn,\n    cursor,",
        "def iniciar_localizacao_rotativo(\n    cursor,",
        texto,
        count=1,
    )
    if n1 != 1:
        raise RuntimeError("Não foi possível remover conn da função iniciar.")

    texto, n2 = re.subn(
        r"def ignorar_localizacao_rotativo\(\n    conn,\n    cursor,",
        "def ignorar_localizacao_rotativo(\n    cursor,",
        texto,
        count=1,
    )
    if n2 != 1:
        raise RuntimeError("Não foi possível remover conn da função ignorar.")

    padrao_tx = re.compile(
        r"(?ms)^    try:\n"
        r"(?P<body>(?:^        .*\n|^$\n)+?)"
        r"^    except Exception:\n"
        r"^        conn\.rollback\(\)\n"
        r"^        raise\n"
    )

    encontrados = list(padrao_tx.finditer(texto))
    if len(encontrados) != 2:
        raise RuntimeError(
            f"Esperados 2 blocos transacionais try/except; encontrados {len(encontrados)}."
        )

    def remover_wrapper(match):
        body = match.group("body")
        saida = []
        for linha in body.splitlines(True):
            if linha.startswith("        "):
                linha = linha[4:]
            saida.append(linha)
        return "".join(saida)

    texto = padrao_tx.sub(remover_wrapper, texto)

    qtd_commit = texto.count("    conn.commit()\n")
    if qtd_commit != 2:
        raise RuntimeError(
            f"Esperados 2 commits no service; encontrados {qtd_commit}."
        )

    texto = texto.replace("    conn.commit()\n", "")

    if "conn.commit()" in texto or "conn.rollback()" in texto:
        raise RuntimeError("Ainda existe commit/rollback no service.")

    if "raise ValueError(" in texto:
        raise RuntimeError("Ainda existe ValueError no service.")

    service.write_text(texto, encoding="utf-8")

    texto = router.read_text(encoding="utf-8")

    marcador = "from infrastructure.database.unit_of_work import SqlServerUnitOfWork\n"
    if marcador not in texto:
        raise RuntimeError("Import do SqlServerUnitOfWork não encontrado.")

    if "from domain.exceptions import BusinessRuleViolation" not in texto:
        texto = texto.replace(
            marcador,
            marcador + "\nfrom domain.exceptions import BusinessRuleViolation\n",
            1,
        )

    antigo = """        return iniciar_localizacao_rotativo(
            conn=conn,
            cursor=cursor,
"""
    novo = """        resultado = iniciar_localizacao_rotativo(
            cursor=cursor,
"""
    if texto.count(antigo) != 1:
        raise RuntimeError("Chamada de iniciar_localizacao_rotativo não encontrada.")
    texto = texto.replace(antigo, novo, 1)

    antigo = """            usuario=dados.usuario
        )

    except ValueError as erro:
"""
    novo = """            usuario=dados.usuario
        )

        uow.commit()
        return resultado

    except BusinessRuleViolation as erro:
        if conn:
            uow.rollback()

"""
    if texto.count(antigo) < 1:
        raise RuntimeError("Fechamento do endpoint iniciar não encontrado.")
    texto = texto.replace(antigo, novo, 1)

    antigo = """        return ignorar_localizacao_rotativo(
            conn=conn,
            cursor=cursor,
"""
    novo = """        resultado = ignorar_localizacao_rotativo(
            cursor=cursor,
"""
    if texto.count(antigo) != 1:
        raise RuntimeError("Chamada de ignorar_localizacao_rotativo não encontrada.")
    texto = texto.replace(antigo, novo, 1)

    antigo = """            usuario=dados.usuario
        )

    except ValueError as erro:
"""
    novo = """            usuario=dados.usuario
        )

        uow.commit()
        return resultado

    except BusinessRuleViolation as erro:
        if conn:
            uow.rollback()

"""
    if texto.count(antigo) != 1:
        raise RuntimeError("Fechamento do endpoint ignorar não encontrado.")
    texto = texto.replace(antigo, novo, 1)

    bloco_generico = """    except Exception as erro:
        raise HTTPException(
            status_code=500,
            detail=str(erro)
        )
"""
    bloco_generico_novo = """    except Exception as erro:
        if conn:
            uow.rollback()

        raise HTTPException(
            status_code=500,
            detail=str(erro)
        )
"""

    if texto.count(bloco_generico) != 2:
        raise RuntimeError(
            f"Esperados 2 blocos Exception no router; encontrados {texto.count(bloco_generico)}."
        )

    texto = texto.replace(bloco_generico, bloco_generico_novo)

    if "except ValueError as erro:" in texto:
        raise RuntimeError("Ainda existe catch de ValueError no router.")

    if texto.count("uow.commit()") != 2:
        raise RuntimeError(
            f"Esperados 2 commits no router; encontrados {texto.count('uow.commit()')}."
        )

    if texto.count("uow.rollback()") != 4:
        raise RuntimeError(
            f"Esperados 4 rollbacks no router; encontrados {texto.count('uow.rollback()')}."
        )

    router.write_text(texto, encoding="utf-8")

    py_compile.compile(str(service), doraise=True)
    py_compile.compile(str(router), doraise=True)

except Exception:
    for arq, backup in backups.items():
        shutil.copy2(backup, arq)
    raise

print("APROVADO")
print()
print("Alterações:")
print("- 9 ValueError -> BusinessRuleViolation")
print("- commit/rollback removidos de services/rotativo_fluxo.py")
print("- parâmetro conn removido das 2 funções do service")
print("- 2 commits movidos para routers/rotativo_fluxo.py")
print("- rollback no router para erro de negócio e erro técnico")
print("- HTTP 400/500 preservados")
print("- py_compile aprovado")
print()
print("Backups:")
for backup in backups.values():
    print(backup)
