SET XACT_ABORT ON;

IF COL_LENGTH(
    'dbo.SessoesContagem',
    'ID_UsuarioAbertura'
) IS NULL
BEGIN
    EXEC(
        'ALTER TABLE dbo.SessoesContagem
         ADD ID_UsuarioAbertura INT NULL'
    );
END;

IF COL_LENGTH(
    'dbo.SessoesContagem',
    'UsuarioAberturaLogin'
) IS NULL
BEGIN
    EXEC(
        'ALTER TABLE dbo.SessoesContagem
         ADD UsuarioAberturaLogin VARCHAR(100) NULL'
    );
END;

IF COL_LENGTH(
    'dbo.SessoesContagem',
    'UsuarioAberturaNome'
) IS NULL
BEGIN
    EXEC(
        'ALTER TABLE dbo.SessoesContagem
         ADD UsuarioAberturaNome VARCHAR(150) NULL'
    );
END;

EXEC sp_executesql N'
;WITH PrimeiroOperador AS
(
    SELECT
        C.ID_Sessao,
        LTRIM(RTRIM(C.CriadoPor)) AS LoginOperador,

        ROW_NUMBER() OVER
        (
            PARTITION BY C.ID_Sessao
            ORDER BY C.ID_Contagem
        ) AS Ordem

    FROM dbo.Contagens C

    WHERE NULLIF(
        LTRIM(RTRIM(C.CriadoPor)),
        ''''
    ) IS NOT NULL
)
UPDATE S

SET
    ID_UsuarioAbertura =
        COALESCE(
            S.ID_UsuarioAbertura,
            U.ID_Usuario
        ),

    UsuarioAberturaLogin =
        COALESCE(
            NULLIF(
                S.UsuarioAberturaLogin,
                ''''
            ),
            P.LoginOperador
        ),

    UsuarioAberturaNome =
        COALESCE(
            NULLIF(
                S.UsuarioAberturaNome,
                ''''
            ),
            U.Nome,
            P.LoginOperador
        )

FROM dbo.SessoesContagem S

INNER JOIN PrimeiroOperador P
    ON P.ID_Sessao = S.ID_Sessao
   AND P.Ordem = 1

LEFT JOIN dbo.Usuarios U
    ON U.Login = P.LoginOperador

WHERE
    S.ID_UsuarioAbertura IS NULL
    OR NULLIF(
        S.UsuarioAberturaLogin,
        ''''
    ) IS NULL
    OR NULLIF(
        S.UsuarioAberturaNome,
        ''''
    ) IS NULL;
';
