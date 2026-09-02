from domain.exceptions import BusinessRuleViolation
# ============================================================
# ORQUESTRADOR DA INTELIGÊNCIA DO INVENTÁRIO ROTATIVO
#
# Objetivo:
#
# Centralizar a atualização dos módulos inteligentes após
# eventos operacionais do inventário rotativo.
#
# Fluxo:
#
# Evento operacional
#       ↓
# Banco já atualizado / commit realizado
#       ↓
# Tendência integrada
#       ↓
# Priorização V1.3
#       ↓
# Contexto atualizado
#       ↓
# Painel gerencial atualizado
#
#
# IMPORTANTE:
#
# Este service deve ser executado APÓS o commit da operação
# principal.
#
# Exemplo:
#
# concluir localização
#     commit
#     ↓
# executar_orquestracao_rotativo()
#
# resolver divergência
#     commit
#     ↓
# executar_orquestracao_rotativo()
# ============================================================


from datetime import datetime


from services.rotativo_priorizacao import (
    recalcular_priorizacao_rotativo,
)

from services.rotativo_tendencia import (
    consultar_tendencias_rotativo,
)

from services.rotativo_painel import (
    consultar_painel_rotativo,
)

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

    return _txt(
        valor
    ).upper()


# ============================================================
# EVENTOS SUPORTADOS
# ============================================================

EVENTOS_SUPORTADOS = (
    "CONCLUSAO_LOCALIZACAO",
    "JUSTIFICATIVA_DIVERGENCIA",
    "RESOLUCAO_DIVERGENCIA",
    "RECONTAGEM",
    "ABERTURA_CICLO",
    "RECALCULO_MANUAL",
)


# ============================================================
# VALIDAR EVENTO
# ============================================================

def _validar_evento(
    origem_evento
):

    evento = _normalizar(
        origem_evento
    )

    if not evento:

        return (
            "RECALCULO_MANUAL"
        )

    if evento not in EVENTOS_SUPORTADOS:

        raise BusinessRuleViolation(
            "Origem do evento inválida. "
            f"Valores permitidos: "
            f"{', '.join(EVENTOS_SUPORTADOS)}."
        )

    return evento


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
            DataInicio

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
# RESUMIR PRIORIZAÇÃO
# ============================================================

def _resumir_priorizacao(
    resultado
):

    if not resultado:

        return None

    resumo = (
        resultado.get(
            "resumo",
            {}
        )
        or {}
    )

    ranking = (
        resultado.get(
            "ranking",
            []
        )
        or []
    )

    sugestao_principal = None

    for item in ranking:

        if (
            item.get(
                "sugerida"
            )
            and
            item.get(
                "prioridade"
            )
            ==
            1
        ):

            sugestao_principal = {
                "localizacao":
                    item.get(
                        "localizacao"
                    ),

                "prioridade":
                    item.get(
                        "prioridade"
                    ),

                "score_risco":
                    item.get(
                        "score_risco"
                    ),

                "classificacao_risco":
                    item.get(
                        "classificacao_risco"
                    ),

                "tipo_sugestao":
                    item.get(
                        "tipo_sugestao"
                    ),

                "tendencia":
                    (
                        item.get(
                            "tendencia",
                            {}
                        )
                        or {}
                    ).get(
                        "classificacao_tendencia"
                    ),
            }

            break

    return {
        "localizacoes_analisadas":
            int(
                resumo.get(
                    "localizacoes_analisadas",
                    0
                )
                or 0
            ),

        "localizacoes_sugeridas":
            int(
                resumo.get(
                    "localizacoes_sugeridas",
                    0
                )
                or 0
            ),

        "sugestoes_por_risco":
            int(
                resumo.get(
                    "sugestoes_por_risco",
                    0
                )
                or 0
            ),

        "sugestoes_por_cobertura":
            int(
                resumo.get(
                    "sugestoes_por_cobertura",
                    0
                )
                or 0
            ),

        "tratativas_pendentes":
            int(
                resumo.get(
                    "tratativas_pendentes",
                    0
                )
                or 0
            ),

        "tendencias_recorrentes":
            int(
                resumo.get(
                    "tendencias_recorrentes",
                    0
                )
                or 0
            ),

        "tendencias_deteriorando":
            int(
                resumo.get(
                    "tendencias_deteriorando",
                    0
                )
                or 0
            ),

        "resolucoes_nao_eficazes":
            int(
                resumo.get(
                    "resolucoes_nao_eficazes",
                    0
                )
                or 0
            ),

        "sugestao_principal":
            sugestao_principal,
    }


