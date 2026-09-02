"""
Repository SQL Server para dbo.Inventarios.

Fase 8D.

Responsabilidades:
- atualizar a rodada atual do inventário;
- finalizar ROTATIVO pela R1;
- finalizar ROTATIVO pela R2.

Somente persistência. Sem controle transacional.
"""


def atualizar_rodada_atual(
    cursor,
    id_inventario: int,
    numero_rodada: int
):

    cursor.execute(
        """
        UPDATE dbo.Inventarios

        SET
            RodadaAtual = ?

        WHERE
            ID_Inventario = ?
        """,
        (
            numero_rodada,
            id_inventario
        )
    )


def finalizar_rotativo_pela_r1(
    cursor,
    id_inventario: int
):

    cursor.execute(
        """
        UPDATE dbo.Inventarios

        SET
            Status = 'FINALIZADO',

            RodadaAtual = 1,

            DataHoraFim = COALESCE(
                DataHoraFim,
                SYSDATETIME()
            ),

            FinalizadoPor = COALESCE(
                NULLIF(
                    LTRIM(
                        RTRIM(FinalizadoPor)
                    ),
                    ''
                ),
                'sistema'
            )

        WHERE
            ID_Inventario = ?
            AND ISNULL(Status, '') <> 'FINALIZADO'
        """,
        id_inventario
    )

    return cursor.rowcount


def finalizar_rotativo_pela_r2(
    cursor,
    id_inventario: int
):

    cursor.execute(
        """
        UPDATE dbo.Inventarios

        SET
            Status = 'FINALIZADO',
            RodadaAtual = 2,

            DataHoraFim = COALESCE(
                DataHoraFim,
                SYSDATETIME()
            ),

            FinalizadoPor = COALESCE(
                NULLIF(
                    LTRIM(
                        RTRIM(FinalizadoPor)
                    ),
                    ''
                ),
                'sistema'
            )

        WHERE
            ID_Inventario = ?
            AND ISNULL(Status, '') <> 'FINALIZADO'
        """,
        id_inventario
    )

    return cursor.rowcount
