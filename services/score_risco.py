from datetime import datetime

from services.historico_divergencias import (
    consultar_historico_divergencias,
)


# ============================================================
# SCORE DE RISCO - V1.1
#
# Ajustes desta versão:
# - confiança histórica conforme tamanho da amostra
# - proteção contra 1/1 = risco histórico máximo
# - magnitude relativa ao saldo esperado
# - manutenção de recorrência e consecutividade como fatores fortes
# - explicação completa dos componentes
# ============================================================


PESOS = {
    "taxa_divergencia_ajustada": 30,
    "divergencias_consecutivas": 25,
    "persistencia": 20,
    "magnitude_relativa": 15,
    "recencia": 10,
}


# ============================================================
# UTILITÁRIOS
# ============================================================

def _txt(valor):
    if valor is None:
        return ""
    return str(valor).strip()


def _num(valor):
    if valor is None:
        return 0.0
    return float(valor)


def _dias_desde(data_evento):
    if data_evento is None:
        return None

    agora = datetime.now()

    if getattr(
        data_evento,
        "tzinfo",
        None
    ) is not None:
        agora = datetime.now(
            tz=data_evento.tzinfo
        )

    diferenca = (
        agora
        -
        data_evento
    )

    return max(
        0,
        diferenca.days
    )


# ============================================================
# CONFIANÇA HISTÓRICA
#
# 1 inventário  = 35%
# 2 inventários = 55%
# 3 inventários = 75%
# 4 inventários = 90%
# 5+            = 100%
#
# A confiança não é um novo peso isolado.
# Ela ajusta o impacto da taxa histórica.
# ============================================================

def _fator_confianca_historica(
    inventarios_validos
):
    total = int(
        inventarios_validos
        or
        0
    )

    if total <= 0:
        return 0.0

    if total == 1:
        return 0.35

    if total == 2:
        return 0.55

    if total == 3:
        return 0.75

    if total == 4:
        return 0.90

    return 1.0


def _classificar_confianca(
    fator
):
    if fator >= 1.0:
        return "ALTA"

    if fator >= 0.75:
        return "BOA"

    if fator >= 0.55:
        return "BAIXA"

    if fator > 0:
        return "MUITO_BAIXA"

    return "SEM_HISTORICO"


# ============================================================
# TAXA DE DIVERGÊNCIA AJUSTADA PELA AMOSTRA
# ============================================================

def _score_taxa_divergencia_ajustada(
    taxa_percentual,
    inventarios_validos
):
    taxa = max(
        0.0,
        min(
            100.0,
            _num(
                taxa_percentual
            )
        )
    )

    confianca = (
        _fator_confianca_historica(
            inventarios_validos
        )
    )

    taxa_ajustada = (
        taxa
        *
        confianca
    )

    score = (
        taxa_ajustada
        /
        100
        *
        PESOS[
            "taxa_divergencia_ajustada"
        ]
    )

    return {
        "score":
            round(
                score,
                2
            ),

        "taxa_original_percentual":
            round(
                taxa,
                2
            ),

        "fator_confianca":
            round(
                confianca,
                2
            ),

        "confianca":
            _classificar_confianca(
                confianca
            ),

        "taxa_ajustada_percentual":
            round(
                taxa_ajustada,
                2
            )
    }


# ============================================================
# DIVERGÊNCIAS CONSECUTIVAS
# ============================================================

def _score_consecutivas(
    consecutivas
):
    consecutivas = int(
        consecutivas
        or
        0
    )

    if consecutivas <= 0:
        fator = 0.0

    elif consecutivas == 1:
        fator = 0.25

    elif consecutivas == 2:
        fator = 0.60

    elif consecutivas == 3:
        fator = 0.85

    else:
        fator = 1.0

    return round(
        fator
        *
        PESOS[
            "divergencias_consecutivas"
        ],
        2
    )


# ============================================================
# PERSISTÊNCIA / RECORRÊNCIA
# ============================================================

def _score_persistencia(
    padrao,
    recorrente
):
    padrao = (
        _txt(
            padrao
        ).upper()
    )

    if padrao in {
        "FALTA_PERSISTENTE",
        "SOBRA_PERSISTENTE",
    }:
        fator = 1.0

    elif padrao in {
        "FALTA_RECORRENTE",
        "SOBRA_RECORRENTE",
        "DIVERGENCIA_OSCILANTE",
    }:
        fator = 0.75

    elif (
        padrao
        ==
        "DIVERGENCIA_ISOLADA"
    ):
        fator = 0.30

    elif recorrente:
        fator = 0.60

    else:
        fator = 0.0

    return round(
        fator
        *
        PESOS[
            "persistencia"
        ],
        2
    )


