"""
Repository SQL Server para dbo.RodadaItens.

Somente persistência. Não executa commit/rollback.
"""


def inserir_item_se_ausente(
    cursor,
    id_inventario: int,
    id_rodada: int,
    codigo: str,
    lote: str,
    motivo: str
):

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


def listar_itens_da_rodada(
    cursor,
    id_inventario: int,
    id_rodada: int
):

    cursor.execute(
        """
        SELECT
            Codigo,

            ISNULL(
                Lote,
                ''
            ) AS Lote

        FROM dbo.RodadaItens

        WHERE
            ID_Inventario = ?
            AND ID_Rodada = ?

        ORDER BY
            Codigo,
            Lote
        """,
        (
            id_inventario,
            id_rodada
        )
    )

    return cursor.fetchall()
