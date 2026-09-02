from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)

from database import get_connection

from dependencies.auth import (
    exigir_permissao,
)

from services.resultado_final import (
    consultar_resultado_final,
)


router = APIRouter(
    tags=["Resultado Final"]
)


# ============================================================
# CONSULTAR RESULTADO FINAL
#
# Permissão:
# ANALISE_VISUALIZAR
# ============================================================

@router.get(
    "/inventarios/{id_inventario}/resultado-final",
    dependencies=[
        Depends(
            exigir_permissao(
                "ANALISE_VISUALIZAR"
            )
        )
    ]
)
def obter_resultado_final(
    id_inventario: int
):

    # ========================================================
    # 1. VALIDA INVENTÁRIO
    # ========================================================

    if id_inventario <= 0:

        raise HTTPException(
            status_code=400,
            detail="Inventário inválido."
        )

    conn = None
    cursor = None

    try:

        # ====================================================
        # 2. CONEXÃO
        # ====================================================

        conn = get_connection()
        cursor = conn.cursor()

        # ====================================================
        # 3. RESULTADO FINAL
        # ====================================================

        return consultar_resultado_final(
            cursor=cursor,
            id_inventario=id_inventario
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