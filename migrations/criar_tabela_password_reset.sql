/* ============================================================
   FLUXO "ESQUECI MINHA SENHA" - SGI
   SQL Server

   Armazena apenas o HASH do token de recuperacao.
   O token em claro so trafega no e-mail e nunca e persistido.
   ============================================================ */

IF NOT EXISTS
(
    SELECT 1
    FROM sys.tables
    WHERE name = 'PasswordResetTokens'
)
BEGIN
    CREATE TABLE dbo.PasswordResetTokens
    (
        ID_PasswordResetToken   INT IDENTITY(1,1) NOT NULL
            CONSTRAINT PK_PasswordResetTokens
            PRIMARY KEY,

        ID_Usuario              INT NOT NULL,

        TokenHash               VARCHAR(128) NOT NULL,

        DataHoraCriacao         DATETIME2(0) NOT NULL
            CONSTRAINT DF_PRT_Criacao
            DEFAULT (SYSDATETIME()),

        DataHoraExpiraEm        DATETIME2(0) NOT NULL,

        DataHoraUso             DATETIME2(0) NULL,

        Utilizado               BIT NOT NULL
            CONSTRAINT DF_PRT_Utilizado
            DEFAULT (0),

        IP_Solicitante          VARCHAR(64) NULL,

        UserAgent               VARCHAR(400) NULL,

        CONSTRAINT FK_PRT_Usuario
            FOREIGN KEY (ID_Usuario)
            REFERENCES dbo.Usuarios (ID_Usuario)
    );

    CREATE INDEX IX_PRT_TokenHash
        ON dbo.PasswordResetTokens (TokenHash);

    CREATE INDEX IX_PRT_Usuario_Utilizado
        ON dbo.PasswordResetTokens (ID_Usuario, Utilizado);
END;
