from pathlib import Path
import shutil
import py_compile
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
    backup = arq.with_name(f"{arq.stem}_backup_uow_safe_{timestamp}{arq.suffix}")
    shutil.copy2(arq, backup)
    backups[arq] = backup


def restaurar():
    for arq, backup in backups.items():
        shutil.copy2(backup, arq)


def unwrap_transaction_blocks(texto):
    """
    Remove exatamente os dois wrappers:
        try:
            ...
        except Exception:
            conn.rollback()
            raise
    usando processamento por linhas, sem regex.
    """
    linhas = texto.splitlines(True)
    saida = []
    i = 0
    encontrados = 0

    while i < len(linhas):
        if linhas[i] == "    try:\n":
            j = i + 1

            # Procura o except correspondente no mesmo nível.
            while j < len(linhas):
                if linhas[j] == "    except Exception:\n":
                    if (
                        j + 2 < len(linhas)
                        and linhas[j + 1] == "        conn.rollback()\n"
                        and linhas[j + 2] == "        raise\n"
                    ):
                        body = linhas[i + 1:j]

                        # Só aceita body integralmente indentado dentro do try.
                        if body and all(
                            (linha.startswith("        ") or linha.strip() == "")
                            for linha in body
                        ):
                            for linha in body:
                                if linha.startswith("        "):
                                    saida.append(linha[4:])
                                else:
                                    saida.append(linha)

                            encontrados += 1
                            i = j + 3
                            break
                j += 1
            else:
                saida.append(linhas[i])
                i += 1

            if i == j + 3 if 'j' in locals() else False:
                continue
        else:
            saida.append(linhas[i])
            i += 1

    if encontrados != 2:
        raise RuntimeError(
            f"Esperados 2 wrappers transacionais; encontrados {encontrados}."
        )

    return "".join(saida)


try:
    texto = service.read_text(encoding="utf-8")

    ve = texto.count("raise ValueError(")
    brv = texto.count("raise BusinessRuleViolation(")
    commits = texto.count("conn.commit()")
    rollbacks = texto.count("conn.rollback()")

    if ve == 0 and commits == 0 and rollbacks == 0:
        if brv < 9:
            raise RuntimeError(
                "rotativo_fluxo parece migrado, mas há menos de 9 BRVs."
            )
        print("OK: services/rotativo_fluxo.py já estava migrado.")

    elif ve == 9 and commits == 2 and rollbacks == 2:
        if "from domain.exceptions import BusinessRuleViolation" not in texto:
            texto = "from domain.exceptions import BusinessRuleViolation\n" + texto

        texto = texto.replace(
            "raise ValueError(",
            "raise BusinessRuleViolation("
        )

        antigo = """def iniciar_localizacao_rotativo(
    conn,
    cursor,"""
        novo = """def iniciar_localizacao_rotativo(
    cursor,"""
        if texto.count(antigo) != 1:
            raise RuntimeError("Assinatura de iniciar não encontrada exatamente 1 vez.")
        texto = texto.replace(antigo, novo, 1)

        antigo = """def ignorar_localizacao_rotativo(
    conn,
    cursor,"""
        novo = """def ignorar_localizacao_rotativo(
    cursor,"""
        if texto.count(antigo) != 1:
            raise RuntimeError("Assinatura de ignorar não encontrada exatamente 1 vez.")
        texto = texto.replace(antigo, novo, 1)

        texto = unwrap_transaction_blocks(texto)

        if texto.count("    conn.commit()\n") != 2:
            raise RuntimeError("Os 2 commits esperados não foram encontrados após unwrap.")

        texto = texto.replace("    conn.commit()\n", "")

        if "conn.commit()" in texto or "conn.rollback()" in texto:
            raise RuntimeError("Ainda existe commit/rollback no service.")

        service.write_text(texto, encoding="utf-8")

        texto = router.read_text(encoding="utf-8")

        marcador = "from infrastructure.database.unit_of_work import SqlServerUnitOfWork\n"
        if marcador not in texto:
            raise RuntimeError("Import SqlServerUnitOfWork não encontrado.")

        if "from domain.exceptions import BusinessRuleViolation" not in texto:
            texto = texto.replace(
                marcador,
                marcador + "\nfrom domain.exceptions import BusinessRuleViolation\n",
                1,
            )

        antigo = """        return iniciar_localizacao_rotativo(
            conn=conn,
            cursor=cursor,"""
        novo = """        resultado = iniciar_localizacao_rotativo(
            cursor=cursor,"""
        if texto.count(antigo) != 1:
            raise RuntimeError("Chamada antiga de iniciar não encontrada exatamente 1 vez.")
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
            raise RuntimeError("Fechamento antigo do endpoint iniciar não encontrado.")
        texto = texto.replace(antigo, novo, 1)

        antigo = """        return ignorar_localizacao_rotativo(
            conn=conn,
            cursor=cursor,"""
        novo = """        resultado = ignorar_localizacao_rotativo(
            cursor=cursor,"""
        if texto.count(antigo) != 1:
            raise RuntimeError("Chamada antiga de ignorar não encontrada exatamente 1 vez.")
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
            raise RuntimeError("Fechamento antigo do endpoint ignorar não encontrado.")
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
                f"Esperados 2 blocos Exception; encontrados {texto.count(bloco_generico)}."
            )
        texto = texto.replace(bloco_generico, bloco_generico_novo)

        router.write_text(texto, encoding="utf-8")

    # Validação final independente do estado inicial.
    st = service.read_text(encoding="utf-8")
    rt = router.read_text(encoding="utf-8")

    if st.count("raise ValueError(") != 0:
        raise RuntimeError("Ainda existe ValueError no service.")
    if st.count("raise BusinessRuleViolation(") < 9:
        raise RuntimeError("BRVs incompletos no service.")
    if "conn.commit()" in st or "conn.rollback()" in st:
        raise RuntimeError("Service ainda possui transação interna.")
    if "def iniciar_localizacao_rotativo(\n    conn," in st:
        raise RuntimeError("conn ainda existe na assinatura iniciar.")
    if "def ignorar_localizacao_rotativo(\n    conn," in st:
        raise RuntimeError("conn ainda existe na assinatura ignorar.")

    if rt.count("uow.commit()") != 2:
        raise RuntimeError(
            f"Router: esperados 2 commits; encontrados {rt.count('uow.commit()')}."
        )
    if rt.count("uow.rollback()") != 4:
        raise RuntimeError(
            f"Router: esperados 4 rollbacks; encontrados {rt.count('uow.rollback()')}."
        )
    if "except ValueError as erro:" in rt:
        raise RuntimeError("Router ainda possui catch ValueError.")

    py_compile.compile(str(service), doraise=True)
    py_compile.compile(str(router), doraise=True)

except BaseException:
    restaurar()
    print("REPROVADO: arquivos de rotativo_fluxo restaurados.")
    raise

print()
print("APROVADO")
print("- rotativo_fluxo migrado/validado sem regex pesado")
print("- transaction ownership no UoW/router")
print("- BusinessRuleViolation preservado")
print("- py_compile aprovado")
print()
print("Backups:")
for backup in backups.values():
    print(backup)
