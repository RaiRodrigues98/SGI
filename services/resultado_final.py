from domain.exceptions import NotFoundError


# ============================================================
# BUSCAR DECISÃO ROTATIVA ATIVA
# ============================================================

def _buscar_decisao_rotativa_resultado(
    cursor,
    id_inventario: int,
    localizacao,
    codigo,
    lote
):
    localizacao_normalizada = (
        str(localizacao or "").strip().upper()
    )
    codigo_normalizado = str(codigo or "").strip()
    lote_normalizado = str(lote or "").strip()

    cursor.execute(
        """
        SELECT TOP 1
            ID_DecisaoRotativo,
            Decisao,
            Justificativa,
            Usuario,
            DataHora,
            Status
        FROM dbo.DecisoesRotativo
        WHERE
            ID_Inventario = ?
            AND UPPER(LTRIM(RTRIM(Localizacao))) = ?
            AND LTRIM(RTRIM(Codigo)) = ?
            AND ISNULL(LTRIM(RTRIM(Lote)), '') = ?
            AND Status = 'ATIVA'
        ORDER BY ID_DecisaoRotativo DESC
        """,
        (
            id_inventario,
            localizacao_normalizada,
            codigo_normalizado,
            lote_normalizado
        )
    )

    linha = cursor.fetchone()

    if not linha:
        return None

    return {
        "id_decisao_rotativo": linha.ID_DecisaoRotativo,
        "decisao": linha.Decisao,
        "justificativa": linha.Justificativa,
        "usuario": linha.Usuario,
        "data_hora": linha.DataHora,
        "status": linha.Status
    }


# ============================================================
# CONSULTA DO RESULTADO FINAL DO INVENTÁRIO
# ============================================================

def consultar_resultado_final(
    cursor,
    id_inventario: int
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
            Status,
            DataHoraFim,
            FinalizadoPor

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

    # ========================================================
    # 2. RESULTADO FINAL
    # ========================================================

    cursor.execute(
        """
        SELECT
            ID_ResultadoFinal,
            Localizacao,
            Codigo,
            Lote,
            Descricao,
            Unidade,
            Categoria,
            QtdEstoque,
            QuantidadeFinal,
            DiferencaFinal,
            StatusFinal,
            OrigemQuantidade,
            ID_DecisaoGestor,
            RodadaFinal,
            UsuarioFinalizacao,
            DataHoraFinalizacao

        FROM dbo.InventarioResultadoFinal

        WHERE ID_Inventario = ?

        ORDER BY
            CASE
                WHEN Localizacao IS NULL THEN 1
                ELSE 0
            END,
            Localizacao,
            Codigo,
            Lote
        """,
        id_inventario
    )

    linhas = cursor.fetchall()

    if not linhas:

        raise NotFoundError(
            "O inventário ainda não possui "
                "resultado final consolidado."
        )

    itens = []

    for linha in linhas:

        qtd_estoque = float(
            linha.QtdEstoque
        )

        quantidade_final = float(
            linha.QuantidadeFinal
        )

        diferenca_final = float(
            linha.DiferencaFinal
        )

        decisao_rotativo = None

        if str(inventario.Tipo or "").strip().upper() == "ROTATIVO":
            decisao_rotativo = _buscar_decisao_rotativa_resultado(
                cursor=cursor,
                id_inventario=id_inventario,
                localizacao=linha.Localizacao,
                codigo=linha.Codigo,
                lote=linha.Lote
            )

        itens.append(
            {
                "id_resultado_final":
                    linha.ID_ResultadoFinal,

                "localizacao":
                    linha.Localizacao,

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
                    qtd_estoque,

                "quantidade_final":
                    quantidade_final,

                "diferenca_final":
                    diferenca_final,

                "status_final":
                    linha.StatusFinal,

                "origem_quantidade":
                    linha.OrigemQuantidade,

                "id_decisao_gestor":
                    linha.ID_DecisaoGestor,

                "rodada_final":
                    linha.RodadaFinal,

                "usuario_finalizacao":
                    linha.UsuarioFinalizacao,

                "data_hora_finalizacao":
                    linha.DataHoraFinalizacao,

                "decisao_rotativo":
                    (
                        decisao_rotativo.get("decisao")
                        if decisao_rotativo
                        else None
                    ),

                "justificativa_rotativo":
                    (
                        decisao_rotativo.get("justificativa")
                        if decisao_rotativo
                        else None
                    ),

                "usuario_decisao_rotativo":
                    (
                        decisao_rotativo.get("usuario")
                        if decisao_rotativo
                        else None
                    ),

                "data_hora_decisao_rotativo":
                    (
                        decisao_rotativo.get("data_hora")
                        if decisao_rotativo
                        else None
                    )
            }
        )

    # ========================================================
    # 3. RESUMO
    # ========================================================

    total_itens = len(
        itens
    )

    total_ok = sum(
        1
        for item in itens
        if item["status_final"] == "OK"
    )

    total_faltas = sum(
        1
        for item in itens
        if item["status_final"] == "FALTA"
    )

    total_sobras = sum(
        1
        for item in itens
        if item["status_final"] == "SOBRA"
    )

    total_divergencias = sum(
        1
        for item in itens
        if (
            item["status_final"]
            == "DIVERGÊNCIA"
        )
    )

    total_nok = (
        total_faltas
        +
        total_sobras
        +
        total_divergencias
    )

    acuracidade = (
        round(
            (
                total_ok
                /
                total_itens
            )
            * 100,
            2
        )
        if total_itens > 0
        else 0
    )

    # ========================================================
    # 4. ORIGEM DA QUANTIDADE FINAL
    # ========================================================

    conciliados = sum(
        1
        for item in itens
        if (
            item["origem_quantidade"]
            == "CONTAGEM_CONCILIADA"
        )
    )

    aceitaram_estoque = sum(
        1
        for item in itens
        if (
            item["origem_quantidade"]
            == "ACEITAR_ESTOQUE"
        )
    )

    aceitaram_contagem = sum(
        1
        for item in itens
        if (
            item["origem_quantidade"]
            == "ACEITAR_CONTAGEM"
        )
    )

    contagem_rotativo = sum(
        1
        for item in itens
        if (
            item["origem_quantidade"]
            == "CONTAGEM_ROTATIVO"
        )
    )

    # ========================================================
    # 5. RETORNO
    # ========================================================

    return {
        "tipo_consulta":
            "RESULTADO_FINAL",

        "id_inventario":
            inventario.ID_Inventario,

        "codigo_inventario":
            inventario.CodigoInventario,

        "tipo_inventario":
            inventario.Tipo,

        "cliente_id":
            inventario.ClienteId,

        "rodada_final":
            inventario.RodadaAtual,

        "status_inventario":
            inventario.Status,

        "data_hora_finalizacao":
            inventario.DataHoraFim,

        "finalizado_por":
            inventario.FinalizadoPor,

        "resumo": {
            "total_itens":
                total_itens,

            "ok":
                total_ok,

            "nok":
                total_nok,

            "faltas":
                total_faltas,

            "sobras":
                total_sobras,

            "divergencias":
                total_divergencias,

            "acuracidade_percentual":
                acuracidade
        },

        "origem_resultado": {
            "contagem_conciliada":
                conciliados,

            "aceitaram_estoque":
                aceitaram_estoque,

            "aceitaram_contagem":
                aceitaram_contagem,

            "contagem_rotativo":
                contagem_rotativo
        },

        "itens":
            itens
    }