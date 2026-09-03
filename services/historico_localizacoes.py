from domain.exceptions import BusinessRuleViolation


# ============================================================
# NORMALIZAÇÃO
# ============================================================

def _normalizar_texto(valor):
    if valor is None:
        return ""

    return str(valor).strip()


def _normalizar_localizacao(valor):
    return _normalizar_texto(valor).upper()


def _normalizar_lote(valor):
    return _normalizar_texto(valor)


def _decimal_para_numero(valor):
    if valor is None:
        return 0

    return float(valor)


# ============================================================
# BUSCAR INVENTÁRIOS DA LOCALIZAÇÃO
# ============================================================

def _buscar_inventarios_localizacao(
    cursor,
    localizacao: str,
    cliente_id: int | None = None,
    tipo: str | None = None,
    data_inicio=None,
    data_fim=None,
    page: int = 1,
    page_size: int = 20
):

    filtros = []
    parametros_filtros = []

    if cliente_id is not None:
        filtros.append(
            "I.ClienteId = ?"
        )
        parametros_filtros.append(
            cliente_id
        )

    if _normalizar_texto(tipo):
        filtros.append(
            "UPPER(LTRIM(RTRIM(I.Tipo))) = ?"
        )
        parametros_filtros.append(
            _normalizar_texto(tipo).upper()
        )

    if data_inicio is not None:
        filtros.append(
            "I.DataHoraInicio >= ?"
        )
        parametros_filtros.append(
            data_inicio
        )

    if data_fim is not None:
        filtros.append(
            """
            I.DataHoraInicio < DATEADD(
                DAY,
                1,
                CAST(? AS date)
            )
            """
        )
        parametros_filtros.append(
            data_fim
        )

    filtro_sql = ""

    if filtros:
        filtro_sql = (
            " AND "
            +
            " AND ".join(
                filtros
            )
        )

    sql = f"""
        SELECT
            COUNT(*) OVER() AS TotalRegistros,
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
                        AND UPPER(
                            LTRIM(RTRIM(E.Localizacao))
                        ) = ?
                )

                OR EXISTS
                (
                    SELECT 1
                    FROM dbo.RodadaLocalizacoes RL
                    WHERE
                        RL.ID_Inventario = I.ID_Inventario
                        AND UPPER(
                            LTRIM(RTRIM(RL.Localizacao))
                        ) = ?
                )

                OR EXISTS
                (
                    SELECT 1
                    FROM dbo.SessoesContagem S
                    WHERE
                        S.ID_Inventario = I.ID_Inventario
                        AND UPPER(
                            LTRIM(RTRIM(S.Localizacao))
                        ) = ?
                )

                OR EXISTS
                (
                    SELECT 1
                    FROM dbo.InventarioResultadoFinal RF
                    WHERE
                        RF.ID_Inventario = I.ID_Inventario
                        AND UPPER(
                            LTRIM(RTRIM(RF.Localizacao))
                        ) = ?
                )
            )

            {filtro_sql}

        ORDER BY
            I.DataHoraInicio DESC,
            I.ID_Inventario DESC

        OFFSET ? ROWS
        FETCH NEXT ? ROWS ONLY
    """

    parametros = [
        localizacao,
        localizacao,
        localizacao,
        localizacao
    ]

    parametros.extend(
        parametros_filtros
    )

    offset = (page - 1) * page_size
    parametros.extend([offset, page_size])

    cursor.execute(
        sql,
        tuple(parametros)
    )

    return cursor.fetchall()


# ============================================================
# SNAPSHOT DA LOCALIZAÇÃO
# ============================================================

