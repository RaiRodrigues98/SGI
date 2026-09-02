from fastapi import (
    APIRouter,
    HTTPException,
)

from database import get_connection

from schemas.usuarios import (
    UsuarioCriacaoEntrada,
    UsuarioAtualizacaoEntrada,
    UsuarioAlterarSenhaEntrada,
    UsuarioPerfilEntrada,
)

from services.usuarios import (
    criar_usuario,
    listar_usuarios,
    consultar_usuario,
    atualizar_usuario,
    alterar_senha_usuario,
    listar_perfis_usuario,
    vincular_perfil_usuario,
    remover_perfil_usuario,
    listar_permissoes_usuario,
)

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from dependencies.auth import (
    exigir_permissao,
)
# ============================================================
# ROUTER
# ============================================================

router = APIRouter(
    prefix="/usuarios",
    tags=["Usuários"],
    dependencies=[
        Depends(
            exigir_permissao(
                "USUARIO_GERENCIAR"
            )
        )
    ]
)

# ============================================================
# CRIAR USUÁRIO
# ============================================================

@router.post("")
def criar(
    dados: UsuarioCriacaoEntrada
):

    conn = None
    cursor = None

    try:

        conn = get_connection()
        cursor = conn.cursor()

        resultado = criar_usuario(
            cursor=cursor,
            nome=dados.nome,
            login=dados.login,
            email=dados.email,
            senha=dados.senha,
            ativo=dados.ativo
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


# ============================================================
# LISTAR USUÁRIOS
#
# Exemplos:
#
# GET /usuarios
# GET /usuarios?ativo=true
# GET /usuarios?ativo=false
# ============================================================

@router.get("")
def listar(
    ativo: bool | None = None
):

    conn = None
    cursor = None

    try:

        conn = get_connection()
        cursor = conn.cursor()

        return listar_usuarios(
            cursor=cursor,
            ativo=ativo
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
# CONSULTAR USUÁRIO
# ============================================================

@router.get(
    "/{id_usuario}"
)
def consultar(
    id_usuario: int
):

    if id_usuario <= 0:

        raise HTTPException(
            status_code=400,
            detail="Usuário inválido."
        )

    conn = None
    cursor = None

    try:

        conn = get_connection()
        cursor = conn.cursor()

        return consultar_usuario(
            cursor=cursor,
            id_usuario=id_usuario
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
# ATUALIZAR USUÁRIO
# ============================================================

@router.put(
    "/{id_usuario}"
)
def atualizar(
    id_usuario: int,
    dados: UsuarioAtualizacaoEntrada
):

    if id_usuario <= 0:

        raise HTTPException(
            status_code=400,
            detail="Usuário inválido."
        )

    conn = None
    cursor = None

    try:

        conn = get_connection()
        cursor = conn.cursor()

        resultado = atualizar_usuario(
            cursor=cursor,
            id_usuario=id_usuario,
            nome=dados.nome,
            email=dados.email,
            ativo=dados.ativo
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


# ============================================================
# ALTERAR SENHA
# ============================================================

@router.patch(
    "/{id_usuario}/senha"
)
def alterar_senha(
    id_usuario: int,
    dados: UsuarioAlterarSenhaEntrada
):

    if id_usuario <= 0:

        raise HTTPException(
            status_code=400,
            detail="Usuário inválido."
        )

    conn = None
    cursor = None

    try:

        conn = get_connection()
        cursor = conn.cursor()

        resultado = alterar_senha_usuario(
            cursor=cursor,
            id_usuario=id_usuario,
            nova_senha=dados.nova_senha
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


# ============================================================
# LISTAR PERFIS DO USUÁRIO
# ============================================================

@router.get(
    "/{id_usuario}/perfis"
)
def listar_perfis(
    id_usuario: int
):

    if id_usuario <= 0:

        raise HTTPException(
            status_code=400,
            detail="Usuário inválido."
        )

    conn = None
    cursor = None

    try:

        conn = get_connection()
        cursor = conn.cursor()

        return {
            "id_usuario":
                id_usuario,

            "perfis":
                listar_perfis_usuario(
                    cursor=cursor,
                    id_usuario=id_usuario
                )
        }

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
# VINCULAR PERFIL
# ============================================================

@router.post(
    "/{id_usuario}/perfis"
)
def vincular_perfil(
    id_usuario: int,
    dados: UsuarioPerfilEntrada
):

    if id_usuario <= 0:

        raise HTTPException(
            status_code=400,
            detail="Usuário inválido."
        )

    conn = None
    cursor = None

    try:

        conn = get_connection()
        cursor = conn.cursor()

        resultado = vincular_perfil_usuario(
            cursor=cursor,
            id_usuario=id_usuario,
            id_perfil=dados.id_perfil
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


# ============================================================
# REMOVER PERFIL
#
# Não exclui o registro fisicamente.
# Desativa o vínculo em UsuarioPerfis.
# ============================================================

@router.delete(
    "/{id_usuario}/perfis/{id_perfil}"
)
def remover_perfil(
    id_usuario: int,
    id_perfil: int
):

    if id_usuario <= 0:

        raise HTTPException(
            status_code=400,
            detail="Usuário inválido."
        )

    if id_perfil <= 0:

        raise HTTPException(
            status_code=400,
            detail="Perfil inválido."
        )

    conn = None
    cursor = None

    try:

        conn = get_connection()
        cursor = conn.cursor()

        resultado = remover_perfil_usuario(
            cursor=cursor,
            id_usuario=id_usuario,
            id_perfil=id_perfil
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


# ============================================================
# PERMISSÕES EFETIVAS DO USUÁRIO
# ============================================================

@router.get(
    "/{id_usuario}/permissoes"
)
def listar_permissoes(
    id_usuario: int
):

    if id_usuario <= 0:

        raise HTTPException(
            status_code=400,
            detail="Usuário inválido."
        )

    conn = None
    cursor = None

    try:

        conn = get_connection()
        cursor = conn.cursor()

        permissoes = listar_permissoes_usuario(
            cursor=cursor,
            id_usuario=id_usuario
        )

        return {
            "id_usuario":
                id_usuario,

            "total":
                len(permissoes),

            "permissoes":
                permissoes
        }

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