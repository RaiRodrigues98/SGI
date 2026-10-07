from types import SimpleNamespace

from domain.exceptions import BusinessRuleViolation
from domain.exceptions import NotFoundError

from services.analise_gestor import (
    analisar_inventario_gestor,
)
from services.analise_rotativo import (
    analisar_inventario_rotativo,
)

from services.configuracoes_inventario_aplicadas import (
    obter_tipo_rodada_aplicada,
    obter_tipo_proxima_rodada_aplicada,
)

from services.rodadas.preview import (
    visualizar_proxima_rodada,
)


# ============================================================
# NORMALIZAÇÃO
# ============================================================

def _texto(valor):

    if valor is None:
        return None

    return str(valor).strip()


def _tipos_rodada_aplicados(
    cursor,
    id_inventario: int,
    tipo_inventario: str,
    numero_rodada: int,
):
    """Resolve a etapa pela configuracao congelada do inventario."""

    try:
        tipo_atual = obter_tipo_rodada_aplicada(
            cursor=cursor,
            id_inventario=id_inventario,
            numero_rodada=numero_rodada,
        )
        tipo_proxima = obter_tipo_proxima_rodada_aplicada(
            cursor=cursor,
            id_inventario=id_inventario,
            numero_rodada_atual=numero_rodada,
        )
    except (BusinessRuleViolation, NotFoundError):
        tipo_normalizado = (tipo_inventario or "").strip().upper()
        tipo_atual = (
            "COMPLETA"
            if numero_rodada == 1
            or (tipo_normalizado == "OFICIAL" and numero_rodada <= 2)
            else "DIVERGENCIAS"
        )
        tipo_proxima = "NAO_CONFIGURADA"

    return (
        str(tipo_atual or "NAO_CONFIGURADA").strip().upper(),
        str(tipo_proxima or "NAO_CONFIGURADA").strip().upper(),
    )



def _tipos_rodadas_aplicados_em_lote(
    cursor,
    inventarios,
):
    """
    Carrega a configura??o das rodadas em lote.

    Evita consultar repetidamente a configura??o aplicada
    para cada invent?rio retornado pela Central.
    """

    resultado = {}
    ids = []

    for inventario in inventarios:
        id_inventario = int(
            inventario.ID_Inventario
        )

        numero_rodada = int(
            inventario.RodadaAtual or 0
        )

        tipo_inventario = (
            _texto(inventario.Tipo) or ""
        ).upper()

        tipo_atual_padrao = (
            "COMPLETA"
            if (
                numero_rodada == 1
                or (
                    tipo_inventario == "OFICIAL"
                    and numero_rodada <= 2
                )
            )
            else "DIVERGENCIAS"
        )

        resultado[id_inventario] = (
            tipo_atual_padrao,
            "NAO_CONFIGURADA",
        )

        ids.append(id_inventario)

    if not ids:
        return resultado

    tamanho_bloco = 500

    for inicio in range(
        0,
        len(ids),
        tamanho_bloco,
    ):
        bloco = ids[
            inicio:
            inicio + tamanho_bloco
        ]

        placeholders = ", ".join(
            "?"
            for _ in bloco
        )

        cursor.execute(
            f"""
            SELECT
                I.ID_Inventario,
                I.RodadaAtual,

                Configuracao.ID_ConfiguracaoAplicada,
                Configuracao.MaxRodadas,

                RodadaAtualAplicada.TipoRodada
                    AS TipoRodadaAtual,

                ProximaRodadaAplicada.TipoRodada
                    AS TipoProximaRodada

            FROM dbo.Inventarios I

            OUTER APPLY
            (
                SELECT TOP 1
                    A.ID_ConfiguracaoAplicada,
                    A.MaxRodadas

                FROM dbo.ConfiguracoesInventarioAplicadas A

                WHERE
                    A.ID_Inventario = I.ID_Inventario
                    AND A.Ativa = 1

                ORDER BY
                    A.ID_ConfiguracaoAplicada DESC
            ) Configuracao

            OUTER APPLY
            (
                SELECT TOP 1
                    R.TipoRodada

                FROM
                    dbo.ConfiguracoesRodadasInventarioAplicadas R

                WHERE
                    R.ID_ConfiguracaoAplicada =
                        Configuracao.ID_ConfiguracaoAplicada
                    AND R.NumeroRodada = I.RodadaAtual
                    AND R.Ativa = 1

                ORDER BY
                    R.ID_ConfiguracaoRodadaAplicada DESC
            ) RodadaAtualAplicada

            OUTER APPLY
            (
                SELECT TOP 1
                    R.TipoRodada

                FROM
                    dbo.ConfiguracoesRodadasInventarioAplicadas R

                WHERE
                    R.ID_ConfiguracaoAplicada =
                        Configuracao.ID_ConfiguracaoAplicada
                    AND R.NumeroRodada = I.RodadaAtual + 1
                    AND R.Ativa = 1

                ORDER BY
                    R.ID_ConfiguracaoRodadaAplicada DESC
            ) ProximaRodadaAplicada

            WHERE
                I.ID_Inventario IN ({placeholders})
            """,
            tuple(bloco),
        )

        for linha in cursor.fetchall():
            id_inventario = int(
                linha.ID_Inventario
            )

            if (
                linha.ID_ConfiguracaoAplicada
                is None
            ):
                continue

            numero_rodada = int(
                linha.RodadaAtual or 0
            )

            max_rodadas = int(
                linha.MaxRodadas or 0
            )

            tipo_atual = (
                _texto(
                    linha.TipoRodadaAtual
                )
                or "NAO_CONFIGURADA"
            ).upper()

            if (
                numero_rodada + 1
                > max_rodadas
            ):
                tipo_proxima = "FINALIZADO"
            else:
                tipo_proxima = (
                    _texto(
                        linha.TipoProximaRodada
                    )
                    or "NAO_CONFIGURADA"
                ).upper()

            resultado[id_inventario] = (
                tipo_atual,
                tipo_proxima,
            )

    return resultado


