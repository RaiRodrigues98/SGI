from fastapi import HTTPException


# ============================================================
# NORMALIZAÇÃO
# ============================================================

def _normalizar_texto(valor):
    if valor is None:
        return ""
    return str(valor).strip()


def _normalizar_lote(valor):
    return _normalizar_texto(valor)


def _normalizar_localizacao(valor):
    return _normalizar_texto(valor).upper()


def _numero(valor):
    if valor is None:
        return 0
    return valor


# ============================================================
# METADADOS / COLUNAS DE QUANTIDADE
# ============================================================

def _buscar_colunas_tabela(cursor, schema: str, tabela: str):
    cursor.execute(
        """
        SELECT COLUMN_NAME
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = ?
          AND TABLE_NAME = ?
        """,
        (schema, tabela)
    )

    return {
        _normalizar_texto(linha[0]).upper(): _normalizar_texto(linha[0])
        for linha in cursor.fetchall()
    }


def _resolver_coluna_quantidade(cursor, tabela: str, candidatos_coluna):
    colunas = _buscar_colunas_tabela(
        cursor=cursor,
        schema="dbo",
        tabela=tabela
    )

    for nome in candidatos_coluna:
        encontrado = colunas.get(_normalizar_texto(nome).upper())
        if encontrado:
            return encontrado

    raise HTTPException(
        status_code=500,
        detail=(
            f"Não foi possível identificar a coluna de quantidade em dbo.{tabela}. "
            "A análise do ROTATIVO foi interrompida para evitar resultado incorreto."
        )
    )


# ============================================================
# RODADAS
# ============================================================

def _buscar_rodada(cursor, id_inventario: int, id_rodada: int):
    cursor.execute(
        """
        SELECT
            ID_Rodada,
            ID_Inventario,
            NumeroRodada,
            Status
        FROM dbo.RodadasInventario
        WHERE ID_Inventario = ?
          AND ID_Rodada = ?
        """,
        (id_inventario, id_rodada)
    )

    rodada = cursor.fetchone()

    if not rodada:
        raise HTTPException(
            status_code=404,
            detail="Rodada não encontrada para este inventário."
        )

    return rodada


def _buscar_id_rodada_numero(cursor, id_inventario: int, numero_rodada: int):
    cursor.execute(
        """
        SELECT TOP 1 ID_Rodada
        FROM dbo.RodadasInventario
        WHERE ID_Inventario = ?
          AND NumeroRodada = ?
        ORDER BY ID_Rodada DESC
        """,
        (id_inventario, numero_rodada)
    )

    linha = cursor.fetchone()
    return linha.ID_Rodada if linha else None


# ============================================================
# CONCLUSÃO OPERACIONAL DA R2
# ============================================================

