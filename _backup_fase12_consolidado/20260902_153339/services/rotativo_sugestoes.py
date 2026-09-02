# ============================================================
# SUGESTÕES OPERACIONAIS DO INVENTÁRIO ROTATIVO
#
# V1.1
#
# Objetivos:
# - Consultar sugestões persistidas do ciclo aberto
# - Exibir progresso operacional do ciclo
# - Permitir filtros por risco e tipo de sugestão
# - Fornecer resposta simplificada para frontend / AppSheet
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


def _percentual(
    quantidade,
    total
):

    total = int(
        total
        or 0
    )

    quantidade = int(
        quantidade
        or 0
    )

    if total <= 0:
        return 0.0

    return round(
        (
            quantidade
            /
            total
        )
        * 100,
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

    armazem = _normalizar(
        armazem
    )

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
            PercentualCobertura,
            DataInicio,
            DataFimPrevista,
            DataFimReal,
            CriadoPor,
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
            armazem
        )
    )

    return cursor.fetchone()


# ============================================================
# RESUMO DO CICLO
# ============================================================

def _buscar_resumo_ciclo(
    cursor,
    id_ciclo: int
):

    cursor.execute(
        """
        SELECT
            COUNT(*) AS Total,

            SUM(
                CASE
                    WHEN UPPER(
                        LTRIM(
                            RTRIM(
                                Status
                            )
                        )
                    ) = 'PENDENTE'
                    THEN 1
                    ELSE 0
                END
            ) AS Pendentes,

            SUM(
                CASE
                    WHEN UPPER(
                        LTRIM(
                            RTRIM(
                                Status
                            )
                        )
                    ) = 'EM_CONTAGEM'
                    THEN 1
                    ELSE 0
                END
            ) AS EmContagem,

            SUM(
                CASE
                    WHEN UPPER(
                        LTRIM(
                            RTRIM(
                                Status
                            )
                        )
                    ) = 'CONTADA'
                    THEN 1
                    ELSE 0
                END
            ) AS Contadas,

            SUM(
                CASE
                    WHEN UPPER(
                        LTRIM(
                            RTRIM(
                                Status
                            )
                        )
                    ) = 'IGNORADA'
                    THEN 1
                    ELSE 0
                END
            ) AS Ignoradas,

            SUM(
                CASE
                    WHEN
                        UPPER(
                            LTRIM(
                                RTRIM(
                                    Status
                                )
                            )
                        ) = 'PENDENTE'
                        AND Sugerida = 1
                    THEN 1
                    ELSE 0
                END
            ) AS SugeridasPendentes,

            SUM(
                CASE
                    WHEN
                        UPPER(
                            LTRIM(
                                RTRIM(
                                    Status
                                )
                            )
                        ) = 'PENDENTE'
                        AND TipoSugestao = 'RISCO'
                    THEN 1
                    ELSE 0
                END
            ) AS SugestoesRiscoPendentes,

            SUM(
                CASE
                    WHEN
                        UPPER(
                            LTRIM(
                                RTRIM(
                                    Status
                                )
                            )
                        ) = 'PENDENTE'
                        AND TipoSugestao = 'COBERTURA_CICLO'
                    THEN 1
                    ELSE 0
                END
            ) AS SugestoesCoberturaPendentes,

            SUM(
                CASE
                    WHEN
                        UPPER(
                            LTRIM(
                                RTRIM(
                                    Status
                                )
                            )
                        ) = 'PENDENTE'
                        AND ClassificacaoRiscoEntrada = 'CRITICO'
                    THEN 1
                    ELSE 0
                END
            ) AS CriticasPendentes,

            SUM(
                CASE
                    WHEN
                        UPPER(
                            LTRIM(
                                RTRIM(
                                    Status
                                )
                            )
                        ) = 'PENDENTE'
                        AND ClassificacaoRiscoEntrada = 'ALTO'
                    THEN 1
                    ELSE 0
                END
            ) AS AltasPendentes,

            SUM(
                CASE
                    WHEN
                        UPPER(
                            LTRIM(
                                RTRIM(
                                    Status
                                )
                            )
                        ) = 'PENDENTE'
                        AND ClassificacaoRiscoEntrada = 'MEDIO'
                    THEN 1
                    ELSE 0
                END
            ) AS MediasPendentes,

            SUM(
                CASE
                    WHEN
                        UPPER(
                            LTRIM(
                                RTRIM(
                                    Status
                                )
                            )
                        ) = 'PENDENTE'
                        AND ClassificacaoRiscoEntrada = 'BAIXO'
                    THEN 1
                    ELSE 0
                END
            ) AS BaixasPendentes

        FROM dbo.CicloRotativoLocalizacoes
        WHERE
            ID_Ciclo = ?
        """,
        (
            id_ciclo,
        )
    )

    return cursor.fetchone()


