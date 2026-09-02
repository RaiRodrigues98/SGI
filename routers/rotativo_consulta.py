from fastapi import (
    APIRouter,
    HTTPException,
    Query,
)

from database import get_connection

from services.rotativo_consulta import (
    consultar_localizacoes_ciclo,
)


router = APIRouter(
    prefix="/rotativo",
    tags=["Controle Rotativo"]
)


@router.get(
    "/ciclos/localizacoes"
)
def listar_localizacoes_ciclo(
    cliente_id: int = Query(
        ...,
        ge=1
    ),

    armazem: str = Query(
        ...,
        min_length=1
    ),

    id_ciclo: int | None = Query(
        default=None,
        ge=1
    ),

    status: str | None = Query(
        default=None
    ),

    classificacao_risco: str | None = Query(
        default=None
    ),

    somente_sugeridas: bool = Query(
        default=False
    ),

    somente_pendentes: bool = Query(
        default=False
    ),

    ordenar_por: str = Query(
        default="PRIORIDADE"
    )
):
    conn = None
    cursor = None

    try:
        conn = get_connection()
        cursor = conn.cursor()

        return consultar_localizacoes_ciclo(
            cursor=cursor,
            cliente_id=cliente_id,
            armazem=armazem,
            id_ciclo=id_ciclo,
            status=status,
            classificacao_risco=(
                classificacao_risco
            ),
            somente_sugeridas=(
                somente_sugeridas
            ),
            somente_pendentes=(
                somente_pendentes
            ),
            ordenar_por=ordenar_por
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
        if cursor:
            cursor.close()

        if conn:
            conn.close()