def _resumo_localizacoes_por_tipo_rodada(
    cursor,
    id_inventario: int,
    id_rodada: int | None,
    tipo_rodada: str,
):
    """Conta somente o universo operacional da rodada atual."""

    if not id_rodada or tipo_rodada == "GESTOR":
        return 0, 0, 0, 0

    if tipo_rodada == "COMPLETA":
        cursor.execute(
            """
            SELECT
                COUNT(*) AS TotalLocalizacoes,
                COALESCE(SUM(CASE
                    WHEN UltimaSessao.ID_Sessao IS NULL THEN 1
                    ELSE 0
                END), 0) AS Pendentes,
                COALESCE(SUM(CASE
                    WHEN UltimaSessao.Status = 'ABERTA' THEN 1
                    ELSE 0
                END), 0) AS EmContagem,
                COALESCE(SUM(CASE
                    WHEN UltimaSessao.ID_Sessao IS NOT NULL
                         AND UltimaSessao.Status <> 'ABERTA' THEN 1
                    ELSE 0
                END), 0) AS Concluidas
            FROM dbo.InventarioEscopoLocalizacoes E
            OUTER APPLY
            (
                SELECT TOP 1
                    S.ID_Sessao,
                    S.Status
                FROM dbo.SessoesContagem S
                WHERE
                    S.ID_Inventario = E.ID_Inventario
                    AND S.ID_Rodada = ?
                    AND S.Localizacao = E.Localizacao
                ORDER BY S.ID_Sessao DESC
            ) UltimaSessao
            WHERE
                E.ID_Inventario = ?
                AND E.Selecionado = 1
            """,
            (id_rodada, id_inventario),
        )
    else:
        cursor.execute(
            """
            SELECT
                COUNT(*) AS TotalLocalizacoes,
                COALESCE(SUM(CASE
                    WHEN Status = 'PENDENTE' THEN 1
                    ELSE 0
                END), 0) AS Pendentes,
                COALESCE(SUM(CASE
                    WHEN Status = 'EM_CONTAGEM' THEN 1
                    ELSE 0
                END), 0) AS EmContagem,
                COALESCE(SUM(CASE
                    WHEN Status = 'CONCLUIDA' THEN 1
                    ELSE 0
                END), 0) AS Concluidas
            FROM dbo.RodadaLocalizacoes
            WHERE
                ID_Inventario = ?
                AND ID_Rodada = ?
            """,
            (id_inventario, id_rodada),
        )

    linha = cursor.fetchone()
    if not linha:
        return 0, 0, 0, 0

    return tuple(int(valor or 0) for valor in linha[:4])


# ============================================================
# LISTAR INVENTÁRIOS
# ============================================================

