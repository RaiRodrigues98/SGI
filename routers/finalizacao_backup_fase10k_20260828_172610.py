from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)

from infrastructure.database.unit_of_work import SqlServerUnitOfWork

from dependencies.auth import (
    exigir_permissao,
)

from schemas.finalizacao import (
    FinalizarInventarioEntrada,
)

from services.finalizacao_inventario import (
    finalizar_inventario_oficial,
)

from services.finalizacao_rotativo import (
    finalizar_inventario_rotativo,
)


router = APIRouter(
    tags=["Finalização"]
)


# ============================================================
# NORMALIZAR TIPO
# ============================================================

def _normalizar_tipo(valor):

    if valor is None:
        return ""

    return (
        str(valor)
        .strip()
        .upper()
    )


# ============================================================
# RESULTADO FINAL JÁ CONSOLIDADO
#
# Usado para tornar o endpoint de finalização idempotente:
# se o inventário já estiver FINALIZADO, devolvemos o resultado
# existente em vez de responder erro.
# ============================================================

def _buscar_resultado_final_existente(
    cursor,
    id_inventario: int
):

    cursor.execute(
        """
        SELECT
            ID_Inventario,
            CodigoInventario,
            Tipo,
            Status,
            RodadaAtual,
            DataHoraFim,
            FinalizadoPor

        FROM dbo.Inventarios

        WHERE ID_Inventario = ?
        """,
        id_inventario
    )

    inventario = cursor.fetchone()

    if not inventario:
        return None

    cursor.execute(
        """
        SELECT
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
            UsuarioFinalizacao,
            DataHoraFinalizacao

        FROM dbo.InventarioResultadoFinal

        WHERE ID_Inventario = ?

        ORDER BY
            Codigo,
            Lote,
            Localizacao
        """,
        id_inventario
    )

    linhas = cursor.fetchall()

    if not linhas:
        return None

    itens = []

    for linha in linhas:
        qtd_estoque = float(
            linha.QtdEstoque or 0
        )
        quantidade_final = float(
            linha.QuantidadeFinal or 0
        )

        itens.append(
            {
                "localizacao":
                    linha.Localizacao,

                "codigo":
                    linha.Codigo,

                "lote":
                    linha.Lote,

                "descricao":
                    linha.Descricao,

                "unidade":
                    linha.Unidade,

                "categoria":
                    linha.Categoria,

                "qtd_estoque":
                    qtd_estoque,

                "quantidade_final":
                    quantidade_final,

                "diferenca_final":
                    (
                        quantidade_final
                        - qtd_estoque
                    ),

                "status_final":
                    linha.StatusFinal,

                "origem_quantidade":
                    linha.OrigemQuantidade,

                "id_decisao_gestor":
                    linha.ID_DecisaoGestor,

                "rodada_final":
                    linha.RodadaFinal,

                "usuario_finalizacao":
                    linha.UsuarioFinalizacao,

                "data_hora_finalizacao":
                    linha.DataHoraFinalizacao,
            }
        )

    total_ok = sum(
        1
        for item in itens
        if item["status_final"] == "OK"
    )

    total_faltas = sum(
        1
        for item in itens
        if item["status_final"] == "FALTA"
    )

    total_sobras = sum(
        1
        for item in itens
        if item["status_final"] == "SOBRA"
    )

    total_divergencias = sum(
        1
        for item in itens
        if (
            item["status_final"]
            == "DIVERGÊNCIA"
        )
    )

    return {
        "sucesso":
            True,

        "idempotente":
            True,

        "id_inventario":
            inventario.ID_Inventario,

        "codigo_inventario":
            inventario.CodigoInventario,

        "tipo_inventario":
            inventario.Tipo,

        "status":
            inventario.Status,

        "finalizado_por":
            inventario.FinalizadoPor,

        "data_hora_finalizacao":
            inventario.DataHoraFim,

        "rodada_final":
            inventario.RodadaAtual,

        "resumo_final": {
            "total_itens":
                len(itens),

            "ok":
                total_ok,

            "faltas":
                total_faltas,

            "sobras":
                total_sobras,

            "divergencias":
                total_divergencias,
        },

        "itens":
            itens,

        "mensagem":
            (
                "Inventário já estava finalizado. "
                "Resultado final existente retornado."
            )
    }


# ============================================================
# FINALIZAR INVENTÁRIO
#
# Permissão:
# INVENTARIO_FINALIZAR
#
# OFICIAL
#   → finalizar_inventario_oficial()
#
# ROTATIVO
#   → finalizar_inventario_rotativo()
#
# O commit permanece responsabilidade deste router.
# ============================================================

