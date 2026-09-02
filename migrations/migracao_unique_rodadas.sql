/* ============================================================
   PROTEÇÃO ESTRUTURAL CONTRA RODADAS DUPLICADAS
   SQL Server

   Regra:
   um inventário não pode possuir duas linhas com o mesmo
   NumeroRodada.
   ============================================================ */

-- 1. Antes de criar o índice, verifique duplicidades existentes.
SELECT
    ID_Inventario,
    NumeroRodada,
    COUNT(*) AS Quantidade
FROM dbo.RodadasInventario
GROUP BY
    ID_Inventario,
    NumeroRodada
HAVING COUNT(*) > 1;

-- Se o SELECT acima não retornar linhas, execute o bloco abaixo.

IF NOT EXISTS
(
    SELECT 1
    FROM sys.indexes
    WHERE
        object_id = OBJECT_ID('dbo.RodadasInventario')
        AND name = 'UX_RodadasInventario_Inventario_Numero'
)
BEGIN
    CREATE UNIQUE INDEX UX_RodadasInventario_Inventario_Numero
        ON dbo.RodadasInventario
        (
            ID_Inventario,
            NumeroRodada
        );
END;
