from domain.exceptions import BusinessRuleViolation, NotFoundError


# ============================================================
# ANÁLISE GENÉRICA DE RECONTAGEM - INVENTÁRIO OFICIAL
#
# Aplica-se:
# R3, R4, R5, R6...
#
# REGRAS:
#
# 1. Conciliação por:
#       Código + Lote
#
# 2. Localização NÃO participa da conciliação quantitativa.
#
# 3. Localização serve para:
#       - rastreabilidade
#       - controle operacional da recontagem
#
# 4. Enquanto existir localização da rodada pendente:
#       resultados são considerados provisórios.
#
# 5. Itens encontrados durante a contagem cega também
#    entram na análise, mesmo que não estejam em RodadaItens.
# ============================================================


# ============================================================
# NORMALIZAÇÃO
# ============================================================

def _normalizar_texto(valor):

    if valor is None:
        return ""

    return str(valor).strip()


def _normalizar_lote(valor):

    return _normalizar_texto(
        valor
    )


def _normalizar_localizacao(valor):

    return (
        _normalizar_texto(
            valor
        )
        .upper()
    )


# ============================================================
# STATUS FINAL DO ITEM
#
# Usado somente quando a rodada está operacionalmente
# concluída.
# ============================================================

def _calcular_status_final(
    qtd_estoque: float,
    qtd_contada: float
):

    if (
        qtd_estoque == 0
        and
        qtd_contada > 0
    ):
        return "SOBRA"

    if (
        qtd_estoque > 0
        and
        qtd_contada == 0
    ):
        return "FALTA"

    if qtd_estoque == qtd_contada:
        return "OK"

    return "DIVERGÊNCIA"


# ============================================================
# BUSCAR LOCALIZAÇÕES BIPADAS PELO ITEM NA RODADA
# ============================================================

def _buscar_localizacoes_bipadas(
    cursor,
    id_inventario: int,
    id_rodada: int,
    codigo: str,
    lote: str
):

    cursor.execute(
        """
        SELECT
            S.Localizacao AS Localizacao,

            SUM(
                C.Quantidade
            ) AS Quantidade

        FROM dbo.Contagens C

        INNER JOIN dbo.SessoesContagem S
            ON S.ID_Sessao =
               C.ID_Sessao

        WHERE
            S.ID_Inventario = ?
            AND S.ID_Rodada = ?
            AND S.ValidaParaConsolidacao = 1
            AND C.Status = 'ATIVA'

            AND C.Codigo = ?

            AND ISNULL(C.Lote, '') = ?

        GROUP BY
            S.Localizacao

        ORDER BY
            S.Localizacao
        """,
        (
            id_inventario,
            id_rodada,
            codigo,
            lote
        )
    )

    linhas = cursor.fetchall()

    return [
        {
            "localizacao":
                linha.Localizacao,

            "quantidade":
                float(
                    linha.Quantidade
                )
        }
        for linha in linhas
    ]


# ============================================================
# BUSCAR LOCALIZAÇÕES OPERACIONAIS DA RODADA
# ============================================================

def _buscar_localizacoes_rodada(
    cursor,
    id_rodada: int
):

    cursor.execute(
        """
        SELECT
            ID_RodadaLocalizacao,
            Localizacao,
            Status

        FROM dbo.RodadaLocalizacoes

        WHERE ID_Rodada = ?

        ORDER BY
            Localizacao
        """,
        (
            id_rodada,
        )
    )

    linhas = cursor.fetchall()

    return [
        {
            "id_rodada_localizacao":
                linha.ID_RodadaLocalizacao,

            "localizacao":
                _normalizar_localizacao(
                    linha.Localizacao
                ),

            "status":
                linha.Status
        }
        for linha in linhas
    ]


# ============================================================
# BUSCAR LOCALIZAÇÕES DO SNAPSHOT
#
# Apenas para rastreabilidade.
# Não interfere na conciliação do OFICIAL.
# ============================================================

def _buscar_localizacoes_snapshot(
    cursor,
    id_inventario: int,
    codigo: str,
    lote: str
):

    cursor.execute(
        """
        SELECT
            Localizacao AS Localizacao,

            SUM(
                SaldoInventario
            ) AS Quantidade

        FROM dbo.InventarioEstoqueSnapshot

        WHERE
            ID_Inventario = ?

            AND Codigo = ?

            AND ISNULL(Lote, '') = ?

        GROUP BY
            Localizacao

        ORDER BY
            Localizacao
        """,
        (
            id_inventario,
            codigo,
            lote
        )
    )

    linhas = cursor.fetchall()

    return [
        {
            "localizacao":
                linha.Localizacao,

            "quantidade":
                float(
                    linha.Quantidade
                )
        }
        for linha in linhas
    ]


