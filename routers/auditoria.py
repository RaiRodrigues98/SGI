from fastapi import APIRouter, HTTPException, Path, Query

from database import get_connection
from domain.exceptions import BusinessRuleViolation
from services.auditoria import consultar_auditoria_inventario


router = APIRouter(
    prefix="/auditoria",
    tags=["Auditoria"],
)


@router.get("/inventarios/{id_inventario}")
def obter_auditoria_inventario(
    id_inventario: int = Path(..., ge=1),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
):
    conn = None
    cursor = None

    try:
        conn = get_connection()
        cursor = conn.cursor()

        return consultar_auditoria_inventario(
            cursor=cursor,
            id_inventario=id_inventario,
            page=page,
            page_size=page_size,
        )

    except BusinessRuleViolation as erro:
        raise HTTPException(status_code=400, detail=str(erro))

    except HTTPException:
        raise

    except Exception as erro:
        raise HTTPException(status_code=500, detail=str(erro))

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
