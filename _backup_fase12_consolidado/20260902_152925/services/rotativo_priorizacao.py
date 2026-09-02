from domain.exceptions import BusinessRuleViolation
from datetime import datetime

from services.rotativo_tendencia import (
    consultar_tendencias_rotativo,
)


# ============================================================
# PRIORIZAÇÃO DE LOCALIZAÇÕES DO INVENTÁRIO ROTATIVO
#
# V1.3
#
# Objetivos:
# - Controlar risco histórico da localização
# - Considerar tempo desde última contagem
# - Priorizar localizações nunca contadas
# - Considerar recorrência de divergências
# - Considerar magnitude das divergências
# - Sempre sugerir localizações PENDENTES
# - Integrar tendência, recorrência, tratativas e eficácia
#
# Tipos de sugestão:
# - RISCO
# - COBERTURA_CICLO
# ============================================================


# ============================================================
# PESOS DO SCORE
# ============================================================

PESO_TAXA_DIVERGENCIA_AJUSTADA = 30.0
PESO_RECENCIA = 30.0
PESO_CONSECUTIVAS = 20.0
PESO_MAGNITUDE = 15.0
PESO_NUNCA_CONTADA = 5.0
PESO_TENDENCIA_MAXIMA = 15.0

BONUS_TENDENCIA = {
    "DETERIORANDO": 15.0,
    "RECORRENTE": 10.0,
    "ATENCAO": 5.0,
    "MELHORANDO": 0.0,
    "ESTAVEL": 0.0,
    "SEM_HISTORICO": 0.0,
}


# ============================================================
# PARÂMETROS
# ============================================================

DIAS_RECENCIA_MAXIMA = 90
CONSECUTIVAS_MAXIMAS = 3

LIMITE_SUGESTAO_PADRAO = 50.0
QUANTIDADE_SUGESTOES_PADRAO = 20


# ============================================================
# UTILITÁRIOS
# ============================================================

def _normalizar(valor):
    return str(
        valor or ""
    ).strip().upper()


def _classificar_score(score):

    if score >= 75:
        return "CRITICO"

    if score >= 50:
        return "ALTO"

    if score >= 25:
        return "MEDIO"

    return "BAIXO"


def _dias_sem_contagem(data):

    if data is None:
        return None

    if getattr(
        data,
        "tzinfo",
        None
    ):

        agora = datetime.now(
            tz=data.tzinfo
        )

    else:

        agora = datetime.now()

    return max(
        0,
        (
            agora
            -
            data
        ).days
    )


# ============================================================
# CONFIANÇA HISTÓRICA
# ============================================================

def _fator_confianca_historica(
    total_contagens
):

    if total_contagens <= 0:
        return 0.0

    if total_contagens == 1:
        return 0.35

    if total_contagens == 2:
        return 0.55

    if total_contagens == 3:
        return 0.75

    if total_contagens == 4:
        return 0.90

    return 1.0


def _classificar_confianca(
    total_contagens
):

    if total_contagens >= 5:
        return "ALTA"

    if total_contagens >= 3:
        return "MEDIA"

    if total_contagens >= 1:
        return "BAIXA"

    return "SEM_HISTORICO"


# ============================================================
# BUSCAR CICLO ABERTO
# ============================================================

def _buscar_ciclo_aberto(
    cursor,
    cliente_id,
    armazem
):

    cursor.execute(
        """
        SELECT TOP 1
            ID_Ciclo,
            CodigoCiclo,
            ClienteId,
            cArmazem,
            Status,
            TotalLocalizacoes,
            LocalizacoesContadas,
            PercentualCobertura
        FROM dbo.CiclosRotativo
        WHERE
            ClienteId = ?
            AND UPPER(
                LTRIM(
                    RTRIM(
                        cArmazem
                    )
                )
            ) = ?
            AND Status = 'ABERTO'
        ORDER BY
            ID_Ciclo DESC
        """,
        (
            cliente_id,
            _normalizar(
                armazem
            ),
        ),
    )

    return cursor.fetchone()


