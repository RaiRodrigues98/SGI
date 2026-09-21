from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from domain.exceptions import (
    BusinessRuleViolation,
    ConflictError,
    NotFoundError,
)

from infrastructure.database.unit_of_work import SqlServerUnitOfWork

from domain.exceptions import BusinessRuleViolation

from dependencies.auth import (
    exigir_permissao,
)

from schemas.inventarios import (
    InventarioCancelamentoEntrada,
    InventarioCriacaoEntrada,
)

from services.inventarios import (
    cancelar_inventario,
    criar_inventario,
)


from services.notificacoes import (
    criar_por_permissao,
)


router = APIRouter(
    tags=["Inventários"]
)


# ============================================================
# CRIAR INVENTÁRIO
# ============================================================


# ============================================================
# CLIENTES / ARMAZENS DISPONIVEIS
# ============================================================

@router.get(
    "/inventarios/clientes-disponiveis"
)
def listar_clientes_disponiveis(
    usuario_atual=Depends(
        exigir_permissao(
            "INVENTARIO_CRIAR"
        )
    )
):
    uow = None

    try:
        uow = SqlServerUnitOfWork()
        uow.open()

        cursor = uow.cursor

        cursor.execute(
            """
            SELECT DISTINCT
                E.ClienteId,
                C.Nome AS Cliente,
                E.cArmazem AS Armazem
            FROM AlzarsiLog.dbo.Estoque E
            INNER JOIN AlzarsiLog.dbo.Cliente C
                ON C.Id = E.ClienteId
            WHERE
                E.ClienteId IS NOT NULL
                AND E.cArmazem IS NOT NULL
                AND LTRIM(RTRIM(E.cArmazem)) <> ''
            ORDER BY
                C.Nome,
                E.cArmazem
            """
        )

        linhas = cursor.fetchall()

        return [
            {
                "cliente_id": int(linha.ClienteId),
                "cliente": str(linha.Cliente).strip(),
                "armazem": str(linha.Armazem).strip(),
            }
            for linha in linhas
        ]

    except Exception as erro:
        raise HTTPException(
            status_code=500,
            detail=str(erro)
        )

    finally:
        if uow:
            uow.close()


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

    uow = None
    conn = None
    cursor = None

    try:

        uow = SqlServerUnitOfWork()
        uow.open()
        conn = uow.connection
        cursor = uow.cursor

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

        id_inventario_criado = int(
            resultado["id_inventario"]
        )

        resumo_notificacoes = criar_por_permissao(
            cursor=cursor,
            codigo_permissao="CONTAGEM_EXECUTAR",
            id_usuario_ator=int(
                usuario_atual["id_usuario"]
            ),
            tipo="INVENTARIO_CRIADO",
            titulo="Novo invent\u00e1rio criado",
            mensagem=(
                f"O invent\u00e1rio "
                f"{resultado['codigo_inventario']} "
                f"foi criado e aguarda a "
                f"defini\u00e7\u00e3o do escopo."
            ),
            prioridade="MEDIA",
            entidade_tipo="INVENTARIO",
            entidade_id=id_inventario_criado,
            id_inventario=id_inventario_criado,
            url=(
                f"/inventarios/"
                f"{id_inventario_criado}"
            ),
            chave_dedupe=(
                "INVENTARIO_CRIADO:"
                f"{id_inventario_criado}"
            ),
            excluir_ator=False,
        )

        resultado["notificacoes"] = (
            resumo_notificacoes
        )

        uow.commit()

        return resultado
    except ConflictError as erro:

        if conn:
            uow.rollback()

        raise HTTPException(
            status_code=409,
            detail=str(erro)
        )
    
    except BusinessRuleViolation as erro:

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



# ============================================================
# CANCELAR INVENTARIO
# ============================================================

@router.patch(
    "/inventarios/{id_inventario}/cancelar"
)
def cancelar(
    id_inventario: int,
    dados: InventarioCancelamentoEntrada,
    usuario_atual=Depends(
        exigir_permissao(
            "INVENTARIO_FINALIZAR"
        )
    )
):

    if id_inventario <= 0:
        raise HTTPException(
            status_code=400,
            detail="Invent\u00e1rio inv\u00e1lido."
        )

    usuario = (
        str(
            usuario_atual[
                "login"
            ]
        )
        .strip()
    )

    uow = None
    conn = None

    try:

        uow = SqlServerUnitOfWork()
        uow.open()

        conn = uow.connection
        cursor = uow.cursor

        resultado = cancelar_inventario(
            cursor=cursor,
            id_inventario=id_inventario,
            motivo=dados.motivo,
            usuario=usuario,
        )

        motivo_notificacao = str(
            resultado.get(
                "motivo_cancelamento"
            )
            or dados.motivo
            or ""
        ).strip()

        resumo_notificacoes = criar_por_permissao(
            cursor=cursor,
            codigo_permissao="CONTAGEM_EXECUTAR",
            id_usuario_ator=int(
                usuario_atual["id_usuario"]
            ),
            tipo="INVENTARIO_CANCELADO",
            titulo="Invent\u00e1rio cancelado",
            mensagem=(
                f"O invent\u00e1rio "
                f"{resultado['codigo_inventario']} "
                f"foi cancelado. "
                f"Motivo: {motivo_notificacao}"
            ),
            prioridade="ALTA",
            entidade_tipo="INVENTARIO",
            entidade_id=id_inventario,
            id_inventario=id_inventario,
            url=(
                f"/historico?"
                f"inventario={id_inventario}"
                f"&aba=visao-geral"
            ),
            chave_dedupe=(
                "INVENTARIO_CANCELADO:"
                f"{id_inventario}"
            ),
            excluir_ator=False,
        )

        resultado["notificacoes"] = (
            resumo_notificacoes
        )

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
