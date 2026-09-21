from pydantic import BaseModel, EmailStr, Field


# ============================================================
# SOLICITAR RECUPERACAO
# ============================================================

class EsqueciSenhaEntrada(BaseModel):

    email: EmailStr = Field(
        ...,
        max_length=200
    )


class EsqueciSenhaResposta(BaseModel):

    sucesso: bool

    mensagem: str


# ============================================================
# REDEFINIR SENHA
# ============================================================

class RedefinirSenhaEntrada(BaseModel):

    token: str = Field(
        ...,
        min_length=20,
        max_length=256
    )

    nova_senha: str = Field(
        ...,
        min_length=8,
        max_length=128
    )


class RedefinirSenhaResposta(BaseModel):

    sucesso: bool

    mensagem: str
