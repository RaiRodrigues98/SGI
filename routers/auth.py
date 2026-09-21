from fastapi import (
    APIRouter,
    HTTPException,
)

from domain.exceptions import (
    AuthenticationError,
    AuthorizationError,
    BusinessRuleViolation,
    ConflictError,
    NotFoundError,
)

from application.exceptions import (
    ApplicationError,
)

from infrastructure.database.unit_of_work import SqlServerUnitOfWork

from schemas.usuarios import (
    LoginEntrada,
    CadastroPublicoEntrada,
)

from services.auth import (
    autenticar_usuario,
    gerar_access_token,
    registrar_ultimo_login,
)

from services.usuarios import (
    criar_usuario,
    vincular_perfil_usuario,
)

from schemas.password_reset import (
    EsqueciSenhaEntrada,
    EsqueciSenhaResposta,
    RedefinirSenhaEntrada,
    RedefinirSenhaResposta,
)

from services.password_reset import (
    solicitar_redefinicao_senha,
    redefinir_senha_com_token,
)

from fastapi import Depends

from dependencies.auth import (
    obter_usuario_atual,
)
# ============================================================
# ROUTER
# ============================================================

router = APIRouter(
    prefix="/auth",
    tags=["Autenticação"]
)


# ============================================================
# LOGIN
#
# Fluxo:
#
# 1. Recebe login e senha
# 2. Localiza usuÃ¡rio
# 3. Verifica se estÃ¡ ativo
# 4. Valida senha Argon2
# 5. Carrega perfis
# 6. Carrega permissÃµes
# 7. Gera JWT
# 8. Atualiza UltimoLogin
# ============================================================