def _buscar_snapshot_localizacao(
    cursor,
    id_inventario: int,
    localizacao: str
):

    cursor.execute(
        """
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
            AND UPPER(
                LTRIM(RTRIM(Localizacao))
            ) = ?

        ORDER BY
            Codigo,
            Lote,
            ID_Snapshot
        """,
        (
            id_inventario,
            localizacao
        )
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
# REGISTRO DA LOCALIZAÇÃO NA RODADA
# ============================================================

def _buscar_registro_localizacao_rodada(
    cursor,
    id_inventario: int,
    id_rodada: int,
    localizacao: str
):

    cursor.execute(
        """
        SELECT TOP 1
            ID_RodadaLocalizacao,
            Status,
            DataHoraCriacao

        FROM dbo.RodadaLocalizacoes

        WHERE
            ID_Inventario = ?
            AND ID_Rodada = ?
            AND UPPER(
                LTRIM(RTRIM(Localizacao))
            ) = ?

        ORDER BY
            ID_RodadaLocalizacao DESC
        """,
        (
            id_inventario,
            id_rodada,
            localizacao
        )
    )

    linha = cursor.fetchone()

    if not linha:
        return None

    return {
        "id_rodada_localizacao":
            linha.ID_RodadaLocalizacao,

        "status":
            linha.Status,

        "data_hora_criacao":
            linha.DataHoraCriacao
    }


# ============================================================
# SESSÕES DA LOCALIZAÇÃO NA RODADA
# ============================================================

def _buscar_sessoes_localizacao_rodada(
    cursor,
    id_inventario: int,
    id_rodada: int,
    localizacao: str
):

    cursor.execute(
        """
        SELECT
            ID_Sessao,
            Localizacao,
            DataHoraInicio,
            DataHoraFim,
            Status,
            LocalizacaoVazia

        FROM dbo.SessoesContagem

        WHERE
            ID_Inventario = ?
            AND ID_Rodada = ?
            AND UPPER(
                LTRIM(RTRIM(Localizacao))
            ) = ?

        ORDER BY
            DataHoraInicio,
            ID_Sessao
        """,
        (
            id_inventario,
            id_rodada,
            localizacao
        )
    )

    linhas = cursor.fetchall()

    return [
        {
            "id_sessao":
                linha.ID_Sessao,

            "localizacao":
                _normalizar_localizacao(
                    linha.Localizacao
                ),

            "data_hora_inicio":
                linha.DataHoraInicio,

            "data_hora_fim":
                linha.DataHoraFim,

            "status":
                linha.Status,

            "localizacao_vazia":
                (
                    bool(linha.LocalizacaoVazia)
                    if linha.LocalizacaoVazia is not None
                    else False
                )
        }
        for linha in linhas
    ]


# ============================================================
# CONTAGENS DA LOCALIZAÇÃO NA RODADA
# ============================================================

def _buscar_contagens_localizacao_rodada(
    cursor,
    id_inventario: int,
    id_rodada: int,
    localizacao: str
):

    cursor.execute(
        """
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

            S.Status AS StatusSessao,
            S.LocalizacaoVazia

        FROM dbo.Contagens C

        INNER JOIN dbo.SessoesContagem S
            ON S.ID_Sessao = C.ID_Sessao

        WHERE
            S.ID_Inventario = ?
            AND S.ID_Rodada = ?
            AND UPPER(
                LTRIM(RTRIM(S.Localizacao))
            ) = ?

        ORDER BY
            C.DataHora,
            C.ID_Contagem
        """,
        (
            id_inventario,
            id_rodada,
            localizacao
        )
    )

    linhas = cursor.fetchall()

    return [
        {
            "id_contagem":
                linha.ID_Contagem,

            "id_sessao":
                linha.ID_Sessao,

            "codigo":
                _normalizar_texto(
                    linha.Codigo
                ),

            "lote":
                _normalizar_lote(
                    linha.Lote
                ),

            "quantidade":
                _decimal_para_numero(
                    linha.Quantidade
                ),

            "status":
                linha.Status,

            "data_hora":
                linha.DataHora,

            "criado_por":
                linha.CriadoPor,

            "cancelamento": {
                "cancelada":
                    (
                        _normalizar_texto(
                            linha.Status
                        ).upper()
                        == "CANCELADA"
                    ),

                "data_hora":
                    linha.DataHoraCancelamento,

                "cancelado_por":
                    linha.CanceladoPor,

                "motivo":
                    linha.MotivoCancelamento
            },

            "sessao": {
                "status":
                    linha.StatusSessao,

                "localizacao_vazia":
                    (
                        bool(linha.LocalizacaoVazia)
                        if linha.LocalizacaoVazia is not None
                        else False
                    )
            }
        }
        for linha in linhas
    ]


# ============================================================
# DECISÕES ROTATIVAS DA LOCALIZAÇÃO
# ============================================================

def _buscar_decisoes_rotativo_localizacao(
    cursor,
    id_inventario: int,
    id_rodada: int,
    localizacao: str
):

    cursor.execute(
        """
        SELECT
            ID_DecisaoRotativo,
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
            AND UPPER(
                LTRIM(RTRIM(Localizacao))
            ) = ?

        ORDER BY
            DataHora,
            ID_DecisaoRotativo
        """,
        (
            id_inventario,
            id_rodada,
            localizacao
        )
    )

    linhas = cursor.fetchall()

    return [
        {
            "id_decisao":
                linha.ID_DecisaoRotativo,

            "codigo":
                _normalizar_texto(
                    linha.Codigo
                ),

            "lote":
                _normalizar_lote(
                    linha.Lote
                ),

            "status_divergencia":
                linha.StatusDivergencia,

            "decisao":
                linha.Decisao,

            "justificativa":
                linha.Justificativa,

            "usuario":
                linha.Usuario,

            "data_hora":
                linha.DataHora,

            "status":
                linha.Status
        }
        for linha in linhas
    ]


# ============================================================
# ITENS PREVISTOS NA RODADA
# ============================================================

def _buscar_itens_previstos_rodada(
    cursor,
    id_inventario: int,
    id_rodada: int,
    numero_rodada: int,
    tipo_inventario: str,
    localizacao: str
):

    tipo_inventario = (
        _normalizar_texto(
            tipo_inventario
        ).upper()
    )

    numero_rodada = int(
        numero_rodada
    )

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

        cursor.execute(
            """
            SELECT
                LTRIM(RTRIM(Codigo)) AS Codigo,
                ISNULL(
                    LTRIM(RTRIM(Lote)),
                    ''
                ) AS Lote,

                MAX(Descricao) AS Descricao,
                MAX(Unidade) AS Unidade,
                MAX(Categoria) AS Categoria,

                SUM(
                    COALESCE(
                        SaldoInventario,
                        0
                    )
                ) AS QtdPrevista

            FROM dbo.InventarioEstoqueSnapshot

            WHERE
                ID_Inventario = ?
                AND UPPER(
                    LTRIM(RTRIM(Localizacao))
                ) = ?

            GROUP BY
                LTRIM(RTRIM(Codigo)),
                ISNULL(
                    LTRIM(RTRIM(Lote)),
                    ''
                )

            ORDER BY
                Codigo,
                Lote
            """,
            (
                id_inventario,
                localizacao
            )
        )

    else:

        cursor.execute(
            """
            WITH ItensRodada AS
            (
                SELECT
                    LTRIM(RTRIM(RI.Codigo)) AS Codigo,
                    ISNULL(
                        LTRIM(RTRIM(RI.Lote)),
                        ''
                    ) AS Lote

                FROM dbo.RodadaItens RI

                WHERE
                    RI.ID_Inventario = ?
                    AND RI.ID_Rodada = ?
            ),

            ItensLocalizacao AS
            (
                SELECT DISTINCT
                    LTRIM(RTRIM(E.Codigo)) AS Codigo,
                    ISNULL(
                        LTRIM(RTRIM(E.Lote)),
                        ''
                    ) AS Lote

                FROM dbo.InventarioEstoqueSnapshot E

                WHERE
                    E.ID_Inventario = ?
                    AND UPPER(
                        LTRIM(RTRIM(E.Localizacao))
                    ) = ?

                UNION

                SELECT DISTINCT
                    LTRIM(RTRIM(C.Codigo)) AS Codigo,
                    ISNULL(
                        LTRIM(RTRIM(C.Lote)),
                        ''
                    ) AS Lote

                FROM dbo.Contagens C

                INNER JOIN dbo.SessoesContagem S
                    ON S.ID_Sessao = C.ID_Sessao

                WHERE
                    S.ID_Inventario = ?
                    AND UPPER(
                        LTRIM(RTRIM(S.Localizacao))
                    ) = ?
            )

            SELECT
                IR.Codigo,
                IR.Lote,

                MAX(E.Descricao) AS Descricao,
                MAX(E.Unidade) AS Unidade,
                MAX(E.Categoria) AS Categoria,

                COALESCE(
                    SUM(E.SaldoInventario),
                    0
                ) AS QtdPrevista

            FROM ItensRodada IR

            INNER JOIN ItensLocalizacao IL
                ON IL.Codigo = IR.Codigo
                AND IL.Lote = IR.Lote

            LEFT JOIN dbo.InventarioEstoqueSnapshot E
                ON E.ID_Inventario = ?
                AND UPPER(
                    LTRIM(RTRIM(E.Localizacao))
                ) = ?
                AND LTRIM(RTRIM(E.Codigo)) = IR.Codigo
                AND ISNULL(
                    LTRIM(RTRIM(E.Lote)),
                    ''
                ) = IR.Lote

            GROUP BY
                IR.Codigo,
                IR.Lote

            ORDER BY
                IR.Codigo,
                IR.Lote
            """,
            (
                id_inventario,
                id_rodada,
                id_inventario,
                localizacao,
                id_inventario,
                localizacao,
                id_inventario,
                localizacao
            )
        )

    linhas = cursor.fetchall()

    return [
        {
            "codigo":
                _normalizar_texto(
                    linha.Codigo
                ),

            "lote":
                _normalizar_lote(
                    linha.Lote
                ),

            "descricao":
                linha.Descricao,

            "unidade":
                linha.Unidade,

            "categoria":
                linha.Categoria,

            "qtd_prevista":
                _decimal_para_numero(
                    linha.QtdPrevista
                )
        }
        for linha in linhas
    ]


# ============================================================
# CONSOLIDAR ITENS DA RODADA
# ============================================================

def _consolidar_itens_rodada(
    itens_previstos,
    contagens
):

    base = {}

    for item in itens_previstos:

        chave = (
            item["codigo"],
            item["lote"]
        )

        base[chave] = {
            "codigo":
                item["codigo"],

            "lote":
                item["lote"],

            "descricao":
                item["descricao"],

            "unidade":
                item["unidade"],

            "categoria":
                item["categoria"],

            "qtd_prevista":
                float(
                    item["qtd_prevista"]
                    or
                    0
                ),

            "qtd_contada_ativa":
                0.0,

            "bipagens_ativas":
                0,

            "bipagens_canceladas":
                0
        }

    for contagem in contagens:

        chave = (
            contagem["codigo"],
            contagem["lote"]
        )

        if chave not in base:
            base[chave] = {
                "codigo":
                    contagem["codigo"],

                "lote":
                    contagem["lote"],

                "descricao":
                    None,

                "unidade":
                    None,

                "categoria":
                    None,

                "qtd_prevista":
                    0.0,

                "qtd_contada_ativa":
                    0.0,

                "bipagens_ativas":
                    0,

                "bipagens_canceladas":
                    0
            }

        status = (
            _normalizar_texto(
                contagem["status"]
            ).upper()
        )

        if status == "ATIVA":

            base[chave][
                "qtd_contada_ativa"
            ] += float(
                contagem["quantidade"]
                or
                0
            )

            base[chave][
                "bipagens_ativas"
            ] += 1

        elif status == "CANCELADA":

            base[chave][
                "bipagens_canceladas"
            ] += 1

    itens = []

    for item in base.values():

        diferenca = (
            item["qtd_contada_ativa"]
            -
            item["qtd_prevista"]
        )

        if abs(diferenca) <= 0.0001:
            status = "OK"

        elif diferenca < 0:
            status = "FALTA"

        else:
            status = "SOBRA"

        item["diferenca"] = diferenca
        item["status"] = status

        itens.append(
            item
        )

    itens.sort(
        key=lambda item: (
            item["codigo"],
            item["lote"]
        )
    )

    return itens


# ============================================================
# RESULTADO FINAL - INVENTÁRIO COMPLETO
#
# Serve para verificar se o inventário possui resultado final,
# independentemente de a coluna Localizacao estar preenchida.
# ============================================================

def _buscar_resultado_final_inventario(
    cursor,
    id_inventario: int
):

    cursor.execute(
        """
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

        ORDER BY
            Codigo,
            Lote,
            ID_ResultadoFinal
        """,
        id_inventario
    )

    return cursor.fetchall()


# ============================================================
# LOCALIZAÇÕES DO ITEM NO SNAPSHOT
#
# Usado apenas para inferir localização de resultados finais
# antigos que foram gravados com Localizacao vazia.
# ============================================================

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
                LTRIM(RTRIM(Localizacao))
            ) AS Localizacao

        FROM dbo.InventarioEstoqueSnapshot

        WHERE
            ID_Inventario = ?
            AND LTRIM(RTRIM(Codigo)) = ?
            AND ISNULL(
                LTRIM(RTRIM(Lote)),
                ''
            ) = ?
            AND NULLIF(
                LTRIM(RTRIM(Localizacao)),
                ''
            ) IS NOT NULL

        ORDER BY
            UPPER(
                LTRIM(RTRIM(Localizacao))
            )
        """,
        (
            id_inventario,
            codigo,
            lote
        )
    )

    return [
        _normalizar_localizacao(
            linha.Localizacao
        )
        for linha in cursor.fetchall()
        if _normalizar_localizacao(
            linha.Localizacao
        )
    ]


# ============================================================
# RESULTADO FINAL DA LOCALIZAÇÃO
#
# Regras:
# 1. Localizacao preenchida e igual à pesquisada:
#    atribuição DIRETA.
#
# 2. Localizacao vazia:
#    tenta inferir por Código + Lote no snapshot.
#    Se existir exatamente UMA localização no snapshot e ela
#    for a localização pesquisada, atribui como
#    INFERIDA_SNAPSHOT.
#
# 3. Se houver mais de uma localização possível, não atribui
#    automaticamente.
# ============================================================

def _resolver_resultado_final_localizacao(
    cursor,
    id_inventario: int,
    localizacao: str,
    linhas_resultado_final
):

    resultados = []
    nao_atribuidos = []

    possui_direta = False
    possui_inferida = False

    cache_localizacoes = {}

    for linha in linhas_resultado_final:

        codigo = _normalizar_texto(
            linha.Codigo
        )

        lote = _normalizar_lote(
            linha.Lote
        )

        localizacao_registrada = (
            _normalizar_localizacao(
                linha.Localizacao
            )
        )

        atribuicao = None
        localizacao_resolvida = None
        localizacoes_possiveis = []

        if localizacao_registrada:

            if (
                localizacao_registrada
                ==
                localizacao
            ):
                atribuicao = "DIRETA"
                localizacao_resolvida = (
                    localizacao_registrada
                )
                possui_direta = True
            else:
                continue

        else:

            chave = (
                codigo,
                lote
            )

            if chave not in cache_localizacoes:
                cache_localizacoes[chave] = (
                    _buscar_localizacoes_snapshot_item(
                        cursor=cursor,
                        id_inventario=id_inventario,
                        codigo=codigo,
                        lote=lote
                    )
                )

            localizacoes_possiveis = (
                cache_localizacoes[
                    chave
                ]
            )

            if (
                len(localizacoes_possiveis)
                == 1
                and
                localizacoes_possiveis[0]
                ==
                localizacao
            ):
                atribuicao = (
                    "INFERIDA_SNAPSHOT"
                )

                localizacao_resolvida = (
                    localizacao
                )

                possui_inferida = True

            else:

                motivo = (
                    "SEM_LOCALIZACAO_NO_SNAPSHOT"
                    if len(localizacoes_possiveis) == 0
                    else
                    "LOCALIZACAO_AMBIGUA"
                )

                nao_atribuidos.append(
                    {
                        "id_resultado_final":
                            linha.ID_ResultadoFinal,

                        "codigo":
                            codigo,

                        "lote":
                            lote,

                        "motivo":
                            motivo,

                        "localizacoes_possiveis":
                            localizacoes_possiveis
                    }
                )

                continue

        resultados.append(
            {
                "id_resultado_final":
                    linha.ID_ResultadoFinal,

                "localizacao":
                    localizacao_resolvida,

                "localizacao_original":
                    localizacao_registrada,

                "atribuicao_localizacao":
                    atribuicao,

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
                    _decimal_para_numero(
                        linha.QtdEstoque
                    ),

                "quantidade_final":
                    _decimal_para_numero(
                        linha.QuantidadeFinal
                    ),

                "diferenca_final":
                    _decimal_para_numero(
                        linha.DiferencaFinal
                    ),

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
                    linha.DataHoraFinalizacao
            }
        )

    if possui_direta and possui_inferida:
        tipo_atribuicao = "MISTA"

    elif possui_direta:
        tipo_atribuicao = "DIRETA"

    elif possui_inferida:
        tipo_atribuicao = (
            "INFERIDA_SNAPSHOT"
        )

    else:
        tipo_atribuicao = (
            "NAO_IDENTIFICADA"
        )

    return {
        "itens":
            resultados,

        "nao_atribuidos":
            nao_atribuidos,

        "tipo_atribuicao":
            tipo_atribuicao
    }


# ============================================================
# CONSULTAR HISTÓRICO DA LOCALIZAÇÃO
# ============================================================

def consultar_historico_localizacao(
    cursor,
    localizacao: str,
    cliente_id: int | None = None,
    tipo: str | None = None,
    data_inicio=None,
    data_fim=None,
    page: int = 1,
    page_size: int = 20
):

    localizacao = (
        _normalizar_localizacao(
            localizacao
        )
    )

    if not localizacao:
        raise BusinessRuleViolation(
            "A localização é obrigatória."
        )

    page = int(page)
    page_size = int(page_size)

    if page < 1:
        raise BusinessRuleViolation(
            "A página deve ser maior ou igual a 1."
        )

    if page_size < 1 or page_size > 200:
        raise BusinessRuleViolation(
            "O tamanho da página deve estar entre 1 e 200."
        )

    inventarios_banco = (
        _buscar_inventarios_localizacao(
            cursor=cursor,
            localizacao=localizacao,
            cliente_id=cliente_id,
            tipo=tipo,
            data_inicio=data_inicio,
            data_fim=data_fim,
            page=page,
            page_size=page_size
        )
    )

    total_registros = (
        int(inventarios_banco[0].TotalRegistros)
        if inventarios_banco
        else 0
    )

    total_paginas = (
        (total_registros + page_size - 1) // page_size
    )

    inventarios = []

    inventarios_ok = 0
    inventarios_com_divergencia = 0

    inventarios_com_resultado_final = 0
    inventarios_sem_resultado_final = 0

    ocorrencias_falta = 0
    ocorrencias_sobra = 0
    ocorrencias_ok = 0

    ultima_ocorrencia = None

    recorrencia_itens = {}

    for inventario in inventarios_banco:

        id_inventario = (
            inventario.ID_Inventario
        )

        snapshot = (
            _buscar_snapshot_localizacao(
                cursor=cursor,
                id_inventario=id_inventario,
                localizacao=localizacao
            )
        )

        rodadas_banco = (
            _buscar_rodadas_inventario(
                cursor=cursor,
                id_inventario=id_inventario
            )
        )

        rodadas = []

        for rodada in rodadas_banco:

            registro_localizacao = (
                _buscar_registro_localizacao_rodada(
                    cursor=cursor,
                    id_inventario=id_inventario,
                    id_rodada=rodada.ID_Rodada,
                    localizacao=localizacao
                )
            )

            sessoes = (
                _buscar_sessoes_localizacao_rodada(
                    cursor=cursor,
                    id_inventario=id_inventario,
                    id_rodada=rodada.ID_Rodada,
                    localizacao=localizacao
                )
            )

            contagens = (
                _buscar_contagens_localizacao_rodada(
                    cursor=cursor,
                    id_inventario=id_inventario,
                    id_rodada=rodada.ID_Rodada,
                    localizacao=localizacao
                )
            )

            decisoes_rotativo = (
                _buscar_decisoes_rotativo_localizacao(
                    cursor=cursor,
                    id_inventario=id_inventario,
                    id_rodada=rodada.ID_Rodada,
                    localizacao=localizacao
                )
            )

            itens_previstos = (
                _buscar_itens_previstos_rodada(
                    cursor=cursor,
                    id_inventario=id_inventario,
                    id_rodada=rodada.ID_Rodada,
                    numero_rodada=rodada.NumeroRodada,
                    tipo_inventario=inventario.Tipo,
                    localizacao=localizacao
                )
            )

            itens_rodada = (
                _consolidar_itens_rodada(
                    itens_previstos=itens_previstos,
                    contagens=contagens
                )
            )

            possui_participacao = (
                registro_localizacao is not None
                or bool(sessoes)
                or bool(contagens)
                or bool(decisoes_rotativo)
                or bool(itens_previstos)
            )

            if not possui_participacao:
                continue

            itens_ok = sum(
                1
                for item in itens_rodada
                if item["status"] == "OK"
            )

            faltas = sum(
                1
                for item in itens_rodada
                if item["status"] == "FALTA"
            )

            sobras = sum(
                1
                for item in itens_rodada
                if item["status"] == "SOBRA"
            )

            rodadas.append(
                {
                    "id_rodada":
                        rodada.ID_Rodada,

                    "numero_rodada":
                        rodada.NumeroRodada,

                    "status_rodada":
                        rodada.Status,

                    "data_hora_inicio":
                        rodada.DataHoraInicio,

                    "data_hora_fim":
                        rodada.DataHoraFim,

                    "criado_por":
                        rodada.CriadoPor,

                    "registro_localizacao":
                        registro_localizacao,

                    "sessoes":
                        sessoes,

                    "resumo": {
                        "itens":
                            len(
                                itens_rodada
                            ),

                        "ok":
                            itens_ok,

                        "faltas":
                            faltas,

                        "sobras":
                            sobras,

                        "bipagens_ativas":
                            sum(
                                item[
                                    "bipagens_ativas"
                                ]
                                for item in itens_rodada
                            ),

                        "bipagens_canceladas":
                            sum(
                                item[
                                    "bipagens_canceladas"
                                ]
                                for item in itens_rodada
                            )
                    },

                    "itens":
                        itens_rodada,

                    "contagens":
                        contagens,

                    "decisoes_rotativo":
                        decisoes_rotativo
                }
            )

        # ====================================================
        # RESULTADO FINAL
        # ====================================================

        resultado_final_banco = (
            _buscar_resultado_final_inventario(
                cursor=cursor,
                id_inventario=id_inventario
            )
        )

        resultado_resolvido = (
            _resolver_resultado_final_localizacao(
                cursor=cursor,
                id_inventario=id_inventario,
                localizacao=localizacao,
                linhas_resultado_final=(
                    resultado_final_banco
                )
            )
        )

        resultado_final = (
            resultado_resolvido[
                "itens"
            ]
        )

        resultado_final_esperado = (
            _normalizar_texto(
                inventario.Status
            ).upper()
            == "FINALIZADO"
        )

        resultado_final_inventario_encontrado = (
            len(
                resultado_final_banco
            ) > 0
        )

        resultado_final_localizacao_encontrado = (
            len(
                resultado_final
            ) > 0
        )

        # Só existe inconsistência estrutural se o inventário
        # finalizado não possuir nenhum resultado final.
        if (
            resultado_final_esperado
            and
            not resultado_final_inventario_encontrado
        ):
            status_consistencia = (
                "INCONSISTENTE"
            )

        else:
            status_consistencia = "OK"

        if resultado_final_inventario_encontrado:
            inventarios_com_resultado_final += 1

        elif resultado_final_esperado:
            inventarios_sem_resultado_final += 1

        possui_divergencia_final = False
        possui_resultado_ok = False

        for resultado in resultado_final:

            status_final = (
                _normalizar_texto(
                    resultado["status_final"]
                ).upper()
            )

            diferenca_final = float(
                resultado[
                    "diferenca_final"
                ]
                or
                0
            )

            chave_item = (
                resultado["codigo"],
                resultado["lote"]
            )

            if chave_item not in recorrencia_itens:
                recorrencia_itens[chave_item] = {
                    "codigo":
                        resultado["codigo"],

                    "lote":
                        resultado["lote"],

                    "ocorrencias":
                        0,

                    "faltas":
                        0,

                    "sobras":
                        0,

                    "ok":
                        0
                }

            recorrencia_itens[
                chave_item
            ]["ocorrencias"] += 1

            if (
                status_final == "OK"
                or
                abs(diferenca_final) <= 0.0001
            ):
                ocorrencias_ok += 1
                possui_resultado_ok = True

                recorrencia_itens[
                    chave_item
                ]["ok"] += 1

            elif (
                status_final == "FALTA"
                or
                diferenca_final < 0
            ):
                ocorrencias_falta += 1
                possui_divergencia_final = True

                recorrencia_itens[
                    chave_item
                ]["faltas"] += 1

            else:
                ocorrencias_sobra += 1
                possui_divergencia_final = True

                recorrencia_itens[
                    chave_item
                ]["sobras"] += 1

        if possui_divergencia_final:
            inventarios_com_divergencia += 1

        elif (
            resultado_final_localizacao_encontrado
            and
            possui_resultado_ok
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

        total_resultado = len(
            resultado_final
        )

        total_ok = sum(
            1
            for item in resultado_final
            if (
                _normalizar_texto(
                    item[
                        "status_final"
                    ]
                ).upper()
                == "OK"
                or
                abs(
                    float(
                        item[
                            "diferenca_final"
                        ]
                        or
                        0
                    )
                )
                <= 0.0001
            )
        )

        total_faltas = sum(
            1
            for item in resultado_final
            if (
                _normalizar_texto(
                    item[
                        "status_final"
                    ]
                ).upper()
                == "FALTA"
                or
                float(
                    item[
                        "diferenca_final"
                    ]
                    or
                    0
                )
                < 0
            )
        )

        total_sobras = sum(
            1
            for item in resultado_final
            if (
                _normalizar_texto(
                    item[
                        "status_final"
                    ]
                ).upper()
                == "SOBRA"
                or
                float(
                    item[
                        "diferenca_final"
                    ]
                    or
                    0
                )
                > 0
            )
        )

        inventarios.append(
            {
                "id_inventario":
                    id_inventario,

                "codigo_inventario":
                    inventario.CodigoInventario,

                "tipo":
                    inventario.Tipo,

                "cliente":
                    inventario.Cliente,

                "cliente_id":
                    inventario.ClienteId,

                "armazem":
                    inventario.cArmazem,

                "descricao":
                    inventario.Descricao,

                "status":
                    inventario.Status,

                "rodada_atual":
                    inventario.RodadaAtual,

                "data_hora_inicio":
                    inventario.DataHoraInicio,

                "data_hora_fim":
                    inventario.DataHoraFim,

                "criado_por":
                    inventario.CriadoPor,

                "finalizado_por":
                    inventario.FinalizadoPor,

                "consistencia": {
                    "resultado_final_esperado":
                        resultado_final_esperado,

                    "resultado_final_inventario_encontrado":
                        resultado_final_inventario_encontrado,

                    "resultado_final_localizacao_encontrado":
                        resultado_final_localizacao_encontrado,

                    "atribuicao_localizacao":
                        resultado_resolvido[
                            "tipo_atribuicao"
                        ],

                    "resultados_nao_atribuidos":
                        len(
                            resultado_resolvido[
                                "nao_atribuidos"
                            ]
                        ),

                    "status":
                        status_consistencia
                },

                "snapshot": {
                    "itens_previstos":
                        len(snapshot),

                    "quantidade_prevista":
                        sum(
                            item[
                                "saldo_inventario"
                            ]
                            for item in snapshot
                        ),

                    "itens":
                        snapshot
                },

                "rodadas":
                    rodadas,

                "resultado_final": {
                    "itens":
                        total_resultado,

                    "ok":
                        total_ok,

                    "faltas":
                        total_faltas,

                    "sobras":
                        total_sobras,

                    "atribuicao_localizacao":
                        resultado_resolvido[
                            "tipo_atribuicao"
                        ],

                    "detalhes":
                        resultado_final,

                    "nao_atribuidos":
                        resultado_resolvido[
                            "nao_atribuidos"
                        ]
                }
            }
        )

    total_inventarios = len(
        inventarios
    )

    taxa_divergencia = (
        round(
            (
                inventarios_com_divergencia
                /
                total_inventarios
            )
            *
            100,
            2
        )
        if total_inventarios > 0
        else 0
    )

    itens_recorrentes = []

    for item in recorrencia_itens.values():

        divergencias = (
            item["faltas"]
            +
            item["sobras"]
        )

        if divergencias < 2:
            continue

        itens_recorrentes.append(
            {
                **item,

                "divergencias":
                    divergencias,

                "recorrente":
                    True
            }
        )

    itens_recorrentes.sort(
        key=lambda item: (
            -item["divergencias"],
            item["codigo"],
            item["lote"]
        )
    )

    return {
        "tipo_consulta":
            "HISTORICO_LOCALIZACAO",

        "pesquisa": {
            "localizacao":
                localizacao,

            "cliente_id":
                cliente_id,

            "tipo":
                tipo,

            "data_inicio":
                data_inicio,

            "data_fim":
                data_fim
        },

        "paginacao": {
            "page": page,
            "page_size": page_size,
            "total_registros": total_registros,
            "total_paginas": total_paginas,
            "registros_pagina": total_inventarios,
            "possui_proxima_pagina": page < total_paginas,
            "possui_pagina_anterior": page > 1
        },

        "resumo": {
            "inventarios_encontrados":
                total_inventarios,

            "inventarios_encontrados_total":
                total_registros,

            "inventarios_com_resultado_final":
                inventarios_com_resultado_final,

            "inventarios_sem_resultado_final":
                inventarios_sem_resultado_final,

            "inventarios_ok":
                inventarios_ok,

            "inventarios_com_divergencia":
                inventarios_com_divergencia,

            "ocorrencias_falta":
                ocorrencias_falta,

            "ocorrencias_sobra":
                ocorrencias_sobra,

            "ocorrencias_ok":
                ocorrencias_ok,

            "taxa_divergencia_percentual":
                taxa_divergencia,

            "ultima_ocorrencia":
                ultima_ocorrencia,

            "possui_recorrencia":
                len(
                    itens_recorrentes
                ) > 0
        },

        "itens_recorrentes":
            itens_recorrentes,

        "inventarios":
            inventarios
    }