# ============================================================
# RESUMIR TENDÊNCIAS
# ============================================================

def _resumir_tendencias(
    resultado
):

    if not resultado:

        return None

    resumo = (
        resultado.get(
            "resumo",
            {}
        )
        or {}
    )

    return {
        "localizacoes_analisadas":
            int(
                resumo.get(
                    "localizacoes_analisadas",
                    0
                )
                or 0
            ),

        "sem_historico":
            int(
                resumo.get(
                    "sem_historico",
                    0
                )
                or 0
            ),

        "estaveis":
            int(
                resumo.get(
                    "estaveis",
                    0
                )
                or 0
            ),

        "atencao":
            int(
                resumo.get(
                    "atencao",
                    0
                )
                or 0
            ),

        "recorrentes":
            int(
                resumo.get(
                    "recorrentes",
                    0
                )
                or 0
            ),

        "deteriorando":
            int(
                resumo.get(
                    "deteriorando",
                    0
                )
                or 0
            ),

        "melhorando":
            int(
                resumo.get(
                    "melhorando",
                    0
                )
                or 0
            ),

        "tratativas_pendentes":
            int(
                resumo.get(
                    "tratativas_pendentes",
                    0
                )
                or 0
            ),

        "resolucoes_nao_eficazes":
            int(
                resumo.get(
                    "resolucoes_nao_eficazes",
                    0
                )
                or 0
            ),

        "resolucoes_sem_evidencia":
            int(
                resumo.get(
                    "resolucoes_sem_evidencia",
                    0
                )
                or 0
            ),

        "alertas":
            int(
                resumo.get(
                    "alertas",
                    0
                )
                or 0
            ),
    }


# ============================================================
# RESUMIR PAINEL
# ============================================================

def _resumir_painel(
    painel
):

    if not painel:

        return None

    progresso = (
        painel.get(
            "progresso",
            {}
        )
        or {}
    )

    tratativas = (
        painel.get(
            "tratativas",
            {}
        )
        or {}
    )

    eficacia = (
        painel.get(
            "eficacia",
            {}
        )
        or {}
    )

    return {
        "progresso": {
            "total_localizacoes":
                int(
                    progresso.get(
                        "total_localizacoes",
                        0
                    )
                    or 0
                ),

            "processadas":
                int(
                    progresso.get(
                        "processadas",
                        0
                    )
                    or 0
                ),

            "pendentes":
                int(
                    progresso.get(
                        "pendentes",
                        0
                    )
                    or 0
                ),

            "percentual_processado":
                float(
                    progresso.get(
                        "percentual_processado",
                        0
                    )
                    or 0
                ),
        },

        "tratativas": {
            "localizacoes_com_recorrencia":
                int(
                    tratativas.get(
                        "localizacoes_com_recorrencia",
                        0
                    )
                    or 0
                ),

            "localizacoes_com_tratativa_pendente":
                int(
                    tratativas.get(
                        "localizacoes_com_tratativa_pendente",
                        0
                    )
                    or 0
                ),

            "ocorrencias_pendentes":
                int(
                    tratativas.get(
                        "ocorrencias_pendentes",
                        0
                    )
                    or 0
                ),

            "ocorrencias_resolvidas":
                int(
                    tratativas.get(
                        "ocorrencias_resolvidas",
                        0
                    )
                    or 0
                ),
        },

        "eficacia": {
            "resolucoes_avaliadas":
                int(
                    eficacia.get(
                        "resolucoes_avaliadas",
                        0
                    )
                    or 0
                ),

            "eficazes":
                int(
                    eficacia.get(
                        "eficazes",
                        0
                    )
                    or 0
                ),

            "nao_eficazes":
                int(
                    eficacia.get(
                        "nao_eficazes",
                        0
                    )
                    or 0
                ),

            "ainda_sem_evidencia":
                int(
                    eficacia.get(
                        "ainda_sem_evidencia",
                        0
                    )
                    or 0
                ),
        },

        "sugestao_principal":
            painel.get(
                "sugestao_principal"
            ),

        "alerta_principal":
            painel.get(
                "alerta_principal"
            ),

        "alerta_tratativa":
            painel.get(
                "alerta_tratativa"
            ),
    }


