from domain.exceptions import BusinessRuleViolation, NotFoundError
from application.exceptions import ApplicationError

from services.analise_gestor import (
    analisar_inventario_gestor,
)


# ============================================================
# FINALIZAÇÃO GERENCIAL DO INVENTÁRIO OFICIAL
#
# Fluxo:
#
# 1. valida inventário
# 2. valida sessões abertas
# 3. executa análise gerencial
# 4. valida decisões pendentes
# 5. consolida resultado final
# 6. grava dbo.InventarioResultadoFinal
# 7. finaliza rodadas
# 8. finaliza inventário
#
# IMPORTANTE:
# o commit permanece responsabilidade do router.
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


# ============================================================
# CALCULAR STATUS FINAL
# ============================================================

def _calcular_status_final(
    qtd_estoque: float,
    quantidade_final: float
):
    """
    Status FINAL do inventário.

    Regra:
    - diferença = QuantidadeFinal - QtdEstoque
    - 0  -> OK
    - <0 -> FALTA
    - >0 -> SOBRA

    DIVERGÊNCIA continua sendo um status de análise/rodada,
    mas não é utilizado no resultado final consolidado.
    """

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
# VERIFICAR SE RESULTADO FINAL JÁ EXISTE
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
# GRAVAR ITEM DO RESULTADO FINAL
# ============================================================

def _gravar_item_resultado_final(
    cursor,
    id_inventario: int,
    codigo: str,
    lote: str,
    descricao,
    unidade,
    categoria,
    qtd_estoque: float,
    quantidade_final: float,
    status_final: str,
    origem_quantidade: str,
    id_decisao_gestor,
    rodada_final,
    usuario: str
):

    cursor.execute(
        """
        INSERT INTO dbo.InventarioResultadoFinal
        (
            ID_Inventario,
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
            ?,
            ?
        )
        """,
        (
            id_inventario,
            codigo,
            lote,
            descricao,
            unidade,
            categoria,
            qtd_estoque,
            quantidade_final,
            status_final,
            origem_quantidade,
            id_decisao_gestor,
            rodada_final,
            usuario
        )
    )


# ============================================================
# FINALIZAR INVENTÁRIO
# ============================================================

