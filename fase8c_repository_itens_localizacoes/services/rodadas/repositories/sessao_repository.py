"""
Repository SQL Server para consultas centradas em dbo.SessoesContagem.

Fase 8B.

Responsabilidades:
- consultar sessões abertas por inventário/rodada;
- consultar localizações históricas associadas a contagens válidas.

Não contém:
- regra de negócio;
- HTTPException;
- commit/rollback.
"""


def contar_sessoes_abertas(
    cursor,
    id_inventario: int,
    id_rodada: int
):

    cursor.execute(
        """
        SELECT COUNT(*)

        FROM dbo.SessoesContagem

        WHERE
            ID_Inventario = ?
            AND ID_Rodada = ?
            AND Status = 'ABERTA'
        """,
        (
            id_inventario,
            id_rodada
        )
    )

    return int(
        cursor.fetchone()[0]
    )


def buscar_localizacoes_historicas_item(
    cursor,
    id_inventario: int,
    codigo: str,
    lote: str
):

    cursor.execute(
        """
        SELECT DISTINCT

            UPPER(
                LTRIM(
                    RTRIM(S.Localizacao)
                )
            ) AS Localizacao

        FROM dbo.Contagens C

        INNER JOIN dbo.SessoesContagem S
            ON S.ID_Sessao = C.ID_Sessao

        WHERE
            S.ID_Inventario = ?
            AND S.ValidaParaConsolidacao = 1
            AND C.Status = 'ATIVA'

            AND LTRIM(
                RTRIM(C.Codigo)
            ) = ?

            AND ISNULL(
                LTRIM(
                    RTRIM(C.Lote)
                ),
                ''
            ) = ?

            AND NULLIF(
                LTRIM(
                    RTRIM(S.Localizacao)
                ),
                ''
            ) IS NOT NULL

        ORDER BY
            UPPER(
                LTRIM(
                    RTRIM(S.Localizacao)
                )
            )
        """,
        (
            id_inventario,
            codigo,
            lote
        )
    )

    return cursor.fetchall()
