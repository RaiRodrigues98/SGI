from datetime import datetime


# ============================================================
# UTILITÁRIOS
# ============================================================

def _txt(valor):
    if valor is None:
        return ""
    return str(valor).strip()


# ============================================================
# GERAR CÓDIGO DO CICLO
# Exemplo:
# ROT-53-ML007-2026-001
# ============================================================

def _gerar_codigo_ciclo(
    cursor,
    cliente_id: int,
    armazem: str
):
    ano = datetime.now().year
    prefixo = (
        f"ROT-{cliente_id}-"
        f"{armazem}-{ano}-"
    )

    cursor.execute(
        """
        SELECT
            CodigoCiclo
        FROM dbo.CiclosRotativo
        WHERE
            ClienteId = ?
            AND UPPER(LTRIM(RTRIM(cArmazem))) = ?
            AND CodigoCiclo LIKE ?
        ORDER BY
            ID_Ciclo DESC
        """,
        (
            cliente_id,
            armazem,
            f"{prefixo}%"
        )
    )

    linhas = cursor.fetchall()

    maior_sequencia = 0

    for linha in linhas:
        codigo = _txt(
            linha.CodigoCiclo
        )

        try:
            sequencia = int(
                codigo.split("-")[-1]
            )
        except Exception:
            continue

        maior_sequencia = max(
            maior_sequencia,
            sequencia
        )

    proxima = (
        maior_sequencia
        +
        1
    )

    return (
        f"{prefixo}"
        f"{proxima:03d}"
    )


# ============================================================
# VERIFICAR CICLO ABERTO
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
            DataInicio,
            DataFimPrevista,
            Status,
            TotalLocalizacoes,
            LocalizacoesContadas,
            PercentualCobertura,
            CriadoPor,
            DataHoraCriacao

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
# BUSCAR LOCALIZAÇÕES ELEGÍVEIS
# ============================================================

