from fastapi import (
    APIRouter,
    HTTPException,
)

from pydantic import BaseModel, Field

from infrastructure.database.unit_of_work import SqlServerUnitOfWork

from domain.exceptions import BusinessRuleViolation
from services.rotativo_cobertura import (
    registrar_conclusao_localizacao_rotativo,
)


router = APIRouter(
    prefix="/rotativo",
    tags=["Controle Rotativo"]
)


# ============================================================
# PAYLOAD
# ============================================================

class ConcluirLocalizacaoRotativoRequest(
    BaseModel
):
    id_sessao: int = Field(
        ...,
        ge=1
    )

    usuario: str | None = None


# ============================================================
# REGISTRAR LOCALIZAÇÃO CONTADA NO CICLO
# ============================================================

@router.post(
    "/ciclos/localizacoes/concluir"
)
def concluir_localizacao_rotativo(
    dados: ConcluirLocalizacaoRotativoRequest
):
    uow = None
    conn = None
    cursor = None

    try:
        uow = SqlServerUnitOfWork()
        uow.open()
        conn = uow.connection
        cursor = uow.cursor

        return (
            registrar_conclusao_localizacao_rotativo(
                conn=conn,
                cursor=cursor,
                id_sessao=dados.id_sessao,
                usuario=dados.usuario
            )
        )

    except BusinessRuleViolation as erro:
        raise HTTPException(
            status_code=400,
            detail=str(
                erro
            )
        )

    except HTTPException:
        raise

    except Exception as erro:
        raise HTTPException(
            status_code=500,
            detail=str(
                erro
            )
        )

    finally:

        if uow:
            uow.close()
