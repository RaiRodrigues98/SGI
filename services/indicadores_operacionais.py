from datetime import datetime

from domain.exceptions import NotFoundError


# ============================================================
# INDICADORES OPERACIONAIS DO INVENTÁRIO
#
# Regras:
# - funciona para ROTATIVO e OFICIAL;
# - por padrão usa a RodadaAtual;
# - pode consultar rodada específica;
# - item = Localização + Código + Lote;
# - bipagem != item processado.
# ============================================================


# ============================================================
# NORMALIZAÇÃO
# ============================================================

def _normalizar_texto(valor):

    if valor is None:
        return ""

    return str(valor).strip()


# ============================================================
# PERCENTUAL
# ============================================================

def _calcular_percentual(
    realizado: float,
    planejado: float
):

    if not planejado:
        return 0.0

    return round(
        (
            realizado
            /
            planejado
        )
        * 100,
        2
    )


# ============================================================
# FORMATAR TEMPO
# ============================================================

def _formatar_segundos(
    segundos
):

    if segundos is None:
        return None

    segundos = max(
        int(segundos),
        0
    )

    horas = segundos // 3600

    minutos = (
        segundos % 3600
    ) // 60

    segundos_restantes = (
        segundos % 60
    )

    return (
        f"{horas:02d}:"
        f"{minutos:02d}:"
        f"{segundos_restantes:02d}"
    )


# ============================================================
# INVENTÁRIO + RODADA
# ============================================================

def _buscar_inventario_rodada(
    cursor,
    id_inventario: int,
    numero_rodada=None
):

    cursor.execute(
        """
        SELECT
            I.ID_Inventario,
            I.CodigoInventario,
            I.Tipo,
            I.ClienteId,
            I.Status,
            I.RodadaAtual,

            R.ID_Rodada,
            R.NumeroRodada,
            R.Status AS StatusRodada,
            R.DataHoraInicio,
            R.DataHoraFim

        FROM dbo.Inventarios I

        INNER JOIN dbo.RodadasInventario R
            ON R.ID_Inventario = I.ID_Inventario

        WHERE
            I.ID_Inventario = ?

            AND R.NumeroRodada = COALESCE(
                ?,
                I.RodadaAtual
            )
        """,
        (
            id_inventario,
            numero_rodada
        )
    )

    linha = cursor.fetchone()

    if not linha:

        raise NotFoundError(
            "Inventário ou rodada não encontrado."
        )

    return linha


# ============================================================
# LOCALIZAÇÕES PLANEJADAS
# ============================================================

def _buscar_localizacoes_planejadas(
    cursor,
    id_inventario: int,
    id_rodada: int
):

    cursor.execute(
        """
        SELECT COUNT(
            DISTINCT X.Localizacao
        )
        FROM
        (
            SELECT
                UPPER(
                    LTRIM(
                        RTRIM(RL.Localizacao)
                    )
                ) AS Localizacao

            FROM dbo.RodadaLocalizacoes RL

            INNER JOIN dbo.RodadasInventario R
                ON R.ID_Rodada = RL.ID_Rodada
                AND R.ID_Inventario = RL.ID_Inventario

            WHERE
                RL.ID_Inventario = ?
                AND RL.ID_Rodada = ?
                AND R.NumeroRodada > 1

            UNION

            SELECT
                UPPER(
                    LTRIM(
                        RTRIM(E.Localizacao)
                    )
                ) AS Localizacao

            FROM dbo.InventarioEscopoLocalizacoes E

            INNER JOIN dbo.RodadasInventario R
                ON R.ID_Rodada = ?
                AND R.ID_Inventario = E.ID_Inventario

            WHERE
                E.ID_Inventario = ?
                AND E.Selecionado = 1
                AND R.NumeroRodada = 1
        ) X
        """,
        (
            id_inventario,
            id_rodada,
            id_rodada,
            id_inventario
        )
    )

    return int(
        cursor.fetchone()[0]
        or
        0
    )

def _buscar_localizacoes_concluidas(
    cursor,
    id_inventario: int,
    id_rodada: int
):

    cursor.execute(
        """
        SELECT COUNT(
            DISTINCT X.Localizacao
        )
        FROM
        (
            SELECT
                UPPER(
                    LTRIM(
                        RTRIM(RL.Localizacao)
                    )
                ) AS Localizacao

            FROM dbo.RodadaLocalizacoes RL

            INNER JOIN dbo.RodadasInventario R
                ON R.ID_Rodada = RL.ID_Rodada
                AND R.ID_Inventario = RL.ID_Inventario

            WHERE
                RL.ID_Inventario = ?
                AND RL.ID_Rodada = ?
                AND R.NumeroRodada > 1
                AND RL.Status = 'CONCLUIDA'

            UNION

            SELECT
                UPPER(
                    LTRIM(
                        RTRIM(E.Localizacao)
                    )
                ) AS Localizacao

            FROM dbo.InventarioEscopoLocalizacoes E

            INNER JOIN dbo.RodadasInventario R
                ON R.ID_Rodada = ?
                AND R.ID_Inventario = E.ID_Inventario

            OUTER APPLY
            (
                SELECT TOP 1
                    S.Status
                FROM dbo.SessoesContagem S
                WHERE
                    S.ID_Inventario = E.ID_Inventario
                    AND S.ID_Rodada = R.ID_Rodada
                    AND S.ValidaParaConsolidacao = 1
                    AND UPPER(
                        LTRIM(
                            RTRIM(S.Localizacao)
                        )
                    )
                    =
                    UPPER(
                        LTRIM(
                            RTRIM(E.Localizacao)
                        )
                    )
                ORDER BY S.ID_Sessao DESC
            ) UltimaSessao

            WHERE
                E.ID_Inventario = ?
                AND E.Selecionado = 1
                AND R.NumeroRodada = 1
                AND UltimaSessao.Status IS NOT NULL
                AND UltimaSessao.Status <> 'ABERTA'
        ) X
        """,
        (
            id_inventario,
            id_rodada,
            id_rodada,
            id_inventario
        )
    )

    return int(
        cursor.fetchone()[0]
        or
        0
    )

