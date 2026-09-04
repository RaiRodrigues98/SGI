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

# FASE 13.12.3B.2 - PLANOS DE ACAO
from datetime import date as _b2_date
from services.planos_acao import atualizar_plano_acao, concluir_plano_acao, consultar_plano_acao, criar_plano_acao, listar_planos_acao


class PlanoAcaoCriacaoPayload(BaseModel):
    descricao_acao: str = Field(min_length=1, max_length=2000)
    responsavel: str = Field(min_length=1, max_length=100)
    data_prazo: _b2_date
    prioridade: str = Field(min_length=1, max_length=20)
    observacao: str | None = Field(default=None, max_length=2000)


class PlanoAcaoAtualizacaoPayload(BaseModel):
    descricao_acao: str = Field(min_length=1, max_length=2000)
    responsavel: str = Field(min_length=1, max_length=100)
    data_prazo: _b2_date
    prioridade: str = Field(min_length=1, max_length=20)
    status: str = Field(min_length=1, max_length=20)
    observacao: str | None = Field(default=None, max_length=2000)


def _b2_rollback(uow):
    try:
        if uow.connection is not None:
            uow.connection.rollback()
    except Exception:
        pass


def _b2_tratar(exc):
    if isinstance(exc, NotFoundError):
        raise HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, (ConflictError, InvalidStateError)):
        raise HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, BusinessRuleViolation):
        raise HTTPException(status_code=400, detail=str(exc))
    raise HTTPException(status_code=500, detail="Erro interno ao processar plano de acao.")


def _b2_leitura(fn):
    uow = SqlServerUnitOfWork()
    try:
        uow.open()
        return fn(uow.cursor)
    except HTTPException:
        raise
    except Exception as exc:
        _b2_tratar(exc)
    finally:
        uow.close()


def _b2_escrita(fn):
    uow = SqlServerUnitOfWork()
    try:
        uow.open()
        resultado = fn(uow.cursor)
        uow.connection.commit()
        return resultado
    except HTTPException:
        _b2_rollback(uow)
        raise
    except Exception as exc:
        _b2_rollback(uow)
        _b2_tratar(exc)
    finally:
        uow.close()


@router.post("/analises/{id_analise}/planos")
def criar_plano(id_analise: int, payload: PlanoAcaoCriacaoPayload, usuario=Depends(exigir_permissao("PLANO_ACAO_GERENCIAR"))):
    ator = _ator(usuario)
    return _b2_escrita(lambda c: criar_plano_acao(c, id_analise, payload.descricao_acao, payload.responsavel, payload.data_prazo, payload.prioridade, payload.observacao, ator))


@router.get("/analises/{id_analise}/planos")
def listar_planos(id_analise: int, _usuario=Depends(exigir_permissao("PLANO_ACAO_VISUALIZAR"))):
    return _b2_leitura(lambda c: listar_planos_acao(c, id_analise))


@router.get("/planos-acao/{id_plano}")
def consultar_plano(id_plano: int, _usuario=Depends(exigir_permissao("PLANO_ACAO_VISUALIZAR"))):
    return _b2_leitura(lambda c: consultar_plano_acao(c, id_plano))


@router.put("/planos-acao/{id_plano}")
def atualizar_plano(id_plano: int, payload: PlanoAcaoAtualizacaoPayload, usuario=Depends(exigir_permissao("PLANO_ACAO_GERENCIAR"))):
    ator = _ator(usuario)
    return _b2_escrita(lambda c: atualizar_plano_acao(c, id_plano, payload.descricao_acao, payload.responsavel, payload.data_prazo, payload.prioridade, payload.status, payload.observacao, ator))


@router.post("/planos-acao/{id_plano}/concluir")
def concluir_plano(id_plano: int, usuario=Depends(exigir_permissao("PLANO_ACAO_GERENCIAR"))):
    ator = _ator(usuario)
    return _b2_escrita(lambda c: concluir_plano_acao(c, id_plano, ator))
