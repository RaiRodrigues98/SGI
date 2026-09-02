# ============================================================
# COMPARATIVO DE RODADAS - INVENTÁRIO OFICIAL
#
# Compara:
# Snapshot x Rodada 1 x Rodada 2
#
# A localização NÃO participa da conciliação.
# Chave: Código + Lote
#
# A localização é usada somente para:
# - rastreabilidade
# - identificar quais posições devem ser recontadas na R3
# ============================================================


# ============================================================
# BUSCAR LOCALIZAÇÕES BIPADAS EM UMA RODADA
# ============================================================

def buscar_localizacoes_rodada(
    cursor,
    id_inventario: int,
    numero_rodada: int,
    codigo: str,
    lote: str
):

    cursor.execute(
        """
        SELECT
            UPPER(
                LTRIM(
                    RTRIM(S.Localizacao)
                )
            ) AS Localizacao,

            SUM(
                C.Quantidade
            ) AS Quantidade

                FROM dbo.Contagens C

        INNER JOIN dbo.SessoesContagem S
            ON S.ID_Sessao = C.ID_Sessao

        INNER JOIN dbo.RodadasInventario R
            ON R.ID_Rodada = S.ID_Rodada

        WHERE
            S.ID_Inventario = ?
            AND R.NumeroRodada = ?
            AND S.ValidaParaConsolidacao = 1
            AND C.Status = 'ATIVA'

            AND LTRIM(
                RTRIM(C.Codigo)
            ) = ?

            AND ISNULL(
                LTRIM(
                    RTRIM(C.Lote)
                ),
                ''
            ) = ?

        GROUP BY
            UPPER(
                LTRIM(
                    RTRIM(S.Localizacao)
                )
            )
        ORDER BY
            UPPER(
                LTRIM(
                    RTRIM(S.Localizacao)
                )
            )
        """,
        (
            id_inventario,
            numero_rodada,
            codigo,
            lote
        )
    )

    linhas = cursor.fetchall()

    return [
        {
            "localizacao":
                linha.Localizacao,

            "quantidade":
                float(
                    linha.Quantidade
                )
        }
        for linha in linhas
    ]


# ============================================================
# BUSCAR LOCALIZAÇÕES ORIGINAIS DO SNAPSHOT
#
# Usado como fallback quando o item deu FALTA e nunca foi
# bipado nem na R1 nem na R2.
#
# Exemplo:
# R1 = FALTA
# R2 = FALTA
#
# Nesse caso precisamos saber onde procurar fisicamente
# o produto na R3.
# ============================================================

def buscar_localizacoes_snapshot(
    cursor,
    id_inventario: int,
    codigo: str,
    lote: str
):

    cursor.execute(
        """
        SELECT
            UPPER(
                LTRIM(
                    RTRIM(Localizacao)
                )
            ) AS Localizacao,

            SUM(
                SaldoInventario
            ) AS Quantidade

        FROM dbo.InventarioEstoqueSnapshot

        WHERE
            ID_Inventario = ?

            AND LTRIM(
                RTRIM(Codigo)
            ) = ?

            AND ISNULL(
                LTRIM(
                    RTRIM(Lote)
                ),
                ''
            ) = ?

        GROUP BY
            UPPER(
                LTRIM(
                    RTRIM(Localizacao)
                )
            )

        ORDER BY
            UPPER(
                LTRIM(
                    RTRIM(Localizacao)
                )
            )
        """,
        (
            id_inventario,
            codigo,
            lote
        )
    )

    linhas = cursor.fetchall()

    return [
        {
            "localizacao":
                linha.Localizacao,

            "quantidade":
                float(
                    linha.Quantidade
                )
        }
        for linha in linhas
    ]


# ============================================================
# COMPARAR RODADA 1 X RODADA 2
# ============================================================

