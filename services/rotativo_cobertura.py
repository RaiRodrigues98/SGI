from domain.exceptions import BusinessRuleViolation
from decimal import Decimal
from services.rotativo_orquestrador import (
    executar_orquestracao_rotativo,
)

from infrastructure.database.unit_of_work import SqlServerUnitOfWork

# ============================================================
# UTILITÁRIOS
# ============================================================

def _txt(valor):
    if valor is None:
        return ""
    return str(valor).strip()


def _bool(valor):
    return bool(valor)


# ============================================================
# RESOLVER ARMAZÉM DA SESSÃO
#
# Prioridade:
# 1. Inventarios.cArmazem
# 2. Snapshot da mesma localização
# ============================================================

def _resolver_armazem_sessao(
    cursor,
    id_inventario: int,
    localizacao: str,
    armazem_inventario
):
    armazem = _txt(
        armazem_inventario
    ).upper()

    if armazem:
        return armazem

    cursor.execute(
        """
        SELECT DISTINCT
            UPPER(LTRIM(RTRIM(cArmazem))) AS cArmazem
        FROM dbo.InventarioEstoqueSnapshot
        WHERE
            ID_Inventario = ?
            AND UPPER(LTRIM(RTRIM(Localizacao))) = ?
            AND NULLIF(LTRIM(RTRIM(cArmazem)), '') IS NOT NULL
        """,
        (
            id_inventario,
            _txt(localizacao).upper()
        )
    )

    armazens = [
        _txt(linha.cArmazem).upper()
        for linha in cursor.fetchall()
        if _txt(linha.cArmazem)
    ]

    armazens = list(
        dict.fromkeys(armazens)
    )

    if len(armazens) == 1:
        return armazens[0]

    if len(armazens) > 1:
        raise BusinessRuleViolation(
            "Não foi possível determinar o armazém da sessão: "
            "existem múltiplos armazéns possíveis no snapshot."
        )

    raise BusinessRuleViolation(
        "Não foi possível determinar o armazém da sessão."
    )


# ============================================================
# BUSCAR SESSÃO
# ============================================================

def _buscar_sessao(
    cursor,
    id_sessao: int
):
    cursor.execute(
        """
        SELECT
            S.ID_Sessao,
            S.Localizacao,
            S.DataHoraInicio,
            S.DataHoraFim,
            S.Status,
            S.ID_Inventario,
            S.ID_Rodada,
            S.LocalizacaoVazia,

            I.ClienteId,
            I.cArmazem

        FROM dbo.SessoesContagem S

        INNER JOIN dbo.Inventarios I
            ON I.ID_Inventario = S.ID_Inventario

        WHERE
            S.ID_Sessao = ?
        """,
        (
            id_sessao,
        )
    )

    return cursor.fetchone()


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
            TotalLocalizacoes,
            LocalizacoesContadas,
            PercentualCobertura
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
# BUSCAR LOCALIZAÇÃO DENTRO DO CICLO
# ============================================================

