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

# ============================================================
# MOVIMENTACAO DOS ULTIMOS 12 MESES
# MOVIMENTACAO_12_MESES_V1
# ============================================================

_ARMAZEM_ESTABELECIMENTO_CNPJ = {
    "ML007": "63590553000161",
}


def _subtrair_um_ano(data: datetime) -> datetime:
    """
    Retorna exatamente um ano antes da data informada.

    Trata 29/02 convertendo para 28/02 quando o ano anterior
    nao for bissexto.
    """

    try:
        return data.replace(
            year=data.year - 1
        )
    except ValueError:
        return data.replace(
            year=data.year - 1,
            day=28
        )


def obter_movimentacao_12_meses(
    cursor,
    id_inventario: int
):
    """
    Retorna recebimentos e expedicoes efetivamente movimentados
    nos 12 meses anteriores a finalizacao de um inventario OFICIAL.

    Regras:

    Recebimento:
    - documento nao cancelado;
    - item conferido;
    - DataConferido preenchida;
    - qArmazenada > 0;
    - quantidade = qArmazenada;
    - valor = qArmazenada * ValorUnitario.

    Expedicao:
    - documento nao cancelado;
    - DataExpedicao preenchida;
    - linha local nao cancelada;
    - cArmazem igual ao inventario;
    - qExpedida > 0;
    - quantidade = qExpedida;
    - valor = qExpedida * ValorUnitario.

    Periodo:
    - fim = DataHoraFinalizacao do inventario;
    - inicio = exatamente 1 ano antes.
    """

    # --------------------------------------------------------
    # INVENTARIO + DATA FINAL
    # --------------------------------------------------------

    cursor.execute(
        """
        SELECT
            I.ID_Inventario,
            I.CodigoInventario,
            I.Tipo,
            I.ClienteId,
            I.Cliente,
            LTRIM(RTRIM(I.cArmazem)) AS Armazem,
            MAX(RF.DataHoraFinalizacao) AS DataHoraFinalizacao

        FROM dbo.Inventarios I

        LEFT JOIN dbo.InventarioResultadoFinal RF
            ON RF.ID_Inventario = I.ID_Inventario

        WHERE
            I.ID_Inventario = ?

        GROUP BY
            I.ID_Inventario,
            I.CodigoInventario,
            I.Tipo,
            I.ClienteId,
            I.Cliente,
            I.cArmazem
        """,
        (
            id_inventario,
        )
    )

    inventario = cursor.fetchone()

    if not inventario:
        raise NotFoundError(
            "Inventário não encontrado."
        )

    tipo = _normalizar_texto(
        inventario[2]
    ).upper()

    if tipo != "OFICIAL":
        raise NotFoundError(
            "Movimentação de 12 meses disponível somente "
            "para inventário oficial."
        )

    cliente_id = inventario[3]

    cliente = _normalizar_texto(
        inventario[4]
    )

    armazem = _normalizar_texto(
        inventario[5]
    ).upper()

    data_fim = inventario[6]

    if data_fim is None:
        raise NotFoundError(
            "Inventário oficial ainda não possui "
            "resultado final."
        )

    data_inicio = _subtrair_um_ano(
        data_fim
    )

    # --------------------------------------------------------
    # CNPJ CLIENTE
    # --------------------------------------------------------

    cursor.execute(
        """
        SELECT
            C.Cnpj
        FROM AlzarsiLog.dbo.Cliente C
        WHERE
            C.Id = ?
        """,
        (
            cliente_id,
        )
    )

    linha_cliente = cursor.fetchone()

    if (
        not linha_cliente
        or
        linha_cliente[0] is None
    ):
        raise NotFoundError(
            "Cliente não encontrado no AlzarsiLog."
        )

    cnpj_cliente = _normalizar_texto(
        linha_cliente[0]
    )

    # --------------------------------------------------------
    # ESTABELECIMENTO
    # --------------------------------------------------------

    cnpj_estabelecimento = (
        _ARMAZEM_ESTABELECIMENTO_CNPJ.get(
            armazem
        )
    )

    if not cnpj_estabelecimento:
        raise NotFoundError(
            f"Armazém {armazem} sem CNPJ de "
            "estabelecimento configurado."
        )

    # --------------------------------------------------------
    # MOVIMENTACOES
    # --------------------------------------------------------

    cursor.execute(
        """
        SET NOCOUNT ON;

        DECLARE @CnpjCliente VARCHAR(30) = ?;
        DECLARE @CnpjEstabelecimento VARCHAR(30) = ?;
        DECLARE @Armazem VARCHAR(50) = ?;
        DECLARE @DataInicio DATETIME2 = ?;
        DECLARE @DataFim DATETIME2 = ?;

        ;WITH Recebimentos AS
        (
            SELECT
                R.Id AS DocumentoId,
                RI.Id AS LinhaId,
                RI.CodigoItem,

                CAST(
                    ISNULL(
                        RI.qArmazenada,
                        0
                    )
                    AS DECIMAL(19,4)
                ) AS Quantidade,

                CAST(
                    RI.ValorUnitario
                    AS DECIMAL(19,6)
                ) AS ValorUnitario

            FROM AlzarsiLog.dbo.Recebimento R

            INNER JOIN
                AlzarsiLog.dbo.RecebimentoItem RI
                ON RI.RecebimentoId = R.Id

            WHERE
                R.CnpjCliente = @CnpjCliente

                AND R.CnpjEstabelecimento =
                    @CnpjEstabelecimento

                AND R.DataCancelado IS NULL

                AND RI.Conferido = 1

                AND RI.DataConferido IS NOT NULL

                AND ISNULL(
                    RI.qArmazenada,
                    0
                ) > 0

                AND RI.DataConferido >=
                    @DataInicio

                AND RI.DataConferido <=
                    @DataFim
        ),

        ResumoRecebimentos AS
        (
            SELECT
                COUNT(
                    DISTINCT DocumentoId
                ) AS Documentos,

                COUNT(*) AS Linhas,

                COUNT(
                    DISTINCT CodigoItem
                ) AS SKUs,

                ISNULL(
                    SUM(Quantidade),
                    0
                ) AS Quantidade,

                ISNULL(
                    SUM(
                        CASE
                            WHEN ValorUnitario IS NULL
                                THEN 1
                            ELSE 0
                        END
                    ),
                    0
                ) AS LinhasSemValor,

                ISNULL(
                    SUM(
                        CASE
                            WHEN ValorUnitario IS NOT NULL
                                THEN
                                    Quantidade
                                    *
                                    ValorUnitario
                            ELSE 0
                        END
                    ),
                    0
                ) AS ValorConhecido

            FROM Recebimentos
        ),

        Expedicoes AS
        (
            SELECT
                E.Id AS DocumentoId,
                EILL.Id AS LinhaId,
                EI.CodigoItem,

                CAST(
                    ISNULL(
                        EILL.qExpedida,
                        0
                    )
                    AS DECIMAL(19,4)
                ) AS Quantidade,

                CAST(
                    EI.ValorUnitario
                    AS DECIMAL(19,6)
                ) AS ValorUnitario

            FROM AlzarsiLog.dbo.Expedicao E

            INNER JOIN
                AlzarsiLog.dbo.ExpedicaoItem EI
                ON EI.ExpedicaoId = E.Id

            INNER JOIN
                AlzarsiLog.dbo.ExpedicaoItemLinhaLocal EILL
                ON EILL.ExpedicaoItemId = EI.Id

            WHERE
                E.CnpjCliente = @CnpjCliente

                AND E.CnpjEstabelecimento =
                    @CnpjEstabelecimento

                AND E.DataCancelado IS NULL

                AND E.DataExpedicao IS NOT NULL

                AND EILL.DataCancelamento IS NULL

                AND LTRIM(
                    RTRIM(EILL.cArmazem)
                ) = @Armazem

                AND ISNULL(
                    EILL.qExpedida,
                    0
                ) > 0

                AND E.DataExpedicao >=
                    @DataInicio

                AND E.DataExpedicao <=
                    @DataFim
        ),

        ResumoExpedicoes AS
        (
            SELECT
                COUNT(
                    DISTINCT DocumentoId
                ) AS Documentos,

                COUNT(*) AS Linhas,

                COUNT(
                    DISTINCT CodigoItem
                ) AS SKUs,

                ISNULL(
                    SUM(Quantidade),
                    0
                ) AS Quantidade,

                ISNULL(
                    SUM(
                        CASE
                            WHEN ValorUnitario IS NULL
                                THEN 1
                            ELSE 0
                        END
                    ),
                    0
                ) AS LinhasSemValor,

                ISNULL(
                    SUM(
                        CASE
                            WHEN ValorUnitario IS NOT NULL
                                THEN
                                    Quantidade
                                    *
                                    ValorUnitario
                            ELSE 0
                        END
                    ),
                    0
                ) AS ValorConhecido

            FROM Expedicoes
        )

        SELECT
            R.Documentos,
            R.Linhas,
            R.SKUs,
            R.Quantidade,
            R.LinhasSemValor,
            R.ValorConhecido,

            E.Documentos,
            E.Linhas,
            E.SKUs,
            E.Quantidade,
            E.LinhasSemValor,
            E.ValorConhecido

        FROM ResumoRecebimentos R
        CROSS JOIN ResumoExpedicoes E;
        """,
        (
            cnpj_cliente,
            cnpj_estabelecimento,
            armazem,
            data_inicio,
            data_fim
        )
    )

    resumo = cursor.fetchone()

    if not resumo:
        raise NotFoundError(
            "Não foi possível calcular a movimentação."
        )

    recebimentos_documentos = int(
        resumo[0] or 0
    )
    recebimentos_linhas = int(
        resumo[1] or 0
    )
    recebimentos_skus = int(
        resumo[2] or 0
    )
    recebimentos_quantidade = float(
        resumo[3] or 0
    )
    recebimentos_sem_valor = int(
        resumo[4] or 0
    )
    recebimentos_valor_conhecido = float(
        resumo[5] or 0
    )

    expedicoes_documentos = int(
        resumo[6] or 0
    )
    expedicoes_linhas = int(
        resumo[7] or 0
    )
    expedicoes_skus = int(
        resumo[8] or 0
    )
    expedicoes_quantidade = float(
        resumo[9] or 0
    )
    expedicoes_sem_valor = int(
        resumo[10] or 0
    )
    expedicoes_valor_conhecido = float(
        resumo[11] or 0
    )

    recebimentos_valor = (
        None
        if recebimentos_sem_valor > 0
        else recebimentos_valor_conhecido
    )

    expedicoes_valor = (
        None
        if expedicoes_sem_valor > 0
        else expedicoes_valor_conhecido
    )

    valor_total = (
        None
        if (
            recebimentos_valor is None
            or
            expedicoes_valor is None
        )
        else
        recebimentos_valor
        +
        expedicoes_valor
    )

    return {
        "id_inventario": int(
            inventario[0]
        ),
        "codigo_inventario": _normalizar_texto(
            inventario[1]
        ),
        "cliente_id": int(
            cliente_id
        ),
        "cliente": cliente,
        "armazem": armazem,

        "periodo": {
            "inicio": data_inicio,
            "fim": data_fim,
            "dias": (
                data_fim
                -
                data_inicio
            ).days,
        },

        "recebimentos": {
            "documentos":
                recebimentos_documentos,

            "linhas":
                recebimentos_linhas,

            "skus":
                recebimentos_skus,

            "quantidade":
                recebimentos_quantidade,

            "valor":
                recebimentos_valor,

            "linhas_sem_valor":
                recebimentos_sem_valor,
        },

        "expedicoes": {
            "documentos":
                expedicoes_documentos,

            "linhas":
                expedicoes_linhas,

            "skus":
                expedicoes_skus,

            "quantidade":
                expedicoes_quantidade,

            "valor":
                expedicoes_valor,

            "linhas_sem_valor":
                expedicoes_sem_valor,
        },

        "total": {
            "documentos":
                recebimentos_documentos
                +
                expedicoes_documentos,

            "linhas":
                recebimentos_linhas
                +
                expedicoes_linhas,

            "quantidade":
                recebimentos_quantidade
                +
                expedicoes_quantidade,

            "valor_movimentado":
                valor_total,
        },
    }


