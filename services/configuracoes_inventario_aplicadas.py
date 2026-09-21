import json

from domain.exceptions import (
    BusinessRuleViolation,
    ConflictError,
    NotFoundError,
)


def _texto(valor):
    if valor is None:
        return ""

    return str(valor).strip()


def _tipo(valor):
    return _texto(valor).upper()


def _serializar_configuracao(linha):
    return {
        "id_configuracao":
            int(linha.ID_ConfiguracaoAplicada),

        "id_configuracao_aplicada":
            int(linha.ID_ConfiguracaoAplicada),

        "id_configuracao_origem":
            linha.ID_ConfiguracaoOrigem,

        "id_configuracao_operacional_origem":
            linha.ID_ConfiguracaoOperacionalOrigem,

        "id_inventario":
            int(linha.ID_Inventario),

        "cliente_id":
            int(linha.ClienteId),

        "tipo_inventario":
            _tipo(linha.Tipo),

        "origem":
            "INVENTARIO",

        "versao":
            int(linha.Versao),

        "validar_localizacao_escopo":
            bool(linha.ValidarLocalizacaoEscopo),

        "permitir_localizacao_vazia":
            bool(linha.PermitirLocalizacaoVazia),

        "permitir_reabertura_localizacao":
            bool(linha.PermitirReaberturaLocalizacao),

        "permitir_alteracao_escopo_apos_snapshot":
            bool(
                linha.PermitirAlteracaoEscopoAposSnapshot
            ),

        "codigo_livre":
            bool(linha.CodigoLivre),

        "permitir_codigo_nao_cadastrado":
            bool(linha.PermitirCodigoNaoCadastrado),

        "permitir_item_fora_localizacao":
            bool(linha.PermitirItemForaLocalizacao),

        "lote_obrigatorio_se_existir":
            bool(linha.LoteObrigatorioSeExistir),

        "validar_lote_codigo":
            bool(linha.ValidarLoteCodigo),

        "validar_lote_localizacao":
            bool(linha.ValidarLoteLocalizacao),

        "quantidade_minima":
            float(linha.QuantidadeMinima),

        "quantidade_maxima":
            float(linha.QuantidadeMaxima),

        "contagem_cega":
            bool(linha.ContagemCega),

        "considera_localizacao_conciliacao":
            bool(
                linha.ConsideraLocalizacaoConciliacao
            ),

        "recontagem_por_localizacao":
            bool(linha.RecontagemPorLocalizacao),

        "rodadas_iniciais":
            int(linha.RodadasIniciais),

        "max_rodadas":
            int(linha.MaxRodadas),

        "permitir_gestor_antecipado":
            bool(linha.PermitirGestorAntecipado),

        "limite_itens_gestor_antecipado":
            int(linha.LimiteItensGestorAntecipado),

        "divergencia_bloqueia_finalizacao":
            bool(linha.DivergenciaBloqueiaFinalizacao),

        "localizacao_obrigatoria":
            bool(linha.LocalizacaoObrigatoria),

        "localizacao_validar_estoque":
            bool(linha.LocalizacaoValidarEstoque),

        "codigo_obrigatorio":
            bool(linha.CodigoObrigatorio),

        "codigo_validar_estoque":
            bool(linha.CodigoValidarEstoque),

        "lote_obrigatorio_quando_existir":
            bool(linha.LoteObrigatorioQuandoExistir),

        "lote_validar_codigo":
            bool(linha.LoteValidarCodigo),

        "quantidade_obrigatoria":
            bool(linha.QuantidadeObrigatoria),

        "quantidade_operacional_minima":
            float(linha.QuantidadeOperacionalMinima),

        "quantidade_operacional_maxima":
            float(linha.QuantidadeOperacionalMaxima),

        "ativa":
            bool(linha.Ativa),

        "criado_por":
            linha.CriadoPor,

        "data_hora_criacao":
            linha.DataHoraCriacao,

        "alterado_por":
            linha.AlteradoPor,

        "data_hora_alteracao":
            linha.DataHoraAlteracao,

        "motivo_ultima_alteracao":
            linha.MotivoUltimaAlteracao,
    }