def _buscar_itens_planejados(
    cursor,
    id_inventario: int,
    id_rodada: int,
    numero_rodada: int
):

    if int(numero_rodada) == 1:

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM
            (
                SELECT DISTINCT
                    UPPER(
                        LTRIM(
                            RTRIM(E.Localizacao)
                        )
                    ) AS Localizacao,

                    LTRIM(
                        RTRIM(E.Codigo)
                    ) AS Codigo,

                    ISNULL(
                        LTRIM(
                            RTRIM(E.Lote)
                        ),
                        ''
                    ) AS Lote

                FROM dbo.InventarioEstoqueSnapshot E

                INNER JOIN dbo.InventarioEscopoLocalizacoes EL
                    ON EL.ID_Inventario = E.ID_Inventario
                    AND EL.Selecionado = 1
                    AND UPPER(
                        LTRIM(
                            RTRIM(EL.Localizacao)
                        )
                    )
                    =
                    UPPER(
                        LTRIM(
                            RTRIM(E.Localizacao)
                        )
                    )

                WHERE
                    E.ID_Inventario = ?
                    AND NULLIF(
                        LTRIM(
                            RTRIM(E.Codigo)
                        ),
                        ''
                    ) IS NOT NULL
            ) X
            """,
            (
                id_inventario,
            )
        )

    else:

        cursor.execute(
            """
            SELECT COUNT(*)

            FROM
            (
                SELECT DISTINCT

                    UPPER(
                        LTRIM(
                            RTRIM(E.Localizacao)
                        )
                    ) AS Localizacao,

                    LTRIM(
                        RTRIM(E.Codigo)
                    ) AS Codigo,

                    ISNULL(
                        LTRIM(
                            RTRIM(E.Lote)
                        ),
                        ''
                    ) AS Lote

                FROM dbo.InventarioEstoqueSnapshot E

                INNER JOIN dbo.RodadaItens RI
                    ON RI.ID_Inventario = E.ID_Inventario
                    AND RI.ID_Rodada = ?

                    AND LTRIM(
                        RTRIM(RI.Codigo)
                    )
                    =
                    LTRIM(
                        RTRIM(E.Codigo)
                    )

                    AND ISNULL(
                        LTRIM(
                            RTRIM(RI.Lote)
                        ),
                        ''
                    )
                    =
                    ISNULL(
                        LTRIM(
                            RTRIM(E.Lote)
                        ),
                        ''
                    )

                INNER JOIN dbo.RodadaLocalizacoes RL
                    ON RL.ID_Inventario = E.ID_Inventario
                    AND RL.ID_Rodada = RI.ID_Rodada

                    AND UPPER(
                        LTRIM(
                            RTRIM(RL.Localizacao)
                        )
                    )
                    =
                    UPPER(
                        LTRIM(
                            RTRIM(E.Localizacao)
                        )
                    )

                WHERE
                    E.ID_Inventario = ?
            ) X
            """,
            (
                id_rodada,
                id_inventario
            )
        )

    return int(
        cursor.fetchone()[0]
        or
        0
    )


# ============================================================
# ITENS PROCESSADOS
#
# Regra operacional:
# - item = Localização + Código + Lote;
# - item é PROCESSADO quando:
#   1) possui ao menos uma contagem ATIVA na rodada; OU
#   2) pertence a uma localização concluída na rodada.
#
# Isso evita tratar como "pendente" um item ausente fisicamente
# cuja localização já foi concluída.
# ============================================================

def _buscar_itens_processados(
    cursor,
    id_inventario: int,
    id_rodada: int,
    numero_rodada: int
):

    if int(numero_rodada) == 1:

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM
            (
                SELECT DISTINCT
                    UPPER(
                        LTRIM(
                            RTRIM(E.Localizacao)
                        )
                    ) AS Localizacao,

                    LTRIM(
                        RTRIM(E.Codigo)
                    ) AS Codigo,

                    ISNULL(
                        LTRIM(
                            RTRIM(E.Lote)
                        ),
                        ''
                    ) AS Lote

                FROM dbo.InventarioEstoqueSnapshot E

                INNER JOIN dbo.InventarioEscopoLocalizacoes EL
                    ON EL.ID_Inventario = E.ID_Inventario
                    AND EL.Selecionado = 1
                    AND UPPER(
                        LTRIM(
                            RTRIM(EL.Localizacao)
                        )
                    )
                    =
                    UPPER(
                        LTRIM(
                            RTRIM(E.Localizacao)
                        )
                    )

                WHERE
                    E.ID_Inventario = ?
                    AND NULLIF(
                        LTRIM(
                            RTRIM(E.Codigo)
                        ),
                        ''
                    ) IS NOT NULL

                    AND
                    (
                        EXISTS
                        (
                            SELECT 1
                            FROM dbo.Contagens C

                            INNER JOIN dbo.SessoesContagem S
                                ON S.ID_Sessao = C.ID_Sessao

                            WHERE
                                S.ID_Inventario = E.ID_Inventario
                                AND S.ID_Rodada = ?
                                AND S.ValidaParaConsolidacao = 1
                                AND C.Status = 'ATIVA'
                                AND UPPER(
                                    LTRIM(
                                        RTRIM(S.Localizacao)
                                    )
                                )
                                =
                                UPPER(
                                    LTRIM(
                                        RTRIM(E.Localizacao)
                                    )
                                )
                                AND LTRIM(
                                    RTRIM(C.Codigo)
                                )
                                =
                                LTRIM(
                                    RTRIM(E.Codigo)
                                )
                                AND ISNULL(
                                    LTRIM(
                                        RTRIM(C.Lote)
                                    ),
                                    ''
                                )
                                =
                                ISNULL(
                                    LTRIM(
                                        RTRIM(E.Lote)
                                    ),
                                    ''
                                )
                        )

                        OR EXISTS
                        (
                            SELECT 1
                            FROM dbo.SessoesContagem S
                            WHERE
                                S.ID_Inventario = E.ID_Inventario
                                AND S.ID_Rodada = ?
                                AND S.ValidaParaConsolidacao = 1
                                AND S.Status <> 'ABERTA'
                                AND UPPER(
                                    LTRIM(
                                        RTRIM(S.Localizacao)
                                    )
                                )
                                =
                                UPPER(
                                    LTRIM(
                                        RTRIM(E.Localizacao)
                                    )
                                )
                        )
                    )
            ) X
            """,
            (
                id_inventario,
                id_rodada,
                id_rodada
            )
        )

    else:

        cursor.execute(
            """
            SELECT COUNT(*)

            FROM
            (
                SELECT DISTINCT
                    UPPER(LTRIM(RTRIM(E.Localizacao))) AS Localizacao,
                    LTRIM(RTRIM(E.Codigo)) AS Codigo,
                    ISNULL(LTRIM(RTRIM(E.Lote)), '') AS Lote

                FROM dbo.InventarioEstoqueSnapshot E

                INNER JOIN dbo.RodadaItens RI
                    ON RI.ID_Inventario = E.ID_Inventario
                    AND RI.ID_Rodada = ?
                    AND LTRIM(RTRIM(RI.Codigo))
                        = LTRIM(RTRIM(E.Codigo))
                    AND ISNULL(LTRIM(RTRIM(RI.Lote)), '')
                        = ISNULL(LTRIM(RTRIM(E.Lote)), '')

                INNER JOIN dbo.RodadaLocalizacoes RL
                    ON RL.ID_Inventario = E.ID_Inventario
                    AND RL.ID_Rodada = RI.ID_Rodada
                    AND UPPER(LTRIM(RTRIM(RL.Localizacao)))
                        = UPPER(LTRIM(RTRIM(E.Localizacao)))

                WHERE
                    E.ID_Inventario = ?
                    AND
                    (
                        RL.Status = 'CONCLUIDA'

                        OR EXISTS
                        (
                            SELECT 1
                            FROM dbo.Contagens C
                            INNER JOIN dbo.SessoesContagem S
                                ON S.ID_Sessao = C.ID_Sessao
                            WHERE
                                S.ID_Inventario = E.ID_Inventario
                                AND S.ID_Rodada = RL.ID_Rodada
                                AND S.ValidaParaConsolidacao = 1
                                AND C.Status = 'ATIVA'
                                AND UPPER(LTRIM(RTRIM(S.Localizacao)))
                                    = UPPER(LTRIM(RTRIM(E.Localizacao)))
                                AND LTRIM(RTRIM(C.Codigo))
                                    = LTRIM(RTRIM(E.Codigo))
                                AND ISNULL(LTRIM(RTRIM(C.Lote)), '')
                                    = ISNULL(LTRIM(RTRIM(E.Lote)), '')
                        )
                    )
            ) X
            """,
            (
                id_rodada,
                id_inventario
            )
        )

    return int(
        cursor.fetchone()[0]
        or
        0
    )


