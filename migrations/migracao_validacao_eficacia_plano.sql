SET NOCOUNT ON;
SET XACT_ABORT ON;

-- ============================================================
-- VALIDAÇÃO DE EFICÁCIA DOS PLANOS DE AÇÃO
--
-- Permite registrar histórico de verificações de eficácia
-- após a conclusão de um plano de ação.
-- ============================================================

IF OBJECT_ID('dbo.ValidacoesEficaciaPlano', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.ValidacoesEficaciaPlano
    (
        ID_ValidacaoEficacia bigint IDENTITY(1,1) NOT NULL,
        ID_PlanoAcao bigint NOT NULL,

        Resultado varchar(20) NOT NULL,
        CriterioValidacao varchar(2000) NOT NULL,
        Observacao varchar(2000) NULL,

        ValidadoPor varchar(100) NOT NULL,
        DataHoraValidacao datetime2 NOT NULL
            CONSTRAINT DF_ValidacoesEficaciaPlano_DataHoraValidacao
            DEFAULT (SYSDATETIME()),

        DataHoraCriacao datetime2 NOT NULL
            CONSTRAINT DF_ValidacoesEficaciaPlano_DataHoraCriacao
            DEFAULT (SYSDATETIME()),

        CONSTRAINT PK_ValidacoesEficaciaPlano
            PRIMARY KEY (ID_ValidacaoEficacia),

        CONSTRAINT FK_ValidacoesEficaciaPlano_PlanoAcao
            FOREIGN KEY (ID_PlanoAcao)
            REFERENCES dbo.PlanosAcaoOcorrencia (ID_PlanoAcao),

        CONSTRAINT CK_ValidacoesEficaciaPlano_Resultado
            CHECK (Resultado IN ('EFICAZ', 'INEFICAZ')),

        CONSTRAINT CK_ValidacoesEficaciaPlano_Criterio
            CHECK (LEN(LTRIM(RTRIM(CriterioValidacao))) > 0),

        CONSTRAINT CK_ValidacoesEficaciaPlano_ValidadoPor
            CHECK (LEN(LTRIM(RTRIM(ValidadoPor))) > 0)
    );
END;

IF NOT EXISTS
(
    SELECT 1
    FROM sys.indexes
    WHERE object_id = OBJECT_ID('dbo.ValidacoesEficaciaPlano')
      AND name = 'IX_ValidacoesEficaciaPlano_PlanoAcao'
)
BEGIN
    CREATE INDEX IX_ValidacoesEficaciaPlano_PlanoAcao
        ON dbo.ValidacoesEficaciaPlano
        (
            ID_PlanoAcao,
            DataHoraValidacao
        );
END;
