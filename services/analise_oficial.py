def montar_resumo_oficial(itens):

    resumo = {
        "total_registros": len(itens),
        "ok": 0,
        "divergencias": 0,
        "faltas": 0,
        "sobras": 0,
        "aguardando_contagem": 0
    }

    for item in itens:

        status = item["status"]

        if status == "OK":
            resumo["ok"] += 1

        elif status == "DIVERGÊNCIA":
            resumo["divergencias"] += 1

        elif status == "FALTA":
            resumo["faltas"] += 1

        elif status == "SOBRA":
            resumo["sobras"] += 1

        elif status == "AGUARDANDO_CONTAGEM":
            resumo["aguardando_contagem"] += 1

    return resumo


# ============================================================
# OFICIAL - ANÁLISE DA SESSÃO
# ============================================================

def analisar_sessao_oficial(
    cursor,
    sessao
):

    """
    No inventário OFICIAL a localização não participa
    da chave de conciliação.

    Esta consulta mostra os itens bipados nesta sessão.

    A análise definitiva do inventário oficial deve ser
    feita pela análise consolidada da rodada.
    """

    cursor.execute(
        """
        WITH SnapshotAgrupado AS
        (
            SELECT

                Codigo AS Codigo,

                ISNULL(Lote, '') AS Lote,

                MAX(Descricao) AS Descricao,
                MAX(Unidade) AS Unidade,
                MAX(Categoria) AS Categoria,

                SUM(
                    SaldoInventario
                ) AS QtdEstoque

            FROM dbo.InventarioEstoqueSnapshot

            WHERE ID_Inventario = ?

            GROUP BY

                Codigo,

                ISNULL(Lote, '')
        ),

        ContagemSessao AS
        (
            SELECT

                C.Codigo AS Codigo,

                ISNULL(C.Lote, '') AS Lote,

                SUM(
                    C.Quantidade
                ) AS QtdContada

            FROM dbo.Contagens C

            WHERE C.ID_Sessao = ?
              AND C.Status = 'ATIVA'

            GROUP BY

                C.Codigo,

                ISNULL(C.Lote, '')
        )

        SELECT

            CONCAT(
                C.Codigo,
                '|',
                C.Lote
            ) AS Chave,

            C.Codigo,
            C.Lote,

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
            ) AS QtdContada,

            ISNULL(
                C.QtdContada,
                0
            )
            -
            ISNULL(
                E.QtdEstoque,
                0
            ) AS Diferenca,

            CASE

                WHEN E.Codigo IS NULL
                    THEN 'SOBRA'

                WHEN
                    ISNULL(
                        C.QtdContada,
                        0
                    )
                    =
                    ISNULL(
                        E.QtdEstoque,
                        0
                    )

                    THEN 'OK'

                ELSE 'DIVERGÊNCIA'

            END AS Status

        FROM ContagemSessao C

        LEFT JOIN SnapshotAgrupado E

            ON E.Codigo = C.Codigo
           AND E.Lote = C.Lote

        ORDER BY
            C.Codigo,
            C.Lote
        """,
        (
            sessao.ID_Inventario,
            sessao.ID_Sessao
        )
    )

    linhas = cursor.fetchall()

    itens = []

    for linha in linhas:

        status = str(
            linha.Status
        ).strip().upper()

        resultado_definitivo = (
            status != "AGUARDANDO_CONTAGEM"
        )

        subtipo_divergencia = None
        detalhe = None

        lotes_falta = sorted(
            lotes_falta_por_codigo.get(
                str(codigo).strip(),
                set()
            )
        )

        lotes_sobra = sorted(
            lotes_sobra_por_codigo.get(
                str(codigo).strip(),
                set()
            )
        )

        if status == "FALTA":

            lotes_alternativos = [
                item_lote
                for item_lote in lotes_sobra
                if item_lote != str(lote or "").strip()
            ]

            if lotes_alternativos:

                subtipo_divergencia = (
                    "LOTE_INCORRETO"
                )

                lotes_texto = ", ".join(
                    item_lote or "Sem lote"
                    for item_lote in lotes_alternativos
                )

                detalhe = (
                    "Lote esperado n\u00e3o contado. "
                    f"Contagem encontrada no lote: {lotes_texto}."
                )

            else:

                subtipo_divergencia = "FALTA"

                detalhe = (
                    "Item previsto no estoque n\u00e3o foi "
                    "identificado na contagem da rodada."
                )

        elif status == "SOBRA":

            lotes_esperados = [
                item_lote
                for item_lote in lotes_falta
                if item_lote != str(lote or "").strip()
            ]

            if lotes_esperados:

                subtipo_divergencia = (
                    "LOTE_INCORRETO"
                )

                lotes_texto = ", ".join(
                    item_lote or "Sem lote"
                    for item_lote in lotes_esperados
                )

                detalhe = (
                    "Lote contado n\u00e3o corresponde ao "
                    f"estoque. Lote esperado: {lotes_texto}."
                )

            else:

                subtipo_divergencia = (
                    "ITEM_NAO_PREVISTO"
                )

                detalhe = (
                    "Item contado sem correspond\u00eancia "
                    "no estoque da rodada."
                )

        elif status == "DIVERG\u00caNCIA":

            subtipo_divergencia = "QUANTIDADE"

            detalhe = (
                "Quantidade contada diferente da "
                "quantidade registrada no estoque."
            )

        itens.append({
            "chave":
                linha.Chave,

            "codigo":
                linha.Codigo,

            "lote":
                linha.Lote,

            "descricao":
                linha.Descricao,

            "unidade":
                linha.Unidade,

            "categoria":
                linha.Categoria,

            "qtd_estoque":
                float(
                    linha.QtdEstoque
                ),

            "qtd_contada_sessao":
                float(
                    linha.QtdContada
                ),

            "diferenca_sessao":
                float(
                    linha.Diferenca
                ),

            "status_sessao":
                linha.Status,

            "localizacao_bipada":
                sessao.Localizacao
        })

    return {
        "tipo_analise":
            "OFICIAL",

        "id_sessao":
            sessao.ID_Sessao,

        "id_inventario":
            sessao.ID_Inventario,

        "id_rodada":
            sessao.ID_Rodada,

        "localizacao_bipada":
            sessao.Localizacao,

        "status_sessao":
            sessao.Status,

        "observacao":
            (
                "No inventário OFICIAL a localização "
                "é utilizada somente para rastreabilidade. "
                "O resultado definitivo é calculado "
                "na análise consolidada da rodada."
            ),

        "itens":
            itens
    }