# ============================================================
# BUSCAR ÚLTIMA CONTAGEM DA LOCALIZAÇÃO
# ============================================================

def _buscar_cadastro_localizacao(
    cursor,
    id_rotativo_localizacao: int
):

    cursor.execute(
        """
        SELECT
            ID_RotativoLocalizacao,
            UltimaContagem,
            ID_InventarioUltimaContagem,
            ID_RodadaUltimaContagem,
            ScoreRisco,
            ClassificacaoRisco,
            Sugerida,
            Prioridade,
            TipoSugestao
        FROM dbo.RotativoLocalizacoes
        WHERE
            ID_RotativoLocalizacao = ?
        """,
        (
            id_rotativo_localizacao,
        )
    )

    return cursor.fetchone()


# ============================================================
# MOTIVO PRINCIPAL
# ============================================================

def _motivo_principal(
    ultima_contagem,
    tipo_sugestao,
    classificacao_risco,
    score_risco
):

    tipo_sugestao = _normalizar(
        tipo_sugestao
    )

    classificacao_risco = _normalizar(
        classificacao_risco
    )

    if ultima_contagem is None:
        return "Localização nunca contada"

    if tipo_sugestao == "RISCO":

        if classificacao_risco in (
            "CRITICO",
            "ALTO"
        ):
            return (
                "Localização priorizada por risco "
                f"{classificacao_risco.lower()}"
            )

        return (
            "Localização priorizada pelo score de risco"
        )

    if tipo_sugestao == "COBERTURA_CICLO":
        return (
            "Localização priorizada para cobertura do ciclo"
        )

    if (
        score_risco is not None
        and float(score_risco) >= 50
    ):
        return (
            "Localização com score de risco elevado"
        )

    return (
        "Localização priorizada para continuidade do ciclo"
    )


# ============================================================
# CONSULTAR SUGESTÕES ROTATIVAS
# ============================================================

