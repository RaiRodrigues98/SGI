from fastapi import (
    APIRouter,
    HTTPException,
)

from pydantic import BaseModel, Field

from infrastructure.database.unit_of_work import SqlServerUnitOfWork

from services.rotativo_fluxo import (
    iniciar_localizacao_rotativo,
    ignorar_localizacao_rotativo,
)


router = APIRouter(
    prefix="/rotativo",
    tags=["Controle Rotativo"]
)


class IniciarLocalizacaoRequest(BaseModel):
    id_ciclo_localizacao: int = Field(..., ge=1)
    id_inventario: int | None = Field(default=None, ge=1)
    id_rodada: int | None = Field(default=None, ge=1)
    usuario: str | None = None


class IgnorarLocalizacaoRequest(BaseModel):
    id_ciclo_localizacao: int = Field(..., ge=1)
    motivo: str = Field(..., min_length=1, max_length=500)
    usuario: str | None = None


@router.post("/ciclos/localizacoes/iniciar")
def iniciar_localizacao(
    dados: IniciarLocalizacaoRequest
):
    uow = None
    conn = None
    cursor = None

    try:
        uow = SqlServerUnitOfWork()
        uow.open()
        conn = uow.connection
        cursor = uow.cursor

        return iniciar_localizacao_rotativo(
            conn=conn,
            cursor=cursor,
            id_ciclo_localizacao=dados.id_ciclo_localizacao,
            id_inventario=dados.id_inventario,
            id_rodada=dados.id_rodada,
            usuario=dados.usuario
        )

    except ValueError as erro:
        raise HTTPException(
            status_code=400,
            detail=str(erro)
        )

    except Exception as erro:
        raise HTTPException(
            status_code=500,
            detail=str(erro)
        )

    finally:
        if uow:
            uow.close()


@router.post("/ciclos/localizacoes/ignorar")
def ignorar_localizacao(
    dados: IgnorarLocalizacaoRequest
):
    uow = None
    conn = None
    cursor = None

    try:
        uow = SqlServerUnitOfWork()
        uow.open()
        conn = uow.connection
        cursor = uow.cursor

        return ignorar_localizacao_rotativo(
            conn=conn,
            cursor=cursor,
            id_ciclo_localizacao=dados.id_ciclo_localizacao,
            motivo=dados.motivo,
            usuario=dados.usuario
        )

    except ValueError as erro:
        raise HTTPException(
            status_code=400,
            detail=str(erro)
        )

    except Exception as erro:
        raise HTTPException(
            status_code=500,
            detail=str(erro)
        )

    finally:
        if uow:
            uow.close()