# ============================================================
# QUANTIDADE PLANEJADA
# ============================================================

def _buscar_quantidade_planejada(
    cursor,
    id_inventario: int,
    id_rodada: int,
    numero_rodada: int
):

    if int(numero_rodada) == 1:

        cursor.execute(
            """
            SELECT
                COALESCE(
                    SUM(
                        E.SaldoInventario
                    ),
                    0
                )

            FROM dbo.InventarioEstoqueSnapshot E

            INNER JOIN dbo.InventarioEscopoLocalizacoes EL
                ON EL.ID_Inventario = E.ID_Inventario
                AND EL.Selecionado = 1
                AND UPPER(
                    LTRIM(
                        RTRIM(EL.Localizacao)
                    )
                )
                =
                UPPER(
                    LTRIM(
                        RTRIM(E.Localizacao)
                    )
                )

            WHERE
                E.ID_Inventario = ?
            """,
            (
                id_inventario,
            )
        )

    else:

        cursor.execute(
            """
            SELECT
                COALESCE(
                    SUM(
                        E.SaldoInventario
                    ),
                    0
                )

            FROM dbo.InventarioEstoqueSnapshot E

            INNER JOIN dbo.RodadaItens RI
                ON RI.ID_Inventario = E.ID_Inventario
                AND RI.ID_Rodada = ?

                AND LTRIM(
                    RTRIM(RI.Codigo)
                )
                =
                LTRIM(
                    RTRIM(E.Codigo)
                )

                AND ISNULL(
                    LTRIM(
                        RTRIM(RI.Lote)
                    ),
                    ''
                )
                =
                ISNULL(
                    LTRIM(
                        RTRIM(E.Lote)
                    ),
                    ''
                )

            INNER JOIN dbo.RodadaLocalizacoes RL
                ON RL.ID_Inventario = E.ID_Inventario
                AND RL.ID_Rodada = RI.ID_Rodada

                AND UPPER(
                    LTRIM(
                        RTRIM(RL.Localizacao)
                    )
                )
                =
                UPPER(
                    LTRIM(
                        RTRIM(E.Localizacao)
                    )
                )

            WHERE
                E.ID_Inventario = ?
            """,
            (
                id_rodada,
                id_inventario
            )
        )

    return float(
        cursor.fetchone()[0]
        or
        0
    )


# ============================================================
# QUANTIDADE CONTADA
# ============================================================

def _buscar_quantidade_contada(
    cursor,
    id_inventario: int,
    id_rodada: int
):

    cursor.execute(
        """
        SELECT
            COALESCE(
                SUM(C.Quantidade),
                0
            )

        FROM dbo.Contagens C

        INNER JOIN dbo.SessoesContagem S
            ON S.ID_Sessao = C.ID_Sessao

        WHERE
            S.ID_Inventario = ?
            AND S.ValidaParaConsolidacao = 1
            AND S.ID_Rodada = ?
            AND C.Status = 'ATIVA'
        """,
        (
            id_inventario,
            id_rodada
        )
    )

    return float(
        cursor.fetchone()[0]
        or
        0
    )


# ============================================================
# TOTAL DE BIPAGENS
# ============================================================

def _buscar_total_bipagens(
    cursor,
    id_inventario: int,
    id_rodada: int
):

    cursor.execute(
        """
        SELECT COUNT(*)

        FROM dbo.Contagens C

        INNER JOIN dbo.SessoesContagem S
            ON S.ID_Sessao = C.ID_Sessao

        WHERE
            S.ID_Inventario = ?
            AND S.ValidaParaConsolidacao = 1
            AND S.ID_Rodada = ?
            AND C.Status = 'ATIVA'
        """,
        (
            id_inventario,
            id_rodada
        )
    )

    return int(
        cursor.fetchone()[0]
        or
        0
    )


# ============================================================
# OPERADORES
#
# No schema atual:
# operador = Contagens.CriadoPor
# ============================================================

def _buscar_operadores(
    cursor,
    id_inventario: int,
    id_rodada: int
):

    cursor.execute(
        """
        SELECT
            COUNT(
                DISTINCT C.CriadoPor
            )

        FROM dbo.Contagens C

        INNER JOIN dbo.SessoesContagem S
            ON S.ID_Sessao = C.ID_Sessao

        WHERE
            S.ID_Inventario = ?
            AND S.ValidaParaConsolidacao = 1
            AND S.ID_Rodada = ?
            AND C.Status = 'ATIVA'

            AND NULLIF(
                LTRIM(
                    RTRIM(C.CriadoPor)
                ),
                ''
            ) IS NOT NULL
        """,
        (
            id_inventario,
            id_rodada
        )
    )

    return int(
        cursor.fetchone()[0]
        or
        0
    )


# ============================================================
# ACOMPANHAMENTO OPERACIONAL
# ============================================================

