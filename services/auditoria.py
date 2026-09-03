from __future__ import annotations

from typing import Any

from domain.exceptions import BusinessRuleViolation


def consultar_auditoria_inventario(
    *,
    cursor,
    id_inventario: int,
    page: int = 1,
    page_size: int = 50,
) -> dict[str, Any]:
    if id_inventario < 1:
        raise BusinessRuleViolation("id_inventario deve ser maior ou igual a 1.")
    if page < 1:
        raise BusinessRuleViolation("page deve ser maior ou igual a 1.")
    if page_size < 1 or page_size > 200:
        raise BusinessRuleViolation("page_size deve estar entre 1 e 200.")

    cursor.execute(
        """
        SELECT
            ID_Inventario, CodigoInventario, Tipo, Cliente, ClienteId,
            cArmazem, Status, DataHoraInicio, DataHoraFim,
            CriadoPor, FinalizadoPor
        FROM dbo.Inventarios
        WHERE ID_Inventario = ?
        """,
        id_inventario,
    )
    inv = cursor.fetchone()

    if not inv:
        return {
            "tipo_consulta": "AUDITORIA_INVENTARIO",
            "inventario": None,
            "resumo": {
                "total_eventos": 0,
                "primeiro_evento": None,
                "ultimo_evento": None,
            },
            "paginacao": {
                "page": page,
                "page_size": page_size,
                "total_registros": 0,
                "total_paginas": 0,
                "registros_pagina": 0,
                "tem_proxima": False,
                "tem_anterior": False,
            },
            "eventos": [],
        }

    inventario = {
        "id_inventario": inv.ID_Inventario,
        "codigo_inventario": inv.CodigoInventario,
        "tipo": inv.Tipo,
        "cliente": inv.Cliente,
        "cliente_id": inv.ClienteId,
        "armazem": inv.cArmazem,
        "status": inv.Status,
        "data_hora_inicio": inv.DataHoraInicio,
        "data_hora_fim": inv.DataHoraFim,
        "criado_por": inv.CriadoPor,
        "finalizado_por": inv.FinalizadoPor,
    }

    offset = (page - 1) * page_size

    sql = """
    WITH Eventos AS (
        SELECT
            I.DataHoraCriacao AS DataHora,
            CAST('INVENTARIO_CRIADO' AS varchar(60)) AS TipoEvento,
            CAST('INVENTARIO' AS varchar(40)) AS Categoria,
            I.CriadoPor AS Usuario,
            CAST('Inventário criado' AS varchar(200)) AS Titulo,
            CAST(I.Descricao AS varchar(1000)) AS Descricao,
            CAST('Inventarios' AS varchar(60)) AS Entidade,
            CAST(I.ID_Inventario AS varchar(100)) AS EntidadeId,
            CAST(NULL AS varchar(100)) AS Localizacao,
            CAST(NULL AS varchar(100)) AS Codigo,
            CAST(NULL AS varchar(150)) AS Lote,
            CAST(NULL AS decimal(18,4)) AS Quantidade,
            CAST(I.Status AS varchar(100)) AS Status,
            CAST(NULL AS varchar(1000)) AS Motivo,
            CAST(NULL AS varchar(1000)) AS Justificativa
        FROM dbo.Inventarios I
        WHERE I.ID_Inventario = ?

        UNION ALL
        SELECT
            I.DataHoraEncaminhamentoGestor,
            'INVENTARIO_ENCAMINHADO_GESTOR',
            'INVENTARIO',
            I.EncaminhadoGestorPor,
            'Inventário encaminhado ao gestor',
            NULL,
            'Inventarios',
            CAST(I.ID_Inventario AS varchar(100)),
            NULL, NULL, NULL, NULL,
            I.Status,
            NULL,
            NULL
        FROM dbo.Inventarios I
        WHERE I.ID_Inventario = ?
          AND I.DataHoraEncaminhamentoGestor IS NOT NULL

        UNION ALL
        SELECT
            I.DataHoraCancelamento,
            'INVENTARIO_CANCELADO',
            'INVENTARIO',
            I.CanceladoPor,
            'Inventário cancelado',
            NULL,
            'Inventarios',
            CAST(I.ID_Inventario AS varchar(100)),
            NULL, NULL, NULL, NULL,
            I.Status,
            I.MotivoCancelamento,
            NULL
        FROM dbo.Inventarios I
        WHERE I.ID_Inventario = ?
          AND I.DataHoraCancelamento IS NOT NULL

        UNION ALL
        SELECT
            I.DataHoraFim,
            'INVENTARIO_FINALIZADO',
            'INVENTARIO',
            I.FinalizadoPor,
            'Inventário finalizado',
            NULL,
            'Inventarios',
            CAST(I.ID_Inventario AS varchar(100)),
            NULL, NULL, NULL, NULL,
            I.Status,
            NULL,
            NULL
        FROM dbo.Inventarios I
        WHERE I.ID_Inventario = ?
          AND I.DataHoraFim IS NOT NULL

        UNION ALL
        SELECT
            R.DataHoraCriacao,
            'RODADA_CRIADA',
            'RODADA',
            R.CriadoPor,
            CONCAT('Rodada ', R.NumeroRodada, ' criada'),
            NULL,
            'RodadasInventario',
            CAST(R.ID_Rodada AS varchar(100)),
            NULL, NULL, NULL, NULL,
            R.Status,
            NULL,
            NULL
        FROM dbo.RodadasInventario R
        WHERE R.ID_Inventario = ?

        UNION ALL
        SELECT
            R.DataHoraFim,
            'RODADA_FINALIZADA',
            'RODADA',
            NULL,
            CONCAT('Rodada ', R.NumeroRodada, ' finalizada'),
            NULL,
            'RodadasInventario',
            CAST(R.ID_Rodada AS varchar(100)),
            NULL, NULL, NULL, NULL,
            R.Status,
            NULL,
            NULL
        FROM dbo.RodadasInventario R
        WHERE R.ID_Inventario = ?
          AND R.DataHoraFim IS NOT NULL

        UNION ALL
        SELECT
            S.DataHoraInicio,
            'SESSAO_CONTAGEM_INICIADA',
            'CONTAGEM',
            NULL,
            'Sessão de contagem iniciada',
            NULL,
            'SessoesContagem',
            CAST(S.ID_Sessao AS varchar(100)),
            S.Localizacao,
            NULL, NULL, NULL,
            S.Status,
            NULL,
            NULL
        FROM dbo.SessoesContagem S
        WHERE S.ID_Inventario = ?

        UNION ALL
        SELECT
            S.DataHoraFim,
            'SESSAO_CONTAGEM_ENCERRADA',
            'CONTAGEM',
            NULL,
            'Sessão de contagem encerrada',
            NULL,
            'SessoesContagem',
            CAST(S.ID_Sessao AS varchar(100)),
            S.Localizacao,
            NULL, NULL, NULL,
            S.Status,
            NULL,
            NULL
        FROM dbo.SessoesContagem S
        WHERE S.ID_Inventario = ?
          AND S.DataHoraFim IS NOT NULL

        UNION ALL
        SELECT
            C.DataHora,
            'CONTAGEM_REGISTRADA',
            'CONTAGEM',
            C.CriadoPor,
            'Contagem registrada',
            NULL,
            'Contagens',
            CAST(C.ID_Contagem AS varchar(100)),
            S.Localizacao,
            C.Codigo,
            C.Lote,
            CAST(C.Quantidade AS decimal(18,4)),
            C.Status,
            NULL,
            NULL
        FROM dbo.Contagens C
        INNER JOIN dbo.SessoesContagem S
            ON S.ID_Sessao = C.ID_Sessao
        WHERE S.ID_Inventario = ?

        UNION ALL
        SELECT
            C.DataHoraCancelamento,
            'CONTAGEM_CANCELADA',
            'CONTAGEM',
            C.CanceladoPor,
            'Contagem cancelada',
            NULL,
            'Contagens',
            CAST(C.ID_Contagem AS varchar(100)),
            S.Localizacao,
            C.Codigo,
            C.Lote,
            CAST(C.Quantidade AS decimal(18,4)),
            C.Status,
            C.MotivoCancelamento,
            NULL
        FROM dbo.Contagens C
        INNER JOIN dbo.SessoesContagem S
            ON S.ID_Sessao = C.ID_Sessao
        WHERE S.ID_Inventario = ?
          AND C.DataHoraCancelamento IS NOT NULL

        UNION ALL
        SELECT
            D.DataHora,
            'DECISAO_ROTATIVO_REGISTRADA',
            'DECISAO',
            D.Usuario,
            CONCAT('Decisão rotativa: ', D.Decisao),
            NULL,
            'DecisoesRotativo',
            CAST(D.ID_DecisaoRotativo AS varchar(100)),
            D.Localizacao,
            D.Codigo,
            D.Lote,
            NULL,
            D.Status,
            NULL,
            D.Justificativa
        FROM dbo.DecisoesRotativo D
        WHERE D.ID_Inventario = ?

        UNION ALL
        SELECT
            O.DataHoraCriacao,
            'DIVERGENCIA_IDENTIFICADA',
            'DIVERGENCIA',
            O.CriadoPor,
            CONCAT('Divergência identificada: ', O.TipoDivergencia),
            CONCAT(
                'Estoque=', CONVERT(varchar(50), O.QtdEstoque),
                '; Contado=', CONVERT(varchar(50), O.QtdContada),
                '; Diferença=', CONVERT(varchar(50), O.Diferenca)
            ),
            'OcorrenciasDivergencia',
            CAST(O.ID_Ocorrencia AS varchar(100)),
            O.Localizacao,
            O.Codigo,
            O.Lote,
            CAST(O.QtdContada AS decimal(18,4)),
            O.StatusResolucao,
            NULL,
            O.Justificativa
        FROM dbo.OcorrenciasDivergencia O
        WHERE O.ID_Inventario = ?

        UNION ALL
        SELECT
            O.DataHoraResolucao,
            'DIVERGENCIA_RESOLVIDA',
            'DIVERGENCIA',
            O.ResolvidoPor,
            CONCAT('Divergência resolvida: ', O.StatusResolucao),
            O.ObservacaoResolucao,
            'OcorrenciasDivergencia',
            CAST(O.ID_Ocorrencia AS varchar(100)),
            O.Localizacao,
            O.Codigo,
            O.Lote,
            CAST(O.QtdContada AS decimal(18,4)),
            O.StatusResolucao,
            O.TipoResolucao,
            O.Justificativa
        FROM dbo.OcorrenciasDivergencia O
        WHERE O.ID_Inventario = ?
          AND O.DataHoraResolucao IS NOT NULL
    ),
    EventosOrdenados AS (
        SELECT
            E.*,
            COUNT(*) OVER() AS TotalRegistros,
            MIN(E.DataHora) OVER() AS PrimeiroEvento,
            MAX(E.DataHora) OVER() AS UltimoEvento
        FROM Eventos E
        WHERE E.DataHora IS NOT NULL
    )
    SELECT
        DataHora, TipoEvento, Categoria, Usuario, Titulo, Descricao,
        Entidade, EntidadeId, Localizacao, Codigo, Lote, Quantidade,
        Status, Motivo, Justificativa,
        TotalRegistros, PrimeiroEvento, UltimoEvento
    FROM EventosOrdenados
    ORDER BY DataHora DESC, TipoEvento ASC, EntidadeId DESC
    OFFSET ? ROWS
    FETCH NEXT ? ROWS ONLY
    """

    params = [id_inventario] * 13 + [offset, page_size]
    cursor.execute(sql, *params)
    rows = cursor.fetchall()

    eventos = []
    total_registros = 0
    primeiro_evento = None
    ultimo_evento = None

    for row in rows:
        total_registros = int(row.TotalRegistros or 0)
        primeiro_evento = row.PrimeiroEvento
        ultimo_evento = row.UltimoEvento

        eventos.append(
            {
                "data_hora": row.DataHora,
                "tipo_evento": row.TipoEvento,
                "categoria": row.Categoria,
                "usuario": row.Usuario,
                "titulo": row.Titulo,
                "descricao": row.Descricao,
                "entidade": row.Entidade,
                "entidade_id": row.EntidadeId,
                "localizacao": row.Localizacao,
                "codigo": row.Codigo,
                "lote": row.Lote,
                "quantidade": row.Quantidade,
                "status": row.Status,
                "motivo": row.Motivo,
                "justificativa": row.Justificativa,
            }
        )

    if not rows and page > 1:
        cursor.execute(
            """
            WITH E AS (
                SELECT DataHoraCriacao AS DataHora FROM dbo.Inventarios WHERE ID_Inventario = ?
                UNION ALL SELECT DataHoraEncaminhamentoGestor FROM dbo.Inventarios WHERE ID_Inventario = ? AND DataHoraEncaminhamentoGestor IS NOT NULL
                UNION ALL SELECT DataHoraCancelamento FROM dbo.Inventarios WHERE ID_Inventario = ? AND DataHoraCancelamento IS NOT NULL
                UNION ALL SELECT DataHoraFim FROM dbo.Inventarios WHERE ID_Inventario = ? AND DataHoraFim IS NOT NULL
                UNION ALL SELECT DataHoraCriacao FROM dbo.RodadasInventario WHERE ID_Inventario = ?
                UNION ALL SELECT DataHoraFim FROM dbo.RodadasInventario WHERE ID_Inventario = ? AND DataHoraFim IS NOT NULL
                UNION ALL SELECT DataHoraInicio FROM dbo.SessoesContagem WHERE ID_Inventario = ?
                UNION ALL SELECT DataHoraFim FROM dbo.SessoesContagem WHERE ID_Inventario = ? AND DataHoraFim IS NOT NULL
                UNION ALL SELECT C.DataHora FROM dbo.Contagens C INNER JOIN dbo.SessoesContagem S ON S.ID_Sessao=C.ID_Sessao WHERE S.ID_Inventario = ?
                UNION ALL SELECT C.DataHoraCancelamento FROM dbo.Contagens C INNER JOIN dbo.SessoesContagem S ON S.ID_Sessao=C.ID_Sessao WHERE S.ID_Inventario = ? AND C.DataHoraCancelamento IS NOT NULL
                UNION ALL SELECT DataHora FROM dbo.DecisoesRotativo WHERE ID_Inventario = ?
                UNION ALL SELECT DataHoraCriacao FROM dbo.OcorrenciasDivergencia WHERE ID_Inventario = ?
                UNION ALL SELECT DataHoraResolucao FROM dbo.OcorrenciasDivergencia WHERE ID_Inventario = ? AND DataHoraResolucao IS NOT NULL
            )
            SELECT COUNT(*) AS TotalRegistros, MIN(DataHora) AS PrimeiroEvento, MAX(DataHora) AS UltimoEvento
            FROM E
            WHERE DataHora IS NOT NULL
            """,
            *([id_inventario] * 13),
        )
        resumo = cursor.fetchone()
        if resumo:
            total_registros = int(resumo.TotalRegistros or 0)
            primeiro_evento = resumo.PrimeiroEvento
            ultimo_evento = resumo.UltimoEvento

    total_paginas = (
        (total_registros + page_size - 1) // page_size
        if total_registros
        else 0
    )

    return {
        "tipo_consulta": "AUDITORIA_INVENTARIO",
        "inventario": inventario,
        "resumo": {
            "total_eventos": total_registros,
            "primeiro_evento": primeiro_evento,
            "ultimo_evento": ultimo_evento,
        },
        "paginacao": {
            "page": page,
            "page_size": page_size,
            "total_registros": total_registros,
            "total_paginas": total_paginas,
            "registros_pagina": len(eventos),
            "tem_proxima": total_paginas > 0 and page < total_paginas,
            "tem_anterior": page > 1 and total_paginas > 0,
        },
        "eventos": eventos,
    }