def listar_inventarios(
    cursor,
    status: str | None = None,
    tipo: str | None = None,
    cliente_id: int | None = None,
    id_inventario: int | None = None
):

    filtros = []
    parametros = []

    if status:
        filtros.append("I.Status = ?")
        parametros.append(status.strip().upper())

    if tipo:
        filtros.append("I.Tipo = ?")
        parametros.append(tipo.strip().upper())

    if cliente_id is not None:
        filtros.append("I.ClienteId = ?")
        parametros.append(cliente_id)

    if id_inventario is not None:
        filtros.append("I.ID_Inventario = ?")
        parametros.append(id_inventario)

    where = ""

    if filtros:
        where = "WHERE " + " AND ".join(filtros)

    cursor.execute(
        f"""
        SELECT
            I.ID_Inventario,
            I.CodigoInventario,
            I.Tipo,
            I.Cliente,
            I.ClienteId,
            I.Descricao,
            I.cArmazem,
            I.RodadaAtual,
            I.Status,
            I.EmAnaliseGestor,
            I.DataHoraEncaminhamentoGestor,
            I.EncaminhadoGestorPor,
            I.DataHoraInicio,
            I.DataHoraFim,
            I.CriadoPor,
            I.FinalizadoPor,

            (
                SELECT COUNT(*)
                FROM dbo.RodadasInventario R
                WHERE R.ID_Inventario = I.ID_Inventario
            ) AS TotalRodadas,

            RodadaAtualInfo.ID_Rodada AS IDRodadaAtual,
            RodadaAtualInfo.Status AS StatusRodada

        FROM dbo.Inventarios I

        OUTER APPLY
        (
            SELECT TOP 1
                R.ID_Rodada,
                R.Status
            FROM dbo.RodadasInventario R
            WHERE
                R.ID_Inventario = I.ID_Inventario
                AND R.NumeroRodada = I.RodadaAtual
            ORDER BY R.ID_Rodada DESC
        ) RodadaAtualInfo


        {where}

        ORDER BY
            I.ID_Inventario DESC
        """,
        tuple(parametros)
    )

    linhas = cursor.fetchall()

    tipos_rodadas_por_inventario = (
        _tipos_rodadas_aplicados_em_lote(
            cursor=cursor,
            inventarios=linhas,
        )
    )

    resultado = []

    for linha in linhas:
        status_inventario = _texto(linha.Status) or ""
        status_normalizado = status_inventario.upper()

        tipo_inventario = (
            _texto(linha.Tipo) or ""
        ).upper()

        (
            tipo_rodada_atual,
            tipo_proxima_rodada,
        ) = tipos_rodadas_por_inventario.get(
            int(linha.ID_Inventario),
            (
                "NAO_CONFIGURADA",
                "NAO_CONFIGURADA",
            ),
        )

        inventario_encerrado = (
            status_normalizado
            in {
                "FINALIZADO",
                "ENCERRADO",
                "CANCELADO",
            }
        )

        if inventario_encerrado:
            (
                total_localizacoes,
                localizacoes_pendentes,
                localizacoes_em_contagem,
                localizacoes_concluidas,
            ) = (0, 0, 0, 0)
        else:
            (
                total_localizacoes,
                localizacoes_pendentes,
                localizacoes_em_contagem,
                localizacoes_concluidas,
            ) = _resumo_localizacoes_por_tipo_rodada(
                cursor=cursor,
                id_inventario=linha.ID_Inventario,
                id_rodada=linha.IDRodadaAtual,
                tipo_rodada=tipo_rodada_atual,
            )

        percentual_progresso = (
            round(
                (
                    localizacoes_concluidas
                    / total_localizacoes
                ) * 100,
                2
            )
            if total_localizacoes > 0
            else 0.0
        )

        if status_normalizado in {"FINALIZADO", "ENCERRADO"}:
            fase_operacional = "FINALIZADO"
            proxima_acao = "CONSULTAR_RESULTADO"

        elif status_normalizado == "CANCELADO":
            fase_operacional = "CANCELADO"
            proxima_acao = "CONSULTAR_INVENTARIO"

        elif bool(linha.EmAnaliseGestor) or tipo_rodada_atual == "GESTOR":
            fase_operacional = "AGUARDANDO_GESTOR"
            proxima_acao = "ANALISAR_GESTOR"

        elif total_localizacoes == 0:
            fase_operacional = "DEFINIR_ESCOPO"
            proxima_acao = "DEFINIR_LOCALIZACOES"

        elif (
            tipo_rodada_atual == "DIVERGENCIAS"
            and localizacoes_em_contagem > 0
        ):
            fase_operacional = "EM_RECONTAGEM"
            proxima_acao = "ACOMPANHAR_RECONTAGEM"

        elif (
            tipo_rodada_atual == "DIVERGENCIAS"
            and localizacoes_pendentes > 0
        ):
            fase_operacional = "AGUARDANDO_RECONTAGEM"
            proxima_acao = "ACOMPANHAR_RECONTAGEM"

        elif localizacoes_em_contagem > 0:
            fase_operacional = "EM_CONTAGEM"
            proxima_acao = "CONTINUAR_CONTAGEM"

        elif localizacoes_pendentes > 0:
            fase_operacional = "AGUARDANDO_CONTAGEM"
            proxima_acao = "INICIAR_CONTAGEM"

        else:
            fase_operacional = "RODADA_CONCLUIDA"
            proxima_acao = "REVISAR_RODADA"

        analise_disponivel = False
        total_divergencias = 0
        divergencias_sem_decisao = 0
        recontagens_pendentes = 0
        divergencias_justificadas = 0
        divergencias_resolvidas = 0
        pode_finalizar = False
        pode_gerar_recontagem = False

        rodada_operacional_concluida = (
            total_localizacoes > 0
            and
            localizacoes_concluidas
            >= total_localizacoes
            and
            localizacoes_pendentes == 0
            and
            localizacoes_em_contagem == 0
        )

        # ====================================================
        # PREVIEW REAL DA PROXIMA RODADA
        #
        # A configuracao informa QUAL seria o tipo da proxima
        # rodada. Ela nao significa, sozinha, que a rodada
        # realmente pode ser criada.
        #
        # Para uma rodada operacional concluida, a Central
        # consulta a mesma regra utilizada pelo fluxo real de
        # criacao de rodadas.
        # ====================================================

        proxima_rodada_operacional_configurada = (
            tipo_inventario == "OFICIAL"
            and
            tipo_proxima_rodada
            in {
                "COMPLETA",
                "DIVERGENCIAS",
            }
        )

        deve_avaliar_preview_proxima_rodada = (
            status_normalizado == "ABERTO"
            and
            rodada_operacional_concluida
            and
            not bool(linha.EmAnaliseGestor)
            and
            proxima_rodada_operacional_configurada
            and
            linha.IDRodadaAtual is not None
            and
            int(linha.RodadaAtual or 0) > 0
        )

        preview_proxima_rodada = None
        preview_proxima_rodada_avaliado = False

        proxima_rodada_operacional_disponivel = False

        if deve_avaliar_preview_proxima_rodada:

            try:

                preview_proxima_rodada = (
                    visualizar_proxima_rodada(
                        cursor=cursor,
                        inventario=SimpleNamespace(
                            ID_Inventario=int(
                                linha.ID_Inventario
                            ),
                            Tipo=tipo_inventario,
                        ),
                        rodada_atual=SimpleNamespace(
                            ID_Rodada=int(
                                linha.IDRodadaAtual
                            ),
                            NumeroRodada=int(
                                linha.RodadaAtual
                            ),
                        ),
                    )
                )

                preview_proxima_rodada_avaliado = (
                    isinstance(
                        preview_proxima_rodada,
                        dict,
                    )
                )

            except (
                BusinessRuleViolation,
                NotFoundError,
            ):
                preview_proxima_rodada = None
                preview_proxima_rodada_avaliado = False

        if preview_proxima_rodada_avaliado:

            tipo_preview = str(
                preview_proxima_rodada.get(
                    "tipo_proxima_rodada"
                )
                or ""
            ).strip().upper()

            proxima_rodada_operacional_disponivel = (
                bool(
                    preview_proxima_rodada.get(
                        "pode_criar",
                        False,
                    )
                )
                and
                tipo_preview
                in {
                    "COMPLETA",
                    "DIVERGENCIAS",
                }
            )

        # Se havia uma proxima rodada operacional configurada,
        # mas o preview nao conseguiu ser avaliado, a Central
        # permanece em RODADA_CONCLUIDA por seguranca.
        #
        # Nao devemos liberar finalizacao nem anunciar uma
        # rodada inexistente com base em uma avaliacao falha.

        preview_operacional_indisponivel = (
            deve_avaliar_preview_proxima_rodada
            and
            not preview_proxima_rodada_avaliado
        )

        deve_analisar_divergencias = (
            status_normalizado == "ABERTO"
            and
            total_localizacoes > 0
            and
            (
                rodada_operacional_concluida
                or
                bool(linha.EmAnaliseGestor)
            )
            and
            not proxima_rodada_operacional_disponivel
            and
            not preview_operacional_indisponivel
        )

        if (
            status_normalizado == "ABERTO"
            and
            rodada_operacional_concluida
            and
            proxima_rodada_operacional_disponivel
        ):
            fase_operacional = (
                "PROXIMA_RODADA_DISPONIVEL"
            )

            proxima_acao = (
                "GERAR_PROXIMA_RODADA"
            )

        if deve_analisar_divergencias:

            try:

                if tipo_inventario == "OFICIAL":

                    analise = (
                        analisar_inventario_gestor(
                            cursor=cursor,
                            id_inventario=linha.ID_Inventario
                        )
                    )

                    resumo_analise = (
                        analise.get("resumo")
                        or {}
                    )

                    total_divergencias = int(
                        resumo_analise.get(
                            "itens_para_decisao_gestor",
                            0
                        )
                        or 0
                    )

                    divergencias_sem_decisao = int(
                        resumo_analise.get(
                            "itens_sem_decisao",
                            0
                        )
                        or 0
                    )

                    recontagens_pendentes = int(
                        resumo_analise.get(
                            "nova_recontagem",
                            0
                        )
                        or 0
                    )

                    divergencias_resolvidas = int(
                        resumo_analise.get(
                            "itens_resolvidos_gestor",
                            0
                        )
                        or 0
                    )

                    pode_finalizar = bool(
                        analise.get(
                            "pode_finalizar_inventario"
                        )
                    ) and bool(
                        analise.get(
                            "operacao_concluida"
                        )
                    )

                    pode_gerar_recontagem = bool(
                        analise.get(
                            "pode_gerar_nova_recontagem"
                        )
                    )

                    analise_disponivel = True

                elif tipo_inventario == "ROTATIVO":

                    analise = (
                        analisar_inventario_rotativo(
                            cursor=cursor,
                            id_inventario=linha.ID_Inventario
                        )
                    )

                    resumo_analise = (
                        analise.get("resumo")
                        or {}
                    )

                    total_divergencias = int(
                        resumo_analise.get(
                            "itens_requerem_decisao",
                            0
                        )
                        or 0
                    )

                    divergencias_sem_decisao = int(
                        resumo_analise.get(
                            "itens_sem_decisao",
                            0
                        )
                        or 0
                    )

                    recontagens_pendentes = int(
                        resumo_analise.get(
                            "itens_para_recontagem",
                            0
                        )
                        or 0
                    )

                    divergencias_justificadas = int(
                        resumo_analise.get(
                            "divergencias_justificadas",
                            0
                        )
                        or 0
                    )

                    divergencias_resolvidas = int(
                        resumo_analise.get(
                            "itens_resolvidos",
                            0
                        )
                        or 0
                    )

                    pode_finalizar = bool(
                        analise.get(
                            "pode_finalizar_inventario"
                        )
                    )

                    pode_gerar_recontagem = bool(
                        analise.get(
                            "pode_gerar_recontagem"
                        )
                    )

                    analise_disponivel = True

            except (
                BusinessRuleViolation,
                NotFoundError,
            ):
                analise_disponivel = False

        # ====================================================
        # FASE AP?S A AN?LISE DAS DIVERG?NCIAS
        # ====================================================

        if analise_disponivel:

            if divergencias_sem_decisao > 0:

                if tipo_inventario == "OFICIAL":
                    fase_operacional = (
                        "AGUARDANDO_GESTOR"
                    )
                    proxima_acao = (
                        "ANALISAR_GESTOR"
                    )

                else:
                    fase_operacional = (
                        "AGUARDANDO_DECISAO"
                    )
                    proxima_acao = (
                        "ANALISAR_ROTATIVO"
                    )

            elif recontagens_pendentes > 0:

                fase_operacional = (
                    "RECONTAGEM_PENDENTE"
                )

                proxima_acao = (
                    "GERAR_RECONTAGEM"
                )

            elif pode_finalizar:

                fase_operacional = (
                    "PRONTO_FINALIZAR"
                )

                proxima_acao = (
                    "FINALIZAR_INVENTARIO"
                )

            else:

                fase_operacional = (
                    "RODADA_CONCLUIDA"
                )

                proxima_acao = (
                    "REVISAR_RODADA"
                )

        resultado.append(
            {
                "id_inventario": linha.ID_Inventario,
                "codigo_inventario": linha.CodigoInventario,
                "tipo": linha.Tipo,
                "cliente": linha.Cliente,
                "cliente_id": linha.ClienteId,
                "descricao": linha.Descricao,
                "armazem": linha.cArmazem,
                "rodada_atual": linha.RodadaAtual,
                "status": linha.Status,
                "em_analise_gestor": bool(
                    linha.EmAnaliseGestor
                ),
                "data_hora_encaminhamento_gestor":
                    linha.DataHoraEncaminhamentoGestor,
                "encaminhado_gestor_por":
                    _texto(linha.EncaminhadoGestorPor),
                "data_hora_inicio": linha.DataHoraInicio,
                "data_hora_fim": linha.DataHoraFim,
                "criado_por": linha.CriadoPor,
                "finalizado_por": linha.FinalizadoPor,
                "total_rodadas": int(
                    linha.TotalRodadas or 0
                ),
                "id_rodada_atual": linha.IDRodadaAtual,
                "status_rodada":
                    _texto(linha.StatusRodada),
                "total_localizacoes": total_localizacoes,
                "localizacoes_pendentes":
                    localizacoes_pendentes,
                "localizacoes_em_contagem":
                    localizacoes_em_contagem,
                "localizacoes_concluidas":
                    localizacoes_concluidas,
                "percentual_progresso":
                    percentual_progresso,
                "fase_operacional":
                    fase_operacional,
                "proxima_acao":
                    proxima_acao,

                "tipo_rodada_atual":
                    tipo_rodada_atual,

                "tipo_proxima_rodada":
                    tipo_proxima_rodada,

                "analise_disponivel":
                    analise_disponivel,

                "total_divergencias":
                    total_divergencias,

                "divergencias_sem_decisao":
                    divergencias_sem_decisao,

                "recontagens_pendentes":
                    recontagens_pendentes,

                "divergencias_justificadas":
                    divergencias_justificadas,

                "divergencias_resolvidas":
                    divergencias_resolvidas,

                "pode_finalizar":
                    pode_finalizar,

                "pode_gerar_recontagem":
                    pode_gerar_recontagem
            }
        )

    return resultado