@router.post(
    "/login"
)
def login(
    dados: LoginEntrada
):

    uow = None
    conn = None
    cursor = None

    try:

        uow = SqlServerUnitOfWork()
        uow.open()
        conn = uow.connection
        cursor = uow.cursor

        # ====================================================
        # 1. AUTENTICA
        # ====================================================

        usuario = autenticar_usuario(
            cursor=cursor,
            login=dados.login,
            senha=dados.senha
        )

        # ====================================================
        # 2. GERA TOKEN
        # ====================================================

        token = gerar_access_token(
            usuario=usuario
        )

        # ====================================================
        # 3. REGISTRA ÃšLTIMO LOGIN
        # ====================================================

        registrar_ultimo_login(
            cursor=cursor,
            id_usuario=(
                usuario["id_usuario"]
            )
        )

        # ====================================================
        # 4. COMMIT
        # ====================================================

        uow.commit()

        # ====================================================
        # 5. RESPOSTA
        #
        # Nunca retorna:
        # - senha
        # - SenhaHash
        # ====================================================

        return {
            "sucesso":
                True,

            "mensagem":
                "Login realizado com sucesso.",

            "access_token":
                token["access_token"],

            "token_type":
                token["token_type"],

            "expires_in":
                token["expires_in"],

            "expira_em":
                token["expira_em"],

            "usuario": {
                "id_usuario":
                    usuario["id_usuario"],

                "nome":
                    usuario["nome"],

                "login":
                    usuario["login"],

                "email":
                    usuario["email"],

                "perfis":
                    usuario["perfis"],

                "permissoes":
                    usuario["permissoes"]
            }
        }

    except AuthenticationError as erro:

        if conn:
            uow.rollback()

        raise HTTPException(
            status_code=401,
            detail=str(erro)
        )

    except AuthorizationError as erro:

        if conn:
            uow.rollback()

        raise HTTPException(
            status_code=403,
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
# USUÃRIO AUTENTICADO
#
# Endpoint inicial para validar o Bearer Token.
# ============================================================

@router.get(
    "/me"
)
def meu_usuario(
    usuario=Depends(
        obter_usuario_atual
    )
):

    return {
        "autenticado":
            True,

        "usuario": {
            "id_usuario":
                usuario["id_usuario"],

            "nome":
                usuario["nome"],

            "login":
                usuario["login"],

            "email":
                usuario["email"],

            "perfis":
                usuario["perfis"],

            "permissoes":
                usuario["permissoes"]
        }
    }

# ============================================================
# CADASTRO PUBLICO
#
# Todo cadastro publico:
# - nasce ATIVO
# - recebe somente o perfil OPERADOR
# - nao pode escolher perfil ou permissoes
# ============================================================

@router.post(
    "/cadastro"
)
def cadastro_publico(
    dados: CadastroPublicoEntrada
):

    uow = None
    conn = None

    try:

        uow = SqlServerUnitOfWork()
        uow.open()

        conn = uow.connection
        cursor = uow.cursor

        # ====================================================
        # 1. LOCALIZA PERFIL OPERADOR
        # ====================================================

        cursor.execute(
            """
            SELECT TOP 1
                ID_Perfil,
                Nome

            FROM dbo.Perfis

            WHERE
                UPPER(
                    LTRIM(
                        RTRIM(Nome)
                    )
                ) = 'OPERADOR'

                AND Ativo = 1

            ORDER BY
                ID_Perfil
            """
        )

        perfil = cursor.fetchone()

        if not perfil:
            raise ApplicationError(
                "Perfil OPERADOR ativo nÃ£o encontrado."
            )

        # ====================================================
        # 2. CRIA USUARIO ATIVO
        # ====================================================

        resultado = criar_usuario(
            cursor=cursor,
            nome=dados.nome,
            login=dados.login,
            email=dados.email,
            senha=dados.senha,
            ativo=True
        )

        id_usuario = int(
            resultado["usuario"]["id_usuario"]
        )

        # ====================================================
        # 3. VINCULA OPERADOR
        # ====================================================

        vincular_perfil_usuario(
            cursor=cursor,
            id_usuario=id_usuario,
            id_perfil=int(
                perfil.ID_Perfil
            )
        )

        # ====================================================
        # 4. COMMIT UNICO
        # ====================================================

        uow.commit()

        return {
            "sucesso": True,
            "mensagem": (
                "Cadastro realizado com sucesso. "
                "VocÃª jÃ¡ pode acessar o SGI."
            ),
            "usuario": resultado["usuario"],
            "perfil": {
                "id_perfil":
                    int(perfil.ID_Perfil),
                "nome":
                    str(perfil.Nome)
            }
        }

    except BusinessRuleViolation as erro:

        if conn:
            uow.rollback()

        raise HTTPException(
            status_code=400,
            detail=str(erro)
        )

    except ConflictError as erro:

        if conn:
            uow.rollback()

        raise HTTPException(
            status_code=409,
            detail=str(erro)
        )

    except NotFoundError as erro:

        if conn:
            uow.rollback()

        raise HTTPException(
            status_code=404,
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
# ESQUECI MINHA SENHA
#
# Fluxo:
# 1. Recebe e-mail
# 2. Se o e-mail existir e o usuario estiver ativo,
#    gera token, persiste o HASH e envia o link por e-mail
# 3. SEMPRE responde 200 (evita enumeracao de usuarios)
# ============================================================

@router.post(
    "/esqueci-senha",
    response_model=EsqueciSenhaResposta
)
def esqueci_senha(
    dados: EsqueciSenhaEntrada
):

    uow = None
    conn = None
    cursor = None

    try:

        uow = SqlServerUnitOfWork()
        uow.open()
        conn = uow.connection
        cursor = uow.cursor

        resultado = solicitar_redefinicao_senha(
            cursor=cursor,
            email=dados.email
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

    except ConflictError as erro:

        if conn:
            uow.rollback()

        raise HTTPException(
            status_code=409,
            detail=str(erro)
        )

    except NotFoundError as erro:

        if conn:
            uow.rollback()

        raise HTTPException(
            status_code=404,
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
# REDEFINIR SENHA COM TOKEN
#
# Fluxo:
# 1. Recebe token + nova senha
# 2. Valida hash do token, expiracao e uso unico
# 3. Atualiza SenhaHash do usuario
# 4. Marca token como utilizado
# ============================================================

@router.post(
    "/reset-senha",
    response_model=RedefinirSenhaResposta
)
def reset_senha(
    dados: RedefinirSenhaEntrada
):

    uow = None
    conn = None
    cursor = None

    try:

        uow = SqlServerUnitOfWork()
        uow.open()
        conn = uow.connection
        cursor = uow.cursor

        resultado = redefinir_senha_com_token(
            cursor=cursor,
            token=dados.token,
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

    except ConflictError as erro:

        if conn:
            uow.rollback()

        raise HTTPException(
            status_code=409,
            detail=str(erro)
        )

    except NotFoundError as erro:

        if conn:
            uow.rollback()

        raise HTTPException(
            status_code=404,
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
