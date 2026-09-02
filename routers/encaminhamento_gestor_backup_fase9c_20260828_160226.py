from fastapi import APIRouter, Depends, HTTPException

from database import get_connection

from dependencies.auth import (
    exigir_permissao,
)

from schemas.encaminhamento_gestor import (
    EncaminharGestorEntrada,
)

from services.encaminhamento_gestor import (
    encaminhar_inventario_para_gestor,
)


router = APIRouter(
    tags=["Gestor"]
)


# ============================================================
# ENCAMINHAR INVENTÁRIO PARA ANÁLISE GERENCIAL
# ============================================================

@router.post(
    "/inventarios/{id_inventario}/encaminhar-gestor"
)
def encaminhar_gestor(
    id_inventario: int,
    dados: EncaminharGestorEntrada,
    usuario_atual=Depends(
        exigir_permissao(
            "GESTOR_DECIDIR"
        )
    )
):

    if id_inventario <= 0:

        raise HTTPException(
            status_code=400,
            detail="Inventário inválido."
        )

    # ========================================================
    # USUÁRIO AUTENTICADO
    #
    # A auditoria vem do JWT. Não confiamos no usuário
    # informado pelo frontend.
    # ========================================================

    usuario = (
        str(usuario_atual["login"]).strip()
    )

    conn = None
    cursor = None

    try:

        conn = get_connection()
        cursor = conn.cursor()

        resultado = (
            encaminhar_inventario_para_gestor(
                cursor=cursor,
                id_inventario=id_inventario,
                usuario=usuario
            )
        )

        # ====================================================
        # O SERVICE NÃO REALIZA COMMIT
        # ====================================================

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