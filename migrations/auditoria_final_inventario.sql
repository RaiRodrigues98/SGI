SET NOCOUNT ON;
SET XACT_ABORT ON;

DECLARE @Resultados TABLE
(
    Ordem       int IDENTITY(1,1) PRIMARY KEY,
    Categoria   varchar(50)  NOT NULL,
    Teste       varchar(160) NOT NULL,
    Status      varchar(12)  NOT NULL,
    TotalFalhas bigint       NOT NULL,
    Detalhe     varchar(500) NULL
);

DECLARE @n bigint;

-- ============================================================
-- AUDITORIA FINAL - INVENTÁRIO
-- Somente leitura: não altera dados nem estrutura.
-- Regra de saída:
--   OK    = nenhuma inconsistência encontrada
--   ERRO  = inconsistência encontrada
--   AVISO = objeto de proteção esperado não localizado
-- ============================================================

-- 01. INVENTÁRIOS - DOMÍNIOS
SELECT @n = COUNT(*)
FROM dbo.Inventarios
WHERE Tipo NOT IN ('OFICIAL','ROTATIVO');
INSERT @Resultados VALUES
('Inventarios','Tipo válido (OFICIAL/ROTATIVO)',
 CASE WHEN @n=0 THEN 'OK' ELSE 'ERRO' END,@n,NULL);

SELECT @n = COUNT(*)
FROM dbo.Inventarios
WHERE Status NOT IN ('ABERTO','EM_CONTAGEM','EM_ANALISE','FINALIZADO','CANCELADO');
INSERT @Resultados VALUES
('Inventarios','Status válido',
 CASE WHEN @n=0 THEN 'OK' ELSE 'ERRO' END,@n,NULL);

SELECT @n = COUNT(*)
FROM dbo.Inventarios
WHERE RodadaAtual < 1;
INSERT @Resultados VALUES
('Inventarios','RodadaAtual >= 1',
 CASE WHEN @n=0 THEN 'OK' ELSE 'ERRO' END,@n,NULL);

SELECT @n = COUNT(*)
FROM dbo.Inventarios
WHERE DataHoraFim IS NOT NULL AND DataHoraFim < DataHoraInicio;
INSERT @Resultados VALUES
('Inventarios','DataHoraFim >= DataHoraInicio',
 CASE WHEN @n=0 THEN 'OK' ELSE 'ERRO' END,@n,NULL);

SELECT @n = COUNT(*)
FROM dbo.Inventarios
WHERE (Status IN ('FINALIZADO','CANCELADO') AND DataHoraFim IS NULL)
   OR (Status = 'ABERTO' AND DataHoraFim IS NOT NULL);
INSERT @Resultados VALUES
('Inventarios','Status coerente com DataHoraFim',
 CASE WHEN @n=0 THEN 'OK' ELSE 'ERRO' END,@n,NULL);

-- 02. RODADAS
SELECT @n = COUNT(*)
FROM dbo.RodadasInventario
WHERE NumeroRodada < 1;
INSERT @Resultados VALUES
('Rodadas','NumeroRodada >= 1',
 CASE WHEN @n=0 THEN 'OK' ELSE 'ERRO' END,@n,NULL);

SELECT @n = COUNT(*)
FROM dbo.RodadasInventario
WHERE Status NOT IN ('ABERTA','EM_CONTAGEM','EM_ANALISE','FINALIZADA','CANCELADA');
INSERT @Resultados VALUES
('Rodadas','Status válido',
 CASE WHEN @n=0 THEN 'OK' ELSE 'ERRO' END,@n,NULL);

SELECT @n = COUNT(*)
FROM dbo.RodadasInventario
WHERE (Status IN ('FINALIZADA','CANCELADA') AND DataHoraFim IS NULL)
   OR (Status = 'ABERTA' AND DataHoraFim IS NOT NULL);
INSERT @Resultados VALUES
('Rodadas','Status coerente com DataHoraFim',
 CASE WHEN @n=0 THEN 'OK' ELSE 'ERRO' END,@n,NULL);