def consultar_sugestoes_rotativo(
    cursor,
    cliente_id: int,
    armazem: str,
    limite: int = 5,
    tipo_sugestao: str | None = None,
    classificacao_risco: str | None = None,
    somente_pendentes: bool = True
):

    armazem = _normalizar(
        armazem
    )

    tipo_sugestao = (
        _normalizar(
            tipo_sugestao
        )
        or None
    )

    classificacao_risco = (
        _normalizar(
            classificacao_risco
        )
        or None
    )

    # ========================================================
    # VALIDAÇÕES
    # ========================================================

    if not armazem:
        raise ValueError(
            "Armazém é obrigatório."
        )

    if limite < 1:
        raise ValueError(
            "O limite deve ser maior que zero."
        )

    if limite > 100:
        raise ValueError(
            "O limite máximo permitido é 100."
        )

    if (
        tipo_sugestao is not None
        and tipo_sugestao not in (
            "RISCO",
            "COBERTURA_CICLO",
        )
    ):
        raise ValueError(
            "tipo_sugestao deve ser "
            "'RISCO' ou 'COBERTURA_CICLO'."
        )

    if (
        classificacao_risco is not None
        and classificacao_risco not in (
            "CRITICO",
            "ALTO",
            "MEDIO",
            "BAIXO",
        )
    ):
        raise ValueError(
            "classificacao_risco deve ser "
            "'CRITICO', 'ALTO', 'MEDIO' ou 'BAIXO'."
        )

    # ========================================================
    # CICLO ABERTO
    # ========================================================

    ciclo = _buscar_ciclo_aberto(
        cursor=cursor,
        cliente_id=cliente_id,
        armazem=armazem
    )

    if not ciclo:

        return {
            "possui_ciclo_aberto":
                False,

            "pesquisa": {
                "cliente_id":
                    cliente_id,

                "armazem":
                    armazem,

                "limite":
                    limite,

                "tipo_sugestao":
                    tipo_sugestao,

                "classificacao_risco":
                    classificacao_risco,

                "somente_pendentes":
                    somente_pendentes,
            },

            "ciclo":
                None,

            "progresso": {
                "total_localizacoes": 0,
                "contadas": 0,
                "ignoradas": 0,
                "em_contagem": 0,
                "pendentes": 0,
                "processadas": 0,
                "percentual_contado": 0.0,
                "percentual_processado": 0.0,
                "percentual_pendente": 0.0,
            },

            "resumo": {
                "sugeridas_pendentes": 0,
                "sugestoes_por_risco": 0,
                "sugestoes_por_cobertura": 0,
                "sugestoes_retornadas": 0,
            },

            "sugestao_principal":
                None,

            "proximas_sugestoes":
                [],
        }

    # ========================================================
    # RESUMO DO CICLO
    # ========================================================

    resumo = _buscar_resumo_ciclo(
        cursor=cursor,
        id_ciclo=ciclo.ID_Ciclo
    )

    total = int(
        resumo.Total
        or 0
    )

    pendentes = int(
        resumo.Pendentes
        or 0
    )

    em_contagem = int(
        resumo.EmContagem
        or 0
    )

    contadas = int(
        resumo.Contadas
        or 0
    )

    ignoradas = int(
        resumo.Ignoradas
        or 0
    )

    sugeridas_pendentes = int(
        resumo.SugeridasPendentes
        or 0
    )

    sugestoes_risco_pendentes = int(
        resumo.SugestoesRiscoPendentes
        or 0
    )

    sugestoes_cobertura_pendentes = int(
        resumo.SugestoesCoberturaPendentes
        or 0
    )

    criticas_pendentes = int(
        resumo.CriticasPendentes
        or 0
    )

    altas_pendentes = int(
        resumo.AltasPendentes
        or 0
    )

    medias_pendentes = int(
        resumo.MediasPendentes
        or 0
    )

    baixas_pendentes = int(
        resumo.BaixasPendentes
        or 0
    )

    processadas = (
        contadas
        +
        ignoradas
    )

    # ========================================================
    # MONTAR QUERY DINÂMICA
    # ========================================================

    filtros = [
        "ID_Ciclo = ?",
        "Sugerida = 1",
    ]

    parametros = [
        ciclo.ID_Ciclo,
    ]

    if somente_pendentes:

        filtros.append(
            """
            UPPER(
                LTRIM(
                    RTRIM(
                        Status
                    )
                )
            ) = 'PENDENTE'
            """
        )

    if tipo_sugestao is not None:

        filtros.append(
            """
            UPPER(
                LTRIM(
                    RTRIM(
                        TipoSugestao
                    )
                )
            ) = ?
            """
        )

        parametros.append(
            tipo_sugestao
        )

    if classificacao_risco is not None:

        filtros.append(
            """
            UPPER(
                LTRIM(
                    RTRIM(
                        ClassificacaoRiscoEntrada
                    )
                )
            ) = ?
            """
        )

        parametros.append(
            classificacao_risco
        )

    where_sql = (
        " AND ".join(
            filtros
        )
    )

    # ========================================================
    # BUSCAR SUGESTÕES
    # ========================================================

    sql = f"""
        SELECT TOP ({int(limite)})
            ID_CicloLocalizacao,
            ID_RotativoLocalizacao,
            Localizacao,
            Status,

            ScoreRiscoEntrada,
            ClassificacaoRiscoEntrada,

            Sugerida,
            Prioridade,
            TipoSugestao,

            DataInclusao,
            DataInicioContagem,
            DataConclusao,

            ID_Inventario,
            ID_Rodada,
            UsuarioContagem,

            DataHoraAtualizacao

        FROM dbo.CicloRotativoLocalizacoes

        WHERE
            {where_sql}

        ORDER BY
            ISNULL(
                Prioridade,
                999999
            ),

            CASE
                WHEN ClassificacaoRiscoEntrada = 'CRITICO'
                THEN 1

                WHEN ClassificacaoRiscoEntrada = 'ALTO'
                THEN 2

                WHEN ClassificacaoRiscoEntrada = 'MEDIO'
                THEN 3

                WHEN ClassificacaoRiscoEntrada = 'BAIXO'
                THEN 4

                ELSE 5
            END,

            ISNULL(
                ScoreRiscoEntrada,
                0
            ) DESC,

            Localizacao
    """

    cursor.execute(
        sql,
        tuple(
            parametros
        )
    )

    linhas = cursor.fetchall()

    # ========================================================
    # MONTAR SUGESTÕES
    # ========================================================

    sugestoes = []

    for linha in linhas:

        cadastro = (
            _buscar_cadastro_localizacao(
                cursor=cursor,
                id_rotativo_localizacao=(
                    linha.ID_RotativoLocalizacao
                )
            )
        )

        ultima_contagem = (
            cadastro.UltimaContagem
            if cadastro
            else None
        )

        score_risco = (
            float(
                linha.ScoreRiscoEntrada
            )
            if linha.ScoreRiscoEntrada is not None
            else None
        )

        tipo = (
            _normalizar(
                linha.TipoSugestao
            )
            or None
        )

        classificacao = (
            _normalizar(
                linha.ClassificacaoRiscoEntrada
            )
            or None
        )

        motivo = _motivo_principal(
            ultima_contagem=ultima_contagem,
            tipo_sugestao=tipo,
            classificacao_risco=classificacao,
            score_risco=score_risco
        )

        sugestoes.append(
            {
                "id_ciclo_localizacao":
                    linha.ID_CicloLocalizacao,

                "id_rotativo_localizacao":
                    linha.ID_RotativoLocalizacao,

                "localizacao":
                    linha.Localizacao,

                "status":
                    linha.Status,

                "prioridade":
                    linha.Prioridade,

                "score_risco":
                    score_risco,

                "classificacao_risco":
                    classificacao,

                "tipo_sugestao":
                    tipo,

                "ultima_contagem":
                    ultima_contagem,

                "id_inventario_ultima_contagem":
                    (
                        cadastro.ID_InventarioUltimaContagem
                        if cadastro
                        else None
                    ),

                "id_rodada_ultima_contagem":
                    (
                        cadastro.ID_RodadaUltimaContagem
                        if cadastro
                        else None
                    ),

                "motivo_principal":
                    motivo,

                "dados_ciclo": {
                    "data_inclusao":
                        linha.DataInclusao,

                    "data_inicio_contagem":
                        linha.DataInicioContagem,

                    "data_conclusao":
                        linha.DataConclusao,

                    "id_inventario":
                        linha.ID_Inventario,

                    "id_rodada":
                        linha.ID_Rodada,

                    "usuario_contagem":
                        linha.UsuarioContagem,

                    "data_hora_atualizacao":
                        linha.DataHoraAtualizacao,
                },
            }
        )

    # ========================================================
    # PRINCIPAL / PRÓXIMAS
    # ========================================================

    sugestao_principal = (
        sugestoes[0]
        if sugestoes
        else None
    )

    proximas_sugestoes = (
        sugestoes[1:]
        if len(
            sugestoes
        ) > 1
        else []
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

            "limite":
                limite,

            "tipo_sugestao":
                tipo_sugestao,

            "classificacao_risco":
                classificacao_risco,

            "somente_pendentes":
                somente_pendentes,
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

            "data_fim_real":
                ciclo.DataFimReal,

            "criado_por":
                ciclo.CriadoPor,

            "finalizado_por":
                ciclo.FinalizadoPor,

            "total_localizacoes":
                ciclo.TotalLocalizacoes,

            "localizacoes_contadas":
                ciclo.LocalizacoesContadas,

            "percentual_cobertura":
                float(
                    ciclo.PercentualCobertura
                    or 0
                ),
        },

        "progresso": {
            "total_localizacoes":
                total,

            "contadas":
                contadas,

            "ignoradas":
                ignoradas,

            "em_contagem":
                em_contagem,

            "pendentes":
                pendentes,

            "processadas":
                processadas,

            "percentual_contado":
                _percentual(
                    contadas,
                    total
                ),

            "percentual_processado":
                _percentual(
                    processadas,
                    total
                ),

            "percentual_pendente":
                _percentual(
                    pendentes,
                    total
                ),
        },

        "resumo": {
            "sugeridas_pendentes":
                sugeridas_pendentes,

            "sugestoes_por_risco":
                sugestoes_risco_pendentes,

            "sugestoes_por_cobertura":
                sugestoes_cobertura_pendentes,

            "sugestoes_retornadas":
                len(
                    sugestoes
                ),

            "risco_pendente": {
                "critico":
                    criticas_pendentes,

                "alto":
                    altas_pendentes,

                "medio":
                    medias_pendentes,

                "baixo":
                    baixas_pendentes,
            },
        },

        "sugestao_principal":
            sugestao_principal,

        "proximas_sugestoes":
            proximas_sugestoes,
    }