# ============================================================
# DETALHE DO INVENTÁRIO
# ============================================================

def consultar_inventario(
    cursor,
    id_inventario: int
):

    cursor.execute(
        """
        SELECT
            ID_Inventario,
            CodigoInventario,
            Tipo,
            Cliente,
            ClienteId,
            Descricao,
            cArmazem,
            RodadaAtual,
            Status,
            EmAnaliseGestor,
            DataHoraEncaminhamentoGestor,
            EncaminhadoGestorPor,
            DataHoraInicio,
            DataHoraFim,
            CriadoPor,
            DataHoraCriacao,
            FinalizadoPor

        FROM dbo.Inventarios

        WHERE ID_Inventario = ?
        """,
        id_inventario
    )

    linha = cursor.fetchone()

    if not linha:

        raise NotFoundError(
            "Inventário não encontrado."
        )

    resumo_operacional = listar_inventarios(
        cursor=cursor,
        id_inventario=id_inventario
    )

    if not resumo_operacional:
        raise NotFoundError(
            "Inventario operacional nao encontrado."
        )

    operacional = resumo_operacional[0]

    return {
        "id_inventario":
            linha.ID_Inventario,

        "codigo_inventario":
            linha.CodigoInventario,

        "tipo":
            linha.Tipo,

        "cliente":
            linha.Cliente,

        "cliente_id":
            linha.ClienteId,

        "descricao":
            linha.Descricao,

        "armazem":
            linha.cArmazem,

        "rodada_atual":
            linha.RodadaAtual,

        "status":
            linha.Status,

        "em_analise_gestor":
            bool(linha.EmAnaliseGestor),

        "data_hora_encaminhamento_gestor":
            linha.DataHoraEncaminhamentoGestor,

        "encaminhado_gestor_por":
            _texto(linha.EncaminhadoGestorPor),

        "data_hora_inicio":
            linha.DataHoraInicio,

        "data_hora_fim":
            linha.DataHoraFim,

        "criado_por":
            linha.CriadoPor,

        "data_hora_criacao":
            linha.DataHoraCriacao,

        "finalizado_por":
            linha.FinalizadoPor,

        "fase_operacional":
            operacional["fase_operacional"],

        "proxima_acao":
            operacional["proxima_acao"],

        "analise_disponivel":
            operacional["analise_disponivel"],

        "pode_finalizar":
            operacional["pode_finalizar"],

        "pode_gerar_recontagem":
            operacional["pode_gerar_recontagem"],

        "total_localizacoes":
            operacional["total_localizacoes"],

        "localizacoes_pendentes":
            operacional["localizacoes_pendentes"],

        "localizacoes_em_contagem":
            operacional["localizacoes_em_contagem"],

        "total_divergencias":
            operacional["total_divergencias"],

        "divergencias_sem_decisao":
            operacional["divergencias_sem_decisao"],

        "recontagens_pendentes":
            operacional["recontagens_pendentes"],

        "localizacoes_concluidas":
            operacional["localizacoes_concluidas"],

        "percentual_progresso":
            operacional["percentual_progresso"]
    }


# ============================================================
# RODADA ATUAL
# ============================================================

def consultar_rodada_atual(
    cursor,
    id_inventario: int
):

    cursor.execute(
        """
        SELECT
            I.ID_Inventario,
            I.CodigoInventario,
            I.Tipo,
            I.RodadaAtual,

            R.ID_Rodada,
            R.NumeroRodada,
            R.Status,
            R.DataHoraInicio

        FROM dbo.Inventarios I

        LEFT JOIN dbo.RodadasInventario R
            ON R.ID_Inventario =
               I.ID_Inventario

           AND R.NumeroRodada =
               I.RodadaAtual

        WHERE I.ID_Inventario = ?
        """,
        id_inventario
    )

    linha = cursor.fetchone()

    if not linha:

        raise NotFoundError(
            "Inventário não encontrado."
        )

    if linha.ID_Rodada is None:

        raise NotFoundError(
            "Rodada atual não encontrada."
        )

    return {
        "id_inventario":
            linha.ID_Inventario,

        "codigo_inventario":
            linha.CodigoInventario,

        "tipo_inventario":
            linha.Tipo,

        "rodada_atual":
            linha.RodadaAtual,

        "id_rodada":
            linha.ID_Rodada,

        "numero_rodada":
            linha.NumeroRodada,

        "status":
            linha.Status,

        "data_hora_inicio":
            linha.DataHoraInicio
    }


# ============================================================
# LOCALIZAÇÕES DO INVENTÁRIO
# ============================================================

