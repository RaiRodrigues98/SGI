"""
Seleção de candidatos para rodadas de divergência do inventário OFICIAL.

Fase 3 da refatoração de services.rodadas_service.

Escopo:
- candidatos da R3 a partir da comparação R1 x R2;
- candidatos das recontagens OFICIAL posteriores.

IMPORTANTE:
- refatoração exclusivamente estrutural;
- nenhuma regra de negócio alterada;
- assinaturas preservadas;
- fluxo ROTATIVO não pertence a este módulo.
"""

from domain.exceptions import BusinessRuleViolation

from services.comparativo_rodadas import (
    comparar_rodadas_oficial,
)

from services.analise_recontagem import (
    analisar_recontagem_oficial,
)


def _buscar_candidatos_r2_oficial(
    cursor,
    id_inventario: int,
    id_rodada_origem: int
):
    """
    Seleciona as divergências da primeira rodada oficial
    quando a configuração possui somente uma rodada inicial.

    A conciliação é feita por Código + Lote.
    Localização participa apenas da rastreabilidade.
    """

    cursor.execute(
        """
        ;WITH Estoque AS (
            SELECT
                LTRIM(RTRIM(Codigo)) AS Codigo,
                LTRIM(
                    RTRIM(
                        ISNULL(Lote, '')
                    )
                ) AS Lote,
                SUM(SaldoInventario) AS QtdEstoque

            FROM dbo.InventarioEstoqueSnapshot

            WHERE ID_Inventario = ?

            GROUP BY
                LTRIM(RTRIM(Codigo)),
                LTRIM(
                    RTRIM(
                        ISNULL(Lote, '')
                    )
                )
        ),
        Contado AS (
            SELECT
                LTRIM(RTRIM(C.Codigo)) AS Codigo,
                LTRIM(
                    RTRIM(
                        ISNULL(C.Lote, '')
                    )
                ) AS Lote,
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
                LTRIM(RTRIM(C.Codigo)),
                LTRIM(
                    RTRIM(
                        ISNULL(C.Lote, '')
                    )
                )
        )
        SELECT
            COALESCE(
                E.Codigo,
                C.Codigo
            ) AS Codigo,

            COALESCE(
                E.Lote,
                C.Lote,
                ''
            ) AS Lote,

            ISNULL(
                E.QtdEstoque,
                0
            ) AS QtdEstoque,

            ISNULL(
                C.QtdContada,
                0
            ) AS QtdContada

        FROM Estoque E

        FULL OUTER JOIN Contado C
            ON C.Codigo = E.Codigo
           AND C.Lote = E.Lote

        WHERE
            ISNULL(E.QtdEstoque, 0)
            <>
            ISNULL(C.QtdContada, 0)

        ORDER BY
            Codigo,
            Lote
        """,
        (
            id_inventario,
            id_inventario,
            id_rodada_origem,
        )
    )

    linhas = cursor.fetchall()

    candidatos = []

    for linha in linhas:
        qtd_estoque = float(
            linha.QtdEstoque or 0
        )

        qtd_contada = float(
            linha.QtdContada or 0
        )

        if (
            qtd_estoque > 0
            and
            qtd_contada == 0
        ):
            motivo = "FALTA_R1"

        elif (
            qtd_estoque == 0
            and
            qtd_contada > 0
        ):
            motivo = "SOBRA_R1"

        else:
            motivo = "DIVERGENCIA_R1"

        candidatos.append(
            {
                "codigo": linha.Codigo,
                "lote": linha.Lote,
                "motivo": motivo,
            }
        )

    return candidatos


def _buscar_candidatos_r3(
    cursor,
    id_inventario: int
):

    comparativo = (
        comparar_rodadas_oficial(
            cursor=cursor,
            id_inventario=id_inventario
        )
    )

    candidatos = []

    for item in comparativo["itens"]:

        if not item.get(
            "vai_para_r3",
            False
        ):
            continue

        status_r1 = (
            item["rodada_1"]["status"]
        )

        status_r2 = (
            item["rodada_2"]["status"]
        )

        if (
            status_r1 != "OK"
            and
            status_r2 != "OK"
        ):

            motivo = (
                "DIVERGENCIA_R1_R2"
            )

        elif status_r1 != "OK":

            motivo = (
                "DIVERGENCIA_R1"
            )

        else:

            motivo = (
                "DIVERGENCIA_R2"
            )

        candidatos.append(
            {
                "codigo":
                    item["codigo"],

                "lote":
                    item["lote"],

                "motivo":
                    motivo
            }
        )

    return candidatos

def _buscar_candidatos_recontagem_anterior(
    cursor,
    id_inventario: int,
    id_rodada_origem: int
):

    analise = (
        analisar_recontagem_oficial(
            cursor=cursor,
            id_inventario=id_inventario,
            id_rodada=id_rodada_origem
        )
    )

    if not analise.get(
        "rodada_operacional_concluida",
        False
    ):

        raise BusinessRuleViolation(
            "A rodada atual ainda não foi "
                "concluída operacionalmente."
        )

    candidatos = []

    for item in analise["itens"]:

        if not item.get(
            "pendente_proxima_rodada",
            False
        ):
            continue

        status = (
            item.get(
                "status"
            )
            or
            "DIVERGÊNCIA"
        )

        numero_rodada = (
            analise["numero_rodada"]
        )

        if status == "FALTA":

            motivo = (
                f"FALTA_R{numero_rodada}"
            )

        elif status == "SOBRA":

            motivo = (
                f"SOBRA_R{numero_rodada}"
            )

        else:

            motivo = (
                f"DIVERGENCIA_R{numero_rodada}"
            )

        candidatos.append(
            {
                "codigo":
                    item["codigo"],

                "lote":
                    item["lote"],

                "motivo":
                    motivo
            }
        )

    return candidatos