def comparar_rodadas_oficial(
    cursor,
    id_inventario: int
):

    # ========================================================
    # 1. BUSCA SNAPSHOT + R1 + R2
    # ========================================================

    cursor.execute(
        """
        WITH Snapshot AS
        (
            SELECT
                LTRIM(
                    RTRIM(Codigo)
                ) AS Codigo,

                ISNULL(
                    LTRIM(
                        RTRIM(Lote)
                    ),
                    ''
                ) AS Lote,

                MAX(
                    Descricao
                ) AS Descricao,

                MAX(
                    Unidade
                ) AS Unidade,

                MAX(
                    Categoria
                ) AS Categoria,

                SUM(
                    SaldoInventario
                ) AS QtdEstoque

            FROM dbo.InventarioEstoqueSnapshot

            WHERE ID_Inventario = ?

            GROUP BY
                LTRIM(
                    RTRIM(Codigo)
                ),

                ISNULL(
                    LTRIM(
                        RTRIM(Lote)
                    ),
                    ''
                )
        ),

        R1 AS
        (
            SELECT
                LTRIM(
                    RTRIM(C.Codigo)
                ) AS Codigo,

                ISNULL(
                    LTRIM(
                        RTRIM(C.Lote)
                    ),
                    ''
                ) AS Lote,

                SUM(
                    C.Quantidade
                ) AS QtdR1

            FROM dbo.Contagens C

            INNER JOIN dbo.SessoesContagem S
                ON S.ID_Sessao = C.ID_Sessao

            INNER JOIN dbo.RodadasInventario R
                ON R.ID_Rodada = S.ID_Rodada

            WHERE
                S.ID_Inventario = ?
                AND R.NumeroRodada = 1
                AND S.ValidaParaConsolidacao = 1
                AND C.Status = 'ATIVA'

            GROUP BY
                LTRIM(
                    RTRIM(C.Codigo)
                ),

                ISNULL(
                    LTRIM(
                        RTRIM(C.Lote)
                    ),
                    ''
                )
        ),

        R2 AS
        (
            SELECT
                LTRIM(
                    RTRIM(C.Codigo)
                ) AS Codigo,

                ISNULL(
                    LTRIM(
                        RTRIM(C.Lote)
                    ),
                    ''
                ) AS Lote,

                SUM(
                    C.Quantidade
                ) AS QtdR2

            FROM dbo.Contagens C

            INNER JOIN dbo.SessoesContagem S
                ON S.ID_Sessao = C.ID_Sessao

            INNER JOIN dbo.RodadasInventario R
                ON R.ID_Rodada = S.ID_Rodada

            WHERE
                S.ID_Inventario = ?
                AND R.NumeroRodada = 2
                AND S.ValidaParaConsolidacao = 1
                AND C.Status = 'ATIVA'

            GROUP BY
                LTRIM(
                    RTRIM(C.Codigo)
                ),

                ISNULL(
                    LTRIM(
                        RTRIM(C.Lote)
                    ),
                    ''
                )
        ),

        Chaves AS
        (
            SELECT
                Codigo,
                Lote
            FROM Snapshot

            UNION

            SELECT
                Codigo,
                Lote
            FROM R1

            UNION

            SELECT
                Codigo,
                Lote
            FROM R2
        )

        SELECT
            C.Codigo,
            C.Lote,

            E.Descricao,
            E.Unidade,
            E.Categoria,

            ISNULL(
                E.QtdEstoque,
                0
            ) AS QtdEstoque,

            ISNULL(
                R1.QtdR1,
                0
            ) AS QtdR1,

            ISNULL(
                R2.QtdR2,
                0
            ) AS QtdR2

        FROM Chaves C

        LEFT JOIN Snapshot E
            ON E.Codigo = C.Codigo
           AND E.Lote = C.Lote

        LEFT JOIN R1
            ON R1.Codigo = C.Codigo
           AND R1.Lote = C.Lote

        LEFT JOIN R2
            ON R2.Codigo = C.Codigo
           AND R2.Lote = C.Lote

        ORDER BY
            C.Codigo,
            C.Lote
        """,
        (
            id_inventario,
            id_inventario,
            id_inventario
        )
    )

    linhas = cursor.fetchall()

    itens = []

    # ========================================================
    # 2. ANALISA ITEM POR ITEM
    # ========================================================

    for linha in linhas:

        codigo = linha.Codigo
        lote = linha.Lote

        estoque = float(
            linha.QtdEstoque
        )

        qtd_r1 = float(
            linha.QtdR1
        )

        qtd_r2 = float(
            linha.QtdR2
        )

        # ----------------------------------------------------
        # LOCALIZAÇÕES BIPADAS NA R1
        # ----------------------------------------------------

        localizacoes_r1 = (
            buscar_localizacoes_rodada(
                cursor=cursor,
                id_inventario=id_inventario,
                numero_rodada=1,
                codigo=codigo,
                lote=lote
            )
        )

        # ----------------------------------------------------
        # LOCALIZAÇÕES BIPADAS NA R2
        # ----------------------------------------------------

        localizacoes_r2 = (
            buscar_localizacoes_rodada(
                cursor=cursor,
                id_inventario=id_inventario,
                numero_rodada=2,
                codigo=codigo,
                lote=lote
            )
        )

        # ----------------------------------------------------
        # LOCALIZAÇÕES ORIGINAIS DO SNAPSHOT
        # ----------------------------------------------------

        localizacoes_snapshot = (
            buscar_localizacoes_snapshot(
                cursor=cursor,
                id_inventario=id_inventario,
                codigo=codigo,
                lote=lote
            )
        )

        # ====================================================
        # STATUS R1
        # ====================================================

        if (
            estoque == 0
            and qtd_r1 > 0
        ):
            status_r1 = "SOBRA"

        elif (
            estoque > 0
            and qtd_r1 == 0
        ):
            status_r1 = "FALTA"

        elif estoque == qtd_r1:
            status_r1 = "OK"

        else:
            status_r1 = "DIVERGÊNCIA"

        # ====================================================
        # STATUS R2
        # ====================================================

        if (
            estoque == 0
            and qtd_r2 > 0
        ):
            status_r2 = "SOBRA"

        elif (
            estoque > 0
            and qtd_r2 == 0
        ):
            status_r2 = "FALTA"

        elif estoque == qtd_r2:
            status_r2 = "OK"

        else:
            status_r2 = "DIVERGÊNCIA"

        # ====================================================
        # REGRA DO CLIENTE 53
        #
        # Divergiu na R1 OU R2
        # -> entra na R3
        # ====================================================

        vai_para_r3 = (
            status_r1 != "OK"
            or
            status_r2 != "OK"
        )

        # ====================================================
        # LOCALIZAÇÕES PARA RECONTAGEM NA R3
        #
        # Primeiro:
        # união das localizações bipadas na R1 e R2.
        #
        # Se nunca foi bipado:
        # usa as localizações originais do snapshot.
        # ====================================================

        localizacoes_encontradas = {
            item["localizacao"]
            for item in (
                localizacoes_r1
                +
                localizacoes_r2
            )
        }

        # ----------------------------------------------------
        # FALLBACK
        #
        # Exemplo:
        # R1 = FALTA
        # R2 = FALTA
        #
        # Nenhuma posição foi bipada.
        # Então usamos o snapshot.
        # ----------------------------------------------------

        if (
            vai_para_r3
            and not localizacoes_encontradas
        ):

            localizacoes_encontradas = {
                item["localizacao"]
                for item
                in localizacoes_snapshot
            }

        localizacoes_para_recontagem = sorted(
            localizacoes_encontradas
        )

        # ====================================================
        # MOTIVO DA R3
        # ====================================================

        if vai_para_r3:

            if (
                status_r1 != "OK"
                and
                status_r2 != "OK"
            ):
                motivo_r3 = (
                    "DIVERGENCIA_R1_R2"
                )

            elif status_r1 != "OK":
                motivo_r3 = (
                    "DIVERGENCIA_R1"
                )

            else:
                motivo_r3 = (
                    "DIVERGENCIA_R2"
                )

        else:
            motivo_r3 = None

        # ====================================================
        # ITEM
        # ====================================================

        itens.append(
            {
                "chave":
                    f"{codigo}|{lote}",

                "codigo":
                    codigo,

                "lote":
                    lote,

                "descricao":
                    linha.Descricao,

                "unidade":
                    linha.Unidade,

                "categoria":
                    linha.Categoria,

                "qtd_estoque":
                    estoque,

                # ============================================
                # LOCALIZAÇÕES DO SNAPSHOT
                # ============================================

                "localizacoes_snapshot":
                    localizacoes_snapshot,

                # ============================================
                # RODADA 1
                # ============================================

                "rodada_1": {
                    "quantidade":
                        qtd_r1,

                    "diferenca":
                        qtd_r1 - estoque,

                    "status":
                        status_r1,

                    "localizacoes_bipadas":
                        localizacoes_r1
                },

                # ============================================
                # RODADA 2
                # ============================================

                "rodada_2": {
                    "quantidade":
                        qtd_r2,

                    "diferenca":
                        qtd_r2 - estoque,

                    "status":
                        status_r2,

                    "localizacoes_bipadas":
                        localizacoes_r2
                },

                # ============================================
                # RODADA 3
                # ============================================

                "vai_para_r3":
                    vai_para_r3,

                "motivo_r3":
                    motivo_r3,

                "localizacoes_para_recontagem":
                    (
                        localizacoes_para_recontagem
                        if vai_para_r3
                        else []
                    )
            }
        )

    # ========================================================
    # 3. RESUMO
    # ========================================================

    total = len(itens)

    r1_ok = sum(
        1
        for item in itens
        if (
            item["rodada_1"]["status"]
            == "OK"
        )
    )

    r1_divergencias = sum(
        1
        for item in itens
        if (
            item["rodada_1"]["status"]
            != "OK"
        )
    )

    r2_ok = sum(
        1
        for item in itens
        if (
            item["rodada_2"]["status"]
            == "OK"
        )
    )

    r2_divergencias = sum(
        1
        for item in itens
        if (
            item["rodada_2"]["status"]
            != "OK"
        )
    )

    candidatos_r3 = sum(
        1
        for item in itens
        if item["vai_para_r3"]
    )

    # ========================================================
    # LOCALIZAÇÕES ÚNICAS DA R3
    # ========================================================

    localizacoes_r3 = sorted(
        {
            localizacao

            for item in itens

            if item["vai_para_r3"]

            for localizacao
            in item[
                "localizacoes_para_recontagem"
            ]
        }
    )

    # ========================================================
    # RETORNO
    # ========================================================

    return {
        "total_itens":
            total,

        "rodada_1_ok":
            r1_ok,

        "rodada_1_divergencias":
            r1_divergencias,

        "rodada_2_ok":
            r2_ok,

        "rodada_2_divergencias":
            r2_divergencias,

        "candidatos_r3":
            candidatos_r3,

        "total_localizacoes_r3":
            len(
                localizacoes_r3
            ),

        "localizacoes_r3":
            localizacoes_r3,

        "itens":
            itens
    }