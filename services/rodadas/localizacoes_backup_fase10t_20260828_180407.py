"""
Operações de localizações vinculadas às rodadas/recontagens.

Fase 1 da refatoração de services.rodadas_service.

IMPORTANTE:
- extração estrutural;
- nenhuma regra de negócio alterada;
- SQL preservado;
- assinaturas das funções preservadas.
"""

from fastapi import HTTPException

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

        raise HTTPException(
            status_code=404,
            detail=(
                "Rodada não encontrada "
                "para este inventário."
            )
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
