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

from application.exceptions import ApplicationError

from infrastructure.database.unit_of_work import (
    SqlServerUnitOfWork,
)

from dependencies.auth import (
    exigir_permissao,
    obter_usuario_atual,
)

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
    listar_perfis_disponiveis,
    vincular_perfil_usuario,
    remover_perfil_usuario,
    listar_permissoes_usuario,
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

    uow = None
    conn = None
    cursor = None

    try:

        uow = SqlServerUnitOfWork()
        uow.open()

        conn = uow.connection
        cursor = uow.cursor

        resultado = criar_usuario(
            cursor=cursor,
            nome=dados.nome,
            login=dados.login,
            email=dados.email,
            senha=dados.senha,
            ativo=dados.ativo
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

    except ConflictError as erro:

        if conn:
            uow.rollback()

        raise HTTPException(
            status_code=409,
            detail=str(erro)
        )

    except ApplicationError as erro:

        if conn:
            uow.rollback()

        raise HTTPException(
            status_code=500,
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
# LISTAR USUÁRIOS
# ============================================================

@router.get("")
def listar(
    ativo: bool | None = None
):

    uow = None

    try:

        uow = SqlServerUnitOfWork()
        uow.open()

        return listar_usuarios(
            cursor=uow.cursor,
            ativo=ativo
        )

    except BusinessRuleViolation as erro:

        raise HTTPException(
            status_code=400,
            detail=str(erro)
        )

    except NotFoundError as erro:

        raise HTTPException(
            status_code=404,
            detail=str(erro)
        )

    except ConflictError as erro:

        raise HTTPException(
            status_code=409,
            detail=str(erro)
        )

    except ApplicationError as erro:

        raise HTTPException(
            status_code=500,
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

        if uow:
            uow.close()


# ============================================================
# CONSULTAR USUÁRIO
# ============================================================

# ============================================================
# PERFIS DISPONIVEIS
# ============================================================

@router.get(
    "/perfis/disponiveis"
)
def consultar_perfis_disponiveis():

    uow = None

    try:

        uow = SqlServerUnitOfWork()
        uow.open()

        perfis = listar_perfis_disponiveis(
            cursor=uow.cursor
        )

        return {
            "total": len(perfis),
            "perfis": perfis
        }

    finally:

        if uow:
            uow.close()


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

    uow = None

    try:

        uow = SqlServerUnitOfWork()
        uow.open()

        return consultar_usuario(
            cursor=uow.cursor,
            id_usuario=id_usuario
        )

    except BusinessRuleViolation as erro:

        raise HTTPException(
            status_code=400,
            detail=str(erro)
        )

    except NotFoundError as erro:

        raise HTTPException(
            status_code=404,
            detail=str(erro)
        )

    except ConflictError as erro:

        raise HTTPException(
            status_code=409,
            detail=str(erro)
        )

    except ApplicationError as erro:

        raise HTTPException(
            status_code=500,
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

        if uow:
            uow.close()


# ============================================================
# ATUALIZAR USUÁRIO
# ============================================================

@router.put(
    "/{id_usuario}"
)
def atualizar(
    id_usuario: int,
    dados: UsuarioAtualizacaoEntrada,
    usuario_atual=Depends(obter_usuario_atual)
):

    if id_usuario <= 0:

        raise HTTPException(
            status_code=400,
            detail="Usuário inválido."
        )

    if (
        id_usuario == usuario_atual["id_usuario"]
        and not dados.ativo
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Nao e permitido desativar "
                "o proprio usuario."
            )
        )

    uow = None
    conn = None

    try:

        uow = SqlServerUnitOfWork()
        uow.open()

        conn = uow.connection

        resultado = atualizar_usuario(
            cursor=uow.cursor,
            id_usuario=id_usuario,
            nome=dados.nome,
            email=dados.email,
            ativo=dados.ativo
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

    except ConflictError as erro:

        if conn:
            uow.rollback()

        raise HTTPException(
            status_code=409,
            detail=str(erro)
        )

    except ApplicationError as erro:

        if conn:
            uow.rollback()

        raise HTTPException(
            status_code=500,
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

    uow = None
    conn = None

    try:

        uow = SqlServerUnitOfWork()
        uow.open()

        conn = uow.connection

        resultado = alterar_senha_usuario(
            cursor=uow.cursor,
            id_usuario=id_usuario,
            nova_senha=dados.nova_senha
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

    except ConflictError as erro:

        if conn:
            uow.rollback()

        raise HTTPException(
            status_code=409,
            detail=str(erro)
        )

    except ApplicationError as erro:

        if conn:
            uow.rollback()

        raise HTTPException(
            status_code=500,
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

    uow = None

    try:

        uow = SqlServerUnitOfWork()
        uow.open()

        return {
            "id_usuario":
                id_usuario,

            "perfis":
                listar_perfis_usuario(
                    cursor=uow.cursor,
                    id_usuario=id_usuario
                )
        }

    except BusinessRuleViolation as erro:

        raise HTTPException(
            status_code=400,
            detail=str(erro)
        )

    except NotFoundError as erro:

        raise HTTPException(
            status_code=404,
            detail=str(erro)
        )

    except ConflictError as erro:

        raise HTTPException(
            status_code=409,
            detail=str(erro)
        )

    except ApplicationError as erro:

        raise HTTPException(
            status_code=500,
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

        if uow:
            uow.close()


# ============================================================
# VINCULAR PERFIL
# ============================================================

@router.post(
    "/{id_usuario}/perfis"
)
def vincular_perfil(
    id_usuario: int,
    dados: UsuarioPerfilEntrada,
    usuario_atual=Depends(obter_usuario_atual)
):

    if id_usuario == usuario_atual["id_usuario"]:
        raise HTTPException(
            status_code=400,
            detail=(
                "Nao e permitido alterar os proprios perfis."
            )
        )

    if id_usuario <= 0:

        raise HTTPException(
            status_code=400,
            detail="Usuário inválido."
        )

    uow = None
    conn = None

    try:

        uow = SqlServerUnitOfWork()
        uow.open()

        conn = uow.connection

        resultado = vincular_perfil_usuario(
            cursor=uow.cursor,
            id_usuario=id_usuario,
            id_perfil=dados.id_perfil
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

    except ConflictError as erro:

        if conn:
            uow.rollback()

        raise HTTPException(
            status_code=409,
            detail=str(erro)
        )

    except ApplicationError as erro:

        if conn:
            uow.rollback()

        raise HTTPException(
            status_code=500,
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
# REMOVER PERFIL
# ============================================================

@router.delete(
    "/{id_usuario}/perfis/{id_perfil}"
)
def remover_perfil(
    id_usuario: int,
    id_perfil: int,
    usuario_atual=Depends(obter_usuario_atual)
):

    if id_usuario == usuario_atual["id_usuario"]:
        raise HTTPException(
            status_code=400,
            detail=(
                "Nao e permitido alterar os proprios perfis."
            )
        )

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

    uow = None
    conn = None

    try:

        uow = SqlServerUnitOfWork()
        uow.open()

        conn = uow.connection

        resultado = remover_perfil_usuario(
            cursor=uow.cursor,
            id_usuario=id_usuario,
            id_perfil=id_perfil
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

    except ConflictError as erro:

        if conn:
            uow.rollback()

        raise HTTPException(
            status_code=409,
            detail=str(erro)
        )

    except ApplicationError as erro:

        if conn:
            uow.rollback()

        raise HTTPException(
            status_code=500,
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

    uow = None

    try:

        uow = SqlServerUnitOfWork()
        uow.open()

        permissoes = listar_permissoes_usuario(
            cursor=uow.cursor,
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

    except BusinessRuleViolation as erro:

        raise HTTPException(
            status_code=400,
            detail=str(erro)
        )

    except NotFoundError as erro:

        raise HTTPException(
            status_code=404,
            detail=str(erro)
        )

    except ConflictError as erro:

        raise HTTPException(
            status_code=409,
            detail=str(erro)
        )

    except ApplicationError as erro:

        raise HTTPException(
            status_code=500,
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

        if uow:
            uow.close()