def finalizar_inventario_oficial(
    cursor,
    id_inventario: int,
    usuario: str
):

    usuario = _normalizar_texto(
        usuario
    )

    if not usuario:

                raise BusinessRuleViolation(
            "Usuário responsável pela finalização é obrigatório."
        )

    # ========================================================
    # 1. INVENTÁRIO
    # ========================================================

    cursor.execute(
        """
        SELECT
            ID_Inventario,
            CodigoInventario,
            Tipo,
            ClienteId,
            RodadaAtual,
            Status

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

    tipo_inventario = (
        str(
            inventario.Tipo
        )
        .strip()
        .upper()
    )

    if tipo_inventario != "OFICIAL":

                raise BusinessRuleViolation(
            "Finalização gerencial disponível somente para inventário OFICIAL."
        )

    if inventario.Status == "FINALIZADO":

                raise BusinessRuleViolation(
            "Este inventário já está finalizado."
        )

    if inventario.Status == "CANCELADO":

                raise BusinessRuleViolation(
            "Inventário cancelado não pode ser finalizado."
        )

    # ========================================================
    # 2. NÃO PERMITE SESSÕES ABERTAS
    # ========================================================

    cursor.execute(
        """
        SELECT COUNT(*)

        FROM dbo.SessoesContagem

        WHERE
            ID_Inventario = ?
            AND Status = 'ABERTA'
        """,
        id_inventario
    )

    sessoes_abertas = (
        cursor.fetchone()[0]
    )

    if sessoes_abertas > 0:

                raise BusinessRuleViolation(
            "Existem sessões de contagem abertas. Encerre todas antes de finalizar o inventário."
        )

    # ========================================================
    # 3. EVITA RESULTADO FINAL DUPLICADO
    # ========================================================

    if _resultado_final_ja_existe(
        cursor=cursor,
        id_inventario=id_inventario
    ):

                raise BusinessRuleViolation(
            "Este inventário já possui resultado final consolidado."
        )

    # ========================================================
    # 4. ANÁLISE GERENCIAL
    # ========================================================

    analise = (
        analisar_inventario_gestor(
            cursor=cursor,
            id_inventario=id_inventario
        )
    )

    resumo = (
        analise.get(
            "resumo",
            {}
        )
    )

    itens_sem_decisao = int(
        resumo.get(
            "itens_sem_decisao",
            0
        )
    )

    nova_recontagem = int(
        resumo.get(
            "nova_recontagem",
            0
        )
    )

    pode_finalizar = bool(
        analise.get(
            "pode_finalizar_inventario",
            False
        )
    )

    operacao_concluida = bool(
        analise.get(
            "operacao_concluida",
            False
        )
    )

    rodadas_nao_finalizadas = (
        analise.get(
            "rodadas_nao_finalizadas"
        )
        or []
    )

    # ========================================================
    # 5. TRAVAS GERENCIAIS E OPERACIONAIS
    # ========================================================

    if not operacao_concluida:

        total_rodadas_nao_finalizadas = len(
            rodadas_nao_finalizadas
        )

        if total_rodadas_nao_finalizadas > 0:

            raise BusinessRuleViolation(
                "A opera??o do invent?rio ainda n?o foi "
                "conclu?da. "
                f"Existem {total_rodadas_nao_finalizadas} "
                "rodada(s) n?o finalizada(s)."
            )

        raise BusinessRuleViolation(
            "A opera??o do invent?rio ainda n?o foi "
            "conclu?da."
        )

    if itens_sem_decisao > 0:

        raise BusinessRuleViolation(
            f"Ainda existem {itens_sem_decisao} "
            "item(ns) sem decis?o gerencial."
        )

    if nova_recontagem > 0:

        raise BusinessRuleViolation(
            f"Existem {nova_recontagem} item(ns) "
            "marcados para NOVA_RECONTAGEM."
        )

    if not pode_finalizar:

        raise BusinessRuleViolation(
            "O invent?rio ainda n?o atende aos "
            "crit?rios de finaliza??o."
        )

    # ========================================================
    # 6. CONSOLIDA ITENS FINAIS
    # ========================================================

    itens_finais = []

    for item in analise["itens"]:

        codigo = _normalizar_texto(
            item["codigo"]
        )

        lote = _normalizar_lote(
            item["lote"]
        )

        qtd_estoque = float(
            item["qtd_estoque"]
        )

        quantidade_final = (
            item.get(
                "quantidade_final_gerencial"
            )
        )

        if quantidade_final is None:

                        raise BusinessRuleViolation(
                f"O item {codigo} | {lote} não possui quantidade final gerencial definida."
            )

        quantidade_final = float(
            quantidade_final
        )

        situacao_gerencial = (
            item.get(
                "situacao_gerencial"
            )
        )

        decisao_gestor = (
            item.get(
                "decisao_gestor",
                {}
            )
        )

        # ====================================================
        # ORIGEM DA QUANTIDADE FINAL
        # ====================================================

        if (
            situacao_gerencial
            == "NAO_NECESSITA_DECISAO"
        ):

            origem_quantidade = (
                "CONTAGEM_CONCILIADA"
            )

            id_decisao_gestor = None

        elif (
            situacao_gerencial
            == "RESOLVIDO_ESTOQUE"
        ):

            origem_quantidade = (
                "ACEITAR_ESTOQUE"
            )

            id_decisao_gestor = (
                decisao_gestor.get(
                    "id_decisao"
                )
            )

        elif (
            situacao_gerencial
            == "RESOLVIDO_CONTAGEM"
        ):

            origem_quantidade = (
                "ACEITAR_CONTAGEM"
            )

            id_decisao_gestor = (
                decisao_gestor.get(
                    "id_decisao"
                )
            )

        else:

                        raise BusinessRuleViolation(
                f"Situação gerencial inválida para finalização do item {codigo} | {lote}: {situacao_gerencial}."
            )

        # ====================================================
        # STATUS FINAL
        # ====================================================

        status_final = (
            _calcular_status_final(
                qtd_estoque=qtd_estoque,
                quantidade_final=quantidade_final
            )
        )

        # ====================================================
        # RODADA FINAL
        #
        # É a última rodada em que o item participou.
        # ====================================================

        rodada_final = (
            item.get(
                "ultima_rodada_participada"
            )
        )

        # ====================================================
        # GRAVA RESULTADO FINAL
        # ====================================================

        _gravar_item_resultado_final(
            cursor=cursor,

            id_inventario=id_inventario,

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

            origem_quantidade=(
                origem_quantidade
            ),

            id_decisao_gestor=(
                id_decisao_gestor
            ),

            rodada_final=(
                rodada_final
            ),

            usuario=usuario
        )

        itens_finais.append(
            {
                "codigo":
                    codigo,

                "lote":
                    lote,

                "qtd_estoque":
                    qtd_estoque,

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

                "id_decisao_gestor":
                    id_decisao_gestor,

                "rodada_final":
                    rodada_final
            }
        )

    # ========================================================
    # 7. SEGURANÇA:
    # CONFIRMA QUANTIDADE GRAVADA
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

        raise ApplicationError(
    "Falha na consolidação do resultado final. "
    f"Itens esperados: {len(itens_finais)}. "
    f"Itens gravados: {total_gravado}."
)
           # ========================================================
    # 8. FINALIZA RODADAS
    # ========================================================

    cursor.execute(
        """
        UPDATE dbo.RodadasInventario

        SET
            Status = 'FINALIZADA',
            DataHoraFim = SYSDATETIME()

        WHERE
            ID_Inventario = ?
            AND Status = 'ABERTA'
        """,
        id_inventario
    )

    # ========================================================
    # 9. FINALIZA INVENTÁRIO
    # ========================================================

    cursor.execute(
        """
        UPDATE dbo.Inventarios

        SET
            Status = 'FINALIZADO',
            DataHoraFim = SYSDATETIME(),
            FinalizadoPor = ?

        WHERE
            ID_Inventario = ?
            AND Status <> 'FINALIZADO'
        """,
        (
            usuario,
            id_inventario
        )
    )

    if cursor.rowcount == 0:

                raise BusinessRuleViolation(
            "Não foi possível atualizar o status do inventário."
        )

    # ========================================================
    # 10. RESUMO FINAL
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

    total_divergencia = sum(
        1
        for item in itens_finais
        if item["status_final"] == "DIVERGÊNCIA"
    )

    # ========================================================
    # 11. RETORNO
    # ========================================================

    return {
        "sucesso": True,

        "id_inventario":
            inventario.ID_Inventario,

        "codigo_inventario":
            inventario.CodigoInventario,

        "status":
            "FINALIZADO",

        "finalizado_por":
            usuario,

        "rodada_final":
            inventario.RodadaAtual,

        "resumo_final": {
            "total_itens":
                len(itens_finais),

            "ok":
                total_ok,

            "faltas":
                total_falta,

            "sobras":
                total_sobra,

            "divergencias":
                total_divergencia
        },

        "itens":
            itens_finais,

        "mensagem": (
            "Resultado final consolidado e "
            "inventário finalizado com sucesso."
        )
    }
