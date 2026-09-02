# ============================================================
# CONTEXTO INTEGRADO DO INVENTÁRIO ROTATIVO
#
# Objetivo:
# Montar a visão completa de uma localização juntando:
#
# - Ciclo atual
# - Cadastro da localização
# - Situação operacional no ciclo
# - Última contagem
# - Histórico rotativo
# - Divergências
# - Justificativas
# - Tratativas
# - Resoluções
# - Recorrência
# - Priorização
# - Evidência posterior à resolução
#
# Este service deve funcionar como camada-base para:
#
# rotativo_tendencia.py
# rotativo_priorizacao.py
# rotativo_tratativas.py
# rotativo_painel.py
# rotativo_eficacia.py
# ============================================================


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


def _float(valor):
    if valor is None:
        return None

    return float(
        valor
    )


# ============================================================
# STATUS RESOLVIDOS
# ============================================================

STATUS_RESOLVIDOS = (
    "RESOLVIDA_RECONTAGEM",
    "RESOLVIDA_AJUSTE",
    "RESOLVIDA_OFICIAL",
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
            DataInicio,
            DataFimPrevista,
            DataFimReal,
            Status,
            TotalLocalizacoes,
            LocalizacoesContadas,
            PercentualCobertura,
            CriadoPor,
            DataHoraCriacao,
            FinalizadoPor

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
# BUSCAR CADASTRO DA LOCALIZAÇÃO
# ============================================================

def _buscar_localizacao_rotativo(
    cursor,
    cliente_id: int,
    armazem: str,
    localizacao: str
):

    cursor.execute(
        """
        SELECT TOP 1
            ID_RotativoLocalizacao,
            ClienteId,
            cArmazem,
            Localizacao,
            Status,
            UltimaContagem,
            ID_InventarioUltimaContagem,
            ID_RodadaUltimaContagem,
            ScoreRisco,
            ClassificacaoRisco,
            Sugerida,
            Prioridade,
            TipoSugestao,
            DataHoraCriacao,
            DataHoraAtualizacao

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
            AND UPPER(
                LTRIM(
                    RTRIM(
                        Localizacao
                    )
                )
            ) = ?

        ORDER BY
            ID_RotativoLocalizacao DESC
        """,
        (
            cliente_id,
            armazem,
            localizacao,
        )
    )

    return cursor.fetchone()


# ============================================================
# BUSCAR LOCALIZAÇÃO NO CICLO
# ============================================================

def _buscar_localizacao_ciclo(
    cursor,
    id_ciclo: int,
    id_rotativo_localizacao: int
):

    cursor.execute(
        """
        SELECT TOP 1
            ID_CicloLocalizacao,
            ID_Ciclo,
            ID_RotativoLocalizacao,
            ClienteId,
            cArmazem,
            Localizacao,
            Status,
            DataInclusao,
            DataInicioContagem,
            DataConclusao,
            ID_Inventario,
            ID_Rodada,
            ScoreRiscoEntrada,
            ClassificacaoRiscoEntrada,
            Sugerida,
            Prioridade,
            UsuarioContagem,
            DataHoraAtualizacao,
            TipoSugestao

        FROM dbo.CicloRotativoLocalizacoes

        WHERE
            ID_Ciclo = ?
            AND ID_RotativoLocalizacao = ?
        """,
        (
            id_ciclo,
            id_rotativo_localizacao,
        )
    )

    return cursor.fetchone()


# ============================================================
# HISTÓRICO ROTATIVO DA LOCALIZAÇÃO
# ============================================================

def _buscar_historico_localizacao(
    cursor,
    id_rotativo_localizacao: int,
    limite_historico: int
):

    sql = f"""
        SELECT TOP ({int(limite_historico)})
            ID_HistoricoRotativo,
            ID_RotativoLocalizacao,
            ClienteId,
            cArmazem,
            Localizacao,
            ID_Inventario,
            ID_Rodada,
            DataHoraInicio,
            DataHoraFim,
            DataHoraContagem,
            Usuario,
            LocalizacaoVazia,
            PossuiDivergencia,
            QuantidadeItens,
            QuantidadeItensOK,
            QuantidadeItensDivergentes,
            ScoreRiscoNaData,
            ClassificacaoRiscoNaData,
            DataHoraRegistro,
            ID_Ciclo

        FROM dbo.RotativoHistoricoLocalizacoes

        WHERE
            ID_RotativoLocalizacao = ?

        ORDER BY
            DataHoraContagem DESC,
            ID_HistoricoRotativo DESC
    """

    cursor.execute(
        sql,
        (
            id_rotativo_localizacao,
        )
    )

    return cursor.fetchall()


# ============================================================
# RESUMIR HISTÓRICO
# ============================================================

def _resumir_historico(
    historico
):

    total = len(
        historico
    )

    divergencias = sum(
        1
        for linha in historico
        if bool(
            linha.PossuiDivergencia
        )
    )

    sem_divergencia = (
        total
        -
        divergencias
    )

    consecutivas = 0

    # Histórico chega do mais recente para o mais antigo.
    for linha in historico:

        if bool(
            linha.PossuiDivergencia
        ):
            consecutivas += 1

        else:
            break

    taxa = (
        round(
            divergencias
            /
            total
            *
            100,
            2
        )
        if total > 0
        else 0.0
    )

    ultima = (
        historico[0]
        if historico
        else None
    )

    ultima_divergencia = None

    for linha in historico:

        if bool(
            linha.PossuiDivergencia
        ):

            ultima_divergencia = (
                linha.DataHoraContagem
            )

            break

    return {
        "contagens":
            total,

        "contagens_ok":
            sem_divergencia,

        "contagens_com_divergencia":
            divergencias,

        "taxa_divergencia_percentual":
            taxa,

        "divergencias_consecutivas":
            consecutivas,

        "ultima_contagem":
            (
                ultima.DataHoraContagem
                if ultima
                else None
            ),

        "ultima_divergencia":
            ultima_divergencia,
    }


# ============================================================
# BUSCAR OCORRÊNCIAS DA LOCALIZAÇÃO
#
# IMPORTANTE:
#
# OcorrenciasDivergencia não possui cArmazem.
#
# Portanto utilizamos RotativoHistoricoLocalizacoes para
# garantir que o inventário/rodada daquela ocorrência
# realmente pertence ao armazém consultado.
# ============================================================

# ============================================================
# BUSCAR OCORRÊNCIAS DA LOCALIZAÇÃO
#
# Regra:
# - Mesmo cliente
# - Inventário ROTATIVO
# - Mesma localização
#
# O agrupamento posterior utiliza:
# Localização + Código + Lote
#
# IMPORTANTE:
# Não exigimos existência em RotativoHistoricoLocalizacoes,
# pois ocorrências antigas podem existir antes da implantação
# completa do histórico rotativo.
# ============================================================

def _buscar_ocorrencias_localizacao(
    cursor,
    cliente_id: int,
    armazem: str,
    localizacao: str
):

    cursor.execute(
        """
        SELECT
            od.ID_Ocorrencia,
            od.ClienteId,
            od.ID_Inventario,
            od.ID_Rodada,
            od.TipoInventario,
            od.Localizacao,
            od.Codigo,
            od.Lote,
            od.QtdEstoque,
            od.QtdContada,
            od.Diferenca,
            od.TipoDivergencia,
            od.StatusResolucao,
            od.Justificativa,
            od.ID_DecisaoRotativo,
            od.ID_InventarioResolucao,
            od.ID_RodadaResolucao,
            od.TipoResolucao,
            od.ObservacaoResolucao,
            od.CriadoPor,
            od.DataHoraCriacao,
            od.ResolvidoPor,
            od.DataHoraResolucao

        FROM dbo.OcorrenciasDivergencia od

        WHERE
            od.ClienteId = ?

            AND UPPER(
                LTRIM(
                    RTRIM(
                        od.TipoInventario
                    )
                )
            ) = 'ROTATIVO'

            AND UPPER(
                LTRIM(
                    RTRIM(
                        od.Localizacao
                    )
                )
            ) = ?

        ORDER BY
            od.DataHoraCriacao DESC,
            od.ID_Ocorrencia DESC
        """,
        (
            cliente_id,
            localizacao,
        )
    )

    return cursor.fetchall()


# ============================================================
# CLASSIFICAR UMA OCORRÊNCIA
# ============================================================

def _classificar_ocorrencia(
    ocorrencia
):

    status = _normalizar(
        ocorrencia.StatusResolucao
    )

    justificativa = _txt(
        ocorrencia.Justificativa
    )

    if status in STATUS_RESOLVIDOS:

        return {
            "status_tratativa":
                "RESOLVIDA",

            "possui_justificativa":
                bool(
                    justificativa
                ),

            "resolvida":
                True,

            "necessita_tratativa":
                False,
        }

    if status == "EM_RECONTAGEM":

        return {
            "status_tratativa":
                "EM_TRATATIVA",

            "possui_justificativa":
                bool(
                    justificativa
                ),

            "resolvida":
                False,

            "necessita_tratativa":
                True,
        }

    if (
        status == "JUSTIFICADA"
        and justificativa
    ):

        return {
            "status_tratativa":
                "JUSTIFICADA_PENDENTE_RESOLUCAO",

            "possui_justificativa":
                True,

            "resolvida":
                False,

            "necessita_tratativa":
                True,
        }

    return {
        "status_tratativa":
            "SEM_JUSTIFICATIVA",

        "possui_justificativa":
            False,

        "resolvida":
            False,

        "necessita_tratativa":
            True,
    }


# ============================================================
# TRANSFORMAR OCORRÊNCIAS
# ============================================================

def _montar_ocorrencias(
    ocorrencias
):

    resultado = []

    for ocorrencia in ocorrencias:

        classificacao = (
            _classificar_ocorrencia(
                ocorrencia
            )
        )

        resultado.append(
            {
                "id_ocorrencia":
                    ocorrencia.ID_Ocorrencia,

                "id_inventario":
                    ocorrencia.ID_Inventario,

                "id_rodada":
                    ocorrencia.ID_Rodada,

                "localizacao":
                    ocorrencia.Localizacao,

                "codigo":
                    ocorrencia.Codigo,

                "lote":
                    ocorrencia.Lote,

                "qtd_estoque":
                    _float(
                        ocorrencia.QtdEstoque
                    ),

                "qtd_contada":
                    _float(
                        ocorrencia.QtdContada
                    ),

                "diferenca":
                    _float(
                        ocorrencia.Diferenca
                    ),

                "tipo_divergencia":
                    ocorrencia.TipoDivergencia,

                "status_resolucao":
                    ocorrencia.StatusResolucao,

                "justificativa":
                    ocorrencia.Justificativa,

                "status_tratativa":
                    classificacao[
                        "status_tratativa"
                    ],

                "possui_justificativa":
                    classificacao[
                        "possui_justificativa"
                    ],

                "resolvida":
                    classificacao[
                        "resolvida"
                    ],

                "necessita_tratativa":
                    classificacao[
                        "necessita_tratativa"
                    ],

                "tipo_resolucao":
                    ocorrencia.TipoResolucao,

                "observacao_resolucao":
                    ocorrencia.ObservacaoResolucao,

                "id_inventario_resolucao":
                    ocorrencia.ID_InventarioResolucao,

                "id_rodada_resolucao":
                    ocorrencia.ID_RodadaResolucao,

                "criado_por":
                    ocorrencia.CriadoPor,

                "data_hora_criacao":
                    ocorrencia.DataHoraCriacao,

                "resolvido_por":
                    ocorrencia.ResolvidoPor,

                "data_hora_resolucao":
                    ocorrencia.DataHoraResolucao,
            }
        )

    return resultado


# ============================================================
# AGRUPAR DIVERGÊNCIAS POR ITEM
#
# Chave operacional:
#
# Localização + Código + Lote
# ============================================================

def _agrupar_divergencias(
    ocorrencias
):

    grupos = {}

    for item in ocorrencias:

        chave = (
            _normalizar(
                item[
                    "localizacao"
                ]
            ),
            _normalizar(
                item[
                    "codigo"
                ]
            ),
            _normalizar(
                item[
                    "lote"
                ]
            ),
        )

        if chave not in grupos:

            grupos[chave] = {
                "localizacao":
                    item[
                        "localizacao"
                    ],

                "codigo":
                    item[
                        "codigo"
                    ],

                "lote":
                    item[
                        "lote"
                    ],

                "ocorrencias":
                    [],
            }

        grupos[chave][
            "ocorrencias"
        ].append(
            item
        )

    resultado = []

    for grupo in grupos.values():

        itens = grupo[
            "ocorrencias"
        ]

        total = len(
            itens
        )

        resolvidas = sum(
            1
            for item in itens
            if item[
                "resolvida"
            ]
        )

        pendentes = sum(
            1
            for item in itens
            if item[
                "necessita_tratativa"
            ]
        )

        sem_justificativa = sum(
            1
            for item in itens
            if not item[
                "possui_justificativa"
            ]
        )

        justificadas = sum(
            1
            for item in itens
            if item[
                "possui_justificativa"
            ]
        )

        recorrente = (
            total >= 2
        )

        ultima = max(
            itens,
            key=lambda item: (
                item[
                    "data_hora_criacao"
                ]
            )
        )

        if sem_justificativa > 0:

            status = (
                "SEM_JUSTIFICATIVA"
            )

        elif pendentes > 0:

            if any(
                item[
                    "status_tratativa"
                ]
                ==
                "EM_TRATATIVA"
                for item in itens
            ):

                status = (
                    "EM_TRATATIVA"
                )

            else:

                status = (
                    "JUSTIFICADA_PENDENTE_RESOLUCAO"
                )

        elif resolvidas == total:

            status = (
                "RESOLVIDA"
            )

        else:

            status = (
                "EM_TRATATIVA"
            )

        resultado.append(
            {
                "localizacao":
                    grupo[
                        "localizacao"
                    ],

                "codigo":
                    grupo[
                        "codigo"
                    ],

                "lote":
                    grupo[
                        "lote"
                    ],

                "ocorrencias":
                    total,

                "recorrente":
                    recorrente,

                "status_tratativa":
                    status,

                "necessita_tratativa":
                    pendentes > 0,

                "resumo": {
                    "justificadas":
                        justificadas,

                    "sem_justificativa":
                        sem_justificativa,

                    "resolvidas":
                        resolvidas,

                    "pendentes":
                        pendentes,
                },

                "ultima_ocorrencia":
                    ultima,
            }
        )

    resultado.sort(
        key=lambda item: (
            0
            if item[
                "necessita_tratativa"
            ]
            else 1,

            0
            if item[
                "recorrente"
            ]
            else 1,

            -item[
                "ocorrencias"
            ],

            _normalizar(
                item[
                    "codigo"
                ]
            ),

            _normalizar(
                item[
                    "lote"
                ]
            ),
        )
    )

    return resultado


# ============================================================
# AVALIAR EFICÁCIA DE UMA RESOLUÇÃO
#
# Regra inicial:
#
# NAO_EFICAZ
# → mesma chave apresentou nova ocorrência após resolução
#
# EFICAZ
# → houve contagem posterior da localização sem divergência
#
# AINDA_SEM_EVIDENCIA
# → ainda não há evidência posterior suficiente
#
# Esta é uma avaliação operacional inicial.
# ============================================================

def _avaliar_eficacia(
    cursor,
    ocorrencia,
    id_rotativo_localizacao: int
):

    if not ocorrencia[
        "resolvida"
    ]:

        return None

    data_resolucao = (
        ocorrencia[
            "data_hora_resolucao"
        ]
    )

    if data_resolucao is None:

        return {
            "classificacao":
                "AINDA_SEM_EVIDENCIA",

            "motivo":
                "Resolução sem data registrada.",
        }

    # --------------------------------------------------------
    # NOVA OCORRÊNCIA DA MESMA CHAVE
    # --------------------------------------------------------

    cursor.execute(
        """
        SELECT TOP 1
            ID_Ocorrencia,
            DataHoraCriacao,
            TipoDivergencia,
            Diferenca

        FROM dbo.OcorrenciasDivergencia

        WHERE
            ClienteId = ?

            AND UPPER(
                LTRIM(
                    RTRIM(
                        TipoInventario
                    )
                )
            ) = 'ROTATIVO'

            AND UPPER(
                LTRIM(
                    RTRIM(
                        Localizacao
                    )
                )
            ) = ?

            AND UPPER(
                LTRIM(
                    RTRIM(
                        Codigo
                    )
                )
            ) = ?

            AND UPPER(
                LTRIM(
                    RTRIM(
                        ISNULL(
                            Lote,
                            ''
                        )
                    )
                )
            ) = ?

            AND DataHoraCriacao > ?

        ORDER BY
            DataHoraCriacao ASC
        """,
        (
            ocorrencia.get(
                "cliente_id"
            ),
            _normalizar(
                ocorrencia[
                    "localizacao"
                ]
            ),
            _normalizar(
                ocorrencia[
                    "codigo"
                ]
            ),
            _normalizar(
                ocorrencia[
                    "lote"
                ]
            ),
            data_resolucao,
        )
    )

    nova_divergencia = (
        cursor.fetchone()
    )

    if nova_divergencia:

        return {
            "classificacao":
                "NAO_EFICAZ",

            "motivo":
                "A mesma combinação Localização + Código + Lote "
                "voltou a apresentar divergência após a resolução.",

            "nova_ocorrencia":
                nova_divergencia.ID_Ocorrencia,

            "data_nova_ocorrencia":
                nova_divergencia.DataHoraCriacao,
        }

    # --------------------------------------------------------
    # CONTAGEM POSTERIOR DA LOCALIZAÇÃO
    # --------------------------------------------------------

    cursor.execute(
        """
        SELECT TOP 1
            ID_HistoricoRotativo,
            DataHoraContagem,
            PossuiDivergencia

        FROM dbo.RotativoHistoricoLocalizacoes

        WHERE
            ID_RotativoLocalizacao = ?
            AND DataHoraContagem > ?

        ORDER BY
            DataHoraContagem ASC,
            ID_HistoricoRotativo ASC
        """,
        (
            id_rotativo_localizacao,
            data_resolucao,
        )
    )

    contagem_posterior = (
        cursor.fetchone()
    )

    if not contagem_posterior:

        return {
            "classificacao":
                "AINDA_SEM_EVIDENCIA",

            "motivo":
                "Ainda não existe nova contagem após a resolução.",
        }

    if not bool(
        contagem_posterior.PossuiDivergencia
    ):

        return {
            "classificacao":
                "EFICAZ",

            "motivo":
                "Houve nova contagem da localização sem divergência.",

            "id_historico_validacao":
                contagem_posterior.ID_HistoricoRotativo,

            "data_validacao":
                contagem_posterior.DataHoraContagem,
        }

    return {
        "classificacao":
            "AINDA_SEM_EVIDENCIA",

        "motivo":
            "Houve nova contagem da localização, mas existem "
            "outras divergências. Ainda não há evidência suficiente "
            "para afirmar eficácia para este item.",
    }


# ============================================================
# MONTAR CONTEXTO COMPLETO DA LOCALIZAÇÃO
# ============================================================

def montar_contexto_localizacao_rotativo(
    cursor,
    cliente_id: int,
    armazem: str,
    localizacao: str,
    limite_historico: int = 10
):

    armazem = _normalizar(
        armazem
    )

    localizacao = _normalizar(
        localizacao
    )

    # ========================================================
    # VALIDAÇÕES
    # ========================================================

    if not armazem:

        raise ValueError(
            "Armazém é obrigatório."
        )

    if not localizacao:

        raise ValueError(
            "Localização é obrigatória."
        )

    if limite_historico < 1:

        raise ValueError(
            "limite_historico deve ser maior que zero."
        )

    if limite_historico > 100:

        raise ValueError(
            "limite_historico máximo permitido é 100."
        )

    # ========================================================
    # CADASTRO ROTATIVO
    # ========================================================

    cadastro = (
        _buscar_localizacao_rotativo(
            cursor=cursor,
            cliente_id=cliente_id,
            armazem=armazem,
            localizacao=localizacao,
        )
    )

    if not cadastro:

        raise ValueError(
            "Localização não encontrada em "
            "RotativoLocalizacoes para este cliente/armazém."
        )

    id_rotativo_localizacao = (
        cadastro.ID_RotativoLocalizacao
    )

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

    ciclo_localizacao = None

    if ciclo:

        ciclo_localizacao = (
            _buscar_localizacao_ciclo(
                cursor=cursor,
                id_ciclo=ciclo.ID_Ciclo,
                id_rotativo_localizacao=(
                    id_rotativo_localizacao
                ),
            )
        )

    # ========================================================
    # HISTÓRICO
    # ========================================================

    historico_db = (
        _buscar_historico_localizacao(
            cursor=cursor,
            id_rotativo_localizacao=(
                id_rotativo_localizacao
            ),
            limite_historico=(
                limite_historico
            ),
        )
    )

    resumo_historico = (
        _resumir_historico(
            historico_db
        )
    )

    historico = []

    for linha in historico_db:

        historico.append(
            {
                "id_historico":
                    linha.ID_HistoricoRotativo,

                "id_inventario":
                    linha.ID_Inventario,

                "id_rodada":
                    linha.ID_Rodada,

                "id_ciclo":
                    linha.ID_Ciclo,

                "data_hora_inicio":
                    linha.DataHoraInicio,

                "data_hora_fim":
                    linha.DataHoraFim,

                "data_hora_contagem":
                    linha.DataHoraContagem,

                "usuario":
                    linha.Usuario,

                "localizacao_vazia":
                    bool(
                        linha.LocalizacaoVazia
                    ),

                "possui_divergencia":
                    bool(
                        linha.PossuiDivergencia
                    ),

                "quantidade_itens":
                    linha.QuantidadeItens,

                "quantidade_itens_ok":
                    linha.QuantidadeItensOK,

                "quantidade_itens_divergentes":
                    linha.QuantidadeItensDivergentes,

                "score_risco_na_data":
                    _float(
                        linha.ScoreRiscoNaData
                    ),

                "classificacao_risco_na_data":
                    linha.ClassificacaoRiscoNaData,
            }
        )

    # ========================================================
    # OCORRÊNCIAS
    # ========================================================

    ocorrencias_db = (
        _buscar_ocorrencias_localizacao(
            cursor=cursor,
            cliente_id=cliente_id,
            armazem=armazem,
            localizacao=localizacao,
        )
    )

    ocorrencias = (
        _montar_ocorrencias(
            ocorrencias_db
        )
    )

    # Acrescenta cliente_id para avaliação da eficácia.
    for ocorrencia in ocorrencias:

        ocorrencia[
            "cliente_id"
        ] = cliente_id

    # ========================================================
    # AGRUPAR TRATATIVAS
    # ========================================================

    grupos_divergencia = (
        _agrupar_divergencias(
            ocorrencias
        )
    )

    # ========================================================
    # EFICÁCIA DAS RESOLUÇÕES
    # ========================================================

    resolucoes = []

    for ocorrencia in ocorrencias:

        if not ocorrencia[
            "resolvida"
        ]:
            continue

        eficacia = (
            _avaliar_eficacia(
                cursor=cursor,
                ocorrencia=ocorrencia,
                id_rotativo_localizacao=(
                    id_rotativo_localizacao
                ),
            )
        )

        resolucoes.append(
            {
                "id_ocorrencia":
                    ocorrencia[
                        "id_ocorrencia"
                    ],

                "codigo":
                    ocorrencia[
                        "codigo"
                    ],

                "lote":
                    ocorrencia[
                        "lote"
                    ],

                "tipo_resolucao":
                    ocorrencia[
                        "tipo_resolucao"
                    ],

                "data_resolucao":
                    ocorrencia[
                        "data_hora_resolucao"
                    ],

                "eficacia":
                    eficacia,
            }
        )

    # ========================================================
    # RESUMO DAS DIVERGÊNCIAS
    # ========================================================

    total_ocorrencias = len(
        ocorrencias
    )

    ocorrencias_resolvidas = sum(
        1
        for item in ocorrencias
        if item[
            "resolvida"
        ]
    )

    ocorrencias_pendentes = sum(
        1
        for item in ocorrencias
        if item[
            "necessita_tratativa"
        ]
    )

    grupos_recorrentes = sum(
        1
        for item in grupos_divergencia
        if item[
            "recorrente"
        ]
    )

    grupos_pendentes = sum(
        1
        for item in grupos_divergencia
        if item[
            "necessita_tratativa"
        ]
    )

    # ========================================================
    # CONTEXTO DO CICLO
    # ========================================================

    contexto_ciclo = None

    if ciclo:

        contexto_ciclo = {
            "id_ciclo":
                ciclo.ID_Ciclo,

            "codigo_ciclo":
                ciclo.CodigoCiclo,

            "status":
                ciclo.Status,

            "data_inicio":
                ciclo.DataInicio,

            "data_fim_prevista":
                ciclo.DataFimPrevista,

            "localizacao_pertence_ciclo":
                ciclo_localizacao is not None,
        }

        if ciclo_localizacao:

            contexto_ciclo[
                "localizacao"
            ] = {
                "id_ciclo_localizacao":
                    ciclo_localizacao.ID_CicloLocalizacao,

                "status":
                    ciclo_localizacao.Status,

                "data_inclusao":
                    ciclo_localizacao.DataInclusao,

                "data_inicio_contagem":
                    ciclo_localizacao.DataInicioContagem,

                "data_conclusao":
                    ciclo_localizacao.DataConclusao,

                "id_inventario":
                    ciclo_localizacao.ID_Inventario,

                "id_rodada":
                    ciclo_localizacao.ID_Rodada,

                "usuario":
                    ciclo_localizacao.UsuarioContagem,
            }

    # ========================================================
    # RETORNO
    # ========================================================

    return {
        "tipo_contexto":
            "CONTEXTO_LOCALIZACAO_ROTATIVO",

        "cliente_id":
            cliente_id,

        "armazem":
            armazem,

        "localizacao":
            localizacao,

        # ====================================================
        # CICLO
        # ====================================================

        "ciclo":
            contexto_ciclo,

        # ====================================================
        # CADASTRO ROTATIVO
        # ====================================================

        "cadastro": {
            "id_rotativo_localizacao":
                cadastro.ID_RotativoLocalizacao,

            "status":
                cadastro.Status,

            "ultima_contagem":
                cadastro.UltimaContagem,

            "id_inventario_ultima_contagem":
                cadastro.ID_InventarioUltimaContagem,

            "id_rodada_ultima_contagem":
                cadastro.ID_RodadaUltimaContagem,

            "data_hora_atualizacao":
                cadastro.DataHoraAtualizacao,
        },

        # ====================================================
        # RISCO
        # ====================================================

        "risco": {
            "score":
                _float(
                    cadastro.ScoreRisco
                ),

            "classificacao":
                cadastro.ClassificacaoRisco,
        },

        # ====================================================
        # PRIORIZAÇÃO
        # ====================================================

        "priorizacao": {
            "sugerida":
                bool(
                    cadastro.Sugerida
                ),

            "prioridade":
                cadastro.Prioridade,

            "tipo_sugestao":
                cadastro.TipoSugestao,

            "score_snapshot_ciclo":
                (
                    _float(
                        ciclo_localizacao.ScoreRiscoEntrada
                    )
                    if ciclo_localizacao
                    else None
                ),

            "classificacao_snapshot_ciclo":
                (
                    ciclo_localizacao.ClassificacaoRiscoEntrada
                    if ciclo_localizacao
                    else None
                ),
        },

        # ====================================================
        # HISTÓRICO
        # ====================================================

        "historico": {
            "resumo":
                resumo_historico,

            "contagens":
                historico,
        },

        # ====================================================
        # DIVERGÊNCIAS / TRATATIVAS
        # ====================================================

        "divergencias": {
            "ocorrencias":
                total_ocorrencias,

            "ocorrencias_resolvidas":
                ocorrencias_resolvidas,

            "ocorrencias_pendentes":
                ocorrencias_pendentes,

            "grupos_divergencia":
                len(
                    grupos_divergencia
                ),

            "grupos_recorrentes":
                grupos_recorrentes,

            "grupos_pendentes":
                grupos_pendentes,

            "possui_recorrencia":
                grupos_recorrentes > 0,

            "necessita_tratativa":
                grupos_pendentes > 0,

            "grupos":
                grupos_divergencia,

            "historico_ocorrencias":
                ocorrencias,
        },

        # ====================================================
        # EFICÁCIA
        # ====================================================

        "eficacia": {
            "resolucoes_avaliadas":
                len(
                    resolucoes
                ),

            "resolucoes":
                resolucoes,
        },
    }