def obter_configuracao_aplicada(
    cursor,
    id_inventario: int,
):
    if id_inventario <= 0:
        raise BusinessRuleViolation(
            "Invent\u00e1rio inv\u00e1lido."
        )

    cursor.execute(
        """
        SELECT
            a.ID_ConfiguracaoAplicada,
            a.ID_Inventario,
            a.ID_ConfiguracaoOrigem,
            a.ID_ConfiguracaoOperacionalOrigem,
            a.Versao,

            i.ClienteId,
            i.Tipo,

            a.ValidarLocalizacaoEscopo,
            a.PermitirLocalizacaoVazia,
            a.PermitirReaberturaLocalizacao,
            a.PermitirAlteracaoEscopoAposSnapshot,

            a.CodigoLivre,
            a.PermitirCodigoNaoCadastrado,
            a.PermitirItemForaLocalizacao,

            a.LoteObrigatorioSeExistir,
            a.ValidarLoteCodigo,
            a.ValidarLoteLocalizacao,

            a.QuantidadeMinima,
            a.QuantidadeMaxima,

            a.ContagemCega,
            a.ConsideraLocalizacaoConciliacao,

            a.RecontagemPorLocalizacao,
            a.RodadasIniciais,
            a.MaxRodadas,

            a.PermitirGestorAntecipado,
            a.LimiteItensGestorAntecipado,
            a.DivergenciaBloqueiaFinalizacao,

            a.LocalizacaoObrigatoria,
            a.LocalizacaoValidarEstoque,

            a.CodigoObrigatorio,
            a.CodigoValidarEstoque,

            a.LoteObrigatorioQuandoExistir,
            a.LoteValidarCodigo,

            a.QuantidadeObrigatoria,
            a.QuantidadeOperacionalMinima,
            a.QuantidadeOperacionalMaxima,

            a.Ativa,
            a.CriadoPor,
            a.DataHoraCriacao,
            a.AlteradoPor,
            a.DataHoraAlteracao,
            a.MotivoUltimaAlteracao

        FROM dbo.ConfiguracoesInventarioAplicadas a

        INNER JOIN dbo.Inventarios i
            ON i.ID_Inventario =
                a.ID_Inventario

        WHERE
            a.ID_Inventario = ?
            AND a.Ativa = 1
        """,
        id_inventario,
    )

    linha = cursor.fetchone()

    if not linha:
        raise NotFoundError(
            "O invent\u00e1rio n\u00e3o possui "
            "configura\u00e7\u00e3o aplicada."
        )

    return _serializar_configuracao(
        linha
    )


def obter_rodadas_aplicadas(
    cursor,
    id_configuracao_aplicada: int,
):
    cursor.execute(
        """
        SELECT
            ID_ConfiguracaoRodadaAplicada,
            NumeroRodada,
            TipoRodada,
            Ativa

        FROM dbo.ConfiguracoesRodadasInventarioAplicadas

        WHERE
            ID_ConfiguracaoAplicada = ?
            AND Ativa = 1

        ORDER BY
            NumeroRodada
        """,
        id_configuracao_aplicada,
    )

    return [
        {
            "id_configuracao_rodada":
                int(
                    linha.ID_ConfiguracaoRodadaAplicada
                ),

            "id_configuracao_rodada_aplicada":
                int(
                    linha.ID_ConfiguracaoRodadaAplicada
                ),

            "numero_rodada":
                int(linha.NumeroRodada),

            "tipo_rodada":
                _tipo(linha.TipoRodada),

            "ativa":
                bool(linha.Ativa),
        }
        for linha in cursor.fetchall()
    ]


