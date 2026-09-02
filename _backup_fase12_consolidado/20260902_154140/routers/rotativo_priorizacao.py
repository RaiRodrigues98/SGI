from fastapi import (
    APIRouter,
    HTTPException,
    Query,
)

from infrastructure.database.unit_of_work import SqlServerUnitOfWork

from domain.exceptions import BusinessRuleViolation

from services.rotativo_priorizacao import (
    recalcular_priorizacao_rotativo,
)


router = APIRouter(
    prefix="/rotativo",
    tags=["Controle Rotativo"]
)


@router.post(
    "/priorizacao/recalcular"
)
def recalcular_priorizacao(
    cliente_id: int = Query(
        ...,
        ge=1
    ),
    armazem: str = Query(
        ...,
        min_length=1
    ),
    limite_score_sugestao: float = Query(
        default=50,
        ge=0,
        le=100
    ),
    quantidade_sugestoes: int = Query(
        default=20,
        ge=1,
        le=500
    )
):
    uow = None
    conn = None
    cursor = None

    try:
        uow = SqlServerUnitOfWork()
        uow.open()
        conn = uow.connection
        cursor = uow.cursor

        return recalcular_priorizacao_rotativo(
            conn=conn,
            cursor=cursor,
            cliente_id=cliente_id,
            armazem=armazem,
            limite_score_sugestao=limite_score_sugestao,
            quantidade_sugestoes=quantidade_sugestoes
        )

    except BusinessRuleViolation as erro:
        raise HTTPException(
            status_code=400,
            detail=str(erro)
        )

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