# ============================================================
# ANALISAR RECONTAGEM
# ============================================================

def analisar_recontagem_oficial(
    cursor,
    id_inventario: int,
    id_rodada: int
):

    # ========================================================
    # 1. INVENTÁRIO
    # ========================================================

    cursor.execute(
        """
        SELECT
            ID_Inventario,
            CodigoInventario,
            Tipo,
            ClienteId,
            RodadaAtual,
            Status

        FROM dbo.Inventarios

        WHERE ID_Inventario = ?
        """,
        id_inventario
    )

    inventario = cursor.fetchone()

    if not inventario:

        raise NotFoundError(
            "Inventário não encontrado."
        )

    tipo_inventario = (
        str(
            inventario.Tipo
        )
        .strip()
        .upper()
    )

    if tipo_inventario != "OFICIAL":

        raise BusinessRuleViolation(
            "Análise de recontagem disponível "
                "somente para inventário OFICIAL."
        )

    # ========================================================
    # 2. RODADA
    # ========================================================

    cursor.execute(
        """
        SELECT
            ID_Rodada,
            ID_Inventario,
            NumeroRodada,
            Status

        FROM dbo.RodadasInventario

        WHERE ID_Rodada = ?
          AND ID_Inventario = ?
        """,
        (
            id_rodada,
            id_inventario
        )
    )

    rodada = cursor.fetchone()

    if not rodada:

        raise NotFoundError(
            "Rodada não encontrada "
                "para este inventário."
        )

    if rodada.NumeroRodada <= 2:

        raise BusinessRuleViolation(
            "Esta análise é destinada "
                "às rodadas de recontagem R3+."
        )

    # ========================================================
    # 3. LOCALIZAÇÕES OPERACIONAIS DA RODADA
    # ========================================================

    localizacoes_rodada = (
        _buscar_localizacoes_rodada(
            cursor=cursor,
            id_rodada=id_rodada
        )
    )

    total_localizacoes = len(
        localizacoes_rodada
    )

    localizacoes_concluidas = sum(
        1
        for item in localizacoes_rodada
        if item["status"] == "CONCLUIDA"
    )

    localizacoes_pendentes = sum(
        1
        for item in localizacoes_rodada
        if item["status"] != "CONCLUIDA"
    )

    # --------------------------------------------------------
    # Enquanto houver qualquer posição pendente,
    # a análise quantitativa ainda é provisória.
    # --------------------------------------------------------

    rodada_operacional_concluida = (
        total_localizacoes > 0
        and
        localizacoes_pendentes == 0
    )

    # ========================================================
    # 4. VERIFICA ITENS ORIGINAIS DA RECONTAGEM
    # ========================================================

    cursor.execute(
        """
        SELECT COUNT(*)

        FROM dbo.RodadaItens

        WHERE ID_Inventario = ?
          AND ID_Rodada = ?
        """,
        (
            id_inventario,
            id_rodada
        )
    )

    total_rodada_itens = (
        cursor.fetchone()[0]
    )

    if total_rodada_itens == 0:

        raise BusinessRuleViolation(
            "Esta rodada não possui itens "
                "de recontagem cadastrados."
        )

    # ========================================================
    # 5. MONTA UNIVERSO DE ANÁLISE
    #
    # Inclui:
    #
    # A) itens que originaram a recontagem
    #
    # +
    #
    # B) itens adicionais encontrados fisicamente
    #    durante a contagem cega.
    #
    # Isso é fundamental para a R3+.
    # ========================================================

    cursor.execute(
        """
        WITH ItensRodada AS
        (
            SELECT
                Codigo AS Codigo,

                ISNULL(Lote, '') AS Lote,

                MAX(
                    Motivo
                ) AS Motivo

            FROM dbo.RodadaItens

            WHERE
                ID_Inventario = ?
                AND ID_Rodada = ?

            GROUP BY
                Codigo,

                ISNULL(Lote, '')
        ),

        ItensEncontrados AS
        (
            SELECT
                C.Codigo AS Codigo,

                ISNULL(C.Lote, '') AS Lote

            FROM dbo.Contagens C

            INNER JOIN dbo.SessoesContagem S
                ON S.ID_Sessao =
                   C.ID_Sessao

            WHERE
                S.ID_Inventario = ?
                AND S.ID_Rodada = ?
                AND S.ValidaParaConsolidacao = 1
                AND C.Status = 'ATIVA'

            GROUP BY
                C.Codigo,

                ISNULL(C.Lote, '')
        ),

        Universo AS
        (
            SELECT
                Codigo,
                Lote
            FROM ItensRodada

            UNION

            SELECT
                Codigo,
                Lote
            FROM ItensEncontrados
        ),

        Snapshot AS
        (
            SELECT
                Codigo AS Codigo,

                ISNULL(Lote, '') AS Lote,

                MAX(
                    Descricao
                ) AS Descricao,

                MAX(
                    Unidade
                ) AS Unidade,

                MAX(
                    Categoria
                ) AS Categoria,

                SUM(
                    SaldoInventario
                ) AS QtdEstoque

            FROM dbo.InventarioEstoqueSnapshot

            WHERE ID_Inventario = ?

            GROUP BY
                Codigo,

                ISNULL(Lote, '')
        ),

        Contagem AS
        (
            SELECT
                C.Codigo AS Codigo,

                ISNULL(C.Lote, '') AS Lote,

                SUM(
                    C.Quantidade
                ) AS QtdContada

            FROM dbo.Contagens C

            INNER JOIN dbo.SessoesContagem S
                ON S.ID_Sessao =
                   C.ID_Sessao

            WHERE
                S.ID_Inventario = ?
                AND S.ID_Rodada = ?
                AND S.ValidaParaConsolidacao = 1
                AND C.Status = 'ATIVA'

            GROUP BY
                C.Codigo,

                ISNULL(C.Lote, '')
        )

        SELECT
            U.Codigo,
            U.Lote,

            I.Motivo,

            CASE
                WHEN I.Codigo IS NULL
                    THEN 0
                ELSE 1
            END AS ItemOriginalRecontagem,

            E.Descricao,
            E.Unidade,
            E.Categoria,

            ISNULL(
                E.QtdEstoque,
                0
            ) AS QtdEstoque,

            ISNULL(
                C.QtdContada,
                0
            ) AS QtdContada

        FROM Universo U

        LEFT JOIN ItensRodada I
            ON I.Codigo = U.Codigo
           AND I.Lote = U.Lote

        LEFT JOIN Snapshot E
            ON E.Codigo = U.Codigo
           AND E.Lote = U.Lote

        LEFT JOIN Contagem C
            ON C.Codigo = U.Codigo
           AND C.Lote = U.Lote

        ORDER BY
            U.Codigo,
            U.Lote
        """,
        (
            id_inventario,
            id_rodada,

            id_inventario,
            id_rodada,

            id_inventario,

            id_inventario,
            id_rodada
        )
    )

    linhas = cursor.fetchall()

    itens = []

    # ========================================================
    # 6. ANALISA ITEM A ITEM
    # ========================================================

    for linha in linhas:

        codigo = _normalizar_texto(
            linha.Codigo
        )

        lote = _normalizar_lote(
            linha.Lote
        )

        qtd_estoque = float(
            linha.QtdEstoque
        )

        qtd_contada = float(
            linha.QtdContada
        )

        diferenca = (
            qtd_contada
            -
            qtd_estoque
        )

        item_original_recontagem = bool(
            linha.ItemOriginalRecontagem
        )

        # ----------------------------------------------------
        # ONDE FOI ENCONTRADO NA RODADA
        # ----------------------------------------------------

        localizacoes_bipadas = (
            _buscar_localizacoes_bipadas(
                cursor=cursor,
                id_inventario=id_inventario,
                id_rodada=id_rodada,
                codigo=codigo,
                lote=lote
            )
        )

        # ----------------------------------------------------
        # ONDE EXISTIA NO SNAPSHOT
        # ----------------------------------------------------

        localizacoes_snapshot = (
            _buscar_localizacoes_snapshot(
                cursor=cursor,
                id_inventario=id_inventario,
                codigo=codigo,
                lote=lote
            )
        )

        # ====================================================
        # STATUS
        #
        # Enquanto houver localização pendente:
        # não consideramos FALTA/DIVERGÊNCIA final.
        # ====================================================

        if not rodada_operacional_concluida:

            status = (
                "AGUARDANDO_CONTAGEM"
            )

            pendente_proxima_rodada = (
                False
            )

            resultado_definitivo = (
                False
            )

        else:

            status = _calcular_status_final(
                qtd_estoque=qtd_estoque,
                qtd_contada=qtd_contada
            )

            pendente_proxima_rodada = (
                status != "OK"
            )

            resultado_definitivo = (
                True
            )

        # ====================================================
        # ORIGEM DO ITEM NA ANÁLISE
        # ====================================================

        if item_original_recontagem:

            origem = (
                "DIVERGENCIA_ORIGINAL"
            )

        else:

            origem = (
                "ENCONTRADO_NA_RECONTAGEM"
            )

        # ====================================================
        # ITEM
        # ====================================================

        itens.append(
            {
                "chave":
                    f"{codigo}|{lote}",

                "codigo":
                    codigo,

                "lote":
                    lote,

                "descricao":
                    linha.Descricao,

                "unidade":
                    linha.Unidade,

                "categoria":
                    linha.Categoria,

                "origem":
                    origem,

                "item_original_recontagem":
                    item_original_recontagem,

                "motivo_entrada_rodada":
                    linha.Motivo,

                "qtd_estoque":
                    qtd_estoque,

                "qtd_contada":
                    qtd_contada,

                "diferenca":
                    diferenca,

                "status":
                    status,

                "resultado_definitivo":
                    resultado_definitivo,

                "localizacoes_snapshot":
                    localizacoes_snapshot,

                "localizacoes_bipadas":
                    localizacoes_bipadas,

                "pendente_proxima_rodada":
                    pendente_proxima_rodada
            }
        )

    # ========================================================
    # 7. RESUMOS
    # ========================================================

    total_itens = len(
        itens
    )

    itens_originais = sum(
        1
        for item in itens
        if item["item_original_recontagem"]
    )

    itens_novos_encontrados = sum(
        1
        for item in itens
        if not item["item_original_recontagem"]
    )

    # ========================================================
    # RESULTADOS DEFINITIVOS
    # ========================================================

    total_ok = sum(
        1
        for item in itens
        if item["status"] == "OK"
    )

    total_divergencias = sum(
        1
        for item in itens
        if item["status"] == "DIVERGÊNCIA"
    )

    total_faltas = sum(
        1
        for item in itens
        if item["status"] == "FALTA"
    )

    total_sobras = sum(
        1
        for item in itens
        if item["status"] == "SOBRA"
    )

    aguardando_contagem = sum(
        1
        for item in itens
        if (
            item["status"]
            ==
            "AGUARDANDO_CONTAGEM"
        )
    )

    pendentes_proxima_rodada = sum(
        1
        for item in itens
        if item["pendente_proxima_rodada"]
    )

    # ========================================================
    # 8. STATUS GERAL DA RECONTAGEM
    # ========================================================

    if not rodada_operacional_concluida:

        status_recontagem = (
            "EM_ANDAMENTO"
        )

    elif pendentes_proxima_rodada == 0:

        status_recontagem = (
            "CONCILIADA"
        )

    else:

        status_recontagem = (
            "COM_DIVERGENCIAS"
        )

    # ========================================================
    # 9. PODE GERAR PRÓXIMA RODADA?
    #
    # Só depois que todas as localizações forem concluídas
    # e existirem divergências remanescentes.
    # ========================================================

    pode_gerar_proxima_rodada = (
        rodada_operacional_concluida
        and
        pendentes_proxima_rodada > 0
    )

    # ========================================================
    # 10. PODE FINALIZAR SEM DIVERGÊNCIA?
    # ========================================================

    pode_finalizar_sem_divergencia = (
        rodada_operacional_concluida
        and
        pendentes_proxima_rodada == 0
    )

    # ========================================================
    # 11. RETORNO
    # ========================================================

    return {

        "tipo_analise":
            "RECONTAGEM_OFICIAL",

        "id_inventario":
            inventario.ID_Inventario,

        "codigo_inventario":
            inventario.CodigoInventario,

        "id_rodada":
            rodada.ID_Rodada,

        "numero_rodada":
            rodada.NumeroRodada,

        "status_rodada":
            rodada.Status,

        "regra_conciliacao":
            "CODIGO_LOTE",

        "considera_localizacao":
            False,

        "contagem_cega":
            True,

        "status_recontagem":
            status_recontagem,

        "rodada_operacional_concluida":
            rodada_operacional_concluida,

        "pode_gerar_proxima_rodada":
            pode_gerar_proxima_rodada,

        "pode_finalizar_sem_divergencia":
            pode_finalizar_sem_divergencia,

        # ====================================================
        # RESUMO
        # ====================================================

        "resumo": {

            "total_itens":
                total_itens,

            "itens_originais_recontagem":
                itens_originais,

            "itens_novos_encontrados":
                itens_novos_encontrados,

            "ok":
                total_ok,

            "divergencias":
                total_divergencias,

            "faltas":
                total_faltas,

            "sobras":
                total_sobras,

            "aguardando_contagem":
                aguardando_contagem,

            "pendentes_proxima_rodada":
                pendentes_proxima_rodada,

            "total_localizacoes":
                total_localizacoes,

            "localizacoes_concluidas":
                localizacoes_concluidas,

            "localizacoes_pendentes":
                localizacoes_pendentes
        },

        # ====================================================
        # LOCALIZAÇÕES
        # ====================================================

        "localizacoes_rodada":
            localizacoes_rodada,

        # ====================================================
        # ITENS
        # ====================================================

        "itens":
            itens
    }