def _buscar_localizacao_ciclo(
    cursor,
    id_ciclo: int,
    localizacao: str
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
            DataInicioContagem,
            DataConclusao,
            ID_Inventario,
            ID_Rodada,
            ScoreRiscoEntrada,
            ClassificacaoRiscoEntrada,
            Sugerida,
            Prioridade,
            UsuarioContagem
        FROM dbo.CicloRotativoLocalizacoes
        WHERE
            ID_Ciclo = ?
            AND UPPER(LTRIM(RTRIM(Localizacao))) = ?
        """,
        (
            id_ciclo,
            _txt(localizacao).upper()
        )
    )

    return cursor.fetchone()


# ============================================================
# RESUMO DAS CONTAGENS DA SESSÃO
# ============================================================

def _resumo_contagens_sessao(
    cursor,
    id_sessao: int
):
    cursor.execute(
        """
        SELECT
            COUNT(CASE WHEN Status = 'ATIVA' THEN 1 END) AS BipagensAtivas,

            COUNT(
                DISTINCT
                CASE
                    WHEN Status = 'ATIVA'
                    THEN CONCAT(
                        LTRIM(RTRIM(Codigo)),
                        '|',
                        ISNULL(LTRIM(RTRIM(Lote)), '')
                    )
                END
            ) AS ItensAtivos,

            COUNT(CASE WHEN Status = 'CANCELADA' THEN 1 END) AS BipagensCanceladas,

            COALESCE(
                SUM(
                    CASE
                        WHEN Status = 'ATIVA'
                        THEN Quantidade
                        ELSE 0
                    END
                ),
                0
            ) AS QuantidadeAtiva

        FROM dbo.Contagens

        WHERE
            ID_Sessao = ?
        """,
        (
            id_sessao,
        )
    )

    linha = cursor.fetchone()

    return {
        "bipagens_ativas":
            int(
                linha.BipagensAtivas
                or
                0
            ),

        "itens_ativos":
            int(
                linha.ItensAtivos
                or
                0
            ),

        "bipagens_canceladas":
            int(
                linha.BipagensCanceladas
                or
                0
            ),

        "quantidade_ativa":
            float(
                linha.QuantidadeAtiva
                or
                0
            )
    }


# ============================================================
# RESUMO OPERACIONAL DAS DIVERGÊNCIAS
#
# Fonte oficial para identificar divergência:
# - InventarioEstoqueSnapshot
# - Contagens ATIVAS da sessão encerrada
#
# Regra de conciliação:
# Localização + Código + Lote
#
# IMPORTANTE:
# DecisoesRotativo representa a TRATATIVA da divergência.
# Não deve ser usada para decidir se a contagem divergiu.
# ============================================================

def _resumo_divergencias(
    cursor,
    id_inventario: int,
    id_sessao: int,
    localizacao: str
):

    localizacao = _txt(
        localizacao
    ).upper()

    cursor.execute(
        """
        WITH Snapshot AS
        (
            SELECT
                UPPER(
                    LTRIM(
                        RTRIM(Localizacao)
                    )
                ) AS Localizacao,

                LTRIM(
                    RTRIM(Codigo)
                ) AS Codigo,

                ISNULL(
                    LTRIM(
                        RTRIM(Lote)
                    ),
                    ''
                ) AS Lote,

                SUM(
                    COALESCE(
                        SaldoInventario,
                        0
                    )
                ) AS QtdEstoque

            FROM dbo.InventarioEstoqueSnapshot

            WHERE
                ID_Inventario = ?
                AND UPPER(
                    LTRIM(
                        RTRIM(Localizacao)
                    )
                ) = ?
                AND NULLIF(
                    LTRIM(
                        RTRIM(Codigo)
                    ),
                    ''
                ) IS NOT NULL

            GROUP BY
                UPPER(
                    LTRIM(
                        RTRIM(Localizacao)
                    )
                ),
                LTRIM(
                    RTRIM(Codigo)
                ),
                ISNULL(
                    LTRIM(
                        RTRIM(Lote)
                    ),
                    ''
                )
        ),

        Contagem AS
        (
            SELECT
                UPPER(
                    LTRIM(
                        RTRIM(S.Localizacao)
                    )
                ) AS Localizacao,

                LTRIM(
                    RTRIM(C.Codigo)
                ) AS Codigo,

                ISNULL(
                    LTRIM(
                        RTRIM(C.Lote)
                    ),
                    ''
                ) AS Lote,

                SUM(
                    COALESCE(
                        C.Quantidade,
                        0
                    )
                ) AS QtdContada

            FROM dbo.Contagens C

            INNER JOIN dbo.SessoesContagem S
                ON S.ID_Sessao = C.ID_Sessao

            WHERE
                C.ID_Sessao = ?
                AND C.Status = 'ATIVA'
                AND UPPER(
                    LTRIM(
                        RTRIM(S.Localizacao)
                    )
                ) = ?
                AND NULLIF(
                    LTRIM(
                        RTRIM(C.Codigo)
                    ),
                    ''
                ) IS NOT NULL

            GROUP BY
                UPPER(
                    LTRIM(
                        RTRIM(S.Localizacao)
                    )
                ),
                LTRIM(
                    RTRIM(C.Codigo)
                ),
                ISNULL(
                    LTRIM(
                        RTRIM(C.Lote)
                    ),
                    ''
                )
        ),

        Conciliacao AS
        (
            SELECT
                COALESCE(
                    E.Localizacao,
                    C.Localizacao
                ) AS Localizacao,

                COALESCE(
                    E.Codigo,
                    C.Codigo
                ) AS Codigo,

                COALESCE(
                    E.Lote,
                    C.Lote,
                    ''
                ) AS Lote,

                COALESCE(
                    E.QtdEstoque,
                    0
                ) AS QtdEstoque,

                COALESCE(
                    C.QtdContada,
                    0
                ) AS QtdContada

            FROM Snapshot E

            FULL OUTER JOIN Contagem C
                ON C.Localizacao = E.Localizacao
                AND C.Codigo = E.Codigo
                AND C.Lote = E.Lote
        )

        SELECT
            COUNT(*) AS TotalItensAnalisados,

            SUM(
                CASE
                    WHEN QtdContada = QtdEstoque
                    THEN 1
                    ELSE 0
                END
            ) AS ItensOK,

            SUM(
                CASE
                    WHEN QtdContada <> QtdEstoque
                    THEN 1
                    ELSE 0
                END
            ) AS ItensDivergentes

        FROM Conciliacao
        """,
        (
            id_inventario,
            localizacao,
            id_sessao,
            localizacao,
        )
    )

    linha = cursor.fetchone()

    total_itens = int(
        linha.TotalItensAnalisados
        or
        0
    )

    itens_ok = int(
        linha.ItensOK
        or
        0
    )

    itens_divergentes = int(
        linha.ItensDivergentes
        or
        0
    )

    return {
        "possui_divergencia":
            itens_divergentes > 0,

        "total_itens_analisados":
            total_itens,

        "itens_ok":
            itens_ok,

        "itens_divergentes":
            itens_divergentes,
    }


# ============================================================
# ATUALIZAR RESUMO DO CICLO
#
# Cobertura considera:
# CONTADA + IGNORADA
#
# Ciclo fecha automaticamente quando não há pendências.
# ============================================================

def _recalcular_ciclo(
    cursor,
    id_ciclo: int,
    usuario: str | None
):
    cursor.execute(
        """
        SELECT
            COUNT(*) AS Total,

            SUM(
                CASE
                    WHEN Status = 'CONTADA'
                    THEN 1
                    ELSE 0
                END
            ) AS Contadas,

            SUM(
                CASE
                    WHEN Status = 'IGNORADA'
                    THEN 1
                    ELSE 0
                END
            ) AS Ignoradas,

            SUM(
                CASE
                    WHEN Status IN (
                        'PENDENTE',
                        'EM_CONTAGEM'
                    )
                    THEN 1
                    ELSE 0
                END
            ) AS Pendentes

        FROM dbo.CicloRotativoLocalizacoes

        WHERE
            ID_Ciclo = ?
        """,
        (
            id_ciclo,
        )
    )

    linha = cursor.fetchone()

    total = int(
        linha.Total
        or
        0
    )

    contadas = int(
        linha.Contadas
        or
        0
    )

    ignoradas = int(
        linha.Ignoradas
        or
        0
    )

    pendentes = int(
        linha.Pendentes
        or
        0
    )

    processadas = (
        contadas
        +
        ignoradas
    )

    percentual = (
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

    ciclo_concluido = (
        total > 0
        and
        pendentes == 0
    )

    if ciclo_concluido:
        cursor.execute(
            """
            UPDATE dbo.CiclosRotativo
            SET
                TotalLocalizacoes = ?,
                LocalizacoesContadas = ?,
                PercentualCobertura = 100,
                Status = 'CONCLUIDO',
                DataFimReal = SYSDATETIME(),
                FinalizadoPor = ?
            WHERE
                ID_Ciclo = ?
            """,
            (
                total,
                contadas,
                usuario,
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
            WHERE
                ID_Ciclo = ?
            """,
            (
                total,
                contadas,
                Decimal(
                    str(
                        percentual
                    )
                ),
                id_ciclo
            )
        )

    return {
        "total_localizacoes":
            total,

        "localizacoes_contadas":
            contadas,

        "localizacoes_ignoradas":
            ignoradas,

        "localizacoes_pendentes":
            pendentes,

        "localizacoes_processadas":
            processadas,

        "percentual_cobertura":
            percentual,

        "ciclo_concluido":
            ciclo_concluido
    }
