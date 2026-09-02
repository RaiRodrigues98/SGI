from fastapi import (
    APIRouter,
    HTTPException,
)

from database import get_connection

from schemas.usuarios import (
    LoginEntrada,
)

from services.auth import (
    autenticar_usuario,
    gerar_access_token,
    registrar_ultimo_login,
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
# 2. Localiza usuário
# 3. Verifica se está ativo
# 4. Valida senha Argon2
# 5. Carrega perfis
# 6. Carrega permissões
# 7. Gera JWT
# 8. Atualiza UltimoLogin
# ============================================================

@router.post(
    "/login"
)
def login(
    dados: LoginEntrada
):

    conn = None
    cursor = None

    try:

        conn = get_connection()
        cursor = conn.cursor()

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
        # 3. REGISTRA ÚLTIMO LOGIN
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

        conn.commit()

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
# USUÁRIO AUTENTICADO
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