def obter_acompanhamento_inventario(
    cursor,
    id_inventario: int,
    numero_rodada=None
):

    # ========================================================
    # 1. CONTEXTO
    # ========================================================

    contexto = (
        _buscar_inventario_rodada(
            cursor=cursor,
            id_inventario=id_inventario,
            numero_rodada=numero_rodada
        )
    )

    id_rodada = int(
        contexto.ID_Rodada
    )

    rodada = int(
        contexto.NumeroRodada
    )

    # ========================================================
    # 2. LOCALIZAÇÕES
    # ========================================================

    localizacoes_planejadas = (
        _buscar_localizacoes_planejadas(
            cursor=cursor,
            id_inventario=id_inventario,
            id_rodada=id_rodada
        )
    )

    localizacoes_concluidas = (
        _buscar_localizacoes_concluidas(
            cursor=cursor,
            id_inventario=id_inventario,
            id_rodada=id_rodada
        )
    )

    localizacoes_pendentes = max(
        localizacoes_planejadas
        -
        localizacoes_concluidas,
        0
    )

    percentual_localizacoes = (
        _calcular_percentual(
            realizado=localizacoes_concluidas,
            planejado=localizacoes_planejadas
        )
    )

    # ========================================================
    # 3. ITENS
    # ========================================================

    itens_planejados = (
        _buscar_itens_planejados(
            cursor=cursor,
            id_inventario=id_inventario,
            id_rodada=id_rodada,
            numero_rodada=rodada
        )
    )

    itens_processados = (
        _buscar_itens_processados(
            cursor=cursor,
            id_inventario=id_inventario,
            id_rodada=id_rodada,
            numero_rodada=rodada
        )
    )

    itens_pendentes = max(
        itens_planejados
        -
        itens_processados,
        0
    )

    percentual_itens = (
        _calcular_percentual(
            realizado=itens_processados,
            planejado=itens_planejados
        )
    )

    # ========================================================
    # 4. VOLUME
    # ========================================================

    quantidade_planejada = (
        _buscar_quantidade_planejada(
            cursor=cursor,
            id_inventario=id_inventario,
            id_rodada=id_rodada,
            numero_rodada=rodada
        )
    )

    quantidade_contada = (
        _buscar_quantidade_contada(
            cursor=cursor,
            id_inventario=id_inventario,
            id_rodada=id_rodada
        )
    )

    # ========================================================
    # 5. ATIVIDADE
    # ========================================================

    total_bipagens = (
        _buscar_total_bipagens(
            cursor=cursor,
            id_inventario=id_inventario,
            id_rodada=id_rodada
        )
    )

    operadores = (
        _buscar_operadores(
            cursor=cursor,
            id_inventario=id_inventario,
            id_rodada=id_rodada
        )
    )

    # ========================================================
    # 6. TEMPO
    # ========================================================

    inicio = (
        contexto.DataHoraInicio
    )

    fim = (
        contexto.DataHoraFim
    )

    agora = datetime.now()

    referencia_fim = (
        fim
        or
        agora
    )

    tempo_segundos = None

    if inicio:

        tempo_segundos = (
            referencia_fim
            -
            inicio
        ).total_seconds()

    # ========================================================
    # 7. RETORNO
    # ========================================================

    return {
        "tipo_indicador":
            "ACOMPANHAMENTO_OPERACIONAL",

        "id_inventario":
            contexto.ID_Inventario,

        "codigo_inventario":
            contexto.CodigoInventario,

        "tipo_inventario":
            contexto.Tipo,

        "cliente_id":
            contexto.ClienteId,

        "status_inventario":
            contexto.Status,

        "id_rodada":
            id_rodada,

        "numero_rodada":
            rodada,

        "status_rodada":
            contexto.StatusRodada,

        "progresso": {

            "itens": {
                "planejados":
                    itens_planejados,

                "processados":
                    itens_processados,

                "pendentes":
                    itens_pendentes,

                "percentual":
                    percentual_itens
            },

            "localizacoes": {
                "planejadas":
                    localizacoes_planejadas,

                "concluidas":
                    localizacoes_concluidas,

                "pendentes":
                    localizacoes_pendentes,

                "percentual":
                    percentual_localizacoes
            }
        },

        "volume": {
            "quantidade_planejada":
                quantidade_planejada,

            "quantidade_registrada":
                quantidade_contada
        },

        "atividade": {
            "total_bipagens":
                total_bipagens,

            "operadores_com_contagem":
                operadores
        },

        "tempo": {
            "data_hora_inicio":
                inicio,

            "data_hora_fim":
                fim,

            "segundos":
                (
                    int(
                        tempo_segundos
                    )
                    if tempo_segundos is not None
                    else None
                ),

            "tempo_formatado":
                _formatar_segundos(
                    tempo_segundos
                )
        }
    }


# ============================================================
# ACOMPANHAMENTO OPERACIONAL POR LOCALIZAÇÃO
#
# Regras:
# - funciona para ROTATIVO e OFICIAL;
# - usa a mesma definição de item do acompanhamento geral:
#   Localização + Código + Lote;
# - item é processado quando possui contagem ATIVA OU quando
#   a localização foi concluída;
# - localização vazia concluída permanece operacionalmente
#   concluída, mesmo sem bipagem;
# - operador = Contagens.CriadoPor no schema atual.
# ============================================================

