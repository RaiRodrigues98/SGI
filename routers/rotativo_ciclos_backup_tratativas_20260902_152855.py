from datetime import datetime

from fastapi import (
    APIRouter,
    HTTPException,
    Query,
)

from pydantic import BaseModel, Field

from infrastructure.database.unit_of_work import SqlServerUnitOfWork

from services.ciclos_rotativo import (
    abrir_ciclo_rotativo,
    consultar_ciclo_atual,
    finalizar_ciclo_rotativo,
)
from services.rotativo_sugestoes import (
    consultar_sugestoes_rotativo,
)
from services.rotativo_painel import (
    consultar_painel_rotativo,
)
from services.rotativo_tendencia import (
    consultar_tendencias_rotativo,
)
from services.rotativo_tratativas import (
    consultar_tratativas_rotativo,
    resolver_ocorrencia_rotativo,
)
from services.rotativo_contexto import (
    montar_contexto_localizacao_rotativo,
)
from services.rotativo_orquestrador import (
    executar_orquestracao_rotativo,
)
router = APIRouter(
    prefix="/rotativo",
    tags=["Controle Rotativo"]
)


# ============================================================
# PAYLOAD
# ============================================================

class AbrirCicloRotativoRequest(
    BaseModel
):
    cliente_id: int = Field(
        ...,
        ge=1
    )

    armazem: str = Field(
        ...,
        min_length=1
    )

    criado_por: str | None = None

    data_fim_prevista: datetime | None = None

class ResolverOcorrenciaRequest(
    BaseModel
):
    tipo_resolucao: str = Field(
        ...,
        min_length=1
    )

    observacao_resolucao: str | None = None

    resolvido_por: str = Field(
        ...,
        min_length=1
    )

    id_inventario_resolucao: int | None = None

    id_rodada_resolucao: int | None = None
# ============================================================
# ABRIR CICLO
# ============================================================

@router.post(
    "/ciclos"
)
def criar_ciclo_rotativo(
    dados: AbrirCicloRotativoRequest
):
    uow = None
    conn = None
    cursor = None

    try:
        uow = SqlServerUnitOfWork()
        uow.open()
        conn = uow.connection
        cursor = uow.cursor

        return abrir_ciclo_rotativo(
            conn=conn,
            cursor=cursor,
            cliente_id=dados.cliente_id,
            armazem=dados.armazem,
            criado_por=dados.criado_por,
            data_fim_prevista=(
                dados.data_fim_prevista
            )
        )

    except ValueError as erro:
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


# ============================================================
# CONSULTAR CICLO ATUAL
# ============================================================

