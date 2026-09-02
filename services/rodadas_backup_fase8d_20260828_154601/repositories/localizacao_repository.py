"""
Repository SQL Server para dbo.RodadaLocalizacoes.

Somente persistência. Não executa commit/rollback.
"""


def inserir_localizacao_se_ausente(
    cursor,
    id_inventario: int,
    id_rodada: int,
    localizacao: str
):

    cursor.execute(
        """
        IF NOT EXISTS
        (
            SELECT 1

            FROM dbo.RodadaLocalizacoes

            WHERE
                ID_Rodada = ?

                AND UPPER(
                    LTRIM(
                        RTRIM(Localizacao)
                    )
                ) = ?
        )
        BEGIN

            INSERT INTO dbo.RodadaLocalizacoes
            (
                ID_Inventario,
                ID_Rodada,
                Localizacao,
                Status
            )

            VALUES
            (
                ?,
                ?,
                ?,
                'PENDENTE'
            )

        END
        """,
        (
            id_rodada,
            localizacao,

            id_inventario,
            id_rodada,
            localizacao
        )
    )
