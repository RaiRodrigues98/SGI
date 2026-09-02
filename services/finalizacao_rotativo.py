from domain.exceptions import BusinessRuleViolation, NotFoundError
from fastapi import HTTPException


# ============================================================
# FINALIZAÇÃO DO INVENTÁRIO ROTATIVO
#
# Regras:
# - R1 é a contagem inicial completa;
# - R2 contém somente divergências da R1;
# - R2 é a última rodada física do ROTATIVO;
# - itens não recontados usam a quantidade da R1;
# - itens recontados usam a quantidade da R2;
# - divergências podem permanecer no resultado final;
# - decisões/justificativas rotativas permanecem rastreáveis;
# - grava dbo.InventarioResultadoFinal antes de finalizar
#   definitivamente o inventário;
# - o commit continua sendo responsabilidade do router.
# ============================================================


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

    return (
        _normalizar_texto(valor)
        .upper()
    )


# ============================================================
# STATUS FINAL
# ============================================================

def _calcular_status_final(
    qtd_estoque: float,
    quantidade_final: float
):

    diferenca = (
        quantidade_final
        -
        qtd_estoque
    )

    if abs(diferenca) <= 0.0001:
        return "OK"

    if diferenca < 0:
        return "FALTA"

    return "SOBRA"


# ============================================================
# VERIFICA SE RESULTADO FINAL JÁ EXISTE
# ============================================================

def _resultado_final_ja_existe(
    cursor,
    id_inventario: int
):

    cursor.execute(
        """
        SELECT COUNT(*)

        FROM dbo.InventarioResultadoFinal

        WHERE ID_Inventario = ?
        """,
        id_inventario
    )

    return (
        cursor.fetchone()[0] > 0
    )


# ============================================================
# BUSCAR DECISÃO ROTATIVA ATIVA
# ============================================================

def _buscar_decisao_rotativa_ativa(
    cursor,
    id_inventario: int,
    id_rodada: int,
    localizacao: str,
    codigo: str,
    lote: str
):

    cursor.execute(
        """
        SELECT TOP 1
            ID_DecisaoRotativo,
            Decisao,
            Justificativa,
            Usuario,
            DataHora,
            Status

        FROM dbo.DecisoesRotativo

        WHERE
            ID_Inventario = ?
            AND ID_Rodada = ?

            AND UPPER(
                LTRIM(
                    RTRIM(Localizacao)
                )
            ) = ?

            AND LTRIM(
                RTRIM(Codigo)
            ) = ?

            AND ISNULL(
                LTRIM(
                    RTRIM(Lote)
                ),
                ''
            ) = ?

            AND Status = 'ATIVA'

        ORDER BY
            ID_DecisaoRotativo DESC
        """,
        (
            id_inventario,
            id_rodada,
            localizacao,
            codigo,
            lote
        )
    )

    linha = cursor.fetchone()

    if not linha:
        return None

    return {
        "id_decisao_rotativo":
            linha.ID_DecisaoRotativo,

        "decisao":
            linha.Decisao,

        "justificativa":
            linha.Justificativa,

        "usuario":
            linha.Usuario,

        "data_hora":
            linha.DataHora,

        "status":
            linha.Status
    }


# ============================================================
# BUSCAR ITENS DO SNAPSHOT
# ============================================================

def _buscar_itens_snapshot(
    cursor,
    id_inventario: int
):

    cursor.execute(
        """
        SELECT
            UPPER(
                LTRIM(
                    RTRIM(Localizacao)
                )
            ) AS Localizacao,

            LTRIM(
                RTRIM(Codigo)
            ) AS Codigo,

            ISNULL(
                LTRIM(
                    RTRIM(Lote)
                ),
                ''
            ) AS Lote,

            MAX(Descricao) AS Descricao,
            MAX(Unidade) AS Unidade,
            MAX(Categoria) AS Categoria,

            SUM(
                COALESCE(
                    SaldoInventario,
                    0
                )
            ) AS QtdEstoque

        FROM dbo.InventarioEstoqueSnapshot

        WHERE
            ID_Inventario = ?
            AND NULLIF(
                LTRIM(
                    RTRIM(Localizacao)
                ),
                ''
            ) IS NOT NULL
            AND NULLIF(
                LTRIM(
                    RTRIM(Codigo)
                ),
                ''
            ) IS NOT NULL

        GROUP BY
            UPPER(
                LTRIM(
                    RTRIM(Localizacao)
                )
            ),
            LTRIM(
                RTRIM(Codigo)
            ),
            ISNULL(
                LTRIM(
                    RTRIM(Lote)
                ),
                ''
            )

        ORDER BY
            UPPER(
                LTRIM(
                    RTRIM(Localizacao)
                )
            ),
            LTRIM(
                RTRIM(Codigo)
            ),
            ISNULL(
                LTRIM(
                    RTRIM(Lote)
                ),
                ''
            )
        """,
        id_inventario
    )

    linhas = cursor.fetchall()

    return [
        {
            "localizacao":
                _normalizar_localizacao(
                    linha.Localizacao
                ),

            "codigo":
                _normalizar_texto(
                    linha.Codigo
                ),

            "lote":
                _normalizar_lote(
                    linha.Lote
                ),

            "descricao":
                linha.Descricao,

            "unidade":
                linha.Unidade,

            "categoria":
                linha.Categoria,

            "qtd_estoque":
                float(
                    linha.QtdEstoque or 0
                )
        }
        for linha in linhas
    ]


