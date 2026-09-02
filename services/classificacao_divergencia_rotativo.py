# services/classificacao_divergencia_rotativo.py

# ============================================================
# NORMALIZAÇÃO
# ============================================================

def normalizar_texto(valor):
    if valor is None:
        return ""
    return str(valor).strip()


def normalizar_localizacao(valor):
    return normalizar_texto(valor).upper()


def normalizar_lote(valor):
    return normalizar_texto(valor)


# ============================================================
# LOCALIZAÇÕES ESPERADAS PARA CÓDIGO + LOTE
# ============================================================

def buscar_localizacoes_esperadas(
    cursor,
    id_inventario: int,
    codigo: str,
    lote: str,
    localizacao_atual: str
):
    codigo = normalizar_texto(codigo)
    lote = normalizar_lote(lote)
    localizacao_atual = normalizar_localizacao(localizacao_atual)

    cursor.execute(
        """
        SELECT DISTINCT
            UPPER(LTRIM(RTRIM(Localizacao))) AS Localizacao
        FROM dbo.InventarioEstoqueSnapshot
        WHERE
            ID_Inventario = ?
            AND LTRIM(RTRIM(Codigo)) = ?
            AND ISNULL(LTRIM(RTRIM(Lote)), '') = ?
            AND UPPER(LTRIM(RTRIM(Localizacao))) <> ?
        ORDER BY
            UPPER(LTRIM(RTRIM(Localizacao)))
        """,
        (
            id_inventario,
            codigo,
            lote,
            localizacao_atual,
        )
    )

    return [
        normalizar_localizacao(linha.Localizacao)
        for linha in cursor.fetchall()
        if normalizar_localizacao(linha.Localizacao)
    ]


# ============================================================
# CLASSIFICAÇÃO INDIVIDUAL
# ============================================================

def classificar_item_rotativo(
    cursor,
    id_inventario: int,
    localizacao: str,
    codigo: str,
    lote: str,
    qtd_estoque: float,
    qtd_contada: float,
    existe_no_snapshot: bool
):
    qtd_estoque = float(qtd_estoque)
    qtd_contada = float(qtd_contada)

    if qtd_estoque == 0 and qtd_contada > 0:

        if existe_no_snapshot:
            return {
                "status": "DIVERGÊNCIA",
                "subtipo_divergencia": "ITEM_SEM_SALDO",
                "localizacoes_esperadas": [],
            }

        localizacoes_esperadas = buscar_localizacoes_esperadas(
            cursor=cursor,
            id_inventario=id_inventario,
            codigo=codigo,
            lote=lote,
            localizacao_atual=localizacao,
        )

        if localizacoes_esperadas:
            return {
                "status": "DIVERGÊNCIA",
                "subtipo_divergencia": "LOCALIZACAO_INCORRETA",
                "localizacoes_esperadas": localizacoes_esperadas,
            }

        return {
            "status": "SOBRA",
            "subtipo_divergencia": "ITEM_NAO_PREVISTO",
            "localizacoes_esperadas": [],
        }

    if qtd_estoque > 0 and qtd_contada == 0:
        return {
            "status": "FALTA",
            "subtipo_divergencia": "QUANTIDADE",
            "localizacoes_esperadas": [],
        }

    if qtd_estoque == qtd_contada:
        return {
            "status": "OK",
            "subtipo_divergencia": None,
            "localizacoes_esperadas": [],
        }

    return {
        "status": "DIVERGÊNCIA",
        "subtipo_divergencia": "QUANTIDADE",
        "localizacoes_esperadas": [],
    }


# ============================================================
# CORRELAÇÃO ENTRE LOTES DO MESMO CÓDIGO
# ============================================================

def aplicar_diagnostico_lotes(itens):
    grupos = {}

    for item in itens:
        if not item.get("resultado_definitivo", True):
            continue

        chave = (
            normalizar_localizacao(item.get("localizacao")),
            normalizar_texto(item.get("codigo")),
        )

        grupos.setdefault(chave, []).append(item)

    for grupo in grupos.values():

        lotes = {
            normalizar_lote(item.get("lote"))
            for item in grupo
        }

        if len(lotes) < 2:
            continue

        total_estoque = sum(
            float(item.get("qtd_estoque", 0))
            for item in grupo
        )

        total_contado = sum(
            float(item.get("qtd_contada", 0))
            for item in grupo
        )

        possui_negativa = any(
            float(item.get("diferenca", 0)) < 0
            for item in grupo
        )

        possui_positiva = any(
            float(item.get("diferenca", 0)) > 0
            for item in grupo
        )

        if not (possui_negativa and possui_positiva):
            continue

        subtipo_grupo = (
            "LOTE_INCORRETO"
            if total_estoque == total_contado
            else "LOTE_E_QUANTIDADE"
        )

        for item in grupo:

            if float(item.get("diferenca", 0)) == 0:
                continue

            if item.get("subtipo_divergencia") in (
                "LOCALIZACAO_INCORRETA",
                "ITEM_SEM_SALDO",
                "ITEM_NAO_PREVISTO",
            ):
                continue

            if item.get("status") in (
                "FALTA",
                "DIVERGÊNCIA",
            ):
                item["subtipo_divergencia"] = subtipo_grupo

    return itens


