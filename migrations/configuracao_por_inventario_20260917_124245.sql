SET NOCOUNT ON;
SET XACT_ABORT ON;

BEGIN TRY
    BEGIN TRANSACTION;

    /* ========================================================
       1. CONFIGURAÇÃO APLICADA AO INVENTÁRIO
       ======================================================== */

    IF OBJECT_ID(
        'dbo.ConfiguracoesInventarioAplicadas',
        'U'
    ) IS NULL
    BEGIN
        CREATE TABLE dbo.ConfiguracoesInventarioAplicadas
        (
            ID_ConfiguracaoAplicada INT
                IDENTITY(1, 1)
                NOT NULL,

            ID_Inventario INT NOT NULL,

            ID_ConfiguracaoOrigem INT NULL,
            ID_ConfiguracaoOperacionalOrigem INT NULL,

            Versao INT NOT NULL
                CONSTRAINT DF_ConfigInvAplicada_Versao
                DEFAULT (1),

            ValidarLocalizacaoEscopo BIT NOT NULL,
            PermitirLocalizacaoVazia BIT NOT NULL,
            PermitirReaberturaLocalizacao BIT NOT NULL,
            PermitirAlteracaoEscopoAposSnapshot BIT NOT NULL,

            CodigoLivre BIT NOT NULL,
            PermitirCodigoNaoCadastrado BIT NOT NULL,
            PermitirItemForaLocalizacao BIT NOT NULL,

            LoteObrigatorioSeExistir BIT NOT NULL,
            ValidarLoteCodigo BIT NOT NULL,
            ValidarLoteLocalizacao BIT NOT NULL,

            QuantidadeMinima DECIMAL(18, 4) NOT NULL,
            QuantidadeMaxima DECIMAL(18, 4) NOT NULL,

            ContagemCega BIT NOT NULL,
            ConsideraLocalizacaoConciliacao BIT NOT NULL,

            RecontagemPorLocalizacao BIT NOT NULL,
            RodadasIniciais INT NOT NULL,
            MaxRodadas INT NOT NULL,

            PermitirGestorAntecipado BIT NOT NULL,
            LimiteItensGestorAntecipado INT NOT NULL,
            DivergenciaBloqueiaFinalizacao BIT NOT NULL,

            /* Regras utilizadas pela interface operacional */

            LocalizacaoObrigatoria BIT NOT NULL,
            LocalizacaoValidarEstoque BIT NOT NULL,

            CodigoObrigatorio BIT NOT NULL,
            CodigoValidarEstoque BIT NOT NULL,

            LoteObrigatorioQuandoExistir BIT NOT NULL,
            LoteValidarCodigo BIT NOT NULL,

            QuantidadeObrigatoria BIT NOT NULL,
            QuantidadeOperacionalMinima DECIMAL(18, 3) NOT NULL,
            QuantidadeOperacionalMaxima DECIMAL(18, 3) NOT NULL,

            Ativa BIT NOT NULL
                CONSTRAINT DF_ConfigInvAplicada_Ativa
                DEFAULT (1),

            CriadoPor VARCHAR(100) NOT NULL,
            DataHoraCriacao DATETIME2(3) NOT NULL
                CONSTRAINT DF_ConfigInvAplicada_Criacao
                DEFAULT (SYSDATETIME()),

            AlteradoPor VARCHAR(100) NULL,
            DataHoraAlteracao DATETIME2(3) NULL,
            MotivoUltimaAlteracao VARCHAR(500) NULL,

            CONSTRAINT PK_ConfiguracoesInventarioAplicadas
                PRIMARY KEY (ID_ConfiguracaoAplicada),

            CONSTRAINT UQ_ConfigInvAplicada_Inventario
                UNIQUE (ID_Inventario),

            CONSTRAINT FK_ConfigInvAplicada_Inventario
                FOREIGN KEY (ID_Inventario)
                REFERENCES dbo.Inventarios (ID_Inventario),

            CONSTRAINT FK_ConfigInvAplicada_Origem
                FOREIGN KEY (ID_ConfiguracaoOrigem)
                REFERENCES dbo.ConfiguracoesInventario (
                    ID_Configuracao
                ),

            CONSTRAINT FK_ConfigInvAplicada_OperacionalOrigem
                FOREIGN KEY (ID_ConfiguracaoOperacionalOrigem)
                REFERENCES dbo.ConfiguracoesOperacionaisInventario (
                    ID_ConfiguracaoOperacional
                ),

            CONSTRAINT CK_ConfigInvAplicada_Versao
                CHECK (Versao >= 1),

            CONSTRAINT CK_ConfigInvAplicada_Quantidade
                CHECK (
                    QuantidadeMinima >= 0
                    AND QuantidadeMaxima >= QuantidadeMinima
                ),

            CONSTRAINT CK_ConfigInvAplicada_QuantidadeOperacional
                CHECK (
                    QuantidadeOperacionalMinima >= 0
                    AND QuantidadeOperacionalMaxima >=
                        QuantidadeOperacionalMinima
                ),

            CONSTRAINT CK_ConfigInvAplicada_Rodadas
                CHECK (
                    RodadasIniciais >= 1
                    AND MaxRodadas >= RodadasIniciais
                )
        );
    END;


    /* ========================================================
       2. RODADAS DA CONFIGURAÇÃO APLICADA
       ======================================================== */

    IF OBJECT_ID(
        'dbo.ConfiguracoesRodadasInventarioAplicadas',
        'U'
    ) IS NULL
    BEGIN
        CREATE TABLE dbo.ConfiguracoesRodadasInventarioAplicadas
        (
            ID_ConfiguracaoRodadaAplicada INT
                IDENTITY(1, 1)
                NOT NULL,

            ID_ConfiguracaoAplicada INT NOT NULL,
            NumeroRodada INT NOT NULL,
            TipoRodada VARCHAR(30) NOT NULL,

            Ativa BIT NOT NULL
                CONSTRAINT DF_ConfigRodadaAplicada_Ativa
                DEFAULT (1),

            DataHoraCriacao DATETIME2(3) NOT NULL
                CONSTRAINT DF_ConfigRodadaAplicada_Criacao
                DEFAULT (SYSDATETIME()),

            CONSTRAINT PK_ConfiguracoesRodadasInventarioAplicadas
                PRIMARY KEY (
                    ID_ConfiguracaoRodadaAplicada
                ),

            CONSTRAINT UQ_ConfigRodadaAplicada
                UNIQUE (
                    ID_ConfiguracaoAplicada,
                    NumeroRodada
                ),

            CONSTRAINT FK_ConfigRodadaAplicada_Config
                FOREIGN KEY (ID_ConfiguracaoAplicada)
                REFERENCES dbo.ConfiguracoesInventarioAplicadas (
                    ID_ConfiguracaoAplicada
                ),

            CONSTRAINT CK_ConfigRodadaAplicada_Numero
                CHECK (NumeroRodada >= 1)
        );
    END;


    /* ========================================================
       3. HISTÓRICO DAS ALTERAÇÕES
       ======================================================== */

    IF OBJECT_ID(
        'dbo.HistoricoConfiguracoesInventarioAplicadas',
        'U'
    ) IS NULL
    BEGIN
        CREATE TABLE dbo.HistoricoConfiguracoesInventarioAplicadas
        (
            ID_HistoricoConfiguracao INT
                IDENTITY(1, 1)
                NOT NULL,

            ID_ConfiguracaoAplicada INT NOT NULL,
            ID_Inventario INT NOT NULL,

            VersaoAnterior INT NULL,
            VersaoNova INT NOT NULL,

            TipoAlteracao VARCHAR(40) NOT NULL,
            Motivo VARCHAR(500) NOT NULL,

            DadosAnteriores NVARCHAR(MAX) NULL,
            DadosNovos NVARCHAR(MAX) NOT NULL,

            AlteradoPor VARCHAR(100) NOT NULL,

            DataHoraAlteracao DATETIME2(3) NOT NULL
                CONSTRAINT DF_HistConfigInv_DataHora
                DEFAULT (SYSDATETIME()),

            CONSTRAINT PK_HistoricoConfiguracoesInventarioAplicadas
                PRIMARY KEY (
                    ID_HistoricoConfiguracao
                ),

            CONSTRAINT FK_HistConfigInv_Config
                FOREIGN KEY (ID_ConfiguracaoAplicada)
                REFERENCES dbo.ConfiguracoesInventarioAplicadas (
                    ID_ConfiguracaoAplicada
                ),

            CONSTRAINT FK_HistConfigInv_Inventario
                FOREIGN KEY (ID_Inventario)
                REFERENCES dbo.Inventarios (
                    ID_Inventario
                ),

            CONSTRAINT CK_HistConfigInv_Versao
                CHECK (VersaoNova >= 1),

            CONSTRAINT CK_HistConfigInv_DadosAnterioresJson
                CHECK (
                    DadosAnteriores IS NULL
                    OR ISJSON(DadosAnteriores) = 1
                ),

            CONSTRAINT CK_HistConfigInv_DadosNovosJson
                CHECK (ISJSON(DadosNovos) = 1)
        );

        CREATE INDEX IX_HistConfigInv_InventarioData
            ON dbo.HistoricoConfiguracoesInventarioAplicadas
            (
                ID_Inventario,
                DataHoraAlteracao DESC
            );
    END;


    /* ========================================================
       4. COPIAR AS REGRAS PARA INVENTÁRIOS EXISTENTES
       ======================================================== */

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

        'MIGRACAO_SGI',
        SYSDATETIME(),

        NULL,
        NULL,
        (
            'Configuração vigente copiada durante a '
            + 'implantação da configuração por inventário.'
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

    WHERE NOT EXISTS
    (
        SELECT 1
        FROM dbo.ConfiguracoesInventarioAplicadas existente
        WHERE
            existente.ID_Inventario =
                i.ID_Inventario
    );


    /* ========================================================
       5. COPIAR CONFIGURAÇÃO DAS RODADAS
       ======================================================== */

    INSERT INTO dbo.ConfiguracoesRodadasInventarioAplicadas
    (
        ID_ConfiguracaoAplicada,
        NumeroRodada,
        TipoRodada,
        Ativa,
        DataHoraCriacao
    )
    SELECT
        aplicada.ID_ConfiguracaoAplicada,
        rodada.NumeroRodada,
        rodada.TipoRodada,
        rodada.Ativa,
        SYSDATETIME()

    FROM dbo.ConfiguracoesInventarioAplicadas aplicada

    INNER JOIN dbo.ConfiguracoesRodadasInventario rodada
        ON rodada.ID_Configuracao =
            aplicada.ID_ConfiguracaoOrigem

    WHERE
        rodada.Ativa = 1

        AND NOT EXISTS
        (
            SELECT 1
            FROM dbo.ConfiguracoesRodadasInventarioAplicadas existente
            WHERE
                existente.ID_ConfiguracaoAplicada =
                    aplicada.ID_ConfiguracaoAplicada

                AND existente.NumeroRodada =
                    rodada.NumeroRodada
        );


    /* ========================================================
       6. REGISTRAR A CRIAÇÃO INICIAL NO HISTÓRICO
       ======================================================== */

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
    SELECT
        aplicada.ID_ConfiguracaoAplicada,
        aplicada.ID_Inventario,

        NULL,
        aplicada.Versao,

        'CRIACAO_MIGRACAO',
        (
            'Configuração vigente copiada durante a '
            + 'implantação do versionamento por inventário.'
        ),

        NULL,

        (
            SELECT
                aplicada.ID_ConfiguracaoAplicada
                    AS id_configuracao_aplicada,

                aplicada.ID_Inventario
                    AS id_inventario,

                aplicada.ID_ConfiguracaoOrigem
                    AS id_configuracao_origem,

                aplicada.ID_ConfiguracaoOperacionalOrigem
                    AS id_configuracao_operacional_origem,

                aplicada.Versao
                    AS versao,

                aplicada.ValidarLocalizacaoEscopo
                    AS validar_localizacao_escopo,

                aplicada.PermitirLocalizacaoVazia
                    AS permitir_localizacao_vazia,

                aplicada.PermitirReaberturaLocalizacao
                    AS permitir_reabertura_localizacao,

                aplicada.PermitirAlteracaoEscopoAposSnapshot
                    AS permitir_alteracao_escopo_apos_snapshot,

                aplicada.CodigoLivre
                    AS codigo_livre,

                aplicada.PermitirCodigoNaoCadastrado
                    AS permitir_codigo_nao_cadastrado,

                aplicada.PermitirItemForaLocalizacao
                    AS permitir_item_fora_localizacao,

                aplicada.LoteObrigatorioSeExistir
                    AS lote_obrigatorio_se_existir,

                aplicada.ValidarLoteCodigo
                    AS validar_lote_codigo,

                aplicada.ValidarLoteLocalizacao
                    AS validar_lote_localizacao,

                aplicada.QuantidadeMinima
                    AS quantidade_minima,

                aplicada.QuantidadeMaxima
                    AS quantidade_maxima,

                aplicada.ContagemCega
                    AS contagem_cega,

                aplicada.ConsideraLocalizacaoConciliacao
                    AS considera_localizacao_conciliacao,

                aplicada.RecontagemPorLocalizacao
                    AS recontagem_por_localizacao,

                aplicada.RodadasIniciais
                    AS rodadas_iniciais,

                aplicada.MaxRodadas
                    AS max_rodadas,

                aplicada.PermitirGestorAntecipado
                    AS permitir_gestor_antecipado,

                aplicada.LimiteItensGestorAntecipado
                    AS limite_itens_gestor_antecipado,

                aplicada.DivergenciaBloqueiaFinalizacao
                    AS divergencia_bloqueia_finalizacao,

                aplicada.LocalizacaoObrigatoria
                    AS localizacao_obrigatoria,

                aplicada.LocalizacaoValidarEstoque
                    AS localizacao_validar_estoque,

                aplicada.CodigoObrigatorio
                    AS codigo_obrigatorio,

                aplicada.CodigoValidarEstoque
                    AS codigo_validar_estoque,

                aplicada.LoteObrigatorioQuandoExistir
                    AS lote_obrigatorio_quando_existir,

                aplicada.LoteValidarCodigo
                    AS lote_validar_codigo,

                aplicada.QuantidadeObrigatoria
                    AS quantidade_obrigatoria,

                aplicada.QuantidadeOperacionalMinima
                    AS quantidade_operacional_minima,

                aplicada.QuantidadeOperacionalMaxima
                    AS quantidade_operacional_maxima

            FOR JSON PATH, WITHOUT_ARRAY_WRAPPER
        ),

        'MIGRACAO_SGI',
        SYSDATETIME()

    FROM dbo.ConfiguracoesInventarioAplicadas aplicada

    WHERE NOT EXISTS
    (
        SELECT 1
        FROM dbo.HistoricoConfiguracoesInventarioAplicadas historico
        WHERE
            historico.ID_ConfiguracaoAplicada =
                aplicada.ID_ConfiguracaoAplicada
    );


    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0
        ROLLBACK TRANSACTION;

    THROW;
END CATCH;


/* ============================================================
   7. VERIFICAÇÕES PÓS-MIGRAÇÃO
   ============================================================ */

SELECT
    (
        SELECT COUNT_BIG(*)
        FROM dbo.Inventarios
    ) AS TotalInventarios,

    (
        SELECT COUNT_BIG(*)
        FROM dbo.ConfiguracoesInventarioAplicadas
    ) AS TotalConfiguracoesAplicadas,

    (
        SELECT COUNT_BIG(*)
        FROM dbo.ConfiguracoesRodadasInventarioAplicadas
    ) AS TotalRodadasAplicadas,

    (
        SELECT COUNT_BIG(*)
        FROM dbo.HistoricoConfiguracoesInventarioAplicadas
    ) AS TotalRegistrosHistorico;


SELECT
    i.ID_Inventario,
    i.CodigoInventario,
    i.Tipo,
    i.Status

FROM dbo.Inventarios i

WHERE NOT EXISTS
(
    SELECT 1
    FROM dbo.ConfiguracoesInventarioAplicadas aplicada
    WHERE
        aplicada.ID_Inventario =
            i.ID_Inventario
)

ORDER BY
    i.ID_Inventario;


SELECT
    aplicada.ID_Inventario,
    COUNT_BIG(*) AS Quantidade

FROM dbo.ConfiguracoesInventarioAplicadas aplicada

GROUP BY
    aplicada.ID_Inventario

HAVING COUNT_BIG(*) > 1;