# ============================================================
# BUSCAR QUANTIDADE CONTADA
# ============================================================

def _buscar_quantidade_contada(
    cursor,
    id_inventario: int,
    id_rodada: int,
    localizacao: str,
    codigo: str,
    lote: str
):

    cursor.execute(
        """
        SELECT
            COALESCE(
                SUM(C.Quantidade),
                0
            ) AS QtdContada

        FROM dbo.Contagens C

        INNER JOIN dbo.SessoesContagem S
            ON S.ID_Sessao = C.ID_Sessao

        WHERE
            S.ID_Inventario = ?
            AND S.ID_Rodada = ?
            AND S.ValidaParaConsolidacao = 1
            
            AND UPPER(
                LTRIM(
                    RTRIM(S.Localizacao)
                )
            ) = ?

            AND LTRIM(
                RTRIM(C.Codigo)
            ) = ?

            AND ISNULL(
                LTRIM(
                    RTRIM(C.Lote)
                ),
                ''
            ) = ?

            AND C.Status = 'ATIVA'
        """,
        (
            id_inventario,
            id_rodada,
            localizacao,
            codigo,
            lote
        )
    )

    linha = cursor.fetchone()

    return float(
        linha.QtdContada or 0
    )


# ============================================================
# ITEM PARTICIPOU DA R2?
# ============================================================

def _item_participou_r2(
    cursor,
    id_inventario: int,
    id_rodada_r2: int,
    codigo: str,
    lote: str
):

    cursor.execute(
        """
        SELECT COUNT(*)

        FROM dbo.RodadaItens

        WHERE
            ID_Inventario = ?
            AND ID_Rodada = ?

            AND LTRIM(
                RTRIM(Codigo)
            ) = ?

            AND ISNULL(
                LTRIM(
                    RTRIM(Lote)
                ),
                ''
            ) = ?
        """,
        (
            id_inventario,
            id_rodada_r2,
            codigo,
            lote
        )
    )

    return (
        cursor.fetchone()[0] > 0
    )


# ============================================================
# GRAVAR RESULTADO FINAL
# ============================================================

def _gravar_item_resultado_final(
    cursor,
    id_inventario: int,
    localizacao: str,
    codigo: str,
    lote: str,
    descricao,
    unidade,
    categoria,
    qtd_estoque: float,
    quantidade_final: float,
    status_final: str,
    origem_quantidade: str,
    rodada_final: int,
    usuario: str
):

    cursor.execute(
        """
        INSERT INTO dbo.InventarioResultadoFinal
        (
            ID_Inventario,
            Localizacao,
            Codigo,
            Lote,
            Descricao,
            Unidade,
            Categoria,
            QtdEstoque,
            QuantidadeFinal,
            StatusFinal,
            OrigemQuantidade,
            ID_DecisaoGestor,
            RodadaFinal,
            UsuarioFinalizacao
        )

        VALUES
        (
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            NULL,
            ?,
            ?
        )
        """,
        (
            id_inventario,
            localizacao,
            codigo,
            lote,
            descricao,
            unidade,
            categoria,
            qtd_estoque,
            quantidade_final,
            status_final,
            origem_quantidade,
            rodada_final,
            usuario
        )
    )


# ============================================================
# FECHAR RECONTAGENS ROTATIVAS RESOLVIDAS NA R2
#
# Regra:
# - somente ocorrência EM_RECONTAGEM;
# - somente decisão RECONTAR ativa da R1;
# - somente item efetivamente recontado na R2;
# - somente quando o resultado final da R2 ficou OK;
# - divergência que persistiu na R2 NÃO é marcada como resolvida.
# ============================================================
# ============================================================
# FECHAR RECONTAGENS ROTATIVAS APÓS R2
#
# Regras:
# - somente ocorrência EM_RECONTAGEM;
# - somente decisão RECONTAR ativa da R1;
# - somente item efetivamente recontado na R2;
#
# Caminho 1:
# R2 terminou OK
# -> RESOLVIDA_RECONTAGEM
# -> decisão CONCLUIDA
#
# Caminho 2:
# R2 continuou divergente
# -> DIVERGENCIA_CONFIRMADA
# -> decisão CONCLUIDA
#
# Importante:
# DIVERGENCIA_CONFIRMADA NÃO é resolução.
# Portanto não preenche TipoResolucao,
# ResolvidoPor ou DataHoraResolucao.
# ============================================================