def obter_configuracao_completa_aplicada(
    cursor,
    id_inventario: int,
):
    configuracao = obter_configuracao_aplicada(
        cursor=cursor,
        id_inventario=id_inventario,
    )

    configuracao["rodadas"] = (
        obter_rodadas_aplicadas(
            cursor=cursor,
            id_configuracao_aplicada=(
                configuracao[
                    "id_configuracao_aplicada"
                ]
            ),
        )
    )

    return configuracao


def obter_tipo_rodada_aplicada(
    cursor,
    id_inventario: int,
    numero_rodada: int,
):
    configuracao = obter_configuracao_aplicada(
        cursor=cursor,
        id_inventario=id_inventario,
    )

    cursor.execute(
        """
        SELECT TOP 1
            TipoRodada

        FROM dbo.ConfiguracoesRodadasInventarioAplicadas

        WHERE
            ID_ConfiguracaoAplicada = ?
            AND NumeroRodada = ?
            AND Ativa = 1
        """,
        (
            configuracao[
                "id_configuracao_aplicada"
            ],
            numero_rodada,
        ),
    )

    linha = cursor.fetchone()

    if not linha:
        return "NAO_CONFIGURADA"

    return _tipo(
        linha.TipoRodada
    )


def obter_tipo_proxima_rodada_aplicada(
    cursor,
    id_inventario: int,
    numero_rodada_atual: int,
):
    configuracao = obter_configuracao_aplicada(
        cursor=cursor,
        id_inventario=id_inventario,
    )

    proxima = numero_rodada_atual + 1

    if proxima > configuracao["max_rodadas"]:
        return "FINALIZADO"

    return obter_tipo_rodada_aplicada(
        cursor=cursor,
        id_inventario=id_inventario,
        numero_rodada=proxima,
    )


