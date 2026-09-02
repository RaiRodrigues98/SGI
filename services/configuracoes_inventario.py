from domain.exceptions import BusinessRuleViolation, NotFoundError


# ============================================================
# CONFIGURAÇÕES DO INVENTÁRIO
#
# Responsável por:
#
# - buscar configuração por ClienteId + TipoInventario
# - buscar sequência de rodadas
# - expor regras operacionais para os services
#
# A partir daqui, o objetivo é reduzir regras fixas
# espalhadas pelo código Python.
# ============================================================


# ============================================================
# NORMALIZAÇÃO
# ============================================================

def _normalizar_texto(valor):

    if valor is None:
        return ""

    return str(valor).strip()


def _normalizar_tipo(valor):

    return (
        _normalizar_texto(valor)
        .upper()
    )


# ============================================================
# BUSCAR CONFIGURAÇÃO PRINCIPAL
# ============================================================

def obter_configuracao_inventario(
    cursor,
    cliente_id: int,
    tipo_inventario: str
):

    tipo = _normalizar_tipo(
        tipo_inventario
    )

    if not tipo:

        raise BusinessRuleViolation(
            "Tipo de inventário não informado."
        )

    cursor.execute(
        """
        SELECT TOP 1
            ID_Configuracao,
            ClienteId,
            TipoInventario,

            ValidarLocalizacaoEscopo,
            PermitirLocalizacaoVazia,
            PermitirReaberturaLocalizacao,

            CodigoLivre,
            PermitirCodigoNaoCadastrado,
            PermitirItemForaLocalizacao,

            LoteObrigatorioSeExistir,
            ValidarLoteCodigo,
            ValidarLoteLocalizacao,

            QuantidadeMinima,
            QuantidadeMaxima,

            ContagemCega,

            ConsideraLocalizacaoConciliacao,

            RecontagemPorLocalizacao,
            RodadasIniciais,
            MaxRodadas,

            PermitirGestorAntecipado,
            LimiteItensGestorAntecipado,

            DivergenciaBloqueiaFinalizacao,

            Ativa,

            CriadoPor,
            DataHoraCriacao,
            AlteradoPor,
            DataHoraAlteracao

        FROM dbo.ConfiguracoesInventario

        WHERE
            ClienteId = ?
            AND TipoInventario = ?
            AND Ativa = 1
        """,
        (
            cliente_id,
            tipo
        )
    )

    linha = cursor.fetchone()

    if not linha:

        raise BusinessRuleViolation(
            "Não existe configuração ativa para "
                f"ClienteId={cliente_id} e "
                f"TipoInventario={tipo}."
        )

    return {
        "id_configuracao":
            linha.ID_Configuracao,

        "cliente_id":
            linha.ClienteId,

        "tipo_inventario":
            linha.TipoInventario,

        "validar_localizacao_escopo":
            bool(
                linha.ValidarLocalizacaoEscopo
            ),

        "permitir_localizacao_vazia":
            bool(
                linha.PermitirLocalizacaoVazia
            ),
        "permitir_reabertura_localizacao":
    bool(
        linha.PermitirReaberturaLocalizacao
    ),

        "codigo_livre":
            bool(
                linha.CodigoLivre
            ),

        "permitir_codigo_nao_cadastrado":
            bool(
                linha.PermitirCodigoNaoCadastrado
            ),

        "permitir_item_fora_localizacao":
            bool(
                linha.PermitirItemForaLocalizacao
            ),

        "lote_obrigatorio_se_existir":
            bool(
                linha.LoteObrigatorioSeExistir
            ),

        "validar_lote_codigo":
            bool(
                linha.ValidarLoteCodigo
            ),

        "validar_lote_localizacao":
            bool(
                linha.ValidarLoteLocalizacao
            ),

        "quantidade_minima":
            float(
                linha.QuantidadeMinima
            ),

        "quantidade_maxima":
            float(
                linha.QuantidadeMaxima
            ),

        "contagem_cega":
            bool(
                linha.ContagemCega
            ),

        "considera_localizacao_conciliacao":
            bool(
                linha.ConsideraLocalizacaoConciliacao
            ),

        "recontagem_por_localizacao":
            bool(
                linha.RecontagemPorLocalizacao
            ),

        "rodadas_iniciais":
            int(
                linha.RodadasIniciais
            ),

        "max_rodadas":
            int(
                linha.MaxRodadas
            ),

        "permitir_gestor_antecipado":
            bool(
                linha.PermitirGestorAntecipado
            ),

        "limite_itens_gestor_antecipado":
            int(
                linha.LimiteItensGestorAntecipado
            ),

        "divergencia_bloqueia_finalizacao":
            bool(
                linha.DivergenciaBloqueiaFinalizacao
            ),

        "ativa":
            bool(
                linha.Ativa
            ),

        "criado_por":
            linha.CriadoPor,

        "data_hora_criacao":
            linha.DataHoraCriacao,

        "alterado_por":
            linha.AlteradoPor,

        "data_hora_alteracao":
            linha.DataHoraAlteracao
    }