# ============================================================
# BUSCAR HISTÓRICO DA LOCALIZAÇÃO
# ============================================================

def _buscar_historico_localizacao(
    cursor,
    id_rotativo_localizacao
):

    cursor.execute(
        """
        SELECT
            ID_HistoricoRotativo,
            DataHoraContagem,
            PossuiDivergencia,
            QuantidadeItens,
            QuantidadeItensOK,
            QuantidadeItensDivergentes
        FROM dbo.RotativoHistoricoLocalizacoes
        WHERE
            ID_RotativoLocalizacao = ?
        ORDER BY
            DataHoraContagem ASC,
            ID_HistoricoRotativo ASC
        """,
        (
            id_rotativo_localizacao,
        ),
    )

    return cursor.fetchall()


# ============================================================
# ANALISAR HISTÓRICO
# ============================================================

def _analisar_historico(
    historico
):

    total = len(
        historico
    )

    if total == 0:

        return {
            "contagens_historicas":
                0,

            "contagens_com_divergencia":
                0,

            "taxa_divergencia_percentual":
                0.0,

            "taxa_divergencia_ajustada_percentual":
                0.0,

            "fator_confianca":
                0.0,

            "confianca":
                "SEM_HISTORICO",

            "divergencias_consecutivas":
                0,

            "magnitude_media_percentual":
                0.0,

            "ultima_contagem_historico":
                None,
        }

    divergencias = 0
    magnitudes = []

    # --------------------------------------------------------
    # Analisar cada contagem histórica
    # --------------------------------------------------------

    for linha in historico:

        possui_divergencia = bool(
            linha.PossuiDivergencia
        )

        if possui_divergencia:
            divergencias += 1

        total_itens = int(
            linha.QuantidadeItens
            or 0
        )

        itens_divergentes = int(
            linha.QuantidadeItensDivergentes
            or 0
        )

        if possui_divergencia:

            if total_itens > 0:

                magnitude = (
                    itens_divergentes
                    /
                    total_itens
                    *
                    100
                )

                magnitude = min(
                    100.0,
                    magnitude
                )

            else:

                magnitude = 100.0

            magnitudes.append(
                magnitude
            )

    # --------------------------------------------------------
    # Divergências consecutivas
    # --------------------------------------------------------

    consecutivas = 0

    for linha in reversed(
        historico
    ):

        if bool(
            linha.PossuiDivergencia
        ):
            consecutivas += 1

        else:
            break

    # --------------------------------------------------------
    # Taxa histórica original
    # --------------------------------------------------------

    taxa_original = (
        divergencias
        /
        total
        *
        100
    )

    # --------------------------------------------------------
    # Confiança histórica
    # --------------------------------------------------------

    fator_confianca = (
        _fator_confianca_historica(
            total
        )
    )

    # --------------------------------------------------------
    # Taxa ajustada
    # --------------------------------------------------------

    taxa_ajustada = (
        taxa_original
        *
        fator_confianca
    )

    # --------------------------------------------------------
    # Magnitude média
    # --------------------------------------------------------

    if magnitudes:

        magnitude_media = (
            sum(
                magnitudes
            )
            /
            len(
                magnitudes
            )
        )

    else:

        magnitude_media = 0.0

    return {
        "contagens_historicas":
            total,

        "contagens_com_divergencia":
            divergencias,

        "taxa_divergencia_percentual":
            round(
                taxa_original,
                2
            ),

        "taxa_divergencia_ajustada_percentual":
            round(
                taxa_ajustada,
                2
            ),

        "fator_confianca":
            fator_confianca,

        "confianca":
            _classificar_confianca(
                total
            ),

        "divergencias_consecutivas":
            consecutivas,

        "magnitude_media_percentual":
            round(
                magnitude_media,
                2
            ),

        "ultima_contagem_historico":
            historico[
                -1
            ].DataHoraContagem,
    }


# ============================================================
# COMPONENTE DE TENDÊNCIA INTEGRADA
#
# A tendência já consolida:
# - recorrência item/lote
# - tratativas pendentes
# - eficácia das resoluções
#
# Portanto esses sinais não são somados separadamente ao score,
# evitando dupla contagem do mesmo risco operacional.
# ============================================================