def _resolver_recontagens_rotativo(
    cursor,
    id_inventario: int,
    id_rodada_r1: int,
    id_rodada_r2: int,
    usuario: str
):

    usuario = (
        _normalizar_texto(usuario)
        or
        "sistema"
    )

    # ========================================================
    # 1. R2 RESOLVEU A DIVERGÊNCIA
    #
    # Resultado final da R2 = OK
    # ========================================================

    cursor.execute(
        """
        UPDATE O

        SET
            O.StatusResolucao = 'RESOLVIDA_RECONTAGEM',

            O.ID_InventarioResolucao = ?,

            O.ID_RodadaResolucao = ?,

            O.TipoResolucao = 'RECONTAGEM',

            O.ObservacaoResolucao =
                'Divergência resolvida após recontagem R2 do inventário rotativo.',

            O.ResolvidoPor = ?,

            O.DataHoraResolucao = SYSDATETIME()

        FROM dbo.OcorrenciasDivergencia O

        INNER JOIN dbo.DecisoesRotativo D
            ON D.ID_DecisaoRotativo =
               O.ID_DecisaoRotativo

        INNER JOIN dbo.InventarioResultadoFinal F
            ON F.ID_Inventario =
               O.ID_Inventario

            AND UPPER(
                LTRIM(
                    RTRIM(F.Localizacao)
                )
            ) =
            UPPER(
                LTRIM(
                    RTRIM(O.Localizacao)
                )
            )

            AND LTRIM(
                RTRIM(F.Codigo)
            ) =
            LTRIM(
                RTRIM(O.Codigo)
            )

            AND ISNULL(
                LTRIM(
                    RTRIM(F.Lote)
                ),
                ''
            ) =
            ISNULL(
                LTRIM(
                    RTRIM(O.Lote)
                ),
                ''
            )

        WHERE
            O.ID_Inventario = ?

            AND O.ID_Rodada = ?

            AND O.StatusResolucao =
                'EM_RECONTAGEM'

            AND D.ID_Inventario = ?

            AND D.ID_Rodada = ?

            AND D.Decisao =
                'RECONTAR'

            AND D.Status =
                'ATIVA'

            AND F.RodadaFinal = 2

            AND F.StatusFinal = 'OK'
        """,
        (
            id_inventario,
            id_rodada_r2,
            usuario,

            id_inventario,
            id_rodada_r1,

            id_inventario,
            id_rodada_r1,
        )
    )

    ocorrencias_resolvidas = int(
        cursor.rowcount or 0
    )

    # ========================================================
    # 2. R2 CONFIRMOU A DIVERGÊNCIA
    #
    # Resultado final da R2 != OK
    #
    # Não é resolução.
    # Apenas encerramos o estado EM_RECONTAGEM.
    # ========================================================

    cursor.execute(
        """
        UPDATE O

        SET
            O.StatusResolucao =
                'DIVERGENCIA_CONFIRMADA',

            O.ID_InventarioResolucao = NULL,

            O.ID_RodadaResolucao = NULL,

            O.TipoResolucao = NULL,

            O.ObservacaoResolucao =
                'Divergência confirmada após recontagem R2 do inventário rotativo.',

            O.ResolvidoPor = NULL,

            O.DataHoraResolucao = NULL

        FROM dbo.OcorrenciasDivergencia O

        INNER JOIN dbo.DecisoesRotativo D
            ON D.ID_DecisaoRotativo =
               O.ID_DecisaoRotativo

        INNER JOIN dbo.InventarioResultadoFinal F
            ON F.ID_Inventario =
               O.ID_Inventario

            AND UPPER(
                LTRIM(
                    RTRIM(F.Localizacao)
                )
            ) =
            UPPER(
                LTRIM(
                    RTRIM(O.Localizacao)
                )
            )

            AND LTRIM(
                RTRIM(F.Codigo)
            ) =
            LTRIM(
                RTRIM(O.Codigo)
            )

            AND ISNULL(
                LTRIM(
                    RTRIM(F.Lote)
                ),
                ''
            ) =
            ISNULL(
                LTRIM(
                    RTRIM(O.Lote)
                ),
                ''
            )

        WHERE
            O.ID_Inventario = ?

            AND O.ID_Rodada = ?

            AND O.StatusResolucao =
                'EM_RECONTAGEM'

            AND D.ID_Inventario = ?

            AND D.ID_Rodada = ?

            AND D.Decisao =
                'RECONTAR'

            AND D.Status =
                'ATIVA'

            AND F.RodadaFinal = 2

            AND F.StatusFinal <> 'OK'
        """,
        (
            id_inventario,
            id_rodada_r1,

            id_inventario,
            id_rodada_r1,
        )
    )

    divergencias_confirmadas = int(
        cursor.rowcount or 0
    )

    # ========================================================
    # 3. CONCLUI TODAS AS DECISÕES RECONTAR DA R1
    #
    # A decisão foi executada nos dois casos:
    #
    # - R2 resolveu;
    # - R2 confirmou a divergência.
    # ========================================================

    cursor.execute(
        """
        UPDATE D

        SET
            D.Status = 'CONCLUIDA'

        FROM dbo.DecisoesRotativo D

        WHERE
            D.ID_Inventario = ?

            AND D.ID_Rodada = ?

            AND D.Decisao =
                'RECONTAR'

            AND D.Status =
                'ATIVA'

            AND EXISTS
            (
                SELECT 1

                FROM dbo.OcorrenciasDivergencia O

                WHERE
                    O.ID_DecisaoRotativo =
                        D.ID_DecisaoRotativo

                    AND O.StatusResolucao IN
                    (
                        'RESOLVIDA_RECONTAGEM',
                        'DIVERGENCIA_CONFIRMADA'
                    )
            )
        """,
        (
            id_inventario,
            id_rodada_r1,
        )
    )

    decisoes_concluidas = int(
        cursor.rowcount or 0
    )

    # ========================================================
    # 4. RETORNO
    # ========================================================

    return {
        "ocorrencias_resolvidas":
            ocorrencias_resolvidas,

        "divergencias_confirmadas":
            divergencias_confirmadas,

        "decisoes_concluidas":
            decisoes_concluidas,
    }
