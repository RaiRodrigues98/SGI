from decimal import Decimal


# ============================================================
# UTILITÁRIOS
# ============================================================

def _txt(valor):
    if valor is None:
        return ""
    return str(valor).strip()


def _normalizar(valor):
    return _txt(valor).upper()


# ============================================================
# LOCALIZAÇÃO DO CICLO
# ============================================================

def _buscar_localizacao_ciclo_por_id(
    cursor,
    id_ciclo_localizacao: int
):
    cursor.execute(
        """
        SELECT
            CL.ID_CicloLocalizacao,
            CL.ID_Ciclo,
            CL.ID_RotativoLocalizacao,
            CL.ClienteId,
            CL.cArmazem,
            CL.Localizacao,
            CL.Status,
            CL.DataInicioContagem,
            CL.DataConclusao,
            CL.ID_Inventario,
            CL.ID_Rodada,
            CL.ScoreRiscoEntrada,
            CL.ClassificacaoRiscoEntrada,
            CL.Sugerida,
            CL.Prioridade,
            CL.UsuarioContagem,
            C.CodigoCiclo,
            C.Status AS StatusCiclo
        FROM dbo.CicloRotativoLocalizacoes CL
        INNER JOIN dbo.CiclosRotativo C
            ON C.ID_Ciclo = CL.ID_Ciclo
        WHERE
            CL.ID_CicloLocalizacao = ?
        """,
        (id_ciclo_localizacao,)
    )

    return cursor.fetchone()


# ============================================================
# INICIAR LOCALIZAÇÃO
# PENDENTE -> EM_CONTAGEM
# ============================================================

def iniciar_localizacao_rotativo(
    conn,
    cursor,
    id_ciclo_localizacao: int,
    id_inventario: int | None = None,
    id_rodada: int | None = None,
    usuario: str | None = None
):
    linha = _buscar_localizacao_ciclo_por_id(
        cursor,
        id_ciclo_localizacao
    )

    if not linha:
        raise ValueError(
            "Localização do ciclo não encontrada."
        )

    if _normalizar(linha.StatusCiclo) != "ABERTO":
        raise ValueError(
            "O ciclo rotativo não está ABERTO."
        )

    status = _normalizar(linha.Status)

    if status == "EM_CONTAGEM":
        return {
            "atualizado": False,
            "motivo": "LOCALIZACAO_JA_EM_CONTAGEM",
            "id_ciclo_localizacao": linha.ID_CicloLocalizacao,
            "localizacao": linha.Localizacao,
            "status": linha.Status
        }

    if status != "PENDENTE":
        raise ValueError(
            f"A localização está com status {status} "
            "e não pode ser iniciada."
        )

    try:
        cursor.execute(
            """
            UPDATE dbo.CicloRotativoLocalizacoes
            SET
                Status = 'EM_CONTAGEM',
                DataInicioContagem = COALESCE(
                    DataInicioContagem,
                    SYSDATETIME()
                ),
                ID_Inventario = COALESCE(?, ID_Inventario),
                ID_Rodada = COALESCE(?, ID_Rodada),
                UsuarioContagem = COALESCE(?, UsuarioContagem),
                DataHoraAtualizacao = SYSDATETIME()
            WHERE
                ID_CicloLocalizacao = ?
                AND Status = 'PENDENTE'
            """,
            (
                id_inventario,
                id_rodada,
                _txt(usuario) or None,
                id_ciclo_localizacao
            )
        )

        if cursor.rowcount != 1:
            raise ValueError(
                "A localização não pôde ser iniciada "
                "porque seu status foi alterado por outro processo."
            )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    return {
        "atualizado": True,
        "motivo": "LOCALIZACAO_INICIADA",
        "id_ciclo": linha.ID_Ciclo,
        "codigo_ciclo": linha.CodigoCiclo,
        "id_ciclo_localizacao": linha.ID_CicloLocalizacao,
        "localizacao": linha.Localizacao,
        "status_anterior": "PENDENTE",
        "status_atual": "EM_CONTAGEM"
    }


# ============================================================
# RECALCULAR CICLO
# CONTADA + IGNORADA = PROCESSADAS
# ============================================================

