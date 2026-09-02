"""
Operações de itens vinculados às rodadas.

Fase 1 da refatoração de services.rodadas_service.

IMPORTANTE:
- extração estrutural;
- nenhuma regra de negócio alterada;
- SQL preservado;
- assinatura das funções preservada.
"""


def _normalizar_texto(valor):

    if valor is None:
        return ""

    return str(valor).strip()


def _normalizar_lote(valor):

    return _normalizar_texto(valor)


def _inserir_rodada_item(
    cursor,
    id_inventario: int,
    id_rodada: int,
    codigo: str,
    lote: str,
    motivo: str
):

    codigo = _normalizar_texto(
        codigo
    )

    lote = _normalizar_lote(
        lote
    )

    cursor.execute(
        """
        IF NOT EXISTS
        (
            SELECT 1

            FROM dbo.RodadaItens

            WHERE
                ID_Inventario = ?
                AND ID_Rodada = ?

                AND LTRIM(
                    RTRIM(Codigo)
                ) = ?

                AND ISNULL(
                    LTRIM(
                        RTRIM(Lote)
                    ),
                    ''
                ) = ?
        )
        BEGIN

            INSERT INTO dbo.RodadaItens
            (
                ID_Inventario,
                ID_Rodada,
                Codigo,
                Lote,
                Motivo,
                Status
            )

            VALUES
            (
                ?,
                ?,
                ?,
                ?,
                ?,
                'PENDENTE'
            )

        END
        """,
        (
            id_inventario,
            id_rodada,
            codigo,
            lote,

            id_inventario,
            id_rodada,
            codigo,
            lote,
            motivo
        )
    )