# ============================================================
# VALORACAO DO ESTOQUE DO INVENTARIO
# VALORACAO_ESTOQUE_V1
#
# Prioridade:
# 1. ValorUnitario congelado no snapshot.
# 2. Ultimo recebimento valido do mesmo Codigo + Lote.
# 3. Ultimo recebimento valido do mesmo Codigo.
# 4. Sem custo.
#
# A consulta e somente leitura. O snapshot nao e alterado.
# ============================================================

def obter_valoracao_estoque(
    cursor,
    id_inventario: int
):
    cursor.execute(
        """
        SELECT
            I.Tipo,
            I.ClienteId,
            I.Cliente,
            I.cArmazem,

            (
                SELECT
                    MAX(RF.DataHoraFinalizacao)
                FROM dbo.InventarioResultadoFinal RF
                WHERE
                    RF.ID_Inventario = I.ID_Inventario
            ) AS DataFim

        FROM dbo.Inventarios I

        WHERE
            I.ID_Inventario = ?
        """,
        (
            id_inventario,
        )
    )

    inventario = cursor.fetchone()

    if not inventario:
        raise NotFoundError(
            "Inventário não encontrado."
        )

    tipo = _normalizar_texto(
        inventario[0]
    ).upper()

    if tipo != "OFICIAL":
        raise NotFoundError(
            "Valoração disponível somente "
            "para inventário oficial."
        )

    cliente_id = inventario[1]

    cliente = _normalizar_texto(
        inventario[2]
    )

    armazem = _normalizar_texto(
        inventario[3]
    ).upper()

    data_fim = inventario[4]

    if data_fim is None:
        raise NotFoundError(
            "Inventário oficial ainda não possui "
            "resultado final."
        )

    # --------------------------------------------------------
    # CLIENTE NO ALZARSILOG
    # --------------------------------------------------------

    cursor.execute(
        """
        SELECT
            C.Cnpj
        FROM AlzarsiLog.dbo.Cliente C
        WHERE
            C.Id = ?
        """,
        (
            cliente_id,
        )
    )

    linha_cliente = cursor.fetchone()

    if (
        not linha_cliente
        or
        linha_cliente[0] is None
    ):
        raise NotFoundError(
            "Cliente n?o encontrado no AlzarsiLog."
        )

    cnpj_cliente = _normalizar_texto(
        linha_cliente[0]
    )

    # --------------------------------------------------------
    # ESTABELECIMENTO
    # --------------------------------------------------------

    cnpj_estabelecimento = (
        _ARMAZEM_ESTABELECIMENTO_CNPJ.get(
            armazem
        )
    )

    if not cnpj_estabelecimento:
        raise NotFoundError(
            f"Armaz?m {armazem} sem CNPJ de "
            "estabelecimento configurado."
        )

    # --------------------------------------------------------
    # VALORACAO
    # --------------------------------------------------------

    cursor.execute(
        """
        SET NOCOUNT ON;

        DECLARE @CnpjCliente VARCHAR(30) = ?;
        DECLARE @CnpjEstabelecimento VARCHAR(30) = ?;
        DECLARE @DataFim DATETIME2 = ?;

        SELECT
            S.ID_Snapshot,
            S.Codigo,
            S.Lote,
            S.qArmazenado,

            CAST(
                S.ValorUnitario
                AS DECIMAL(19,6)
            ) AS ValorSnapshot,

            CAST(
                COALESCE(
                    S.ValorUnitario,
                    RL.ValorUnitario,
                    RC.ValorUnitario
                )
                AS DECIMAL(19,6)
            ) AS ValorUnitarioFinal,

            CASE
                WHEN S.ValorUnitario IS NOT NULL
                    THEN 'SNAPSHOT'

                WHEN RL.ValorUnitario IS NOT NULL
                    THEN 'ULTIMO_RECEBIMENTO_CODIGO_LOTE'

                WHEN RC.ValorUnitario IS NOT NULL
                    THEN 'ULTIMO_RECEBIMENTO_CODIGO'

                ELSE 'SEM_CUSTO'
            END AS OrigemCusto

        FROM dbo.InventarioEstoqueSnapshot S

        OUTER APPLY
        (
            SELECT TOP (1)
                CAST(
                    RI.ValorUnitario
                    AS DECIMAL(19,6)
                ) AS ValorUnitario

            FROM AlzarsiLog.dbo.RecebimentoItem RI

            INNER JOIN AlzarsiLog.dbo.Recebimento R
                ON R.Id = RI.RecebimentoId

            WHERE
                R.CnpjCliente = @CnpjCliente

                AND R.CnpjEstabelecimento =
                    @CnpjEstabelecimento

                AND R.DataCancelado IS NULL

                AND RI.Conferido = 1

                AND RI.DataConferido IS NOT NULL

                AND RI.DataConferido <= @DataFim

                AND ISNULL(
                    RI.qArmazenada,
                    0
                ) > 0

                AND RI.ValorUnitario IS NOT NULL

                AND LTRIM(RTRIM(RI.CodigoItem))
                    =
                    LTRIM(RTRIM(S.Codigo))

                AND LTRIM(
                    RTRIM(
                        ISNULL(
                            RI.CodigoLote,
                            ''
                        )
                    )
                )
                    =
                    LTRIM(
                        RTRIM(
                            ISNULL(
                                S.Lote,
                                ''
                            )
                        )
                    )

            ORDER BY
                RI.DataConferido DESC,
                RI.Id DESC
        ) RL

        OUTER APPLY
        (
            SELECT TOP (1)
                CAST(
                    RI.ValorUnitario
                    AS DECIMAL(19,6)
                ) AS ValorUnitario

            FROM AlzarsiLog.dbo.RecebimentoItem RI

            INNER JOIN AlzarsiLog.dbo.Recebimento R
                ON R.Id = RI.RecebimentoId

            WHERE
                R.CnpjCliente = @CnpjCliente

                AND R.CnpjEstabelecimento =
                    @CnpjEstabelecimento

                AND R.DataCancelado IS NULL

                AND RI.Conferido = 1

                AND RI.DataConferido IS NOT NULL

                AND RI.DataConferido <= @DataFim

                AND ISNULL(
                    RI.qArmazenada,
                    0
                ) > 0

                AND RI.ValorUnitario IS NOT NULL

                AND LTRIM(RTRIM(RI.CodigoItem))
                    =
                    LTRIM(RTRIM(S.Codigo))

            ORDER BY
                RI.DataConferido DESC,
                RI.Id DESC
        ) RC

        WHERE
            S.ID_Inventario = ?

        ORDER BY
            S.Codigo,
            S.Lote,
            S.ID_Snapshot;
        """,
        (
            cnpj_cliente,
            cnpj_estabelecimento,
            data_fim,
            id_inventario
        )
    )

    linhas = cursor.fetchall()

    agrupados = {}

    for linha in linhas:
        codigo = _normalizar_texto(
            linha[1]
        )

        lote = _normalizar_texto(
            linha[2]
        )

        quantidade = float(
            linha[3] or 0
        )

        valor_unitario = (
            None
            if linha[5] is None
            else float(linha[5])
        )

        origem = _normalizar_texto(
            linha[6]
        ) or "SEM_CUSTO"

        chave = (
            codigo,
            lote
        )

        if chave not in agrupados:
            agrupados[chave] = {
                "codigo": codigo,
                "lote": lote,
                "quantidade": 0.0,
                "valor_total_conhecido": 0.0,
                "custo_referencia": None,
                "linhas": 0,
                "linhas_sem_custo": 0,
                "origens": {
                    "SNAPSHOT": 0,
                    "ULTIMO_RECEBIMENTO_CODIGO_LOTE": 0,
                    "ULTIMO_RECEBIMENTO_CODIGO": 0,
                    "SEM_CUSTO": 0,
                },
            }

        item = agrupados[chave]

        item["quantidade"] += quantidade
        item["linhas"] += 1

        if origem not in item["origens"]:
            item["origens"][origem] = 0

        item["origens"][origem] += 1

        if valor_unitario is None:
            if quantidade != 0:
                item["linhas_sem_custo"] += 1

            continue

        if item["custo_referencia"] is None:
            item["custo_referencia"] = (
                valor_unitario
            )

        item["valor_total_conhecido"] += (
            quantidade
            *
            valor_unitario
        )

    itens = []

    total_valor_estoque = 0.0
    possui_item_sem_custo = False

    itens_snapshot = 0
    itens_fallback_lote = 0
    itens_fallback_codigo = 0
    itens_mistos = 0
    itens_sem_custo = 0

    for chave in sorted(
        agrupados.keys()
    ):
        item = agrupados[chave]

        quantidade = float(
            item["quantidade"]
        )

        linhas_sem_custo = int(
            item["linhas_sem_custo"]
        )

        origens_ativas = [
            origem
            for origem, total in
            item["origens"].items()
            if (
                total > 0
                and
                origem != "SEM_CUSTO"
            )
        ]

        if linhas_sem_custo > 0:
            valor_total = None
            valor_unitario = None
            origem_final = "SEM_CUSTO"

            itens_sem_custo += 1
            possui_item_sem_custo = True

        else:
            valor_total = float(
                item["valor_total_conhecido"]
            )

            if quantidade != 0:
                valor_unitario = (
                    valor_total
                    /
                    quantidade
                )
            else:
                valor_unitario = (
                    item["custo_referencia"]
                )

            if len(origens_ativas) == 1:
                origem_final = (
                    origens_ativas[0]
                )
            elif len(origens_ativas) > 1:
                origem_final = "MISTO"
            else:
                origem_final = "SEM_CUSTO"

            if origem_final == "SNAPSHOT":
                itens_snapshot += 1

            elif (
                origem_final
                ==
                "ULTIMO_RECEBIMENTO_CODIGO_LOTE"
            ):
                itens_fallback_lote += 1

            elif (
                origem_final
                ==
                "ULTIMO_RECEBIMENTO_CODIGO"
            ):
                itens_fallback_codigo += 1

            elif origem_final == "MISTO":
                itens_mistos += 1

            elif origem_final == "SEM_CUSTO":
                itens_sem_custo += 1
                possui_item_sem_custo = True

            if valor_total is not None:
                total_valor_estoque += (
                    valor_total
                )

        itens.append(
            {
                "codigo": item["codigo"],
                "lote": item["lote"],
                "quantidade": quantidade,
                "valor_unitario":
                    valor_unitario,
                "valor_total":
                    valor_total,
                "origem_custo":
                    origem_final,
                "linhas":
                    int(item["linhas"]),
                "linhas_sem_custo":
                    linhas_sem_custo,
                "origens":
                    item["origens"],
            }
        )

    return {
        "id_inventario":
            int(id_inventario),

        "cliente_id":
            int(cliente_id),

        "cliente":
            cliente,

        "armazem":
            armazem,

        "data_referencia":
            data_fim,

        "resumo": {
            "itens":
                len(itens),

            "itens_snapshot":
                itens_snapshot,

            "itens_fallback_codigo_lote":
                itens_fallback_lote,

            "itens_fallback_codigo":
                itens_fallback_codigo,

            "itens_mistos":
                itens_mistos,

            "itens_sem_custo":
                itens_sem_custo,

            "valor_estoque": (
                None
                if possui_item_sem_custo
                else total_valor_estoque
            ),
        },

        "itens":
            itens,
    }

