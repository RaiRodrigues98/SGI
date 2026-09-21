"""
Operações de localizações vinculadas às rodadas/recontagens.

Fase 1 da refatoração de services.rodadas_service.

IMPORTANTE:
- extração estrutural;
- nenhuma regra de negócio alterada;
- SQL preservado;
- assinaturas das funções preservadas.
"""

from domain.exceptions import NotFoundError

from services.rodadas.repositories.rodada_repository import (
    buscar_rodada_para_sincronizacao,
)

from services.rodadas.repositories.sessao_repository import (
    buscar_localizacoes_historicas_item,
)

from services.rodadas.repositories.item_repository import (
    listar_itens_da_rodada,
)

from services.rodadas.repositories.localizacao_repository import (
    inserir_localizacao_se_ausente,
)


def _normalizar_texto(valor):

    if valor is None:
        return ""

    return str(valor).strip()


def _normalizar_lote(valor):

    return _normalizar_texto(valor)


def _normalizar_localizacao(valor):

    return (
        _normalizar_texto(valor)
        .upper()
    )


def _buscar_localizacoes_snapshot_item(
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
                    RTRIM(Localizacao)
                )
            ) AS Localizacao

        FROM dbo.InventarioEstoqueSnapshot

        WHERE
            ID_Inventario = ?

            AND LTRIM(
                RTRIM(Codigo)
            ) = ?

            AND ISNULL(
                LTRIM(
                    RTRIM(Lote)
                ),
                ''
            ) = ?

            AND NULLIF(
                LTRIM(
                    RTRIM(Localizacao)
                ),
                ''
            ) IS NOT NULL

        ORDER BY
            UPPER(
                LTRIM(
                    RTRIM(Localizacao)
                )
            )
        """,
        (
            id_inventario,
            codigo,
            lote
        )
    )

    linhas = cursor.fetchall()

    return [
        _normalizar_localizacao(
            linha.Localizacao
        )
        for linha in linhas
        if _normalizar_localizacao(
            linha.Localizacao
        )
    ]

def _buscar_localizacoes_contagem_item(
    cursor,
    id_inventario: int,
    codigo: str,
    lote: str
):

    linhas = (
        buscar_localizacoes_historicas_item(
            cursor=cursor,
            id_inventario=id_inventario,
            codigo=codigo,
            lote=lote
        )
    )

    return [
        _normalizar_localizacao(
            linha.Localizacao
        )
        for linha in linhas
        if _normalizar_localizacao(
            linha.Localizacao
        )
    ]

def _buscar_localizacoes_para_item(
    cursor,
    id_inventario: int,
    codigo: str,
    lote: str
):

    localizacoes = set()

    # Snapshot
    for localizacao in (
        _buscar_localizacoes_snapshot_item(
            cursor=cursor,
            id_inventario=id_inventario,
            codigo=codigo,
            lote=lote
        )
    ):
        localizacoes.add(
            localizacao
        )

    # Histórico físico
    for localizacao in (
        _buscar_localizacoes_contagem_item(
            cursor=cursor,
            id_inventario=id_inventario,
            codigo=codigo,
            lote=lote
        )
    ):
        localizacoes.add(
            localizacao
        )

    return sorted(
        localizacoes
    )

def _inserir_rodada_localizacao(
    cursor,
    id_inventario: int,
    id_rodada: int,
    localizacao: str
):

    localizacao = (
        _normalizar_localizacao(
            localizacao
        )
    )

    if not localizacao:
        return

    inserir_localizacao_se_ausente(
        cursor=cursor,
        id_inventario=id_inventario,
        id_rodada=id_rodada,
        localizacao=localizacao
    )

def rodada_operacional_concluida(
    cursor,
    id_rodada: int
) -> bool:

    # SGI: conclusao R1 pelo escopo e sessoes
    cursor.execute(
        """
        SELECT ID_Inventario, NumeroRodada
        FROM dbo.RodadasInventario
        WHERE ID_Rodada = ?
        """,
        (id_rodada,)
    )

    contexto = cursor.fetchone()

    if contexto is None:
        return False

    if int(contexto.NumeroRodada) == 1:
        cursor.execute(
            """
            SELECT
                COUNT(*) AS TotalLocalizacoes,
                COALESCE(
                    SUM(
                        CASE
                            WHEN U.ID_Sessao IS NOT NULL
                             AND U.ValidaParaConsolidacao = 1
                             AND U.Status IS NOT NULL
                             AND UPPER(LTRIM(RTRIM(U.Status)))
                                 NOT IN (
                                     'ABERTA',
                                     'CANCELADA',
                                     'INVALIDADA',
                                     'PENDENTE',
                                     'EM_CONTAGEM'
                                 )
                            THEN 0
                            ELSE 1
                        END
                    ),
                    0
                ) AS LocalizacoesPendentes
            FROM dbo.InventarioEscopoLocalizacoes E
            OUTER APPLY (
                SELECT TOP 1
                    S.ID_Sessao,
                    S.Status,
                    S.ValidaParaConsolidacao
                FROM dbo.SessoesContagem S
                WHERE S.ID_Inventario = E.ID_Inventario
                  AND S.ID_Rodada = ?
                  AND S.Localizacao = E.Localizacao
                ORDER BY S.ID_Sessao DESC
            ) U
            WHERE E.ID_Inventario = ?
              AND E.Selecionado = 1
            """,
            (
                id_rodada,
                contexto.ID_Inventario,
            )
        )

        resumo = cursor.fetchone()

        return bool(
            resumo
            and int(resumo[0] or 0) > 0
            and int(resumo[1] or 0) == 0
        )

    cursor.execute(
        """
        SELECT
            COUNT(*) AS TotalLocalizacoes,
            COALESCE(
                SUM(
                    CASE
                        WHEN Status = 'CONCLUIDA'
                            THEN 0
                        ELSE 1
                    END
                ),
                0
            ) AS LocalizacoesPendentes

        FROM dbo.RodadaLocalizacoes

        WHERE ID_Rodada = ?
        """,
        (
            id_rodada,
        )
    )

    linha = cursor.fetchone()

    if not linha:
        return False

    total_localizacoes = int(
        linha[0] or 0
    )

    localizacoes_pendentes = int(
        linha[1] or 0
    )

    return (
        total_localizacoes > 0
        and
        localizacoes_pendentes == 0
    )


def sincronizar_localizacoes_recontagem(
    cursor,
    id_inventario: int,
    id_rodada: int
):

    # ========================================================
    # VALIDA RODADA
    # ========================================================

    rodada = (
        buscar_rodada_para_sincronizacao(
            cursor=cursor,
            id_rodada=id_rodada,
            id_inventario=id_inventario
        )
    )

    if not rodada:

        raise NotFoundError(
            "Rodada não encontrada "
                "para este inventário."
        )

    # ========================================================
    # ITENS DA RODADA
    # ========================================================

    itens = (
        listar_itens_da_rodada(
            cursor=cursor,
            id_inventario=id_inventario,
            id_rodada=id_rodada
        )
    )

    localizacoes = set()

    # ========================================================
    # LOCALIZAÇÕES DOS ITENS
    # ========================================================

    for item in itens:

        codigo = _normalizar_texto(
            item.Codigo
        )

        lote = _normalizar_lote(
            item.Lote
        )

        localizacoes_item = (
            _buscar_localizacoes_para_item(
                cursor=cursor,
                id_inventario=id_inventario,
                codigo=codigo,
                lote=lote
            )
        )

        for localizacao in (
            localizacoes_item
        ):
            localizacoes.add(
                localizacao
            )

    # ========================================================
    # INSERE LOCALIZAÇÕES
    # ========================================================

    for localizacao in sorted(
        localizacoes
    ):

        _inserir_rodada_localizacao(
            cursor=cursor,
            id_inventario=id_inventario,
            id_rodada=id_rodada,
            localizacao=localizacao
        )

    return {
        "id_inventario":
            id_inventario,

        "id_rodada":
            id_rodada,

        "numero_rodada":
            rodada.NumeroRodada,

        "localizacoes_geradas":
            len(localizacoes),

        "localizacoes":
            sorted(
                localizacoes
            )
    }
