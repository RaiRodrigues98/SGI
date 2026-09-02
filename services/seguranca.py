from argon2 import PasswordHasher
from argon2.exceptions import (
    VerifyMismatchError,
    VerificationError,
    InvalidHashError,
)


# ============================================================
# PASSWORD HASHER
# ============================================================

_password_hasher = PasswordHasher()


# ============================================================
# GERAR HASH DA SENHA
# ============================================================

def gerar_hash_senha(
    senha: str
) -> str:

    senha = (
        str(senha)
        if senha is not None
        else ""
    )

    if not senha:

        raise ValueError(
            "Senha obrigatória."
        )

    return _password_hasher.hash(
        senha
    )


# ============================================================
# VERIFICAR SENHA
# ============================================================

def verificar_senha(
    senha: str,
    senha_hash: str
) -> bool:

    senha = (
        str(senha)
        if senha is not None
        else ""
    )

    senha_hash = (
        str(senha_hash)
        if senha_hash is not None
        else ""
    )

    if (
        not senha
        or
        not senha_hash
    ):
        return False

    try:

        return _password_hasher.verify(
            senha_hash,
            senha
        )

    except (
        VerifyMismatchError,
        VerificationError,
        InvalidHashError
    ):

        return False


# ============================================================
# VERIFICAR SE HASH PRECISA SER ATUALIZADO
#
# Útil futuramente no login:
# se alterarmos os parâmetros do Argon2, podemos gerar
# um novo hash após uma autenticação válida.
# ============================================================

def hash_precisa_atualizacao(
    senha_hash: str
) -> bool:

    senha_hash = (
        str(senha_hash)
        if senha_hash is not None
        else ""
    )

    if not senha_hash:
        return False

    try:

        return _password_hasher.check_needs_rehash(
            senha_hash
        )

    except (
        VerificationError,
        InvalidHashError
    ):

        return False