def criar_configuracao_aplicada(
    cursor,
    id_inventario: int,
    usuario: str,
):
    usuario = _texto(usuario)

    if id_inventario <= 0:
        raise BusinessRuleViolation(
            "Invent\u00e1rio inv\u00e1lido."
        )

    if not usuario:
        raise BusinessRuleViolation(
            "Usu\u00e1rio respons\u00e1vel n\u00e3o informado."
        )

    cursor.execute(
        """
        SELECT TOP 1
            ID_ConfiguracaoAplicada

        FROM dbo.ConfiguracoesInventarioAplicadas

        WHERE ID_Inventario = ?
        """,
        id_inventario,
    )

    existente = cursor.fetchone()

    if existente:
        return obter_configuracao_completa_aplicada(
            cursor=cursor,
            id_inventario=id_inventario,
        )

    cursor.execute(
        """
        INSERT INTO dbo.ConfiguracoesInventarioAplicadas
        (
            ID_Inventario,

            ID_ConfiguracaoOrigem,
            ID_ConfiguracaoOperacionalOrigem,

            Versao,

            ValidarLocalizacaoEscopo,
            PermitirLocalizacaoVazia,
            PermitirReaberturaLocalizacao,
            PermitirAlteracaoEscopoAposSnapshot,

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

            LocalizacaoObrigatoria,
            LocalizacaoValidarEstoque,

            CodigoObrigatorio,
            CodigoValidarEstoque,

            LoteObrigatorioQuandoExistir,
            LoteValidarCodigo,

            QuantidadeObrigatoria,
            QuantidadeOperacionalMinima,
            QuantidadeOperacionalMaxima,

            Ativa,

            CriadoPor,
            DataHoraCriacao,

            AlteradoPor,
            DataHoraAlteracao,
            MotivoUltimaAlteracao
        )

        OUTPUT
            INSERTED.ID_ConfiguracaoAplicada

        SELECT
            i.ID_Inventario,

            cfg.ID_Configuracao,
            op.ID_ConfiguracaoOperacional,

            1,

            cfg.ValidarLocalizacaoEscopo,
            cfg.PermitirLocalizacaoVazia,
            cfg.PermitirReaberturaLocalizacao,
            cfg.PermitirAlteracaoEscopoAposSnapshot,

            cfg.CodigoLivre,
            cfg.PermitirCodigoNaoCadastrado,
            cfg.PermitirItemForaLocalizacao,

            cfg.LoteObrigatorioSeExistir,
            cfg.ValidarLoteCodigo,
            cfg.ValidarLoteLocalizacao,

            cfg.QuantidadeMinima,
            cfg.QuantidadeMaxima,

            cfg.ContagemCega,
            cfg.ConsideraLocalizacaoConciliacao,

            cfg.RecontagemPorLocalizacao,
            cfg.RodadasIniciais,
            cfg.MaxRodadas,

            cfg.PermitirGestorAntecipado,
            cfg.LimiteItensGestorAntecipado,
            cfg.DivergenciaBloqueiaFinalizacao,

            COALESCE(
                op.LocalizacaoObrigatoria,
                CONVERT(BIT, 1)
            ),

            COALESCE(
                op.LocalizacaoValidarEstoque,
                CONVERT(BIT, 1)
            ),

            COALESCE(
                op.CodigoObrigatorio,
                CONVERT(BIT, 1)
            ),

            COALESCE(
                op.CodigoValidarEstoque,
                CONVERT(BIT, 0)
            ),

            COALESCE(
                op.LoteObrigatorioQuandoExistir,
                CONVERT(BIT, 1)
            ),

            COALESCE(
                op.LoteValidarCodigo,
                CONVERT(BIT, 1)
            ),

            COALESCE(
                op.QuantidadeObrigatoria,
                CONVERT(BIT, 1)
            ),

            COALESCE(
                op.QuantidadeMinima,
                CONVERT(DECIMAL(18, 3), 0)
            ),

            COALESCE(
                op.QuantidadeMaxima,
                CONVERT(DECIMAL(18, 3), 999)
            ),

            1,

            ?,
            SYSDATETIME(),

            NULL,
            NULL,
            (
                'Configura\u00e7\u00e3o copiada automaticamente '
                + 'na cria\u00e7\u00e3o do invent\u00e1rio.'
            )

        FROM dbo.Inventarios i

        CROSS APPLY
        (
            SELECT TOP 1
                c.*

            FROM dbo.ConfiguracoesInventario c

            WHERE
                c.ClienteId = i.ClienteId
                AND UPPER(
                    LTRIM(
                        RTRIM(c.TipoInventario)
                    )
                ) = UPPER(
                    LTRIM(
                        RTRIM(i.Tipo)
                    )
                )
                AND c.Ativa = 1

            ORDER BY
                c.ID_Configuracao DESC
        ) cfg

        OUTER APPLY
        (
            SELECT TOP 1
                o.*

            FROM dbo.ConfiguracoesOperacionaisInventario o

            WHERE
                o.ClienteId = i.ClienteId
                AND UPPER(
                    LTRIM(
                        RTRIM(o.TipoInventario)
                    )
                ) = UPPER(
                    LTRIM(
                        RTRIM(i.Tipo)
                    )
                )
                AND o.Ativo = 1

            ORDER BY
                o.ID_ConfiguracaoOperacional DESC
        ) op

        WHERE i.ID_Inventario = ?
        """,
        (
            usuario,
            id_inventario,
        ),
    )

    criada = cursor.fetchone()

    if not criada:
        raise BusinessRuleViolation(
            "N\u00e3o foi poss\u00edvel copiar a "
            "configura\u00e7\u00e3o para o invent\u00e1rio."
        )

    id_configuracao_aplicada = int(
        criada.ID_ConfiguracaoAplicada
    )

    cursor.execute(
        """
        INSERT INTO dbo.ConfiguracoesRodadasInventarioAplicadas
        (
            ID_ConfiguracaoAplicada,
            NumeroRodada,
            TipoRodada,
            Ativa,
            DataHoraCriacao
        )
        SELECT
            ?,
            rodada.NumeroRodada,
            rodada.TipoRodada,
            rodada.Ativa,
            SYSDATETIME()

        FROM dbo.ConfiguracoesRodadasInventario rodada

        INNER JOIN dbo.ConfiguracoesInventarioAplicadas aplicada
            ON aplicada.ID_ConfiguracaoOrigem =
                rodada.ID_Configuracao

        WHERE
            aplicada.ID_ConfiguracaoAplicada = ?
            AND rodada.Ativa = 1
        """,
        (
            id_configuracao_aplicada,
            id_configuracao_aplicada,
        ),
    )

    configuracao = (
        obter_configuracao_completa_aplicada(
            cursor=cursor,
            id_inventario=id_inventario,
        )
    )

    if not any(
        rodada["numero_rodada"] == 1
        for rodada in configuracao["rodadas"]
    ):
        raise BusinessRuleViolation(
            "A Rodada 1 n\u00e3o est\u00e1 configurada "
            "para este invent\u00e1rio."
        )

    dados_novos = json.dumps(
        configuracao,
        ensure_ascii=False,
        default=str,
    )

    cursor.execute(
        """
        INSERT INTO dbo.HistoricoConfiguracoesInventarioAplicadas
        (
            ID_ConfiguracaoAplicada,
            ID_Inventario,

            VersaoAnterior,
            VersaoNova,

            TipoAlteracao,
            Motivo,

            DadosAnteriores,
            DadosNovos,

            AlteradoPor,
            DataHoraAlteracao
        )
        VALUES
        (
            ?,
            ?,

            NULL,
            1,

            'CRIACAO_INVENTARIO',
            ?,

            NULL,
            ?,

            ?,
            SYSDATETIME()
        )
        """,
        (
            id_configuracao_aplicada,
            id_inventario,
            (
                "Configura\u00e7\u00e3o copiada automaticamente "
                "na cria\u00e7\u00e3o do invent\u00e1rio."
            ),
            dados_novos,
            usuario,
        ),
    )

    return configuracao


