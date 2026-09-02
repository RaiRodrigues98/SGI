from domain.exceptions import BusinessRuleViolation


# ============================================================
# NORMALIZAÇÃO
# ============================================================

def _normalizar_texto(valor):
    if valor is None:
        return ""

    return str(valor).strip()


def _normalizar_lote(valor):
    return _normalizar_texto(valor)


def _normalizar_localizacao(valor):
    return _normalizar_texto(valor).upper()


def _decimal_para_numero(valor):
    if valor is None:
        return 0

    return float(valor)


# ============================================================
# BUSCAR INVENTÁRIOS DO ITEM
# ============================================================

def _buscar_inventarios_item(
    cursor,
    codigo: str,
    lote: str | None = None,
    cliente_id: int | None = None,
    data_inicio=None,
    data_fim=None
):

    filtros_inventario = []
    parametros_inventario = []

    if cliente_id is not None:
        filtros_inventario.append(
            "I.ClienteId = ?"
        )
        parametros_inventario.append(
            cliente_id
        )

    if data_inicio is not None:
        filtros_inventario.append(
            "I.DataHoraInicio >= ?"
        )
        parametros_inventario.append(
            data_inicio
        )

    if data_fim is not None:
        filtros_inventario.append(
            """
            I.DataHoraInicio < DATEADD(
                DAY,
                1,
                CAST(? AS date)
            )
            """
        )
        parametros_inventario.append(
            data_fim
        )

    filtro_inventario_sql = ""

    if filtros_inventario:
        filtro_inventario_sql = (
            " AND "
            +
            " AND ".join(
                filtros_inventario
            )
        )

    filtro_lote_snapshot = ""
    filtro_lote_contagem = ""
    filtro_lote_resultado = ""
    filtro_lote_rodada_item = ""
    filtro_lote_rotativo = ""
    filtro_lote_gestor = ""

    if lote is not None:
        filtro_lote_snapshot = """
            AND ISNULL(
                LTRIM(RTRIM(E.Lote)),
                ''
            ) = ?
        """

        filtro_lote_contagem = """
            AND ISNULL(
                LTRIM(RTRIM(C.Lote)),
                ''
            ) = ?
        """

        filtro_lote_resultado = """
            AND ISNULL(
                LTRIM(RTRIM(RF.Lote)),
                ''
            ) = ?
        """

        filtro_lote_rodada_item = """
            AND ISNULL(
                LTRIM(RTRIM(RI.Lote)),
                ''
            ) = ?
        """

        filtro_lote_rotativo = """
            AND ISNULL(
                LTRIM(RTRIM(DR.Lote)),
                ''
            ) = ?
        """

        filtro_lote_gestor = """
            AND ISNULL(
                LTRIM(RTRIM(DG.Lote)),
                ''
            ) = ?
        """

    sql = f"""
        SELECT
            I.ID_Inventario,
            I.CodigoInventario,
            I.Tipo,
            I.Cliente,
            I.ClienteId,
            I.cArmazem,
            I.Descricao,
            I.RodadaAtual,
            I.Status,
            I.DataHoraInicio,
            I.DataHoraFim,
            I.CriadoPor,
            I.FinalizadoPor

        FROM dbo.Inventarios I

        WHERE
            (
                EXISTS
                (
                    SELECT 1
                    FROM dbo.InventarioEstoqueSnapshot E
                    WHERE
                        E.ID_Inventario = I.ID_Inventario
                        AND LTRIM(RTRIM(E.Codigo)) = ?
                        {filtro_lote_snapshot}
                )

                OR EXISTS
                (
                    SELECT 1
                    FROM dbo.Contagens C
                    INNER JOIN dbo.SessoesContagem S
                        ON S.ID_Sessao = C.ID_Sessao
                    WHERE
                        S.ID_Inventario = I.ID_Inventario
                        AND LTRIM(RTRIM(C.Codigo)) = ?
                        {filtro_lote_contagem}
                )

                OR EXISTS
                (
                    SELECT 1
                    FROM dbo.InventarioResultadoFinal RF
                    WHERE
                        RF.ID_Inventario = I.ID_Inventario
                        AND LTRIM(RTRIM(RF.Codigo)) = ?
                        {filtro_lote_resultado}
                )

                OR EXISTS
                (
                    SELECT 1
                    FROM dbo.RodadaItens RI
                    WHERE
                        RI.ID_Inventario = I.ID_Inventario
                        AND LTRIM(RTRIM(RI.Codigo)) = ?
                        {filtro_lote_rodada_item}
                )

                OR EXISTS
                (
                    SELECT 1
                    FROM dbo.DecisoesRotativo DR
                    WHERE
                        DR.ID_Inventario = I.ID_Inventario
                        AND LTRIM(RTRIM(DR.Codigo)) = ?
                        {filtro_lote_rotativo}
                )

                OR EXISTS
                (
                    SELECT 1
                    FROM dbo.DecisoesGestorInventario DG
                    WHERE
                        DG.ID_Inventario = I.ID_Inventario
                        AND LTRIM(RTRIM(DG.Codigo)) = ?
                        {filtro_lote_gestor}
                )
            )

            {filtro_inventario_sql}

        ORDER BY
            I.DataHoraInicio DESC,
            I.ID_Inventario DESC
    """

    parametros = []

    for _ in range(6):
        parametros.append(codigo)

        if lote is not None:
            parametros.append(lote)

    parametros.extend(
        parametros_inventario
    )

    cursor.execute(
        sql,
        tuple(parametros)
    )

    return cursor.fetchall()