# ============================================================
# EXECUTAR INTELIGÊNCIA APÓS CONCLUSÃO DA LOCALIZAÇÃO
#
# IMPORTANTE:
# - Deve ser chamada somente APÓS o commit operacional.
# - Falha analítica não pode desfazer a conclusão da contagem.
# ============================================================

def _executar_inteligencia_pos_conclusao(
    conn,
    cursor,
    cliente_id: int,
    armazem: str,
    localizacao: str,
    id_inventario: int,
    id_rodada: int,
    usuario: str | None,
    ciclo_concluido: bool,
):

    # --------------------------------------------------------
    # Última localização do ciclo
    #
    # O ciclo já foi alterado para CONCLUIDO por
    # _recalcular_ciclo().
    #
    # Portanto não existe mais ciclo ABERTO para o
    # orquestrador operacional atualizar.
    # --------------------------------------------------------

    if ciclo_concluido:

        return {
            "executada":
                False,

            "motivo":
                "CICLO_CONCLUIDO",

            "mensagem":
                "A localização foi concluída e o ciclo foi "
                "encerrado. Não existe mais ranking ativo "
                "para recalcular neste ciclo.",
        }

    try:

        resultado = (
            executar_orquestracao_rotativo(
                conn=conn,
                cursor=cursor,
                cliente_id=cliente_id,
                armazem=armazem,
                origem_evento=(
                    "CONCLUSAO_LOCALIZACAO"
                ),
                localizacao=localizacao,
                id_inventario=id_inventario,
                id_rodada=id_rodada,
                usuario=usuario,
                limite_score_sugestao=50.0,
                quantidade_sugestoes=20,
                retornar_painel=True,
            )
        )

        return {
            "executada":
                True,

            "motivo":
                "INTELIGENCIA_ATUALIZADA",

            "resultado":
                resultado,
        }

    except Exception as erro:

        # ----------------------------------------------------
        # NÃO propagar o erro.
        #
        # A operação de contagem já foi confirmada no banco.
        # Falha na inteligência deve ser registrada/retornada,
        # não provocar rollback da conclusão operacional.
        # ----------------------------------------------------

        return {
            "executada":
                False,

            "motivo":
                "FALHA_ATUALIZACAO_INTELIGENCIA",

            "erro":
                str(
                    erro
                ),

            "mensagem":
                "A localização foi concluída normalmente, "
                "mas houve falha ao atualizar a inteligência "
                "do inventário rotativo.",
        }