# ============================================================
# OFICIAL - ANÁLISE CONSOLIDADA DA RODADA
# ============================================================

def analisar_rodada_oficial(
    cursor,
    inventario,
    rodada
):

    # --------------------------------------------------------
    # 1. SNAPSHOT + CONTAGEM
    #
    # IMPORTANTE:
    # Localização NÃO participa do GROUP BY.
    # --------------------------------------------------------

    cursor.execute(
        """
        WITH SnapshotAgrupado AS
        (
            SELECT

                E.Codigo AS Codigo,

                ISNULL(E.Lote, '') AS Lote,

                MAX(E.Descricao) AS Descricao,
                MAX(E.Unidade) AS Unidade,
                MAX(E.Categoria) AS Categoria,

                SUM(
                    E.SaldoInventario
                ) AS QtdEstoque,

                MAX(
                    CASE
                        WHEN ISNULL(
                            RL.LocalizacaoConcluida,
                            0
                        ) = 0
                            THEN 1
                        ELSE 0
                    END
                ) AS TemLocalizacaoPendente

            FROM dbo.InventarioEstoqueSnapshot E

            LEFT JOIN
            (
                SELECT
                    Localizacao,

                    CASE
                        WHEN SUM(
                            CASE
                                WHEN Status = 'CONCLUIDA'
                                    THEN 0
                                ELSE 1
                            END
                        ) = 0
                            THEN 1
                        ELSE 0
                    END AS LocalizacaoConcluida

                FROM dbo.RodadaLocalizacoes

                WHERE ID_Rodada = ?

                GROUP BY
                    Localizacao
            ) RL
                ON RL.Localizacao = E.Localizacao

            WHERE E.ID_Inventario = ?

            GROUP BY

                E.Codigo,

                ISNULL(E.Lote, '')
        ),

        ContagemAgrupada AS
        (
            SELECT

                C.Codigo AS Codigo,

                ISNULL(C.Lote, '') AS Lote,

                SUM(
                    C.Quantidade
                ) AS QtdContada

            FROM dbo.Contagens C

            INNER JOIN dbo.SessoesContagem S
                ON S.ID_Sessao = C.ID_Sessao

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

            CONCAT(
                COALESCE(
                    E.Codigo,
                    C.Codigo
                ),
                '|',
                COALESCE(
                    E.Lote,
                    C.Lote,
                    ''
                )
            ) AS Chave,

            COALESCE(
                E.Codigo,
                C.Codigo
            ) AS Codigo,

            COALESCE(
                E.Lote,
                C.Lote,
                ''
            ) AS Lote,

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
            ) AS QtdContada,

            ISNULL(
                C.QtdContada,
                0
            )
            -
            ISNULL(
                E.QtdEstoque,
                0
            ) AS Diferenca,

            CASE

                WHEN E.Codigo IS NULL
                     AND C.Codigo IS NOT NULL
                    THEN 'SOBRA'

                WHEN C.Codigo IS NULL
                     AND ISNULL(
                         E.TemLocalizacaoPendente,
                         1
                     ) = 1
                    THEN 'AGUARDANDO_CONTAGEM'

                WHEN C.Codigo IS NULL
                    THEN 'FALTA'

                WHEN
                    ISNULL(
                        C.QtdContada,
                        0
                    )
                    =
                    ISNULL(
                        E.QtdEstoque,
                        0
                    )

                    THEN 'OK'

                ELSE 'DIVERGÊNCIA'

            END AS Status

        FROM SnapshotAgrupado E

        FULL OUTER JOIN ContagemAgrupada C

            ON E.Codigo = C.Codigo
           AND E.Lote = C.Lote

        ORDER BY

            COALESCE(
                E.Codigo,
                C.Codigo
            ),

            COALESCE(
                E.Lote,
                C.Lote
            )
        """,
        (
            rodada.ID_Rodada,
            inventario.ID_Inventario,
            inventario.ID_Inventario,
            rodada.ID_Rodada
        )
    )

    linhas = cursor.fetchall()

    itens = []

    lotes_falta_por_codigo = {}
    lotes_sobra_por_codigo = {}

    for linha_resultado in linhas:

        status_resultado = str(
            linha_resultado.Status
        ).strip().upper()

        codigo_resultado = str(
            linha_resultado.Codigo
        ).strip()

        lote_resultado = str(
            linha_resultado.Lote or ""
        ).strip()

        if status_resultado == "FALTA":

            lotes_falta_por_codigo.setdefault(
                codigo_resultado,
                set()
            ).add(lote_resultado)

        elif status_resultado == "SOBRA":

            lotes_sobra_por_codigo.setdefault(
                codigo_resultado,
                set()
            ).add(lote_resultado)

    # --------------------------------------------------------
    # 2. MONTA ITENS
    # --------------------------------------------------------

    for linha in linhas:

        codigo = linha.Codigo
        lote = linha.Lote

        # ----------------------------------------------------
        # CLASSIFICACAO DA DIVERGENCIA
        # ----------------------------------------------------

        status = str(
            linha.Status
        ).strip().upper()

        resultado_definitivo = (
            status != "AGUARDANDO_CONTAGEM"
        )

        subtipo_divergencia = None
        detalhe = None

        codigo_chave = str(
            codigo or ""
        ).strip()

        lote_chave = str(
            lote or ""
        ).strip()

        lotes_falta = sorted(
            lotes_falta_por_codigo.get(
                codigo_chave,
                set()
            )
        )

        lotes_sobra = sorted(
            lotes_sobra_por_codigo.get(
                codigo_chave,
                set()
            )
        )

        if status == "FALTA":

            lotes_alternativos = [
                item_lote
                for item_lote in lotes_sobra
                if item_lote != lote_chave
            ]

            if lotes_alternativos:

                subtipo_divergencia = (
                    "LOTE_INCORRETO"
                )

                lotes_texto = ", ".join(
                    item_lote or "Sem lote"
                    for item_lote in lotes_alternativos
                )

                detalhe = (
                    "Lote esperado n\u00e3o contado. "
                    f"Contagem encontrada no lote: {lotes_texto}."
                )

            else:

                subtipo_divergencia = "FALTA"

                detalhe = (
                    "Item previsto no estoque n\u00e3o foi "
                    "identificado na contagem da rodada."
                )

        elif status == "SOBRA":

            lotes_esperados = [
                item_lote
                for item_lote in lotes_falta
                if item_lote != lote_chave
            ]

            if lotes_esperados:

                subtipo_divergencia = (
                    "LOTE_INCORRETO"
                )

                lotes_texto = ", ".join(
                    item_lote or "Sem lote"
                    for item_lote in lotes_esperados
                )

                detalhe = (
                    "Lote contado n\u00e3o corresponde ao "
                    f"estoque. Lote esperado: {lotes_texto}."
                )

            else:

                subtipo_divergencia = (
                    "ITEM_NAO_PREVISTO"
                )

                detalhe = (
                    "Item contado sem correspond\u00eancia "
                    "no estoque da rodada."
                )

        elif status == "DIVERG\u00caNCIA":

            subtipo_divergencia = "QUANTIDADE"

            detalhe = (
                "Quantidade contada diferente da "
                "quantidade registrada no estoque."
            )

        # ----------------------------------------------------
        # BUSCA ONDE O ITEM FOI BIPADO
        #
        # Isto NÃO interfere na conciliação.
        # É somente rastreabilidade.
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT

                S.Localizacao AS Localizacao,

                SUM(
                    C.Quantidade
                ) AS Quantidade

            FROM dbo.Contagens C

            INNER JOIN dbo.SessoesContagem S
                ON S.ID_Sessao = C.ID_Sessao

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
                inventario.ID_Inventario,
                rodada.ID_Rodada,
                codigo,
                lote
            )
        )

        localizacoes = cursor.fetchall()

        localizacoes_bipadas = []

        for loc in localizacoes:

            localizacoes_bipadas.append({
                "localizacao":
                    loc.Localizacao,

                "quantidade":
                    float(
                        loc.Quantidade
                    )
            })

        itens.append({

            "chave":
                linha.Chave,

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

            "qtd_estoque":
                float(
                    linha.QtdEstoque
                ),

            "qtd_contada":
                float(
                    linha.QtdContada
                ),

            "diferenca":
                float(
                    linha.Diferenca
                ),

            "status":
                linha.Status,

            "subtipo_divergencia":
                subtipo_divergencia,

            "detalhe":
                detalhe,

            "resultado_definitivo":
                resultado_definitivo,

            "localizacoes_bipadas":
                localizacoes_bipadas
        })

    # --------------------------------------------------------
    # 3. RETORNO
    # --------------------------------------------------------

    return {

        "tipo_analise":
            "OFICIAL",

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

        "resumo":
            montar_resumo_oficial(itens),

        "itens":
            itens
    }