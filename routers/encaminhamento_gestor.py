from fastapi import APIRouter, Depends, HTTPException
from domain.exceptions import BusinessRuleViolation, NotFoundError

from infrastructure.database.unit_of_work import SqlServerUnitOfWork

from dependencies.auth import (
    exigir_permissao,
)

from schemas.encaminhamento_gestor import (
    EncaminharGestorEntrada,
)

from services.encaminhamento_gestor import (
    encaminhar_inventario_para_gestor,
)


from services.notificacoes import (
    criar_por_permissao,
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

    uow = None
    conn = None
    cursor = None

    try:

        uow = SqlServerUnitOfWork()
        uow.open()
        conn = uow.connection
        cursor = uow.cursor

        resultado = (
            encaminhar_inventario_para_gestor(
                cursor=cursor,
                id_inventario=id_inventario,
                usuario=usuario
            )
        )

        if not resultado.get("ja_encaminhado", False):
            id_rodada = int(
                resultado.get("id_rodada") or 0
            )

            codigo_inventario = str(
                resultado.get("codigo_inventario")
                or id_inventario
            )

            total_pendentes = int(
                resultado.get("total_itens_pendentes")
                or 0
            )

            resumo_notificacoes = criar_por_permissao(
                cursor=cursor,
                codigo_permissao="GESTOR_DECIDIR",
                id_usuario_ator=int(
                    usuario_atual["id_usuario"]
                ),
                tipo="GESTOR_ANALISE_SOLICITADA",
                titulo="Invent\u00e1rio aguardando decis\u00e3o",
                mensagem=(
                    f"O invent\u00e1rio {codigo_inventario} "
                    f"foi encaminhado ao gestor com "
                    f"{total_pendentes} item(ns) pendente(s)."
                ),
                prioridade="CRITICA",
                entidade_tipo="INVENTARIO",
                entidade_id=id_inventario,
                id_inventario=id_inventario,
                url=f"/inventarios/{id_inventario}",
                chave_dedupe=(
                    "GESTOR_ANALISE_SOLICITADA:"
                    f"{id_inventario}:{id_rodada}"
                ),
                excluir_ator=False,
            )

            resultado["notificacoes"] = resumo_notificacoes
        else:
            resultado["notificacoes"] = {
                "destinatarios_localizados": 0,
                "notificacoes_criadas": 0,
            }

        # ====================================================
        # O SERVICE NÃO REALIZA COMMIT
        # ====================================================

        uow.commit()

        return resultado

    except BusinessRuleViolation as erro:
        if conn:
            uow.rollback()

        raise HTTPException(
            status_code=400,
            detail=str(erro)
        )

    except NotFoundError as erro:
        if conn:
            uow.rollback()

        raise HTTPException(
            status_code=404,
            detail=str(erro)
        )

    except HTTPException:

        if conn:
            uow.rollback()

        raise

    except Exception as erro:

        if conn:
            uow.rollback()

        raise HTTPException(
            status_code=500,
            detail=str(erro)
        )

    finally:

        if uow:
            uow.close()