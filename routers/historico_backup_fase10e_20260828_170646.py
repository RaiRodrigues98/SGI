from datetime import date

from fastapi import (
    APIRouter,
    HTTPException,
    Query,
)

from database import get_connection

from services.historico_inventarios import (
    consultar_historico_inventarios,
)

from services.historico_itens import (
    consultar_historico_item,
)

from services.historico_localizacoes import (
    consultar_historico_localizacao,
)

router = APIRouter(
    prefix="/historico",
    tags=["Histórico e Rastreabilidade"]
)


# ============================================================
# HISTÓRICO DE INVENTÁRIOS
# ============================================================

@router.get(
    "/inventarios"
)
def listar_historico_inventarios(
    cliente_id: int | None = Query(
        default=None,
        ge=1
    ),
    tipo: str | None = Query(
        default=None
    ),
    status: str | None = Query(
        default=None
    ),
    data_inicio: date | None = Query(
        default=None
    ),
    data_fim: date | None = Query(
        default=None
    ),
    codigo_inventario: str | None = Query(
        default=None
    ),
    page: int = Query(
        default=1,
        ge=1
    ),
    page_size: int = Query(
        default=50,
        ge=1,
        le=200
    )
):

    conn = None
    cursor = None

    try:

        conn = get_connection()
        cursor = conn.cursor()

        resultado = (
            consultar_historico_inventarios(
                cursor=cursor,
                cliente_id=cliente_id,
                tipo=tipo,
                status=status,
                data_inicio=data_inicio,
                data_fim=data_fim,
                codigo_inventario=(
                    codigo_inventario
                ),
                page=page,
                page_size=page_size
            )
        )

        return resultado

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
# HISTÓRICO DE ITEM / LOTE
# ============================================================

@router.get(
    "/itens"
)
def listar_historico_item(
    codigo: str = Query(
        ...,
        min_length=1
    ),
    lote: str | None = Query(
        default=None
    ),
    cliente_id: int | None = Query(
        default=None,
        ge=1
    ),
    data_inicio: date | None = Query(
        default=None
    ),
    data_fim: date | None = Query(
        default=None
    )
):

    conn = None
    cursor = None

    try:

        conn = get_connection()
        cursor = conn.cursor()

        resultado = (
            consultar_historico_item(
                cursor=cursor,
                codigo=codigo,
                lote=lote,
                cliente_id=cliente_id,
                data_inicio=data_inicio,
                data_fim=data_fim
            )
        )

        return resultado

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
# HISTÓRICO DE LOCALIZAÇÃO
# ============================================================


@router.get(
    "/localizacoes"
)
def listar_historico_localizacao(
    localizacao: str = Query(
        ...,
        min_length=1
    ),
    cliente_id: int | None = Query(
        default=None,
        ge=1
    ),
    tipo: str | None = Query(
        default=None
    ),
    data_inicio: date | None = Query(
        default=None
    ),
    data_fim: date | None = Query(
        default=None
    )
):

    conn = None
    cursor = None

    try:

        conn = get_connection()
        cursor = conn.cursor()

        resultado = (
            consultar_historico_localizacao(
                cursor=cursor,
                localizacao=localizacao,
                cliente_id=cliente_id,
                tipo=tipo,
                data_inicio=data_inicio,
                data_fim=data_fim
            )
        )

        return resultado

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
# HISTÓRICO DE DIVERGÊNCIAS E RECORRÊNCIA
# ============================================================

from services.historico_divergencias import (
    consultar_historico_divergencias,
)


@router.get(
    "/divergencias"
)
def listar_historico_divergencias(
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
    tipo_inventario: str | None = Query(
        default=None
    ),
    data_inicio: date | None = Query(
        default=None
    ),
    data_fim: date | None = Query(
        default=None
    ),
    somente_recorrentes: bool = Query(
        default=False
    )
):

    conn = None
    cursor = None

    try:

        conn = get_connection()
        cursor = conn.cursor()

        return consultar_historico_divergencias(
            cursor=cursor,
            cliente_id=cliente_id,
            armazem=armazem,
            localizacao=localizacao,
            codigo=codigo,
            lote=lote,
            tipo_inventario=tipo_inventario,
            data_inicio=data_inicio,
            data_fim=data_fim,
            somente_recorrentes=(
                somente_recorrentes
            )
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