# ============================================================
# REGISTRAR CONCLUSÃO DA LOCALIZAÇÃO
#
# Deve ser chamado após SessoesContagem.Status = ENCERRADA.
# ============================================================

# ============================================================
# PROCESSAR INTELIG?NCIA P?S-CONCLUS?O EM BACKGROUND
#
# Esta rotina:
# - abre uma nova conex?o;
# - n?o reutiliza a conex?o da requisi??o HTTP;
# - executa somente ap?s a conclus?o operacional;
# - n?o pode desfazer a contagem em caso de falha anal?tica.
# ============================================================

def processar_inteligencia_conclusao_rotativo_background(
    id_sessao: int,
    usuario: str | None = None
):
    uow = None

    try:
        uow = SqlServerUnitOfWork()
        uow.open()

        conn = uow.connection
        cursor = uow.cursor

        sessao = _buscar_sessao(
            cursor=cursor,
            id_sessao=id_sessao
        )

        if not sessao:
            return

        localizacao = (
            _txt(
                sessao.Localizacao
            ).upper()
        )

        if not localizacao:
            return

        armazem = (
            _resolver_armazem_sessao(
                cursor=cursor,
                id_inventario=sessao.ID_Inventario,
                localizacao=localizacao,
                armazem_inventario=sessao.cArmazem
            )
        )

        executar_orquestracao_rotativo(
            conn=conn,
            cursor=cursor,
            cliente_id=sessao.ClienteId,
            armazem=armazem,
            origem_evento="CONCLUSAO_LOCALIZACAO",
            localizacao=localizacao,
            id_inventario=sessao.ID_Inventario,
            id_rodada=sessao.ID_Rodada,
            usuario=(
                _txt(usuario)
                or None
            ),
            limite_score_sugestao=50.0,
            quantidade_sugestoes=20,
            retornar_painel=True,
        )

    except Exception as erro:
        print(
            "[ROTATIVO][BACKGROUND] "
            f"Falha na inteligencia da sessao {id_sessao}: {erro}"
        )

    finally:
        if uow:
            uow.close()


