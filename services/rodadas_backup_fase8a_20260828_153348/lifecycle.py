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


def _finalizar_rodada_atual(
    cursor,
    id_inventario: int,
    id_rodada: int
):

    cursor.execute(
        """
        SELECT
            ID_Rodada,
            Status

        FROM dbo.RodadasInventario

        WHERE
            ID_Inventario = ?
            AND ID_Rodada = ?
        """,
        (
            id_inventario,
            id_rodada
        )
    )

    rodada = cursor.fetchone()

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

    cursor.execute(
        """
        UPDATE dbo.RodadasInventario

        SET
            Status = 'FINALIZADA',
            DataHoraFim = COALESCE(
                DataHoraFim,
                SYSDATETIME()
            )

        WHERE
            ID_Inventario = ?
            AND ID_Rodada = ?
            AND Status <> 'FINALIZADA'
        """,
        (
            id_inventario,
            id_rodada
        )
    )

    if cursor.rowcount == 0:

        raise HTTPException(
            status_code=400,
            detail=(
                "Não foi possível finalizar "
                "a rodada atual."
            )
        )

    return True
