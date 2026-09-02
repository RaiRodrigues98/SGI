from datetime import date

from domain.exceptions import BusinessRuleViolation


# ============================================================
# NORMALIZAÇÃO
# ============================================================

def _normalizar_texto(valor):

    if valor is None:
        return ""

    return str(valor).strip()


# ============================================================
# HISTÓRICO DE INVENTÁRIOS
#
# Filtros:
# - cliente_id
# - tipo
# - status
# - data_inicio
# - data_fim
# - codigo_inventario
# - page
# - page_size
# ============================================================

def consultar_historico_inventarios(
    cursor,
    cliente_id=None,
    tipo=None,
    status=None,
    data_inicio=None,
    data_fim=None,
    codigo_inventario=None,
    page: int = 1,
    page_size: int = 50
):

    # ========================================================
    # 1. VALIDA PAGINAÇÃO
    # ========================================================

    if page < 1:

        raise BusinessRuleViolation(
            "page deve ser maior ou igual a 1."
        )

    if page_size < 1 or page_size > 200:

        raise BusinessRuleViolation(
            "page_size deve estar entre 1 e 200."
        )

    offset = (
        page - 1
    ) * page_size

    # ========================================================
    # 2. MONTA FILTROS
    # ========================================================

    filtros = []
    parametros = []

    if cliente_id is not None:

        filtros.append(
            "I.ClienteId = ?"
        )

        parametros.append(
            cliente_id
        )

    if _normalizar_texto(tipo):

        filtros.append(
            "UPPER(LTRIM(RTRIM(I.Tipo))) = ?"
        )

        parametros.append(
            _normalizar_texto(tipo).upper()
        )

    if _normalizar_texto(status):

        filtros.append(
            "UPPER(LTRIM(RTRIM(I.Status))) = ?"
        )

        parametros.append(
            _normalizar_texto(status).upper()
        )

    if data_inicio is not None:

        filtros.append(
            """
            I.DataHoraInicio >= ?
            """
        )

        parametros.append(
            data_inicio
        )

    if data_fim is not None:

        filtros.append(
            """
            I.DataHoraInicio < DATEADD(
                DAY,
                1,
                CAST(? AS date)
            )
            """
        )

        parametros.append(
            data_fim
        )

    if _normalizar_texto(
        codigo_inventario
    ):

        filtros.append(
            """
            I.CodigoInventario LIKE ?
            """
        )

        parametros.append(
            "%"
            +
            _normalizar_texto(
                codigo_inventario
            )
            +
            "%"
        )

    where_sql = ""

    if filtros:

        where_sql = (
            "WHERE "
            +
            " AND ".join(
                filtros
            )
        )

    # ========================================================
    # 3. TOTAL DE REGISTROS
    # ========================================================

    sql_total = f"""
        SELECT COUNT(*)

        FROM dbo.Inventarios I

        {where_sql}
    """

    cursor.execute(
        sql_total,
        tuple(parametros)
    )

    total_registros = int(
        cursor.fetchone()[0]
        or
        0
    )

    # ========================================================
    # 4. CONSULTA PAGINADA
    # ========================================================

    sql = f"""
        SELECT
            I.ID_Inventario,
            I.CodigoInventario,
            I.Tipo,
            I.Cliente,
            I.ClienteId,
            I.cArmazem,
            I.Descricao,
            I.RodadaAtual,
            I.Status,
            I.DataHoraInicio,
            I.DataHoraFim,
            I.CriadoPor,
            I.DataHoraCriacao,
            I.FinalizadoPor,
            I.EmAnaliseGestor,
            I.DataHoraEncaminhamentoGestor,
            I.EncaminhadoGestorPor,
            I.CanceladoPor,
            I.MotivoCancelamento,
            I.DataHoraCancelamento

        FROM dbo.Inventarios I

        {where_sql}

        ORDER BY
            I.DataHoraCriacao DESC,
            I.ID_Inventario DESC

        OFFSET ? ROWS
        FETCH NEXT ? ROWS ONLY
    """

    parametros_paginados = (
        parametros
        +
        [
            offset,
            page_size
        ]
    )

    cursor.execute(
        sql,
        tuple(
            parametros_paginados
        )
    )

    linhas = cursor.fetchall()

    # ========================================================
    # 5. MONTA RETORNO
    # ========================================================

    inventarios = []

    for linha in linhas:

        inventarios.append(
            {
                "id_inventario":
                    linha.ID_Inventario,

                "codigo_inventario":
                    linha.CodigoInventario,

                "tipo":
                    linha.Tipo,

                "cliente":
                    linha.Cliente,

                "cliente_id":
                    linha.ClienteId,

                "armazem":
                    linha.cArmazem,

                "descricao":
                    linha.Descricao,

                "rodada_atual":
                    linha.RodadaAtual,

                "status":
                    linha.Status,

                "data_hora_inicio":
                    linha.DataHoraInicio,

                "data_hora_fim":
                    linha.DataHoraFim,

                "criado_por":
                    linha.CriadoPor,

                "data_hora_criacao":
                    linha.DataHoraCriacao,

                "finalizado_por":
                    linha.FinalizadoPor,

                "gestor": {
                    "em_analise":
                        bool(
                            linha.EmAnaliseGestor
                        )
                        if linha.EmAnaliseGestor is not None
                        else False,

                    "data_hora_encaminhamento":
                        linha.DataHoraEncaminhamentoGestor,

                    "encaminhado_por":
                        linha.EncaminhadoGestorPor
                },

                "cancelamento": {
                    "cancelado":
                        (
                            linha.DataHoraCancelamento
                            is not None
                        ),

                    "cancelado_por":
                        linha.CanceladoPor,

                    "motivo":
                        linha.MotivoCancelamento,

                    "data_hora":
                        linha.DataHoraCancelamento
                }
            }
        )

    # ========================================================
    # 6. PAGINAÇÃO
    # ========================================================

    total_paginas = (
        (
            total_registros
            +
            page_size
            -
            1
        )
        //
        page_size
    )

    return {
        "tipo_consulta":
            "HISTORICO_INVENTARIOS",

        "paginacao": {
            "page":
                page,

            "page_size":
                page_size,

            "total_registros":
                total_registros,

            "total_paginas":
                total_paginas,

            "possui_proxima_pagina":
                page < total_paginas,

            "possui_pagina_anterior":
                page > 1
        },

        "filtros": {
            "cliente_id":
                cliente_id,

            "tipo":
                tipo,

            "status":
                status,

            "data_inicio":
                data_inicio,

            "data_fim":
                data_fim,

            "codigo_inventario":
                codigo_inventario
        },

        "inventarios":
            inventarios
    }