# ============================================================
# ATUALIZAR STATUS DAS DECISÕES NO RETORNO
# ============================================================

def _atualizar_status_decisoes_retorno(
    cursor,
    itens_finais: list
):

    for item in itens_finais:

        decisao = item.get(
            "decisao_rotativa"
        )

        if not decisao:
            continue

        id_decisao = decisao.get(
            "id_decisao_rotativo"
        )

        if not id_decisao:
            continue

        cursor.execute(
            """
            SELECT
                Status

            FROM dbo.DecisoesRotativo

            WHERE ID_DecisaoRotativo = ?
            """,
            id_decisao
        )

        linha = cursor.fetchone()

        if linha:

            decisao["status"] = (
                _normalizar_texto(
                    linha.Status
                )
                .upper()
          )

# ============================================================
# CONSOLIDAR RESULTADO FINAL ROTATIVO PELA R1
#
# Usado quando:
# - inventário é ROTATIVO;
# - R1 foi concluída;
# - não existem itens que precisem seguir para R2;
# - divergências justificadas permanecem como divergência final;
# - não cria R2.
#
# Regra:
# - snapshot é o universo final;
# - quantidade final = quantidade contada na R1;
# - RodadaFinal = 1;
# - item conciliado mantém CONTAGEM_CONCILIADA;
# - divergência justificada mantém rastreabilidade da decisão;
# - não executa fechamento de recontagens, pois R2 não existiu;
# - commit continua sendo responsabilidade do router.
# ============================================================