@router.get(
    "/ciclos/atual"
)
def obter_ciclo_atual(
    cliente_id: int = Query(
        ...,
        ge=1
    ),
    armazem: str = Query(
        ...,
        min_length=1
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

        return consultar_ciclo_atual(
            cursor=cursor,
            cliente_id=cliente_id,
            armazem=armazem
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
# ============================================================
# SUGESTÕES OPERACIONAIS DO CICLO
# ============================================================

@router.get(
    "/ciclos/sugestoes"
)
def obter_sugestoes_rotativo(
    cliente_id: int = Query(
        ...,
        ge=1
    ),
    armazem: str = Query(
        ...,
        min_length=1
    ),
    limite: int = Query(
        default=5,
        ge=1,
        le=100
    ),
    tipo_sugestao: str | None = Query(
        default=None
    ),
    classificacao_risco: str | None = Query(
        default=None
    ),
    somente_pendentes: bool = Query(
        default=True
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

        return consultar_sugestoes_rotativo(
            cursor=cursor,
            cliente_id=cliente_id,
            armazem=armazem,
            limite=limite,
            tipo_sugestao=tipo_sugestao,
            classificacao_risco=classificacao_risco,
            somente_pendentes=somente_pendentes
        )

    except ValueError as erro:

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

# ============================================================
# PAINEL GERENCIAL DO CICLO ROTATIVO
# ============================================================

@router.get(
    "/ciclos/painel"
)
def obter_painel_rotativo(
    cliente_id: int = Query(
        ...,
        ge=1
    ),
    armazem: str = Query(
        ...,
        min_length=1
    ),
    limite_prioridades: int = Query(
        default=5,
        ge=1,
        le=50
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

        return consultar_painel_rotativo(
            cursor=cursor,
            cliente_id=cliente_id,
            armazem=armazem,
            limite_prioridades=limite_prioridades
        )

    except ValueError as erro:

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
# ============================================================
# TENDÊNCIAS DAS LOCALIZAÇÕES DO ROTATIVO
# ============================================================

@router.get(
    "/ciclos/tendencias"
)
def obter_tendencias_rotativo(
    cliente_id: int = Query(
        ...,
        ge=1
    ),
    armazem: str = Query(
        ...,
        min_length=1
    ),
    limite_historico: int = Query(
        default=6,
        ge=1,
        le=50
    ),
    somente_alertas: bool = Query(
        default=False
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

        return consultar_tendencias_rotativo(
            cursor=cursor,
            cliente_id=cliente_id,
            armazem=armazem,
            limite_historico=limite_historico,
            somente_alertas=somente_alertas
        )

    except ValueError as erro:

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
# ============================================================
# TRATATIVAS DAS DIVERGÊNCIAS DO ROTATIVO
# ============================================================

@router.get(
    "/ciclos/tratativas"
)
def obter_tratativas_rotativo(
    cliente_id: int = Query(
        ...,
        ge=1
    ),
    armazem: str = Query(
        ...,
        min_length=1
    ),
    somente_pendentes: bool = Query(
        default=False
    ),
    somente_recorrentes: bool = Query(
        default=False
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

        return consultar_tratativas_rotativo(
            cursor=cursor,
            cliente_id=cliente_id,
            armazem=armazem,
            somente_pendentes=somente_pendentes,
            somente_recorrentes=somente_recorrentes
        )

    except ValueError as erro:

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
# ============================================================
# FINALIZAR CICLO ROTATIVO
# ============================================================

@router.post(
    "/ciclos/{id_ciclo}/finalizar"
)
def finalizar_ciclo(
    id_ciclo: int,
    finalizado_por: str | None = Query(
        default=None
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

        resultado = finalizar_ciclo_rotativo(
            conn=conn,
            cursor=cursor,
            id_ciclo=id_ciclo,
            finalizado_por=finalizado_por
        )

        return resultado

    except ValueError as erro:
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
# ============================================================
# RESOLVER OCORRÊNCIA DE DIVERGÊNCIA
# ============================================================

@router.post(
    "/ciclos/tratativas/{id_ocorrencia}/resolver"
)
def resolver_tratativa_rotativo(
    id_ocorrencia: int,
    dados: ResolverOcorrenciaRequest
):
    uow = None
    conn = None
    cursor = None

    try:

        uow = SqlServerUnitOfWork()
        uow.open()
        conn = uow.connection
        cursor = uow.cursor

        return resolver_ocorrencia_rotativo(
            conn=conn,
            cursor=cursor,
            id_ocorrencia=id_ocorrencia,
            tipo_resolucao=dados.tipo_resolucao,
            observacao_resolucao=(
                dados.observacao_resolucao
            ),
            resolvido_por=dados.resolvido_por,
            id_inventario_resolucao=(
                dados.id_inventario_resolucao
            ),
            id_rodada_resolucao=(
                dados.id_rodada_resolucao
            )
        )

    except ValueError as erro:

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
# ============================================================
# CONTEXTO INTEGRADO DA LOCALIZAÇÃO
# ============================================================

@router.get(
    "/contexto/localizacao"
)
def obter_contexto_localizacao_rotativo(
    cliente_id: int = Query(
        ...,
        ge=1
    ),
    armazem: str = Query(
        ...,
        min_length=1
    ),
    localizacao: str = Query(
        ...,
        min_length=1
    ),
    limite_historico: int = Query(
        default=10,
        ge=1,
        le=100
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

        return montar_contexto_localizacao_rotativo(
            cursor=cursor,
            cliente_id=cliente_id,
            armazem=armazem,
            localizacao=localizacao,
            limite_historico=limite_historico
        )

    except ValueError as erro:

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

# ============================================================
# ORQUESTRAR INTELIGÊNCIA DO ROTATIVO
#
# Endpoint de teste/manual.
# Depois os eventos operacionais chamarão o mesmo service.
# ============================================================

@router.post(
    "/inteligencia/recalcular"
)
def recalcular_inteligencia_rotativo(
    cliente_id: int = Query(
        ...,
        ge=1
    ),
    armazem: str = Query(
        ...,
        min_length=1
    ),
    localizacao: str | None = Query(
        default=None
    ),
    usuario: str | None = Query(
        default=None
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

        return executar_orquestracao_rotativo(
            conn=conn,
            cursor=cursor,
            cliente_id=cliente_id,
            armazem=armazem,
            origem_evento="RECALCULO_MANUAL",
            localizacao=localizacao,
            usuario=usuario,
            limite_score_sugestao=50,
            quantidade_sugestoes=20,
            retornar_painel=True,
        )

    except ValueError as erro:

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