def _buscar_localizacoes_elegiveis(
    cursor,
    cliente_id: int,
    armazem: str
):
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
            ID_RodadaUltimaContagem,
            ScoreRisco,
            ClassificacaoRisco,
            Sugerida,
            Prioridade

        FROM dbo.RotativoLocalizacoes

        WHERE
            ClienteId = ?
            AND UPPER(LTRIM(RTRIM(cArmazem))) = ?
            AND Status <> 'INATIVA'

        ORDER BY
            CASE
                WHEN ClassificacaoRisco = 'CRITICO' THEN 1
                WHEN ClassificacaoRisco = 'ALTO' THEN 2
                WHEN ClassificacaoRisco = 'MEDIO' THEN 3
                WHEN ClassificacaoRisco = 'BAIXO' THEN 4
                ELSE 5
            END,
            ISNULL(Prioridade, 999999),
            Localizacao
        """,
        (
            cliente_id,
            armazem
        )
    )

    return cursor.fetchall()


# ============================================================
# ABRIR CICLO ROTATIVO
# ============================================================

def abrir_ciclo_rotativo(
    conn,
    cursor,
    cliente_id: int,
    armazem: str,
    criado_por: str | None = None,
    data_fim_prevista=None
):
    armazem = _txt(
        armazem
    ).upper()

    criado_por = (
        _txt(
            criado_por
        )
        or
        None
    )

    if not armazem:
        raise ValueError(
            "Armazém é obrigatório."
        )

    # --------------------------------------------------------
    # Impede dois ciclos abertos para o mesmo cliente/armazém
    # --------------------------------------------------------

    ciclo_aberto = (
        _buscar_ciclo_aberto(
            cursor=cursor,
            cliente_id=cliente_id,
            armazem=armazem
        )
    )

    if ciclo_aberto:
        return {
            "criado": False,
            "motivo": "CICLO_JA_ABERTO",
            "ciclo": {
                "id_ciclo":
                    ciclo_aberto.ID_Ciclo,

                "codigo_ciclo":
                    ciclo_aberto.CodigoCiclo,

                "data_inicio":
                    ciclo_aberto.DataInicio,

                "data_fim_prevista":
                    ciclo_aberto.DataFimPrevista,

                "status":
                    ciclo_aberto.Status,

                "total_localizacoes":
                    ciclo_aberto.TotalLocalizacoes,

                "localizacoes_contadas":
                    ciclo_aberto.LocalizacoesContadas,

                "percentual_cobertura":
                    float(
                        ciclo_aberto.PercentualCobertura
                        or
                        0
                    )
            }
        }

    # --------------------------------------------------------
    # Busca universo operacional do rotativo
    # --------------------------------------------------------

    localizacoes = (
        _buscar_localizacoes_elegiveis(
            cursor=cursor,
            cliente_id=cliente_id,
            armazem=armazem
        )
    )

    if not localizacoes:
        raise ValueError(
            "Nenhuma localização elegível foi encontrada "
            "em RotativoLocalizacoes para este cliente/armazém."
        )

    codigo_ciclo = (
        _gerar_codigo_ciclo(
            cursor=cursor,
            cliente_id=cliente_id,
            armazem=armazem
        )
    )

    try:
        # ----------------------------------------------------
        # Cabeçalho do ciclo
        # ----------------------------------------------------

        cursor.execute(
            """
            INSERT INTO dbo.CiclosRotativo (
                ClienteId,
                cArmazem,
                CodigoCiclo,
                DataInicio,
                DataFimPrevista,
                Status,
                TotalLocalizacoes,
                LocalizacoesContadas,
                PercentualCobertura,
                CriadoPor,
                DataHoraCriacao
            )
            OUTPUT INSERTED.ID_Ciclo
            VALUES (
                ?,
                ?,
                ?,
                SYSDATETIME(),
                ?,
                'ABERTO',
                ?,
                0,
                0,
                ?,
                SYSDATETIME()
            )
            """,
            (
                cliente_id,
                armazem,
                codigo_ciclo,
                data_fim_prevista,
                len(
                    localizacoes
                ),
                criado_por
            )
        )

        id_ciclo = (
            cursor.fetchone()[0]
        )

        # ----------------------------------------------------
        # Snapshot das localizações pertencentes ao ciclo
        # ----------------------------------------------------

        for posicao, linha in enumerate(
            localizacoes,
            start=1
        ):
            prioridade = (
                linha.Prioridade
                if linha.Prioridade is not None
                else posicao
            )

            cursor.execute(
                """
                INSERT INTO dbo.CicloRotativoLocalizacoes (
                    ID_Ciclo,
                    ID_RotativoLocalizacao,
                    ClienteId,
                    cArmazem,
                    Localizacao,
                    Status,
                    DataInclusao,
                    ScoreRiscoEntrada,
                    ClassificacaoRiscoEntrada,
                    Sugerida,
                    Prioridade,
                    DataHoraAtualizacao
                )
                VALUES (
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    'PENDENTE',
                    SYSDATETIME(),
                    ?,
                    ?,
                    ?,
                    ?,
                    SYSDATETIME()
                )
                """,
                (
                    id_ciclo,
                    linha.ID_RotativoLocalizacao,
                    linha.ClienteId,
                    _txt(
                        linha.cArmazem
                    ).upper(),
                    _txt(
                        linha.Localizacao
                    ).upper(),
                    linha.ScoreRisco,
                    linha.ClassificacaoRisco,
                    bool(
                        linha.Sugerida
                    ),
                    prioridade
                )
            )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    return {
        "criado": True,
        "motivo": "CICLO_CRIADO",
        "ciclo": {
            "id_ciclo":
                id_ciclo,

            "codigo_ciclo":
                codigo_ciclo,

            "cliente_id":
                cliente_id,

            "armazem":
                armazem,

            "status":
                "ABERTO",

            "total_localizacoes":
                len(
                    localizacoes
                ),

            "localizacoes_contadas":
                0,

            "percentual_cobertura":
                0,

            "data_fim_prevista":
                data_fim_prevista
        }
    }


# ============================================================
# CONSULTAR CICLO ATUAL
# ============================================================

def consultar_ciclo_atual(
    cursor,
    cliente_id: int,
    armazem: str
):
    armazem = _txt(
        armazem
    ).upper()

    ciclo = (
        _buscar_ciclo_aberto(
            cursor=cursor,
            cliente_id=cliente_id,
            armazem=armazem
        )
    )

    if not ciclo:
        return {
            "possui_ciclo_aberto": False,
            "ciclo": None
        }

    cursor.execute(
        """
        SELECT
            ID_CicloLocalizacao,
            ID_RotativoLocalizacao,
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
            DataHoraAtualizacao

        FROM dbo.CicloRotativoLocalizacoes

        WHERE
            ID_Ciclo = ?

        ORDER BY
            CASE
                WHEN Status = 'PENDENTE' THEN 1
                WHEN Status = 'EM_CONTAGEM' THEN 2
                WHEN Status = 'CONTADA' THEN 3
                WHEN Status = 'IGNORADA' THEN 4
                ELSE 5
            END,
            CASE
                WHEN ClassificacaoRiscoEntrada = 'CRITICO' THEN 1
                WHEN ClassificacaoRiscoEntrada = 'ALTO' THEN 2
                WHEN ClassificacaoRiscoEntrada = 'MEDIO' THEN 3
                WHEN ClassificacaoRiscoEntrada = 'BAIXO' THEN 4
                ELSE 5
            END,
            ISNULL(Prioridade, 999999),
            Localizacao
        """,
        (
            ciclo.ID_Ciclo,
        )
    )

    linhas = (
        cursor.fetchall()
    )

    localizacoes = []

    pendentes = 0
    em_contagem = 0
    contadas = 0
    ignoradas = 0

    for linha in linhas:
        status = _txt(
            linha.Status
        ).upper()

        if status == "PENDENTE":
            pendentes += 1

        elif status == "EM_CONTAGEM":
            em_contagem += 1

        elif status == "CONTADA":
            contadas += 1

        elif status == "IGNORADA":
            ignoradas += 1

        localizacoes.append(
            {
                "id_ciclo_localizacao":
                    linha.ID_CicloLocalizacao,

                "id_rotativo_localizacao":
                    linha.ID_RotativoLocalizacao,

                "localizacao":
                    linha.Localizacao,

                "status":
                    linha.Status,

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

                "sugerida":
                    bool(
                        linha.Sugerida
                    ),

                "prioridade":
                    linha.Prioridade,

                "usuario_contagem":
                    linha.UsuarioContagem,

                "data_hora_atualizacao":
                    linha.DataHoraAtualizacao
            }
        )

    return {
        "possui_ciclo_aberto": True,

        "ciclo": {
            "id_ciclo":
                ciclo.ID_Ciclo,

            "codigo_ciclo":
                ciclo.CodigoCiclo,

            "cliente_id":
                cliente_id,

            "armazem":
                armazem,

            "data_inicio":
                ciclo.DataInicio,

            "data_fim_prevista":
                ciclo.DataFimPrevista,

            "status":
                ciclo.Status,

            "total_localizacoes":
                ciclo.TotalLocalizacoes,

            "localizacoes_contadas":
                ciclo.LocalizacoesContadas,

            "percentual_cobertura":
                float(
                    ciclo.PercentualCobertura
                    or
                    0
                ),

            "resumo_localizacoes": {
                "pendentes":
                    pendentes,

                "em_contagem":
                    em_contagem,

                "contadas":
                    contadas,

                "ignoradas":
                    ignoradas
            },

            "localizacoes":
                localizacoes
        }
    }
# ============================================================
# FINALIZAR CICLO ROTATIVO
# ============================================================

def finalizar_ciclo_rotativo(
    conn,
    cursor,
    id_ciclo: int,
    finalizado_por: str | None = None
):
    finalizado_por = (
        _txt(finalizado_por)
        or None
    )

    if not id_ciclo:
        raise ValueError(
            "ID do ciclo é obrigatório."
        )

    # ========================================================
    # BUSCAR CICLO
    # ========================================================

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
        WHERE ID_Ciclo = ?
        """,
        (
            id_ciclo,
        )
    )

    ciclo = cursor.fetchone()

    if not ciclo:
        raise ValueError(
            "Ciclo rotativo não encontrado."
        )

    status_ciclo = (
        _txt(ciclo.Status)
        .upper()
    )

    # ========================================================
    # CICLO JÁ FECHADO
    # ========================================================

    if (
        status_ciclo == "CONCLUIDO"
        and ciclo.DataFimReal is not None
    ):
        return {
            "finalizado": False,
            "motivo": "CICLO_JA_FINALIZADO",
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

                "data_fim_real":
                    ciclo.DataFimReal,

                "finalizado_por":
                    ciclo.FinalizadoPor,
            }
        }

    # ========================================================
    # STATUS PERMITIDOS
    # ========================================================

    if status_ciclo not in (
        "ABERTO",
        "CONCLUIDO",
    ):
        raise ValueError(
            f"O ciclo está com status '{status_ciclo}' "
            "e não pode ser finalizado."
        )

    # ========================================================
    # CONSULTAR STATUS DAS LOCALIZAÇÕES
    # ========================================================

    cursor.execute(
        """
        SELECT
            UPPER(LTRIM(RTRIM(Status))) AS Status,
            COUNT(*) AS Quantidade
        FROM dbo.CicloRotativoLocalizacoes
        WHERE ID_Ciclo = ?
        GROUP BY
            UPPER(LTRIM(RTRIM(Status)))
        """,
        (
            id_ciclo,
        )
    )

    linhas_status = cursor.fetchall()

    contadores = {
        "PENDENTE": 0,
        "EM_CONTAGEM": 0,
        "CONTADA": 0,
        "IGNORADA": 0,
    }

    outros_status = {}

    for linha in linhas_status:

        status = (
            _txt(linha.Status)
            .upper()
        )

        quantidade = int(
            linha.Quantidade
            or 0
        )

        if status in contadores:
            contadores[status] = quantidade
        else:
            outros_status[status] = quantidade

    pendentes = contadores["PENDENTE"]
    em_contagem = contadores["EM_CONTAGEM"]
    contadas = contadores["CONTADA"]
    ignoradas = contadores["IGNORADA"]

    total_localizacoes = int(
        ciclo.TotalLocalizacoes
        or 0
    )

    # ========================================================
    # BLOQUEAR SE EXISTIR TRABALHO ABERTO
    # ========================================================

    if (
        pendentes > 0
        or em_contagem > 0
    ):
        return {
            "finalizado": False,
            "motivo": "CICLO_COM_LOCALIZACOES_ABERTAS",
            "ciclo": {
                "id_ciclo":
                    ciclo.ID_Ciclo,

                "codigo_ciclo":
                    ciclo.CodigoCiclo,

                "status":
                    ciclo.Status,

                "total_localizacoes":
                    total_localizacoes,

                "pendentes":
                    pendentes,

                "em_contagem":
                    em_contagem,

                "contadas":
                    contadas,

                "ignoradas":
                    ignoradas,
            },

            "mensagem":
                "O ciclo não pode ser finalizado enquanto "
                "existirem localizações PENDENTE ou EM_CONTAGEM."
        }

    # ========================================================
    # VALIDAR STATUS DESCONHECIDOS
    # ========================================================

    if outros_status:
        return {
            "finalizado": False,
            "motivo": "STATUS_LOCALIZACAO_NAO_RECONHECIDO",
            "status_encontrados":
                outros_status,
            "mensagem":
                "Existem localizações com status não previsto."
        }

    # ========================================================
    # INDICADORES
    # ========================================================

    processadas = (
        contadas
        +
        ignoradas
    )

    if total_localizacoes > 0:

        percentual_contado = round(
            (
                contadas
                /
                total_localizacoes
            )
            * 100,
            2
        )

        percentual_processado = round(
            (
                processadas
                /
                total_localizacoes
            )
            * 100,
            2
        )

    else:

        percentual_contado = 0.0
        percentual_processado = 0.0

    # ========================================================
    # VALIDAR CONSISTÊNCIA
    # ========================================================

    if processadas != total_localizacoes:

        return {
            "finalizado": False,
            "motivo": "COBERTURA_INCONSISTENTE",
            "ciclo": {
                "id_ciclo":
                    ciclo.ID_Ciclo,

                "codigo_ciclo":
                    ciclo.CodigoCiclo,

                "total_localizacoes":
                    total_localizacoes,

                "contadas":
                    contadas,

                "ignoradas":
                    ignoradas,

                "processadas":
                    processadas,
            },

            "mensagem":
                "A quantidade processada não corresponde "
                "ao total de localizações do ciclo."
        }

    # ========================================================
    # FINALIZAR CICLO
    # ========================================================

    try:

        cursor.execute(
            """
            UPDATE dbo.CiclosRotativo
            SET
                DataFimReal = SYSDATETIME(),
                Status = 'CONCLUIDO',
                LocalizacoesContadas = ?,
                PercentualCobertura = ?,
                FinalizadoPor = ?
            WHERE ID_Ciclo = ?
              AND Status IN ('ABERTO', 'CONCLUIDO')
            """,
            (
                contadas,
                percentual_processado,
                finalizado_por,
                id_ciclo,
            )
        )

        if cursor.rowcount == 0:

            conn.rollback()

            raise ValueError(
                "O ciclo não pôde ser finalizado. "
                "O status pode ter sido alterado por outro processo."
            )

        conn.commit()

    except Exception:

        conn.rollback()
        raise

    # ========================================================
    # RECUPERAR CICLO
    # ========================================================

    cursor.execute(
        """
        SELECT
            DataFimReal,
            Status,
            FinalizadoPor,
            LocalizacoesContadas,
            PercentualCobertura
        FROM dbo.CiclosRotativo
        WHERE ID_Ciclo = ?
        """,
        (
            id_ciclo,
        )
    )

    ciclo_final = cursor.fetchone()

    # ========================================================
    # RETORNO
    # ========================================================

    return {
        "finalizado": True,
        "motivo": "CICLO_FINALIZADO",

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
                ciclo_final.Status,

            "data_inicio":
                ciclo.DataInicio,

            "data_fim_prevista":
                ciclo.DataFimPrevista,

            "data_fim_real":
                ciclo_final.DataFimReal,

            "finalizado_por":
                ciclo_final.FinalizadoPor,
        },

        "resultado": {
            "total_localizacoes":
                total_localizacoes,

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

            "percentual_contado":
                percentual_contado,

            "percentual_processado":
                percentual_processado,

            "ciclo_concluido":
                True,
        }
    }