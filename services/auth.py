from datetime import (
    datetime,
    timedelta,
    timezone,
)

import os

from fastapi import HTTPException
from domain.exceptions import AuthenticationError, AuthorizationError
from jose import (
    JWTError,
    jwt,
)

from services.seguranca import (
    verificar_senha,
    hash_precisa_atualizacao,
    gerar_hash_senha,
)

from services.usuarios import (
    listar_perfis_usuario,
    listar_permissoes_usuario,
)

# ============================================================
# CONFIGURAÇÃO JWT
#
# Em produção, JWT_SECRET deve obrigatoriamente vir
# de variável de ambiente.
# ============================================================

JWT_SECRET = os.getenv(
    "JWT_SECRET",
    "sgi-chave-desenvolvimento-alterar-em-producao"
)

JWT_ALGORITHM = "HS256"

JWT_EXPIRACAO_MINUTOS = int(
    os.getenv(
        "JWT_EXPIRACAO_MINUTOS",
        "480"
    )
)


# ============================================================
# BUSCAR USUÁRIO PARA AUTENTICAÇÃO
#
# Esta função acessa SenhaHash internamente.
# O hash nunca deve ser retornado ao frontend.
# ============================================================

def _buscar_usuario_login(
    cursor,
    login: str
):

    login = (
        str(login).strip().lower()
        if login is not None
        else ""
    )

    if not login:

        return None

    cursor.execute(
        """
        SELECT TOP 1
            ID_Usuario,
            Nome,
            Login,
            Email,
            SenhaHash,
            Ativo,
            UltimoLogin

        FROM dbo.Usuarios

        WHERE
            LOWER(
                LTRIM(
                    RTRIM(Login)
                )
            ) = ?
        """,
        login
    )

    return cursor.fetchone()


# ============================================================
# AUTENTICAR USUÁRIO
# ============================================================

def autenticar_usuario(
    cursor,
    login: str,
    senha: str
):

    login = (
        str(login).strip().lower()
        if login is not None
        else ""
    )

    senha = (
        str(senha)
        if senha is not None
        else ""
    )

    if not login or not senha:

                raise AuthenticationError(
            "Login ou senha inválidos."
        )

    usuario = _buscar_usuario_login(
        cursor=cursor,
        login=login
    )

    # ========================================================
    # NÃO INFORMAMOS SE FOI LOGIN OU SENHA QUE FALHOU
    # ========================================================

    if not usuario:

                raise AuthenticationError(
            "Login ou senha inválidos."
        )

    # ========================================================
    # USUÁRIO INATIVO
    # ========================================================

    if not bool(
        usuario.Ativo
    ):

                raise AuthorizationError(
            "Usuário inativo."
        )

    # ========================================================
    # VALIDA SENHA ARGON2
    # ========================================================

    senha_valida = verificar_senha(
        senha=senha,
        senha_hash=usuario.SenhaHash
    )

    if not senha_valida:

                raise AuthenticationError(
            "Login ou senha inválidos."
        )

    # ========================================================
    # ATUALIZA HASH SE OS PARÂMETROS DO ARGON2 MUDAREM
    # ========================================================

    if hash_precisa_atualizacao(
        usuario.SenhaHash
    ):

        novo_hash = gerar_hash_senha(
            senha
        )

        cursor.execute(
            """
            UPDATE dbo.Usuarios

            SET
                SenhaHash = ?,
                DataHoraAtualizacao =
                    SYSDATETIME()

            WHERE ID_Usuario = ?
            """,
            (
                novo_hash,
                usuario.ID_Usuario
            )
        )

    # ========================================================
    # PERFIS
    # ========================================================

    perfis = listar_perfis_usuario(
        cursor=cursor,
        id_usuario=usuario.ID_Usuario
    )

    # ========================================================
    # PERMISSÕES EFETIVAS
    # ========================================================

    permissoes = listar_permissoes_usuario(
        cursor=cursor,
        id_usuario=usuario.ID_Usuario
    )

    return {
        "id_usuario":
            usuario.ID_Usuario,

        "nome":
            usuario.Nome,

        "login":
            usuario.Login,

        "email":
            usuario.Email,

        "ativo":
            bool(usuario.Ativo),

        "perfis":
            perfis,

        "permissoes":
            permissoes
    }


# ============================================================
# GERAR ACCESS TOKEN
# ============================================================

def gerar_access_token(
    usuario: dict
):

    agora = datetime.now(
        timezone.utc
    )

    expiracao = (
        agora
        +
        timedelta(
            minutes=JWT_EXPIRACAO_MINUTOS
        )
    )

    codigos_permissoes = [
        item["codigo"]
        for item in usuario["permissoes"]
    ]

    nomes_perfis = [
        item["nome"]
        for item in usuario["perfis"]
    ]

    payload = {
        # Subject do JWT
        "sub":
            str(
                usuario["id_usuario"]
            ),

        "login":
            usuario["login"],

        "perfis":
            nomes_perfis,

        "permissoes":
            codigos_permissoes,

        "iat":
            agora,

        "exp":
            expiracao
    }

    token = jwt.encode(
        payload,
        JWT_SECRET,
        algorithm=JWT_ALGORITHM
    )

    return {
        "access_token":
            token,

        "token_type":
            "bearer",

        "expires_in":
            JWT_EXPIRACAO_MINUTOS * 60,

        "expira_em":
            expiracao
    }


# ============================================================
# REGISTRAR ÚLTIMO LOGIN
# ============================================================

def registrar_ultimo_login(
    cursor,
    id_usuario: int
):

    cursor.execute(
        """
        UPDATE dbo.Usuarios

        SET
            UltimoLogin =
                SYSDATETIME()

        WHERE ID_Usuario = ?
        """,
        id_usuario
    )


# ============================================================
# DECODIFICAR / VALIDAR TOKEN
#
# Será utilizado posteriormente nas rotas protegidas.
# ============================================================

def decodificar_token(
    token: str
):

    if not token:

                raise AuthenticationError(
            "Token de autenticação ausente."
        )

    try:

        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[
                JWT_ALGORITHM
            ]
        )

    except JWTError:

                raise AuthenticationError(
            "Token inválido ou expirado."
        )

    id_usuario = payload.get(
        "sub"
    )

    if not id_usuario:

                raise AuthenticationError(
            "Token inválido."
        )

    try:

        id_usuario = int(
            id_usuario
        )

    except (
        TypeError,
        ValueError
    ):

                raise AuthenticationError(
            "Token inválido."
        )

    return {
        "id_usuario":
            id_usuario,

        "login":
            payload.get(
                "login"
            ),

        "perfis":
            payload.get(
                "perfis",
                []
            ),

        "permissoes":
            payload.get(
                "permissoes",
                []
            )
    }