# ============================================================
# MAGNITUDE RELATIVA
#
# Em vez de olhar apenas "faltaram 3 unidades",
# mede a gravidade em relação ao estoque esperado.
#
# Exemplo:
# estoque esperado = 1
# diferença = -1
# impacto relativo = 100%
#
# Para recorrência, calculamos a média dos impactos relativos
# dos eventos divergentes.
# ============================================================

def _calcular_magnitude_relativa(
    eventos
):
    impactos = []

    for evento in eventos:

        status = _txt(
            evento.get(
                "status"
            )
        ).upper()

        if status == "OK":
            continue

        qtd_estoque = abs(
            _num(
                evento.get(
                    "qtd_estoque"
                )
            )
        )

        diferenca = abs(
            _num(
                evento.get(
                    "diferenca"
                )
            )
        )

        if diferenca <= 0:
            continue

        if qtd_estoque > 0:
            impacto = (
                diferenca
                /
                qtd_estoque
            )

        else:
            # Caso clássico de sobra:
            # estoque esperado = 0
            # contagem física > 0
            #
            # Não existe denominador de estoque.
            # Tratamos como impacto integral.
            impacto = 1.0

        impacto = max(
            0.0,
            min(
                2.0,
                impacto
            )
        )

        impactos.append(
            impacto
        )

    if not impactos:
        return {
            "media_percentual": 0.0,
            "maxima_percentual": 0.0,
            "eventos_divergentes": 0,
        }

    media = (
        sum(
            impactos
        )
        /
        len(
            impactos
        )
    )

    maxima = max(
        impactos
    )

    return {
        "media_percentual":
            round(
                media
                *
                100,
                2
            ),

        "maxima_percentual":
            round(
                maxima
                *
                100,
                2
            ),

        "eventos_divergentes":
            len(
                impactos
            )
    }


def _score_magnitude_relativa(
    eventos
):
    magnitude = (
        _calcular_magnitude_relativa(
            eventos
        )
    )

    media = (
        magnitude[
            "media_percentual"
        ]
    )

    if media <= 0:
        fator = 0.0

    elif media < 5:
        fator = 0.15

    elif media < 15:
        fator = 0.30

    elif media < 30:
        fator = 0.50

    elif media < 60:
        fator = 0.75

    else:
        fator = 1.0

    return {
        "score":
            round(
                fator
                *
                PESOS[
                    "magnitude_relativa"
                ],
                2
            ),

        **magnitude
    }


# ============================================================
# RECÊNCIA
# ============================================================

def _score_recencia(
    ultima_divergencia
):
    dias = _dias_desde(
        ultima_divergencia
    )

    if dias is None:
        fator = 0.0

    elif dias <= 7:
        fator = 1.0

    elif dias <= 30:
        fator = 0.80

    elif dias <= 90:
        fator = 0.55

    elif dias <= 180:
        fator = 0.30

    else:
        fator = 0.10

    return {
        "score":
            round(
                fator
                *
                PESOS[
                    "recencia"
                ],
                2
            ),

        "dias_desde_ultima_divergencia":
            dias
    }


# ============================================================
# CLASSIFICAÇÃO
# ============================================================

def _classificar_score(
    score
):
    score = _num(
        score
    )

    if score >= 75:
        return "CRITICO"

    if score >= 50:
        return "ALTO"

    if score >= 25:
        return "MEDIO"

    return "BAIXO"


# ============================================================
# MOTIVOS
# ============================================================

def _montar_motivos(
    historico,
    analise_taxa,
    analise_magnitude
):
    motivos = []

    taxa = _num(
        historico.get(
            "taxa_divergencia_percentual"
        )
    )

    inventarios = int(
        historico.get(
            "inventarios_validos"
        )
        or
        0
    )

    consecutivas = int(
        historico.get(
            "divergencias_consecutivas"
        )
        or
        0
    )

    padrao = _txt(
        historico.get(
            "padrao"
        )
    )

    ultima_situacao = _txt(
        historico.get(
            "ultima_situacao"
        )
    )

    if taxa > 0:
        motivos.append(
            (
                f"Taxa histórica de divergência de {taxa:g}% "
                f"em {inventarios} inventário"
                f"{'s' if inventarios != 1 else ''}"
            )
        )

    if (
        analise_taxa[
            "fator_confianca"
        ]
        <
        1
    ):
        motivos.append(
            (
                "Confiança histórica "
                f"{analise_taxa['confianca']} "
                f"({analise_taxa['fator_confianca'] * 100:g}%)"
            )
        )

    if consecutivas > 0:
        motivos.append(
            (
                f"{consecutivas} divergência"
                f"{'s' if consecutivas != 1 else ''} "
                "consecutiva"
                f"{'s' if consecutivas != 1 else ''}"
            )
        )

    if padrao and padrao != "SEM_DIVERGENCIA":
        motivos.append(
            f"Padrão {padrao}"
        )

    if (
        analise_magnitude[
            "media_percentual"
        ]
        >
        0
    ):
        motivos.append(
            (
                "Magnitude relativa média das divergências: "
                f"{analise_magnitude['media_percentual']:g}%"
            )
        )

    if (
        ultima_situacao
        and
        ultima_situacao != "OK"
    ):
        motivos.append(
            (
                "Última situação registrada: "
                f"{ultima_situacao}"
            )
        )

    return motivos


