from fastapi import (
    APIRouter,
    HTTPException,
    Query,
)

from database import get_connection

from services.score_risco import (
    consultar_priorizacao_risco,
)


router = APIRouter(
    prefix="/risco",
    tags=["Risco e Priorização"]
)


# ============================================================
# SCORE DE RISCO E PRIORIZAÇÃO DE CONTAGEM
# ============================================================

@router.get(
    "/priorizacao"
)
def listar_priorizacao_risco(
    cliente_id: int | None = Query(
        default=None,
        ge=1
    ),
    armazem: str | None = Query(
        default=None
    ),
    localizacao: str | None = Query(
        default=None
    ),
    codigo: str | None = Query(
        default=None
    ),
    lote: str | None = Query(
        default=None
    ),
    classificacao: str | None = Query(
        default=None
    ),
    somente_prioritarios: bool = Query(
        default=False
    ),
    limite: int = Query(
        default=100,
        ge=1,
        le=500
    )
):
    conn = None
    cursor = None

    try:
        conn = get_connection()
        cursor = conn.cursor()

        return consultar_priorizacao_risco(
            cursor=cursor,
            cliente_id=cliente_id,
            armazem=armazem,
            localizacao=localizacao,
            codigo=codigo,
            lote=lote,
            classificacao=classificacao,
            somente_prioritarios=(
                somente_prioritarios
            ),
            limite=limite
        )

    except HTTPException:
        raise

    except Exception as erro:
        raise HTTPException(
            status_code=500,
            detail=str(erro)
        )

    finally:
        if cursor:
            cursor.close()

        if conn:
            conn.close()
