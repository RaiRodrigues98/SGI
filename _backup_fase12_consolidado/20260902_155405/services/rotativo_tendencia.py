from domain.exceptions import BusinessRuleViolation
# ============================================================
# TENDÊNCIA INTEGRADA DO INVENTÁRIO ROTATIVO
#
# Fonte central:
# services.rotativo_contexto.py
#
# Objetivos:
# - Detectar estabilidade
# - Detectar atenção
# - Detectar recorrência
# - Detectar deterioração
# - Detectar melhora
# - Considerar tratativas
# - Considerar eficácia das resoluções
# ============================================================

from services.rotativo_contexto import (
    montar_contexto_localizacao_rotativo,
)


# ============================================================
# UTILITÁRIOS
# ============================================================

def _txt(valor):
    if valor is None:
        return ""

    return str(valor).strip()


def _normalizar(valor):
    return _txt(valor).upper()


def _percentual(parte, total):

    parte = int(
        parte
        or 0
    )

    total = int(
        total
        or 0
    )

    if total <= 0:
        return 0.0

    return round(
        parte
        /
        total
        *
        100,
        2
    )


# ============================================================
# BUSCAR CICLO ABERTO
# ============================================================

def _buscar_ciclo_aberto(
    cursor,
    cliente_id: int,
    armazem: str
):

    cursor.execute(
        """
        SELECT TOP 1
            ID_Ciclo,
            CodigoCiclo,
            ClienteId,
            cArmazem,
            Status,
            DataInicio,
            DataFimPrevista

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
            armazem,
        )
    )

    return cursor.fetchone()


# ============================================================
# BUSCAR LOCALIZAÇÕES DO CICLO
# ============================================================

def _buscar_localizacoes_ciclo(
    cursor,
    id_ciclo: int
):

    cursor.execute(
        """
        SELECT
            ID_CicloLocalizacao,
            ID_RotativoLocalizacao,
            Localizacao,
            Status,
            Prioridade,
            ScoreRiscoEntrada,
            ClassificacaoRiscoEntrada,
            TipoSugestao

        FROM dbo.CicloRotativoLocalizacoes

        WHERE
            ID_Ciclo = ?

        ORDER BY
            ISNULL(
                Prioridade,
                999999
            ),
            Localizacao
        """,
        (
            id_ciclo,
        )
    )

    return cursor.fetchall()


# ============================================================
# CALCULAR TAXA DE DIVERGÊNCIA DE UMA LISTA DE CONTAGENS
# ============================================================

def _taxa_divergencia_contagens(
    contagens
):

    total = len(
        contagens
    )

    if total == 0:
        return 0.0

    divergencias = sum(
        1
        for item in contagens
        if bool(
            item.get(
                "possui_divergencia"
            )
        )
    )

    return _percentual(
        divergencias,
        total
    )


# ============================================================
# DIVIDIR HISTÓRICO ENTRE ANTIGO E RECENTE
# ============================================================

def _comparar_historico(
    contagens
):

    if not contagens:

        return {
            "taxa_anterior":
                0.0,

            "taxa_recente":
                0.0,

            "variacao":
                0.0,

            "possui_amostra_comparavel":
                False,
        }

    # O contexto devolve o histórico do mais recente
    # para o mais antigo.
    cronologico = list(
        reversed(
            contagens
        )
    )

    total = len(
        cronologico
    )

    if total < 3:

        taxa_total = (
            _taxa_divergencia_contagens(
                cronologico
            )
        )

        return {
            "taxa_anterior":
                taxa_total,

            "taxa_recente":
                taxa_total,

            "variacao":
                0.0,

            "possui_amostra_comparavel":
                False,
        }

    metade = max(
        1,
        total // 2
    )

    anterior = (
        cronologico[
            :metade
        ]
    )

    recente = (
        cronologico[
            metade:
        ]
    )

    if not recente:

        recente = anterior

    taxa_anterior = (
        _taxa_divergencia_contagens(
            anterior
        )
    )

    taxa_recente = (
        _taxa_divergencia_contagens(
            recente
        )
    )

    return {
        "taxa_anterior":
            taxa_anterior,

        "taxa_recente":
            taxa_recente,

        "variacao":
            round(
                taxa_recente
                -
                taxa_anterior,
                2
            ),

        "possui_amostra_comparavel":
            True,
    }


# ============================================================
# EXTRAIR EFICÁCIA CONSOLIDADA
# ============================================================

def _resumir_eficacia(
    contexto
):

    resolucoes = (
        contexto
        .get(
            "eficacia",
            {}
        )
        .get(
            "resolucoes",
            []
        )
        or []
    )

    eficazes = 0
    nao_eficazes = 0
    sem_evidencia = 0

    ultima_classificacao = None
    ultima_resolucao = None

    for resolucao in resolucoes:

        eficacia = (
            resolucao.get(
                "eficacia"
            )
            or {}
        )

        classificacao = (
            eficacia.get(
                "classificacao"
            )
        )

        if classificacao == "EFICAZ":
            eficazes += 1

        elif classificacao == "NAO_EFICAZ":
            nao_eficazes += 1

        elif (
            classificacao
            ==
            "AINDA_SEM_EVIDENCIA"
        ):
            sem_evidencia += 1

        data_resolucao = (
            resolucao.get(
                "data_resolucao"
            )
        )

        if (
            ultima_resolucao is None
            or (
                data_resolucao is not None
                and
                (
                    ultima_resolucao.get(
                        "data_resolucao"
                    )
                    is None
                    or
                    data_resolucao
                    >
                    ultima_resolucao.get(
                        "data_resolucao"
                    )
                )
            )
        ):

            ultima_resolucao = (
                resolucao
            )

            ultima_classificacao = (
                classificacao
            )

    return {
        "resolucoes_avaliadas":
            len(
                resolucoes
            ),

        "eficazes":
            eficazes,

        "nao_eficazes":
            nao_eficazes,

        "ainda_sem_evidencia":
            sem_evidencia,

        "ultima_classificacao":
            ultima_classificacao,

        "ultima_resolucao":
            ultima_resolucao,
    }


# ============================================================
# CLASSIFICAR NÍVEL DE EVIDÊNCIA
# ============================================================

def _classificar_evidencia(
    contagens_historicas: int,
    ocorrencias: int,
    recorrencia_item_lote: bool
):

    if (
        contagens_historicas >= 5
        or
        ocorrencias >= 3
    ):
        return "ALTA"

    if (
        contagens_historicas >= 2
        or
        recorrencia_item_lote
        or
        ocorrencias >= 2
    ):
        return "MEDIA"

    if (
        contagens_historicas >= 1
        or
        ocorrencias >= 1
    ):
        return "BAIXA"

    return "SEM_EVIDENCIA"


# ============================================================
# CLASSIFICAR TENDÊNCIA INTEGRADA
# ============================================================

def _classificar_tendencia_integrada(
    contexto
):

    historico = (
        contexto.get(
            "historico",
            {}
        )
        or {}
    )

    resumo_historico = (
        historico.get(
            "resumo",
            {}
        )
        or {}
    )

    contagens = (
        historico.get(
            "contagens",
            []
        )
        or []
    )

    divergencias = (
        contexto.get(
            "divergencias",
            {}
        )
        or {}
    )

    eficacia = (
        _resumir_eficacia(
            contexto
        )
    )

    comparacao = (
        _comparar_historico(
            contagens
        )
    )

    total_contagens = int(
        resumo_historico.get(
            "contagens",
            0
        )
        or 0
    )

    contagens_divergentes = int(
        resumo_historico.get(
            "contagens_com_divergencia",
            0
        )
        or 0
    )

    taxa_historica = float(
        resumo_historico.get(
            "taxa_divergencia_percentual",
            0
        )
        or 0
    )

    consecutivas = int(
        resumo_historico.get(
            "divergencias_consecutivas",
            0
        )
        or 0
    )

    total_ocorrencias = int(
        divergencias.get(
            "ocorrencias",
            0
        )
        or 0
    )

    ocorrencias_pendentes = int(
        divergencias.get(
            "ocorrencias_pendentes",
            0
        )
        or 0
    )

    grupos_recorrentes = int(
        divergencias.get(
            "grupos_recorrentes",
            0
        )
        or 0
    )

    possui_recorrencia = bool(
        divergencias.get(
            "possui_recorrencia",
            False
        )
    )

    necessita_tratativa = bool(
        divergencias.get(
            "necessita_tratativa",
            False
        )
    )

    motivos = []

    # ========================================================
    # SEM HISTÓRICO
    # ========================================================

    if (
        total_contagens == 0
        and
        total_ocorrencias == 0
    ):

        return {
            "classificacao":
                "SEM_HISTORICO",

            "direcao":
                "SEM_DADOS",

            "nivel_evidencia":
                "SEM_EVIDENCIA",

            "motivos": [
                "Localização sem histórico de contagem "
                "e sem ocorrência de divergência."
            ],

            "fatores": {
                "contagens_historicas":
                    0,

                "divergencias_consecutivas":
                    0,

                "recorrencia_item_lote":
                    False,

                "grupos_recorrentes":
                    0,

                "tratativa_pendente":
                    False,

                "ocorrencias_pendentes":
                    0,

                "resolucoes_nao_eficazes":
                    0,

                "resolucoes_sem_evidencia":
                    0,
            },

            "comparacao_historica":
                comparacao,

            "eficacia":
                eficacia,
        }

    nivel_evidencia = (
        _classificar_evidencia(
            contagens_historicas=(
                total_contagens
            ),
            ocorrencias=(
                total_ocorrencias
            ),
            recorrencia_item_lote=(
                possui_recorrencia
            ),
        )
    )

    # ========================================================
    # 1. DETERIORANDO
    #
    # Piora estatística recente ou resolução não eficaz
    # acompanhada de nova divergência.
    # ========================================================

    deteriorando_por_historico = (
        comparacao[
            "possui_amostra_comparavel"
        ]
        and
        comparacao[
            "variacao"
        ]
        >= 20
        and
        comparacao[
            "taxa_recente"
        ]
        > comparacao[
            "taxa_anterior"
        ]
    )

    deteriorando_por_eficacia = (
        eficacia[
            "nao_eficazes"
        ]
        > 0
    )

    if (
        deteriorando_por_historico
        or
        deteriorando_por_eficacia
    ):

        if deteriorando_por_historico:

            motivos.append(
                "A taxa recente de divergência aumentou "
                "em relação ao histórico anterior."
            )

        if deteriorando_por_eficacia:

            motivos.append(
                "Existe resolução classificada como não eficaz."
            )

        if possui_recorrencia:

            motivos.append(
                "Existe recorrência para a mesma combinação "
                "Localização + Código + Lote."
            )

        if consecutivas > 0:

            motivos.append(
                f"{consecutivas} divergência(s) consecutiva(s)."
            )

        if necessita_tratativa:

            motivos.append(
                "Existem divergências ainda com tratativa pendente."
            )

        return {
            "classificacao":
                "DETERIORANDO",

            "direcao":
                "PIORA",

            "nivel_evidencia":
                nivel_evidencia,

            "motivos":
                motivos,

            "fatores": {
                "contagens_historicas":
                    total_contagens,

                "taxa_divergencia_historica":
                    taxa_historica,

                "divergencias_consecutivas":
                    consecutivas,

                "recorrencia_item_lote":
                    possui_recorrencia,

                "grupos_recorrentes":
                    grupos_recorrentes,

                "tratativa_pendente":
                    necessita_tratativa,

                "ocorrencias_pendentes":
                    ocorrencias_pendentes,

                "resolucoes_nao_eficazes":
                    eficacia[
                        "nao_eficazes"
                    ],

                "resolucoes_sem_evidencia":
                    eficacia[
                        "ainda_sem_evidencia"
                    ],
            },

            "comparacao_historica":
                comparacao,

            "eficacia":
                eficacia,
        }

    # ========================================================
    # 2. RECORRENTE
    #
    # Recorrência operacional por item/lote é evidência
    # suficiente mesmo que o histórico consolidado da
    # localização ainda tenha poucas contagens.
    # ========================================================

    if (
        possui_recorrencia
        or
        consecutivas >= 2
        or
        grupos_recorrentes > 0
    ):

        if possui_recorrencia:

            motivos.append(
                "A mesma combinação Localização + Código + Lote "
                "apresentou divergência mais de uma vez."
            )

        if grupos_recorrentes > 0:

            motivos.append(
                f"{grupos_recorrentes} grupo(s) recorrente(s) "
                "de divergência identificado(s)."
            )

        if consecutivas >= 2:

            motivos.append(
                f"{consecutivas} divergências consecutivas "
                "no histórico da localização."
            )

        if necessita_tratativa:

            motivos.append(
                "Existe tratativa de divergência ainda pendente."
            )

        if (
            eficacia[
                "ainda_sem_evidencia"
            ]
            > 0
        ):

            motivos.append(
                "Existe resolução ainda sem evidência posterior "
                "suficiente para validar sua eficácia."
            )

        return {
            "classificacao":
                "RECORRENTE",

            "direcao":
                "RECORRENCIA",

            "nivel_evidencia":
                nivel_evidencia,

            "motivos":
                motivos,

            "fatores": {
                "contagens_historicas":
                    total_contagens,

                "taxa_divergencia_historica":
                    taxa_historica,

                "divergencias_consecutivas":
                    consecutivas,

                "recorrencia_item_lote":
                    possui_recorrencia,

                "grupos_recorrentes":
                    grupos_recorrentes,

                "tratativa_pendente":
                    necessita_tratativa,

                "ocorrencias_pendentes":
                    ocorrencias_pendentes,

                "resolucoes_nao_eficazes":
                    eficacia[
                        "nao_eficazes"
                    ],

                "resolucoes_sem_evidencia":
                    eficacia[
                        "ainda_sem_evidencia"
                    ],
            },

            "comparacao_historica":
                comparacao,

            "eficacia":
                eficacia,
        }

    # ========================================================
    # 3. MELHORANDO
    # ========================================================

    melhorando_por_historico = (
        comparacao[
            "possui_amostra_comparavel"
        ]
        and
        comparacao[
            "variacao"
        ]
        <= -20
        and
        comparacao[
            "taxa_recente"
        ]
        < comparacao[
            "taxa_anterior"
        ]
    )

    melhorando_por_eficacia = (
        eficacia[
            "eficazes"
        ]
        > 0
        and
        eficacia[
            "nao_eficazes"
        ]
        == 0
        and
        consecutivas == 0
    )

    if (
        melhorando_por_historico
        or
        melhorando_por_eficacia
    ):

        if melhorando_por_historico:

            motivos.append(
                "A taxa recente de divergência caiu "
                "em relação ao histórico anterior."
            )

        if melhorando_por_eficacia:

            motivos.append(
                "Existe resolução com evidência posterior "
                "classificada como eficaz."
            )

        if consecutivas == 0:

            motivos.append(
                "A sequência atual não apresenta divergências consecutivas."
            )

        if necessita_tratativa:

            motivos.append(
                "Apesar da melhora, ainda existe tratativa pendente."
            )

        return {
            "classificacao":
                "MELHORANDO",

            "direcao":
                "MELHORA",

            "nivel_evidencia":
                nivel_evidencia,

            "motivos":
                motivos,

            "fatores": {
                "contagens_historicas":
                    total_contagens,

                "taxa_divergencia_historica":
                    taxa_historica,

                "divergencias_consecutivas":
                    consecutivas,

                "recorrencia_item_lote":
                    possui_recorrencia,

                "grupos_recorrentes":
                    grupos_recorrentes,

                "tratativa_pendente":
                    necessita_tratativa,

                "ocorrencias_pendentes":
                    ocorrencias_pendentes,

                "resolucoes_eficazes":
                    eficacia[
                        "eficazes"
                    ],

                "resolucoes_sem_evidencia":
                    eficacia[
                        "ainda_sem_evidencia"
                    ],
            },

            "comparacao_historica":
                comparacao,

            "eficacia":
                eficacia,
        }

    # ========================================================
    # 4. ATENÇÃO
    # ========================================================

    if (
        contagens_divergentes > 0
        or
        total_ocorrencias > 0
        or
        necessita_tratativa
    ):

        if contagens_divergentes > 0:

            motivos.append(
                "Existe divergência registrada no histórico "
                "da localização."
            )

        if consecutivas == 1:

            motivos.append(
                "A última contagem apresentou divergência."
            )

        if necessita_tratativa:

            motivos.append(
                "Existe tratativa de divergência pendente."
            )

        if (
            eficacia[
                "ainda_sem_evidencia"
            ]
            > 0
        ):

            motivos.append(
                "Existe resolução ainda sem evidência "
                "posterior de eficácia."
            )

        return {
            "classificacao":
                "ATENCAO",

            "direcao":
                "MONITORAR",

            "nivel_evidencia":
                nivel_evidencia,

            "motivos":
                motivos,

            "fatores": {
                "contagens_historicas":
                    total_contagens,

                "taxa_divergencia_historica":
                    taxa_historica,

                "divergencias_consecutivas":
                    consecutivas,

                "recorrencia_item_lote":
                    possui_recorrencia,

                "grupos_recorrentes":
                    grupos_recorrentes,

                "tratativa_pendente":
                    necessita_tratativa,

                "ocorrencias_pendentes":
                    ocorrencias_pendentes,

                "resolucoes_nao_eficazes":
                    eficacia[
                        "nao_eficazes"
                    ],

                "resolucoes_sem_evidencia":
                    eficacia[
                        "ainda_sem_evidencia"
                    ],
            },

            "comparacao_historica":
                comparacao,

            "eficacia":
                eficacia,
        }

    # ========================================================
    # 5. ESTÁVEL
    # ========================================================

    motivos.append(
        "Não foram identificadas divergências relevantes "
        "no histórico analisado."
    )

    if (
        eficacia[
            "eficazes"
        ]
        > 0
    ):

        motivos.append(
            "Existe resolução anterior com evidência de eficácia."
        )

    return {
        "classificacao":
            "ESTAVEL",

        "direcao":
            "ESTAVEL",

        "nivel_evidencia":
            nivel_evidencia,

        "motivos":
            motivos,

        "fatores": {
            "contagens_historicas":
                total_contagens,

            "taxa_divergencia_historica":
                taxa_historica,

            "divergencias_consecutivas":
                consecutivas,

            "recorrencia_item_lote":
                possui_recorrencia,

            "grupos_recorrentes":
                grupos_recorrentes,

            "tratativa_pendente":
                necessita_tratativa,

            "ocorrencias_pendentes":
                ocorrencias_pendentes,

            "resolucoes_eficazes":
                eficacia[
                    "eficazes"
                ],

            "resolucoes_nao_eficazes":
                eficacia[
                    "nao_eficazes"
                ],

            "resolucoes_sem_evidencia":
                eficacia[
                    "ainda_sem_evidencia"
                ],
        },

        "comparacao_historica":
            comparacao,

        "eficacia":
            eficacia,
    }


# ============================================================
# CONSULTAR TENDÊNCIAS DO ROTATIVO
# ============================================================

def consultar_tendencias_rotativo(
    cursor,
    cliente_id: int,
    armazem: str,
    limite_historico: int = 6,
    somente_alertas: bool = False
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

    if limite_historico < 1:

        raise BusinessRuleViolation(
            "limite_historico deve ser maior que zero."
        )

    if limite_historico > 100:

        raise BusinessRuleViolation(
            "limite_historico máximo permitido é 100."
        )

    # ========================================================
    # CICLO ABERTO
    # ========================================================

    ciclo = (
        _buscar_ciclo_aberto(
            cursor=cursor,
            cliente_id=cliente_id,
            armazem=armazem,
        )
    )

    if not ciclo:

        return {
            "possui_ciclo_aberto":
                False,

            "ciclo":
                None,

            "resumo": {
                "localizacoes_analisadas":
                    0,

                "sem_historico":
                    0,

                "estaveis":
                    0,

                "atencao":
                    0,

                "recorrentes":
                    0,

                "deteriorando":
                    0,

                "melhorando":
                    0,

                "tratativas_pendentes":
                    0,

                "resolucoes_nao_eficazes":
                    0,
            },

            "tendencias":
                [],
        }

    # ========================================================
    # LOCALIZAÇÕES DO CICLO
    # ========================================================

    localizacoes = (
        _buscar_localizacoes_ciclo(
            cursor=cursor,
            id_ciclo=ciclo.ID_Ciclo,
        )
    )

    tendencias = []

    # ========================================================
    # ANALISAR CADA LOCALIZAÇÃO
    # ========================================================

    for linha in localizacoes:

        contexto = (
            montar_contexto_localizacao_rotativo(
                cursor=cursor,
                cliente_id=cliente_id,
                armazem=armazem,
                localizacao=linha.Localizacao,
                limite_historico=limite_historico,
            )
        )

        analise = (
            _classificar_tendencia_integrada(
                contexto
            )
        )

        resumo_historico = (
            contexto
            .get(
                "historico",
                {}
            )
            .get(
                "resumo",
                {}
            )
            or {}
        )

        divergencias = (
            contexto.get(
                "divergencias",
                {}
            )
            or {}
        )

        item = {
            "id_ciclo_localizacao":
                linha.ID_CicloLocalizacao,

            "id_rotativo_localizacao":
                linha.ID_RotativoLocalizacao,

            "localizacao":
                linha.Localizacao,

            "status_ciclo":
                linha.Status,

            "prioridade":
                linha.Prioridade,

            "score_risco":
                (
                    float(
                        linha.ScoreRiscoEntrada
                    )
                    if linha.ScoreRiscoEntrada
                    is not None
                    else None
                ),

            "classificacao_risco":
                linha.ClassificacaoRiscoEntrada,

            "tipo_sugestao":
                linha.TipoSugestao,

            "ultima_contagem":
                resumo_historico.get(
                    "ultima_contagem"
                ),

            "classificacao_tendencia":
                analise[
                    "classificacao"
                ],

            "direcao":
                analise[
                    "direcao"
                ],

            "nivel_evidencia":
                analise[
                    "nivel_evidencia"
                ],

            "historico": {
                "contagens_analisadas":
                    int(
                        resumo_historico.get(
                            "contagens",
                            0
                        )
                        or 0
                    ),

                "contagens_com_divergencia":
                    int(
                        resumo_historico.get(
                            "contagens_com_divergencia",
                            0
                        )
                        or 0
                    ),

                "taxa_divergencia_percentual":
                    float(
                        resumo_historico.get(
                            "taxa_divergencia_percentual",
                            0
                        )
                        or 0
                    ),

                "divergencias_consecutivas":
                    int(
                        resumo_historico.get(
                            "divergencias_consecutivas",
                            0
                        )
                        or 0
                    ),

                "ultima_divergencia":
                    resumo_historico.get(
                        "ultima_divergencia"
                    ),

                "taxa_divergencia_anterior_percentual":
                    analise[
                        "comparacao_historica"
                    ][
                        "taxa_anterior"
                    ],

                "taxa_divergencia_recente_percentual":
                    analise[
                        "comparacao_historica"
                    ][
                        "taxa_recente"
                    ],

                "variacao_taxa_percentual":
                    analise[
                        "comparacao_historica"
                    ][
                        "variacao"
                    ],
            },

            "recorrencia": {
                "possui_recorrencia_item_lote":
                    bool(
                        divergencias.get(
                            "possui_recorrencia",
                            False
                        )
                    ),

                "grupos_recorrentes":
                    int(
                        divergencias.get(
                            "grupos_recorrentes",
                            0
                        )
                        or 0
                    ),

                "grupos_divergencia":
                    int(
                        divergencias.get(
                            "grupos_divergencia",
                            0
                        )
                        or 0
                    ),
            },

            "tratativa": {
                "necessita_tratativa":
                    bool(
                        divergencias.get(
                            "necessita_tratativa",
                            False
                        )
                    ),

                "ocorrencias_pendentes":
                    int(
                        divergencias.get(
                            "ocorrencias_pendentes",
                            0
                        )
                        or 0
                    ),

                "ocorrencias_resolvidas":
                    int(
                        divergencias.get(
                            "ocorrencias_resolvidas",
                            0
                        )
                        or 0
                    ),

                "grupos_pendentes":
                    int(
                        divergencias.get(
                            "grupos_pendentes",
                            0
                        )
                        or 0
                    ),
            },

            "eficacia":
                analise[
                    "eficacia"
                ],

            "fatores":
                analise[
                    "fatores"
                ],

            "motivos":
                analise[
                    "motivos"
                ],
        }

        # ----------------------------------------------------
        # SOMENTE ALERTAS
        # ----------------------------------------------------

        if somente_alertas:

            if (
                item[
                    "classificacao_tendencia"
                ]
                not in (
                    "ATENCAO",
                    "RECORRENTE",
                    "DETERIORANDO",
                )
            ):
                continue

        tendencias.append(
            item
        )

    # ========================================================
    # ORDENAÇÃO
    # ========================================================

    ordem = {
        "DETERIORANDO":
            1,

        "RECORRENTE":
            2,

        "ATENCAO":
            3,

        "MELHORANDO":
            4,

        "ESTAVEL":
            5,

        "SEM_HISTORICO":
            6,
    }

    tendencias.sort(
        key=lambda item: (
            ordem.get(
                item[
                    "classificacao_tendencia"
                ],
                99
            ),

            0
            if (
                item[
                    "tratativa"
                ][
                    "necessita_tratativa"
                ]
            )
            else 1,

            item[
                "prioridade"
            ]
            if item[
                "prioridade"
            ] is not None
            else 999999,

            -float(
                item[
                    "score_risco"
                ]
                or 0
            ),

            item[
                "localizacao"
            ],
        )
    )

    # ========================================================
    # RESUMO
    # ========================================================

    resumo = {
        "localizacoes_analisadas":
            len(
                tendencias
            ),

        "sem_historico":
            sum(
                1
                for item in tendencias
                if item[
                    "classificacao_tendencia"
                ]
                ==
                "SEM_HISTORICO"
            ),

        "estaveis":
            sum(
                1
                for item in tendencias
                if item[
                    "classificacao_tendencia"
                ]
                ==
                "ESTAVEL"
            ),

        "atencao":
            sum(
                1
                for item in tendencias
                if item[
                    "classificacao_tendencia"
                ]
                ==
                "ATENCAO"
            ),

        "recorrentes":
            sum(
                1
                for item in tendencias
                if item[
                    "classificacao_tendencia"
                ]
                ==
                "RECORRENTE"
            ),

        "deteriorando":
            sum(
                1
                for item in tendencias
                if item[
                    "classificacao_tendencia"
                ]
                ==
                "DETERIORANDO"
            ),

        "melhorando":
            sum(
                1
                for item in tendencias
                if item[
                    "classificacao_tendencia"
                ]
                ==
                "MELHORANDO"
            ),

        "tratativas_pendentes":
            sum(
                1
                for item in tendencias
                if item[
                    "tratativa"
                ][
                    "necessita_tratativa"
                ]
            ),

        "localizacoes_com_recorrencia_item_lote":
            sum(
                1
                for item in tendencias
                if item[
                    "recorrencia"
                ][
                    "possui_recorrencia_item_lote"
                ]
            ),

        "resolucoes_nao_eficazes":
            sum(
                int(
                    item[
                        "eficacia"
                    ].get(
                        "nao_eficazes",
                        0
                    )
                    or 0
                )
                for item in tendencias
            ),

        "resolucoes_sem_evidencia":
            sum(
                int(
                    item[
                        "eficacia"
                    ].get(
                        "ainda_sem_evidencia",
                        0
                    )
                    or 0
                )
                for item in tendencias
            ),
    }

    resumo[
        "alertas"
    ] = (
        resumo[
            "atencao"
        ]
        +
        resumo[
            "recorrentes"
        ]
        +
        resumo[
            "deteriorando"
        ]
    )

    # ========================================================
    # RETORNO
    # ========================================================

    return {
        "possui_ciclo_aberto":
            True,

        "modelo": {
            "versao":
                "2.0",

            "estrategia":
                "TENDENCIA_INTEGRADA",

            "fontes": [
                "HISTORICO_LOCALIZACAO",
                "RECORRENCIA_ITEM_LOTE",
                "TRATATIVAS",
                "EFICACIA_RESOLUCOES",
            ],

            "ordem_classificacao": [
                "DETERIORANDO",
                "RECORRENTE",
                "ATENCAO",
                "MELHORANDO",
                "ESTAVEL",
                "SEM_HISTORICO",
            ],
        },

        "pesquisa": {
            "cliente_id":
                cliente_id,

            "armazem":
                armazem,

            "limite_historico":
                limite_historico,

            "somente_alertas":
                somente_alertas,
        },

        "ciclo": {
            "id_ciclo":
                ciclo.ID_Ciclo,

            "codigo_ciclo":
                ciclo.CodigoCiclo,

            "cliente_id":
                ciclo.ClienteId,

            "armazem":
                ciclo.cArmazem,

            "status":
                ciclo.Status,

            "data_inicio":
                ciclo.DataInicio,

            "data_fim_prevista":
                ciclo.DataFimPrevista,
        },

        "resumo":
            resumo,

        "tendencias":
            tendencias,
    }