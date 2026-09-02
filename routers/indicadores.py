from fastapi import APIRouter, HTTPException, Query
from domain.exceptions import NotFoundError

from database import get_connection

from services.indicadores_operacionais import (
    obter_acompanhamento_inventario,
)
from services.indicadores_operacionais import (
    obter_acompanhamento_inventario,
    obter_acompanhamento_localizacoes,
    obter_produtividade_inventario,
)

router = APIRouter(
    prefix="/inventarios",
    tags=["Indicadores"]
)


# ============================================================
# ACOMPANHAMENTO OPERACIONAL DO INVENTÁRIO
# ============================================================

@router.get(
    "/{id_inventario}/indicadores/acompanhamento"
)
def consultar_acompanhamento_operacional(
    id_inventario: int,
    rodada: int | None = Query(
        default=None,
        ge=1
    )
):

    conn = None
    cursor = None

    try:

        conn = get_connection()

        cursor = conn.cursor()

        resultado = (
            obter_acompanhamento_inventario(
                cursor=cursor,
                id_inventario=id_inventario,
                numero_rodada=rodada
            )
        )

        return resultado

    except NotFoundError as erro:

        raise HTTPException(
            status_code=404,
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

        if cursor:
            cursor.close()

        if conn:
            conn.close()

# ============================================================
# TEMPO E PRODUTIVIDADE OPERACIONAL
# ============================================================

@router.get(
    "/{id_inventario}/indicadores/produtividade"
)
def consultar_produtividade_operacional(
    id_inventario: int,
    rodada: int | None = Query(
        default=None,
        ge=1
    )
):

    conn = None
    cursor = None

    try:

        conn = get_connection()
        cursor = conn.cursor()

        resultado = obter_produtividade_inventario(
            cursor=cursor,
            id_inventario=id_inventario,
            numero_rodada=rodada
        )

        return resultado

    except NotFoundError as erro:

        raise HTTPException(
            status_code=404,
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

        if cursor:
            cursor.close()

        if conn:
            conn.close()