def consultar_localizacoes_inventario(
    cursor,
    id_inventario: int
):

    inventario = consultar_inventario(
        cursor=cursor,
        id_inventario=id_inventario
    )

    tipo = (
        inventario["tipo"]
        .strip()
        .upper()
    )

    rodada_atual = (
        inventario["rodada_atual"]
    )

    cursor.execute(
        """
        SELECT TOP 1
            ID_Rodada

        FROM dbo.RodadasInventario

        WHERE
            ID_Inventario = ?
            AND NumeroRodada = ?
        """,
        (
            id_inventario,
            rodada_atual
        )
    )

    rodada = cursor.fetchone()

    id_rodada = (
        rodada.ID_Rodada
        if rodada
        else None
    )

    # ========================================================
    # ESCOPO COMPLETO: R1 OU R2 OFICIAL CONFIGURADA COMO COMPLETA
    # ========================================================

    usar_escopo_completo = (
        rodada_atual == 1
    )

    if (
        tipo == "OFICIAL"
        and rodada_atual == 2
    ):
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM dbo.RodadaLocalizacoes
            WHERE
                ID_Inventario = ?
                AND ID_Rodada = ?
            """,
            (
                id_inventario,
                id_rodada
            )
        )

        possui_escopo_da_rodada = (
            int(
                cursor.fetchone()[0] or 0
            ) > 0
        )

        usar_escopo_completo = (
            not possui_escopo_da_rodada
        )

    if usar_escopo_completo:

        cursor.execute(
            """
            SELECT
                E.Localizacao AS Localizacao,

                E.Selecionado,

                UltimaSessao.ID_Sessao,
                UltimaSessao.Status AS StatusSessao

            FROM dbo.InventarioEscopoLocalizacoes E

            OUTER APPLY
            (
                SELECT TOP 1
                    S.ID_Sessao,
                    S.Status

                FROM dbo.SessoesContagem S

                WHERE
                    S.ID_Inventario = E.ID_Inventario
                    AND S.ID_Rodada = ?
                    AND S.Localizacao = E.Localizacao

                ORDER BY
                    S.ID_Sessao DESC
            ) UltimaSessao

            WHERE
                E.ID_Inventario = ?
                AND E.Selecionado = 1

            ORDER BY
                E.Localizacao
            """,
            (
                id_rodada,
                id_inventario
            )
        )

        linhas = cursor.fetchall()

        resultado = []

        for linha in linhas:

            if linha.ID_Sessao is None:

                status = "PENDENTE"

            elif linha.StatusSessao == "ABERTA":

                status = "EM_CONTAGEM"

            else:

                status = "CONCLUIDA"

            resultado.append(
                {
                    "localizacao":
                        linha.Localizacao,

                    "id_sessao":
                        linha.ID_Sessao,

                    "status":
                        status
                }
            )

        return {
            "id_inventario":
                id_inventario,

            "tipo":
                tipo,

            "rodada_atual":
                rodada_atual,

            "id_rodada":
                id_rodada,

            "localizacoes":
                resultado
        }

    # ========================================================
    # ESCOPO ESPECIFICO DA RODADA
    # ========================================================

    cursor.execute(
        """
        SELECT
            RL.ID_RodadaLocalizacao,
            RL.Localizacao,
            RL.Status

        FROM dbo.RodadaLocalizacoes RL

        WHERE
            RL.ID_Inventario = ?
            AND RL.ID_Rodada = ?

        ORDER BY
            RL.Localizacao
        """,
        (
            id_inventario,
            id_rodada
        )
    )

    linhas = cursor.fetchall()

    return {
        "id_inventario":
            id_inventario,

        "tipo":
            tipo,

        "rodada_atual":
            rodada_atual,

        "id_rodada":
            id_rodada,

        "localizacoes": [
            {
                "id_rodada_localizacao":
                    linha.ID_RodadaLocalizacao,

                "localizacao":
                    linha.Localizacao,

                "status":
                    linha.Status
            }
            for linha in linhas
        ]
    }


# ============================================================
# VISÃO OPERACIONAL ATUAL
# ============================================================

def consultar_contagem_atual(
    cursor,
    id_inventario: int
):

    inventario = consultar_inventario(
        cursor=cursor,
        id_inventario=id_inventario
    )

    rodada = consultar_rodada_atual(
        cursor=cursor,
        id_inventario=id_inventario
    )

    localizacoes = (
        consultar_localizacoes_inventario(
            cursor=cursor,
            id_inventario=id_inventario
        )
    )

    lista = (
        localizacoes["localizacoes"]
    )

    pendentes = sum(
        1
        for item in lista
        if item["status"] == "PENDENTE"
    )

    em_contagem = sum(
        1
        for item in lista
        if item["status"] == "EM_CONTAGEM"
    )

    concluidas = sum(
        1
        for item in lista
        if item["status"] == "CONCLUIDA"
    )

    return {
        "id_inventario":
            id_inventario,

        "codigo_inventario":
            inventario[
                "codigo_inventario"
            ],

        "tipo":
            inventario["tipo"],

        "status_inventario":
            inventario["status"],

        "rodada": rodada,

        "resumo_operacional": {
            "total_localizacoes":
                len(lista),

            "pendentes":
                pendentes,

            "em_contagem":
                em_contagem,

            "concluidas":
                concluidas
        },

        "localizacoes":
            lista
    }
# ============================================================
# DETALHE OPERACIONAL DA LOCALIZAÇÃO
#
# Mantém contagem cega:
#
# NÃO retorna:
# - SaldoInventario
# - QtdEstoque
# - Quantidade esperada
#
# Retorna somente informações operacionais e itens já bipados.
# ============================================================

def consultar_detalhe_localizacao(
    cursor,
    id_inventario: int,
    localizacao: str
):

    localizacao = (
        str(localizacao)
        .strip()
        .upper()
    )

    if not localizacao:

        raise BusinessRuleViolation(
            "Localização obrigatória."
        )

    # ========================================================
    # 1. INVENTÁRIO
    # ========================================================

    inventario = consultar_inventario(
        cursor=cursor,
        id_inventario=id_inventario
    )

    tipo = (
        str(
            inventario["tipo"]
        )
        .strip()
        .upper()
    )

    rodada_atual = (
        inventario["rodada_atual"]
    )

    # ========================================================
    # 2. RODADA ATUAL
    # ========================================================

    cursor.execute(
        """
        SELECT
            ID_Rodada,
            NumeroRodada,
            Status

        FROM dbo.RodadasInventario

        WHERE
            ID_Inventario = ?
            AND NumeroRodada = ?
        """,
        (
            id_inventario,
            rodada_atual
        )
    )

    rodada = cursor.fetchone()

    if not rodada:

        raise NotFoundError(
            "Rodada atual não encontrada."
        )

    id_rodada = (
        rodada.ID_Rodada
    )

    # ========================================================
    # 3. VALIDA SE LOCALIZAÇÃO PERTENCE À RODADA
    #
    # R1 OU R2 OFICIAL COMPLETA:
    # InventarioEscopoLocalizacoes
    #
    # RODADAS COM ESCOPO ESPECIFICO:
    # RodadaLocalizacoes
    # ========================================================

    usar_escopo_completo_localizacao = (
        rodada.NumeroRodada == 1
    )

    if (
        tipo == "OFICIAL"
        and rodada.NumeroRodada == 2
    ):
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM dbo.RodadaLocalizacoes
            WHERE
                ID_Inventario = ?
                AND ID_Rodada = ?
            """,
            (
                id_inventario,
                id_rodada
            )
        )

        possui_localizacoes_da_rodada = (
            int(
                cursor.fetchone()[0] or 0
            ) > 0
        )

        usar_escopo_completo_localizacao = (
            not possui_localizacoes_da_rodada
        )

    if usar_escopo_completo_localizacao:

        cursor.execute(
            """
            SELECT TOP 1
                ID_EscopoLocalizacao,
                Selecionado

            FROM dbo.InventarioEscopoLocalizacoes

            WHERE
                ID_Inventario = ?

                AND Localizacao = ?
            """,
            (
                id_inventario,
                localizacao
            )
        )

        escopo = cursor.fetchone()

        if not escopo:

            raise NotFoundError(
                "Localização não pertence "
                    "ao escopo deste inventário."
            )

        if not escopo.Selecionado:

            raise BusinessRuleViolation(
                "Esta localização foi retirada "
                    "do escopo do inventário."
            )

    else:

        cursor.execute(
            """
            SELECT TOP 1
                ID_RodadaLocalizacao,
                Status

            FROM dbo.RodadaLocalizacoes

            WHERE
                ID_Inventario = ?
                AND ID_Rodada = ?

                AND Localizacao = ?
            """,
            (
                id_inventario,
                id_rodada,
                localizacao
            )
        )

        escopo = cursor.fetchone()

        if not escopo:

            raise NotFoundError(
                "Localização não pertence "
                    "ao escopo desta rodada."
            )

    # ========================================================
    # 4. BUSCA ÚLTIMA SESSÃO DA LOCALIZAÇÃO
    # ========================================================

    cursor.execute(
        """
        SELECT TOP 1
            ID_Sessao,
            Status,
            DataHoraInicio,
            DataHoraFim,
            LocalizacaoVazia,
            UsuarioAberturaLogin,
            UsuarioAberturaNome

        FROM dbo.SessoesContagem

        WHERE
            ID_Inventario = ?
            AND ID_Rodada = ?

            AND Localizacao = ?

        ORDER BY
            ID_Sessao DESC
        """,
        (
            id_inventario,
            id_rodada,
            localizacao
        )
    )

    ultima_sessao = (
        cursor.fetchone()
    )

    usuario_sessao_login = None
    usuario_sessao_nome = None

    if ultima_sessao:
        usuario_sessao_login = (
            str(
                ultima_sessao.UsuarioAberturaLogin
            ).strip()
            if ultima_sessao.UsuarioAberturaLogin
            else None
        )

        usuario_sessao_nome = (
            str(
                ultima_sessao.UsuarioAberturaNome
            ).strip()
            if ultima_sessao.UsuarioAberturaNome
            else usuario_sessao_login
        )

    # ========================================================
    # 5. DEFINE STATUS OPERACIONAL
    # ========================================================

    if not ultima_sessao:

        status_localizacao = (
            "PENDENTE"
        )

        id_sessao_atual = None

        localizacao_vazia = False

    elif ultima_sessao.Status == "ABERTA":

        status_localizacao = (
            "EM_CONTAGEM"
        )

        id_sessao_atual = (
            ultima_sessao.ID_Sessao
        )

        localizacao_vazia = False

    else:

        status_localizacao = (
            "CONCLUIDA"
        )

        id_sessao_atual = (
            ultima_sessao.ID_Sessao
        )

        localizacao_vazia = bool(
            ultima_sessao.LocalizacaoVazia
        )

    # ========================================================
    # 6. BUSCA TODAS AS CONTAGENS ATIVAS DA LOCALIZAÇÃO
    #
    # Importante:
    #
    # Pode existir mais de uma sessão encerrada para a mesma
    # localização. Somamos as contagens válidas da rodada.
    # ========================================================

    cursor.execute(
        """
        SELECT
            C.Codigo AS Codigo,

            ISNULL(C.Lote, '') AS Lote,

            SUM(
                C.Quantidade
            ) AS Quantidade,

            MAX(
                E.Descricao
            ) AS Produto,

            MAX(
                E.Unidade
            ) AS Unidade,

            MAX(
                E.Categoria
            ) AS Categoria

        FROM dbo.Contagens C

        INNER JOIN dbo.SessoesContagem S
            ON S.ID_Sessao =
               C.ID_Sessao

        LEFT JOIN dbo.InventarioEstoqueSnapshot E
            ON E.ID_Inventario =
               S.ID_Inventario

           AND E.Localizacao =
               S.Localizacao

           AND E.Codigo =
               C.Codigo

           AND ISNULL(E.Lote, '') =
               ISNULL(C.Lote, '')

        WHERE
            S.ID_Inventario = ?
            AND S.ID_Rodada = ?

            AND S.Localizacao = ?
            AND S.ValidaParaConsolidacao = 1

            AND C.Status = 'ATIVA'

        GROUP BY
            C.Codigo,

            ISNULL(C.Lote, '')

        ORDER BY
            C.Codigo,

            ISNULL(C.Lote, '')
        """,
        (
            id_inventario,
            id_rodada,
            localizacao
        )
    )

    linhas = cursor.fetchall()

    itens_bipados = []

    quantidade_total = 0.0

    for linha in linhas:

        quantidade = float(
            linha.Quantidade
        )

        quantidade_total += (
            quantidade
        )

        itens_bipados.append(
            {
                "codigo":
                    linha.Codigo,

                "produto":
                    linha.Produto,

                "lote":
                    linha.Lote,

                "unidade":
                    linha.Unidade,

                "categoria":
                    linha.Categoria,

                "quantidade":
                    quantidade
            }
        )

    # ========================================================
    # 7. CONTAGEM DE SESSÕES DA LOCALIZAÇÃO
    # ========================================================

    cursor.execute(
        """
        SELECT
            COUNT(*) AS TotalSessoes,

            SUM(
                CASE
                    WHEN Status = 'ABERTA'
                    THEN 1
                    ELSE 0
                END
            ) AS SessoesAbertas,

            SUM(
                CASE
                    WHEN Status = 'ENCERRADA'
                    THEN 1
                    ELSE 0
                END
            ) AS SessoesEncerradas

        FROM dbo.SessoesContagem

        WHERE
            ID_Inventario = ?
            AND ID_Rodada = ?

            AND Localizacao = ?
        """,
        (
            id_inventario,
            id_rodada,
            localizacao
        )
    )

    resumo_sessoes = (
        cursor.fetchone()
    )

    total_sessoes = int(
        resumo_sessoes.TotalSessoes
        or 0
    )

    sessoes_abertas = int(
        resumo_sessoes.SessoesAbertas
        or 0
    )

    sessoes_encerradas = int(
        resumo_sessoes.SessoesEncerradas
        or 0
    )

    # ========================================================
    # 8. RETORNO
    # ========================================================

    return {
        "id_inventario":
            id_inventario,

        "codigo_inventario":
            inventario[
                "codigo_inventario"
            ],

        "tipo_inventario":
            tipo,

        "status_inventario":
            inventario["status"],

        "id_rodada":
            id_rodada,

        "numero_rodada":
            rodada.NumeroRodada,

        "status_rodada":
            rodada.Status,

        "localizacao":
            localizacao,

        "status_localizacao":
            status_localizacao,

        "id_sessao_atual":
            id_sessao_atual,

        "usuario_sessao_login":
            usuario_sessao_login,

        "usuario_sessao_nome":
            usuario_sessao_nome,

        "localizacao_vazia":
            localizacao_vazia,

        "contagem_cega":
            True,

        "resumo": {
            "registros_bipados":
                len(
                    itens_bipados
                ),

            "quantidade_total_bipada":
                quantidade_total,

            "total_sessoes":
                total_sessoes,

            "sessoes_abertas":
                sessoes_abertas,

            "sessoes_encerradas":
                sessoes_encerradas
        },

        "itens_bipados":
            itens_bipados
    }
