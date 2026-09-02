"""
Operações de lifecycle de rodada.

Fase 5 da refatoração de services.rodadas_service.

Nesta fase, _finalizar_rodada_atual foi extraída junto com a
finalização ROTATIVO para evitar dependência circular entre o
orquestrador e o novo módulo de encerramento.

IMPORTANTE:
- refatoração exclusivamente estrutural;
- nenhuma regra de negócio alterada;
- SQL e assinatura preservados;
- commit continua sob a mesma responsabilidade existente.
"""

from fastapi import HTTPException

from services.rodadas.repositories.rodada_repository import (
    buscar_rodada_para_finalizacao,
    marcar_rodada_finalizada,
)


def _normalizar_texto(valor):

    if valor is None:
        return ""

    return str(valor).strip()


def _finalizar_rodada_atual(
    cursor,
    id_inventario: int,
    id_rodada: int
):

    rodada = (
        buscar_rodada_para_finalizacao(
            cursor=cursor,
            id_inventario=id_inventario,
            id_rodada=id_rodada
        )
    )

    if not rodada:

        raise HTTPException(
            status_code=404,
            detail="Rodada atual não encontrada."
        )

    status_atual = (
        _normalizar_texto(
            rodada.Status
        )
        .upper()
    )

    if status_atual == "CANCELADA":

        raise HTTPException(
            status_code=400,
            detail=(
                "Não é possível gerar uma próxima rodada "
                "a partir de uma rodada cancelada."
            )
        )

    if status_atual == "FINALIZADA":

        return False

    linhas_afetadas = (
        marcar_rodada_finalizada(
            cursor=cursor,
            id_inventario=id_inventario,
            id_rodada=id_rodada
        )
    )

    if linhas_afetadas == 0:

        raise HTTPException(
            status_code=400,
            detail=(
                "Não foi possível finalizar "
                "a rodada atual."
            )
        )

    return True
