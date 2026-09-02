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
                (
                    E.qArmazenado
                    -
                    E.qReservado
                )

            FROM AlzarsiLog.dbo.Estoque E

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