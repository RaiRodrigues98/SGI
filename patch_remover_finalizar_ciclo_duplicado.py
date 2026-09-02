from pathlib import Path
import shutil
import py_compile
from datetime import datetime

ROOT = Path.cwd()
service = ROOT / "services" / "ciclos_rotativo.py"

if not service.exists():
    raise FileNotFoundError(f"Não encontrado: {service}")

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup = service.with_name(
    f"{service.stem}_backup_remove_finalizar_duplicado_{timestamp}{service.suffix}"
)

shutil.copy2(service, backup)

try:
    texto = service.read_text(encoding="utf-8")

    assinatura = "def finalizar_ciclo_rotativo("

    posicoes = []
    inicio = 0

    while True:
        pos = texto.find(assinatura, inicio)
        if pos == -1:
            break
        posicoes.append(pos)
        inicio = pos + len(assinatura)

    if len(posicoes) != 2:
        raise RuntimeError(
            "Estrutura inesperada: esperadas exatamente 2 definições de "
            f"finalizar_ciclo_rotativo; encontradas {len(posicoes)}."
        )

    primeira_def = posicoes[0]
    segunda_def = posicoes[1]

    # Localiza o cabeçalho imediatamente anterior à primeira definição.
    cabecalho = (
        "# ============================================================\n"
        "# FINALIZAR CICLO ROTATIVO\n"
        "# ============================================================\n"
    )

    inicio_bloco = texto.rfind(
        cabecalho,
        0,
        primeira_def
    )

    if inicio_bloco == -1:
        # Fallback: remove a partir da própria primeira definição.
        inicio_bloco = primeira_def

    # Localiza o cabeçalho imediatamente anterior à segunda definição.
    inicio_segundo_bloco = texto.rfind(
        cabecalho,
        primeira_def,
        segunda_def
    )

    if inicio_segundo_bloco == -1:
        inicio_segundo_bloco = segunda_def

    if inicio_segundo_bloco <= inicio_bloco:
        raise RuntimeError(
            "Não foi possível delimitar com segurança as duas implementações."
        )

    bloco_removido = texto[inicio_bloco:inicio_segundo_bloco]

    # Proteções: a primeira implementação conhecida é a versão incompleta.
    marcadores_esperados = (
        "CICLO_COM_LOCALIZACOES_ABERTAS",
        "STATUS_LOCALIZACAO_NAO_RECONHECIDO",
        "COBERTURA_INCONSISTENTE",
    )

    for marcador in marcadores_esperados:
        if marcador not in bloco_removido:
            raise RuntimeError(
                f"O primeiro bloco não contém o marcador esperado: {marcador}"
            )

    # A implementação morta não deve executar a finalização persistente.
    if "UPDATE dbo.CiclosRotativo" in bloco_removido:
        raise RuntimeError(
            "Proteção acionada: a primeira implementação contém UPDATE. "
            "Nada foi alterado."
        )

    texto_novo = (
        texto[:inicio_bloco]
        + texto[inicio_segundo_bloco:]
    )

    if texto_novo.count(assinatura) != 1:
        raise RuntimeError(
            "Após a limpeza deveria existir exatamente uma definição "
            "de finalizar_ciclo_rotativo."
        )

    # Confirma que a implementação sobrevivente é a versão funcional.
    segunda_atual = texto_novo.find(assinatura)

    trecho_sobrevivente = texto_novo[segunda_atual:]

    if "UPDATE dbo.CiclosRotativo" not in trecho_sobrevivente:
        raise RuntimeError(
            "A implementação sobrevivente não contém o UPDATE esperado."
        )

    if "Status = 'CONCLUIDO'" not in trecho_sobrevivente:
        raise RuntimeError(
            "A implementação sobrevivente não contém Status = 'CONCLUIDO'."
        )

    service.write_text(
        texto_novo,
        encoding="utf-8"
    )

    py_compile.compile(
        str(service),
        doraise=True
    )

except Exception:
    shutil.copy2(backup, service)
    raise


print("APROVADO")
print()
print("Alterações:")
print("- removida somente a primeira definição morta de finalizar_ciclo_rotativo")
print("- segunda implementação preservada integralmente")
print("- nenhuma regra de negócio alterada")
print("- nenhum endpoint alterado")
print("- py_compile aprovado")
print()
print(f"Backup: {backup}")