def _avaliar_conclusao_operacional(cursor, id_inventario: int, id_rodada: int):
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM dbo.SessoesContagem
        WHERE ID_Inventario = ?
          AND ID_Rodada = ?
          AND Status = 'ABERTA'
        """,
        (id_inventario, id_rodada)
    )
    sessoes_abertas = int(cursor.fetchone()[0])

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM dbo.RodadaLocalizacoes
        WHERE ID_Inventario = ?
          AND ID_Rodada = ?
        """,
        (id_inventario, id_rodada)
    )
    total_localizacoes = int(cursor.fetchone()[0])

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM dbo.RodadaLocalizacoes RL
        WHERE RL.ID_Inventario = ?
          AND RL.ID_Rodada = ?
          AND EXISTS
          (
              SELECT 1
              FROM dbo.SessoesContagem S
              WHERE S.ID_Inventario = RL.ID_Inventario
                AND S.ID_Rodada = RL.ID_Rodada
                AND UPPER(LTRIM(RTRIM(S.Localizacao))) =
                    UPPER(LTRIM(RTRIM(RL.Localizacao)))
                AND S.Status <> 'ABERTA'
          )
        """,
        (id_inventario, id_rodada)
    )
    localizacoes_processadas = int(cursor.fetchone()[0])

    localizacoes_pendentes = max(
        total_localizacoes - localizacoes_processadas,
        0
    )

    concluida = (
        sessoes_abertas == 0
        and total_localizacoes > 0
        and localizacoes_pendentes == 0
    )

    return {
        "rodada_operacional_concluida": concluida,
        "sessoes_abertas": sessoes_abertas,
        "total_localizacoes": total_localizacoes,
        "localizacoes_processadas": localizacoes_processadas,
        "localizacoes_pendentes": localizacoes_pendentes,
    }


# ============================================================
# BASE COMPARATIVA R1 x R2 x SNAPSHOT
# ============================================================

def _buscar_base_comparativa(
    cursor,
    id_inventario: int,
    id_rodada_r1: int,
    id_rodada_r2: int
):
    coluna_qtd_snapshot = _resolver_coluna_quantidade(
        cursor=cursor,
        tabela="InventarioEstoqueSnapshot",
        candidatos_coluna=(
            "SaldoInventario",
            "qArmazenado",
            "Quantidade",
            "QuantidadeEstoque",
            "QtdEstoque",
            "Qtd_WMS",
            "QtdWMS",
            "Saldo",
            "SaldoEstoque",
        )
    )

    coluna_qtd_contagem = _resolver_coluna_quantidade(
        cursor=cursor,
        tabela="Contagens",
        candidatos_coluna=(
            "Quantidade",
            "QuantidadeContada",
            "Quantidade_Contada",
            "QtdContada",
            "Qtd_Contada",
        )
    )

    # O universo da análise da R2 ROTATIVO é EXCLUSIVAMENTE RodadaItens
    # da própria R2. Itens que ficaram OK na R1 não pertencem à recontagem
    # e não podem ser classificados como inconsistência apenas por não terem
    # sido contados novamente.
    sql = f"""
        WITH ItensR2 AS
        (
            SELECT DISTINCT
                LTRIM(RTRIM(Codigo)) AS Codigo,
                ISNULL(LTRIM(RTRIM(Lote)), '') AS Lote
            FROM dbo.RodadaItens
            WHERE ID_Inventario = ?
              AND ID_Rodada = ?
              AND NULLIF(LTRIM(RTRIM(Codigo)), '') IS NOT NULL
        ),
        EscopoLocal AS
        (
            SELECT DISTINCT
                UPPER(LTRIM(RTRIM(Localizacao))) AS Localizacao
            FROM dbo.RodadaLocalizacoes
            WHERE ID_Inventario = ?
              AND ID_Rodada = ?
              AND NULLIF(LTRIM(RTRIM(Localizacao)), '') IS NOT NULL
        ),
        Snapshot AS
        (
            SELECT
                UPPER(LTRIM(RTRIM(E.Localizacao))) AS Localizacao,
                LTRIM(RTRIM(E.Codigo)) AS Codigo,
                ISNULL(LTRIM(RTRIM(E.Lote)), '') AS Lote,
                SUM(COALESCE(E.[{coluna_qtd_snapshot}], 0)) AS QtdWMS
            FROM dbo.InventarioEstoqueSnapshot E
            INNER JOIN ItensR2 I
                ON I.Codigo = LTRIM(RTRIM(E.Codigo))
               AND I.Lote = ISNULL(LTRIM(RTRIM(E.Lote)), '')
            INNER JOIN EscopoLocal X
                ON X.Localizacao = UPPER(LTRIM(RTRIM(E.Localizacao)))
            WHERE E.ID_Inventario = ?
            GROUP BY
                UPPER(LTRIM(RTRIM(E.Localizacao))),
                LTRIM(RTRIM(E.Codigo)),
                ISNULL(LTRIM(RTRIM(E.Lote)), '')
        ),
        R1 AS
        (
            SELECT
                UPPER(LTRIM(RTRIM(S.Localizacao))) AS Localizacao,
                LTRIM(RTRIM(C.Codigo)) AS Codigo,
                ISNULL(LTRIM(RTRIM(C.Lote)), '') AS Lote,
                SUM(COALESCE(C.[{coluna_qtd_contagem}], 0)) AS QtdR1
            FROM dbo.Contagens C
            INNER JOIN dbo.SessoesContagem S
                ON S.ID_Sessao = C.ID_Sessao
            INNER JOIN ItensR2 I
                ON I.Codigo = LTRIM(RTRIM(C.Codigo))
               AND I.Lote = ISNULL(LTRIM(RTRIM(C.Lote)), '')
            INNER JOIN EscopoLocal X
                ON X.Localizacao = UPPER(LTRIM(RTRIM(S.Localizacao)))
            WHERE S.ID_Inventario = ?
              AND S.ID_Rodada = ?
              AND S.ValidaParaConsolidacao = 1
              AND C.Status = 'ATIVA'
            GROUP BY
                UPPER(LTRIM(RTRIM(S.Localizacao))),
                LTRIM(RTRIM(C.Codigo)),
                ISNULL(LTRIM(RTRIM(C.Lote)), '')
        ),
        R2 AS
        (
            SELECT
                UPPER(LTRIM(RTRIM(S.Localizacao))) AS Localizacao,
                LTRIM(RTRIM(C.Codigo)) AS Codigo,
                ISNULL(LTRIM(RTRIM(C.Lote)), '') AS Lote,
                SUM(COALESCE(C.[{coluna_qtd_contagem}], 0)) AS QtdR2
            FROM dbo.Contagens C
            INNER JOIN dbo.SessoesContagem S
                ON S.ID_Sessao = C.ID_Sessao
            INNER JOIN ItensR2 I
                ON I.Codigo = LTRIM(RTRIM(C.Codigo))
               AND I.Lote = ISNULL(LTRIM(RTRIM(C.Lote)), '')
            INNER JOIN EscopoLocal X
                ON X.Localizacao = UPPER(LTRIM(RTRIM(S.Localizacao)))
            WHERE S.ID_Inventario = ?
              AND S.ID_Rodada = ?
              AND S.ValidaParaConsolidacao = 1
              AND C.Status = 'ATIVA'
            GROUP BY
                UPPER(LTRIM(RTRIM(S.Localizacao))),
                LTRIM(RTRIM(C.Codigo)),
                ISNULL(LTRIM(RTRIM(C.Lote)), '')
        ),
        Chaves AS
        (
            -- Para cada item candidato, preserva qualquer localização em que
            -- ele exista no snapshot, tenha sido contado na R1 ou na R2, mas
            -- somente dentro das localizações efetivamente abertas para a R2.
            SELECT Localizacao, Codigo, Lote FROM Snapshot
            UNION
            SELECT Localizacao, Codigo, Lote FROM R1
            UNION
            SELECT Localizacao, Codigo, Lote FROM R2
        )
        SELECT
            K.Localizacao,
            K.Codigo,
            K.Lote,
            COALESCE(E.QtdWMS, 0) AS QtdWMS,
            COALESCE(A.QtdR1, 0) AS QtdR1,
            COALESCE(B.QtdR2, 0) AS QtdR2
        FROM Chaves K
        LEFT JOIN Snapshot E
            ON E.Localizacao = K.Localizacao
           AND E.Codigo = K.Codigo
           AND E.Lote = K.Lote
        LEFT JOIN R1 A
            ON A.Localizacao = K.Localizacao
           AND A.Codigo = K.Codigo
           AND A.Lote = K.Lote
        LEFT JOIN R2 B
            ON B.Localizacao = K.Localizacao
           AND B.Codigo = K.Codigo
           AND B.Lote = K.Lote
        ORDER BY K.Codigo, K.Lote, K.Localizacao
    """

    cursor.execute(
        sql,
        (
            id_inventario,
            id_rodada_r2,
            id_inventario,
            id_rodada_r2,
            id_inventario,
            id_inventario,
            id_rodada_r1,
            id_inventario,
            id_rodada_r2,
        )
    )

    return cursor.fetchall()


# ============================================================
# CLASSIFICAÇÃO DO ITEM
# ============================================================

def _classificar_item(localizacoes):
    total_wms = sum(_numero(x["qtd_wms"]) for x in localizacoes)
    total_r1 = sum(_numero(x["qtd_r1"]) for x in localizacoes)
    total_r2 = sum(_numero(x["qtd_r2"]) for x in localizacoes)

    r2_por_local_igual_wms = all(
        _numero(x["qtd_r2"]) == _numero(x["qtd_wms"])
        for x in localizacoes
    )

    r1_por_local_igual_r2 = all(
        _numero(x["qtd_r1"]) == _numero(x["qtd_r2"])
        for x in localizacoes
    )

    # 1. R2 confirmou exatamente o snapshot, inclusive por endereço.
    if r2_por_local_igual_wms:
        return {
            "classificacao": "RESOLVIDO_R2",
            "requer_gestor": False,
            "pendente_proxima_rodada": False,
        }

    # 2. Total físico está correto, mas a distribuição por endereço não.
    #    Ex.: WMS A04=10/A05=0 e físico A04=0/A05=10.
    if total_r2 == total_wms:
        return {
            "classificacao": "DIVERGENCIA_LOCALIZACAO",
            "requer_gestor": True,
            "pendente_proxima_rodada": False,
        }

    # 3. R1 e R2 repetiram o mesmo resultado físico divergente.
    if r1_por_local_igual_r2:
        return {
            "classificacao": "DIVERGENCIA_CONFIRMADA",
            "requer_gestor": True,
            "pendente_proxima_rodada": False,
        }

    # 4. R1 e R2 discordam entre si e nenhuma resolveu contra o WMS.
    return {
        "classificacao": "INCONSISTENCIA_R1_R2",
        "requer_gestor": False,
        "pendente_proxima_rodada": True,
    }


# ============================================================
# API PRINCIPAL
# ============================================================

def analisar_recontagem_rotativo(
    cursor,
    id_inventario: int,
    id_rodada: int
):
    rodada_r2 = _buscar_rodada(
        cursor=cursor,
        id_inventario=id_inventario,
        id_rodada=id_rodada
    )

    numero_rodada = int(rodada_r2.NumeroRodada)

    if numero_rodada < 2:
        raise HTTPException(
            status_code=400,
            detail="A análise de recontagem ROTATIVO exige uma rodada 2 ou superior."
        )

    id_rodada_r1 = _buscar_id_rodada_numero(
        cursor=cursor,
        id_inventario=id_inventario,
        numero_rodada=1
    )

    if not id_rodada_r1:
        raise HTTPException(
            status_code=400,
            detail="A R1 do inventário ROTATIVO não foi encontrada."
        )

    conclusao = _avaliar_conclusao_operacional(
        cursor=cursor,
        id_inventario=id_inventario,
        id_rodada=id_rodada
    )

    linhas = _buscar_base_comparativa(
        cursor=cursor,
        id_inventario=id_inventario,
        id_rodada_r1=id_rodada_r1,
        id_rodada_r2=id_rodada
    )

    por_item = {}

    for linha in linhas:
        codigo = _normalizar_texto(linha.Codigo)
        lote = _normalizar_lote(linha.Lote)
        localizacao = _normalizar_localizacao(linha.Localizacao)

        chave = (codigo, lote)

        if chave not in por_item:
            por_item[chave] = {
                "codigo": codigo,
                "lote": lote,
                "localizacoes": []
            }

        qtd_wms = _numero(linha.QtdWMS)
        qtd_r1 = _numero(linha.QtdR1)
        qtd_r2 = _numero(linha.QtdR2)

        if qtd_r2 == qtd_wms:
            status_local = "OK"
        elif qtd_r2 < qtd_wms:
            status_local = "FALTA"
        else:
            status_local = "SOBRA"

        por_item[chave]["localizacoes"].append(
            {
                "localizacao": localizacao,
                "qtd_wms": qtd_wms,
                "qtd_r1": qtd_r1,
                "qtd_r2": qtd_r2,
                "diferenca_r2_wms": qtd_r2 - qtd_wms,
                "status": status_local,
            }
        )

    itens = []

    resumo = {
        "total_itens": 0,
        "resolvidos_r2": 0,
        "divergencias_confirmadas": 0,
        "divergencias_localizacao": 0,
        "inconsistencias_r1_r2": 0,
        "itens_para_gestor": 0,
        "itens_para_nova_recontagem": 0,
    }

    for chave in sorted(por_item.keys()):
        item = por_item[chave]
        classificacao = _classificar_item(item["localizacoes"])

        total_wms = sum(x["qtd_wms"] for x in item["localizacoes"])
        total_r1 = sum(x["qtd_r1"] for x in item["localizacoes"])
        total_r2 = sum(x["qtd_r2"] for x in item["localizacoes"])

        item_saida = {
            "codigo": item["codigo"],
            "lote": item["lote"],
            "qtd_wms_total": total_wms,
            "qtd_r1_total": total_r1,
            "qtd_r2_total": total_r2,
            "diferenca_r2_wms_total": total_r2 - total_wms,
            "classificacao": classificacao["classificacao"],
            "requer_gestor": classificacao["requer_gestor"],
            "pendente_proxima_rodada": classificacao["pendente_proxima_rodada"],
            "localizacoes": item["localizacoes"],
        }

        itens.append(item_saida)
        resumo["total_itens"] += 1

        if item_saida["classificacao"] == "RESOLVIDO_R2":
            resumo["resolvidos_r2"] += 1
        elif item_saida["classificacao"] == "DIVERGENCIA_CONFIRMADA":
            resumo["divergencias_confirmadas"] += 1
        elif item_saida["classificacao"] == "DIVERGENCIA_LOCALIZACAO":
            resumo["divergencias_localizacao"] += 1
        elif item_saida["classificacao"] == "INCONSISTENCIA_R1_R2":
            resumo["inconsistencias_r1_r2"] += 1

        if item_saida["requer_gestor"]:
            resumo["itens_para_gestor"] += 1

        if item_saida["pendente_proxima_rodada"]:
            resumo["itens_para_nova_recontagem"] += 1

    pode_encerrar_sem_gestor = (
        conclusao["rodada_operacional_concluida"]
        and resumo["itens_para_gestor"] == 0
        and resumo["itens_para_nova_recontagem"] == 0
    )

    return {
        "id_inventario": id_inventario,
        "id_rodada": id_rodada,
        "numero_rodada": numero_rodada,
        **conclusao,
        "resumo": resumo,
        "pode_encerrar_sem_gestor": pode_encerrar_sem_gestor,
        "itens": itens,
    }
