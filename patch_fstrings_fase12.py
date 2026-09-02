from pathlib import Path
import shutil
import py_compile
from datetime import datetime

ROOT = Path.cwd()

arquivos = [
    ROOT / "services" / "encaminhamento_gestor.py",
    ROOT / "services" / "finalizacao_inventario.py",
    ROOT / "services" / "finalizacao_rotativo.py",
]

for arq in arquivos:
    if not arq.exists():
        raise FileNotFoundError(f"Não encontrado: {arq}")

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backups = {}

for arq in arquivos:
    backup = arq.with_name(
        f"{arq.stem}_backup_fstrings_{timestamp}{arq.suffix}"
    )
    shutil.copy2(arq, backup)
    backups[arq] = backup

substituicoes = {
    arquivos[0]: [
        (
            '"A quantidade de itens divergentes excede o limite configurado para encaminhamento antecipado ao gestor. Pendentes: {total_pendentes}. Limite: {limite_gestor}."',
            'f"A quantidade de itens divergentes excede o limite configurado para encaminhamento antecipado ao gestor. Pendentes: {total_pendentes}. Limite: {limite_gestor}."',
        ),
    ],
    arquivos[1]: [
        (
            '"Ainda existem {itens_sem_decisao} item(ns) sem decisão gerencial."',
            'f"Ainda existem {itens_sem_decisao} item(ns) sem decisão gerencial."',
        ),
        (
            '"Existem {nova_recontagem} item(ns) marcados para NOVA_RECONTAGEM."',
            'f"Existem {nova_recontagem} item(ns) marcados para NOVA_RECONTAGEM."',
        ),
        (
            '"O item {codigo} | {lote} não possui quantidade final gerencial definida."',
            'f"O item {codigo} | {lote} não possui quantidade final gerencial definida."',
        ),
        (
            '"Situação gerencial inválida para finalização do item {codigo} | {lote}: {situacao_gerencial}."',
            'f"Situação gerencial inválida para finalização do item {codigo} | {lote}: {situacao_gerencial}."',
        ),
    ],
    arquivos[2]: [
        (
            '"Existe divergência da R1 sem tratamento válido para encerramento antecipado. Localização: {localizacao}; Código: {codigo}; Lote: {lote}."',
            'f"Existe divergência da R1 sem tratamento válido para encerramento antecipado. Localização: {localizacao}; Código: {codigo}; Lote: {lote}."',
        ),
    ],
}

try:
    total = 0

    for arq, pares in substituicoes.items():
        texto = arq.read_text(encoding="utf-8")

        for antigo, novo in pares:
            qtd = texto.count(antigo)

            if qtd != 1:
                raise RuntimeError(
                    f"{arq.name}: esperado exatamente 1 ocorrência de:\n"
                    f"{antigo}\nEncontradas: {qtd}"
                )

            texto = texto.replace(antigo, novo, 1)
            total += 1

        arq.write_text(texto, encoding="utf-8")

    if total != 6:
        raise RuntimeError(
            f"Esperadas 6 correções; preparadas {total}."
        )

    for arq in arquivos:
        py_compile.compile(str(arq), doraise=True)

    # Valida que os literais defeituosos não sobraram.
    for arq, pares in substituicoes.items():
        texto = arq.read_text(encoding="utf-8")

        for antigo, novo in pares:
            if antigo in texto:
                raise RuntimeError(
                    f"{arq.name}: literal defeituoso ainda presente."
                )

            if novo not in texto:
                raise RuntimeError(
                    f"{arq.name}: f-string corrigida não encontrada."
                )

except Exception:
    for arq, backup in backups.items():
        shutil.copy2(backup, arq)
    raise


print("APROVADO")
print()
print("Correções realizadas: 6")
print("- encaminhamento_gestor.py: 1")
print("- finalizacao_inventario.py: 4")
print("- finalizacao_rotativo.py: 1")
print("- mensagens preservadas; apenas interpolação ativada")
print("- py_compile aprovado")
print()
print("Backups:")
for backup in backups.values():
    print(backup)