def _recalcular_ciclo(
    cursor,
    id_ciclo: int,
    usuario: str | None = None
):
    cursor.execute(
        """
        SELECT
            COUNT(*) AS Total,
            SUM(CASE WHEN Status = 'CONTADA' THEN 1 ELSE 0 END) AS Contadas,
            SUM(CASE WHEN Status = 'IGNORADA' THEN 1 ELSE 0 END) AS Ignoradas,
            SUM(
                CASE
                    WHEN Status IN ('PENDENTE', 'EM_CONTAGEM')
                    THEN 1 ELSE 0
                END
            ) AS Pendentes
        FROM dbo.CicloRotativoLocalizacoes
        WHERE ID_Ciclo = ?
        """,
        (id_ciclo,)
    )

    linha = cursor.fetchone()

    total = int(linha.Total or 0)
    contadas = int(linha.Contadas or 0)
    ignoradas = int(linha.Ignoradas or 0)
    pendentes = int(linha.Pendentes or 0)

    processadas = contadas + ignoradas

    percentual = (
        round((processadas / total) * 100, 2)
        if total > 0
        else 0
    )

    concluido = (
        total > 0
        and pendentes == 0
    )

    if concluido:
        cursor.execute(
            """
            UPDATE dbo.CiclosRotativo
            SET
                TotalLocalizacoes = ?,
                LocalizacoesContadas = ?,
                PercentualCobertura = 100,
                Status = 'CONCLUIDO',
                DataFimReal = COALESCE(
                    DataFimReal,
                    SYSDATETIME()
                ),
                FinalizadoPor = COALESCE(
                    FinalizadoPor,
                    ?
                )
            WHERE ID_Ciclo = ?
            """,
            (
                total,
                contadas,
                _txt(usuario) or None,
                id_ciclo
            )
        )

        percentual = 100.0

    else:
        cursor.execute(
            """
            UPDATE dbo.CiclosRotativo
            SET
                TotalLocalizacoes = ?,
                LocalizacoesContadas = ?,
                PercentualCobertura = ?
            WHERE ID_Ciclo = ?
            """,
            (
                total,
                contadas,
                Decimal(str(percentual)),
                id_ciclo
            )
        )

    return {
        "total_localizacoes": total,
        "localizacoes_contadas": contadas,
        "localizacoes_ignoradas": ignoradas,
        "localizacoes_pendentes": pendentes,
        "localizacoes_processadas": processadas,
        "percentual_cobertura": percentual,
        "ciclo_concluido": concluido
    }


# ============================================================
# IGNORAR LOCALIZAÇÃO
# PENDENTE -> IGNORADA
#
# Não atualiza UltimaContagem.
# Não grava histórico de contagem.
# ============================================================

def ignorar_localizacao_rotativo(
    conn,
    cursor,
    id_ciclo_localizacao: int,
    motivo: str,
    usuario: str | None = None
):
    motivo = _txt(motivo)
    usuario = _txt(usuario) or None

    if not motivo:
        raise ValueError(
            "O motivo para ignorar a localização é obrigatório."
        )

    linha = _buscar_localizacao_ciclo_por_id(
        cursor,
        id_ciclo_localizacao
    )

    if not linha:
        raise ValueError(
            "Localização do ciclo não encontrada."
        )

    if _normalizar(linha.StatusCiclo) != "ABERTO":
        raise ValueError(
            "O ciclo rotativo não está ABERTO."
        )

    status = _normalizar(linha.Status)

    if status == "IGNORADA":
        return {
            "atualizado": False,
            "motivo": "LOCALIZACAO_JA_IGNORADA",
            "id_ciclo_localizacao": linha.ID_CicloLocalizacao,
            "localizacao": linha.Localizacao,
            "status": linha.Status
        }

    if status != "PENDENTE":
        raise ValueError(
            "Somente uma localização PENDENTE pode ser ignorada."
        )

    try:
        cursor.execute(
            """
            UPDATE dbo.CicloRotativoLocalizacoes
            SET
                Status = 'IGNORADA',
                MotivoIgnorada = ?,
                UsuarioIgnorou = ?,
                DataHoraIgnorada = SYSDATETIME(),
                DataHoraAtualizacao = SYSDATETIME()
            WHERE
                ID_CicloLocalizacao = ?
                AND Status = 'PENDENTE'
            """,
            (
                motivo,
                usuario,
                id_ciclo_localizacao
            )
        )

        if cursor.rowcount != 1:
            raise ValueError(
                "A localização não pôde ser ignorada "
                "porque seu status foi alterado por outro processo."
            )

        cobertura = _recalcular_ciclo(
            cursor,
            linha.ID_Ciclo,
            usuario
        )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    return {
        "atualizado": True,
        "motivo": "LOCALIZACAO_IGNORADA",
        "id_ciclo": linha.ID_Ciclo,
        "codigo_ciclo": linha.CodigoCiclo,
        "id_ciclo_localizacao": linha.ID_CicloLocalizacao,
        "localizacao": linha.Localizacao,
        "status_anterior": "PENDENTE",
        "status_atual": "IGNORADA",
        "justificativa": motivo,
        "ciclo": cobertura
    }


