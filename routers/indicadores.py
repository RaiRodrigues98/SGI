from fastapi import APIRouter, HTTPException, Query
from domain.exceptions import NotFoundError

from database import get_connection

from services.indicadores_operacionais import (
    obter_acompanhamento_inventario,
    obter_acompanhamento_localizacoes,
    obter_produtividade_inventario,
    obter_movimentacao_12_meses,
    obter_valoracao_estoque,
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

# ============================================================
# ACOMPANHAMENTO OPERACIONAL POR LOCALIZACAO
# ============================================================

@router.get(
    "/{id_inventario}/indicadores/acompanhamento/localizacoes"
)
def consultar_acompanhamento_localizacoes(
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

        return obter_acompanhamento_localizacoes(
            cursor=cursor,
            id_inventario=id_inventario,
            numero_rodada=rodada
        )

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

# ============================================================
# MOVIMENTACAO DOS ULTIMOS 12 MESES
# MOVIMENTACAO_12_MESES_V1
# ============================================================

@router.get(
    "/{id_inventario}/indicadores/movimentacao-12-meses"
)
def consultar_movimentacao_12_meses(
    id_inventario: int
):

    conn = None
    cursor = None

    try:

        conn = get_connection()
        cursor = conn.cursor()

        return obter_movimentacao_12_meses(
            cursor=cursor,
            id_inventario=id_inventario
        )

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
# VALORACAO DO ESTOQUE
# VALORACAO_ESTOQUE_V1
# ============================================================

@router.get(
    "/{id_inventario}/indicadores/valoracao-estoque"
)
def consultar_valoracao_estoque(
    id_inventario: int
):
    conn = None
    cursor = None

    try:
        conn = get_connection()
        cursor = conn.cursor()

        return obter_valoracao_estoque(
            cursor=cursor,
            id_inventario=id_inventario
        )

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