def _calcular_componente_tendencia(
    tendencia_info
):

    if not tendencia_info:
        return 0.0

    classificacao = _normalizar(
        tendencia_info.get(
            "classificacao_tendencia"
        )
    )

    return float(
        BONUS_TENDENCIA.get(
            classificacao,
            0.0
        )
    )


# ============================================================
# CALCULAR SCORE
# ============================================================

def _calcular_score(
    ultima_contagem,
    analise,
    tendencia_info=None
):

    taxa_ajustada = (
        analise[
            "taxa_divergencia_ajustada_percentual"
        ]
    )

    consecutivas = (
        analise[
            "divergencias_consecutivas"
        ]
    )

    magnitude = (
        analise[
            "magnitude_media_percentual"
        ]
    )

    dias = _dias_sem_contagem(
        ultima_contagem
    )

    # --------------------------------------------------------
    # Taxa histórica ajustada
    # --------------------------------------------------------

    componente_taxa = (
        min(
            100.0,
            taxa_ajustada
        )
        /
        100
        *
        PESO_TAXA_DIVERGENCIA_AJUSTADA
    )

    # --------------------------------------------------------
    # Recência
    # --------------------------------------------------------

    if ultima_contagem is None:
        componente_recencia = (
            PESO_RECENCIA
        )
    else:
        componente_recencia = (
            min(
                dias,
                DIAS_RECENCIA_MAXIMA
            )
            /
            DIAS_RECENCIA_MAXIMA
            *
            PESO_RECENCIA
        )

    # --------------------------------------------------------
    # Divergências consecutivas
    # --------------------------------------------------------

    componente_consecutivas = (
        min(
            consecutivas,
            CONSECUTIVAS_MAXIMAS
        )
        /
        CONSECUTIVAS_MAXIMAS
        *
        PESO_CONSECUTIVAS
    )

    # --------------------------------------------------------
    # Magnitude das divergências
    # --------------------------------------------------------

    componente_magnitude = (
        min(
            100.0,
            magnitude
        )
        /
        100
        *
        PESO_MAGNITUDE
    )

    # --------------------------------------------------------
    # Bônus de cobertura
    # --------------------------------------------------------

    componente_nunca_contada = (
        PESO_NUNCA_CONTADA
        if ultima_contagem is None
        else 0.0
    )

    # --------------------------------------------------------
    # Tendência integrada
    #
    # DETERIORANDO = +15
    # RECORRENTE   = +10
    # ATENCAO      = +5
    # demais       = 0
    # --------------------------------------------------------

    componente_tendencia = (
        _calcular_componente_tendencia(
            tendencia_info
        )
    )

    # --------------------------------------------------------
    # Score total
    # --------------------------------------------------------

    score_base = (
        componente_taxa
        +
        componente_recencia
        +
        componente_consecutivas
        +
        componente_magnitude
        +
        componente_nunca_contada
    )

    score = (
        score_base
        +
        componente_tendencia
    )

    score = round(
        min(
            100.0,
            score
        ),
        2
    )

    return {
        "score":
            score,

        "score_base":
            round(
                min(
                    100.0,
                    score_base
                ),
                2
            ),

        "classificacao":
            _classificar_score(
                score
            ),

        "dias_sem_contagem":
            dias,

        "componentes": {
            "taxa_divergencia_ajustada":
                round(
                    componente_taxa,
                    2
                ),

            "recencia":
                round(
                    componente_recencia,
                    2
                ),

            "divergencias_consecutivas":
                round(
                    componente_consecutivas,
                    2
                ),

            "magnitude":
                round(
                    componente_magnitude,
                    2
                ),

            "nunca_contada":
                round(
                    componente_nunca_contada,
                    2
                ),

            "tendencia_integrada":
                round(
                    componente_tendencia,
                    2
                ),
        },
    }


# ============================================================
# MOTIVOS DA PRIORIZAÇÃO
# ============================================================

