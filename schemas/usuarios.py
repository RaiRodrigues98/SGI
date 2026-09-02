from pydantic import BaseModel, EmailStr, Field


# ============================================================
# CRIAR USUÁRIO
# ============================================================

class UsuarioCriacaoEntrada(BaseModel):

    nome: str = Field(
        ...,
        min_length=2,
        max_length=150
    )

    login: str = Field(
        ...,
        min_length=3,
        max_length=100
    )

    email: EmailStr | None = None

    senha: str = Field(
        ...,
        min_length=8,
        max_length=128
    )

    ativo: bool = True


# ============================================================
# ATUALIZAR USUÁRIO
# ============================================================

class UsuarioAtualizacaoEntrada(BaseModel):

    nome: str = Field(
        ...,
        min_length=2,
        max_length=150
    )

    email: EmailStr | None = None

    ativo: bool


# ============================================================
# ALTERAR SENHA
# ============================================================

class UsuarioAlterarSenhaEntrada(BaseModel):

    nova_senha: str = Field(
        ...,
        min_length=8,
        max_length=128
    )


# ============================================================
# VINCULAR PERFIL
# ============================================================

class UsuarioPerfilEntrada(BaseModel):

    id_perfil: int = Field(
        ...,
        gt=0
    )


# ============================================================
# LOGIN
#
# Vamos usar depois no módulo de autenticação.
# ============================================================

class LoginEntrada(BaseModel):

    login: str = Field(
        ...,
        min_length=1,
        max_length=100
    )

    senha: str = Field(
        ...,
        min_length=1,
        max_length=128
    )