# ============================================================
# BUSCAR PRODUTO PARA CONTAGEM CEGA
#
# Retorna dados cadastrais do item no snapshot.
#
# NÃO retorna:
# - SaldoInventario
# - QtdEstoque
# - quantidade esperada
# - diferença
#
# Se o mesmo código possuir vários lotes, todos são retornados.
# ============================================================

def buscar_produto_contagem(
    cursor,
    id_inventario: int,
    codigo: str
):

    codigo = (
        str(codigo).strip()
        if codigo is not None
        else ""
    )

    if not codigo:

        raise BusinessRuleViolation(
            "Código obrigatório."
        )

    # ========================================================
    # 1. VALIDA INVENTÁRIO
    # ========================================================

    cursor.execute(
        """
        SELECT
            ID_Inventario,
            CodigoInventario,
            Tipo,
            Status

        FROM dbo.Inventarios

        WHERE ID_Inventario = ?
        """,
        id_inventario
    )

    inventario = cursor.fetchone()

    if not inventario:

        raise NotFoundError(
            "Inventário não encontrado."
        )

    if _texto(inventario.Status).upper() != "ABERTO":

        raise BusinessRuleViolation(
            "O inventário não está aberto para contagem."
        )

    # ========================================================
    # 2. BUSCA DADOS CADASTRAIS NO SNAPSHOT
    #
    # A consulta preserva a contagem cega. Nenhuma quantidade
    # ou saldo é selecionado ou devolvido ao operador.
    # ========================================================

    cursor.execute(
        """
        SELECT DISTINCT
            Codigo AS Codigo,
            ISNULL(Lote, '') AS Lote,
            Descricao AS Produto,
            Unidade,
            Categoria

        FROM dbo.InventarioEstoqueSnapshot

        WHERE
            ID_Inventario = ?
            AND LTRIM(RTRIM(Codigo)) = ?

        ORDER BY
            Lote
        """,
        (
            id_inventario,
            codigo
        )
    )

    linhas = cursor.fetchall()

    if not linhas:

        raise NotFoundError(
            "Produto não encontrado no estoque deste inventário."
        )

    lotes = sorted({
        _texto(linha.Lote)
        for linha in linhas
        if _texto(linha.Lote)
    })

    produto = linhas[0]
    possui_lote = bool(lotes)

    return {
        "valido":
            True,

        "id_inventario":
            inventario.ID_Inventario,

        "codigo_inventario":
            inventario.CodigoInventario,

        "tipo_inventario":
            inventario.Tipo,

        "status_inventario":
            inventario.Status,

        "codigo":
            produto.Codigo,

        "produto":
            produto.Produto,

        "unidade":
            produto.Unidade,

        "categoria":
            produto.Categoria,

        "possui_lote":
            possui_lote,

        "lotes":
            lotes,

        "contagem_cega":
            True,

        "proximo_passo": (
            "INFORMAR_LOTE"
            if possui_lote
            else "INFORMAR_QUANTIDADE"
        )
    }

   # ============================================================