@router.post(
    "/inventarios/{id_inventario}/finalizar"
)
def finalizar_inventario(
    id_inventario: int,
    dados: FinalizarInventarioEntrada,
    usuario_atual=Depends(
        exigir_permissao(
            "INVENTARIO_FINALIZAR"
        )
    )
):

    # ========================================================
    # 1. VALIDA ID
    # ========================================================

    if id_inventario <= 0:

        raise HTTPException(
            status_code=400,
            detail="Inventário inválido."
        )

    # ========================================================
    # 2. USUÁRIO AUTENTICADO
    #
    # Auditoria vem do JWT. Não confiamos no usuário enviado
    # pelo frontend.
    # ========================================================

    usuario = (
        str(usuario_atual["login"]).strip()
    )


    uow = None
    cursor = None

    try:

        uow = SqlServerUnitOfWork()
        uow.open()
        cursor = uow.cursor

        # ====================================================
        # 3. LOCK TRANSACIONAL DE FINALIZAÇÃO
        #
        # Garante que apenas uma requisição possa finalizar
        # este inventário por vez.
        #
        # O lock pertence à transação e será liberado
        # automaticamente no COMMIT ou ROLLBACK deste router.
        # ====================================================

        recurso_lock = (
            f"SGI:INVENTARIO:{id_inventario}:FINALIZAR"
        )

        cursor.execute(
            """
            DECLARE @resultado INT;

            EXEC @resultado = sys.sp_getapplock
                @Resource = ?,
                @LockMode = 'Exclusive',
                @LockOwner = 'Transaction',
                @LockTimeout = 10000;

            SELECT @resultado AS ResultadoLock;
            """,
            recurso_lock
        )

        lock_resultado = cursor.fetchone()

        codigo_lock = (
            int(lock_resultado.ResultadoLock)
            if lock_resultado
            else -999
        )

        if codigo_lock < 0:

            if codigo_lock == -1:
                detalhe_lock = "tempo limite excedido"
            elif codigo_lock == -2:
                detalhe_lock = "solicitação cancelada"
            elif codigo_lock == -3:
                detalhe_lock = "deadlock"
            else:
                detalhe_lock = f"código {codigo_lock}"

            raise HTTPException(
                status_code=409,
                detail=(
                    "Não foi possível reservar a finalização "
                    "do inventário porque outra operação está "
                    f"em andamento ({detalhe_lock}). "
                    "Tente novamente."
                )
            )

        # ====================================================
        # 4. BUSCA INVENTÁRIO
        #
        # Fazemos a identificação do tipo no router para
        # direcionar ao service correto.
        # ====================================================

        cursor.execute(
            """
            SELECT
                ID_Inventario,
                CodigoInventario,
                Tipo,
                Status

            FROM dbo.Inventarios

            WHERE ID_Inventario = ?
            """,
            id_inventario
        )

        inventario = cursor.fetchone()

        if not inventario:

            raise HTTPException(
                status_code=404,
                detail="Inventário não encontrado."
            )

        tipo = _normalizar_tipo(
            inventario.Tipo
        )

        # ====================================================
        # 5. VALIDA TIPO
        # ====================================================

        if tipo not in (
            "OFICIAL",
            "ROTATIVO"
        ):

            raise HTTPException(
                status_code=400,
                detail=(
                    "Tipo de inventário não suportado "
                    "para finalização: "
                    f"{inventario.Tipo}"
                )
            )

        # ====================================================
        # 6. EVITA CHAMAR SERVICE SE JÁ FINALIZADO
        #
        # Os services também validam isso.
        # Mantemos aqui para resposta mais rápida.
        # ====================================================

        status_inventario = (
            _normalizar_tipo(
                inventario.Status
            )
        )

        if status_inventario == "FINALIZADO":

            resultado_existente = (
                _buscar_resultado_final_existente(
                    cursor=cursor,
                    id_inventario=id_inventario
                )
            )

            if not resultado_existente:

                raise HTTPException(
                    status_code=409,
                    detail=(
                        "O inventário está marcado como "
                        "FINALIZADO, mas o resultado final "
                        "consolidado não foi encontrado."
                    )
                )

            uow.rollback()

            return resultado_existente

        if status_inventario == "CANCELADO":

            raise HTTPException(
                status_code=400,
                detail=(
                    "Inventário cancelado não pode "
                    "ser finalizado."
                )
            )

        # ====================================================
        # 7. DIRECIONA PARA O MOTOR CORRETO
        # ====================================================

        if tipo == "OFICIAL":

            resultado = (
                finalizar_inventario_oficial(
                    cursor=cursor,
                    id_inventario=id_inventario,
                    usuario=usuario
                )
            )

        else:

            resultado = (
                finalizar_inventario_rotativo(
                    cursor=cursor,
                    id_inventario=id_inventario,
                    usuario=usuario
                )
            )

        # ====================================================
        # 8. COMMIT
        #
        # Nenhum dos services deve executar commit.
        #
        # Se qualquer operação acima falhar, cairá no
        # rollback e nenhuma finalização parcial ficará
        # gravada.
        # ====================================================

        uow.commit()

        return resultado

    except HTTPException:

        if uow:
            uow.rollback()

        raise

    except Exception as erro:

        if uow:
            uow.rollback()

        raise HTTPException(
            status_code=500,
            detail=str(erro)
        )

    finally:

        if uow:
            uow.close()