# ============================================================
# SNAPSHOT DO ITEM
# ============================================================

def _buscar_snapshot_item(
    cursor,
    id_inventario: int,
    codigo: str,
    lote: str | None
):

    filtro_lote = ""
    parametros = [
        id_inventario,
        codigo
    ]

    if lote is not None:
        filtro_lote = """
            AND ISNULL(
                LTRIM(RTRIM(Lote)),
                ''
            ) = ?
        """
        parametros.append(
            lote
        )

    cursor.execute(
        f"""
        SELECT
            ID_Snapshot,
            ID_Origem,
            cArmazem,
            Localizacao,
            Codigo,
            ISNULL(Lote, '') AS Lote,
            Descricao,
            Unidade,
            Categoria,
            Validade,
            qArmazenado,
            qReservado,
            SaldoInventario,
            DataHoraSnapshot

        FROM dbo.InventarioEstoqueSnapshot

        WHERE
            ID_Inventario = ?
            AND LTRIM(RTRIM(Codigo)) = ?
            {filtro_lote}

        ORDER BY
            Localizacao,
            Lote,
            ID_Snapshot
        """,
        tuple(parametros)
    )

    linhas = cursor.fetchall()

    return [
        {
            "id_snapshot": linha.ID_Snapshot,
            "id_origem": linha.ID_Origem,
            "armazem": linha.cArmazem,
            "localizacao": _normalizar_localizacao(
                linha.Localizacao
            ),
            "codigo": _normalizar_texto(
                linha.Codigo
            ),
            "lote": _normalizar_lote(
                linha.Lote
            ),
            "descricao": linha.Descricao,
            "unidade": linha.Unidade,
            "categoria": linha.Categoria,
            "validade": linha.Validade,
            "q_armazenado": _decimal_para_numero(
                linha.qArmazenado
            ),
            "q_reservado": _decimal_para_numero(
                linha.qReservado
            ),
            "saldo_inventario": _decimal_para_numero(
                linha.SaldoInventario
            ),
            "data_hora_snapshot": linha.DataHoraSnapshot
        }
        for linha in linhas
    ]


# ============================================================
# RODADAS DO INVENTÁRIO
# ============================================================

def _buscar_rodadas_inventario(
    cursor,
    id_inventario: int
):

    cursor.execute(
        """
        SELECT
            ID_Rodada,
            NumeroRodada,
            Status,
            DataHoraInicio,
            DataHoraFim,
            CriadoPor,
            DataHoraCriacao

        FROM dbo.RodadasInventario

        WHERE
            ID_Inventario = ?

        ORDER BY
            NumeroRodada,
            ID_Rodada
        """,
        id_inventario
    )

    return cursor.fetchall()


# ============================================================
# ITEM PREVISTO NA RODADA
#
# R1:
# - item pertence ao snapshot;
# - localização do snapshot pertence ao escopo da rodada.
#
# R2+:
# - item existe em RodadaItens da rodada.
# ============================================================

