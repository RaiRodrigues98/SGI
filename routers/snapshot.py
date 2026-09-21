from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)

from infrastructure.database.unit_of_work import SqlServerUnitOfWork

from dependencies.auth import (
    exigir_permissao,
)

from schemas.snapshot import (
    GerarSnapshotEntrada,
)


router = APIRouter(
    tags=["Snapshot do Inventário"]
)


# ============================================================
# GERAR SNAPSHOT DO INVENTÁRIO
#
# Permissão:
# CONFIGURACAO_EDITAR
#
# IMPORTANTE:
#
# O snapshot representa a fotografia do estoque utilizada
# como referência para todo o processo de inventário.
#
# Por isso:
#
# - não é uma operação de contagem;
# - não deve ficar disponível ao OPERADOR;
# - só pode ser gerado uma vez por inventário;
# - utiliza somente as localizações selecionadas no escopo;
# - não pode existir snapshot parcial.
#
# Futuramente podemos criar uma permissão específica:
#
# SNAPSHOT_GERAR
#
# ============================================================

@router.get(
    "/inventarios/{id_inventario}/snapshot/status"
)
def consultar_status_snapshot(
    id_inventario: int,
    usuario_atual=Depends(
        exigir_permissao(
            "INVENTARIO_VISUALIZAR"
        )
    )
):
    if id_inventario <= 0:
        raise HTTPException(
            status_code=400,
            detail="Invent?rio inv?lido."
        )

    uow = None

    try:
        uow = SqlServerUnitOfWork()
        uow.open()
        cursor = uow.cursor

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM dbo.Inventarios
            WHERE ID_Inventario = ?
            """,
            id_inventario
        )

        if int(cursor.fetchone()[0]) == 0:
            raise HTTPException(
                status_code=404,
                detail="Invent?rio n?o encontrado."
            )

        cursor.execute(
            """
            SELECT
                COUNT(*) AS RegistrosSnapshot,
                COUNT(DISTINCT Localizacao) AS LocalizacoesSnapshot
            FROM dbo.InventarioEstoqueSnapshot
            WHERE ID_Inventario = ?
            """,
            id_inventario
        )

        resultado = cursor.fetchone()

        registros_snapshot = int(
            resultado.RegistrosSnapshot or 0
        )

        localizacoes_snapshot = int(
            resultado.LocalizacoesSnapshot or 0
        )

        return {
            "id_inventario": id_inventario,
            "snapshot_gerado": registros_snapshot > 0,
            "registros_snapshot": registros_snapshot,
            "localizacoes_snapshot": localizacoes_snapshot,
        }

    except HTTPException:
        raise

    except Exception as erro:
        raise HTTPException(
            status_code=500,
            detail=str(erro)
        )

    finally:
        if uow:
            uow.close()



# ============================================================
# CONSULTAR CONTEUDO DO SNAPSHOT
#
# Retorna exclusivamente os dados congelados no momento da
# geracao do snapshot. Nao consulta o estoque vivo.
# ============================================================

@router.get(
    "/inventarios/{id_inventario}/snapshot"
)
def consultar_snapshot_inventario(
    id_inventario: int,
    usuario_atual=Depends(
        exigir_permissao(
            "ANALISE_VISUALIZAR"
        )
    )
):
    if id_inventario <= 0:
        raise HTTPException(
            status_code=400,
            detail="Invent\u00e1rio inv\u00e1lido."
        )

    uow = None

    try:
        uow = SqlServerUnitOfWork()
        uow.open()
        cursor = uow.cursor

        # ----------------------------------------------------
        # INVENTARIO
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT
                ID_Inventario,
                CodigoInventario,
                Tipo,
                Cliente,
                ClienteId,
                cArmazem
            FROM dbo.Inventarios
            WHERE ID_Inventario = ?
            """,
            id_inventario
        )

        inventario = cursor.fetchone()

        if not inventario:
            raise HTTPException(
                status_code=404,
                detail="Invent\u00e1rio n\u00e3o encontrado."
            )

        # ----------------------------------------------------
        # SNAPSHOT CONGELADO
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT
                ID_Snapshot,
                ID_Origem,
                cArmazem,
                Localizacao,
                Codigo,
                Lote,
                Descricao,
                Unidade,
                Categoria,
                Validade,
                qArmazenado,
                qReservado,
                qBloqueado,
                qEstimado,
                ValorUnitario,
                StatusEstoque,
                TipoLocalizacao,
                SaldoInventario,
                DataHoraSnapshot
            FROM dbo.InventarioEstoqueSnapshot
            WHERE ID_Inventario = ?
            ORDER BY
                Localizacao,
                Codigo,
                Lote
            """,
            id_inventario
        )

        linhas = cursor.fetchall()

        itens = []

        for linha in linhas:

            valor_unitario = (
                float(linha.ValorUnitario)
                if linha.ValorUnitario is not None
                else None
            )

            q_armazenado = float(
                linha.qArmazenado
            )

            valor_total = (
                valor_unitario * q_armazenado
                if valor_unitario is not None
                else None
            )

            itens.append({
                "id_origem": (
                    int(linha.ID_Origem)
                    if linha.ID_Origem is not None
                    else int(linha.ID_Snapshot)
                ),

                "c_armazem":
                    linha.cArmazem,

                "localizacao":
                    linha.Localizacao,

                "codigo":
                    linha.Codigo,

                "lote":
                    linha.Lote,

                "cliente_id":
                    inventario.ClienteId,

                "descricao":
                    linha.Descricao,

                "unidade":
                    linha.Unidade,

                "categoria":
                    linha.Categoria,

                "validade":
                    linha.Validade,

                "valor_unitario":
                    valor_unitario,

                "valor_total":
                    valor_total,

                "q_armazenado":
                    q_armazenado,

                "q_reservado":
                    float(
                        linha.qReservado
                    ),

                # Na consulta atual de estoque candidato,
                # Separando corresponde a qReservado.
                "q_separando":
                    float(
                        linha.qReservado
                    ),

                "q_bloqueado": (
                    float(linha.qBloqueado)
                    if linha.qBloqueado is not None
                    else None
                ),

                "q_recebimento": (
                    float(linha.qEstimado)
                    if linha.qEstimado is not None
                    else None
                ),

                "saldo_inventario":
                    float(
                        linha.SaldoInventario
                    ),

                "status_estoque":
                    linha.StatusEstoque,

                "tipo_localizacao":
                    linha.TipoLocalizacao,

                "data_hora_snapshot":
                    linha.DataHoraSnapshot,
            })

        return {
            "id_inventario":
                inventario.ID_Inventario,

            "codigo_inventario":
                inventario.CodigoInventario,

            "tipo":
                inventario.Tipo,

            "cliente":
                inventario.Cliente,

            "cliente_id":
                inventario.ClienteId,

            "c_armazem":
                inventario.cArmazem,

            "total":
                len(itens),

            "itens":
                itens,
        }

    except HTTPException:
        raise

    except Exception as erro:
        raise HTTPException(
            status_code=500,
            detail=str(erro)
        )

    finally:
        if uow:
            uow.close()


@router.post(
    "/inventarios/{id_inventario}/snapshot"
)
def gerar_snapshot_inventario(
    id_inventario: int,
    dados: GerarSnapshotEntrada,
    usuario_atual=Depends(
        exigir_permissao(
            "CONFIGURACAO_EDITAR"
        )
    )
):

    # ========================================================
    # 1. VALIDA INVENTÁRIO
    # ========================================================

    if id_inventario <= 0:

        raise HTTPException(
            status_code=400,
            detail="Inventário inválido."
        )

    # ========================================================
    # 2. USUÁRIO AUTENTICADO
    #
    # Auditoria vem do JWT.
    # ========================================================

    gerado_por = (
        str(usuario_atual["login"]).strip()
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
        # 3. BUSCA INVENTÁRIO
        # ====================================================

        cursor.execute(
            """
            SELECT
                ID_Inventario,
                CodigoInventario,
                ClienteId,
                cArmazem,
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

        # ====================================================
        # 4. VALIDA STATUS DO INVENTÁRIO
        # ====================================================

        status_inventario = (
            str(inventario.Status)
            .strip()
            .upper()
            if inventario.Status is not None
            else ""
        )

        if status_inventario in (
            "FINALIZADO",
            "CANCELADO",
        ):

            raise HTTPException(
                status_code=400,
                detail=(
                    "O inventário não permite "
                    "geração de snapshot."
                )
            )

        # ====================================================
        # 5. VALIDA CLIENTE
        # ====================================================

        if inventario.ClienteId is None:

            raise HTTPException(
                status_code=400,
                detail=(
                    "Inventário sem ClienteId "
                    "configurado."
                )
            )

        # ====================================================
        # 6. VALIDA ARMAZÉM
        # ====================================================

        armazem = (
            str(inventario.cArmazem).strip()
            if inventario.cArmazem is not None
            else ""
        )

        if not armazem:

            raise HTTPException(
                status_code=400,
                detail=(
                    "Inventário sem armazém "
                    "configurado."
                )
            )

        # ====================================================
        # 7. IMPEDE SNAPSHOT DUPLICADO
        # ====================================================

        cursor.execute(
            """
            SELECT COUNT(*)

            FROM dbo.InventarioEstoqueSnapshot

            WHERE ID_Inventario = ?
            """,
            id_inventario
        )

        total_snapshot = int(
            cursor.fetchone()[0]
        )

        if total_snapshot > 0:

            raise HTTPException(
                status_code=400,
                detail=(
                    "Este inventário já possui "
                    "snapshot gerado."
                )
            )

        # ====================================================
        # 8. CONFIRMA ESCOPO SELECIONADO
        # ====================================================

        cursor.execute(
            """
            SELECT COUNT(*)

            FROM dbo.InventarioEscopoLocalizacoes

            WHERE
                ID_Inventario = ?
                AND Selecionado = 1
            """,
            id_inventario
        )

        total_escopo = int(
            cursor.fetchone()[0]
        )

        if total_escopo == 0:

            raise HTTPException(
                status_code=400,
                detail=(
                    "O inventário não possui "
                    "localizações selecionadas "
                    "no escopo."
                )
            )

        # ====================================================
        # 9. GERA SNAPSHOT
        #
        # Somente:
        #
        # - cliente do inventário;
        # - armazém do inventário;
        # - localizações selecionadas;
        # - saldo diferente de zero.
        #
        # SaldoInventario:
        #
        # qArmazenado - qReservado
        # ====================================================

        cursor.execute(
            """
            INSERT INTO dbo.InventarioEstoqueSnapshot
            (
                ID_Inventario,
                ID_Origem,
                cArmazem,
                Localizacao,
                Codigo,
                Lote,
                Descricao,
                Unidade,
                Categoria,
                Validade,
                qArmazenado,
                qReservado,
                qBloqueado,
                qEstimado,
                ValorUnitario,
                StatusEstoque,
                TipoLocalizacao,
                SaldoInventario
            )

            SELECT
                ?,
                E.Id,
                E.cArmazem,
                E.cLocalizacao,
                E.cItem,
                E.cLote,
                E.dItem,
                E.cUnidade,
                E.cCategoria,
                E.Validade,
                E.qArmazenado,
                E.qReservado,
                E.qBloqueado,
                E.qEstimado,
                Preco.ValorUnitario,
                E.StatusEstoque,
                E.TipoLocalizacao,
                (
                    E.qArmazenado
                    -
                    E.qReservado
                )

            FROM AlzarsiLog.dbo.Estoque E

            INNER JOIN AlzarsiLog.dbo.Cliente C
                ON C.Id = E.ClienteId

            OUTER APPLY (
                SELECT TOP 1
                    RI.ValorUnitario

                FROM AlzarsiLog.dbo.RecebimentoItem RI

                INNER JOIN AlzarsiLog.dbo.Recebimento R
                    ON R.Id = RI.RecebimentoId

                WHERE
                    R.CnpjCliente = C.Cnpj

                    AND RI.CodigoItem = E.cItem

                    AND ISNULL(
                        LTRIM(RTRIM(RI.CodigoLote)),
                        ''
                    ) = ISNULL(
                        LTRIM(RTRIM(E.cLote)),
                        ''
                    )

                    AND RI.ValorUnitario IS NOT NULL

                ORDER BY
                    R.DataCriacao DESC,
                    RI.Id DESC
            ) Preco

            INNER JOIN dbo.InventarioEscopoLocalizacoes EL
                ON EL.ID_Inventario = ?
                AND EL.Localizacao = E.cLocalizacao
                AND EL.Selecionado = 1

            WHERE
                E.ClienteId = ?
                AND E.cArmazem = ?

                AND (
                    E.qArmazenado
                    -
                    E.qReservado
                ) <> 0
            """,
            (
                id_inventario,
                id_inventario,
                inventario.ClienteId,
                armazem
            )
        )

        linhas_inseridas = (
            cursor.rowcount
        )

        # ====================================================
        # 10. VALIDA RESULTADO
        # ====================================================

        if (
            linhas_inseridas is None
            or linhas_inseridas <= 0
        ):

            raise HTTPException(
                status_code=400,
                detail=(
                    "Nenhum item foi encontrado "
                    "para gerar o snapshot."
                )
            )

        # ====================================================
        # 11. COMMIT
        # ====================================================

        uow.commit()

        # ====================================================
        # 12. RETORNO
        # ====================================================

        return {
            "sucesso":
                True,

            "id_inventario":
                id_inventario,

            "codigo_inventario":
                inventario.CodigoInventario,

            "cliente_id":
                inventario.ClienteId,

            "armazem":
                armazem,

            "localizacoes_escopo":
                total_escopo,

            "registros_snapshot":
                linhas_inseridas,

            "gerado_por":
                gerado_por,

            "mensagem":
                "Snapshot do estoque gerado com sucesso."
        }

    except HTTPException:

        if conn:
            uow.rollback()

        raise

    except Exception as erro:

        if conn:
            uow.rollback()

        raise HTTPException(
            status_code=500,
            detail=str(erro)
        )

    finally:

        if uow:
            uow.close()