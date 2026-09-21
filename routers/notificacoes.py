from fastapi import APIRouter, Depends, HTTPException, Query

from dependencies.auth import obter_usuario_atual
from domain.exceptions import NotFoundError
from infrastructure.database.unit_of_work import SqlServerUnitOfWork
from services.notificacoes import (
    contar_nao_lidas,
    listar,
    marcar_como_lida,
    marcar_todas_como_lidas,
)


router = APIRouter(
    prefix="/notificacoes",
    tags=["Notificações"],
)


def _id_usuario(usuario_atual) -> int:
    return int(usuario_atual["id_usuario"])


def _executar_leitura(operacao):
    uow = SqlServerUnitOfWork()

    try:
        uow.open()
        return operacao(uow.cursor)
    except HTTPException:
        raise
    except Exception as erro:
        raise HTTPException(status_code=500, detail=str(erro))
    finally:
        uow.close()


def _executar_escrita(operacao):
    uow = SqlServerUnitOfWork()

    try:
        uow.open()
        resultado = operacao(uow.cursor)
        uow.commit()
        return resultado
    except NotFoundError as erro:
        uow.rollback()
        raise HTTPException(status_code=404, detail=str(erro))
    except HTTPException:
        uow.rollback()
        raise
    except Exception as erro:
        uow.rollback()
        raise HTTPException(status_code=500, detail=str(erro))
    finally:
        uow.close()


@router.get("")
def listar_notificacoes(
    somente_nao_lidas: bool = Query(default=False),
    limite: int = Query(default=30, ge=1, le=100),
    usuario_atual=Depends(obter_usuario_atual),
):
    id_usuario = _id_usuario(usuario_atual)

    notificacoes = _executar_leitura(
        lambda cursor: listar(
            cursor=cursor,
            id_usuario=id_usuario,
            somente_nao_lidas=somente_nao_lidas,
            limite=limite,
        )
    )

    return {
        "total": len(notificacoes),
        "notificacoes": notificacoes,
    }


@router.get("/nao-lidas/quantidade")
def quantidade_nao_lidas(
    usuario_atual=Depends(obter_usuario_atual),
):
    id_usuario = _id_usuario(usuario_atual)

    quantidade = _executar_leitura(
        lambda cursor: contar_nao_lidas(
            cursor=cursor,
            id_usuario=id_usuario,
        )
    )

    return {
        "quantidade": quantidade,
    }


@router.patch("/{id_notificacao}/ler")
def ler_notificacao(
    id_notificacao: int,
    usuario_atual=Depends(obter_usuario_atual),
):
    if id_notificacao <= 0:
        raise HTTPException(
            status_code=400,
            detail="Notificação inválida.",
        )

    id_usuario = _id_usuario(usuario_atual)

    return _executar_escrita(
        lambda cursor: marcar_como_lida(
            cursor=cursor,
            id_notificacao=id_notificacao,
            id_usuario=id_usuario,
        )
    )


@router.patch("/ler-todas")
def ler_todas_notificacoes(
    usuario_atual=Depends(obter_usuario_atual),
):
    id_usuario = _id_usuario(usuario_atual)

    return _executar_escrita(
        lambda cursor: marcar_todas_como_lidas(
            cursor=cursor,
            id_usuario=id_usuario,
        )
    )
