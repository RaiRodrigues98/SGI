SET NOCOUNT ON;
SET XACT_ABORT ON;

IF EXISTS
(
    SELECT 1
    FROM sys.check_constraints
    WHERE name = 'CK_OcorrenciasDivergencia_StatusResolucao'
      AND parent_object_id = OBJECT_ID('dbo.OcorrenciasDivergencia')
)
BEGIN
    ALTER TABLE dbo.OcorrenciasDivergencia
    DROP CONSTRAINT CK_OcorrenciasDivergencia_StatusResolucao;
END;

ALTER TABLE dbo.OcorrenciasDivergencia
ADD CONSTRAINT CK_OcorrenciasDivergencia_StatusResolucao
CHECK
(
    StatusResolucao IN
    (
        'PENDENTE',
        'JUSTIFICADA',
        'EM_RECONTAGEM',
        'DIVERGENCIA_CONFIRMADA',
        'RESOLVIDA_RECONTAGEM',
        'RESOLVIDA_AJUSTE',
        'RESOLVIDA_OFICIAL',
        'RESOLVIDA_EFICACIA'
    )
);