# ============================================================
# DIAGNÓSTICO COMPLETO PARA UMA DECISÃO
#
# Usa a sessão encerrada informada para não somar sessões antigas.
# ============================================================

def obter_diagnostico_item_rotativo(
    cursor,
    id_inventario: int,
    id_sessao: int,
    localizacao: str,
    codigo: str,
    lote: str
):
    localizacao = normalizar_localizacao(localizacao)
    codigo = normalizar_texto(codigo)
    lote = normalizar_lote(lote)

    cursor.execute(
        """
        WITH Snapshot AS
        (
            SELECT
                UPPER(LTRIM(RTRIM(E.Localizacao))) AS Localizacao,
                LTRIM(RTRIM(E.Codigo)) AS Codigo,
                ISNULL(LTRIM(RTRIM(E.Lote)), '') AS Lote,
                SUM(E.SaldoInventario) AS QtdEstoque
            FROM dbo.InventarioEstoqueSnapshot E
            WHERE
                E.ID_Inventario = ?
                AND UPPER(LTRIM(RTRIM(E.Localizacao))) = ?
                AND LTRIM(RTRIM(E.Codigo)) = ?
            GROUP BY
                UPPER(LTRIM(RTRIM(E.Localizacao))),
                LTRIM(RTRIM(E.Codigo)),
                ISNULL(LTRIM(RTRIM(E.Lote)), '')
        ),
        Contagem AS
        (
            SELECT
                UPPER(LTRIM(RTRIM(S.Localizacao))) AS Localizacao,
                LTRIM(RTRIM(C.Codigo)) AS Codigo,
                ISNULL(LTRIM(RTRIM(C.Lote)), '') AS Lote,
                SUM(C.Quantidade) AS QtdContada
            FROM dbo.Contagens C
            INNER JOIN dbo.SessoesContagem S
                ON S.ID_Sessao = C.ID_Sessao
            WHERE
                C.ID_Sessao = ?
                AND C.Status = 'ATIVA'
                AND UPPER(LTRIM(RTRIM(S.Localizacao))) = ?
                AND LTRIM(RTRIM(C.Codigo)) = ?
            GROUP BY
                UPPER(LTRIM(RTRIM(S.Localizacao))),
                LTRIM(RTRIM(C.Codigo)),
                ISNULL(LTRIM(RTRIM(C.Lote)), '')
        ),
        Universo AS
        (
            SELECT Localizacao, Codigo, Lote FROM Snapshot
            UNION
            SELECT Localizacao, Codigo, Lote FROM Contagem
        )
        SELECT
            U.Localizacao,
            U.Codigo,
            U.Lote,
            ISNULL(E.QtdEstoque, 0) AS QtdEstoque,
            ISNULL(C.QtdContada, 0) AS QtdContada,
            CASE WHEN E.Codigo IS NULL THEN 0 ELSE 1 END AS ExisteNoSnapshot
        FROM Universo U
        LEFT JOIN Snapshot E
            ON E.Localizacao = U.Localizacao
           AND E.Codigo = U.Codigo
           AND E.Lote = U.Lote
        LEFT JOIN Contagem C
            ON C.Localizacao = U.Localizacao
           AND C.Codigo = U.Codigo
           AND C.Lote = U.Lote
        ORDER BY U.Lote
        """,
        (
            id_inventario,
            localizacao,
            codigo,
            id_sessao,
            localizacao,
            codigo,
        )
    )

    linhas = cursor.fetchall()

    itens = []

    for linha in linhas:
        qtd_estoque = float(linha.QtdEstoque)
        qtd_contada = float(linha.QtdContada)
        diferenca = qtd_contada - qtd_estoque

        diagnostico = classificar_item_rotativo(
            cursor=cursor,
            id_inventario=id_inventario,
            localizacao=linha.Localizacao,
            codigo=linha.Codigo,
            lote=linha.Lote,
            qtd_estoque=qtd_estoque,
            qtd_contada=qtd_contada,
            existe_no_snapshot=bool(linha.ExisteNoSnapshot),
        )

        itens.append(
            {
                "localizacao": normalizar_localizacao(linha.Localizacao),
                "codigo": normalizar_texto(linha.Codigo),
                "lote": normalizar_lote(linha.Lote),
                "qtd_estoque": qtd_estoque,
                "qtd_contada": qtd_contada,
                "diferenca": diferenca,
                "existe_no_snapshot": bool(linha.ExisteNoSnapshot),
                "status": diagnostico["status"],
                "subtipo_divergencia": diagnostico["subtipo_divergencia"],
                "localizacoes_esperadas": diagnostico["localizacoes_esperadas"],
                "resultado_definitivo": True,
            }
        )

    itens = aplicar_diagnostico_lotes(itens)

    alvo = next(
        (
            item
            for item in itens
            if (
                item["localizacao"] == localizacao
                and item["codigo"] == codigo
                and item["lote"] == lote
            )
        ),
        None
    )

    if alvo is None:
        return {
            "localizacao": localizacao,
            "codigo": codigo,
            "lote": lote,
            "qtd_estoque": 0.0,
            "qtd_contada": 0.0,
            "diferenca": 0.0,
            "existe_no_snapshot": False,
            "status": "OK",
            "subtipo_divergencia": None,
            "localizacoes_esperadas": [],
        }

    return alvo