def obter_acompanhamento_localizacoes(
    cursor,
    id_inventario: int,
    numero_rodada=None
):

    contexto = _buscar_inventario_rodada(
        cursor=cursor,
        id_inventario=id_inventario,
        numero_rodada=numero_rodada
    )

    id_rodada = int(contexto.ID_Rodada)
    rodada = int(contexto.NumeroRodada)

    # --------------------------------------------------------
    # Localizações previstas na rodada
    # --------------------------------------------------------

    if rodada == 1:

        cursor.execute(
            """
            SELECT
                UPPER(
                    LTRIM(
                        RTRIM(E.Localizacao)
                    )
                ) AS Localizacao,

                CASE
                    WHEN UltimaSessao.Status IS NOT NULL
                         AND UltimaSessao.Status <> 'ABERTA'
                        THEN 'CONCLUIDA'
                    ELSE 'PENDENTE'
                END AS Status

            FROM dbo.InventarioEscopoLocalizacoes E

            OUTER APPLY
            (
                SELECT TOP 1
                    S.Status
                FROM dbo.SessoesContagem S
                WHERE
                    S.ID_Inventario = E.ID_Inventario
                    AND S.ID_Rodada = ?
                    AND S.ValidaParaConsolidacao = 1
                    AND UPPER(
                        LTRIM(
                            RTRIM(S.Localizacao)
                        )
                    )
                    =
                    UPPER(
                        LTRIM(
                            RTRIM(E.Localizacao)
                        )
                    )
                ORDER BY S.ID_Sessao DESC
            ) UltimaSessao

            WHERE
                E.ID_Inventario = ?
                AND E.Selecionado = 1
                AND NULLIF(
                    LTRIM(
                        RTRIM(E.Localizacao)
                    ),
                    ''
                ) IS NOT NULL

            ORDER BY
                UPPER(
                    LTRIM(
                        RTRIM(E.Localizacao)
                    )
                )
            """,
            (
                id_rodada,
                id_inventario
            )
        )

    else:

        cursor.execute(
            """
            SELECT
                UPPER(
                    LTRIM(
                        RTRIM(RL.Localizacao)
                    )
                ) AS Localizacao,
                RL.Status

            FROM dbo.RodadaLocalizacoes RL

            WHERE
                RL.ID_Inventario = ?
                AND RL.ID_Rodada = ?
                AND NULLIF(
                    LTRIM(
                        RTRIM(RL.Localizacao)
                    ),
                    ''
                ) IS NOT NULL

            ORDER BY
                UPPER(
                    LTRIM(
                        RTRIM(RL.Localizacao)
                    )
                )
            """,
            (
                id_inventario,
                id_rodada
            )
        )

    linhas_localizacoes = cursor.fetchall()

    # --------------------------------------------------------
    # Itens planejados por localização
    # --------------------------------------------------------

    if rodada == 1:

        cursor.execute(
            """
            SELECT
                UPPER(
                    LTRIM(
                        RTRIM(E.Localizacao)
                    )
                ) AS Localizacao,
                COUNT(*) AS ItensPlanejados

            FROM
            (
                SELECT DISTINCT
                    ID_Inventario,
                    Localizacao,
                    LTRIM(
                        RTRIM(Codigo)
                    ) AS Codigo,
                    ISNULL(
                        LTRIM(
                            RTRIM(Lote)
                        ),
                        ''
                    ) AS Lote

                FROM dbo.InventarioEstoqueSnapshot

                WHERE
                    ID_Inventario = ?
                    AND NULLIF(
                        LTRIM(
                            RTRIM(Codigo)
                        ),
                        ''
                    ) IS NOT NULL
            ) E

            INNER JOIN dbo.InventarioEscopoLocalizacoes EL
                ON EL.ID_Inventario = E.ID_Inventario
                AND EL.Selecionado = 1
                AND UPPER(
                    LTRIM(
                        RTRIM(EL.Localizacao)
                    )
                )
                =
                UPPER(
                    LTRIM(
                        RTRIM(E.Localizacao)
                    )
                )

            GROUP BY
                UPPER(
                    LTRIM(
                        RTRIM(E.Localizacao)
                    )
                )
            """,
            (
                id_inventario,
            )
        )

    else:

        cursor.execute(
            """
            SELECT
                UPPER(LTRIM(RTRIM(E.Localizacao))) AS Localizacao,
                COUNT(*) AS ItensPlanejados
            FROM
            (
                SELECT DISTINCT
                    E.ID_Inventario,
                    E.Localizacao,
                    LTRIM(RTRIM(E.Codigo)) AS Codigo,
                    ISNULL(LTRIM(RTRIM(E.Lote)), '') AS Lote
                FROM dbo.InventarioEstoqueSnapshot E
                INNER JOIN dbo.RodadaItens RI
                    ON RI.ID_Inventario = E.ID_Inventario
                    AND RI.ID_Rodada = ?
                    AND LTRIM(RTRIM(RI.Codigo))
                        = LTRIM(RTRIM(E.Codigo))
                    AND ISNULL(LTRIM(RTRIM(RI.Lote)), '')
                        = ISNULL(LTRIM(RTRIM(E.Lote)), '')
                WHERE
                    E.ID_Inventario = ?
            ) E
            INNER JOIN dbo.RodadaLocalizacoes RL
                ON RL.ID_Inventario = E.ID_Inventario
                AND RL.ID_Rodada = ?
                AND UPPER(LTRIM(RTRIM(RL.Localizacao)))
                    = UPPER(LTRIM(RTRIM(E.Localizacao)))
            GROUP BY
                UPPER(LTRIM(RTRIM(E.Localizacao)))
            """,
            (
                id_rodada,
                id_inventario,
                id_rodada
            )
        )

    planejados = {
        _normalizar_texto(linha.Localizacao).upper():
            int(linha.ItensPlanejados or 0)
        for linha in cursor.fetchall()
    }

    # --------------------------------------------------------
    # Atividade física por localização
    # --------------------------------------------------------

    cursor.execute(
        """
        SELECT
            UPPER(LTRIM(RTRIM(S.Localizacao))) AS Localizacao,
            COUNT(C.ID_Contagem) AS TotalBipagens,
            COALESCE(SUM(C.Quantidade), 0) AS QuantidadeRegistrada,
            MIN(S.DataHoraInicio) AS HoraInicio,
            MAX(
                CASE
                    WHEN C.DataHora IS NOT NULL THEN C.DataHora
                    ELSE S.DataHoraFim
                END
            ) AS UltimaAtividade
        FROM dbo.SessoesContagem S
        LEFT JOIN dbo.Contagens C
            ON C.ID_Sessao = S.ID_Sessao
            AND C.Status = 'ATIVA'
        WHERE
            S.ID_Inventario = ?
            AND S.ID_Rodada = ?
            AND S.ValidaParaConsolidacao = 1
            AND NULLIF(LTRIM(RTRIM(S.Localizacao)), '') IS NOT NULL
        GROUP BY
            UPPER(LTRIM(RTRIM(S.Localizacao)))
        """,
        (
            id_inventario,
            id_rodada
        )
    )

    atividade = {}

    for linha in cursor.fetchall():
        localizacao = _normalizar_texto(
            linha.Localizacao
        ).upper()

        atividade[localizacao] = {
            "total_bipagens": int(
                linha.TotalBipagens or 0
            ),
            "quantidade_registrada": float(
                linha.QuantidadeRegistrada or 0
            ),
            "hora_inicio": linha.HoraInicio,
            "ultima_atividade": linha.UltimaAtividade
        }

    # --------------------------------------------------------
    # Operadores por localização
    # --------------------------------------------------------

    cursor.execute(
        """
        SELECT DISTINCT
            UPPER(LTRIM(RTRIM(S.Localizacao))) AS Localizacao,
            LTRIM(RTRIM(C.CriadoPor)) AS Operador
        FROM dbo.Contagens C
        INNER JOIN dbo.SessoesContagem S
            ON S.ID_Sessao = C.ID_Sessao
        WHERE
            S.ID_Inventario = ?
            AND S.ValidaParaConsolidacao = 1
            AND S.ID_Rodada = ?
            AND C.Status = 'ATIVA'
            AND NULLIF(LTRIM(RTRIM(S.Localizacao)), '') IS NOT NULL
            AND NULLIF(LTRIM(RTRIM(C.CriadoPor)), '') IS NOT NULL
        ORDER BY
            UPPER(LTRIM(RTRIM(S.Localizacao))),
            LTRIM(RTRIM(C.CriadoPor))
        """,
        (
            id_inventario,
            id_rodada
        )
    )

    operadores = {}

    for linha in cursor.fetchall():
        localizacao = _normalizar_texto(
            linha.Localizacao
        ).upper()

        operadores.setdefault(
            localizacao,
            []
        ).append(
            _normalizar_texto(
                linha.Operador
            )
        )

    agora = datetime.now()
    localizacoes = []

    for linha in linhas_localizacoes:

        localizacao = _normalizar_texto(
            linha.Localizacao
        ).upper()

        status_banco = _normalizar_texto(
            linha.Status
        ).upper()

        itens_planejados = planejados.get(
            localizacao,
            0
        )

        dados_atividade = atividade.get(
            localizacao,
            {}
        )

        total_bipagens = int(
            dados_atividade.get(
                "total_bipagens",
                0
            )
        )

        quantidade_registrada = float(
            dados_atividade.get(
                "quantidade_registrada",
                0
            )
        )

        hora_inicio = dados_atividade.get(
            "hora_inicio"
        )

        ultima_atividade = dados_atividade.get(
            "ultima_atividade"
        )

        # A mesma regra homologada no acompanhamento geral:
        # localização concluída => todos os itens previstos nela
        # foram operacionalmente processados, inclusive faltas.
        if status_banco == "CONCLUIDA":
            itens_processados = itens_planejados
        else:
            # Enquanto não concluída, contamos somente itens
            # previstos que efetivamente possuem contagem ativa.
            if rodada == 1:
                cursor.execute(
                    """
                    SELECT COUNT(*)
                    FROM
                    (
                        SELECT DISTINCT
                            LTRIM(RTRIM(E.Codigo)) AS Codigo,
                            ISNULL(LTRIM(RTRIM(E.Lote)), '') AS Lote
                        FROM dbo.InventarioEstoqueSnapshot E
                        WHERE
                            E.ID_Inventario = ?
                            AND UPPER(LTRIM(RTRIM(E.Localizacao))) = ?
                            AND NULLIF(LTRIM(RTRIM(E.Codigo)), '') IS NOT NULL
                            AND EXISTS
                            (
                                SELECT 1
                                FROM dbo.Contagens C
                                INNER JOIN dbo.SessoesContagem S
                                    ON S.ID_Sessao = C.ID_Sessao
                                WHERE
                                    S.ID_Inventario = E.ID_Inventario
                                    AND S.ID_Rodada = ?
                                    AND S.ValidaParaConsolidacao = 1
                                    AND C.Status = 'ATIVA'
                                    AND UPPER(LTRIM(RTRIM(S.Localizacao))) = ?
                                    AND LTRIM(RTRIM(C.Codigo))
                                        = LTRIM(RTRIM(E.Codigo))
                                    AND ISNULL(LTRIM(RTRIM(C.Lote)), '')
                                        = ISNULL(LTRIM(RTRIM(E.Lote)), '')
                            )
                    ) X
                    """,
                    (
                        id_inventario,
                        localizacao,
                        id_rodada,
                        localizacao
                    )
                )
            else:
                cursor.execute(
                    """
                    SELECT COUNT(*)
                    FROM
                    (
                        SELECT DISTINCT
                            LTRIM(RTRIM(E.Codigo)) AS Codigo,
                            ISNULL(LTRIM(RTRIM(E.Lote)), '') AS Lote
                        FROM dbo.InventarioEstoqueSnapshot E
                        INNER JOIN dbo.RodadaItens RI
                            ON RI.ID_Inventario = E.ID_Inventario
                            AND RI.ID_Rodada = ?
                            AND LTRIM(RTRIM(RI.Codigo))
                                = LTRIM(RTRIM(E.Codigo))
                            AND ISNULL(LTRIM(RTRIM(RI.Lote)), '')
                                = ISNULL(LTRIM(RTRIM(E.Lote)), '')
                        WHERE
                            E.ID_Inventario = ?
                            AND UPPER(LTRIM(RTRIM(E.Localizacao))) = ?
                            AND EXISTS
                            (
                                SELECT 1
                                FROM dbo.Contagens C
                                INNER JOIN dbo.SessoesContagem S
                                    ON S.ID_Sessao = C.ID_Sessao
                                WHERE
                                    S.ID_Inventario = E.ID_Inventario
                                    AND S.ID_Rodada = ?
                                    AND S.ValidaParaConsolidacao = 1
                                    AND C.Status = 'ATIVA'
                                    AND UPPER(LTRIM(RTRIM(S.Localizacao))) = ?
                                    AND LTRIM(RTRIM(C.Codigo))
                                        = LTRIM(RTRIM(E.Codigo))
                                    AND ISNULL(LTRIM(RTRIM(C.Lote)), '')
                                        = ISNULL(LTRIM(RTRIM(E.Lote)), '')
                            )
                    ) X
                    """,
                    (
                        id_rodada,
                        id_inventario,
                        localizacao,
                        id_rodada,
                        localizacao
                    )
                )

            itens_processados = int(
                cursor.fetchone()[0]
                or 0
            )

        itens_pendentes = max(
            itens_planejados
            -
            itens_processados,
            0
        )

        percentual = _calcular_percentual(
            realizado=itens_processados,
            planejado=itens_planejados
        )

        if status_banco == "CONCLUIDA":
            status_operacional = "CONCLUIDA"
        elif hora_inicio or total_bipagens > 0:
            status_operacional = "EM_ANDAMENTO"
        else:
            status_operacional = "PENDENTE"

        tempo_sem_atividade = None

        if (
            status_operacional != "CONCLUIDA"
            and ultima_atividade is not None
        ):
            tempo_sem_atividade = max(
                int(
                    (
                        agora
                        -
                        ultima_atividade
                    ).total_seconds()
                ),
                0
            )

        localizacoes.append(
            {
                "localizacao":
                    localizacao,

                "status":
                    status_operacional,

                "status_registro":
                    status_banco,

                "itens_planejados":
                    itens_planejados,

                "itens_processados":
                    itens_processados,

                "itens_pendentes":
                    itens_pendentes,

                "percentual":
                    percentual,

                "total_bipagens":
                    total_bipagens,

                "quantidade_registrada":
                    quantidade_registrada,

                "operadores":
                    operadores.get(
                        localizacao,
                        []
                    ),

                "hora_inicio":
                    hora_inicio,

                "ultima_atividade":
                    ultima_atividade,

                "tempo_sem_atividade_segundos":
                    tempo_sem_atividade,

                "tempo_sem_atividade_formatado":
                    _formatar_segundos(
                        tempo_sem_atividade
                    )
            }
        )

    total = len(localizacoes)

    concluidas = sum(
        1
        for item in localizacoes
        if item["status"] == "CONCLUIDA"
    )

    em_andamento = sum(
        1
        for item in localizacoes
        if item["status"] == "EM_ANDAMENTO"
    )

    pendentes = sum(
        1
        for item in localizacoes
        if item["status"] == "PENDENTE"
    )

    return {
        "tipo_indicador":
            "ACOMPANHAMENTO_LOCALIZACOES",

        "id_inventario":
            contexto.ID_Inventario,

        "codigo_inventario":
            contexto.CodigoInventario,

        "tipo_inventario":
            contexto.Tipo,

        "cliente_id":
            contexto.ClienteId,

        "status_inventario":
            contexto.Status,

        "id_rodada":
            id_rodada,

        "numero_rodada":
            rodada,

        "status_rodada":
            contexto.StatusRodada,

        "resumo": {
            "localizacoes_planejadas":
                total,

            "localizacoes_concluidas":
                concluidas,

            "localizacoes_em_andamento":
                em_andamento,

            "localizacoes_pendentes":
                pendentes,

            "percentual":
                _calcular_percentual(
                    realizado=concluidas,
                    planejado=total
                )
        },

        "localizacoes":
            localizacoes
    }