def registrar_conclusao_localizacao_rotativo(
    conn,
    cursor,
    id_sessao: int,
    usuario: str | None = None,
    processar_inteligencia: bool = True
):
    usuario = (
        _txt(usuario)
        or
        None
    )

    sessao = (
        _buscar_sessao(
            cursor=cursor,
            id_sessao=id_sessao
        )
    )

    if not sessao:
        raise BusinessRuleViolation(
            "Sessão de contagem não encontrada."
        )

    if (
        _txt(
            sessao.Status
        ).upper()
        !=
        "ENCERRADA"
    ):
        raise BusinessRuleViolation(
            "A sessão precisa estar ENCERRADA antes "
            "de registrar a cobertura do ciclo."
        )

    localizacao = (
        _txt(
            sessao.Localizacao
        ).upper()
    )

    if not localizacao:
        raise BusinessRuleViolation(
            "A sessão não possui localização."
        )

    armazem = (
        _resolver_armazem_sessao(
            cursor=cursor,
            id_inventario=sessao.ID_Inventario,
            localizacao=localizacao,
            armazem_inventario=sessao.cArmazem
        )
    )

    ciclo = (
        _buscar_ciclo_aberto(
            cursor=cursor,
            cliente_id=sessao.ClienteId,
            armazem=armazem
        )
    )

    if not ciclo:
        raise BusinessRuleViolation(
            "Não existe ciclo rotativo ABERTO para "
            "o cliente/armazém desta sessão."
        )

    ciclo_localizacao = (
        _buscar_localizacao_ciclo(
            cursor=cursor,
            id_ciclo=ciclo.ID_Ciclo,
            localizacao=localizacao
        )
    )

    if not ciclo_localizacao:
        raise BusinessRuleViolation(
            "A localização da sessão não pertence "
            "ao ciclo rotativo atual."
        )

    # Idempotência: não duplica histórico se endpoint for chamado 2x.
    if (
        _txt(
            ciclo_localizacao.Status
        ).upper()
        ==
        "CONTADA"
    ):
        return {
            "registrado": False,
            "motivo": "LOCALIZACAO_JA_CONTADA_NO_CICLO",
            "id_ciclo":
                ciclo.ID_Ciclo,
            "codigo_ciclo":
                ciclo.CodigoCiclo,
            "localizacao":
                localizacao,
            "status":
                "CONTADA"
        }

    resumo_contagens = (
        _resumo_contagens_sessao(
            cursor=cursor,
            id_sessao=id_sessao
        )
    )

    resumo_divergencias = (
        _resumo_divergencias(
            cursor=cursor,
            id_inventario=sessao.ID_Inventario,
            id_sessao=sessao.ID_Sessao,
            localizacao=localizacao
        )
    )

    # QuantidadeItens representa o universo efetivamente analisado
    # no confronto Snapshot x Contagem.
    #
    # Isso inclui também itens existentes no estoque que não foram
    # bipados, por exemplo uma FALTA com QtdContada = 0.
    quantidade_itens = (
        resumo_divergencias[
            "total_itens_analisados"
        ]
    )

    quantidade_itens_divergentes = (
        resumo_divergencias[
            "itens_divergentes"
        ]
    )

    quantidade_itens_ok = (
        resumo_divergencias[
            "itens_ok"
        ]
    )

    try:
        # ----------------------------------------------------
        # 1. Marca localização do ciclo como CONTADA
        # ----------------------------------------------------

        cursor.execute(
            """
            UPDATE dbo.CicloRotativoLocalizacoes
            SET
                Status = 'CONTADA',
                DataInicioContagem = COALESCE(
                    DataInicioContagem,
                    ?
                ),
                DataConclusao = ?,
                ID_Inventario = ?,
                ID_Rodada = ?,
                UsuarioContagem = ?,
                DataHoraAtualizacao = SYSDATETIME()
            WHERE
                ID_CicloLocalizacao = ?
            """,
            (
                sessao.DataHoraInicio,
                sessao.DataHoraFim,
                sessao.ID_Inventario,
                sessao.ID_Rodada,
                usuario,
                ciclo_localizacao.ID_CicloLocalizacao
            )
        )

        # ----------------------------------------------------
        # 2. Atualiza estado atual da localização
        # ----------------------------------------------------

        cursor.execute(
            """
            UPDATE dbo.RotativoLocalizacoes
            SET
                Status = 'CONTADA',
                UltimaContagem = ?,
                ID_InventarioUltimaContagem = ?,
                ID_RodadaUltimaContagem = ?,
                DataHoraAtualizacao = SYSDATETIME()
            WHERE
                ID_RotativoLocalizacao = ?
            """,
            (
                sessao.DataHoraFim,
                sessao.ID_Inventario,
                sessao.ID_Rodada,
                ciclo_localizacao.ID_RotativoLocalizacao
            )
        )

        # ----------------------------------------------------
        # 3. Grava histórico da cobertura
        # ----------------------------------------------------

        cursor.execute(
            """
            INSERT INTO dbo.RotativoHistoricoLocalizacoes (
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
            )
            VALUES (
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                SYSDATETIME(),
                ?
            )
            """,
            (
                ciclo_localizacao.ID_RotativoLocalizacao,
                sessao.ClienteId,
                armazem,
                localizacao,
                sessao.ID_Inventario,
                sessao.ID_Rodada,
                sessao.DataHoraInicio,
                sessao.DataHoraFim,
                sessao.DataHoraFim,
                usuario,
                _bool(
                    sessao.LocalizacaoVazia
                ),
                resumo_divergencias[
                    "possui_divergencia"
                ],
                quantidade_itens,
                quantidade_itens_ok,
                quantidade_itens_divergentes,
                ciclo_localizacao.ScoreRiscoEntrada,
                ciclo_localizacao.ClassificacaoRiscoEntrada,
                ciclo.ID_Ciclo
            )
        )

        # ----------------------------------------------------
        # 4. Recalcula cobertura e pode fechar o ciclo
        # ----------------------------------------------------

        cobertura = (
            _recalcular_ciclo(
                cursor=cursor,
                id_ciclo=ciclo.ID_Ciclo,
                usuario=usuario
            )
        )

        conn.commit()

    except Exception:
        conn.rollback()
        raise
    # ========================================================
    # 5. ATUALIZAR INTELIGÊNCIA DO ROTATIVO
    #
    # Executado somente APÓS o commit operacional.
    # ========================================================

    if processar_inteligencia:
        inteligencia = (
            _executar_inteligencia_pos_conclusao(
                conn=conn,
                cursor=cursor,
                cliente_id=sessao.ClienteId,
                armazem=armazem,
                localizacao=localizacao,
                id_inventario=sessao.ID_Inventario,
                id_rodada=sessao.ID_Rodada,
                usuario=usuario,
                ciclo_concluido=(
                    cobertura[
                        "ciclo_concluido"
                    ]
                ),
            )
        )

    else:
        inteligencia = {
            "executada": False,
            "motivo": "PROCESSAMENTO_POS_RESPOSTA",
            "resultado": None,
            "erro": None,
            "mensagem": (
                "A conclus?o operacional foi registrada. "
                "A intelig?ncia rotativa ser? atualizada "
                "ap?s a resposta ao operador."
            ),
        }

    return {
        "registrado": True,
        "motivo": "LOCALIZACAO_CONTADA_REGISTRADA",
        "sessao": {
            "id_sessao":
                sessao.ID_Sessao,

            "id_inventario":
                sessao.ID_Inventario,

            "id_rodada":
                sessao.ID_Rodada,

            "localizacao":
                localizacao,

            "localizacao_vazia":
                _bool(
                    sessao.LocalizacaoVazia
                ),

            "data_hora_inicio":
                sessao.DataHoraInicio,

            "data_hora_fim":
                sessao.DataHoraFim
        },
        "resultado_operacional": {
            "bipagens_ativas":
                resumo_contagens[
                    "bipagens_ativas"
                ],

            "bipagens_canceladas":
                resumo_contagens[
                    "bipagens_canceladas"
                ],

            "quantidade_registrada":
                resumo_contagens[
                    "quantidade_ativa"
                ],

            "itens_contados":
                quantidade_itens,

            "possui_divergencia":
                resumo_divergencias[
                    "possui_divergencia"
                ],

            "itens_divergentes":
                quantidade_itens_divergentes
        },
            "ciclo": {
            "id_ciclo":
                ciclo.ID_Ciclo,

            "codigo_ciclo":
                ciclo.CodigoCiclo,

            **cobertura
        },

        "inteligencia": {
            "executada":
                inteligencia[
                    "executada"
                ],

            "motivo":
                inteligencia[
                    "motivo"
                ],

            "resultado":
                inteligencia.get(
                    "resultado"
                ),

            "erro":
                inteligencia.get(
                    "erro"
                ),

            "mensagem":
                inteligencia.get(
                    "mensagem"
                ),
        }
    }