from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from domain.exceptions import NotFoundError

from database import get_connection

from dependencies.auth import (
    exigir_permissao,
)

from services.consultas_operacionais import (
    listar_inventarios,
    consultar_inventario,
    consultar_rodada_atual,
    consultar_localizacoes_inventario,
    consultar_contagem_atual,
    consultar_detalhe_localizacao,
    buscar_produto_contagem,
)

from services.configuracoes_inventario import (
    obter_configuracao_completa_por_inventario,
)

from services.configuracoes_operacionais import (
    obter_configuracao_operacional_inventario,
)


router = APIRouter(
    tags=["Consultas"]
)


# ============================================================
# LISTAR INVENTÁRIOS
#
# Permissão:
# INVENTARIO_VISUALIZAR
#
# Utilizado para listar os inventários disponíveis.
# ============================================================

@router.get(
    "/inventarios",
    dependencies=[
        Depends(
            exigir_permissao(
                "INVENTARIO_VISUALIZAR"
            )
        )
    ]
)
def listar(
    status: str | None = None,
    tipo: str | None = None,
    cliente_id: int | None = None
):

    conn = None
    cursor = None

    try:

        conn = get_connection()
        cursor = conn.cursor()

        return listar_inventarios(
            cursor=cursor,
            status=status,
            tipo=tipo,
            cliente_id=cliente_id
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
# DETALHE DO INVENTÁRIO
#
# Permissão:
# INVENTARIO_VISUALIZAR
# ============================================================

@router.get(
    "/inventarios/{id_inventario}",
    dependencies=[
        Depends(
            exigir_permissao(
                "INVENTARIO_VISUALIZAR"
            )
        )
    ]
)
def detalhe(
    id_inventario: int
):

    if id_inventario <= 0:

        raise HTTPException(
            status_code=400,
            detail="Inventário inválido."
        )

    conn = None
    cursor = None

    try:

        conn = get_connection()
        cursor = conn.cursor()

        return consultar_inventario(
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
# RODADA ATUAL
#
# Permissão:
# CONTAGEM_EXECUTAR
#
# Necessária para o operador descobrir a rodada operacional
# do inventário antes de iniciar a contagem.
# ============================================================

@router.get(
    "/inventarios/{id_inventario}/rodada-atual",
    dependencies=[
        Depends(
            exigir_permissao(
                "CONTAGEM_EXECUTAR"
            )
        )
    ]
)
def rodada_atual(
    id_inventario: int
):

    if id_inventario <= 0:

        raise HTTPException(
            status_code=400,
            detail="Inventário inválido."
        )

    conn = None
    cursor = None

    try:

        conn = get_connection()
        cursor = conn.cursor()

        return consultar_rodada_atual(
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
# LOCALIZAÇÕES DO INVENTÁRIO
#
# Permissão:
# CONTAGEM_EXECUTAR
#
# Faz parte do fluxo operacional da contagem.
# ============================================================

@router.get(
    "/inventarios/{id_inventario}/localizacoes",
    dependencies=[
        Depends(
            exigir_permissao(
                "CONTAGEM_EXECUTAR"
            )
        )
    ]
)
def localizacoes(
    id_inventario: int
):

    if id_inventario <= 0:

        raise HTTPException(
            status_code=400,
            detail="Inventário inválido."
        )

    conn = None
    cursor = None

    try:

        conn = get_connection()
        cursor = conn.cursor()

        return consultar_localizacoes_inventario(
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
# CONTAGEM ATUAL
#
# Permissão:
# CONTAGEM_EXECUTAR
#
# Retorna somente a visão operacional da rodada atual.
# ============================================================

@router.get(
    "/inventarios/{id_inventario}/contagem-atual",
    dependencies=[
        Depends(
            exigir_permissao(
                "CONTAGEM_EXECUTAR"
            )
        )
    ]
)
def contagem_atual(
    id_inventario: int
):

    if id_inventario <= 0:

        raise HTTPException(
            status_code=400,
            detail="Inventário inválido."
        )

    conn = None
    cursor = None

    try:

        conn = get_connection()
        cursor = conn.cursor()

        return consultar_contagem_atual(
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
# DETALHE OPERACIONAL DA LOCALIZAÇÃO
#
# Permissão:
# CONTAGEM_EXECUTAR
#
# Mantém o fluxo operacional e a contagem cega.
# ============================================================

@router.get(
    "/inventarios/{id_inventario}/localizacoes/{localizacao}",
    dependencies=[
        Depends(
            exigir_permissao(
                "CONTAGEM_EXECUTAR"
            )
        )
    ]
)
def detalhe_localizacao(
    id_inventario: int,
    localizacao: str
):

    if id_inventario <= 0:

        raise HTTPException(
            status_code=400,
            detail="Inventário inválido."
        )

    localizacao = (
        str(localizacao).strip()
        if localizacao is not None
        else ""
    )

    if not localizacao:

        raise HTTPException(
            status_code=400,
            detail="Localização obrigatória."
        )

    conn = None
    cursor = None

    try:

        conn = get_connection()
        cursor = conn.cursor()

        return consultar_detalhe_localizacao(
            cursor=cursor,
            id_inventario=id_inventario,
            localizacao=localizacao
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
# BUSCAR / VALIDAR PRODUTO PARA CONTAGEM
#
# Permissão:
# CONTAGEM_EXECUTAR
#
# Utilizado durante a bipagem do código.
# ============================================================

@router.get(
    "/inventarios/{id_inventario}/produtos/{codigo}",
    dependencies=[
        Depends(
            exigir_permissao(
                "CONTAGEM_EXECUTAR"
            )
        )
    ]
)
def buscar_produto(
    id_inventario: int,
    codigo: str
):

    if id_inventario <= 0:

        raise HTTPException(
            status_code=400,
            detail="Inventário inválido."
        )

    codigo = (
        str(codigo).strip()
        if codigo is not None
        else ""
    )

    if not codigo:

        raise HTTPException(
            status_code=400,
            detail="Código obrigatório."
        )

    conn = None
    cursor = None

    try:

        conn = get_connection()
        cursor = conn.cursor()

        return buscar_produto_contagem(
            cursor=cursor,
            id_inventario=id_inventario,
            codigo=codigo
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
# CONFIGURAÇÃO COMPLETA DO INVENTÁRIO
#
# Permissão:
# CONFIGURACAO_VISUALIZAR
#
# Esta visão pode conter regras administrativas e de gestão,
# portanto não faz parte da consulta operacional do operador.
# ============================================================

@router.get(
    "/inventarios/{id_inventario}/configuracao",
    dependencies=[
        Depends(
            exigir_permissao(
                "CONFIGURACAO_VISUALIZAR"
            )
        )
    ]
)
def consultar_configuracao(
    id_inventario: int
):

    if id_inventario <= 0:

        raise HTTPException(
            status_code=400,
            detail="Inventário inválido."
        )

    conn = None
    cursor = None

    try:

        conn = get_connection()
        cursor = conn.cursor()

        return (
            obter_configuracao_completa_por_inventario(
                cursor=cursor,
                id_inventario=id_inventario
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


# ============================================================
# CONFIGURAÇÃO OPERACIONAL DO INVENTÁRIO
#
# Permissão:
# CONTAGEM_EXECUTAR
#
# Esta configuração é utilizada pelo frontend durante o fluxo
# de contagem para saber como tratar:
#
# - localização
# - código
# - lote
# - quantidade
# - contagem cega
#
# O backend continua sendo responsável pela validação final.
# ============================================================

@router.get(
    "/inventarios/{id_inventario}/configuracao-operacional",
    dependencies=[
        Depends(
            exigir_permissao(
                "CONTAGEM_EXECUTAR"
            )
        )
    ]
)
def configuracao_operacional_inventario(
    id_inventario: int
):

    if id_inventario <= 0:

        raise HTTPException(
            status_code=400,
            detail="Inventário inválido."
        )

    conn = None
    cursor = None

    try:

        conn = get_connection()
        cursor = conn.cursor()

        return obter_configuracao_operacional_inventario(
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