SELECT @n = COUNT(*)
FROM dbo.RodadasInventario R
LEFT JOIN dbo.Inventarios I ON I.ID_Inventario = R.ID_Inventario
WHERE I.ID_Inventario IS NULL;
INSERT @Resultados VALUES
('Rodadas','Sem rodada órfã de Inventarios',
 CASE WHEN @n=0 THEN 'OK' ELSE 'ERRO' END,@n,NULL);

SELECT @n = COUNT(*)
FROM
(
    SELECT ID_Inventario, NumeroRodada
    FROM dbo.RodadasInventario
    GROUP BY ID_Inventario, NumeroRodada
    HAVING COUNT(*) > 1
) X;
INSERT @Resultados VALUES
('Rodadas','Sem NumeroRodada duplicado no mesmo inventário',
 CASE WHEN @n=0 THEN 'OK' ELSE 'ERRO' END,@n,NULL);

-- 03. SESSÕES
SELECT @n = COUNT(*)
FROM dbo.SessoesContagem
WHERE Status NOT IN ('ABERTA','ENCERRADA');
INSERT @Resultados VALUES
('Sessoes','Status válido (ABERTA/ENCERRADA)',
 CASE WHEN @n=0 THEN 'OK' ELSE 'ERRO' END,@n,NULL);

SELECT @n = COUNT(*)
FROM dbo.SessoesContagem
WHERE (Status='ENCERRADA' AND DataHoraFim IS NULL)
   OR (Status='ABERTA' AND DataHoraFim IS NOT NULL);
INSERT @Resultados VALUES
('Sessoes','Status coerente com DataHoraFim',
 CASE WHEN @n=0 THEN 'OK' ELSE 'ERRO' END,@n,NULL);

SELECT @n = COUNT(*)
FROM dbo.SessoesContagem S
LEFT JOIN dbo.Inventarios I ON I.ID_Inventario=S.ID_Inventario
LEFT JOIN dbo.RodadasInventario R ON R.ID_Rodada=S.ID_Rodada
WHERE I.ID_Inventario IS NULL
   OR R.ID_Rodada IS NULL
   OR R.ID_Inventario <> S.ID_Inventario;
INSERT @Resultados VALUES
('Sessoes','Inventário/Rodada da sessão coerentes',
 CASE WHEN @n=0 THEN 'OK' ELSE 'ERRO' END,@n,NULL);

-- 04. CONTAGENS
SELECT @n = COUNT(*)
FROM dbo.Contagens C
LEFT JOIN dbo.SessoesContagem S ON S.ID_Sessao=C.ID_Sessao
WHERE S.ID_Sessao IS NULL;
INSERT @Resultados VALUES
('Contagens','Sem contagem órfã de sessão',
 CASE WHEN @n=0 THEN 'OK' ELSE 'ERRO' END,@n,NULL);

SELECT @n = COUNT(*)
FROM dbo.Contagens
WHERE Status='ATIVA' AND Quantidade <= 0;
INSERT @Resultados VALUES
('Contagens','Contagens ATIVAS com Quantidade > 0',
 CASE WHEN @n=0 THEN 'OK' ELSE 'ERRO' END,@n,NULL);

-- 05. DECISÕES DO GESTOR
SELECT @n = COUNT(*)
FROM dbo.DecisoesGestorInventario
WHERE Decisao NOT IN ('ACEITAR_ESTOQUE','ACEITAR_CONTAGEM','NOVA_RECONTAGEM');
INSERT @Resultados VALUES
('Gestor','Decisao dentro do domínio',
 CASE WHEN @n=0 THEN 'OK' ELSE 'ERRO' END,@n,NULL);

SELECT @n = COUNT(*)
FROM dbo.DecisoesGestorInventario
WHERE Status NOT IN ('ATIVA','SUBSTITUIDA','CONSUMIDA');
INSERT @Resultados VALUES
('Gestor','Status dentro do domínio',
 CASE WHEN @n=0 THEN 'OK' ELSE 'ERRO' END,@n,NULL);