# ============================================================
# TEMPO E PRODUTIVIDADE OPERACIONAL
#
# Regras:
# - funciona para ROTATIVO e OFICIAL;
# - por padrão utiliza a RodadaAtual;
# - permite consultar rodada específica;
# - produtividade da rodada usa tempo decorrido da rodada;
# - tempo efetivo de atividade usa primeira e última contagem
#   ATIVA registrada na rodada;
# - tempo médio por localização considera o intervalo entre
#   início e fim de cada localização/sessão;
# - operador = Contagens.CriadoPor;
# - registros sem CriadoPor entram em "SEM_USUARIO" para não
#   desaparecerem dos totais operacionais.
# ============================================================


# ============================================================
# TAXA POR HORA
# ============================================================

def _calcular_taxa_hora(
    quantidade: float,
    segundos
):

    if segundos is None:
        return 0.0

    segundos = float(
        segundos
        or
        0
    )

    if segundos <= 0:
        return 0.0

    return round(
        float(quantidade or 0)
        /
        (
            segundos
            /
            3600
        ),
        2
    )


# ============================================================
# ESTATÍSTICAS DE TEMPO DAS LOCALIZAÇÕES
# ============================================================

def _buscar_tempos_localizacoes_produtividade(
    cursor,
    id_inventario: int,
    id_rodada: int
):

    cursor.execute(
        """
        SELECT
            UPPER(
                LTRIM(
                    RTRIM(S.Localizacao)
                )
            ) AS Localizacao,

            MIN(
                S.DataHoraInicio
            ) AS DataHoraInicio,

            MAX(
                COALESCE(
                    S.DataHoraFim,
                    SYSDATETIME()
                )
            ) AS DataHoraFim

        FROM dbo.SessoesContagem S

        WHERE
            S.ID_Inventario = ?
            AND S.ValidaParaConsolidacao = 1
            AND S.ID_Rodada = ?

            AND NULLIF(
                LTRIM(
                    RTRIM(S.Localizacao)
                ),
                ''
            ) IS NOT NULL

        GROUP BY
            UPPER(
                LTRIM(
                    RTRIM(S.Localizacao)
                )
            )

        ORDER BY
            UPPER(
                LTRIM(
                    RTRIM(S.Localizacao)
                )
            )
        """,
        (
            id_inventario,
            id_rodada
        )
    )

    localizacoes = []

    for linha in cursor.fetchall():

        inicio = linha.DataHoraInicio
        fim = linha.DataHoraFim

        segundos = None

        if (
            inicio is not None
            and
            fim is not None
        ):

            segundos = max(
                int(
                    (
                        fim
                        -
                        inicio
                    ).total_seconds()
                ),
                0
            )

        localizacoes.append(
            {
                "localizacao":
                    _normalizar_texto(
                        linha.Localizacao
                    ).upper(),

                "data_hora_inicio":
                    inicio,

                "data_hora_fim":
                    fim,

                "tempo_segundos":
                    segundos,

                "tempo_formatado":
                    _formatar_segundos(
                        segundos
                    )
            }
        )

    return localizacoes


