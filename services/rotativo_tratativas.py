# ============================================================
# TRATATIVAS DE DIVERGÊNCIAS DO INVENTÁRIO ROTATIVO
#
# Objetivos:
# - Consultar ocorrências de divergência do ciclo
# - Identificar justificativas pendentes
# - Identificar divergências recorrentes
# - Consolidar por Localização + Código + Lote
# - Expor necessidade de tratativa
# - Resolver ocorrências de divergência
# - Atualizar automaticamente a inteligência do rotativo
# ============================================================


from services.rotativo_orquestrador import (
    executar_orquestracao_rotativo,
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
# STATUS DE RESOLUÇÃO
#
# Permitidos pela constraint:
# CK_OcorrenciasDivergencia_StatusResolucao
#
# - PENDENTE
# - JUSTIFICADA
# - EM_RECONTAGEM
# - RESOLVIDA_RECONTAGEM
# - RESOLVIDA_AJUSTE
# - RESOLVIDA_OFICIAL
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
            Status

        FROM dbo.CiclosRotativo

        WHERE
            ClienteId = ?

            AND UPPER(
                LTRIM(
                    RTRIM(cArmazem)
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
# CLASSIFICAR SITUAÇÃO DA TRATATIVA
# ============================================================

def _classificar_tratativa(
    status_resolucao,
    justificativa,
    tipo_resolucao,
    data_hora_resolucao
):

    status = _normalizar(
        status_resolucao
    )

    justificativa = _txt(
        justificativa
    )

    tipo_resolucao = _txt(
        tipo_resolucao
    )

    # --------------------------------------------------------
    # RESOLVIDA
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # COMPATIBILIDADE COM REGISTROS LEGADOS
    # --------------------------------------------------------

    if (
        tipo_resolucao
        and
        data_hora_resolucao is not None
    ):

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

    # --------------------------------------------------------
    # EM RECONTAGEM
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # JUSTIFICADA, MAS NÃO RESOLVIDA
    # --------------------------------------------------------

    if (
        status == "JUSTIFICADA"
        and
        justificativa
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

    # --------------------------------------------------------
    # SEM JUSTIFICATIVA
    # --------------------------------------------------------

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
# CONSULTAR TRATATIVAS DO ROTATIVO
# ============================================================

def consultar_tratativas_rotativo(
    cursor,
    cliente_id: int,
    armazem: str,
    somente_pendentes: bool = False,
    somente_recorrentes: bool = False
):

    armazem = _normalizar(
        armazem
    )

    if not armazem:

        raise ValueError(
            "Armazém é obrigatório."
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
                "grupos_divergencia":
                    0,

                "ocorrencias":
                    0,

                "sem_justificativa":
                    0,

                "justificadas_pendentes":
                    0,

                "em_tratativa":
                    0,

                "resolvidas":
                    0,

                "recorrentes":
                    0,

                "necessitam_tratativa":
                    0,
            },

            "tratativas":
                [],
        }

    # ========================================================
    # BUSCAR LOCALIZAÇÕES DO CICLO
    # ========================================================

    cursor.execute(
        """
        SELECT
            ID_RotativoLocalizacao,
            Localizacao

        FROM dbo.CicloRotativoLocalizacoes

        WHERE
            ID_Ciclo = ?
        """,
        (
            ciclo.ID_Ciclo,
        )
    )

    localizacoes_ciclo = (
        cursor.fetchall()
    )

    conjunto_localizacoes = {
        _normalizar(
            linha.Localizacao
        )
        for linha in localizacoes_ciclo
        if _normalizar(
            linha.Localizacao
        )
    }

    if not conjunto_localizacoes:

        return {
            "possui_ciclo_aberto":
                True,

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
            },

            "resumo": {
                "grupos_divergencia":
                    0,

                "ocorrencias":
                    0,

                "sem_justificativa":
                    0,

                "justificadas_pendentes":
                    0,

                "em_tratativa":
                    0,

                "resolvidas":
                    0,

                "recorrentes":
                    0,

                "necessitam_tratativa":
                    0,
            },

            "tratativas":
                [],
        }

    # ========================================================
    # BUSCAR OCORRÊNCIAS ROTATIVAS DO CLIENTE
    #
    # Depois filtramos pelas localizações pertencentes ao
    # ciclo atual.
    #
    # Isso permite identificar recorrência entre inventários.
    # ========================================================

    cursor.execute(
        """
        SELECT
            ID_Ocorrencia,
            ClienteId,
            ID_Inventario,
            ID_Rodada,
            TipoInventario,
            Localizacao,
            Codigo,
            Lote,
            QtdEstoque,
            QtdContada,
            Diferenca,
            TipoDivergencia,
            StatusResolucao,
            Justificativa,
            ID_DecisaoRotativo,
            ID_InventarioResolucao,
            ID_RodadaResolucao,
            TipoResolucao,
            ObservacaoResolucao,
            CriadoPor,
            DataHoraCriacao,
            ResolvidoPor,
            DataHoraResolucao

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

        ORDER BY
            DataHoraCriacao ASC,
            ID_Ocorrencia ASC
        """,
        (
            cliente_id,
        )
    )

    ocorrencias = (
        cursor.fetchall()
    )

    # ========================================================
    # AGRUPAR POR:
    # Localização + Código + Lote
    # ========================================================

    grupos = {}

    total_ocorrencias_consideradas = 0

    for ocorrencia in ocorrencias:

        localizacao = _normalizar(
            ocorrencia.Localizacao
        )

        if (
            localizacao
            not in
            conjunto_localizacoes
        ):
            continue

        codigo = _normalizar(
            ocorrencia.Codigo
        )

        lote = _normalizar(
            ocorrencia.Lote
        )

        chave = (
            localizacao,
            codigo,
            lote,
        )

        if chave not in grupos:

            grupos[chave] = {
                "localizacao":
                    localizacao,

                "codigo":
                    ocorrencia.Codigo,

                "lote":
                    ocorrencia.Lote,

                "ocorrencias":
                    [],
            }

        classificacao = (
            _classificar_tratativa(
                status_resolucao=(
                    ocorrencia.StatusResolucao
                ),
                justificativa=(
                    ocorrencia.Justificativa
                ),
                tipo_resolucao=(
                    ocorrencia.TipoResolucao
                ),
                data_hora_resolucao=(
                    ocorrencia.DataHoraResolucao
                ),
            )
        )

        grupos[chave][
            "ocorrencias"
        ].append(
            {
                "id_ocorrencia":
                    ocorrencia.ID_Ocorrencia,

                "id_inventario":
                    ocorrencia.ID_Inventario,

                "id_rodada":
                    ocorrencia.ID_Rodada,

                "tipo_inventario":
                    ocorrencia.TipoInventario,

                "localizacao":
                    ocorrencia.Localizacao,

                "codigo":
                    ocorrencia.Codigo,

                "lote":
                    ocorrencia.Lote,

                "qtd_estoque":
                    (
                        float(
                            ocorrencia.QtdEstoque
                        )
                        if ocorrencia.QtdEstoque is not None
                        else None
                    ),

                "qtd_contada":
                    (
                        float(
                            ocorrencia.QtdContada
                        )
                        if ocorrencia.QtdContada is not None
                        else None
                    ),

                "diferenca":
                    (
                        float(
                            ocorrencia.Diferenca
                        )
                        if ocorrencia.Diferenca is not None
                        else None
                    ),

                "tipo_divergencia":
                    ocorrencia.TipoDivergencia,

                "status_resolucao":
                    ocorrencia.StatusResolucao,

                "justificativa":
                    ocorrencia.Justificativa,

                "id_decisao_rotativo":
                    ocorrencia.ID_DecisaoRotativo,

                "id_inventario_resolucao":
                    ocorrencia.ID_InventarioResolucao,

                "id_rodada_resolucao":
                    ocorrencia.ID_RodadaResolucao,

                "tipo_resolucao":
                    ocorrencia.TipoResolucao,

                "observacao_resolucao":
                    ocorrencia.ObservacaoResolucao,

                "criado_por":
                    ocorrencia.CriadoPor,

                "data_hora_criacao":
                    ocorrencia.DataHoraCriacao,

                "resolvido_por":
                    ocorrencia.ResolvidoPor,

                "data_hora_resolucao":
                    ocorrencia.DataHoraResolucao,

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
            }
        )

        total_ocorrencias_consideradas += 1

    # ========================================================
    # CONSOLIDAR GRUPOS
    # ========================================================

    tratativas = []

    for grupo in grupos.values():

        itens = grupo[
            "ocorrencias"
        ]

        if not itens:
            continue

        total_ocorrencias = len(
            itens
        )

        # ----------------------------------------------------
        # CONTADORES
        # ----------------------------------------------------

        sem_justificativa = sum(
            1
            for item in itens
            if (
                item[
                    "status_tratativa"
                ]
                ==
                "SEM_JUSTIFICATIVA"
            )
        )

        justificadas_pendentes = sum(
            1
            for item in itens
            if (
                item[
                    "status_tratativa"
                ]
                ==
                "JUSTIFICADA_PENDENTE_RESOLUCAO"
            )
        )

        em_tratativa = sum(
            1
            for item in itens
            if (
                item[
                    "status_tratativa"
                ]
                ==
                "EM_TRATATIVA"
            )
        )

        resolvidas = sum(
            1
            for item in itens
            if (
                item[
                    "status_tratativa"
                ]
                ==
                "RESOLVIDA"
            )
        )

        necessita_tratativa = any(
            item[
                "necessita_tratativa"
            ]
            for item in itens
        )

        # ----------------------------------------------------
        # RECORRÊNCIA
        #
        # Duas ou mais ocorrências para:
        # Localização + Código + Lote
        # ----------------------------------------------------

        recorrente = (
            total_ocorrencias
            >=
            2
        )

        # ----------------------------------------------------
        # ÚLTIMA OCORRÊNCIA
        # ----------------------------------------------------

        ultima_ocorrencia = max(
            itens,
            key=lambda item: (
                item[
                    "data_hora_criacao"
                ]
            )
        )

        # ----------------------------------------------------
        # TIPO PREDOMINANTE
        # ----------------------------------------------------

        contagem_tipos = {}

        for item in itens:

            tipo = _normalizar(
                item[
                    "tipo_divergencia"
                ]
            )

            if not tipo:
                continue

            contagem_tipos[tipo] = (
                contagem_tipos.get(
                    tipo,
                    0
                )
                +
                1
            )

        tipo_predominante = None

        if contagem_tipos:

            tipo_predominante = max(
                contagem_tipos,
                key=contagem_tipos.get,
            )

        # ----------------------------------------------------
        # STATUS CONSOLIDADO
        # ----------------------------------------------------

        if sem_justificativa > 0:

            status_consolidado = (
                "SEM_JUSTIFICATIVA"
            )

        elif justificadas_pendentes > 0:

            status_consolidado = (
                "JUSTIFICADA_PENDENTE_RESOLUCAO"
            )

        elif em_tratativa > 0:

            status_consolidado = (
                "EM_TRATATIVA"
            )

        elif resolvidas == total_ocorrencias:

            status_consolidado = (
                "RESOLVIDA"
            )

        else:

            status_consolidado = (
                "EM_TRATATIVA"
            )

        # ----------------------------------------------------
        # MONTAR TRATATIVA
        # ----------------------------------------------------

        tratativa = {
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

            "tipo_divergencia_predominante":
                tipo_predominante,

            "ocorrencias":
                total_ocorrencias,

            "recorrente":
                recorrente,

            "status_tratativa":
                status_consolidado,

            "necessita_tratativa":
                necessita_tratativa,

            "resumo": {
                "sem_justificativa":
                    sem_justificativa,

                "justificadas_pendentes":
                    justificadas_pendentes,

                "em_tratativa":
                    em_tratativa,

                "resolvidas":
                    resolvidas,
            },

            "ultima_ocorrencia": {
                "id_ocorrencia":
                    ultima_ocorrencia[
                        "id_ocorrencia"
                    ],

                "id_inventario":
                    ultima_ocorrencia[
                        "id_inventario"
                    ],

                "id_rodada":
                    ultima_ocorrencia[
                        "id_rodada"
                    ],

                "tipo_divergencia":
                    ultima_ocorrencia[
                        "tipo_divergencia"
                    ],

                "diferenca":
                    ultima_ocorrencia[
                        "diferenca"
                    ],

                "status_resolucao":
                    ultima_ocorrencia[
                        "status_resolucao"
                    ],

                "justificativa":
                    ultima_ocorrencia[
                        "justificativa"
                    ],

                "tipo_resolucao":
                    ultima_ocorrencia[
                        "tipo_resolucao"
                    ],

                "observacao_resolucao":
                    ultima_ocorrencia[
                        "observacao_resolucao"
                    ],

                "data_hora_criacao":
                    ultima_ocorrencia[
                        "data_hora_criacao"
                    ],

                "resolvido_por":
                    ultima_ocorrencia[
                        "resolvido_por"
                    ],

                "data_hora_resolucao":
                    ultima_ocorrencia[
                        "data_hora_resolucao"
                    ],
            },

            "historico_ocorrencias":
                list(
                    reversed(
                        itens
                    )
                ),
        }

        # ----------------------------------------------------
        # FILTRO: SOMENTE PENDENTES
        # ----------------------------------------------------

        if (
            somente_pendentes
            and
            not necessita_tratativa
        ):
            continue

        # ----------------------------------------------------
        # FILTRO: SOMENTE RECORRENTES
        # ----------------------------------------------------

        if (
            somente_recorrentes
            and
            not recorrente
        ):
            continue

        tratativas.append(
            tratativa
        )

    # ========================================================
    # ORDENAÇÃO
    # ========================================================

    ordem_status = {
        "SEM_JUSTIFICATIVA":
            1,

        "JUSTIFICADA_PENDENTE_RESOLUCAO":
            2,

        "EM_TRATATIVA":
            3,

        "RESOLVIDA":
            4,
    }

    tratativas.sort(
        key=lambda item: (
            0
            if item[
                "recorrente"
            ]
            else 1,

            ordem_status.get(
                item[
                    "status_tratativa"
                ],
                99,
            ),

            -item[
                "ocorrencias"
            ],

            item[
                "localizacao"
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

    # ========================================================
    # RESUMO
    # ========================================================

    grupos_sem_justificativa = sum(
        1
        for item in tratativas
        if (
            item[
                "status_tratativa"
            ]
            ==
            "SEM_JUSTIFICATIVA"
        )
    )

    grupos_justificados_pendentes = sum(
        1
        for item in tratativas
        if (
            item[
                "status_tratativa"
            ]
            ==
            "JUSTIFICADA_PENDENTE_RESOLUCAO"
        )
    )

    grupos_em_tratativa = sum(
        1
        for item in tratativas
        if (
            item[
                "status_tratativa"
            ]
            ==
            "EM_TRATATIVA"
        )
    )

    grupos_resolvidos = sum(
        1
        for item in tratativas
        if (
            item[
                "status_tratativa"
            ]
            ==
            "RESOLVIDA"
        )
    )

    grupos_recorrentes = sum(
        1
        for item in tratativas
        if item[
            "recorrente"
        ]
    )

    necessitam_tratativa = sum(
        1
        for item in tratativas
        if item[
            "necessita_tratativa"
        ]
    )

    # ========================================================
    # RETORNO
    # ========================================================

    return {
        "possui_ciclo_aberto":
            True,

        "pesquisa": {
            "cliente_id":
                cliente_id,

            "armazem":
                armazem,

            "somente_pendentes":
                somente_pendentes,

            "somente_recorrentes":
                somente_recorrentes,
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
        },

        "resumo": {
            "grupos_divergencia":
                len(
                    tratativas
                ),

            "ocorrencias":
                total_ocorrencias_consideradas,

            "sem_justificativa":
                grupos_sem_justificativa,

            "justificadas_pendentes":
                grupos_justificados_pendentes,

            "em_tratativa":
                grupos_em_tratativa,

            "resolvidas":
                grupos_resolvidos,

            "recorrentes":
                grupos_recorrentes,

            "necessitam_tratativa":
                necessitam_tratativa,
        },

        "tratativas":
            tratativas,
    }


# ============================================================
# RESOLVER STATUS A PARTIR DO TIPO DE RESOLUÇÃO
# ============================================================

def _resolver_status_resolucao(
    tipo_resolucao: str
):

    tipo = _normalizar(
        tipo_resolucao
    )

    if not tipo:

        raise ValueError(
            "Tipo de resolução é obrigatório."
        )

    # --------------------------------------------------------
    # RECONTAGEM
    # --------------------------------------------------------

    if tipo in (
        "RECONTAGEM",
        "RESOLVIDA_RECONTAGEM",
    ):

        return (
            "RESOLVIDA_RECONTAGEM"
        )

    # --------------------------------------------------------
    # AJUSTE
    # --------------------------------------------------------

    if tipo in (
        "AJUSTE",
        "AJUSTE_ESTOQUE",
        "AJUSTE_SALDO",
        "RESOLVIDA_AJUSTE",
    ):

        return (
            "RESOLVIDA_AJUSTE"
        )

    # --------------------------------------------------------
    # INVENTÁRIO OFICIAL
    # --------------------------------------------------------

    if tipo in (
        "OFICIAL",
        "INVENTARIO_OFICIAL",
        "RESOLVIDA_OFICIAL",
    ):

        return (
            "RESOLVIDA_OFICIAL"
        )

    raise ValueError(
        "Tipo de resolução inválido. "
        "Valores aceitos: RECONTAGEM, "
        "AJUSTE_ESTOQUE ou OFICIAL."
    )


# ============================================================
# RESOLVER OCORRÊNCIA DE DIVERGÊNCIA
# ============================================================

def resolver_ocorrencia_rotativo(
    conn,
    cursor,
    id_ocorrencia: int,
    tipo_resolucao: str,
    observacao_resolucao: str | None = None,
    resolvido_por: str | None = None,
    id_inventario_resolucao: int | None = None,
    id_rodada_resolucao: int | None = None,
):

    tipo_resolucao = _normalizar(
        tipo_resolucao
    )

    observacao_resolucao = (
        _txt(
            observacao_resolucao
        )
        or
        None
    )

    resolvido_por = (
        _txt(
            resolvido_por
        )
        or
        None
    )

    # ========================================================
    # VALIDAÇÕES
    # ========================================================

    if not id_ocorrencia:

        raise ValueError(
            "ID da ocorrência é obrigatório."
        )

    if not tipo_resolucao:

        raise ValueError(
            "Tipo de resolução é obrigatório."
        )

    if not resolvido_por:

        raise ValueError(
            "Usuário responsável pela resolução "
            "é obrigatório."
        )

    # ========================================================
    # STATUS FINAL
    # ========================================================

    status_resolucao_final = (
        _resolver_status_resolucao(
            tipo_resolucao
        )
    )

    # ========================================================
    # BUSCAR OCORRÊNCIA
    # ========================================================

    cursor.execute(
        """
        SELECT
            ID_Ocorrencia,
            ClienteId,
            ID_Inventario,
            ID_Rodada,
            TipoInventario,
            Localizacao,
            Codigo,
            Lote,
            QtdEstoque,
            QtdContada,
            Diferenca,
            TipoDivergencia,
            StatusResolucao,
            Justificativa,
            ID_DecisaoRotativo,
            ID_InventarioResolucao,
            ID_RodadaResolucao,
            TipoResolucao,
            ObservacaoResolucao,
            CriadoPor,
            DataHoraCriacao,
            ResolvidoPor,
            DataHoraResolucao

        FROM dbo.OcorrenciasDivergencia

        WHERE
            ID_Ocorrencia = ?
        """,
        (
            id_ocorrencia,
        )
    )

    ocorrencia = (
        cursor.fetchone()
    )

    if not ocorrencia:

        raise ValueError(
            "Ocorrência de divergência "
            "não encontrada."
        )

    # ========================================================
    # VALIDAR TIPO
    # ========================================================

    if (
        _normalizar(
            ocorrencia.TipoInventario
        )
        !=
        "ROTATIVO"
    ):

        raise ValueError(
            "A ocorrência informada não pertence "
            "a um inventário ROTATIVO."
        )

    # ========================================================
    # STATUS ATUAL
    # ========================================================

    status_atual = (
        _normalizar(
            ocorrencia.StatusResolucao
        )
    )

    # ========================================================
    # IDEMPOTÊNCIA
    # ========================================================

    if status_atual in STATUS_RESOLVIDOS:

        return {
            "resolvido":
                False,

            "motivo":
                "OCORRENCIA_JA_RESOLVIDA",

            "ocorrencia": {
                "id_ocorrencia":
                    ocorrencia.ID_Ocorrencia,

                "localizacao":
                    ocorrencia.Localizacao,

                "codigo":
                    ocorrencia.Codigo,

                "lote":
                    ocorrencia.Lote,

                "status_resolucao":
                    ocorrencia.StatusResolucao,

                "tipo_resolucao":
                    ocorrencia.TipoResolucao,

                "resolvido_por":
                    ocorrencia.ResolvidoPor,

                "data_hora_resolucao":
                    ocorrencia.DataHoraResolucao,
            },

            "inteligencia":
                None,
        }

    # ========================================================
    # SEGUNDA PROTEÇÃO DE IDEMPOTÊNCIA
    # ========================================================

    if (
        ocorrencia.DataHoraResolucao
        is not None
        and
        _txt(
            ocorrencia.TipoResolucao
        )
    ):

        return {
            "resolvido":
                False,

            "motivo":
                "OCORRENCIA_JA_RESOLVIDA",

            "ocorrencia": {
                "id_ocorrencia":
                    ocorrencia.ID_Ocorrencia,

                "localizacao":
                    ocorrencia.Localizacao,

                "codigo":
                    ocorrencia.Codigo,

                "lote":
                    ocorrencia.Lote,

                "status_resolucao":
                    ocorrencia.StatusResolucao,

                "tipo_resolucao":
                    ocorrencia.TipoResolucao,

                "resolvido_por":
                    ocorrencia.ResolvidoPor,

                "data_hora_resolucao":
                    ocorrencia.DataHoraResolucao,
            },

            "inteligencia":
                None,
        }

    # ========================================================
    # JUSTIFICATIVA OBRIGATÓRIA
    # ========================================================

    if not _txt(
        ocorrencia.Justificativa
    ):

        raise ValueError(
            "A ocorrência precisa possuir justificativa "
            "antes da resolução."
        )

    # ========================================================
    # VALIDAR IDs DE RESOLUÇÃO
    # ========================================================

    if (
        id_rodada_resolucao is not None
        and
        id_inventario_resolucao is None
    ):

        raise ValueError(
            "Ao informar id_rodada_resolucao, "
            "id_inventario_resolucao também deve "
            "ser informado."
        )

    # ========================================================
    # INVENTÁRIO DE RESOLUÇÃO
    # ========================================================

    if id_inventario_resolucao is not None:

        cursor.execute(
            """
            SELECT
                ID_Inventario,
                ClienteId

            FROM dbo.Inventarios

            WHERE
                ID_Inventario = ?
            """,
            (
                id_inventario_resolucao,
            )
        )

        inventario_resolucao = (
            cursor.fetchone()
        )

        if not inventario_resolucao:

            raise ValueError(
                "Inventário de resolução "
                "não encontrado."
            )

        if (
            inventario_resolucao.ClienteId
            !=
            ocorrencia.ClienteId
        ):

            raise ValueError(
                "O inventário de resolução pertence "
                "a outro cliente."
            )

    # ========================================================
    # RODADA DE RESOLUÇÃO
    # ========================================================

    if id_rodada_resolucao is not None:

        cursor.execute(
            """
            SELECT
                ID_Rodada,
                ID_Inventario

            FROM dbo.RodadasInventario

            WHERE
                ID_Rodada = ?
            """,
            (
                id_rodada_resolucao,
            )
        )

        rodada_resolucao = (
            cursor.fetchone()
        )

        if not rodada_resolucao:

            raise ValueError(
                "Rodada de resolução não encontrada."
            )

        if (
            rodada_resolucao.ID_Inventario
            !=
            id_inventario_resolucao
        ):

            raise ValueError(
                "A rodada de resolução não pertence "
                "ao inventário de resolução informado."
            )

    # ========================================================
    # RESOLVER OCORRÊNCIA
    #
    # IMPORTANTE:
    # primeiro concluímos a operação e realizamos COMMIT.
    # Depois executamos a inteligência.
    # ========================================================

    try:

        cursor.execute(
            """
            UPDATE dbo.OcorrenciasDivergencia

            SET
                StatusResolucao = ?,
                ID_InventarioResolucao = ?,
                ID_RodadaResolucao = ?,
                TipoResolucao = ?,
                ObservacaoResolucao = ?,
                ResolvidoPor = ?,
                DataHoraResolucao = SYSDATETIME()

            WHERE
                ID_Ocorrencia = ?

                AND StatusResolucao NOT IN (
                    'RESOLVIDA_RECONTAGEM',
                    'RESOLVIDA_AJUSTE',
                    'RESOLVIDA_OFICIAL'
                )

                AND DataHoraResolucao IS NULL
            """,
            (
                status_resolucao_final,
                id_inventario_resolucao,
                id_rodada_resolucao,
                tipo_resolucao,
                observacao_resolucao,
                resolvido_por,
                id_ocorrencia,
            )
        )

        if cursor.rowcount == 0:

            conn.rollback()

            raise ValueError(
                "A ocorrência não pôde ser resolvida. "
                "Ela pode já ter sido resolvida ou "
                "alterada por outro processo."
            )

        conn.commit()

    except Exception:

        conn.rollback()

        raise

    # ========================================================
    # RECUPERAR REGISTRO ATUALIZADO
    # ========================================================

    cursor.execute(
        """
        SELECT
            ID_Ocorrencia,
            ClienteId,
            ID_Inventario,
            ID_Rodada,
            TipoInventario,
            Localizacao,
            Codigo,
            Lote,
            Diferenca,
            TipoDivergencia,
            StatusResolucao,
            Justificativa,
            ID_InventarioResolucao,
            ID_RodadaResolucao,
            TipoResolucao,
            ObservacaoResolucao,
            ResolvidoPor,
            DataHoraResolucao

        FROM dbo.OcorrenciasDivergencia

        WHERE
            ID_Ocorrencia = ?
        """,
        (
            id_ocorrencia,
        )
    )

    atualizada = (
        cursor.fetchone()
    )

    if not atualizada:

        raise ValueError(
            "Ocorrência atualizada, mas não foi "
            "possível recuperar o registro."
        )

    # ========================================================
    # IDENTIFICAR ARMAZÉM
    #
    # OcorrenciasDivergencia ainda não possui cArmazem.
    # Portanto recuperamos pelo cadastro rotativo.
    # ========================================================

    cursor.execute(
        """
        SELECT TOP 1
            cArmazem

        FROM dbo.RotativoLocalizacoes

        WHERE
            ClienteId = ?

            AND UPPER(
                LTRIM(
                    RTRIM(Localizacao)
                )
            ) =
            UPPER(
                LTRIM(
                    RTRIM(?)
                )
            )

        ORDER BY
            ID_RotativoLocalizacao DESC
        """,
        (
            atualizada.ClienteId,
            atualizada.Localizacao,
        )
    )

    localizacao_rotativo = (
        cursor.fetchone()
    )

    armazem = (
        _normalizar(
            localizacao_rotativo.cArmazem
        )
        if localizacao_rotativo
        else None
    )

    # ========================================================
    # CLASSIFICAR RESULTADO
    # ========================================================

    classificacao_final = (
        _classificar_tratativa(
            status_resolucao=(
                atualizada.StatusResolucao
            ),
            justificativa=(
                atualizada.Justificativa
            ),
            tipo_resolucao=(
                atualizada.TipoResolucao
            ),
            data_hora_resolucao=(
                atualizada.DataHoraResolucao
            ),
        )
    )

    # ========================================================
    # INTELIGÊNCIA PÓS-RESOLUÇÃO
    #
    # A operação já está commitada.
    #
    # Falha de tendência/priorização/painel não deve desfazer
    # a resolução da ocorrência.
    # ========================================================

    inteligencia = None

    if armazem:

        try:

            inteligencia = (
                executar_orquestracao_rotativo(
                    conn=conn,
                    cursor=cursor,
                    cliente_id=(
                        atualizada.ClienteId
                    ),
                    armazem=armazem,
                    origem_evento=(
                        "RESOLUCAO_DIVERGENCIA"
                    ),
                    localizacao=(
                        atualizada.Localizacao
                    ),
                    id_ocorrencia=(
                        atualizada.ID_Ocorrencia
                    ),
                    id_inventario=(
                        atualizada.ID_Inventario
                    ),
                    id_rodada=(
                        atualizada.ID_Rodada
                    ),
                    usuario=(
                        atualizada.ResolvidoPor
                    ),
                    limite_score_sugestao=50.0,
                    quantidade_sugestoes=20,
                    retornar_painel=True,
                )
            )

        except Exception as erro:

            inteligencia = {
                "orquestrado":
                    False,

                "motivo":
                    "FALHA_ATUALIZACAO_INTELIGENCIA",

                "erro":
                    str(
                        erro
                    ),

                "mensagem":
                    (
                        "A ocorrência foi resolvida, "
                        "mas houve falha ao atualizar "
                        "a inteligência do rotativo."
                    ),
            }

    else:

        inteligencia = {
            "orquestrado":
                False,

            "motivo":
                "ARMAZEM_NAO_IDENTIFICADO",

            "erro":
                None,

            "mensagem":
                (
                    "A ocorrência foi resolvida, mas "
                    "não foi possível identificar o "
                    "armazém para recalcular a inteligência."
                ),
        }

    # ========================================================
    # RETORNO
    # ========================================================

    return {
        "resolvido":
            True,

        "motivo":
            "OCORRENCIA_RESOLVIDA",

        "ocorrencia": {
            "id_ocorrencia":
                atualizada.ID_Ocorrencia,

            "cliente_id":
                atualizada.ClienteId,

            "id_inventario":
                atualizada.ID_Inventario,

            "id_rodada":
                atualizada.ID_Rodada,

            "tipo_inventario":
                atualizada.TipoInventario,

            "localizacao":
                atualizada.Localizacao,

            "codigo":
                atualizada.Codigo,

            "lote":
                atualizada.Lote,

            "tipo_divergencia":
                atualizada.TipoDivergencia,

            "diferenca":
                (
                    float(
                        atualizada.Diferenca
                    )
                    if atualizada.Diferenca is not None
                    else None
                ),

            "status_resolucao":
                atualizada.StatusResolucao,

            "status_tratativa":
                classificacao_final[
                    "status_tratativa"
                ],

            "necessita_tratativa":
                classificacao_final[
                    "necessita_tratativa"
                ],

            "justificativa":
                atualizada.Justificativa,

            "tipo_resolucao":
                atualizada.TipoResolucao,

            "observacao_resolucao":
                atualizada.ObservacaoResolucao,

            "id_inventario_resolucao":
                atualizada.ID_InventarioResolucao,

            "id_rodada_resolucao":
                atualizada.ID_RodadaResolucao,

            "resolvido_por":
                atualizada.ResolvidoPor,

            "data_hora_resolucao":
                atualizada.DataHoraResolucao,
        },

        "inteligencia": {
            "executada":
                bool(
                    inteligencia
                    and
                    inteligencia.get(
                        "orquestrado"
                    )
                ),

            "motivo":
                (
                    inteligencia.get(
                        "motivo"
                    )
                    if inteligencia
                    else None
                ),

            "resultado":
                (
                    inteligencia
                    if (
                        inteligencia
                        and
                        inteligencia.get(
                            "orquestrado"
                        )
                    )
                    else None
                ),

            "erro":
                (
                    inteligencia.get(
                        "erro"
                    )
                    if inteligencia
                    else None
                ),

            "mensagem":
                (
                    inteligencia.get(
                        "mensagem"
                    )
                    if inteligencia
                    else None
                ),
        },
    }