# ============================================================
# CALCULAR SCORE DE UMA COMBINAÇÃO
# ============================================================

def _calcular_score_combinacao(
    combinacao
):
    historico = combinacao[
        "historico"
    ]

    eventos = combinacao.get(
        "eventos",
        []
    )

    analise_taxa = (
        _score_taxa_divergencia_ajustada(
            taxa_percentual=historico.get(
                "taxa_divergencia_percentual"
            ),
            inventarios_validos=historico.get(
                "inventarios_validos"
            )
        )
    )

    score_consecutivas = (
        _score_consecutivas(
            historico.get(
                "divergencias_consecutivas"
            )
        )
    )

    score_persistencia = (
        _score_persistencia(
            historico.get(
                "padrao"
            ),
            historico.get(
                "recorrente"
            )
        )
    )

    analise_magnitude = (
        _score_magnitude_relativa(
            eventos
        )
    )

    analise_recencia = (
        _score_recencia(
            historico.get(
                "ultima_divergencia"
            )
        )
    )

    componentes = {
        "taxa_divergencia_ajustada":
            analise_taxa[
                "score"
            ],

        "divergencias_consecutivas":
            score_consecutivas,

        "persistencia":
            score_persistencia,

        "magnitude_relativa":
            analise_magnitude[
                "score"
            ],

        "recencia":
            analise_recencia[
                "score"
            ]
    }

    score = round(
        sum(
            componentes.values()
        ),
        2
    )

    score = max(
        0.0,
        min(
            100.0,
            score
        )
    )

    classificacao = (
        _classificar_score(
            score
        )
    )

    return {
        "cliente_id":
            combinacao.get(
                "cliente_id"
            ),

        "cliente":
            combinacao.get(
                "cliente"
            ),

        "armazem":
            combinacao.get(
                "armazem"
            ),

        "localizacao":
            combinacao.get(
                "localizacao"
            ),

        "codigo":
            combinacao.get(
                "codigo"
            ),

        "lote":
            combinacao.get(
                "lote"
            ),

        "descricao":
            combinacao.get(
                "descricao"
            ),

        "unidade":
            combinacao.get(
                "unidade"
            ),

        "categoria":
            combinacao.get(
                "categoria"
            ),

        "score_risco":
            score,

        "classificacao":
            classificacao,

        "componentes_score":
            componentes,

        "analise_confianca": {
            "inventarios_validos":
                historico.get(
                    "inventarios_validos"
                ),

            "taxa_divergencia_original_percentual":
                analise_taxa[
                    "taxa_original_percentual"
                ],

            "fator_confianca":
                analise_taxa[
                    "fator_confianca"
                ],

            "confianca":
                analise_taxa[
                    "confianca"
                ],

            "taxa_divergencia_ajustada_percentual":
                analise_taxa[
                    "taxa_ajustada_percentual"
                ]
        },

        "analise_magnitude": {
            "media_percentual":
                analise_magnitude[
                    "media_percentual"
                ],

            "maxima_percentual":
                analise_magnitude[
                    "maxima_percentual"
                ],

            "eventos_divergentes":
                analise_magnitude[
                    "eventos_divergentes"
                ]
        },

        "analise_recencia": {
            "dias_desde_ultima_divergencia":
                analise_recencia[
                    "dias_desde_ultima_divergencia"
                ]
        },

        "historico": {
            "inventarios_validos":
                historico.get(
                    "inventarios_validos"
                ),

            "ok":
                historico.get(
                    "ok"
                ),

            "faltas":
                historico.get(
                    "faltas"
                ),

            "sobras":
                historico.get(
                    "sobras"
                ),

            "divergencias":
                historico.get(
                    "divergencias"
                ),

            "taxa_divergencia_percentual":
                historico.get(
                    "taxa_divergencia_percentual"
                ),

            "divergencias_consecutivas":
                historico.get(
                    "divergencias_consecutivas"
                ),

            "ultima_divergencia":
                historico.get(
                    "ultima_divergencia"
                ),

            "ultima_situacao":
                historico.get(
                    "ultima_situacao"
                ),

            "direcao_predominante":
                historico.get(
                    "direcao_predominante"
                ),

            "padrao":
                historico.get(
                    "padrao"
                ),

            "recorrente":
                historico.get(
                    "recorrente"
                )
        },

        "motivos":
            _montar_motivos(
                historico=historico,
                analise_taxa=analise_taxa,
                analise_magnitude=(
                    analise_magnitude
                )
            )
    }