def _dados_modelo(dados):
    if hasattr(dados, "model_dump"):
        return dados.model_dump()

    if hasattr(dados, "dict"):
        return dados.dict()

    return dict(dados)


def atualizar_configuracao_aplicada(
    cursor,
    id_inventario: int,
    dados,
    usuario: str,
):
    if id_inventario <= 0:
        raise BusinessRuleViolation(
            "Invent\u00e1rio inv\u00e1lido."
        )

    usuario = _texto(usuario)

    if not usuario:
        raise BusinessRuleViolation(
            "Usu\u00e1rio respons\u00e1vel n\u00e3o informado."
        )

    entrada = _dados_modelo(
        dados
    )

    motivo = _texto(
        entrada.get("motivo")
    )

    if len(motivo) < 5:
        raise BusinessRuleViolation(
            "Informe um motivo com pelo menos 5 caracteres."
        )

    versao_esperada = int(
        entrada.get("versao_esperada") or 0
    )

    quantidade_minima = float(
        entrada["quantidade_minima"]
    )

    quantidade_maxima = float(
        entrada["quantidade_maxima"]
    )

    quantidade_operacional_minima = float(
        entrada["quantidade_operacional_minima"]
    )

    quantidade_operacional_maxima = float(
        entrada["quantidade_operacional_maxima"]
    )

    if quantidade_minima > quantidade_maxima:
        raise BusinessRuleViolation(
            "Quantidade m\u00ednima n\u00e3o pode ser "
            "maior que a quantidade m\u00e1xima."
        )

    if (
        quantidade_operacional_minima
        > quantidade_operacional_maxima
    ):
        raise BusinessRuleViolation(
            "Quantidade operacional m\u00ednima n\u00e3o pode "
            "ser maior que a quantidade operacional m\u00e1xima."
        )

    rodadas_iniciais = int(
        entrada["rodadas_iniciais"]
    )

    max_rodadas = int(
        entrada["max_rodadas"]
    )

    if rodadas_iniciais > max_rodadas:
        raise BusinessRuleViolation(
            "Rodadas iniciais n\u00e3o podem superar "
            "o m\u00e1ximo de rodadas."
        )

    rodadas = entrada.get("rodadas") or []

    rodadas_normalizadas = []

    for rodada in rodadas:
        if hasattr(rodada, "model_dump"):
            rodada = rodada.model_dump()
        elif hasattr(rodada, "dict"):
            rodada = rodada.dict()

        numero = int(
            rodada["numero_rodada"]
        )

        tipo_rodada = _tipo(
            rodada["tipo_rodada"]
        )

        if tipo_rodada not in (
            "COMPLETA",
            "DIVERGENCIAS",
            "GESTOR",
        ):
            raise BusinessRuleViolation(
                f"Tipo inv\u00e1lido na Rodada {numero}."
            )

        rodadas_normalizadas.append(
            {
                "numero_rodada": numero,
                "tipo_rodada": tipo_rodada,
            }
        )

    numeros = [
        rodada["numero_rodada"]
        for rodada in rodadas_normalizadas
    ]

    if len(numeros) != len(set(numeros)):
        raise BusinessRuleViolation(
            "Existem rodadas duplicadas."
        )

    numeros_esperados = list(
        range(1, max_rodadas + 1)
    )

    if sorted(numeros) != numeros_esperados:
        raise BusinessRuleViolation(
            "As rodadas devem formar uma sequ\u00eancia "
            f"de 1 at\u00e9 {max_rodadas}."
        )

    cursor.execute(
        """
        SELECT
            a.ID_ConfiguracaoAplicada,
            a.Versao,
            i.RodadaAtual,
            i.Status

        FROM dbo.ConfiguracoesInventarioAplicadas a
            WITH (UPDLOCK, ROWLOCK)

        INNER JOIN dbo.Inventarios i
            ON i.ID_Inventario =
                a.ID_Inventario

        WHERE
            a.ID_Inventario = ?
            AND a.Ativa = 1
        """,
        id_inventario,
    )

    atual = cursor.fetchone()

    if not atual:
        raise NotFoundError(
            "Configura\u00e7\u00e3o aplicada n\u00e3o encontrada."
        )

    versao_atual = int(
        atual.Versao
    )

    if versao_atual != versao_esperada:
        raise ConflictError(
            "A configura\u00e7\u00e3o foi alterada por outro "
            "usu\u00e1rio. Atualize a tela antes de salvar."
        )

    rodada_atual = int(
        atual.RodadaAtual or 1
    )

    if max_rodadas < rodada_atual:
        raise BusinessRuleViolation(
            "O m\u00e1ximo de rodadas n\u00e3o pode ser menor "
            f"que a rodada atual ({rodada_atual})."
        )

    id_configuracao = int(
        atual.ID_ConfiguracaoAplicada
    )

    antes = obter_configuracao_completa_aplicada(
        cursor=cursor,
        id_inventario=id_inventario,
    )

    tipos_existentes = {
        int(rodada["numero_rodada"]):
            _tipo(rodada["tipo_rodada"])
        for rodada in antes["rodadas"]
    }

    tipos_novos = {
        rodada["numero_rodada"]:
            rodada["tipo_rodada"]
        for rodada in rodadas_normalizadas
    }

    for numero in range(1, rodada_atual + 1):
        tipo_existente = tipos_existentes.get(
            numero
        )

        tipo_novo = tipos_novos.get(
            numero
        )

        if tipo_existente is None:
            raise BusinessRuleViolation(
                f"A Rodada {numero} executada n\u00e3o possui "
                "configura\u00e7\u00e3o registrada."
            )

        if tipo_novo != tipo_existente:
            raise BusinessRuleViolation(
                f"O tipo da Rodada {numero} n\u00e3o pode ser "
                "alterado porque ela j\u00e1 foi alcan\u00e7ada."
            )

    cursor.execute(
        """
        UPDATE dbo.ConfiguracoesInventarioAplicadas

        SET
            ValidarLocalizacaoEscopo = ?,
            PermitirLocalizacaoVazia = ?,
            PermitirReaberturaLocalizacao = ?,
            PermitirAlteracaoEscopoAposSnapshot = ?,

            CodigoLivre = ?,
            PermitirCodigoNaoCadastrado = ?,
            PermitirItemForaLocalizacao = ?,

            LoteObrigatorioSeExistir = ?,
            ValidarLoteCodigo = ?,
            ValidarLoteLocalizacao = ?,

            QuantidadeMinima = ?,
            QuantidadeMaxima = ?,

            ContagemCega = ?,
            ConsideraLocalizacaoConciliacao = ?,

            RecontagemPorLocalizacao = ?,
            RodadasIniciais = ?,
            MaxRodadas = ?,

            PermitirGestorAntecipado = ?,
            LimiteItensGestorAntecipado = ?,
            DivergenciaBloqueiaFinalizacao = ?,

            LocalizacaoObrigatoria = ?,
            LocalizacaoValidarEstoque = ?,

            CodigoObrigatorio = ?,
            CodigoValidarEstoque = ?,

            LoteObrigatorioQuandoExistir = ?,
            LoteValidarCodigo = ?,

            QuantidadeObrigatoria = ?,
            QuantidadeOperacionalMinima = ?,
            QuantidadeOperacionalMaxima = ?,

            Versao = Versao + 1,
            AlteradoPor = ?,
            DataHoraAlteracao = SYSDATETIME(),
            MotivoUltimaAlteracao = ?

        WHERE
            ID_ConfiguracaoAplicada = ?
            AND Versao = ?
        """,
        (
            entrada["validar_localizacao_escopo"],
            entrada["permitir_localizacao_vazia"],
            entrada["permitir_reabertura_localizacao"],
            entrada[
                "permitir_alteracao_escopo_apos_snapshot"
            ],

            entrada["codigo_livre"],
            entrada["permitir_codigo_nao_cadastrado"],
            entrada["permitir_item_fora_localizacao"],

            entrada["lote_obrigatorio_se_existir"],
            entrada["validar_lote_codigo"],
            entrada["validar_lote_localizacao"],

            quantidade_minima,
            quantidade_maxima,

            entrada["contagem_cega"],
            entrada[
                "considera_localizacao_conciliacao"
            ],

            entrada["recontagem_por_localizacao"],
            rodadas_iniciais,
            max_rodadas,

            entrada["permitir_gestor_antecipado"],
            entrada["limite_itens_gestor_antecipado"],
            entrada[
                "divergencia_bloqueia_finalizacao"
            ],

            entrada["localizacao_obrigatoria"],
            entrada["localizacao_validar_estoque"],

            entrada["codigo_obrigatorio"],
            entrada["codigo_validar_estoque"],

            entrada[
                "lote_obrigatorio_quando_existir"
            ],
            entrada["lote_validar_codigo"],

            entrada["quantidade_obrigatoria"],
            quantidade_operacional_minima,
            quantidade_operacional_maxima,

            usuario,
            motivo,

            id_configuracao,
            versao_esperada,
        ),
    )

    if cursor.rowcount != 1:
        raise ConflictError(
            "A configura\u00e7\u00e3o mudou durante o salvamento. "
            "Atualize a tela e tente novamente."
        )

    cursor.execute(
        """
        UPDATE dbo.ConfiguracoesRodadasInventarioAplicadas

        SET Ativa = 0

        WHERE
            ID_ConfiguracaoAplicada = ?
            AND NumeroRodada > ?
        """,
        (
            id_configuracao,
            rodada_atual,
        ),
    )

    for rodada in rodadas_normalizadas:
        numero = rodada["numero_rodada"]

        if numero <= rodada_atual:
            continue

        cursor.execute(
            """
            UPDATE dbo.ConfiguracoesRodadasInventarioAplicadas

            SET
                TipoRodada = ?,
                Ativa = 1

            WHERE
                ID_ConfiguracaoAplicada = ?
                AND NumeroRodada = ?
            """,
            (
                rodada["tipo_rodada"],
                id_configuracao,
                numero,
            ),
        )

        if cursor.rowcount == 0:
            cursor.execute(
                """
                INSERT INTO
                    dbo.ConfiguracoesRodadasInventarioAplicadas
                (
                    ID_ConfiguracaoAplicada,
                    NumeroRodada,
                    TipoRodada,
                    Ativa,
                    DataHoraCriacao
                )
                VALUES
                (
                    ?,
                    ?,
                    ?,
                    1,
                    SYSDATETIME()
                )
                """,
                (
                    id_configuracao,
                    numero,
                    rodada["tipo_rodada"],
                ),
            )

    depois = obter_configuracao_completa_aplicada(
        cursor=cursor,
        id_inventario=id_inventario,
    )

    dados_anteriores = json.dumps(
        antes,
        ensure_ascii=False,
        default=str,
    )

    dados_novos = json.dumps(
        depois,
        ensure_ascii=False,
        default=str,
    )

    cursor.execute(
        """
        INSERT INTO dbo.HistoricoConfiguracoesInventarioAplicadas
        (
            ID_ConfiguracaoAplicada,
            ID_Inventario,

            VersaoAnterior,
            VersaoNova,

            TipoAlteracao,
            Motivo,

            DadosAnteriores,
            DadosNovos,

            AlteradoPor,
            DataHoraAlteracao
        )
        VALUES
        (
            ?,
            ?,

            ?,
            ?,

            'ATUALIZACAO',
            ?,

            ?,
            ?,

            ?,
            SYSDATETIME()
        )
        """,
        (
            id_configuracao,
            id_inventario,

            versao_atual,
            depois["versao"],

            motivo,

            dados_anteriores,
            dados_novos,

            usuario,
        ),
    )

    return {
        "sucesso": True,
        "mensagem": (
            "Configura\u00e7\u00e3o do invent\u00e1rio "
            "atualizada com sucesso."
        ),
        "configuracao": depois,
    }


