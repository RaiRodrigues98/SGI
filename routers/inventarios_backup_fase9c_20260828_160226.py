from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)

from database import get_connection

from dependencies.auth import (
    exigir_permissao,
)

from schemas.inventarios import (
    InventarioCriacaoEntrada,
)

from services.inventarios import (
    criar_inventario,
)


router = APIRouter(
    tags=["Inventários"]
)


# ============================================================
# CRIAR INVENTÁRIO
# ============================================================

@router.post(
    "/inventarios"
)
def criar(
    dados: InventarioCriacaoEntrada,
    usuario_atual=Depends(
        exigir_permissao(
            "INVENTARIO_CRIAR"
        )
    )
):

    usuario = (
        str(
            usuario_atual[
                "login"
            ]
        )
        .strip()
    )

    conn = None
    cursor = None

    try:

        conn = get_connection()
        cursor = conn.cursor()

        resultado = criar_inventario(
            cursor=cursor,
            codigo_inventario=(
                dados.codigo_inventario
            ),
            tipo=dados.tipo,
            cliente_id=dados.cliente_id,
            cliente=dados.cliente,
            descricao=dados.descricao,
            armazem=dados.armazem,
            usuario=usuario
        )

        conn.commit()

        return resultado

    except HTTPException:

        if conn:
            conn.rollback()

        raise

    except Exception as erro:

        if conn:
            conn.rollback()

        raise HTTPException(
            status_code=500,
            detail=str(erro)
        )

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()