def _item_previsto_na_rodada(
    cursor,
    id_inventario: int,
    id_rodada: int,
    numero_rodada: int,
    tipo_inventario: str,
    codigo: str,
    lote: str | None
):

    tipo_inventario = (
        _normalizar_texto(
            tipo_inventario
        )
        .upper()
    )

    numero_rodada = int(
        numero_rodada
    )

    # ========================================================
    # RODADAS COMPLETAS
    #
    # ROTATIVO:
    # R1 é completa.
    #
    # OFICIAL:
    # R1 e R2 são completas.
    #
    # Para histórico, basta o item existir no snapshot.
    # Não dependemos de RodadaLocalizacoes porque registros
    # históricos antigos podem não possuir esse vínculo completo.
    # ========================================================

    rodada_completa = (
        (
            tipo_inventario == "ROTATIVO"
            and
            numero_rodada == 1
        )
        or
        (
            tipo_inventario == "OFICIAL"
            and
            numero_rodada in (1, 2)
        )
    )

    if rodada_completa:

        parametros = [
            id_inventario,
            codigo
        ]

        filtro_lote = ""

        if lote is not None:

            filtro_lote = """
                AND ISNULL(
                    LTRIM(RTRIM(E.Lote)),
                    ''
                ) = ?
            """

            parametros.append(
                lote
            )

        cursor.execute(
            f"""
            SELECT COUNT(*)

            FROM dbo.InventarioEstoqueSnapshot E

            WHERE
                E.ID_Inventario = ?

                AND LTRIM(
                    RTRIM(E.Codigo)
                ) = ?

                {filtro_lote}
            """,
            tuple(parametros)
        )

        return (
            cursor.fetchone()[0] > 0
        )

    # ========================================================
    # RODADAS DE DIVERGÊNCIA
    #
    # R2 ROTATIVO
    # R3+ OFICIAL
    # ========================================================

    parametros = [
        id_inventario,
        id_rodada,
        codigo
    ]

    filtro_lote = ""

    if lote is not None:

        filtro_lote = """
            AND ISNULL(
                LTRIM(RTRIM(RI.Lote)),
                ''
            ) = ?
        """

        parametros.append(
            lote
        )

    cursor.execute(
        f"""
        SELECT COUNT(*)

        FROM dbo.RodadaItens RI

        WHERE
            RI.ID_Inventario = ?
            AND RI.ID_Rodada = ?

            AND LTRIM(
                RTRIM(RI.Codigo)
            ) = ?

            {filtro_lote}
        """,
        tuple(parametros)
    )

    return (
        cursor.fetchone()[0] > 0
    )
# ============================================================
# CONTAGENS DO ITEM POR RODADA
#
# Histórico:
# - ATIVA
# - CANCELADA
#
# Não filtramos status porque cancelamentos fazem parte da
# trilha de auditoria.
# ============================================================

def _buscar_contagens_item_rodada(
    cursor,
    id_inventario: int,
    id_rodada: int,
    codigo: str,
    lote: str | None
):

    filtro_lote = ""

    parametros = [
        id_inventario,
        id_rodada,
        codigo
    ]

    if lote is not None:
        filtro_lote = """
            AND ISNULL(
                LTRIM(RTRIM(C.Lote)),
                ''
            ) = ?
        """
        parametros.append(
            lote
        )

    cursor.execute(
        f"""
        SELECT
            C.ID_Contagem,
            C.ID_Sessao,
            C.Codigo,
            ISNULL(C.Lote, '') AS Lote,
            C.Quantidade,
            C.Status,
            C.DataHora,
            C.CriadoPor,
            C.DataHoraCancelamento,
            C.CanceladoPor,
            C.MotivoCancelamento,

            S.Localizacao,
            S.DataHoraInicio AS SessaoInicio,
            S.DataHoraFim AS SessaoFim,
            S.Status AS StatusSessao,
            S.LocalizacaoVazia

        FROM dbo.Contagens C

        INNER JOIN dbo.SessoesContagem S
            ON S.ID_Sessao = C.ID_Sessao

        WHERE
            S.ID_Inventario = ?
            AND S.ID_Rodada = ?
            AND LTRIM(RTRIM(C.Codigo)) = ?
            {filtro_lote}

        ORDER BY
            C.DataHora,
            C.ID_Contagem
        """,
        tuple(parametros)
    )

    linhas = cursor.fetchall()

    return [
        {
            "id_contagem": linha.ID_Contagem,
            "id_sessao": linha.ID_Sessao,
            "localizacao": _normalizar_localizacao(
                linha.Localizacao
            ),
            "codigo": _normalizar_texto(
                linha.Codigo
            ),
            "lote": _normalizar_lote(
                linha.Lote
            ),
            "quantidade": _decimal_para_numero(
                linha.Quantidade
            ),
            "status": linha.Status,
            "data_hora": linha.DataHora,
            "criado_por": linha.CriadoPor,
            "cancelamento": {
                "cancelada": (
                    _normalizar_texto(
                        linha.Status
                    ).upper()
                    == "CANCELADA"
                ),
                "data_hora": linha.DataHoraCancelamento,
                "cancelado_por": linha.CanceladoPor,
                "motivo": linha.MotivoCancelamento
            },
            "sessao": {
                "status": linha.StatusSessao,
                "data_hora_inicio": linha.SessaoInicio,
                "data_hora_fim": linha.SessaoFim,
                "localizacao_vazia": (
                    bool(linha.LocalizacaoVazia)
                    if linha.LocalizacaoVazia is not None
                    else False
                )
            }
        }
        for linha in linhas
    ]