# ============================================================
# BUSCAR CONFIGURAÇÃO A PARTIR DO INVENTÁRIO
# ============================================================

def obter_configuracao_por_inventario(
    cursor,
    id_inventario: int
):

    cursor.execute(
        """
        SELECT
            ID_Inventario,
            ClienteId,
            Tipo

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

    if inventario.ClienteId is None:

        raise BusinessRuleViolation(
            "O inventário não possui ClienteId "
                "configurado."
        )

    return obter_configuracao_inventario(
        cursor=cursor,
        cliente_id=inventario.ClienteId,
        tipo_inventario=inventario.Tipo
    )


# ============================================================
# BUSCAR RODADAS CONFIGURADAS
# ============================================================

def obter_rodadas_configuradas(
    cursor,
    id_configuracao: int
):

    cursor.execute(
        """
        SELECT
            ID_ConfiguracaoRodada,
            NumeroRodada,
            TipoRodada,
            Ativa

        FROM dbo.ConfiguracoesRodadasInventario

        WHERE
            ID_Configuracao = ?
            AND Ativa = 1

        ORDER BY
            NumeroRodada
        """,
        id_configuracao
    )

    linhas = cursor.fetchall()

    return [
        {
            "id_configuracao_rodada":
                linha.ID_ConfiguracaoRodada,

            "numero_rodada":
                int(
                    linha.NumeroRodada
                ),

            "tipo_rodada":
                linha.TipoRodada,

            "ativa":
                bool(
                    linha.Ativa
                )
        }
        for linha in linhas
    ]


# ============================================================
# CONFIGURAÇÃO COMPLETA
#
# Retorna:
#
# configuração geral
# +
# sequência das rodadas
# ============================================================

def obter_configuracao_completa(
    cursor,
    cliente_id: int,
    tipo_inventario: str
):

    configuracao = (
        obter_configuracao_inventario(
            cursor=cursor,
            cliente_id=cliente_id,
            tipo_inventario=tipo_inventario
        )
    )

    rodadas = (
        obter_rodadas_configuradas(
            cursor=cursor,
            id_configuracao=(
                configuracao[
                    "id_configuracao"
                ]
            )
        )
    )

    configuracao[
        "rodadas"
    ] = rodadas

    return configuracao


# ============================================================
# CONFIGURAÇÃO COMPLETA POR INVENTÁRIO
# ============================================================

def obter_configuracao_completa_por_inventario(
    cursor,
    id_inventario: int
):

    configuracao = (
        obter_configuracao_por_inventario(
            cursor=cursor,
            id_inventario=id_inventario
        )
    )

    configuracao[
        "rodadas"
    ] = (
        obter_rodadas_configuradas(
            cursor=cursor,
            id_configuracao=(
                configuracao[
                    "id_configuracao"
                ]
            )
        )
    )

    return configuracao


# ============================================================
# BUSCAR TIPO DE UMA RODADA
# ============================================================

def obter_tipo_rodada_configurada(
    cursor,
    cliente_id: int,
    tipo_inventario: str,
    numero_rodada: int
):

    configuracao = (
        obter_configuracao_inventario(
            cursor=cursor,
            cliente_id=cliente_id,
            tipo_inventario=tipo_inventario
        )
    )

    cursor.execute(
        """
        SELECT TOP 1
            TipoRodada

        FROM dbo.ConfiguracoesRodadasInventario

        WHERE
            ID_Configuracao = ?
            AND NumeroRodada = ?
            AND Ativa = 1
        """,
        (
            configuracao[
                "id_configuracao"
            ],
            numero_rodada
        )
    )

    linha = cursor.fetchone()

    if not linha:

        return "NAO_CONFIGURADA"

    return _normalizar_tipo(
        linha.TipoRodada
    )


# ============================================================
# BUSCAR TIPO DA PRÓXIMA RODADA
# ============================================================

def obter_tipo_proxima_rodada_configurada(
    cursor,
    cliente_id: int,
    tipo_inventario: str,
    numero_rodada_atual: int
):

    configuracao = (
        obter_configuracao_inventario(
            cursor=cursor,
            cliente_id=cliente_id,
            tipo_inventario=tipo_inventario
        )
    )

    proxima = (
        numero_rodada_atual
        + 1
    )

    if (
        proxima
        >
        configuracao["max_rodadas"]
    ):

        return "FINALIZADO"

    return obter_tipo_rodada_configurada(
        cursor=cursor,
        cliente_id=cliente_id,
        tipo_inventario=tipo_inventario,
        numero_rodada=proxima
    )