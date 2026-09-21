from domain.exceptions import BusinessRuleViolation
# ============================================================
# PAINEL GERENCIAL DO INVENTÁRIO ROTATIVO
# ============================================================

from services.rotativo_tendencia import (
    consultar_tendencias_rotativo,
)
from services.rotativo_contexto import (
    montar_contexto_localizacao_rotativo,
    _buscar_ocorrencias_localizacao,
    _montar_ocorrencias,
    _agrupar_divergencias,
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


def _percentual(qtd, total):

    qtd = int(qtd or 0)
    total = int(total or 0)

    if total <= 0:
        return 0.0

    return round(
        qtd / total * 100,
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
            AND UPPER(LTRIM(RTRIM(cArmazem))) = ?
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
# CONSULTAR PAINEL
# ============================================================

def consultar_painel_rotativo(
    cursor,
    cliente_id: int,
    armazem: str,
    limite_prioridades: int = 5
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

    if limite_prioridades < 1:
        raise BusinessRuleViolation(
            "limite_prioridades deve ser maior que zero."
        )

    if limite_prioridades > 50:
        raise BusinessRuleViolation(
            "limite_prioridades máximo permitido é 50."
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
            "possui_ciclo_aberto": False,
            "ciclo": None,
            "progresso": None,
            "risco": None,
            "historico": None,
            "execucao_dia": None,
            "backlog": None,
            "tendencias": None,
            "tratativas": None,
            "eficacia": None,
            "alerta_principal": None,
            "alerta_tratativa": None,
            "sugestao_principal": None,
            "top_prioridades": []
        }

    id_ciclo = ciclo.ID_Ciclo

    # ========================================================
    # PROGRESSO DO CICLO
    # ========================================================

    cursor.execute(
        """
        SELECT
            COUNT(*) AS Total,

            SUM(
                CASE
                    WHEN UPPER(LTRIM(RTRIM(Status))) = 'PENDENTE'
                    THEN 1
                    ELSE 0
                END
            ) AS Pendentes,

            SUM(
                CASE
                    WHEN UPPER(LTRIM(RTRIM(Status))) = 'EM_CONTAGEM'
                    THEN 1
                    ELSE 0
                END
            ) AS EmContagem,

            SUM(
                CASE
                    WHEN UPPER(LTRIM(RTRIM(Status))) = 'CONTADA'
                    THEN 1
                    ELSE 0
                END
            ) AS Contadas,

            SUM(
                CASE
                    WHEN UPPER(LTRIM(RTRIM(Status))) = 'IGNORADA'
                    THEN 1
                    ELSE 0
                END
            ) AS Ignoradas

        FROM dbo.CicloRotativoLocalizacoes

        WHERE
            ID_Ciclo = ?
        """,
        (
            id_ciclo,
        )
    )

    progresso_db = cursor.fetchone()

    total = int(
        progresso_db.Total
        or 0
    )

    pendentes = int(
        progresso_db.Pendentes
        or 0
    )

    em_contagem = int(
        progresso_db.EmContagem
        or 0
    )

    contadas = int(
        progresso_db.Contadas
        or 0
    )

    ignoradas = int(
        progresso_db.Ignoradas
        or 0
    )

    processadas = (
        contadas
        +
        ignoradas
    )

    # ========================================================
    # RISCO DAS LOCALIZAÇÕES PENDENTES
    # ========================================================

    cursor.execute(
        """
        SELECT

            SUM(
                CASE
                    WHEN UPPER(
                        LTRIM(
                            RTRIM(
                                ClassificacaoRiscoEntrada
                            )
                        )
                    ) = 'CRITICO'
                    THEN 1
                    ELSE 0
                END
            ) AS Critico,

            SUM(
                CASE
                    WHEN UPPER(
                        LTRIM(
                            RTRIM(
                                ClassificacaoRiscoEntrada
                            )
                        )
                    ) = 'ALTO'
                    THEN 1
                    ELSE 0
                END
            ) AS Alto,

            SUM(
                CASE
                    WHEN UPPER(
                        LTRIM(
                            RTRIM(
                                ClassificacaoRiscoEntrada
                            )
                        )
                    ) = 'MEDIO'
                    THEN 1
                    ELSE 0
                END
            ) AS Medio,

            SUM(
                CASE
                    WHEN UPPER(
                        LTRIM(
                            RTRIM(
                                ClassificacaoRiscoEntrada
                            )
                        )
                    ) = 'BAIXO'
                    THEN 1
                    ELSE 0
                END
            ) AS Baixo,

            SUM(
                CASE
                    WHEN UPPER(
                        LTRIM(
                            RTRIM(
                                TipoSugestao
                            )
                        )
                    ) = 'RISCO'
                    THEN 1
                    ELSE 0
                END
            ) AS SugestaoRisco,

            SUM(
                CASE
                    WHEN UPPER(
                        LTRIM(
                            RTRIM(
                                TipoSugestao
                            )
                        )
                    ) = 'COBERTURA_CICLO'
                    THEN 1
                    ELSE 0
                END
            ) AS SugestaoCobertura

        FROM dbo.CicloRotativoLocalizacoes

        WHERE
            ID_Ciclo = ?
            AND UPPER(
                LTRIM(
                    RTRIM(Status)
                )
            ) = 'PENDENTE'
        """,
        (
            id_ciclo,
        )
    )

    risco_db = cursor.fetchone()

    critico = int(
        risco_db.Critico
        or 0
    )

    alto = int(
        risco_db.Alto
        or 0
    )

    medio = int(
        risco_db.Medio
        or 0
    )

    baixo = int(
        risco_db.Baixo
        or 0
    )

    sugestoes_risco = int(
        risco_db.SugestaoRisco
        or 0
    )

    sugestoes_cobertura = int(
        risco_db.SugestaoCobertura
        or 0
    )

    # ========================================================
    # HISTÓRICO DAS LOCALIZAÇÕES
    # ========================================================

    cursor.execute(
        """
        WITH HistoricoPorLocalizacao AS (

            SELECT
                ID_RotativoLocalizacao,

                COUNT(*) AS TotalContagens,

                SUM(
                    CASE
                        WHEN PossuiDivergencia = 1
                        THEN 1
                        ELSE 0
                    END
                ) AS TotalDivergencias

            FROM dbo.RotativoHistoricoLocalizacoes

            GROUP BY
                ID_RotativoLocalizacao
        )

        SELECT
            COUNT(*) AS Total,

            SUM(
                CASE
                    WHEN rl.UltimaContagem IS NULL
                    THEN 1
                    ELSE 0
                END
            ) AS NuncaContadas,

            SUM(
                CASE
                    WHEN ISNULL(
                        hp.TotalDivergencias,
                        0
                    ) >= 1
                    THEN 1
                    ELSE 0
                END
            ) AS ComDivergenciaHistorica,

            SUM(
                CASE
                    WHEN ISNULL(
                        hp.TotalDivergencias,
                        0
                    ) >= 2
                    THEN 1
                    ELSE 0
                END
            ) AS ComRecorrencia

        FROM dbo.CicloRotativoLocalizacoes crl

        INNER JOIN dbo.RotativoLocalizacoes rl
            ON rl.ID_RotativoLocalizacao =
               crl.ID_RotativoLocalizacao

        LEFT JOIN HistoricoPorLocalizacao hp
            ON hp.ID_RotativoLocalizacao =
               rl.ID_RotativoLocalizacao

        WHERE
            crl.ID_Ciclo = ?
        """,
        (
            id_ciclo,
        )
    )

    historico_db = cursor.fetchone()

    nunca_contadas = int(
        historico_db.NuncaContadas
        or 0
    )

    divergencia_historica = int(
        historico_db.ComDivergenciaHistorica
        or 0
    )

    recorrencia = int(
        historico_db.ComRecorrencia
        or 0
    )

    # ========================================================
    # EXECUÇÃO DO DIA
    # ========================================================

    cursor.execute(
        """
        SELECT

            SUM(
                CASE
                    WHEN
                        UPPER(
                            LTRIM(
                                RTRIM(Status)
                            )
                        ) = 'CONTADA'
                        AND DataConclusao IS NOT NULL
                        AND CAST(
                            DataConclusao AS date
                        ) = CAST(
                            GETDATE() AS date
                        )
                    THEN 1
                    ELSE 0
                END
            ) AS ContadasHoje,

            SUM(
                CASE
                    WHEN
                        UPPER(
                            LTRIM(
                                RTRIM(Status)
                            )
                        ) = 'IGNORADA'
                        AND CAST(
                            DataHoraAtualizacao AS date
                        ) = CAST(
                            GETDATE() AS date
                        )
                    THEN 1
                    ELSE 0
                END
            ) AS IgnoradasHoje,

            AVG(
                CASE
                    WHEN
                        UPPER(
                            LTRIM(
                                RTRIM(Status)
                            )
                        ) = 'CONTADA'
                        AND DataInicioContagem IS NOT NULL
                        AND DataConclusao IS NOT NULL
                        AND CAST(
                            DataConclusao AS date
                        ) = CAST(
                            GETDATE() AS date
                        )
                    THEN
                        DATEDIFF(
                            SECOND,
                            DataInicioContagem,
                            DataConclusao
                        ) / 60.0
                    ELSE NULL
                END
            ) AS TempoMedioMinutos

        FROM dbo.CicloRotativoLocalizacoes

        WHERE
            ID_Ciclo = ?
        """,
        (
            id_ciclo,
        )
    )

    execucao_db = cursor.fetchone()

    contadas_hoje = int(
        execucao_db.ContadasHoje
        or 0
    )

    ignoradas_hoje = int(
        execucao_db.IgnoradasHoje
        or 0
    )

    tempo_medio = round(
        float(
            execucao_db.TempoMedioMinutos
            or 0
        ),
        2
    )

    # ========================================================
    # DIVERGÊNCIAS REGISTRADAS HOJE
    # ========================================================

    cursor.execute(
        """
        SELECT
            COUNT(
                DISTINCT
                rh.ID_RotativoLocalizacao
            ) AS LocalizacoesComDivergenciaHoje

        FROM dbo.RotativoHistoricoLocalizacoes rh

        INNER JOIN dbo.CicloRotativoLocalizacoes crl
            ON crl.ID_RotativoLocalizacao =
               rh.ID_RotativoLocalizacao

        WHERE
            crl.ID_Ciclo = ?
            AND rh.PossuiDivergencia = 1
            AND CAST(
                rh.DataHoraContagem AS date
            ) = CAST(
                GETDATE() AS date
            )
        """,
        (
            id_ciclo,
        )
    )

    divergencia_hoje_db = cursor.fetchone()

    divergencias_hoje = int(
        divergencia_hoje_db.LocalizacoesComDivergenciaHoje
        or 0
    )

    # ========================================================
    # PRODUTIVIDADE POR USUÁRIO HOJE
    # ========================================================

    cursor.execute(
        """
        SELECT
            UsuarioContagem,

            COUNT(*) AS LocalizacoesContadas

        FROM dbo.CicloRotativoLocalizacoes

        WHERE
            ID_Ciclo = ?
            AND UPPER(
                LTRIM(
                    RTRIM(Status)
                )
            ) = 'CONTADA'
            AND DataConclusao IS NOT NULL
            AND CAST(
                DataConclusao AS date
            ) = CAST(
                GETDATE() AS date
            )
            AND UsuarioContagem IS NOT NULL
            AND LTRIM(
                RTRIM(UsuarioContagem)
            ) <> ''

        GROUP BY
            UsuarioContagem

        ORDER BY
            LocalizacoesContadas DESC,
            UsuarioContagem
        """,
        (
            id_ciclo,
        )
    )

    produtividade_db = cursor.fetchall()

    produtividade = []

    for linha in produtividade_db:

        produtividade.append(
            {
                "usuario":
                    linha.UsuarioContagem,

                "localizacoes_contadas":
                    int(
                        linha.LocalizacoesContadas
                        or 0
                    )
            }
        )

    usuarios_ativos = len(
        produtividade
    )

    # ========================================================
    # TOP PRIORIDADES
    # ========================================================

    sql_prioridades = f"""
        SELECT TOP ({int(limite_prioridades)})
            crl.ID_CicloLocalizacao,
            crl.ID_RotativoLocalizacao,
            crl.Localizacao,
            crl.Status,
            crl.ScoreRiscoEntrada,
            crl.ClassificacaoRiscoEntrada,
            crl.Sugerida,
            crl.Prioridade,
            crl.TipoSugestao,
            rl.UltimaContagem,
            rl.ID_InventarioUltimaContagem,
            rl.ID_RodadaUltimaContagem

        FROM dbo.CicloRotativoLocalizacoes crl

        INNER JOIN dbo.RotativoLocalizacoes rl
            ON rl.ID_RotativoLocalizacao =
               crl.ID_RotativoLocalizacao

        WHERE
            crl.ID_Ciclo = ?
            AND UPPER(
                LTRIM(
                    RTRIM(crl.Status)
                )
            ) = 'PENDENTE'
            AND crl.Sugerida = 1

        ORDER BY
            ISNULL(
                crl.Prioridade,
                999999
            ),
            ISNULL(
                crl.ScoreRiscoEntrada,
                0
            ) DESC,
            crl.Localizacao
    """

    cursor.execute(
        sql_prioridades,
        (
            id_ciclo,
        )
    )

    prioridades_db = cursor.fetchall()

    prioridades = []

    for linha in prioridades_db:

        ultima_contagem = (
            linha.UltimaContagem
        )

        if (
            _normalizar(
                linha.TipoSugestao
            )
            ==
            "RISCO"
        ):

            motivo = (
                "Localização priorizada por risco"
            )

        elif ultima_contagem is None:

            motivo = (
                "Localização nunca contada"
            )

        else:

            motivo = (
                "Localização priorizada "
                "para cobertura do ciclo"
            )

        prioridades.append(
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
                    (
                        float(
                            linha.ScoreRiscoEntrada
                        )
                        if linha.ScoreRiscoEntrada is not None
                        else None
                    ),

                "classificacao_risco":
                    linha.ClassificacaoRiscoEntrada,

                "tipo_sugestao":
                    linha.TipoSugestao,

                "ultima_contagem":
                    ultima_contagem,

                "id_inventario_ultima_contagem":
                    linha.ID_InventarioUltimaContagem,

                "id_rodada_ultima_contagem":
                    linha.ID_RodadaUltimaContagem,

                "motivo":
                    motivo,
            }
        )

    # ========================================================
    # SUGESTÃO PRINCIPAL
    # ========================================================

    sugestao_principal = (
        prioridades[0]
        if prioridades
        else None
    )

    # ========================================================
    # BACKLOG
    # ========================================================

    risco_alto_critico = (
        critico
        +
        alto
    )

    # ========================================================
    # TENDÊNCIAS DAS LOCALIZAÇÕES
    # ========================================================

    analise_tendencias = consultar_tendencias_rotativo(
        cursor=cursor,
        cliente_id=cliente_id,
        armazem=armazem,
        limite_historico=6,
        somente_alertas=False
    )

    resumo_tendencias = (
        analise_tendencias.get(
            "resumo",
            {}
        )
        or {}
    )

    lista_tendencias = (
        analise_tendencias.get(
            "tendencias",
            []
        )
        or []
    )

    tendencias_painel = {
        "sem_historico":
            int(
                resumo_tendencias.get(
                    "sem_historico",
                    0
                )
                or 0
            ),

        "estaveis":
            int(
                resumo_tendencias.get(
                    "estaveis",
                    0
                )
                or 0
            ),

        "atencao":
            int(
                resumo_tendencias.get(
                    "atencao",
                    0
                )
                or 0
            ),

        "recorrentes":
            int(
                resumo_tendencias.get(
                    "recorrentes",
                    0
                )
                or 0
            ),

        "deteriorando":
            int(
                resumo_tendencias.get(
                    "deteriorando",
                    0
                )
                or 0
            ),

        "melhorando":
            int(
                resumo_tendencias.get(
                    "melhorando",
                    0
                )
                or 0
            ),
    }

    tendencias_painel["alertas"] = (
        tendencias_painel["atencao"]
        +
        tendencias_painel["recorrentes"]
        +
        tendencias_painel["deteriorando"]
    )

    # ========================================================
    # ALERTA PRINCIPAL
    # ========================================================

    alerta_principal = None

    ordem_alerta = {
        "DETERIORANDO": 1,
        "RECORRENTE": 2,
        "ATENCAO": 3,
    }

    candidatos_alerta = [
        item
        for item in lista_tendencias
        if item.get(
            "classificacao_tendencia"
        )
        in ordem_alerta
    ]

    candidatos_alerta.sort(
        key=lambda item: (
            ordem_alerta.get(
                item.get(
                    "classificacao_tendencia"
                ),
                99
            ),

            item.get(
                "prioridade"
            )
            if item.get(
                "prioridade"
            ) is not None
            else 999999,

            -float(
                item.get(
                    "score_risco"
                )
                or 0
            ),

            item.get(
                "localizacao"
            )
            or ""
        )
    )

    if candidatos_alerta:

        principal = candidatos_alerta[0]

        motivos = (
            principal.get(
                "motivos"
            )
            or []
        )

        historico_alerta = (
            principal.get(
                "historico"
            )
            or {}
        )

        alerta_principal = {
            "localizacao":
                principal.get(
                    "localizacao"
                ),

            "classificacao_tendencia":
                principal.get(
                    "classificacao_tendencia"
                ),

            "direcao":
                principal.get(
                    "direcao"
                ),

            "score_risco":
                principal.get(
                    "score_risco"
                ),

            "classificacao_risco":
                principal.get(
                    "classificacao_risco"
                ),

            "prioridade":
                principal.get(
                    "prioridade"
                ),

            "tipo_sugestao":
                principal.get(
                    "tipo_sugestao"
                ),

            "divergencias_consecutivas":
                historico_alerta.get(
                    "divergencias_consecutivas",
                    0
                ),

            "taxa_divergencia_recente_percentual":
                historico_alerta.get(
                    "taxa_divergencia_recente_percentual",
                    0
                ),

            "ultima_divergencia":
                historico_alerta.get(
                    "ultima_divergencia"
                ),

            "motivo_principal":
                (
                    motivos[0]
                    if motivos
                    else None
                ),

            "motivos":
                motivos,
        }

    # ========================================================
    # INDICADORES INTEGRADOS A PARTIR DAS TENDENCIAS
    #
    # A analise de tendencias ja montou o contexto completo
    # de todas as localizacoes do ciclo. O painel reutiliza
    # esses agregados e evita uma segunda varredura N+1.
    # ========================================================

    localizacoes_com_recorrencia = sum(
        1
        for item in lista_tendencias
        if bool(
            (
                item.get(
                    "recorrencia",
                    {}
                )
                or {}
            ).get(
                "possui_recorrencia_item_lote",
                False
            )
        )
    )

    localizacoes_com_tratativa_pendente = sum(
        1
        for item in lista_tendencias
        if bool(
            (
                item.get(
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

    ocorrencias_pendentes = sum(
        int(
            (
                item.get(
                    "tratativa",
                    {}
                )
                or {}
            ).get(
                "ocorrencias_pendentes",
                0
            )
            or 0
        )
        for item in lista_tendencias
    )

    ocorrencias_resolvidas = sum(
        int(
            (
                item.get(
                    "tratativa",
                    {}
                )
                or {}
            ).get(
                "ocorrencias_resolvidas",
                0
            )
            or 0
        )
        for item in lista_tendencias
    )

    grupos_recorrentes = sum(
        int(
            (
                item.get(
                    "recorrencia",
                    {}
                )
                or {}
            ).get(
                "grupos_recorrentes",
                0
            )
            or 0
        )
        for item in lista_tendencias
    )

    grupos_pendentes = sum(
        int(
            (
                item.get(
                    "tratativa",
                    {}
                )
                or {}
            ).get(
                "grupos_pendentes",
                0
            )
            or 0
        )
        for item in lista_tendencias
    )

    # ========================================================
    # INDICADORES DE EFICACIA
    # ========================================================

    resolucoes_avaliadas = sum(
        int(
            (
                item.get(
                    "eficacia",
                    {}
                )
                or {}
            ).get(
                "resolucoes_avaliadas",
                0
            )
            or 0
        )
        for item in lista_tendencias
    )

    eficazes = sum(
        int(
            (
                item.get(
                    "eficacia",
                    {}
                )
                or {}
            ).get(
                "eficazes",
                0
            )
            or 0
        )
        for item in lista_tendencias
    )

    nao_eficazes = sum(
        int(
            (
                item.get(
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
        for item in lista_tendencias
    )

    sem_evidencia = sum(
        int(
            (
                item.get(
                    "eficacia",
                    {}
                )
                or {}
            ).get(
                "ainda_sem_evidencia",
                0
            )
            or 0
        )
        for item in lista_tendencias
    )

    # ========================================================
    # ALERTA DE TRATATIVA
    #
    # Mantem a mesma prioridade:
    # 1. recorrencia
    # 2. maior quantidade de ocorrencias pendentes
    # 3. maior score de risco
    # 4. localizacao
    # ========================================================

    alerta_tratativa = None

    candidatos_tratativa = [
        item
        for item in lista_tendencias
        if bool(
            (
                item.get(
                    "tratativa",
                    {}
                )
                or {}
            ).get(
                "necessita_tratativa",
                False
            )
        )
    ]

    candidatos_tratativa.sort(
        key=lambda item: (
            0
            if bool(
                (
                    item.get(
                        "recorrencia",
                        {}
                    )
                    or {}
                ).get(
                    "possui_recorrencia_item_lote",
                    False
                )
            )
            else 1,

            -int(
                (
                    item.get(
                        "tratativa",
                        {}
                    )
                    or {}
                ).get(
                    "ocorrencias_pendentes",
                    0
                )
                or 0
            ),

            -float(
                item.get(
                    "score_risco",
                    0
                )
                or 0
            ),

            item.get(
                "localizacao",
                ""
            ),
        )
    )

    if candidatos_tratativa:

        principal_tratativa = (
            candidatos_tratativa[0]
        )

        localizacao_principal = (
            principal_tratativa.get(
                "localizacao"
            )
        )

        tratativa_principal = (
            principal_tratativa.get(
                "tratativa",
                {}
            )
            or {}
        )

        recorrencia_principal = (
            principal_tratativa.get(
                "recorrencia",
                {}
            )
            or {}
        )

        # ----------------------------------------------------
        # Preservar grupo_principal sem remontar o contexto.
        #
        # Somente a localizacao escolhida como alerta precisa
        # ter suas ocorrencias carregadas para montar o grupo.
        # ----------------------------------------------------

        ocorrencias_principal_db = (
            _buscar_ocorrencias_localizacao(
                cursor=cursor,
                cliente_id=cliente_id,
                armazem=armazem,
                localizacao=(
                    localizacao_principal
                ),
            )
        )

        ocorrencias_principal = (
            _montar_ocorrencias(
                ocorrencias_principal_db
            )
        )

        grupos_principal = (
            _agrupar_divergencias(
                ocorrencias_principal
            )
        )

        grupo_principal = (
            grupos_principal[0]
            if grupos_principal
            else None
        )

        alerta_tratativa = {
            "localizacao":
                localizacao_principal,

            "score_risco":
                principal_tratativa.get(
                    "score_risco"
                ),

            "classificacao_risco":
                principal_tratativa.get(
                    "classificacao_risco"
                ),

            "possui_recorrencia":
                bool(
                    recorrencia_principal.get(
                        "possui_recorrencia_item_lote",
                        False
                    )
                ),

            "ocorrencias_pendentes":
                int(
                    tratativa_principal.get(
                        "ocorrencias_pendentes",
                        0
                    )
                    or 0
                ),

            "ocorrencias_resolvidas":
                int(
                    tratativa_principal.get(
                        "ocorrencias_resolvidas",
                        0
                    )
                    or 0
                ),

            "grupos_pendentes":
                int(
                    tratativa_principal.get(
                        "grupos_pendentes",
                        0
                    )
                    or 0
                ),

            "necessita_tratativa":
                True,

            "grupo_principal":
                grupo_principal,
        }

    # ========================================================
    # RETORNO
    # ========================================================

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

            "data_fim_prevista":
                ciclo.DataFimPrevista,

            "criado_por":
                ciclo.CriadoPor,
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

        "risco": {

            "critico":
                critico,

            "alto":
                alto,

            "medio":
                medio,

            "baixo":
                baixo,

            "sugestoes_por_risco":
                sugestoes_risco,

            "sugestoes_por_cobertura":
                sugestoes_cobertura,
        },

        "historico": {

            "nunca_contadas":
                nunca_contadas,

            "com_divergencia_historica":
                divergencia_historica,

            "com_recorrencia":
                recorrencia,
        },

        "execucao_dia": {

            "localizacoes_contadas_hoje":
                contadas_hoje,

            "localizacoes_com_divergencia_hoje":
                divergencias_hoje,

            "localizacoes_ignoradas_hoje":
                ignoradas_hoje,

            "tempo_medio_por_localizacao_minutos":
                tempo_medio,

            "usuarios_ativos":
                usuarios_ativos,

            "produtividade_por_usuario":
                produtividade,
        },

        "backlog": {

            "pendentes_ciclo":
                pendentes,

            "sem_historico_contagem":
                nunca_contadas,

            "risco_alto_critico_pendente":
                risco_alto_critico,
        },

        "tendencias":
            tendencias_painel,

        "tratativas": {

            "localizacoes_com_recorrencia":
                localizacoes_com_recorrencia,

            "localizacoes_com_tratativa_pendente":
                localizacoes_com_tratativa_pendente,

            "grupos_recorrentes":
                grupos_recorrentes,

            "grupos_pendentes":
                grupos_pendentes,

            "ocorrencias_pendentes":
                ocorrencias_pendentes,

            "ocorrencias_resolvidas":
                ocorrencias_resolvidas,
        },

        "eficacia": {

            "resolucoes_avaliadas":
                resolucoes_avaliadas,

            "eficazes":
                eficazes,

            "nao_eficazes":
                nao_eficazes,

            "ainda_sem_evidencia":
                sem_evidencia,
        },

        "alerta_principal":
            alerta_principal,

        "alerta_tratativa":
            alerta_tratativa,

        "sugestao_principal":
            sugestao_principal,

        "top_prioridades":
            prioridades,
    }