# ============================================================
# MOTIVO DE ENTRADA NA RODADA
# ============================================================

def _buscar_rodada_itens(
    cursor,
    id_inventario: int,
    id_rodada: int,
    codigo: str,
    lote: str | None
):

    filtro_lote = ""

    parametros = [
        id_inventario,
        id_rodada,
        codigo
    ]

    if lote is not None:
        filtro_lote = """
            AND ISNULL(
                LTRIM(RTRIM(Lote)),
                ''
            ) = ?
        """
        parametros.append(
            lote
        )

    cursor.execute(
        f"""
        SELECT
            ID_RodadaItem,
            Codigo,
            ISNULL(Lote, '') AS Lote,
            Motivo,
            Status,
            DataHoraCriacao

        FROM dbo.RodadaItens

        WHERE
            ID_Inventario = ?
            AND ID_Rodada = ?
            AND LTRIM(RTRIM(Codigo)) = ?
            {filtro_lote}

        ORDER BY
            ID_RodadaItem
        """,
        tuple(parametros)
    )

    linhas = cursor.fetchall()

    return [
        {
            "id_rodada_item": linha.ID_RodadaItem,
            "codigo": _normalizar_texto(
                linha.Codigo
            ),
            "lote": _normalizar_lote(
                linha.Lote
            ),
            "motivo": linha.Motivo,
            "status": linha.Status,
            "data_hora_criacao": linha.DataHoraCriacao
        }
        for linha in linhas
    ]


# ============================================================
# DECISÕES ROTATIVO
# ============================================================

def _buscar_decisoes_rotativo(
    cursor,
    id_inventario: int,
    id_rodada: int,
    codigo: str,
    lote: str | None
):

    filtro_lote = ""

    parametros = [
        id_inventario,
        id_rodada,
        codigo
    ]

    if lote is not None:
        filtro_lote = """
            AND ISNULL(
                LTRIM(RTRIM(Lote)),
                ''
            ) = ?
        """
        parametros.append(
            lote
        )

    cursor.execute(
        f"""
        SELECT
            ID_DecisaoRotativo,
            Localizacao,
            Codigo,
            ISNULL(Lote, '') AS Lote,
            StatusDivergencia,
            Decisao,
            Justificativa,
            Usuario,
            DataHora,
            Status

        FROM dbo.DecisoesRotativo

        WHERE
            ID_Inventario = ?
            AND ID_Rodada = ?
            AND LTRIM(RTRIM(Codigo)) = ?
            {filtro_lote}

        ORDER BY
            DataHora,
            ID_DecisaoRotativo
        """,
        tuple(parametros)
    )

    linhas = cursor.fetchall()

    return [
        {
            "id_decisao": linha.ID_DecisaoRotativo,
            "localizacao": _normalizar_localizacao(
                linha.Localizacao
            ),
            "codigo": _normalizar_texto(
                linha.Codigo
            ),
            "lote": _normalizar_lote(
                linha.Lote
            ),
            "status_divergencia": linha.StatusDivergencia,
            "decisao": linha.Decisao,
            "justificativa": linha.Justificativa,
            "usuario": linha.Usuario,
            "data_hora": linha.DataHora,
            "status": linha.Status
        }
        for linha in linhas
    ]