# ============================================================
# CONSULTAR PRIORIZAÇÃO
# ============================================================

def consultar_priorizacao_risco(
    cursor,
    cliente_id: int | None = None,
    armazem: str | None = None,
    localizacao: str | None = None,
    codigo: str | None = None,
    lote: str | None = None,
    classificacao: str | None = None,
    somente_prioritarios: bool = False,
    limite: int = 100
):
    resultado_historico = (
        consultar_historico_divergencias(
            cursor=cursor,
            cliente_id=cliente_id,
            armazem=armazem,
            localizacao=localizacao,
            codigo=codigo,
            lote=lote,
            tipo_inventario=None,
            data_inicio=None,
            data_fim=None,
            somente_recorrentes=False
        )
    )

    detalhes = [
        _calcular_score_combinacao(
            item
        )
        for item in resultado_historico.get(
            "combinacoes",
            []
        )
    ]

    if classificacao:
        classificacao = (
            _txt(
                classificacao
            ).upper()
        )

        detalhes = [
            item
            for item in detalhes
            if item[
                "classificacao"
            ]
            ==
            classificacao
        ]

    if somente_prioritarios:
        detalhes = [
            item
            for item in detalhes
            if item[
                "classificacao"
            ] in {
                "ALTO",
                "CRITICO",
            }
        ]

    detalhes.sort(
        key=lambda item: (
            -item[
                "score_risco"
            ],
            item[
                "armazem"
            ]
            or
            "",
            item[
                "localizacao"
            ]
            or
            "",
            item[
                "codigo"
            ]
            or
            "",
            item[
                "lote"
            ]
            or
            ""
        )
    )

    for indice, item in enumerate(
        detalhes,
        start=1
    ):
        item[
            "prioridade_contagem"
        ] = indice

    total_antes_limite = len(
        detalhes
    )

    detalhes = detalhes[
        :limite
    ]

    contagem_classificacoes = {
        "BAIXO": 0,
        "MEDIO": 0,
        "ALTO": 0,
        "CRITICO": 0,
    }

    for item in detalhes:
        contagem_classificacoes[
            item[
                "classificacao"
            ]
        ] += 1

    score_medio = (
        round(
            sum(
                item[
                    "score_risco"
                ]
                for item in detalhes
            )
            /
            len(
                detalhes
            ),
            2
        )
        if detalhes
        else 0
    )

    return {
        "tipo_indicador":
            "SCORE_RISCO_PRIORIZACAO",

        "pesquisa": {
            "cliente_id":
                cliente_id,

            "armazem":
                armazem,

            "localizacao":
                localizacao,

            "codigo":
                codigo,

            "lote":
                lote,

            "classificacao":
                classificacao,

            "somente_prioritarios":
                somente_prioritarios,

            "limite":
                limite
        },

        "modelo": {
            "versao":
                "1.1",

            "score_minimo":
                0,

            "score_maximo":
                100,

            "faixas": {
                "BAIXO":
                    "0-24.99",

                "MEDIO":
                    "25-49.99",

                "ALTO":
                    "50-74.99",

                "CRITICO":
                    "75-100"
            },

            "pesos":
                PESOS,

            "confianca_historica": {
                "1_inventario":
                    0.35,

                "2_inventarios":
                    0.55,

                "3_inventarios":
                    0.75,

                "4_inventarios":
                    0.90,

                "5_ou_mais":
                    1.0
            }
        },

        "resumo": {
            "combinacoes_elegiveis":
                total_antes_limite,

            "retornadas":
                len(
                    detalhes
                ),

            "baixo":
                contagem_classificacoes[
                    "BAIXO"
                ],

            "medio":
                contagem_classificacoes[
                    "MEDIO"
                ],

            "alto":
                contagem_classificacoes[
                    "ALTO"
                ],

            "critico":
                contagem_classificacoes[
                    "CRITICO"
                ],

            "score_medio":
                score_medio
        },

        "ranking_prioridade":
            detalhes
    }