def _montar_motivos(
    ultima_contagem,
    analise,
    score_info,
    tendencia_info=None
):

    motivos = []

    # --------------------------------------------------------
    # Cobertura
    # --------------------------------------------------------

    if ultima_contagem is None:
        motivos.append(
            "Localização nunca contada"
        )
    else:
        motivos.append(
            f"{score_info['dias_sem_contagem']} "
            "dias desde a última contagem"
        )

    # --------------------------------------------------------
    # Histórico
    # --------------------------------------------------------

    if (
        analise[
            "taxa_divergencia_percentual"
        ]
        > 0
    ):
        motivos.append(
            "Taxa histórica de divergência de "
            f"{analise['taxa_divergencia_percentual']}% "
            f"em {analise['contagens_historicas']} "
            "contagem(ns)"
        )

    if (
        analise[
            "taxa_divergencia_ajustada_percentual"
        ]
        > 0
    ):
        motivos.append(
            "Taxa ajustada pela confiança histórica: "
            f"{analise['taxa_divergencia_ajustada_percentual']}%"
        )

    if (
        analise[
            "divergencias_consecutivas"
        ]
        > 0
    ):
        motivos.append(
            f"{analise['divergencias_consecutivas']} "
            "divergência(s) consecutiva(s)"
        )

    if (
        analise[
            "magnitude_media_percentual"
        ]
        > 0
    ):
        motivos.append(
            "Magnitude média das divergências: "
            f"{analise['magnitude_media_percentual']}%"
        )

    # --------------------------------------------------------
    # Tendência integrada
    # --------------------------------------------------------

    if tendencia_info:
        classificacao = _normalizar(
            tendencia_info.get(
                "classificacao_tendencia"
            )
        )

        componente = (
            score_info
            .get(
                "componentes",
                {}
            )
            .get(
                "tendencia_integrada",
                0
            )
        )

        if classificacao:
            motivos.append(
                "Tendência integrada: "
                f"{classificacao} "
                f"(+{componente} ponto(s) no score)"
            )

        motivos_tendencia = (
            tendencia_info.get(
                "motivos",
                []
            )
            or []
        )

        for motivo in motivos_tendencia[:3]:
            if motivo not in motivos:
                motivos.append(
                    motivo
                )

    if not motivos:
        motivos.append(
            "Sem fatores históricos relevantes"
        )

    return motivos


# ============================================================
# DEFINIR TIPO DE SUGESTÃO
# ============================================================

def _definir_tipo_sugestao(
    item,
    limite_score_sugestao
):

    if not item[
        "elegivel_sugestao"
    ]:
        return None

    tendencia = (
        item.get(
            "tendencia",
            {}
        )
        or {}
    )

    classificacao_tendencia = _normalizar(
        tendencia.get(
            "classificacao_tendencia"
        )
    )

    # Tendência crítica/recorrente caracteriza sugestão
    # por risco mesmo que o score ainda esteja abaixo do
    # limite numérico configurado.
    if classificacao_tendencia in (
        "DETERIORANDO",
        "RECORRENTE",
    ):
        return "RISCO"

    if (
        item[
            "score_risco"
        ]
        >=
        limite_score_sugestao
    ):
        return "RISCO"

    return "COBERTURA_CICLO"


# ============================================================
# CHAVE DE ORDENAÇÃO DAS SUGESTÕES
# ============================================================

def _chave_prioridade(
    item
):

    nunca_contada = (
        item[
            "ultima_contagem"
        ]
        is None
    )

    dias_sem_contagem = (
        item[
            "dias_sem_contagem"
        ]
    )

    if dias_sem_contagem is None:
        dias_sem_contagem = 999999

    taxa_divergencia = (
        item[
            "historico"
        ][
            "taxa_divergencia_percentual"
        ]
    )

    consecutivas = (
        item[
            "historico"
        ][
            "divergencias_consecutivas"
        ]
    )

    # --------------------------------------------------------
    # Ordem:
    #
    # 1. Nunca contada
    # 2. Maior score
    # 3. Mais dias sem contagem
    # 4. Maior taxa de divergência
    # 5. Mais divergências consecutivas
    # 6. Localização
    # --------------------------------------------------------

    return (
        0
        if nunca_contada
        else 1,

        -item[
            "score_risco"
        ],

        -dias_sem_contagem,

        -taxa_divergencia,

        -consecutivas,

        item[
            "localizacao"
        ],
    )