# ============================================================
# JANELA DE ATIVIDADE FÍSICA DA RODADA
# ============================================================

def _buscar_janela_atividade_produtividade(
    cursor,
    id_inventario: int,
    id_rodada: int
):

    cursor.execute(
        """
        SELECT
            MIN(C.DataHora) AS PrimeiraAtividade,
            MAX(C.DataHora) AS UltimaAtividade

        FROM dbo.Contagens C

        INNER JOIN dbo.SessoesContagem S
            ON S.ID_Sessao = C.ID_Sessao

        WHERE
            S.ID_Inventario = ?
            AND S.ValidaParaConsolidacao = 1
            AND S.ID_Rodada = ?
            AND C.Status = 'ATIVA'
        """,
        (
            id_inventario,
            id_rodada
        )
    )

    linha = cursor.fetchone()

    primeira = (
        linha.PrimeiraAtividade
        if linha
        else None
    )

    ultima = (
        linha.UltimaAtividade
        if linha
        else None
    )

    segundos = None

    if (
        primeira is not None
        and
        ultima is not None
    ):

        segundos = max(
            int(
                (
                    ultima
                    -
                    primeira
                ).total_seconds()
            ),
            0
        )

    return {
        "primeira_atividade":
            primeira,

        "ultima_atividade":
            ultima,

        "tempo_segundos":
            segundos,

        "tempo_formatado":
            _formatar_segundos(
                segundos
            )
    }


# ============================================================
# PRODUTIVIDADE POR OPERADOR
# ============================================================

def _buscar_produtividade_operadores(
    cursor,
    id_inventario: int,
    id_rodada: int
):

    cursor.execute(
        """
        SELECT
            COALESCE(
                NULLIF(
                    LTRIM(
                        RTRIM(C.CriadoPor)
                    ),
                    ''
                ),
                'SEM_USUARIO'
            ) AS Operador,

            COUNT(
                C.ID_Contagem
            ) AS TotalBipagens,

            COALESCE(
                SUM(C.Quantidade),
                0
            ) AS QuantidadeRegistrada,

            COUNT(
                DISTINCT
                UPPER(
                    LTRIM(
                        RTRIM(S.Localizacao)
                    )
                )
                +
                '|'
                +
                LTRIM(
                    RTRIM(C.Codigo)
                )
                +
                '|'
                +
                ISNULL(
                    LTRIM(
                        RTRIM(C.Lote)
                    ),
                    ''
                )
            ) AS ItensDistintos,

            COUNT(
                DISTINCT
                UPPER(
                    LTRIM(
                        RTRIM(S.Localizacao)
                    )
                )
            ) AS LocalizacoesComAtividade,

            MIN(
                C.DataHora
            ) AS PrimeiraAtividade,

            MAX(
                C.DataHora
            ) AS UltimaAtividade

        FROM dbo.Contagens C

        INNER JOIN dbo.SessoesContagem S
            ON S.ID_Sessao = C.ID_Sessao

        WHERE
            S.ID_Inventario = ?
            AND S.ID_Rodada = ?
            AND S.ValidaParaConsolidacao = 1
            AND C.Status = 'ATIVA'

        GROUP BY
            COALESCE(
                NULLIF(
                    LTRIM(
                        RTRIM(C.CriadoPor)
                    ),
                    ''
                ),
                'SEM_USUARIO'
            )

        ORDER BY
            COUNT(C.ID_Contagem) DESC,
            COALESCE(
                NULLIF(
                    LTRIM(
                        RTRIM(C.CriadoPor)
                    ),
                    ''
                ),
                'SEM_USUARIO'
            )
        """,
        (
            id_inventario,
            id_rodada
        )
    )

    operadores = []

    for linha in cursor.fetchall():

        primeira = linha.PrimeiraAtividade
        ultima = linha.UltimaAtividade

        tempo_ativo_segundos = None

        if (
            primeira is not None
            and
            ultima is not None
        ):

            tempo_ativo_segundos = max(
                int(
                    (
                        ultima
                        -
                        primeira
                    ).total_seconds()
                ),
                0
            )

        operadores.append(
            {
                "operador":
                    _normalizar_texto(
                        linha.Operador
                    )
                    or
                    "SEM_USUARIO",

                "total_bipagens":
                    int(
                        linha.TotalBipagens
                        or
                        0
                    ),

                "quantidade_registrada":
                    float(
                        linha.QuantidadeRegistrada
                        or
                        0
                    ),

                "itens_distintos_com_bipagem":
                    int(
                        linha.ItensDistintos
                        or
                        0
                    ),

                "localizacoes_com_atividade":
                    int(
                        linha.LocalizacoesComAtividade
                        or
                        0
                    ),

                "primeira_atividade":
                    primeira,

                "ultima_atividade":
                    ultima,

                "tempo_ativo_segundos":
                    tempo_ativo_segundos,

                "tempo_ativo_formatado":
                    _formatar_segundos(
                        tempo_ativo_segundos
                    ),

                "bipagens_hora":
                    _calcular_taxa_hora(
                        quantidade=(
                            linha.TotalBipagens
                            or
                            0
                        ),
                        segundos=tempo_ativo_segundos
                    ),

                "quantidade_hora":
                    _calcular_taxa_hora(
                        quantidade=(
                            linha.QuantidadeRegistrada
                            or
                            0
                        ),
                        segundos=tempo_ativo_segundos
                    )
            }
        )

    return operadores


# ============================================================
# PRODUTIVIDADE DO INVENTÁRIO / RODADA
# ============================================================