def listar_historico_configuracao_aplicada(
    cursor,
    id_inventario: int,
):
    if id_inventario <= 0:
        raise BusinessRuleViolation(
            "Invent\u00e1rio inv\u00e1lido."
        )

    cursor.execute(
        """
        SELECT
            ID_HistoricoConfiguracao,
            ID_ConfiguracaoAplicada,
            ID_Inventario,

            VersaoAnterior,
            VersaoNova,

            TipoAlteracao,
            Motivo,

            DadosAnteriores,
            DadosNovos,

            AlteradoPor,
            DataHoraAlteracao

        FROM dbo.HistoricoConfiguracoesInventarioAplicadas

        WHERE ID_Inventario = ?

        ORDER BY
            DataHoraAlteracao DESC,
            ID_HistoricoConfiguracao DESC
        """,
        id_inventario,
    )

    historico = []

    for linha in cursor.fetchall():
        historico.append(
            {
                "id_historico_configuracao":
                    int(
                        linha.ID_HistoricoConfiguracao
                    ),

                "id_configuracao_aplicada":
                    int(
                        linha.ID_ConfiguracaoAplicada
                    ),

                "id_inventario":
                    int(linha.ID_Inventario),

                "versao_anterior":
                    linha.VersaoAnterior,

                "versao_nova":
                    int(linha.VersaoNova),

                "tipo_alteracao":
                    linha.TipoAlteracao,

                "motivo":
                    linha.Motivo,

                "dados_anteriores":
                    (
                        json.loads(
                            linha.DadosAnteriores
                        )
                        if linha.DadosAnteriores
                        else None
                    ),

                "dados_novos":
                    json.loads(
                        linha.DadosNovos
                    ),

                "alterado_por":
                    linha.AlteradoPor,

                "data_hora_alteracao":
                    linha.DataHoraAlteracao,
            }
        )

    return {
        "id_inventario":
            id_inventario,

        "total":
            len(historico),

        "historico":
            historico,
    }
