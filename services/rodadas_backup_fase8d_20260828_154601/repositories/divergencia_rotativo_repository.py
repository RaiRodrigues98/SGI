"""
Read repository das divergências do inventário ROTATIVO.

Fase 8B.

Esta consulta é deliberadamente separada de sessao_repository.py
porque cruza múltiplos agregados:
- InventarioEstoqueSnapshot;
- Contagens;
- SessoesContagem;
- DecisoesRotativo.

Ela representa um read model de divergência, não uma operação
do agregado Sessão.

Não contém:
- regra de decisão;
- HTTPException;
- commit/rollback.
"""


def buscar_primeira_divergencia_r1_sem_tratamento(
    cursor,
    id_inventario: int,
    id_rodada_r1: int
):

    cursor.execute(
        """
        WITH Snapshot AS
        (
            SELECT
                UPPER(LTRIM(RTRIM(E.Localizacao))) AS Localizacao,
                LTRIM(RTRIM(E.Codigo)) AS Codigo,
                ISNULL(LTRIM(RTRIM(E.Lote)), '') AS Lote,
                SUM(E.SaldoInventario) AS QtdEstoque
            FROM dbo.InventarioEstoqueSnapshot E
            WHERE E.ID_Inventario = ?
            GROUP BY
                UPPER(LTRIM(RTRIM(E.Localizacao))),
                LTRIM(RTRIM(E.Codigo)),
                ISNULL(LTRIM(RTRIM(E.Lote)), '')
        ),
        Contado AS
        (
            SELECT
                UPPER(LTRIM(RTRIM(S.Localizacao))) AS Localizacao,
                LTRIM(RTRIM(C.Codigo)) AS Codigo,
                ISNULL(LTRIM(RTRIM(C.Lote)), '') AS Lote,
                SUM(C.Quantidade) AS QtdContada
            FROM dbo.Contagens C
            INNER JOIN dbo.SessoesContagem S
                ON S.ID_Sessao = C.ID_Sessao
            WHERE
                S.ID_Inventario = ?
                AND S.ID_Rodada = ?
                AND S.ValidaParaConsolidacao = 1
                AND C.Status = 'ATIVA'
            GROUP BY
                UPPER(LTRIM(RTRIM(S.Localizacao))),
                LTRIM(RTRIM(C.Codigo)),
                ISNULL(LTRIM(RTRIM(C.Lote)), '')
        ),
        Comparacao AS
        (
            SELECT
                COALESCE(E.Localizacao, C.Localizacao) AS Localizacao,
                COALESCE(E.Codigo, C.Codigo) AS Codigo,
                COALESCE(E.Lote, C.Lote) AS Lote,
                ISNULL(E.QtdEstoque, 0) AS QtdEstoque,
                ISNULL(C.QtdContada, 0) AS QtdContada
            FROM Snapshot E
            FULL OUTER JOIN Contado C
                ON C.Localizacao = E.Localizacao
                AND C.Codigo = E.Codigo
                AND C.Lote = E.Lote
        )
        SELECT TOP 1
            X.Localizacao,
            X.Codigo,
            X.Lote,
            X.QtdEstoque,
            X.QtdContada,
            X.QtdContada - X.QtdEstoque AS Diferenca
        FROM Comparacao X
        WHERE
            X.QtdContada <> X.QtdEstoque
            AND NOT EXISTS
            (
                SELECT 1
                FROM dbo.DecisoesRotativo D
                WHERE
                    D.ID_Inventario = ?
                    AND D.ID_Rodada = ?
                    AND UPPER(LTRIM(RTRIM(D.Localizacao))) = X.Localizacao
                    AND LTRIM(RTRIM(D.Codigo)) = X.Codigo
                    AND ISNULL(LTRIM(RTRIM(D.Lote)), '') = X.Lote
                    AND D.Decisao IN ('RECONTAR', 'JUSTIFICAR_DIVERGENCIA')
                    AND D.Status IN ('ATIVA', 'CONCLUIDA')
            )
        ORDER BY X.Localizacao, X.Codigo, X.Lote
        """,
        (
            id_inventario,
            id_inventario,
            id_rodada_r1,
            id_inventario,
            id_rodada_r1
        )
    )

    return cursor.fetchone()