SELECT @n = COUNT(*)
FROM
(
    SELECT ID_Inventario, Codigo, Lote
    FROM dbo.DecisoesGestorInventario
    WHERE Status='ATIVA'
    GROUP BY ID_Inventario, Codigo, Lote
    HAVING COUNT(*) > 1
) X;
INSERT @Resultados VALUES
('Gestor','No máximo uma decisão ATIVA por item',
 CASE WHEN @n=0 THEN 'OK' ELSE 'ERRO' END,@n,NULL);

SELECT @n = COUNT(*)
FROM dbo.DecisoesGestorInventario
WHERE QuantidadeAprovada < 0
   OR (Decisao='ACEITAR_CONTAGEM' AND QuantidadeAprovada IS NULL)
   OR (Decisao='ACEITAR_ESTOQUE' AND QuantidadeAprovada IS NULL)
   OR (Decisao='NOVA_RECONTAGEM' AND QuantidadeAprovada IS NOT NULL)
   OR (Decisao='NOVA_RECONTAGEM'
       AND (Justificativa IS NULL OR LTRIM(RTRIM(Justificativa))=''));
INSERT @Resultados VALUES
('Gestor','Decisao x QuantidadeAprovada x Justificativa',
 CASE WHEN @n=0 THEN 'OK' ELSE 'ERRO' END,@n,NULL);

-- NOVA_RECONTAGEM ativa em inventário já finalizado é inconsistente.
SELECT @n = COUNT(*)
FROM dbo.DecisoesGestorInventario D
JOIN dbo.Inventarios I ON I.ID_Inventario=D.ID_Inventario
WHERE D.Decisao='NOVA_RECONTAGEM'
  AND D.Status='ATIVA'
  AND I.Status IN ('FINALIZADO','CANCELADO');
INSERT @Resultados VALUES
('Gestor','Sem NOVA_RECONTAGEM ATIVA em inventário encerrado',
 CASE WHEN @n=0 THEN 'OK' ELSE 'ERRO' END,@n,NULL);

-- 06. RESULTADO FINAL
SELECT @n = COUNT(*)
FROM dbo.InventarioResultadoFinal
WHERE ABS(ISNULL(DiferencaFinal, QuantidadeFinal-QtdEstoque)
          - (QuantidadeFinal-QtdEstoque)) > 0.0001;
INSERT @Resultados VALUES
('ResultadoFinal','DiferencaFinal = QuantidadeFinal - QtdEstoque',
 CASE WHEN @n=0 THEN 'OK' ELSE 'ERRO' END,@n,NULL);

SELECT @n = COUNT(*)
FROM dbo.InventarioResultadoFinal
WHERE StatusFinal NOT IN ('OK','FALTA','SOBRA');
INSERT @Resultados VALUES
('ResultadoFinal','StatusFinal somente OK/FALTA/SOBRA',
 CASE WHEN @n=0 THEN 'OK' ELSE 'ERRO' END,@n,NULL);

SELECT @n = COUNT(*)
FROM dbo.InventarioResultadoFinal
WHERE (ABS(QuantidadeFinal-QtdEstoque) <= 0.0001 AND StatusFinal <> 'OK')
   OR ((QuantidadeFinal-QtdEstoque) < -0.0001 AND StatusFinal <> 'FALTA')
   OR ((QuantidadeFinal-QtdEstoque) >  0.0001 AND StatusFinal <> 'SOBRA');
INSERT @Resultados VALUES
('ResultadoFinal','StatusFinal coerente com a diferença',
 CASE WHEN @n=0 THEN 'OK' ELSE 'ERRO' END,@n,NULL);

