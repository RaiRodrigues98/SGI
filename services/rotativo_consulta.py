from datetime import datetime


# ============================================================
# UTILITÁRIOS
# ============================================================

def _txt(valor):
    if valor is None:
        return ""
    return str(valor).strip()


def _normalizar(valor):
    return _txt(valor).upper()


def _dias_sem_contagem(data_ultima_contagem):
    if data_ultima_contagem is None:
        return None

    agora = datetime.now()

    if getattr(
        data_ultima_contagem,
        "tzinfo",
        None
    ) is not None:
        agora = datetime.now(
            tz=data_ultima_contagem.tzinfo
        )

    diferenca = (
        agora
        -
        data_ultima_contagem
    )

    return max(
        0,
        diferenca.days
    )


# ============================================================
# BUSCAR CICLO
# ============================================================

def _buscar_ciclo(
    cursor,
    cliente_id: int,
    armazem: str,
    id_ciclo: int | None = None
):
    armazem = _normalizar(
        armazem
    )

    if id_ciclo is not None:
        cursor.execute(
            """
            SELECT
                ID_Ciclo,
                ClienteId,
                cArmazem,
                CodigoCiclo,
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
                ID_Ciclo = ?
                AND ClienteId = ?
                AND UPPER(LTRIM(RTRIM(cArmazem))) = ?
            """,
            (
                id_ciclo,
                cliente_id,
                armazem
            )
        )

        return cursor.fetchone()

    cursor.execute(
        """
        SELECT TOP 1
            ID_Ciclo,
            ClienteId,
            cArmazem,
            CodigoCiclo,
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
# MOTIVOS DA SUGESTÃO
# ============================================================

def _montar_motivos(
    status_ciclo,
    classificacao_risco,
    sugerida,
    ultima_contagem,
    dias_sem_contagem
):
    motivos = []

    status_ciclo = _normalizar(
        status_ciclo
    )

    classificacao_risco = _normalizar(
        classificacao_risco
    )

    if status_ciclo == "PENDENTE":
        motivos.append(
            "Localização ainda não contada no ciclo"
        )

    elif status_ciclo == "EM_CONTAGEM":
        motivos.append(
            "Localização com contagem em andamento"
        )

    elif status_ciclo == "CONTADA":
        motivos.append(
            "Localização já contada no ciclo"
        )

    elif status_ciclo == "IGNORADA":
        motivos.append(
            "Localização ignorada no ciclo"
        )

    if classificacao_risco in {
        "CRITICO",
        "ALTO",
    }:
        motivos.append(
            f"Risco {classificacao_risco}"
        )

    elif classificacao_risco:
        motivos.append(
            f"Classificação de risco {classificacao_risco}"
        )

    if ultima_contagem is None:
        motivos.append(
            "Sem histórico de última contagem"
        )

    elif dias_sem_contagem is not None:
        motivos.append(
            f"{dias_sem_contagem} dias desde a última contagem"
        )

    if bool(sugerida):
        motivos.append(
            "Sugerida pelo SGI"
        )

    return motivos


# ============================================================
# CONSULTA OPERACIONAL DAS LOCALIZAÇÕES DO CICLO
# ============================================================

def consultar_localizacoes_ciclo(
    cursor,
    cliente_id: int,
    armazem: str,
    id_ciclo: int | None = None,
    status: str | None = None,
    classificacao_risco: str | None = None,
    somente_sugeridas: bool = False,
    somente_pendentes: bool = False,
    ordenar_por: str = "PRIORIDADE"
):
    armazem = _normalizar(
        armazem
    )

    status = (
        _normalizar(status)
        or
        None
    )

    classificacao_risco = (
        _normalizar(
            classificacao_risco
        )
        or
        None
    )

    ordenar_por = (
        _normalizar(
            ordenar_por
        )
        or
        "PRIORIDADE"
    )

    ordenacoes_validas = {
        "PRIORIDADE",
        "RISCO",
        "ULTIMA_CONTAGEM",
        "LOCALIZACAO",
    }

    if ordenar_por not in ordenacoes_validas:
        raise ValueError(
            "ordenar_por deve ser PRIORIDADE, RISCO, "
            "ULTIMA_CONTAGEM ou LOCALIZACAO."
        )

    ciclo = _buscar_ciclo(
        cursor=cursor,
        cliente_id=cliente_id,
        armazem=armazem,
        id_ciclo=id_ciclo
    )

    if not ciclo:
        return {
            "possui_ciclo": False,
            "ciclo": None,
            "resumo": None,
            "localizacoes": []
        }

    filtros = [
        "CL.ID_Ciclo = ?"
    ]

    params = [
        ciclo.ID_Ciclo
    ]

    if status:
        filtros.append(
            "UPPER(LTRIM(RTRIM(CL.Status))) = ?"
        )
        params.append(
            status
        )

    if classificacao_risco:
        filtros.append(
            """
            UPPER(
                LTRIM(
                    RTRIM(
                        COALESCE(
                            RL.ClassificacaoRisco,
                            CL.ClassificacaoRiscoEntrada
                        )
                    )
                )
            ) = ?
            """
        )
        params.append(
            classificacao_risco
        )

    if somente_sugeridas:
        filtros.append(
            """
            COALESCE(
                RL.Sugerida,
                CL.Sugerida
            ) = 1
            """
        )

    if somente_pendentes:
        filtros.append(
            "CL.Status = 'PENDENTE'"
        )

    where_sql = (
        " AND ".join(
            filtros
        )
    )

    order_sql = {
        "PRIORIDADE": """
            CASE CL.Status
                WHEN 'PENDENTE' THEN 1
                WHEN 'EM_CONTAGEM' THEN 2
                WHEN 'CONTADA' THEN 3
                WHEN 'IGNORADA' THEN 4
                ELSE 5
            END,
            CASE
                WHEN COALESCE(
                    RL.ClassificacaoRisco,
                    CL.ClassificacaoRiscoEntrada
                ) = 'CRITICO' THEN 1
                WHEN COALESCE(
                    RL.ClassificacaoRisco,
                    CL.ClassificacaoRiscoEntrada
                ) = 'ALTO' THEN 2
                WHEN COALESCE(
                    RL.ClassificacaoRisco,
                    CL.ClassificacaoRiscoEntrada
                ) = 'MEDIO' THEN 3
                WHEN COALESCE(
                    RL.ClassificacaoRisco,
                    CL.ClassificacaoRiscoEntrada
                ) = 'BAIXO' THEN 4
                ELSE 5
            END,
            ISNULL(
                RL.Prioridade,
                ISNULL(
                    CL.Prioridade,
                    999999
                )
            ),
            CASE
                WHEN RL.UltimaContagem IS NULL THEN 0
                ELSE 1
            END,
            RL.UltimaContagem,
            CL.Localizacao
        """,

        "RISCO": """
            CASE
                WHEN COALESCE(
                    RL.ClassificacaoRisco,
                    CL.ClassificacaoRiscoEntrada
                ) = 'CRITICO' THEN 1
                WHEN COALESCE(
                    RL.ClassificacaoRisco,
                    CL.ClassificacaoRiscoEntrada
                ) = 'ALTO' THEN 2
                WHEN COALESCE(
                    RL.ClassificacaoRisco,
                    CL.ClassificacaoRiscoEntrada
                ) = 'MEDIO' THEN 3
                WHEN COALESCE(
                    RL.ClassificacaoRisco,
                    CL.ClassificacaoRiscoEntrada
                ) = 'BAIXO' THEN 4
                ELSE 5
            END,
            COALESCE(
                RL.ScoreRisco,
                CL.ScoreRiscoEntrada,
                0
            ) DESC,
            CL.Localizacao
        """,

        "ULTIMA_CONTAGEM": """
            CASE
                WHEN RL.UltimaContagem IS NULL THEN 0
                ELSE 1
            END,
            RL.UltimaContagem,
            CL.Localizacao
        """,

        "LOCALIZACAO": """
            CL.Localizacao
        """
    }[
        ordenar_por
    ]

    cursor.execute(
        f"""
        SELECT
            CL.ID_CicloLocalizacao,
            CL.ID_Ciclo,
            CL.ID_RotativoLocalizacao,
            CL.ClienteId,
            CL.cArmazem,
            CL.Localizacao,

            CL.Status AS StatusCiclo,
            CL.DataInclusao,
            CL.DataInicioContagem,
            CL.DataConclusao,
            CL.ID_Inventario,
            CL.ID_Rodada,
            CL.UsuarioContagem,

            CL.ScoreRiscoEntrada,
            CL.ClassificacaoRiscoEntrada,
            CL.Sugerida AS SugeridaEntrada,
            CL.Prioridade AS PrioridadeEntrada,

            RL.Status AS StatusCadastro,
            RL.UltimaContagem,
            RL.ID_InventarioUltimaContagem,
            RL.ID_RodadaUltimaContagem,
            RL.ScoreRisco,
            RL.ClassificacaoRisco,
            RL.Sugerida,
            RL.Prioridade,

            CL.MotivoIgnorada,
            CL.UsuarioIgnorou,
            CL.DataHoraIgnorada

        FROM dbo.CicloRotativoLocalizacoes CL

        INNER JOIN dbo.RotativoLocalizacoes RL
            ON RL.ID_RotativoLocalizacao =
               CL.ID_RotativoLocalizacao

        WHERE
            {where_sql}

        ORDER BY
            {order_sql}
        """,
        tuple(
            params
        )
    )

    linhas = cursor.fetchall()

    localizacoes = []

    contadores = {
        "pendentes": 0,
        "em_contagem": 0,
        "contadas": 0,
        "ignoradas": 0,
        "sugeridas": 0,
        "criticas": 0,
        "altas": 0,
        "medias": 0,
        "baixas": 0,
        "sem_historico_contagem": 0,
    }

    for linha in linhas:
        status_ciclo = _normalizar(
            linha.StatusCiclo
        )

        if status_ciclo == "PENDENTE":
            contadores["pendentes"] += 1
        elif status_ciclo == "EM_CONTAGEM":
            contadores["em_contagem"] += 1
        elif status_ciclo == "CONTADA":
            contadores["contadas"] += 1
        elif status_ciclo == "IGNORADA":
            contadores["ignoradas"] += 1

        score_risco = (
            linha.ScoreRisco
            if linha.ScoreRisco is not None
            else linha.ScoreRiscoEntrada
        )

        classificacao = (
            linha.ClassificacaoRisco
            if linha.ClassificacaoRisco is not None
            else linha.ClassificacaoRiscoEntrada
        )

        sugerida = (
            bool(linha.Sugerida)
            if linha.Sugerida is not None
            else bool(
                linha.SugeridaEntrada
            )
        )

        prioridade = (
            linha.Prioridade
            if linha.Prioridade is not None
            else linha.PrioridadeEntrada
        )

        if sugerida:
            contadores["sugeridas"] += 1

        classificacao_norm = _normalizar(
            classificacao
        )

        if classificacao_norm == "CRITICO":
            contadores["criticas"] += 1
        elif classificacao_norm == "ALTO":
            contadores["altas"] += 1
        elif classificacao_norm == "MEDIO":
            contadores["medias"] += 1
        elif classificacao_norm == "BAIXO":
            contadores["baixas"] += 1

        dias_sem_contagem = (
            _dias_sem_contagem(
                linha.UltimaContagem
            )
        )

        if linha.UltimaContagem is None:
            contadores[
                "sem_historico_contagem"
            ] += 1

        localizacoes.append(
            {
                "id_ciclo_localizacao":
                    linha.ID_CicloLocalizacao,

                "id_rotativo_localizacao":
                    linha.ID_RotativoLocalizacao,

                "localizacao":
                    linha.Localizacao,

                "status_ciclo":
                    linha.StatusCiclo,

                "status_cadastro":
                    linha.StatusCadastro,

                "ultima_contagem":
                    linha.UltimaContagem,

                "dias_sem_contagem":
                    dias_sem_contagem,

                "id_inventario_ultima_contagem":
                    linha.ID_InventarioUltimaContagem,

                "id_rodada_ultima_contagem":
                    linha.ID_RodadaUltimaContagem,

                "score_risco":
                    (
                        float(score_risco)
                        if score_risco is not None
                        else None
                    ),

                "classificacao_risco":
                    classificacao,

                "sugerida":
                    sugerida,

                "prioridade":
                    prioridade,

                "motivos":
                    _montar_motivos(
                        status_ciclo=linha.StatusCiclo,
                        classificacao_risco=classificacao,
                        sugerida=sugerida,
                        ultima_contagem=linha.UltimaContagem,
                        dias_sem_contagem=dias_sem_contagem
                    ),

                "contagem_ciclo": {
                    "data_inclusao":
                        linha.DataInclusao,

                    "data_inicio":
                        linha.DataInicioContagem,

                    "data_conclusao":
                        linha.DataConclusao,

                    "id_inventario":
                        linha.ID_Inventario,

                    "id_rodada":
                        linha.ID_Rodada,

                    "usuario":
                        linha.UsuarioContagem
                },

                "ignoracao": {
                    "ignorada":
                        status_ciclo == "IGNORADA",

                    "motivo":
                        linha.MotivoIgnorada,

                    "usuario":
                        linha.UsuarioIgnorou,

                    "data_hora":
                        linha.DataHoraIgnorada
                },

                "snapshot_risco_entrada": {
                    "score":
                        (
                            float(
                                linha.ScoreRiscoEntrada
                            )
                            if linha.ScoreRiscoEntrada is not None
                            else None
                        ),

                    "classificacao":
                        linha.ClassificacaoRiscoEntrada,

                    "sugerida":
                        bool(
                            linha.SugeridaEntrada
                        ),

                    "prioridade":
                        linha.PrioridadeEntrada
                }
            }
        )

    # --------------------------------------------------------
    # Resumo real do ciclo inteiro, independente dos filtros
    # --------------------------------------------------------

    cursor.execute(
        """
        SELECT
            COUNT(*) AS Total,

            SUM(
                CASE
                    WHEN Status = 'PENDENTE'
                    THEN 1 ELSE 0
                END
            ) AS Pendentes,

            SUM(
                CASE
                    WHEN Status = 'EM_CONTAGEM'
                    THEN 1 ELSE 0
                END
            ) AS EmContagem,

            SUM(
                CASE
                    WHEN Status = 'CONTADA'
                    THEN 1 ELSE 0
                END
            ) AS Contadas,

            SUM(
                CASE
                    WHEN Status = 'IGNORADA'
                    THEN 1 ELSE 0
                END
            ) AS Ignoradas

        FROM dbo.CicloRotativoLocalizacoes
        WHERE
            ID_Ciclo = ?
        """,
        (
            ciclo.ID_Ciclo,
        )
    )

    resumo_ciclo = cursor.fetchone()

    total = int(
        resumo_ciclo.Total
        or
        0
    )

    pendentes = int(
        resumo_ciclo.Pendentes
        or
        0
    )

    em_contagem = int(
        resumo_ciclo.EmContagem
        or
        0
    )

    contadas = int(
        resumo_ciclo.Contadas
        or
        0
    )

    ignoradas = int(
        resumo_ciclo.Ignoradas
        or
        0
    )

    processadas = (
        contadas
        +
        ignoradas
    )

    cobertura = (
        round(
            (
                processadas
                /
                total
            )
            *
            100,
            2
        )
        if total > 0
        else 0
    )

    return {
        "possui_ciclo":
            True,

        "pesquisa": {
            "cliente_id":
                cliente_id,

            "armazem":
                armazem,

            "id_ciclo":
                ciclo.ID_Ciclo,

            "status":
                status,

            "classificacao_risco":
                classificacao_risco,

            "somente_sugeridas":
                somente_sugeridas,

            "somente_pendentes":
                somente_pendentes,

            "ordenar_por":
                ordenar_por
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

            "total_localizacoes":
                total,

            "localizacoes_contadas":
                contadas,

            "localizacoes_ignoradas":
                ignoradas,

            "localizacoes_processadas":
                processadas,

            "localizacoes_pendentes":
                pendentes,

            "localizacoes_em_contagem":
                em_contagem,

            "percentual_cobertura":
                cobertura
        },

        "resumo_retorno": {
            "localizacoes_retornadas":
                len(
                    localizacoes
                ),

            **contadores
        },

        "localizacoes":
            localizacoes
    }