# ============================================================
# RESUMO REAL DA LOCALIZAÇÃO NO INVENTÁRIO
#
# Itens previstos = itens distintos do snapshot.
# Itens contados  = itens distintos das contagens ATIVAS.
# Itens divergentes = união Snapshot x Contagem onde quantidade difere.
# ============================================================

def calcular_resumo_localizacao(
    cursor,
    id_inventario: int,
    id_rodada: int,
    localizacao: str
):
    localizacao = _normalizar(localizacao)

    cursor.execute(
        """
        WITH Snapshot AS (
            SELECT
                UPPER(LTRIM(RTRIM(Codigo))) AS Codigo,
                UPPER(ISNULL(LTRIM(RTRIM(Lote)), '')) AS Lote,
                SUM(ISNULL(SaldoInventario, 0)) AS QtdPrevista
            FROM dbo.InventarioEstoqueSnapshot
            WHERE
                ID_Inventario = ?
                AND UPPER(LTRIM(RTRIM(Localizacao))) = ?
            GROUP BY
                UPPER(LTRIM(RTRIM(Codigo))),
                UPPER(ISNULL(LTRIM(RTRIM(Lote)), ''))
        ),
        Contado AS (
            SELECT
                UPPER(LTRIM(RTRIM(C.Codigo))) AS Codigo,
                UPPER(ISNULL(LTRIM(RTRIM(C.Lote)), '')) AS Lote,
                SUM(ISNULL(C.Quantidade, 0)) AS QtdContada
            FROM dbo.Contagens C
            INNER JOIN dbo.SessoesContagem S
                ON S.ID_Sessao = C.ID_Sessao
            WHERE
                S.ID_Inventario = ?
                AND S.ID_Rodada = ?
                AND UPPER(LTRIM(RTRIM(S.Localizacao))) = ?
                AND S.ValidaParaConsolidacao = 1
                AND C.Status = 'ATIVA'
            GROUP BY
                UPPER(LTRIM(RTRIM(C.Codigo))),
                UPPER(ISNULL(LTRIM(RTRIM(C.Lote)), ''))
        ),
        Universo AS (
            SELECT Codigo, Lote FROM Snapshot
            UNION
            SELECT Codigo, Lote FROM Contado
        )
        SELECT
            COUNT(*) AS ItensAnalisados,
            SUM(CASE WHEN S.Codigo IS NOT NULL THEN 1 ELSE 0 END) AS ItensPrevistos,
            SUM(CASE WHEN C.Codigo IS NOT NULL THEN 1 ELSE 0 END) AS ItensContados,
            SUM(
                CASE
                    WHEN ISNULL(C.QtdContada, 0) = ISNULL(S.QtdPrevista, 0)
                    THEN 1 ELSE 0
                END
            ) AS ItensOK,
            SUM(
                CASE
                    WHEN ISNULL(C.QtdContada, 0) <> ISNULL(S.QtdPrevista, 0)
                    THEN 1 ELSE 0
                END
            ) AS ItensDivergentes
        FROM Universo U
        LEFT JOIN Snapshot S
            ON S.Codigo = U.Codigo
            AND S.Lote = U.Lote
        LEFT JOIN Contado C
            ON C.Codigo = U.Codigo
            AND C.Lote = U.Lote
        """,
        (
            id_inventario,
            localizacao,
            id_inventario,
            id_rodada,
            localizacao
        )
    )

    linha = cursor.fetchone()

    if not linha:
        return {
            "itens_analisados": 0,
            "itens_previstos": 0,
            "itens_contados": 0,
            "itens_ok": 0,
            "itens_divergentes": 0,
            "possui_divergencia": False
        }

    itens_analisados = int(
        linha.ItensAnalisados or 0
    )
    itens_previstos = int(
        linha.ItensPrevistos or 0
    )
    itens_contados = int(
        linha.ItensContados or 0
    )
    itens_ok = int(
        linha.ItensOK or 0
    )
    itens_divergentes = int(
        linha.ItensDivergentes or 0
    )

    return {
        "itens_analisados": itens_analisados,
        "itens_previstos": itens_previstos,
        "itens_contados": itens_contados,
        "itens_ok": itens_ok,
        "itens_divergentes": itens_divergentes,
        "possui_divergencia": itens_divergentes > 0
    }