SELECT @n = COUNT(*)
FROM dbo.InventarioResultadoFinal
WHERE OrigemQuantidade NOT IN
('ACEITAR_CONTAGEM','ACEITAR_ESTOQUE','CONTAGEM_CONCILIADA','CONTAGEM_ROTATIVO');
INSERT @Resultados VALUES
('ResultadoFinal','OrigemQuantidade dentro do domínio',
 CASE WHEN @n=0 THEN 'OK' ELSE 'ERRO' END,@n,NULL);

SELECT @n = COUNT(*)
FROM dbo.InventarioResultadoFinal
WHERE (OrigemQuantidade IN ('ACEITAR_ESTOQUE','ACEITAR_CONTAGEM')
       AND ID_DecisaoGestor IS NULL)
   OR (OrigemQuantidade IN ('CONTAGEM_CONCILIADA','CONTAGEM_ROTATIVO')
       AND ID_DecisaoGestor IS NOT NULL);
INSERT @Resultados VALUES
('ResultadoFinal','OrigemQuantidade x ID_DecisaoGestor',
 CASE WHEN @n=0 THEN 'OK' ELSE 'ERRO' END,@n,NULL);

SELECT @n = COUNT(*)
FROM dbo.InventarioResultadoFinal RF
LEFT JOIN dbo.DecisoesGestorInventario D
    ON D.ID_Decisao=RF.ID_DecisaoGestor
WHERE RF.ID_DecisaoGestor IS NOT NULL
  AND (
       D.ID_Decisao IS NULL
       OR D.ID_Inventario<>RF.ID_Inventario
       OR LTRIM(RTRIM(D.Codigo))<>LTRIM(RTRIM(RF.Codigo))
       OR ISNULL(LTRIM(RTRIM(D.Lote)),'')<>ISNULL(LTRIM(RTRIM(RF.Lote)),'')
       OR D.Decisao<>RF.OrigemQuantidade
       OR ABS(ISNULL(D.QuantidadeAprovada,0)-RF.QuantidadeFinal)>0.0001
  );
INSERT @Resultados VALUES
('ResultadoFinal','Decisão gerencial vinculada ao item/quantidade corretos',
 CASE WHEN @n=0 THEN 'OK' ELSE 'ERRO' END,@n,NULL);

SELECT @n = COUNT(*)
FROM dbo.InventarioResultadoFinal RF
JOIN dbo.Inventarios I ON I.ID_Inventario=RF.ID_Inventario
WHERE (I.Tipo='OFICIAL' AND RF.Localizacao IS NOT NULL)
   OR (I.Tipo='ROTATIVO'
       AND (RF.Localizacao IS NULL OR LTRIM(RTRIM(RF.Localizacao))=''));
INSERT @Resultados VALUES
('ResultadoFinal','Localizacao coerente com Tipo do inventário',
 CASE WHEN @n=0 THEN 'OK' ELSE 'ERRO' END,@n,NULL);

SELECT @n = COUNT(*)
FROM dbo.InventarioResultadoFinal RF
LEFT JOIN dbo.RodadasInventario R
  ON R.ID_Inventario=RF.ID_Inventario
 AND R.NumeroRodada=RF.RodadaFinal
WHERE RF.RodadaFinal IS NULL
   OR RF.RodadaFinal < 1
   OR R.ID_Rodada IS NULL;
INSERT @Resultados VALUES
('ResultadoFinal','RodadaFinal válida e existente',
 CASE WHEN @n=0 THEN 'OK' ELSE 'ERRO' END,@n,NULL);

-- Última participação do item (OFICIAL): usa RodadaItens, inclusive participação com quantidade 0.
;WITH UltimaParticipacao AS
(
    SELECT
        RI.ID_Inventario,
        LTRIM(RTRIM(RI.Codigo)) Codigo,
        ISNULL(LTRIM(RTRIM(RI.Lote)),'') Lote,
        MAX(R.NumeroRodada) UltimaRodada
    FROM dbo.RodadaItens RI
    JOIN dbo.RodadasInventario R
      ON R.ID_Rodada=RI.ID_Rodada
     AND R.ID_Inventario=RI.ID_Inventario
    GROUP BY
        RI.ID_Inventario,
        LTRIM(RTRIM(RI.Codigo)),
        ISNULL(LTRIM(RTRIM(RI.Lote)),'')
)
SELECT @n=COUNT(*)
FROM dbo.InventarioResultadoFinal RF
JOIN dbo.Inventarios I ON I.ID_Inventario=RF.ID_Inventario
JOIN UltimaParticipacao U
  ON U.ID_Inventario=RF.ID_Inventario
 AND U.Codigo=LTRIM(RTRIM(RF.Codigo))
 AND U.Lote=ISNULL(LTRIM(RTRIM(RF.Lote)),'')