# ============================================================
# EXECUTAR ORQUESTRAÇÃO
# ============================================================

def executar_orquestracao_rotativo(
    conn,
    cursor,
    cliente_id: int,
    armazem: str,
    origem_evento: str = "RECALCULO_MANUAL",
    localizacao: str | None = None,
    id_ocorrencia: int | None = None,
    id_inventario: int | None = None,
    id_rodada: int | None = None,
    usuario: str | None = None,
    limite_score_sugestao: float = 50.0,
    quantidade_sugestoes: int = 20,
    retornar_painel: bool = True,
):

    armazem = _normalizar(
        armazem
    )

    localizacao = (
        _normalizar(
            localizacao
        )
        or None
    )

    usuario = (
        _txt(
            usuario
        )
        or None
    )

    evento = _validar_evento(
        origem_evento
    )

    # ========================================================
    # VALIDAÇÕES
    # ========================================================

    if not cliente_id:

        raise BusinessRuleViolation(
            "Cliente é obrigatório."
        )

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
            "limite_score_sugestao deve "
            "estar entre 0 e 100."
        )

    if quantidade_sugestoes < 1:

        raise BusinessRuleViolation(
            "quantidade_sugestoes deve "
            "ser maior que zero."
        )

    data_inicio = (
        datetime.now()
    )

    etapas = []

    # ========================================================
    # CICLO ATUAL
    # ========================================================

    ciclo = (
        _buscar_ciclo_aberto(
            cursor=cursor,
            cliente_id=cliente_id,
            armazem=armazem,
        )
    )

    # ========================================================
    # SEM CICLO ABERTO
    #
    # Não existe ranking operacional para atualizar.
    # ========================================================

    if not ciclo:

        return {
            "orquestrado":
                False,

            "motivo":
                "SEM_CICLO_ABERTO",

            "evento": {
                "origem":
                    evento,

                "cliente_id":
                    cliente_id,

                "armazem":
                    armazem,

                "localizacao":
                    localizacao,

                "id_ocorrencia":
                    id_ocorrencia,

                "id_inventario":
                    id_inventario,

                "id_rodada":
                    id_rodada,

                "usuario":
                    usuario,
            },

            "ciclo":
                None,

            "mensagem":
                "A operação foi registrada, porém não existe "
                "ciclo rotativo ABERTO para recalcular.",
        }

    # ========================================================
    # 1. TENDÊNCIA ANTES DO RECÁLCULO
    #
    # Não persiste score.
    # Faz a leitura integrada do contexto atual.
    # ========================================================

    tendencias_antes = (
        consultar_tendencias_rotativo(
            cursor=cursor,
            cliente_id=cliente_id,
            armazem=armazem,
            limite_historico=6,
            somente_alertas=False,
        )
    )

    etapas.append(
        {
            "etapa":
                "TENDENCIA_INTEGRADA",

            "status":
                "OK",
        }
    )

    # ========================================================
    # 2. RECALCULAR PRIORIZAÇÃO
    #
    # A V1.3 já consome a tendência integrada e,
    # indiretamente, contexto, tratativas e eficácia.
    #
    # IMPORTANTE:
    # recalcular_priorizacao_rotativo() realiza commit.
    # ========================================================

    priorizacao = (
        recalcular_priorizacao_rotativo(
            conn=conn,
            cursor=cursor,
            cliente_id=cliente_id,
            armazem=armazem,
            limite_score_sugestao=(
                limite_score_sugestao
            ),
            quantidade_sugestoes=(
                quantidade_sugestoes
            ),
        )
    )

    etapas.append(
        {
            "etapa":
                "PRIORIZACAO",

            "status":
                "OK",

            "versao":
                (
                    priorizacao
                    .get(
                        "modelo",
                        {}
                    )
                    .get(
                        "versao"
                    )
                ),
        }
    )

    # ========================================================
    # 3. TENDÊNCIA APÓS RECÁLCULO
    #
    # Isso garante que score, classificação e prioridade
    # retornados pela tendência estejam sincronizados com
    # a priorização recém-gravada.
    # ========================================================

    tendencias_depois = (
        consultar_tendencias_rotativo(
            cursor=cursor,
            cliente_id=cliente_id,
            armazem=armazem,
            limite_historico=6,
            somente_alertas=False,
        )
    )

    etapas.append(
        {
            "etapa":
                "TENDENCIA_POS_PRIORIZACAO",

            "status":
                "OK",
        }
    )

    # ========================================================
    # 4. CONTEXTO DA LOCALIZAÇÃO AFETADA
    # ========================================================

    contexto_localizacao = None

    if localizacao:

        try:

            contexto_localizacao = (
                montar_contexto_localizacao_rotativo(
                    cursor=cursor,
                    cliente_id=cliente_id,
                    armazem=armazem,
                    localizacao=localizacao,
                    limite_historico=10,
                )
            )

            etapas.append(
                {
                    "etapa":
                        "CONTEXTO_LOCALIZACAO",

                    "status":
                        "OK",

                    "localizacao":
                        localizacao,
                }
            )

        except (ValueError, BusinessRuleViolation) as erro:

            etapas.append(
                {
                    "etapa":
                        "CONTEXTO_LOCALIZACAO",

                    "status":
                        "IGNORADO",

                    "localizacao":
                        localizacao,

                    "motivo":
                        str(
                            erro
                        ),
                }
            )

    # ========================================================
    # 5. PAINEL GERENCIAL
    # ========================================================

    painel = None

    if retornar_painel:

        painel = (
            consultar_painel_rotativo(
                cursor=cursor,
                cliente_id=cliente_id,
                armazem=armazem,
                limite_prioridades=5,
            )
        )

        etapas.append(
            {
                "etapa":
                    "PAINEL",

                "status":
                    "OK",
            }
        )

    # ========================================================
    # FINALIZAÇÃO
    # ========================================================

    data_fim = (
        datetime.now()
    )

    duracao_ms = round(
        (
            data_fim
            -
            data_inicio
        ).total_seconds()
        *
        1000,
        2
    )

    # ========================================================
    # RETORNO
    # ========================================================

    return {
        "orquestrado":
            True,

        "motivo":
            "INTELIGENCIA_ROTATIVO_ATUALIZADA",

        "evento": {
            "origem":
                evento,

            "cliente_id":
                cliente_id,

            "armazem":
                armazem,

            "localizacao":
                localizacao,

            "id_ocorrencia":
                id_ocorrencia,

            "id_inventario":
                id_inventario,

            "id_rodada":
                id_rodada,

            "usuario":
                usuario,

            "data_hora_processamento":
                data_fim,
        },

        "ciclo": {
            "id_ciclo":
                ciclo.ID_Ciclo,

            "codigo_ciclo":
                ciclo.CodigoCiclo,

            "status":
                ciclo.Status,
        },

        "execucao": {
            "duracao_ms":
                duracao_ms,

            "etapas":
                etapas,
        },

        "tendencias": {
            "antes":
                _resumir_tendencias(
                    tendencias_antes
                ),

            "depois":
                _resumir_tendencias(
                    tendencias_depois
                ),
        },

        "priorizacao":
            _resumir_priorizacao(
                priorizacao
            ),

        "contexto_localizacao":
            contexto_localizacao,

        "painel":
            (
                _resumir_painel(
                    painel
                )
                if painel
                else None
            ),
    }