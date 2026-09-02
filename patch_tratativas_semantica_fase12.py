from pathlib import Path
import ast
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


def funcoes_que_chamam(texto, nome_chamada):
    tree = ast.parse(texto)
    resultado = []
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for interno in ast.walk(node):
            if (
                isinstance(interno, ast.Call)
                and isinstance(interno.func, ast.Name)
                and interno.func.id == nome_chamada
            ):
                resultado.append(node)
                break
    return resultado


def extrair(texto, node):
    linhas = texto.splitlines(True)
    return "".join(linhas[node.lineno - 1:node.end_lineno])


def substituir(texto, node, novo):
    linhas = texto.splitlines(True)
    return (
        "".join(linhas[:node.lineno - 1])
        + novo
        + "".join(linhas[node.end_lineno:])
    )


try:
    # ========================================================
    # SERVICE — RESTAURAR FASE 11
    # ========================================================
    texto = service.read_text(encoding="utf-8")

    qtd_value = texto.count("raise ValueError(")
    if qtd_value != 16:
        raise RuntimeError(
            "rotativo_tratativas.py: eram esperados exatamente "
            f"16 'raise ValueError('; encontrados {qtd_value}. "
            "Nenhuma alteração foi aplicada."
        )

    commits_antes = texto.count("conn.commit()")
    rollbacks_antes = texto.count("conn.rollback()")

    if commits_antes != 1 or rollbacks_antes != 2:
        raise RuntimeError(
            "Fronteira transacional inesperada em rotativo_tratativas.py: "
            f"commit={commits_antes}, rollback={rollbacks_antes}. "
            "Patch cancelado para não alterar semântica."
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

    # A fronteira de commit/rollback deve permanecer exatamente igual.
    if texto.count("conn.commit()") != commits_antes:
        raise RuntimeError("Quantidade de commits foi alterada indevidamente.")
    if texto.count("conn.rollback()") != rollbacks_antes:
        raise RuntimeError("Quantidade de rollbacks foi alterada indevidamente.")

    if "raise ValueError(" in texto:
        raise RuntimeError(
            "Ainda existe raise ValueError em rotativo_tratativas.py."
        )

    service.write_text(texto, encoding="utf-8")

    # ========================================================
    # ROUTER — SOMENTE ENDPOINTS DE TRATATIVAS
    # ========================================================
    texto = router.read_text(encoding="utf-8")

    marcador = (
        "from infrastructure.database.unit_of_work import "
        "SqlServerUnitOfWork\n"
    )
    if "from domain.exceptions import BusinessRuleViolation" not in texto:
        if marcador not in texto:
            raise RuntimeError(
                "Import do SqlServerUnitOfWork não localizado no router."
            )
        texto = texto.replace(
            marcador,
            marcador + "\nfrom domain.exceptions import BusinessRuleViolation\n",
            1
        )

    chamadas = [
        "consultar_tratativas_rotativo",
        "resolver_ocorrencia_rotativo",
    ]

    for chamada in chamadas:
        funcoes = funcoes_que_chamam(texto, chamada)
        if len(funcoes) != 1:
            raise RuntimeError(
                f"Esperada 1 função de router chamando {chamada}; "
                f"encontradas {len(funcoes)}."
            )

        node = funcoes[0]
        trecho = extrair(texto, node)

        qtd = trecho.count("except ValueError as erro:")
        if qtd != 1:
            raise RuntimeError(
                f"{chamada}: esperado 1 except ValueError; encontrado {qtd}."
            )

        trecho = trecho.replace(
            "except ValueError as erro:",
            "except BusinessRuleViolation as erro:",
            1
        )

        texto = substituir(texto, node, trecho)

    router.write_text(texto, encoding="utf-8")

    # ========================================================
    # VALIDAÇÃO
    # ========================================================
    py_compile.compile(str(service), doraise=True)
    py_compile.compile(str(router), doraise=True)

    final_service = service.read_text(encoding="utf-8")

    if final_service.count("raise BusinessRuleViolation(") < 16:
        raise RuntimeError(
            "Validação final: BusinessRuleViolation insuficiente."
        )

    if final_service.count("conn.commit()") != 1:
        raise RuntimeError(
            "Validação final: commit da tratativa foi alterado."
        )

    if final_service.count("conn.rollback()") != 2:
        raise RuntimeError(
            "Validação final: rollbacks da tratativa foram alterados."
        )

except Exception:
    for arq, backup in backups.items():
        shutil.copy2(backup, arq)
    raise

print("APROVADO")
print()
print("services/rotativo_tratativas.py")
print("- 16 ValueError -> BusinessRuleViolation")
print("- 1 commit preservado")
print("- 2 rollbacks preservados")
print("- fronteira pós-commit/inteligência NÃO foi alterada")
print()
print("routers/rotativo_ciclos.py")
print("- consultar_tratativas_rotativo: catch -> BusinessRuleViolation")
print("- resolver_ocorrencia_rotativo: catch -> BusinessRuleViolation")
print("- demais endpoints não foram alterados por este patch")
print()
print("py_compile: APROVADO")
print()
print("Backups:")
for backup in backups.values():
    print(backup)
