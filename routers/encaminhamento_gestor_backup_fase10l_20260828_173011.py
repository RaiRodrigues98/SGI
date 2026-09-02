from fastapi import APIRouter, Depends, HTTPException

from infrastructure.database.unit_of_work import SqlServerUnitOfWork

from dependencies.auth import (
    exigir_permissao,
)

from schemas.encaminhamento_gestor import (
    EncaminharGestorEntrada,
)

from services.encaminhamento_gestor import (
    encaminhar_inventario_para_gestor,
)


router = APIRouter(
    tags=["Gestor"]
)


# ============================================================
# ENCAMINHAR INVENTÁRIO PARA ANÁLISE GERENCIAL
# ============================================================

@router.post(
    "/inventarios/{id_inventario}/encaminhar-gestor"
)
def encaminhar_gestor(
    id_inventario: int,
    dados: EncaminharGestorEntrada,
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

    # ========================================================
    # USUÁRIO AUTENTICADO
    #
    # A auditoria vem do JWT. Não confiamos no usuário
    # informado pelo frontend.
    # ========================================================

    usuario = (
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

        resultado = (
            encaminhar_inventario_para_gestor(
                cursor=cursor,
                id_inventario=id_inventario,
                usuario=usuario
            )
        )

        # ====================================================
        # O SERVICE NÃO REALIZA COMMIT
        # ====================================================

        uow.commit()

        return resultado

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