def obter_produtividade_inventario(
    cursor,
    id_inventario: int,
    numero_rodada=None
):

    # ========================================================
    # 1. CONTEXTO
    # ========================================================

    contexto = (
        _buscar_inventario_rodada(
            cursor=cursor,
            id_inventario=id_inventario,
            numero_rodada=numero_rodada
        )
    )

    id_rodada = int(
        contexto.ID_Rodada
    )

    rodada = int(
        contexto.NumeroRodada
    )

    # ========================================================
    # 2. PRODUÇÃO DA RODADA
    # ========================================================

    total_bipagens = (
        _buscar_total_bipagens(
            cursor=cursor,
            id_inventario=id_inventario,
            id_rodada=id_rodada
        )
    )

    quantidade_registrada = (
        _buscar_quantidade_contada(
            cursor=cursor,
            id_inventario=id_inventario,
            id_rodada=id_rodada
        )
    )

    itens_processados = (
        _buscar_itens_processados(
            cursor=cursor,
            id_inventario=id_inventario,
            id_rodada=id_rodada,
            numero_rodada=rodada
        )
    )

    localizacoes_concluidas = (
        _buscar_localizacoes_concluidas(
            cursor=cursor,
            id_inventario=id_inventario,
            id_rodada=id_rodada
        )
    )

    # ========================================================
    # 3. TEMPO DECORRIDO DA RODADA
    # ========================================================

    inicio_rodada = (
        contexto.DataHoraInicio
    )

    fim_rodada = (
        contexto.DataHoraFim
    )

    referencia_fim = (
        fim_rodada
        or
        datetime.now()
    )

    tempo_decorrido_segundos = None

    if inicio_rodada is not None:

        tempo_decorrido_segundos = max(
            int(
                (
                    referencia_fim
                    -
                    inicio_rodada
                ).total_seconds()
            ),
            0
        )

    # ========================================================
    # 4. JANELA EFETIVA DE ATIVIDADE
    # ========================================================

    janela_atividade = (
        _buscar_janela_atividade_produtividade(
            cursor=cursor,
            id_inventario=id_inventario,
            id_rodada=id_rodada
        )
    )

    # ========================================================
    # 5. TEMPOS POR LOCALIZAÇÃO
    # ========================================================

    tempos_localizacoes = (
        _buscar_tempos_localizacoes_produtividade(
            cursor=cursor,
            id_inventario=id_inventario,
            id_rodada=id_rodada
        )
    )

    tempos_validos = [
        item["tempo_segundos"]
        for item in tempos_localizacoes
        if item["tempo_segundos"] is not None
    ]

    tempo_operacional_segundos = sum(
        tempos_validos
    ) if tempos_validos else 0

    tempo_medio_localizacao_segundos = None

    if tempos_validos:

        tempo_medio_localizacao_segundos = round(
            sum(
                tempos_validos
            )
            /
            len(
                tempos_validos
            ),
            2
        )

    localizacao_mais_rapida = None
    localizacao_mais_lenta = None

    if tempos_validos:

        localizacao_mais_rapida = min(
            (
                item
                for item in tempos_localizacoes
                if item["tempo_segundos"] is not None
            ),
            key=lambda item:
                item["tempo_segundos"]
        )

        localizacao_mais_lenta = max(
            (
                item
                for item in tempos_localizacoes
                if item["tempo_segundos"] is not None
            ),
            key=lambda item:
                item["tempo_segundos"]
        )

    # ========================================================
    # 6. PRODUTIVIDADE POR OPERADOR
    # ========================================================

    operadores = (
        _buscar_produtividade_operadores(
            cursor=cursor,
            id_inventario=id_inventario,
            id_rodada=id_rodada
        )
    )

    operadores_identificados = sum(
        1
        for item in operadores
        if item["operador"] != "SEM_USUARIO"
    )

    bipagens_sem_usuario = sum(
        item["total_bipagens"]
        for item in operadores
        if item["operador"] == "SEM_USUARIO"
    )

    # ========================================================
    # 7. RETORNO
    # ========================================================

    return {
        "tipo_indicador":
            "PRODUTIVIDADE_OPERACIONAL",

        "id_inventario":
            contexto.ID_Inventario,

        "codigo_inventario":
            contexto.CodigoInventario,

        "tipo_inventario":
            contexto.Tipo,

        "cliente_id":
            contexto.ClienteId,

        "status_inventario":
            contexto.Status,

        "id_rodada":
            id_rodada,

        "numero_rodada":
            rodada,

        "status_rodada":
            contexto.StatusRodada,

        "tempo": {
            "data_hora_inicio_rodada": inicio_rodada,
            "data_hora_fim_rodada": fim_rodada,

            "tempo_decorrido_segundos": tempo_decorrido_segundos,
            "tempo_decorrido_formatado":
                _formatar_segundos(tempo_decorrido_segundos),

            "tempo_operacional_segundos": tempo_operacional_segundos,
            "tempo_operacional_formatado":
                _formatar_segundos(tempo_operacional_segundos),

            "primeira_bipagem":
                janela_atividade["primeira_atividade"],
            "ultima_bipagem":
                janela_atividade["ultima_atividade"],
            "janela_bipagens_segundos":
                janela_atividade["tempo_segundos"],
            "janela_bipagens_formatada":
                janela_atividade["tempo_formatado"],

            "tempo_medio_localizacao_segundos": 
                tempo_medio_localizacao_segundos,
            "tempo_medio_localizacao_formatado":
    _formatar_segundos(
        int(
            tempo_medio_localizacao_segundos
            + 0.5
        )
        if tempo_medio_localizacao_segundos is not None
        else None
    )
        },

        "producao": {
            "total_bipagens":
                total_bipagens,

            "quantidade_registrada":
                quantidade_registrada,

            "itens_processados":
                itens_processados,

            "localizacoes_concluidas":
                localizacoes_concluidas
        },

        "produtividade": {
            "global": {
                "bipagens_hora":
                    _calcular_taxa_hora(
                        total_bipagens,
                        tempo_decorrido_segundos
                    ),
                "quantidade_hora":
                    _calcular_taxa_hora(
                        quantidade_registrada,
                        tempo_decorrido_segundos
                    ),
                "itens_processados_hora":
                    _calcular_taxa_hora(
                        itens_processados,
                        tempo_decorrido_segundos
                    ),
                "localizacoes_concluidas_hora":
                    _calcular_taxa_hora(
                        localizacoes_concluidas,
                        tempo_decorrido_segundos
                    )
            },

            "operacional": {
                "bipagens_hora":
                    _calcular_taxa_hora(
                        total_bipagens,
                        tempo_operacional_segundos
                    ),
                "quantidade_hora":
                    _calcular_taxa_hora(
                        quantidade_registrada,
                        tempo_operacional_segundos
                    ),
                "itens_processados_hora":
                    _calcular_taxa_hora(
                        itens_processados,
                        tempo_operacional_segundos
                    ),
                "localizacoes_concluidas_hora":
                    _calcular_taxa_hora(
                        localizacoes_concluidas,
                        tempo_operacional_segundos
                    )
            }
        },

        "qualidade_dado_operador": {
            "operadores_identificados":
                operadores_identificados,

            "bipagens_sem_usuario":
                bipagens_sem_usuario,

            "possui_bipagens_sem_usuario":
                bipagens_sem_usuario > 0
        },

        "extremos_localizacao": {
            "mais_rapida":
                localizacao_mais_rapida,

            "mais_lenta":
                localizacao_mais_lenta
        },

        "operadores":
            operadores,

        "localizacoes_tempo":
            tempos_localizacoes
    }