WHERE I.Tipo='OFICIAL'
  AND RF.RodadaFinal<>U.UltimaRodada;
INSERT @Resultados VALUES
('ResultadoFinal','OFICIAL: RodadaFinal = última participação do item',
 CASE WHEN @n=0 THEN 'OK' ELSE 'ERRO' END,@n,NULL);

-- Unicidade lógica
SELECT @n=COUNT(*)
FROM
(
    SELECT RF.ID_Inventario, RF.Codigo, RF.Lote
    FROM dbo.InventarioResultadoFinal RF
    JOIN dbo.Inventarios I ON I.ID_Inventario=RF.ID_Inventario
    WHERE I.Tipo='OFICIAL'
    GROUP BY RF.ID_Inventario,RF.Codigo,RF.Lote
    HAVING COUNT(*)>1
) X;
INSERT @Resultados VALUES
('ResultadoFinal','OFICIAL sem resultado final duplicado',
 CASE WHEN @n=0 THEN 'OK' ELSE 'ERRO' END,@n,NULL);

SELECT @n=COUNT(*)
FROM
(
    SELECT RF.ID_Inventario,RF.Localizacao,RF.Codigo,RF.Lote
    FROM dbo.InventarioResultadoFinal RF
    JOIN dbo.Inventarios I ON I.ID_Inventario=RF.ID_Inventario
    WHERE I.Tipo='ROTATIVO'
    GROUP BY RF.ID_Inventario,RF.Localizacao,RF.Codigo,RF.Lote
    HAVING COUNT(*)>1
) X;
INSERT @Resultados VALUES
('ResultadoFinal','ROTATIVO sem resultado final duplicado',
 CASE WHEN @n=0 THEN 'OK' ELSE 'ERRO' END,@n,NULL);

-- 07. OBJETOS DE PROTEÇÃO CRÍTICOS
SELECT @n=COUNT(*)
FROM sys.indexes
WHERE object_id=OBJECT_ID('dbo.DecisoesGestorInventario')
  AND name='UX_DecisoesGestorInventario_UmaAtivaPorItem'
  AND is_unique=1
  AND has_filter=1;
INSERT @Resultados VALUES
('Protecoes','Índice UNIQUE de uma decisão ATIVA por item',
 CASE WHEN @n=1 THEN 'OK' ELSE 'AVISO' END,
 CASE WHEN @n=1 THEN 0 ELSE 1 END,
 'Esperado: UX_DecisoesGestorInventario_UmaAtivaPorItem');

SELECT @n=COUNT(*)
FROM sys.indexes
WHERE object_id=OBJECT_ID('dbo.InventarioResultadoFinal')
  AND name='UX_InventarioResultadoFinal_Oficial'
  AND is_unique=1
  AND has_filter=1;
INSERT @Resultados VALUES
('Protecoes','Índice UNIQUE resultado OFICIAL',
 CASE WHEN @n=1 THEN 'OK' ELSE 'AVISO' END,
 CASE WHEN @n=1 THEN 0 ELSE 1 END,
 'Filtro esperado: Localizacao IS NULL');

SELECT @n=COUNT(*)
FROM sys.indexes
WHERE object_id=OBJECT_ID('dbo.InventarioResultadoFinal')
  AND name='UX_InventarioResultadoFinal_Rotativo'
  AND is_unique=1
  AND has_filter=1;