# VALIDAR LOTE BIPADO
#
# O lote nunca é selecionado automaticamente.
# O operador obrigatoriamente deve bipar.
# ============================================================

def validar_lote_contagem(
    cursor,
    id_inventario: int,
    codigo: str,
    lote: str
):

    codigo = (
        str(codigo).strip()
        if codigo is not None
        else ""
    )

    lote = (
        str(lote).strip()
        if lote is not None
        else ""
    )

    if not codigo:

        raise BusinessRuleViolation(
            "Código obrigatório."
        )

    if not lote:

        raise BusinessRuleViolation(
            "Lote obrigatório."
        )

    cursor.execute(
        """
        SELECT TOP 1
            Codigo AS Codigo,

            ISNULL(Lote, '') AS Lote,

            Descricao AS Produto,
            Unidade,
            Categoria

        FROM dbo.InventarioEstoqueSnapshot

        WHERE
            ID_Inventario = ?

            AND Codigo = ?

            AND ISNULL(Lote, '') = ?
        """,
        (
            id_inventario,
            codigo,
            lote
        )
    )

    linha = cursor.fetchone()

    if not linha:

        raise NotFoundError(
            "Lote não encontrado para este código "
                "no inventário."
        )

    return {
        "valido":
            True,

        "id_inventario":
            id_inventario,

        "codigo":
            linha.Codigo,

        "lote":
            linha.Lote,

        "produto":
            linha.Produto,

        "unidade":
            linha.Unidade,

        "categoria":
            linha.Categoria,

        "contagem_cega":
            True,

        "proximo_passo":
            "INFORMAR_QUANTIDADE"
    }



# PAGINACAO_CENTRAL_SGI_V1
from datetime import datetime


def _prioridade_fase_central(fase: str) -> int:
    prioridades = {
        "AGUARDANDO_GESTOR": 0,
        "AGUARDANDO_DECISAO": 0,
        "RECONTAGEM_PENDENTE": 1,
        "AGUARDANDO_RECONTAGEM": 1,
        "EM_RECONTAGEM": 1,
        "PROXIMA_RODADA_DISPONIVEL": 2,
        "PRONTO_FINALIZAR": 2,
        "RODADA_CONCLUIDA": 3,
        "EM_CONTAGEM": 4,
        "AGUARDANDO_CONTAGEM": 5,
        "DEFINIR_ESCOPO": 6,
        "FINALIZADO": 7,
        "CANCELADO": 8,
    }
    return prioridades.get(str(fase or "").upper(), 99)


def _data_central(valor):
    if valor is None:
        return None
    if isinstance(valor, datetime):
        return valor.replace(tzinfo=None)
    try:
        return datetime.fromisoformat(str(valor).replace("Z", "+00:00")).replace(tzinfo=None)
    except (TypeError, ValueError):
        return None


