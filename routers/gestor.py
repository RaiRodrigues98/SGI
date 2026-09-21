from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)

from infrastructure.database.unit_of_work import SqlServerUnitOfWork

from dependencies.auth import (
    exigir_permissao,
)

from schemas.gestor import (
    DecisaoGestorEntrada,
)


from services.notificacoes import (
    criar_por_permissao,
)


router = APIRouter(
    tags=["Gestor"]
)


DECISOES_VALIDAS = (
    "ACEITAR_ESTOQUE",
    "ACEITAR_CONTAGEM",
    "NOVA_RECONTAGEM",
)


# ============================================================
# REGISTRAR DECISÃO DO GESTOR
# ============================================================

@router.post(
    "/inventarios/{id_inventario}/decisoes-gestor"
)
def registrar_decisao_gestor(
    id_inventario: int,
    dados: DecisaoGestorEntrada,
    usuario_atual=Depends(
        exigir_permissao(
            "GESTOR_DECIDIR"
        )
    )
):

    if id_inventario <= 0:
        raise HTTPException(
            status_code=400,
            detail="Inventário inválido."
        )

    codigo = (
        dados.codigo
        .strip()
    )

    lote = (
        dados.lote.strip()
        if dados.lote
        else ""
    )

    decisao = (
        dados.decisao
        .strip()
        .upper()
    )

    usuario = (
    str(
        usuario_atual["login"]
    )
    .strip()
)

    justificativa = (
        dados.justificativa.strip()
        if dados.justificativa
        else None
    )

    # ========================================================
    # VALIDAÇÕES BÁSICAS
    # ========================================================

    if not codigo:
        raise HTTPException(
            status_code=400,
            detail="Código obrigatório."
        )

    if not usuario:
        raise HTTPException(
            status_code=400,
            detail="Usuário obrigatório."
        )

    if decisao not in DECISOES_VALIDAS:
        raise HTTPException(
            status_code=400,
            detail=(
                "Decisão inválida. "
                "Valores permitidos: "
                "ACEITAR_ESTOQUE, "
                "ACEITAR_CONTAGEM ou "
                "NOVA_RECONTAGEM."
            )
        )

    # ========================================================
    # ACEITAR CONTAGEM EXIGE QUANTIDADE
    # ========================================================

    if (
        decisao == "ACEITAR_CONTAGEM"
        and
        dados.quantidade_aprovada is None
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Quantidade aprovada obrigatória "
                "para ACEITAR_CONTAGEM."
            )
        )

    if (
        dados.quantidade_aprovada is not None
        and
        dados.quantidade_aprovada < 0
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Quantidade aprovada não pode "
                "ser negativa."
            )
        )

    # ========================================================
    # NOVA RECONTAGEM EXIGE JUSTIFICATIVA
    # ========================================================

    if (
        decisao == "NOVA_RECONTAGEM"
        and
        not justificativa
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Justificativa obrigatória "
                "para solicitar nova recontagem."
            )
        )

    uow = None
    conn = None
    cursor = None

    try:

        uow = SqlServerUnitOfWork()
        uow.open()
        conn = uow.connection
        cursor = uow.cursor

        # ====================================================
        # 1. INVENTÁRIO
        # ====================================================

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
            raise HTTPException(
                status_code=404,
                detail="Inventário não encontrado."
            )

        if (
            str(inventario.Tipo)
            .strip()
            .upper()
            != "OFICIAL"
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Decisão gerencial disponível "
                    "somente para inventário OFICIAL."
                )
            )

        if inventario.Status in (
            "FINALIZADO",
            "CANCELADO"
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "O inventário não permite "
                    "novas decisões."
                )
            )

        # ====================================================
        # 2. VALIDA SE O ITEM EXISTE NO UNIVERSO DO INVENTÁRIO
        #
        # Snapshot OU alguma contagem
        # ====================================================

        cursor.execute(
            """
            SELECT COUNT(*)

            FROM
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
                    ) AS Lote

                FROM dbo.InventarioEstoqueSnapshot

                WHERE ID_Inventario = ?

                UNION

                SELECT
                    LTRIM(
                        RTRIM(C.Codigo)
                    ) AS Codigo,

                    ISNULL(
                        LTRIM(
                            RTRIM(C.Lote)
                        ),
                        ''
                    ) AS Lote

                FROM dbo.Contagens C

                INNER JOIN dbo.SessoesContagem S
                    ON S.ID_Sessao =
                       C.ID_Sessao

                WHERE
                    S.ID_Inventario = ?
                    AND S.ValidaParaConsolidacao = 1
                    AND C.Status = 'ATIVA'

            ) U

            WHERE U.Codigo = ?
              AND U.Lote = ?
            """,
            (
                id_inventario,
                id_inventario,
                codigo,
                lote
            )
        )

        item_existe = (
            cursor.fetchone()[0]
        )

        if item_existe == 0:
            raise HTTPException(
                status_code=404,
                detail=(
                    "Código + Lote não encontrado "
                    "neste inventário."
                )
            )

        # ====================================================
        # 3. DESATIVA DECISÃO ANTERIOR
        #
        # Mantemos histórico.
        # Não apagamos registros.
        # ====================================================

        # ====================================================
        # 3.1 SERIALIZA A DECISÃO DO ITEM
        #
        # UPDLOCK + HOLDLOCK evita duas requisições simultâneas
        # decidirem o mesmo ID_Inventario + Codigo + Lote.
        # ====================================================

        cursor.execute(
            """
            SELECT ID_Decisao
            FROM dbo.DecisoesGestorInventario WITH (UPDLOCK, HOLDLOCK)
            WHERE ID_Inventario = ?
              AND Codigo = ?
              AND Lote = ?
              AND Status = 'ATIVA'
            """,
            (
                id_inventario,
                codigo,
                lote
            )
        )

        cursor.fetchone()

        cursor.execute(
            """
            UPDATE dbo.DecisoesGestorInventario

            SET Status = 'SUBSTITUIDA'

            WHERE ID_Inventario = ?
              AND Codigo = ?
              AND Lote = ?
              AND Status = 'ATIVA'
            """,
            (
                id_inventario,
                codigo,
                lote
            )
        )

        # ====================================================
        # 4. QUANTIDADE APROVADA
        #
        # ACEITAR_ESTOQUE:
        # pega automaticamente o Snapshot.
        #
        # ACEITAR_CONTAGEM:
        # usa quantidade enviada pelo gestor.
        #
        # NOVA_RECONTAGEM:
        # fica NULL.
        # ====================================================

        quantidade_aprovada = None

        if decisao == "ACEITAR_ESTOQUE":

            cursor.execute(
                """
                SELECT
                    ISNULL(
                        SUM(SaldoInventario),
                        0
                    ) AS Quantidade

                FROM dbo.InventarioEstoqueSnapshot

                WHERE ID_Inventario = ?

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
                    codigo,
                    lote
                )
            )

            saldo = cursor.fetchone()

            quantidade_aprovada = float(
                saldo.Quantidade
                if saldo
                else 0
            )

        elif decisao == "ACEITAR_CONTAGEM":

            quantidade_aprovada = float(
                dados.quantidade_aprovada
            )

        # ====================================================
        # 5. INSERE DECISÃO
        # ====================================================

        cursor.execute(
            """
            INSERT INTO dbo.DecisoesGestorInventario
            (
                ID_Inventario,
                Codigo,
                Lote,
                Decisao,
                QuantidadeAprovada,
                Justificativa,
                Usuario,
                Status
            )

            OUTPUT
                INSERTED.ID_Decisao,
                INSERTED.DataHora

            VALUES
            (
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                'ATIVA'
            )
            """,
            (
                id_inventario,
                codigo,
                lote,
                decisao,
                quantidade_aprovada,
                justificativa,
                usuario
            )
        )

        nova = cursor.fetchone()

        if decisao == "NOVA_RECONTAGEM":
            tipo_notificacao = (
                "RECONTAGEM_SOLICITADA"
            )
            titulo_notificacao = (
                "Nova recontagem solicitada"
            )
            mensagem_notificacao = (
                f"O gestor solicitou nova "
                f"recontagem para o item "
                f"{codigo}"
                + (
                    f", lote {lote}"
                    if lote
                    else ""
                )
                + (
                    f", no invent\u00e1rio "
                    f"{inventario.CodigoInventario}."
                )
            )
            prioridade_notificacao = "CRITICA"
            permissao_destino = "RODADA_GERAR"
        else:
            tipo_notificacao = (
                "GESTOR_DECISAO_REGISTRADA"
            )
            titulo_notificacao = (
                "Decis\u00e3o do gestor registrada"
            )
            mensagem_notificacao = (
                f"O item {codigo}"
                + (
                    f", lote {lote}"
                    if lote
                    else ""
                )
                + (
                    f", recebeu a decis\u00e3o "
                    f"{decisao.replace('_', ' ').title()} "
                    f"no invent\u00e1rio "
                    f"{inventario.CodigoInventario}."
                )
            )
            prioridade_notificacao = "ALTA"
            permissao_destino = (
                "INVENTARIO_FINALIZAR"
            )

        resumo_notificacoes = (
            criar_por_permissao(
                cursor=cursor,
                codigo_permissao=(
                    permissao_destino
                ),
                id_usuario_ator=int(
                    usuario_atual["id_usuario"]
                ),
                tipo=tipo_notificacao,
                titulo=titulo_notificacao,
                mensagem=mensagem_notificacao,
                prioridade=(
                    prioridade_notificacao
                ),
                entidade_tipo="DECISAO_GESTOR",
                entidade_id=int(
                    nova.ID_Decisao
                ),
                id_inventario=id_inventario,
                url=(
                    f"/inventarios/"
                    f"{id_inventario}"
                ),
                chave_dedupe=(
                    f"{tipo_notificacao}:"
                    f"{id_inventario}:"
                    f"{nova.ID_Decisao}"
                ),
                excluir_ator=False,
            )
        )

        uow.commit()

        return {
            "sucesso":
                True,

            "id_decisao":
                nova.ID_Decisao,

            "id_inventario":
                id_inventario,

            "codigo_inventario":
                inventario.CodigoInventario,

            "codigo":
                codigo,

            "lote":
                lote,

            "decisao":
                decisao,

            "quantidade_aprovada":
                quantidade_aprovada,

            "justificativa":
                justificativa,

            "usuario":
                usuario,

            "data_hora":
                nova.DataHora,

            "status":
                "ATIVA",

            "notificacoes":
                resumo_notificacoes,

            "mensagem":
                "Decisão gerencial registrada com sucesso."
        }

    except HTTPException:

        if conn:
            uow.rollback()

        raise

    except Exception as erro:

        if conn:
            uow.rollback()

        mensagem_erro = str(
            erro
        )

        if (
            "2601" in mensagem_erro
            or "2627" in mensagem_erro
        ):
            raise HTTPException(
                status_code=409,
                detail=(
                    "Outra decisão foi registrada ao mesmo tempo "
                    "para este Código + Lote. Atualize a análise "
                    "e tente novamente."
                )
            )

        raise HTTPException(
            status_code=500,
            detail=str(erro)
        )

    finally:

        if uow:
            uow.close()