def consolidar_resultado_final_rotativo_r1(
    cursor,
    id_inventario: int,
    id_rodada_r1: int,
    usuario: str
):

    usuario = (
        _normalizar_texto(usuario)
        or
        "sistema"
    )

    # ========================================================
    # 1. VALIDA INVENTÁRIO
    # ========================================================

    cursor.execute(
        """
        SELECT
            ID_Inventario,
            CodigoInventario,
            Tipo,
            Status,
            RodadaAtual

        FROM dbo.Inventarios

        WHERE ID_Inventario = ?
        """,
        id_inventario
    )

    inventario = cursor.fetchone()

    if not inventario:

                raise NotFoundError(
            "Inventário não encontrado."
        )

    tipo = (
        _normalizar_texto(
            inventario.Tipo
        )
        .upper()
    )

    if tipo != "ROTATIVO":

                raise BusinessRuleViolation(
            "Consolidação final pela R1 disponível somente para inventário ROTATIVO."
        )

    # ========================================================
    # 2. EVITA DUPLICIDADE
    # ========================================================

    if _resultado_final_ja_existe(
        cursor=cursor,
        id_inventario=id_inventario
    ):

                raise BusinessRuleViolation(
            "Este inventário já possui resultado final consolidado."
        )

    # ========================================================
    # 3. SNAPSHOT É O UNIVERSO FINAL
    # ========================================================

    itens_snapshot = (
        _buscar_itens_snapshot(
            cursor=cursor,
            id_inventario=id_inventario
        )
    )

    if not itens_snapshot:

                raise BusinessRuleViolation(
            "O inventário não possui itens no snapshot para consolidação."
        )

    itens_finais = []

    # ========================================================
    # 4. CONSOLIDA ITEM A ITEM PELA R1
    # ========================================================

    for item in itens_snapshot:

        localizacao = (
            item["localizacao"]
        )

        codigo = (
            item["codigo"]
        )

        lote = (
            item["lote"]
        )

        qtd_estoque = float(
            item["qtd_estoque"]
        )

        qtd_r1 = (
            _buscar_quantidade_contada(
                cursor=cursor,
                id_inventario=id_inventario,
                id_rodada=id_rodada_r1,
                localizacao=localizacao,
                codigo=codigo,
                lote=lote
            )
        )

        quantidade_final = qtd_r1
        rodada_final = 1

        status_final = (
            _calcular_status_final(
                qtd_estoque=qtd_estoque,
                quantidade_final=quantidade_final
            )
        )

        # ====================================================
        # DECISÃO ROTATIVA DA R1
        # ====================================================

        decisao_rotativa = (
            _buscar_decisao_rotativa_ativa(
                cursor=cursor,
                id_inventario=id_inventario,
                id_rodada=id_rodada_r1,
                localizacao=localizacao,
                codigo=codigo,
                lote=lote
            )
        )

        # ====================================================
        # ORIGEM DA QUANTIDADE
        #
        # OK:
        #   quantidade conciliada diretamente na R1.
        #
        # Divergência justificada:
        #   quantidade da R1 aceita como resultado final,
        #   preservando a divergência física.
        # ====================================================

        if status_final == "OK":

            origem_quantidade = (
                "CONTAGEM_CONCILIADA"
            )

        elif (
            decisao_rotativa
            and
            _normalizar_texto(
                decisao_rotativa.get(
                    "decisao"
                )
            ).upper()
            ==
            "JUSTIFICAR_DIVERGENCIA"
        ):

            origem_quantidade = (
                "R1_DIVERGENCIA_JUSTIFICADA"
            )

        else:

            # Segurança:
            # este caminho não deveria ser usado para
            # divergência sem tratamento, pois nesse caso
            # deveria existir candidato para R2.
                        raise BusinessRuleViolation(
                "Existe divergência da R1 sem tratamento válido para encerramento antecipado. Localização: {localizacao}; Código: {codigo}; Lote: {lote}."
            )

        # ====================================================
        # GRAVA RESULTADO FINAL
        # ====================================================

        _gravar_item_resultado_final(
            cursor=cursor,
            id_inventario=id_inventario,
            localizacao=localizacao,
            codigo=codigo,
            lote=lote,
            descricao=item.get(
                "descricao"
            ),
            unidade=item.get(
                "unidade"
            ),
            categoria=item.get(
                "categoria"
            ),
            qtd_estoque=qtd_estoque,
            quantidade_final=quantidade_final,
            status_final=status_final,
            origem_quantidade=origem_quantidade,
            rodada_final=rodada_final,
            usuario=usuario
        )

        itens_finais.append(
            {
                "localizacao":
                    localizacao,

                "codigo":
                    codigo,

                "lote":
                    lote,

                "qtd_estoque":
                    qtd_estoque,

                "qtd_r1":
                    qtd_r1,

                "qtd_r2":
                    None,

                "quantidade_final":
                    quantidade_final,

                "diferenca_final":
                    (
                        quantidade_final
                        -
                        qtd_estoque
                    ),

                "status_final":
                    status_final,

                "origem_quantidade":
                    origem_quantidade,

                "rodada_final":
                    1,

                "decisao_rotativa":
                    decisao_rotativa
            }
        )

    # ========================================================
    # 5. SEGURANÇA DE CONSOLIDAÇÃO
    # ========================================================

    cursor.execute(
        """
        SELECT COUNT(*)

        FROM dbo.InventarioResultadoFinal

        WHERE ID_Inventario = ?
        """,
        id_inventario
    )

    total_gravado = (
        cursor.fetchone()[0]
    )

    if total_gravado != len(
        itens_finais
    ):

        raise HTTPException(
            status_code=500,
            detail=(
                "Falha na consolidação do resultado final "
                "do inventário ROTATIVO pela R1. "
                f"Itens esperados: {len(itens_finais)}. "
                f"Itens gravados: {total_gravado}."
            )
        )

    # ========================================================
    # 6. CONCLUI DECISÕES DE JUSTIFICATIVA
    #
    # A justificativa já foi consumida pelo resultado final.
    # Não existe R2 para executar.
    # ========================================================

    cursor.execute(
        """
        UPDATE dbo.DecisoesRotativo

        SET
            Status = 'CONCLUIDA'

        WHERE
            ID_Inventario = ?
            AND ID_Rodada = ?
            AND Decisao = 'JUSTIFICAR_DIVERGENCIA'
            AND Status = 'ATIVA'
        """,
        (
            id_inventario,
            id_rodada_r1
        )
    )

    decisoes_justificadas_concluidas = int(
        cursor.rowcount or 0
    )

    # ========================================================
    # 7. ATUALIZA STATUS DAS DECISÕES NO RETORNO
    # ========================================================

    _atualizar_status_decisoes_retorno(
        cursor=cursor,
        itens_finais=itens_finais
    )

    # ========================================================
    # 8. RESUMO
    # ========================================================

    total_ok = sum(
        1
        for item in itens_finais
        if item["status_final"] == "OK"
    )

    total_falta = sum(
        1
        for item in itens_finais
        if item["status_final"] == "FALTA"
    )

    total_sobra = sum(
        1
        for item in itens_finais
        if item["status_final"] == "SOBRA"
    )

    total_justificados = sum(
        1
        for item in itens_finais
        if (
            item.get("decisao_rotativa")
            and
            _normalizar_texto(
                item["decisao_rotativa"].get(
                    "decisao"
                )
            ).upper()
            ==
            "JUSTIFICAR_DIVERGENCIA"
        )
    )

    # ========================================================
    # 9. RETORNO
    # ========================================================

    return {
        "sucesso":
            True,

        "id_inventario":
            id_inventario,

        "codigo_inventario":
            inventario.CodigoInventario,

        "rodada_final":
            1,

        "encerramento":
            "R1_SEM_RECONTAGEM",

        "total_itens":
            len(
                itens_finais
            ),

        "resumo": {
            "ok":
                total_ok,

            "faltas":
                total_falta,

            "sobras":
                total_sobra,

            "divergencias_justificadas":
                total_justificados
        },

        "decisoes_justificadas_concluidas":
            decisoes_justificadas_concluidas,

        "itens":
            itens_finais
    }