INSERT @Resultados VALUES
('Protecoes','Índice UNIQUE resultado ROTATIVO',
 CASE WHEN @n=1 THEN 'OK' ELSE 'AVISO' END,
 CASE WHEN @n=1 THEN 0 ELSE 1 END,
 'Filtro esperado: Localizacao IS NOT NULL');

SELECT @n=COUNT(*)
FROM sys.foreign_keys
WHERE parent_object_id=OBJECT_ID('dbo.InventarioResultadoFinal')
  AND name='FK_InventarioResultadoFinal_DecisaoGestor'
  AND is_disabled=0
  AND is_not_trusted=0;
INSERT @Resultados VALUES
('Protecoes','FK ResultadoFinal -> DecisaoGestor ativa/confiável',
 CASE WHEN @n=1 THEN 'OK' ELSE 'AVISO' END,
 CASE WHEN @n=1 THEN 0 ELSE 1 END,NULL);

-- CHECKs: procuramos pela regra, não só pelo nome.
SELECT @n=COUNT(*)
FROM sys.check_constraints
WHERE parent_object_id=OBJECT_ID('dbo.DecisoesGestorInventario')
  AND is_disabled=0
  AND is_not_trusted=0
  AND definition LIKE '%CONSUMIDA%';
INSERT @Resultados VALUES
('Protecoes','CHECK de Status do gestor contempla CONSUMIDA',
 CASE WHEN @n>0 THEN 'OK' ELSE 'AVISO' END,
 CASE WHEN @n>0 THEN 0 ELSE 1 END,NULL);

SELECT @n=COUNT(*)
FROM sys.check_constraints
WHERE parent_object_id=OBJECT_ID('dbo.DecisoesGestorInventario')
  AND is_disabled=0
  AND is_not_trusted=0
  AND definition LIKE '%NOVA_RECONTAGEM%'
  AND definition LIKE '%ACEITAR_CONTAGEM%'
  AND definition LIKE '%ACEITAR_ESTOQUE%';
INSERT @Resultados VALUES
('Protecoes','CHECK do domínio Decisao',
 CASE WHEN @n>0 THEN 'OK' ELSE 'AVISO' END,
 CASE WHEN @n>0 THEN 0 ELSE 1 END,NULL);

SELECT @n=COUNT(*)
FROM sys.check_constraints
WHERE parent_object_id=OBJECT_ID('dbo.InventarioResultadoFinal')
  AND is_disabled=0
  AND is_not_trusted=0
  AND definition LIKE '%CONTAGEM_ROTATIVO%'
  AND definition LIKE '%CONTAGEM_CONCILIADA%';
INSERT @Resultados VALUES
('Protecoes','CHECK do domínio OrigemQuantidade',
 CASE WHEN @n>0 THEN 'OK' ELSE 'AVISO' END,
 CASE WHEN @n>0 THEN 0 ELSE 1 END,NULL);

-- 08. RESUMO
SELECT
    Ordem,
    Categoria,
    Teste,
    Status,
    TotalFalhas,
    Detalhe
FROM @Resultados
ORDER BY
    CASE Status WHEN 'ERRO' THEN 1 WHEN 'AVISO' THEN 2 ELSE 3 END,
    Ordem;

SELECT
    COUNT(*) AS TotalTestes,
    SUM(CASE WHEN Status='OK' THEN 1 ELSE 0 END) AS OK,
    SUM(CASE WHEN Status='ERRO' THEN 1 ELSE 0 END) AS Erros,
    SUM(CASE WHEN Status='AVISO' THEN 1 ELSE 0 END) AS Avisos,
    CASE
        WHEN SUM(CASE WHEN Status='ERRO' THEN 1 ELSE 0 END)>0
            THEN 'REPROVADO'
        WHEN SUM(CASE WHEN Status='AVISO' THEN 1 ELSE 0 END)>0
            THEN 'APROVADO COM AVISOS'
        ELSE 'APROVADO'
    END AS StatusAuditoria
FROM @Resultados;