# ============================================================
# DECISÕES DO GESTOR
# ============================================================

def _buscar_decisoes_gestor(
    cursor,
    id_inventario: int,
    codigo: str,
    lote: str | None
):

    filtro_lote = ""

    parametros = [
        id_inventario,
        codigo
    ]

    if lote is not None:
        filtro_lote = """
            AND ISNULL(
                LTRIM(RTRIM(Lote)),
                ''
            ) = ?
        """
        parametros.append(
            lote
        )

    cursor.execute(
        f"""
        SELECT
            ID_Decisao,
            Codigo,
            ISNULL(Lote, '') AS Lote,
            Decisao,
            QuantidadeAprovada,
            Justificativa,
            Usuario,
            DataHora,
            Status

        FROM dbo.DecisoesGestorInventario

        WHERE
            ID_Inventario = ?
            AND LTRIM(RTRIM(Codigo)) = ?
            {filtro_lote}

        ORDER BY
            DataHora,
            ID_Decisao
        """,
        tuple(parametros)
    )

    linhas = cursor.fetchall()

    return [
        {
            "id_decisao": linha.ID_Decisao,
            "codigo": _normalizar_texto(
                linha.Codigo
            ),
            "lote": _normalizar_lote(
                linha.Lote
            ),
            "decisao": linha.Decisao,
            "quantidade_aprovada": (
                _decimal_para_numero(
                    linha.QuantidadeAprovada
                )
                if linha.QuantidadeAprovada is not None
                else None
            ),
            "justificativa": linha.Justificativa,
            "usuario": linha.Usuario,
            "data_hora": linha.DataHora,
            "status": linha.Status
        }
        for linha in linhas
    ]


# ============================================================
# RESULTADO FINAL
# ============================================================

def _buscar_resultado_final(
    cursor,
    id_inventario: int,
    codigo: str,
    lote: str | None
):

    filtro_lote = ""

    parametros = [
        id_inventario,
        codigo
    ]

    if lote is not None:
        filtro_lote = """
            AND ISNULL(
                LTRIM(RTRIM(Lote)),
                ''
            ) = ?
        """
        parametros.append(
            lote
        )

    cursor.execute(
        f"""
        SELECT
            ID_ResultadoFinal,
            Codigo,
            ISNULL(Lote, '') AS Lote,
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
            DataHoraFinalizacao,
            Localizacao

        FROM dbo.InventarioResultadoFinal

        WHERE
            ID_Inventario = ?
            AND LTRIM(RTRIM(Codigo)) = ?
            {filtro_lote}

        ORDER BY
            Localizacao,
            Lote,
            ID_ResultadoFinal
        """,
        tuple(parametros)
    )

    linhas = cursor.fetchall()

    return [
        {
            "id_resultado_final": linha.ID_ResultadoFinal,
            "localizacao": _normalizar_localizacao(
                linha.Localizacao
            ),
            "codigo": _normalizar_texto(
                linha.Codigo
            ),
            "lote": _normalizar_lote(
                linha.Lote
            ),
            "descricao": linha.Descricao,
            "unidade": linha.Unidade,
            "categoria": linha.Categoria,
            "qtd_estoque": _decimal_para_numero(
                linha.QtdEstoque
            ),
            "quantidade_final": _decimal_para_numero(
                linha.QuantidadeFinal
            ),
            "diferenca_final": _decimal_para_numero(
                linha.DiferencaFinal
            ),
            "status_final": linha.StatusFinal,
            "origem_quantidade": linha.OrigemQuantidade,
            "id_decisao_gestor": linha.ID_DecisaoGestor,
            "rodada_final": linha.RodadaFinal,
            "usuario_finalizacao": linha.UsuarioFinalizacao,
            "data_hora_finalizacao": linha.DataHoraFinalizacao
        }
        for linha in linhas
    ]


# ============================================================
# CONSULTAR HISTÓRICO ITEM / LOTE
# ============================================================