# ============================================================
# CONSOLIDAR RESULTADO FINAL ROTATIVO
# ============================================================

def consolidar_resultado_final_rotativo(
    cursor,
    id_inventario: int,
    id_rodada_r1: int,
    id_rodada_r2: int,
    usuario: str
):

    usuario = (
        _normalizar_texto(
            usuario
        )
        or
        "sistema"
    )

    # ========================================================
    # 1. VALIDA INVENTÁRIO
    # ========================================================

    cursor.execute(
        """
        SELECT
            ID_Inventario,
            CodigoInventario,
            Tipo,
            Status,
            RodadaAtual

        FROM dbo.Inventarios

        WHERE ID_Inventario = ?
        """,
        id_inventario
    )

    inventario = cursor.fetchone()

    if not inventario:

                raise NotFoundError(
            "Inventário não encontrado."
        )

    tipo = (
        _normalizar_texto(
            inventario.Tipo
        )
        .upper()
    )

    if tipo != "ROTATIVO":

                raise BusinessRuleViolation(
            "Consolidação final ROTATIVO disponível somente para inventário ROTATIVO."
        )

    # ========================================================
    # 2. EVITA DUPLICIDADE
    # ========================================================

    if _resultado_final_ja_existe(
        cursor=cursor,
        id_inventario=id_inventario
    ):

                raise BusinessRuleViolation(
            "Este inventário já possui resultado final consolidado."
        )

    # ========================================================
    # 3. SNAPSHOT É O UNIVERSO FINAL
    # ========================================================

    itens_snapshot = (
        _buscar_itens_snapshot(
            cursor=cursor,
            id_inventario=id_inventario
        )
    )

    if not itens_snapshot:

                raise BusinessRuleViolation(
            "O inventário não possui itens no snapshot para consolidação."
        )

    itens_finais = []

    # ========================================================
    # 4. CONSOLIDA ITEM A ITEM
    # ========================================================

    for item in itens_snapshot:

        localizacao = (
            item["localizacao"]
        )

        codigo = (
            item["codigo"]
        )

        lote = (
            item["lote"]
        )

        qtd_estoque = float(
            item["qtd_estoque"]
        )

        qtd_r1 = (
            _buscar_quantidade_contada(
                cursor=cursor,
                id_inventario=id_inventario,
                id_rodada=id_rodada_r1,
                localizacao=localizacao,
                codigo=codigo,
                lote=lote
            )
        )

        participou_r2 = (
            _item_participou_r2(
                cursor=cursor,
                id_inventario=id_inventario,
                id_rodada_r2=id_rodada_r2,
                codigo=codigo,
                lote=lote
            )
        )

        decisao_rotativa = None

        if participou_r2:

            qtd_r2 = (
                _buscar_quantidade_contada(
                    cursor=cursor,
                    id_inventario=id_inventario,
                    id_rodada=id_rodada_r2,
                    localizacao=localizacao,
                    codigo=codigo,
                    lote=lote
                )
            )

            quantidade_final = qtd_r2
            rodada_final = 2

            decisao_rotativa = (
                _buscar_decisao_rotativa_ativa(
                    cursor=cursor,
                    id_inventario=id_inventario,
                    id_rodada=id_rodada_r1,
                    localizacao=localizacao,
                    codigo=codigo,
                    lote=lote
                )
            )

            if decisao_rotativa:

                if (
                    _normalizar_texto(
                        decisao_rotativa.get(
                            "decisao"
                        )
                    )
                    .upper()
                    ==
                    "JUSTIFICAR_DIVERGENCIA"
                ):
                    origem_quantidade = (
                        "CONTAGEM_ROTATIVO"
                    )
                else:
                    origem_quantidade = (
                        "CONTAGEM_ROTATIVO"
                    )

            elif abs(
                qtd_r2
                -
                qtd_estoque
            ) <= 0.0001:

                origem_quantidade = (
                    "CONTAGEM_ROTATIVO"
                )

            else:

                origem_quantidade = (
                    "CONTAGEM_ROTATIVO"
                )

        else:

            qtd_r2 = None
            quantidade_final = qtd_r1
            rodada_final = 1
            origem_quantidade = (
                "CONTAGEM_CONCILIADA"
            )

        status_final = (
            _calcular_status_final(
                qtd_estoque=qtd_estoque,
                quantidade_final=(
                    quantidade_final
                )
            )
        )

        _gravar_item_resultado_final(
            cursor=cursor,
            id_inventario=id_inventario,
            localizacao=localizacao,
            codigo=codigo,
            lote=lote,
            descricao=item.get(
                "descricao"
            ),
            unidade=item.get(
                "unidade"
            ),
            categoria=item.get(
                "categoria"
            ),
            qtd_estoque=qtd_estoque,
            quantidade_final=(
                quantidade_final
            ),
            status_final=status_final,
            origem_quantidade=(
                origem_quantidade
            ),
            rodada_final=(
                rodada_final
            ),
            usuario=usuario
        )

        itens_finais.append(
            {
                "localizacao":
                    localizacao,

                "codigo":
                    codigo,

                "lote":
                    lote,

                "qtd_estoque":
                    qtd_estoque,

                "qtd_r1":
                    qtd_r1,

                "qtd_r2":
                    qtd_r2,

                "quantidade_final":
                    quantidade_final,

                "diferenca_final":
                    (
                        quantidade_final
                        -
                        qtd_estoque
                    ),

                "status_final":
                    status_final,

                "origem_quantidade":
                    origem_quantidade,

                "rodada_final":
                    rodada_final,

                "decisao_rotativa":
                    decisao_rotativa
            }
        )

    # ========================================================
    # 5. SEGURANÇA DE CONSOLIDAÇÃO
    # ========================================================

    cursor.execute(
        """
        SELECT COUNT(*)

        FROM dbo.InventarioResultadoFinal

        WHERE ID_Inventario = ?
        """,
        id_inventario
    )

    total_gravado = (
        cursor.fetchone()[0]
    )

    if total_gravado != len(
        itens_finais
    ):

        raise HTTPException(
            status_code=500,
            detail=(
                "Falha na consolidação do resultado final "
                "do inventário ROTATIVO. "
                f"Itens esperados: {len(itens_finais)}. "
                f"Itens gravados: {total_gravado}."
            )
        )

    # ========================================================
    # 6. FECHA RECONTAGENS RESOLVIDAS NA R2
    # ========================================================

    fechamento_recontagens = (
        _resolver_recontagens_rotativo(
            cursor=cursor,
            id_inventario=id_inventario,
            id_rodada_r1=id_rodada_r1,
            id_rodada_r2=id_rodada_r2,
            usuario=usuario
        )
    )
    # ========================================================
    # ATUALIZA STATUS DAS DECISÕES APÓS O FECHAMENTO
    # ========================================================

    _atualizar_status_decisoes_retorno(
        cursor=cursor,
        itens_finais=itens_finais
    )
    # ========================================================
    # 7. RESUMO
    # ========================================================

    total_ok = sum(
        1
        for item in itens_finais
        if item["status_final"] == "OK"
    )

    total_falta = sum(
        1
        for item in itens_finais
        if item["status_final"] == "FALTA"
    )

    total_sobra = sum(
        1
        for item in itens_finais
        if item["status_final"] == "SOBRA"
    )

    total_justificados = sum(
        1
        for item in itens_finais
        if (
            item.get("decisao_rotativa")
            and
            _normalizar_texto(
                item["decisao_rotativa"].get("decisao")
            ).upper()
            == "JUSTIFICAR_DIVERGENCIA"
        )
    )

    return {
        "sucesso":
            True,

        "id_inventario":
            id_inventario,

        "codigo_inventario":
            inventario.CodigoInventario,

        "total_itens":
            len(
                itens_finais
            ),

        "resumo": {
            "ok":
                total_ok,

            "faltas":
                total_falta,

            "sobras":
                total_sobra,

            "divergencias_justificadas":
                total_justificados
        },

        "fechamento_recontagens":
            fechamento_recontagens,

        "itens":
            itens_finais
    }


