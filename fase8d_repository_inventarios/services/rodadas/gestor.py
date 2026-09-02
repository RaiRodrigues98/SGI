"""
Regras de decisões gerenciais relacionadas à geração de novas rodadas.

Fase 4 da refatoração de services.rodadas_service.

Escopo:
- buscar decisões NOVA_RECONTAGEM;
- verificar decisões gerenciais ativas;
- montar candidatos definidos pelo gestor.

IMPORTANTE:
- refatoração exclusivamente estrutural;
- nenhuma regra de negócio alterada;
- assinaturas preservadas;
- criação/finalização de rodada permanece fora deste módulo.
"""


def _normalizar_texto(valor):

    if valor is None:
        return ""

    return str(valor).strip()


def _normalizar_lote(valor):

    return _normalizar_texto(valor)


def _buscar_itens_nova_recontagem_gestor(
    cursor,
    id_inventario: int
):

    cursor.execute(
        """
        SELECT
            D.ID_Decisao,

            LTRIM(
                RTRIM(D.Codigo)
            ) AS Codigo,

            ISNULL(
                LTRIM(
                    RTRIM(D.Lote)
                ),
                ''
            ) AS Lote,

            D.Decisao,
            D.Justificativa,
            D.Usuario,
            D.DataHora

        FROM dbo.DecisoesGestorInventario D

        WHERE
            D.ID_Inventario = ?
            AND D.Status = 'ATIVA'
            AND D.Decisao = 'NOVA_RECONTAGEM'

        ORDER BY
            D.ID_Decisao
        """,
        id_inventario
    )

    linhas = cursor.fetchall()

    return [
        {
            "id_decisao":
                linha.ID_Decisao,

            "codigo":
                _normalizar_texto(
                    linha.Codigo
                ),

            "lote":
                _normalizar_lote(
                    linha.Lote
                ),

            "decisao":
                linha.Decisao,

            "justificativa":
                linha.Justificativa,

            "usuario":
                linha.Usuario,

            "data_hora":
                linha.DataHora
        }
        for linha in linhas
    ]

def _existem_decisoes_gestor_ativas(
    cursor,
    id_inventario: int
):

    cursor.execute(
        """
        SELECT COUNT(*)

        FROM dbo.DecisoesGestorInventario

        WHERE
            ID_Inventario = ?
            AND Status = 'ATIVA'
        """,
        id_inventario
    )

    return (
        cursor.fetchone()[0] > 0
    )

def _buscar_candidatos_gestor(
    cursor,
    id_inventario: int
):

    decisoes = (
        _buscar_itens_nova_recontagem_gestor(
            cursor=cursor,
            id_inventario=id_inventario
        )
    )

    candidatos = []

    for decisao in decisoes:

        candidatos.append(
            {
                "codigo":
                    decisao["codigo"],

                "lote":
                    decisao["lote"],

                "motivo":
                    (
                        "DECISAO_GESTOR_"
                        "NOVA_RECONTAGEM"
                    ),

                "id_decisao":
                    decisao["id_decisao"]
            }
        )

    return candidatos