def consultar_historico_item(
    cursor,
    codigo: str,
    lote: str | None = None,
    cliente_id: int | None = None,
    data_inicio=None,
    data_fim=None
):

    codigo = _normalizar_texto(
        codigo
    )

    if not codigo:
        raise BusinessRuleViolation(
            "O código do item é obrigatório."
        )

    if lote is not None:
        lote = _normalizar_lote(
            lote
        )

    inventarios_encontrados = (
        _buscar_inventarios_item(
            cursor=cursor,
            codigo=codigo,
            lote=lote,
            cliente_id=cliente_id,
            data_inicio=data_inicio,
            data_fim=data_fim
        )
    )

    inventarios = []

    inventarios_com_resultado_final = 0
    inventarios_sem_resultado_final = 0
    inventarios_com_divergencia = 0
    inventarios_ok = 0

    total_faltas = 0
    total_sobras = 0
    total_resultados_ok = 0

    ultima_ocorrencia = None

    for inventario in inventarios_encontrados:

        id_inventario = (
            inventario.ID_Inventario
        )

        snapshot = (
            _buscar_snapshot_item(
                cursor=cursor,
                id_inventario=id_inventario,
                codigo=codigo,
                lote=lote
            )
        )

        qtd_snapshot = sum(
            item["saldo_inventario"]
            for item in snapshot
        )

        rodadas_banco = (
            _buscar_rodadas_inventario(
                cursor=cursor,
                id_inventario=id_inventario
            )
        )

        rodadas = []

        for rodada in rodadas_banco:

            contagens = (
                _buscar_contagens_item_rodada(
                    cursor=cursor,
                    id_inventario=id_inventario,
                    id_rodada=rodada.ID_Rodada,
                    codigo=codigo,
                    lote=lote
                )
            )

            rodada_itens = (
                _buscar_rodada_itens(
                    cursor=cursor,
                    id_inventario=id_inventario,
                    id_rodada=rodada.ID_Rodada,
                    codigo=codigo,
                    lote=lote
                )
            )

            decisoes_rotativo = (
                _buscar_decisoes_rotativo(
                    cursor=cursor,
                    id_inventario=id_inventario,
                    id_rodada=rodada.ID_Rodada,
                    codigo=codigo,
                    lote=lote
                )
            )

            item_previsto = (
    _item_previsto_na_rodada(
        cursor=cursor,
        id_inventario=id_inventario,
        id_rodada=rodada.ID_Rodada,
        numero_rodada=rodada.NumeroRodada,
        tipo_inventario=inventario.Tipo,
        codigo=codigo,
        lote=lote
    )
)

            possui_atividade_item = (
                item_previsto
                or bool(contagens)
                or bool(rodada_itens)
                or bool(decisoes_rotativo)
            )

            if not possui_atividade_item:
                continue

            quantidade_contada_ativa = sum(
                item["quantidade"]
                for item in contagens
                if (
                    _normalizar_texto(
                        item.get(
                            "status"
                        )
                    ).upper()
                    == "ATIVA"
                )
            )

            # Para R1, o comparativo é naturalmente contra o snapshot.
            # Para R2+, esta leitura serve como trilha histórica simples
            # do item. A classificação final definitiva continua sendo
            # a de InventarioResultadoFinal.
            if quantidade_contada_ativa < qtd_snapshot:
                status_item_rodada = "FALTA"

            elif quantidade_contada_ativa > qtd_snapshot:
                status_item_rodada = "SOBRA"

            else:
                status_item_rodada = "OK"

            rodadas.append(
                {
                    "id_rodada": rodada.ID_Rodada,
                    "numero_rodada": rodada.NumeroRodada,
                    "status": rodada.Status,
                    "data_hora_inicio": rodada.DataHoraInicio,
                    "data_hora_fim": rodada.DataHoraFim,
                    "criado_por": rodada.CriadoPor,
                    "data_hora_criacao": rodada.DataHoraCriacao,

                    "item_previsto": item_previsto,
                    "qtd_snapshot": qtd_snapshot,
                    "qtd_contada_ativa": quantidade_contada_ativa,
                    "status_item_rodada": status_item_rodada,

                    "motivos_recontagem": rodada_itens,
                    "contagens": contagens,
                    "decisoes_rotativo": decisoes_rotativo
                }
            )

        decisoes_gestor = (
            _buscar_decisoes_gestor(
                cursor=cursor,
                id_inventario=id_inventario,
                codigo=codigo,
                lote=lote
            )
        )

        resultado_final = (
            _buscar_resultado_final(
                cursor=cursor,
                id_inventario=id_inventario,
                codigo=codigo,
                lote=lote
            )
        )

        resultado_final_esperado = (
            _normalizar_texto(
                inventario.Status
            ).upper()
            == "FINALIZADO"
        )

        resultado_final_encontrado = (
            len(resultado_final) > 0
        )

        if (
            resultado_final_esperado
            and
            not resultado_final_encontrado
        ):
            status_consistencia = (
                "INCONSISTENTE"
            )

        else:
            status_consistencia = "OK"

        if resultado_final_encontrado:
            inventarios_com_resultado_final += 1
        elif resultado_final_esperado:
            inventarios_sem_resultado_final += 1

        possui_divergencia = False
        possui_ok = False

        for resultado in resultado_final:

            status_final = (
                _normalizar_texto(
                    resultado[
                        "status_final"
                    ]
                ).upper()
            )

            diferenca = (
                resultado[
                    "diferenca_final"
                ]
            )

            if (
                status_final == "OK"
                or diferenca == 0
            ):
                total_resultados_ok += 1
                possui_ok = True

            elif (
                status_final == "FALTA"
                or diferenca < 0
            ):
                total_faltas += 1
                possui_divergencia = True

            elif (
                status_final == "SOBRA"
                or diferenca > 0
            ):
                total_sobras += 1
                possui_divergencia = True

            else:
                possui_divergencia = True

        if possui_divergencia:
            inventarios_com_divergencia += 1

        elif (
            resultado_final_encontrado
            and
            possui_ok
        ):
            inventarios_ok += 1

        data_referencia = (
            inventario.DataHoraFim
            or
            inventario.DataHoraInicio
        )

        if (
            data_referencia is not None
            and
            (
                ultima_ocorrencia is None
                or
                data_referencia
                >
                ultima_ocorrencia
            )
        ):
            ultima_ocorrencia = (
                data_referencia
            )

        inventarios.append(
            {
                "id_inventario": id_inventario,
                "codigo_inventario": inventario.CodigoInventario,
                "tipo": inventario.Tipo,
                "cliente": inventario.Cliente,
                "cliente_id": inventario.ClienteId,
                "armazem": inventario.cArmazem,
                "descricao": inventario.Descricao,
                "status": inventario.Status,
                "rodada_atual": inventario.RodadaAtual,
                "data_hora_inicio": inventario.DataHoraInicio,
                "data_hora_fim": inventario.DataHoraFim,
                "criado_por": inventario.CriadoPor,
                "finalizado_por": inventario.FinalizadoPor,

                "consistencia": {
                    "resultado_final_esperado":
                        resultado_final_esperado,

                    "resultado_final_encontrado":
                        resultado_final_encontrado,

                    "status":
                        status_consistencia
                },

                "snapshot": snapshot,
                "rodadas": rodadas,
                "decisoes_gestor": decisoes_gestor,
                "resultado_final": resultado_final
            }
        )

    possui_recorrencia = (
        inventarios_com_divergencia >= 2
    )

    return {
        "tipo_consulta":
            "HISTORICO_ITEM_LOTE",

        "pesquisa": {
            "codigo": codigo,
            "lote": lote,
            "cliente_id": cliente_id,
            "data_inicio": data_inicio,
            "data_fim": data_fim
        },

        "resumo": {
            "inventarios_encontrados":
                len(inventarios),

            "inventarios_com_resultado_final":
                inventarios_com_resultado_final,

            "inventarios_sem_resultado_final":
                inventarios_sem_resultado_final,

            "inventarios_ok":
                inventarios_ok,

            "inventarios_com_divergencia":
                inventarios_com_divergencia,

            "ocorrencias_falta":
                total_faltas,

            "ocorrencias_sobra":
                total_sobras,

            "ocorrencias_ok":
                total_resultados_ok,

            "ultima_ocorrencia":
                ultima_ocorrencia,

            "possui_recorrencia":
                possui_recorrencia
        },

        "inventarios":
            inventarios
    }