# ============================================================
# RECALCULAR PRIORIZAÇÃO ROTATIVA
# ============================================================

def recalcular_priorizacao_rotativo(
    conn,
    cursor,
    cliente_id,
    armazem,
    limite_score_sugestao=LIMITE_SUGESTAO_PADRAO,
    quantidade_sugestoes=QUANTIDADE_SUGESTOES_PADRAO,
):

    armazem = _normalizar(
        armazem
    )

    # ========================================================
    # VALIDAÇÕES
    # ========================================================

    if not armazem:

        raise BusinessRuleViolation(
            "Armazém é obrigatório."
        )

    if not (
        0
        <=
        limite_score_sugestao
        <=
        100
    ):

        raise BusinessRuleViolation(
            "limite_score_sugestao "
            "deve estar entre 0 e 100."
        )

    if quantidade_sugestoes < 1:

        raise BusinessRuleViolation(
            "quantidade_sugestoes "
            "deve ser maior que zero."
        )

    # ========================================================
    # CICLO ABERTO
    # ========================================================

    ciclo = (
        _buscar_ciclo_aberto(
            cursor=cursor,
            cliente_id=cliente_id,
            armazem=armazem
        )
    )

    # ========================================================
    # BUSCAR UNIVERSO ROTATIVO
    # ========================================================

    cursor.execute(
        """
        SELECT
            ID_RotativoLocalizacao,
            ClienteId,
            cArmazem,
            Localizacao,
            Status,
            UltimaContagem,
            ID_InventarioUltimaContagem,
            ID_RodadaUltimaContagem
        FROM dbo.RotativoLocalizacoes
        WHERE
            ClienteId = ?
            AND UPPER(
                LTRIM(
                    RTRIM(
                        cArmazem
                    )
                )
            ) = ?
            AND Status <> 'INATIVA'
        ORDER BY
            Localizacao
        """,
        (
            cliente_id,
            armazem,
        ),
    )

    localizacoes = (
        cursor.fetchall()
    )

    if not localizacoes:

        raise BusinessRuleViolation(
            "Nenhuma localização cadastrada em "
            "RotativoLocalizacoes para este cliente/armazém."
        )

    # ========================================================
    # STATUS DAS LOCALIZAÇÕES NO CICLO
    # ========================================================

    status_ciclo = {}

    if ciclo:

        cursor.execute(
            """
            SELECT
                ID_RotativoLocalizacao,
                ID_CicloLocalizacao,
                Status
            FROM dbo.CicloRotativoLocalizacoes
            WHERE
                ID_Ciclo = ?
            """,
            (
                ciclo.ID_Ciclo,
            ),
        )

        for linha in cursor.fetchall():

            status_ciclo[
                linha.ID_RotativoLocalizacao
            ] = {
                "id_ciclo_localizacao":
                    linha.ID_CicloLocalizacao,

                "status":
                    _normalizar(
                        linha.Status
                    ),
            }

    # ========================================================
    # TENDÊNCIA INTEGRADA DAS LOCALIZAÇÕES
    #
    # consultar_tendencias_rotativo() utiliza rotativo_contexto.py
    # e consolida:
    # - histórico
    # - recorrência item/lote
    # - tratativas
    # - eficácia das resoluções
    # ========================================================

    tendencias_por_localizacao = {}

    if ciclo:
        analise_tendencias = (
            consultar_tendencias_rotativo(
                cursor=cursor,
                cliente_id=cliente_id,
                armazem=armazem,
                limite_historico=6,
                somente_alertas=False,
            )
        )

        for tendencia in (
            analise_tendencias.get(
                "tendencias",
                []
            )
            or []
        ):
            tendencias_por_localizacao[
                tendencia[
                    "id_rotativo_localizacao"
                ]
            ] = tendencia

    # ========================================================
    # CALCULAR SCORE DAS LOCALIZAÇÕES
    # ========================================================

    calculados = []

    for linha in localizacoes:

        historico = (
            _buscar_historico_localizacao(
                cursor=cursor,
                id_rotativo_localizacao=(
                    linha.ID_RotativoLocalizacao
                )
            )
        )

        analise = (
            _analisar_historico(
                historico
            )
        )

        ultima_contagem = (
            linha.UltimaContagem
            or
            analise[
                "ultima_contagem_historico"
            ]
        )

        tendencia_info = (
            tendencias_por_localizacao.get(
                linha.ID_RotativoLocalizacao
            )
        )

        score_info = (
            _calcular_score(
                ultima_contagem=ultima_contagem,
                analise=analise,
                tendencia_info=tendencia_info,
            )
        )

        ciclo_info = (
            status_ciclo.get(
                linha.ID_RotativoLocalizacao
            )
        )

        status_no_ciclo = (
            ciclo_info[
                "status"
            ]
            if ciclo_info
            else None
        )

        elegivel = (
            ciclo is not None
            and
            status_no_ciclo
            ==
            "PENDENTE"
        )

        item = {
            "id_rotativo_localizacao":
                linha.ID_RotativoLocalizacao,

            "localizacao":
                _normalizar(
                    linha.Localizacao
                ),

            "ultima_contagem":
                ultima_contagem,

            "score_risco":
                score_info[
                    "score"
                ],

            "score_base":
                score_info[
                    "score_base"
                ],

            "classificacao_risco":
                score_info[
                    "classificacao"
                ],

            "dias_sem_contagem":
                score_info[
                    "dias_sem_contagem"
                ],

            "componentes_score":
                score_info[
                    "componentes"
                ],

            "historico":
                analise,

            "tendencia":
                tendencia_info,

            "status_ciclo":
                status_no_ciclo,

            "elegivel_sugestao":
                elegivel,

            "motivos":
                _montar_motivos(
                    ultima_contagem=ultima_contagem,
                    analise=analise,
                    score_info=score_info,
                    tendencia_info=tendencia_info,
                ),

            "sugerida":
                False,

            "prioridade":
                None,

            "tipo_sugestao":
                None,
        }

        calculados.append(
            item
        )

    # ========================================================
    # CANDIDATOS À SUGESTÃO
    #
    # V1.3:
    # Não exige score mínimo para entrar na lista de cobertura.
    # Tendências DETERIORANDO/RECORRENTE são classificadas como RISCO.
    #
    # Toda localização PENDENTE pode ser sugerida.
    # ========================================================

    candidatos = [
        item
        for item in calculados
        if item[
            "elegivel_sugestao"
        ]
    ]

    candidatos.sort(
        key=_chave_prioridade
    )

    # ========================================================
    # LIMITAR QUANTIDADE DE SUGESTÕES
    # ========================================================

    selecionados = (
        candidatos[
            :quantidade_sugestoes
        ]
    )

    # ========================================================
    # ATRIBUIR PRIORIDADE
    # ========================================================

    prioridades = {}

    for indice, item in enumerate(
        selecionados,
        start=1
    ):

        prioridades[
            item[
                "id_rotativo_localizacao"
            ]
        ] = indice

    # ========================================================
    # CLASSIFICAR SUGESTÕES
    # ========================================================

    for item in calculados:

        identificador = (
            item[
                "id_rotativo_localizacao"
            ]
        )

        if identificador in prioridades:

            item[
                "sugerida"
            ] = True

            item[
                "prioridade"
            ] = prioridades[
                identificador
            ]

            item[
                "tipo_sugestao"
            ] = (
                _definir_tipo_sugestao(
                    item=item,
                    limite_score_sugestao=(
                        limite_score_sugestao
                    )
                )
            )

        else:

            item[
                "sugerida"
            ] = False

            item[
                "prioridade"
            ] = None

            item[
                "tipo_sugestao"
            ] = None

    # ========================================================
    # ATUALIZAR BANCO
    # ========================================================

    try:

        # ----------------------------------------------------
        # Cadastro mestre da localização
        # ----------------------------------------------------

        for item in calculados:

            cursor.execute(
    """
    UPDATE dbo.RotativoLocalizacoes
    SET
        ScoreRisco = ?,
        ClassificacaoRisco = ?,
        Sugerida = ?,
        Prioridade = ?,
        TipoSugestao = ?,
        DataHoraAtualizacao = SYSDATETIME()
    WHERE
        ID_RotativoLocalizacao = ?
    """,
    (
        item["score_risco"],
        item["classificacao_risco"],
        bool(item["sugerida"]),
        item["prioridade"],
        item["tipo_sugestao"],
        item["id_rotativo_localizacao"],
    ),
)

        # ----------------------------------------------------
        # Snapshot do ciclo atual
        # ----------------------------------------------------

        if ciclo:

            for item in calculados:

                ciclo_info = (
                    status_ciclo.get(
                        item[
                            "id_rotativo_localizacao"
                        ]
                    )
                )

                if not ciclo_info:
                    continue

                cursor.execute(
    """
    UPDATE dbo.CicloRotativoLocalizacoes
    SET
        ScoreRiscoEntrada = ?,
        ClassificacaoRiscoEntrada = ?,
        Sugerida = ?,
        Prioridade = ?,
        TipoSugestao = ?,
        DataHoraAtualizacao = SYSDATETIME()
    WHERE
        ID_CicloLocalizacao = ?
    """,
    (
        item[
            "score_risco"
        ],

        item[
            "classificacao_risco"
        ],

        bool(
            item[
                "sugerida"
            ]
        ),

        item[
            "prioridade"
        ],

        item[
            "tipo_sugestao"
        ],

        ciclo_info[
            "id_ciclo_localizacao"
        ],
    ),
)

        conn.commit()

    except Exception:

        conn.rollback()
        raise

    # ========================================================
    # ORDENAR RETORNO
    # ========================================================

    calculados.sort(
        key=lambda item: (
            0
            if item[
                "sugerida"
            ]
            else 1,

            item[
                "prioridade"
            ]
            if item[
                "prioridade"
            ]
            is not None
            else 999999,

            -item[
                "score_risco"
            ],

            item[
                "localizacao"
            ],
        )
    )

    # ========================================================
    # RESUMOS
    # ========================================================

    sugestoes_risco = sum(
        1
        for item in calculados
        if (
            item[
                "sugerida"
            ]
            and
            item[
                "tipo_sugestao"
            ]
            ==
            "RISCO"
        )
    )

    sugestoes_cobertura = sum(
        1
        for item in calculados
        if (
            item[
                "sugerida"
            ]
            and
            item[
                "tipo_sugestao"
            ]
            ==
            "COBERTURA_CICLO"
        )
    )

    nunca_contadas_pendentes = sum(
        1
        for item in calculados
        if (
            item[
                "elegivel_sugestao"
            ]
            and
            item[
                "ultima_contagem"
            ]
            is None
        )
    )

    tendencias_deteriorando = sum(
        1
        for item in calculados
        if _normalizar(
            (
                item.get(
                    "tendencia",
                    {}
                )
                or {}
            ).get(
                "classificacao_tendencia"
            )
        ) == "DETERIORANDO"
    )

    tendencias_recorrentes = sum(
        1
        for item in calculados
        if _normalizar(
            (
                item.get(
                    "tendencia",
                    {}
                )
                or {}
            ).get(
                "classificacao_tendencia"
            )
        ) == "RECORRENTE"
    )

    tendencias_atencao = sum(
        1
        for item in calculados
        if _normalizar(
            (
                item.get(
                    "tendencia",
                    {}
                )
                or {}
            ).get(
                "classificacao_tendencia"
            )
        ) == "ATENCAO"
    )

    tratativas_pendentes = sum(
        1
        for item in calculados
        if bool(
            (
                (
                    item.get(
                        "tendencia",
                        {}
                    )
                    or {}
                ).get(
                    "tratativa",
                    {}
                )
                or {}
            ).get(
                "necessita_tratativa",
                False
            )
        )
    )

    resolucoes_nao_eficazes = sum(
        int(
            (
                (
                    item.get(
                        "tendencia",
                        {}
                    )
                    or {}
                ).get(
                    "eficacia",
                    {}
                )
                or {}
            ).get(
                "nao_eficazes",
                0
            )
            or 0
        )
        for item in calculados
    )

    # ========================================================
    # RETORNO
    # ========================================================

    return {
        "tipo_indicador":
            "PRIORIZACAO_LOCALIZACOES_ROTATIVO",

        "modelo": {
            "versao":
                "1.3",

            "estrategia":
                "RISCO_COBERTURA_E_TENDENCIA_INTEGRADA",

            "pesos": {
                "taxa_divergencia_ajustada":
                    PESO_TAXA_DIVERGENCIA_AJUSTADA,

                "recencia":
                    PESO_RECENCIA,

                "divergencias_consecutivas":
                    PESO_CONSECUTIVAS,

                "magnitude":
                    PESO_MAGNITUDE,

                "nunca_contada":
                    PESO_NUNCA_CONTADA,

                "tendencia_integrada_maxima":
                    PESO_TENDENCIA_MAXIMA,
            },

            "bonus_tendencia": {
                "DETERIORANDO":
                    BONUS_TENDENCIA["DETERIORANDO"],

                "RECORRENTE":
                    BONUS_TENDENCIA["RECORRENTE"],

                "ATENCAO":
                    BONUS_TENDENCIA["ATENCAO"],

                "MELHORANDO":
                    BONUS_TENDENCIA["MELHORANDO"],

                "ESTAVEL":
                    BONUS_TENDENCIA["ESTAVEL"],

                "SEM_HISTORICO":
                    BONUS_TENDENCIA["SEM_HISTORICO"],
            },

            "fontes_integradas": [
                "HISTORICO_LOCALIZACAO",
                "RECORRENCIA_ITEM_LOTE",
                "TRATATIVAS",
                "EFICACIA_RESOLUCOES",
                "TENDENCIA_INTEGRADA",
            ],

            "confianca_historica": {
                "1_contagem":
                    0.35,

                "2_contagens":
                    0.55,

                "3_contagens":
                    0.75,

                "4_contagens":
                    0.90,

                "5_ou_mais":
                    1.0,
            },

            "parametros": {
                "limite_score_risco":
                    limite_score_sugestao,

                "quantidade_sugestoes":
                    quantidade_sugestoes,
            },

            "regra_sugestao": {
                "somente_localizacoes_pendentes":
                    True,

                "score_minimo_obrigatorio":
                    False,

                "prioriza_nunca_contada":
                    True,

                "usa_score_para_ordenacao":
                    True,

                "tendencia_recorrente_forca_tipo_risco":
                    True,

                "evita_dupla_contagem_tratativa_eficacia":
                    True,
            },
        },

        "ciclo": {
            "possui_ciclo_aberto":
                ciclo is not None,

            "id_ciclo":
                (
                    ciclo.ID_Ciclo
                    if ciclo
                    else None
                ),

            "codigo_ciclo":
                (
                    ciclo.CodigoCiclo
                    if ciclo
                    else None
                ),
        },

        "resumo": {
            "localizacoes_analisadas":
                len(
                    calculados
                ),

            "localizacoes_elegiveis_sugestao":
                len(
                    candidatos
                ),

            "localizacoes_sugeridas":
                len(
                    selecionados
                ),

            "sugestoes_por_risco":
                sugestoes_risco,

            "sugestoes_por_cobertura":
                sugestoes_cobertura,

            "nunca_contadas_pendentes":
                nunca_contadas_pendentes,

            "tendencias_deteriorando":
                tendencias_deteriorando,

            "tendencias_recorrentes":
                tendencias_recorrentes,

            "tendencias_atencao":
                tendencias_atencao,

            "tratativas_pendentes":
                tratativas_pendentes,

            "resolucoes_nao_eficazes":
                resolucoes_nao_eficazes,
        },

        "ranking":
            calculados,
    }