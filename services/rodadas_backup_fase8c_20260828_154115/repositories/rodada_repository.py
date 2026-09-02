"""
Repository SQL Server para dbo.RodadasInventario.

Fase 8A.

Regra arquitetural:
- somente persistência;
- sem regra de negócio;
- sem HTTPException;
- sem commit/rollback;
- consultas mantidas separadas para preservar exatamente
  projeções, filtros e ordenações da baseline aprovada.
"""


def buscar_rodada_para_finalizacao(
    cursor,
    id_inventario: int,
    id_rodada: int
):

    cursor.execute(
        """
        SELECT
            ID_Rodada,
            Status

        FROM dbo.RodadasInventario

        WHERE
            ID_Inventario = ?
            AND ID_Rodada = ?
        """,
        (
            id_inventario,
            id_rodada
        )
    )

    return cursor.fetchone()


def marcar_rodada_finalizada(
    cursor,
    id_inventario: int,
    id_rodada: int
):

    cursor.execute(
        """
        UPDATE dbo.RodadasInventario

        SET
            Status = 'FINALIZADA',
            DataHoraFim = COALESCE(
                DataHoraFim,
                SYSDATETIME()
            )

        WHERE
            ID_Inventario = ?
            AND ID_Rodada = ?
            AND Status <> 'FINALIZADA'
        """,
        (
            id_inventario,
            id_rodada
        )
    )

    return cursor.rowcount


def buscar_proxima_rodada_existente(
    cursor,
    id_inventario: int,
    numero_proxima: int
):

    cursor.execute(
        """
        SELECT
            ID_Rodada,
            NumeroRodada,
            Status,
            DataHoraInicio

        FROM dbo.RodadasInventario

        WHERE
            ID_Inventario = ?
            AND NumeroRodada = ?
        """,
        (
            id_inventario,
            numero_proxima
        )
    )

    return cursor.fetchone()


def inserir_rodada_aberta(
    cursor,
    id_inventario: int,
    numero_rodada: int
):

    cursor.execute(
        """
        INSERT INTO dbo.RodadasInventario
        (
            ID_Inventario,
            NumeroRodada,
            Status,
            DataHoraInicio
        )

        OUTPUT
            INSERTED.ID_Rodada,
            INSERTED.NumeroRodada,
            INSERTED.Status,
            INSERTED.DataHoraInicio

        VALUES
        (
            ?,
            ?,
            'ABERTA',
            SYSDATETIME()
        )
        """,
        (
            id_inventario,
            numero_rodada
        )
    )

    return cursor.fetchone()


def buscar_r1(
    cursor,
    id_inventario: int
):

    cursor.execute(
        """
        SELECT TOP 1
            ID_Rodada

        FROM dbo.RodadasInventario

        WHERE
            ID_Inventario = ?
            AND NumeroRodada = 1

        ORDER BY
            ID_Rodada
        """,
        id_inventario
    )

    return cursor.fetchone()


def buscar_proxima_rodada_preview(
    cursor,
    id_inventario: int,
    numero_proxima: int
):

    cursor.execute(
        """
        SELECT TOP 1
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
            numero_proxima
        )
    )

    return cursor.fetchone()


def buscar_rodada_para_sincronizacao(
    cursor,
    id_rodada: int,
    id_inventario: int
):

    cursor.execute(
        """
        SELECT
            ID_Rodada,
            ID_Inventario,
            NumeroRodada,
            Status

        FROM dbo.RodadasInventario

        WHERE
            ID_Rodada = ?
            AND ID_Inventario = ?
        """,
        (
            id_rodada,
            id_inventario
        )
    )

    return cursor.fetchone()