# ============================================================
# FINALIZAR INVENTÁRIO ROTATIVO
#
# Interface pública usada por routers/finalizacao.py
# ============================================================

def finalizar_inventario_rotativo(
    cursor,
    id_inventario: int,
    usuario: str
):

    usuario = (
        _normalizar_texto(usuario)
        or
        "sistema"
    )

    cursor.execute(
        """
        SELECT
            ID_Inventario,
            CodigoInventario,
            Tipo,
            Status,
            RodadaAtual
        FROM dbo.Inventarios
        WHERE ID_Inventario = ?
        """,
        id_inventario
    )

    inventario = cursor.fetchone()

    if not inventario:
                raise NotFoundError(
            "Inventário não encontrado."
        )

    tipo = _normalizar_texto(
        inventario.Tipo
    ).upper()

    if tipo != "ROTATIVO":
                raise BusinessRuleViolation(
            "Finalização disponível somente para inventário ROTATIVO."
        )

    status = _normalizar_texto(
        inventario.Status
    ).upper()

    if status == "FINALIZADO":
                raise BusinessRuleViolation(
            "Este inventário já está finalizado."
        )

    if status == "CANCELADO":
                raise BusinessRuleViolation(
            "Inventário cancelado não pode ser finalizado."
        )

    cursor.execute(
        """
        SELECT
            ID_Rodada,
            NumeroRodada,
            Status
        FROM dbo.RodadasInventario
        WHERE
            ID_Inventario = ?
            AND NumeroRodada IN (1, 2)
        ORDER BY NumeroRodada
        """,
        id_inventario
    )

    rodadas = {
        int(linha.NumeroRodada): linha
        for linha in cursor.fetchall()
    }

    r1 = rodadas.get(1)
    r2 = rodadas.get(2)

    if not r1:
                raise BusinessRuleViolation(
            "Não foi possível localizar a R1 do inventário ROTATIVO."
        )

    if not r2:
                raise BusinessRuleViolation(
            "A R2 do inventário ROTATIVO ainda não foi criada."
        )

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM dbo.SessoesContagem
        WHERE
            ID_Inventario = ?
            AND ID_Rodada = ?
            AND Status = 'ABERTA'
        """,
        (
            id_inventario,
            r2.ID_Rodada
        )
    )

    sessoes_abertas = int(
        cursor.fetchone()[0]
    )

    if sessoes_abertas > 0:
                raise BusinessRuleViolation(
            "Existem sessões abertas na R2. Encerre todas antes de finalizar."
        )

    resultado_final = (
        consolidar_resultado_final_rotativo(
            cursor=cursor,
            id_inventario=id_inventario,
            id_rodada_r1=r1.ID_Rodada,
            id_rodada_r2=r2.ID_Rodada,
            usuario=usuario
        )
    )

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
            AND Status = 'ABERTA'
        """,
        id_inventario
    )

    cursor.execute(
        """
        UPDATE dbo.Inventarios
        SET
            Status = 'FINALIZADO',
            RodadaAtual = 2,
            DataHoraFim = COALESCE(
                DataHoraFim,
                SYSDATETIME()
            ),
            FinalizadoPor = ?
        WHERE
            ID_Inventario = ?
            AND ISNULL(Status, '') <> 'FINALIZADO'
        """,
        (
            usuario,
            id_inventario
        )
    )

    if cursor.rowcount == 0:
                raise BusinessRuleViolation(
            "Não foi possível finalizar o inventário ROTATIVO."
        )

    return {
        "sucesso": True,
        "id_inventario": id_inventario,
        "codigo_inventario": inventario.CodigoInventario,
        "tipo_inventario": "ROTATIVO",
        "status": "FINALIZADO",
        "finalizado_por": usuario,
        "rodada_final": 2,
        "resultado_final": resultado_final,
        "mensagem": (
            "Resultado final consolidado e inventário "
            "ROTATIVO finalizado com sucesso."
        )
    }
