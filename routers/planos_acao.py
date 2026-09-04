from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from dependencies.auth import exigir_permissao
from domain.exceptions import (
    BusinessRuleViolation,
    ConflictError,
    InvalidStateError,
    NotFoundError,
)
from infrastructure.database.unit_of_work import SqlServerUnitOfWork
from services.planos_acao import (
    atualizar_analise,
    consultar_analise_ocorrencia,
    criar_analise_ocorrencia,
    encerrar_analise,
)


router = APIRouter(tags=["Planos de AÃƒÂ§ÃƒÂ£o"])


class AnalisePayload(BaseModel):
    categoria_causa: str = Field(min_length=1, max_length=50)
    causa_raiz: str = Field(min_length=1, max_length=2000)
    observacao: str | None = Field(default=None, max_length=2000)


def _ator(usuario):
    login = str(usuario.get("login") or "").strip()
    if not login:
        raise HTTPException(
            status_code=401,
            detail="UsuÃƒÂ¡rio autenticado sem login vÃƒÂ¡lido.",
        )
    return login


def _rollback(uow):
    if getattr(uow, "connection", None):
        uow.connection.rollback()


def _executar_leitura(operacao):
    uow = SqlServerUnitOfWork()
    try:
        uow.open()
        return operacao(uow.cursor)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except InvalidStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except BusinessRuleViolation as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Erro interno ao processar anÃƒÂ¡lise de ocorrÃƒÂªncia.",
        )
    finally:
        uow.close()


def _executar_escrita(operacao):
    uow = SqlServerUnitOfWork()
    try:
        uow.open()
        resultado = operacao(uow.cursor)
        uow.connection.commit()
        return resultado
    except NotFoundError as exc:
        _rollback(uow)
        raise HTTPException(status_code=404, detail=str(exc))
    except ConflictError as exc:
        _rollback(uow)
        raise HTTPException(status_code=409, detail=str(exc))
    except InvalidStateError as exc:
        _rollback(uow)
        raise HTTPException(status_code=409, detail=str(exc))
    except BusinessRuleViolation as exc:
        _rollback(uow)
        raise HTTPException(status_code=400, detail=str(exc))
    except HTTPException:
        _rollback(uow)
        raise
    except Exception:
        _rollback(uow)
        raise HTTPException(
            status_code=500,
            detail="Erro interno ao processar anÃƒÂ¡lise de ocorrÃƒÂªncia.",
        )
    finally:
        uow.close()


@router.post("/ocorrencias/{id_ocorrencia}/analise")
def criar_analise(
    id_ocorrencia: int,
    payload: AnalisePayload,
    usuario=Depends(exigir_permissao("PLANO_ACAO_GERENCIAR")),
):
    ator = _ator(usuario)
    return _executar_escrita(
        lambda cursor: criar_analise_ocorrencia(
            cursor,
            id_ocorrencia,
            payload.categoria_causa,
            payload.causa_raiz,
            payload.observacao,
            ator,
        )
    )


@router.get("/ocorrencias/{id_ocorrencia}/analise")
def consultar_analise(
    id_ocorrencia: int,
    _usuario=Depends(exigir_permissao("PLANO_ACAO_VISUALIZAR")),
):
    return _executar_leitura(
        lambda cursor: consultar_analise_ocorrencia(cursor, id_ocorrencia)
    )


@router.put("/analises/{id_analise}")
def alterar_analise(
    id_analise: int,
    payload: AnalisePayload,
    usuario=Depends(exigir_permissao("PLANO_ACAO_GERENCIAR")),
):
    ator = _ator(usuario)
    return _executar_escrita(
        lambda cursor: atualizar_analise(
            cursor,
            id_analise,
            payload.categoria_causa,
            payload.causa_raiz,
            payload.observacao,
            ator,
        )
    )


@router.post("/analises/{id_analise}/encerrar")
def encerrar(
    id_analise: int,
    usuario=Depends(exigir_permissao("PLANO_ACAO_GERENCIAR")),
):
    ator = _ator(usuario)
    return _executar_escrita(
        lambda cursor: encerrar_analise(cursor, id_analise, ator)
    )
