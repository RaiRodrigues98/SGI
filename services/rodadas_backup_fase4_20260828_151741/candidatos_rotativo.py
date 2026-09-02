"""
Regras de seleção/validação de candidatos da recontagem ROTATIVO.

Fase 2 da refatoração de services.rodadas_service.

Escopo desta fase:
- validar que as divergências da R1 possuem tratamento válido;
- selecionar os candidatos da R2 do inventário ROTATIVO;
- preservar helpers auxiliares já existentes.

IMPORTANTE:
- refatoração exclusivamente estrutural;
- nenhuma regra de negócio alterada;
- SQL preservado;
- assinaturas preservadas;
- nenhuma rotina do inventário OFICIAL foi movida para este módulo.
"""

from fastapi import HTTPException


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


def _validar_divergencias_r1_rotativo_tratadas(
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

    pendente = cursor.fetchone()

    if pendente:
        raise HTTPException(
            status_code=400,
            detail=(
                "Existe divergência da R1 sem tratamento válido. "
                f"Localização: {_normalizar_localizacao(pendente.Localizacao)}; "
                f"Código: {_normalizar_texto(pendente.Codigo)}; "
                f"Lote: {_normalizar_lote(pendente.Lote)}; "
                f"Estoque: {pendente.QtdEstoque}; "
                f"Contado: {pendente.QtdContada}; "
                f"Diferença: {pendente.Diferenca}."
            )
        )

    return True

def _buscar_colunas_tabela(
    cursor,
    schema: str,
    tabela: str
):

    cursor.execute(
        """
        SELECT COLUMN_NAME
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = ?
          AND TABLE_NAME = ?
        """,
        (
            schema,
            tabela
        )
    )

    return {
        _normalizar_texto(linha[0]).upper():
            _normalizar_texto(linha[0])
        for linha in cursor.fetchall()
    }

def _resolver_coluna_quantidade_rotativo(
    cursor,
    tabela: str,
    candidatos_coluna
):

    colunas = _buscar_colunas_tabela(
        cursor=cursor,
        schema="dbo",
        tabela=tabela
    )

    for nome in candidatos_coluna:

        encontrado = colunas.get(
            _normalizar_texto(nome).upper()
        )

        if encontrado:
            return encontrado

    raise HTTPException(
        status_code=500,
        detail=(
            f"Não foi possível identificar a coluna de quantidade "
            f"em dbo.{tabela}. "
            "A R2 do inventário ROTATIVO não foi criada para evitar "
            "uma comparação de estoque incorreta."
        )
    )

def _buscar_candidatos_r2_rotativo(
    cursor,
    id_inventario: int,
    id_rodada_origem: int
):

    # ========================================================
    # REGRA
    #
    # A R2 do ROTATIVO recebe somente itens com decisão ativa
    # RECONTAR na rodada de origem.
    #
    # Chave operacional:
    # Localização + Código + Lote
    # ========================================================

    cursor.execute(
        """
        SELECT
            UPPER(LTRIM(RTRIM(D.Localizacao))) AS Localizacao,
            LTRIM(RTRIM(D.Codigo)) AS Codigo,
            ISNULL(LTRIM(RTRIM(D.Lote)), '') AS Lote,
            D.ID_DecisaoRotativo,
            D.Decisao

        FROM dbo.DecisoesRotativo D

        WHERE
            D.ID_Inventario = ?
            AND D.ID_Rodada = ?
            AND D.Status = 'ATIVA'
            AND D.Decisao = 'RECONTAR'
            AND NULLIF(LTRIM(RTRIM(D.Localizacao)), '') IS NOT NULL
            AND NULLIF(LTRIM(RTRIM(D.Codigo)), '') IS NOT NULL

        ORDER BY
            UPPER(LTRIM(RTRIM(D.Localizacao))),
            LTRIM(RTRIM(D.Codigo)),
            ISNULL(LTRIM(RTRIM(D.Lote)), '')
        """,
        (
            id_inventario,
            id_rodada_origem
        )
    )

    linhas = cursor.fetchall()

    # RodadaItens é única por Código + Lote; as localizações
    # decididas ficam vinculadas ao candidato consolidado.
    consolidados = {}

    for linha in linhas:

        codigo = _normalizar_texto(
            linha.Codigo
        )

        lote = _normalizar_lote(
            linha.Lote
        )

        localizacao = _normalizar_localizacao(
            linha.Localizacao
        )

        chave = (
            codigo,
            lote
        )

        if chave not in consolidados:

            consolidados[chave] = {
                "codigo": codigo,
                "lote": lote,
                "motivo": "DECISAO_ROTATIVO_RECONTAR",
                "localizacoes": set(),
                "ids_decisao_rotativo": []
            }

        if localizacao:
            consolidados[chave]["localizacoes"].add(
                localizacao
            )

        consolidados[chave]["ids_decisao_rotativo"].append(
            linha.ID_DecisaoRotativo
        )

    candidatos = []

    for item in consolidados.values():
        item["localizacoes"] = sorted(
            item["localizacoes"]
        )
        candidatos.append(item)

    candidatos.sort(
        key=lambda item: (
            item["codigo"],
            item["lote"]
        )
    )

    return candidatos
