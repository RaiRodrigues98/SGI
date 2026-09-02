from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from domain.exceptions import NotFoundError

from infrastructure.database.unit_of_work import SqlServerUnitOfWork

from domain.exceptions import BusinessRuleViolation

from dependencies.auth import (
    exigir_permissao,
)

from schemas.inventarios import (
    InventarioCriacaoEntrada,
)

from services.inventarios import (
    criar_inventario,
)


router = APIRouter(
    tags=["Inventários"]
)


# ============================================================
# CRIAR INVENTÁRIO
# ============================================================

@router.post(
    "/inventarios"
)
def criar(
    dados: InventarioCriacaoEntrada,
    usuario_atual=Depends(
        exigir_permissao(
            "INVENTARIO_CRIAR"
        )
    )
):

    usuario = (
        str(
            usuario_atual[
                "login"
            ]
        )
        .strip()
    )

    uow = None
    conn = None
    cursor = None

    try:

        uow = SqlServerUnitOfWork()
        uow.open()
        conn = uow.connection
        cursor = uow.cursor

        resultado = criar_inventario(
            cursor=cursor,
            codigo_inventario=(
                dados.codigo_inventario
            ),
            tipo=dados.tipo,
            cliente_id=dados.cliente_id,
            cliente=dados.cliente,
            descricao=dados.descricao,
            armazem=dados.armazem,
            usuario=usuario
        )

        uow.commit()

        return resultado

    except BusinessRuleViolation as erro:

        uow.rollback()

        raise HTTPException(
            status_code=400,
            detail=str(erro)
        )

    except NotFoundError as erro:
        if conn:
            uow.rollback()

        raise HTTPException(
            status_code=404,
            detail=str(erro)
        )

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