def listar_inventarios_central(
    cursor,
    pagina: int = 1,
    por_pagina: int = 25,
    pesquisa: str | None = None,
    tipo: str | None = None,
    status: str | None = None,
    cliente_id: int | None = None,
    fase: str | None = "ATIVAS",
    pendencias: str | None = "TODAS",
    periodo: str | None = "QUALQUER",
    data_inicial: str | None = None,
    data_final: str | None = None,
):
    """Entrega somente a pagina exibida pela Central, preservando suas regras."""
    todos = listar_inventarios(cursor=cursor)
    terminais = {"FINALIZADO", "CANCELADO"}

    status_disponiveis = sorted({
        str(item.get("status") or "").strip().upper()
        for item in todos
        if item.get("status")
    })
    fases_disponiveis = sorted(
        {
            str(item.get("fase_operacional") or "").strip().upper()
            for item in todos
            if item.get("fase_operacional")
        },
        key=_prioridade_fase_central,
    )

    clientes = {}
    for item in todos:
        nome = str(item.get("cliente") or "").strip()
        nome_normalizado = nome.upper()
        if "ENDRESS+HAUSER" not in nome_normalizado and nome_normalizado != "UM GRAU E MEIO":
            continue
        identificador = int(item.get("cliente_id") or 0)
        if identificador > 0:
            clientes[identificador] = nome

    inventarios_ativos = [
        item for item in todos
        if str(item.get("status") or "").strip().upper() not in terminais
    ]

    ano = datetime.now().year
    prefixo = f"INV-{ano}-"
    maior_sequencia = 0
    for item in todos:
        codigo = str(item.get("codigo_inventario") or "")
        if not codigo.startswith(prefixo):
            continue
        try:
            maior_sequencia = max(maior_sequencia, int(codigo[len(prefixo):]))
        except ValueError:
            pass
    proximo_codigo = f"{prefixo}{maior_sequencia + 1:03d}"

    termo = str(pesquisa or "").strip().casefold()
    tipo_normalizado = str(tipo or "TODOS").strip().upper()
    status_normalizado = str(status or "TODOS").strip().upper()
    pendencias_normalizadas = str(pendencias or "TODAS").strip().upper()
    periodo_normalizado = str(periodo or "QUALQUER").strip().upper()

    hoje = datetime.now()
    inicio = fim = None
    if periodo_normalizado == "HOJE":
        inicio = hoje.replace(hour=0, minute=0, second=0, microsecond=0)
        fim = hoje.replace(hour=23, minute=59, second=59, microsecond=999999)
    elif periodo_normalizado in {"ULTIMOS_7_DIAS", "ULTIMOS_30_DIAS"}:
        from datetime import timedelta
        dias = 6 if periodo_normalizado == "ULTIMOS_7_DIAS" else 29
        inicio = (hoje - timedelta(days=dias)).replace(hour=0, minute=0, second=0, microsecond=0)
        fim = hoje.replace(hour=23, minute=59, second=59, microsecond=999999)
    elif periodo_normalizado == "ESTE_MES":
        inicio = hoje.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if hoje.month == 12:
            proximo_mes = hoje.replace(year=hoje.year + 1, month=1, day=1)
        else:
            proximo_mes = hoje.replace(month=hoje.month + 1, day=1)
        from datetime import timedelta
        fim = proximo_mes - timedelta(microseconds=1)
    elif periodo_normalizado == "PERSONALIZADO":
        try:
            inicio = datetime.fromisoformat(data_inicial) if data_inicial else None
        except ValueError:
            inicio = None
        try:
            fim = datetime.fromisoformat(data_final).replace(hour=23, minute=59, second=59, microsecond=999999) if data_final else None
        except ValueError:
            fim = None

    base = []
    for item in todos:
        campos = (
            item.get("id_inventario"),
            item.get("codigo_inventario"),
            item.get("cliente"),
            item.get("cliente_id"),
            item.get("armazem"),
        )
        if termo and not any(termo in str(valor or "").casefold() for valor in campos):
            continue
        if tipo_normalizado != "TODOS" and str(item.get("tipo") or "").upper() != tipo_normalizado:
            continue
        if status_normalizado != "TODOS" and str(item.get("status") or "").upper() != status_normalizado:
            continue
        if cliente_id is not None and int(item.get("cliente_id") or 0) != cliente_id:
            continue

        tem_pendencias = (
            int(item.get("total_localizacoes") or 0) == 0
            or int(item.get("localizacoes_pendentes") or 0) > 0
            or int(item.get("localizacoes_em_contagem") or 0) > 0
        )
        if pendencias_normalizadas == "COM_PENDENCIAS" and not tem_pendencias:
            continue
        if pendencias_normalizadas == "SEM_PENDENCIAS" and tem_pendencias:
            continue

        if inicio or fim:
            data_item = _data_central(item.get("data_hora_inicio"))
            if data_item is None or (inicio and data_item < inicio) or (fim and data_item > fim):
                continue
        base.append(item)

    def contar(fases):
        return sum(1 for item in base if str(item.get("fase_operacional") or "").upper() in fases)

    totais = {
        "preparacao": contar({"DEFINIR_ESCOPO"}),
        "execucao": contar({"AGUARDANDO_CONTAGEM", "EM_CONTAGEM", "AGUARDANDO_RECONTAGEM", "EM_RECONTAGEM"}),
        "aguardando_decisao": contar({"AGUARDANDO_GESTOR", "AGUARDANDO_DECISAO"}),
        "recontagem": contar({"RECONTAGEM_PENDENTE", "AGUARDANDO_RECONTAGEM", "EM_RECONTAGEM"}),
        "pronto_finalizar": contar({"PRONTO_FINALIZAR"}),
        "encerrados": contar(terminais),
    }

    fase_normalizada = str(fase or "ATIVAS").strip().upper()
    filtrados = []
    for item in base:
        fase_item = str(item.get("fase_operacional") or "").strip().upper()
        corresponde = (
            fase_normalizada == "TODAS"
            or (fase_normalizada == "ATIVAS" and fase_item not in terminais)
            or (fase_normalizada == "EM_EXECUCAO" and fase_item in {"AGUARDANDO_CONTAGEM", "EM_CONTAGEM", "AGUARDANDO_RECONTAGEM", "EM_RECONTAGEM"})
            or (fase_normalizada == "AGUARDANDO_DECISAO_GERAL" and fase_item in {"AGUARDANDO_GESTOR", "AGUARDANDO_DECISAO"})
            or (fase_normalizada == "ENCERRADOS" and fase_item in terminais)
            or fase_item == fase_normalizada
        )
        if corresponde:
            filtrados.append(item)

    filtrados.sort(key=lambda item: (
        _prioridade_fase_central(item.get("fase_operacional")),
        -int(item.get("id_inventario") or 0),
    ))

    por_pagina = max(1, min(int(por_pagina or 25), 100))
    total_registros = len(filtrados)
    total_paginas = max(1, (total_registros + por_pagina - 1) // por_pagina)
    pagina = max(1, min(int(pagina or 1), total_paginas))
    inicio_pagina = (pagina - 1) * por_pagina

    return {
        "itens": filtrados[inicio_pagina:inicio_pagina + por_pagina],
        "pagina": pagina,
        "por_pagina": por_pagina,
        "total_registros": total_registros,
        "total_paginas": total_paginas,
        "totais": totais,
        "status_disponiveis": status_disponiveis,
        "clientes_filtro": [
            {"id": identificador, "nome": nome}
            for identificador, nome in sorted(clientes.items(), key=lambda par: par[1].casefold())
        ],
        "fases_disponiveis": fases_disponiveis,
        "inventarios_ativos": inventarios_ativos,
        "proximo_codigo": proximo_codigo,
    }
