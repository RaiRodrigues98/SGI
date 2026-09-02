from typing import Optional

from pydantic import BaseModel, Field


# ============================================================
# INICIAR LOCALIZAÇÃO
# ============================================================

class LocalizacaoEntrada(BaseModel):

    id_inventario: int = Field(
        ...,
        gt=0
    )

    id_rodada: int = Field(
        ...,
        gt=0
    )

    localizacao: str = Field(
        ...,
        min_length=1,
        max_length=50
    )


# ============================================================
# SALVAR CONTAGEM
# ============================================================

class ContagemEntrada(BaseModel):

    id_sessao: int = Field(
        ...,
        gt=0
    )

    codigo: str = Field(
        ...,
        min_length=1,
        max_length=60
    )

    lote: Optional[str] = Field(
        default=None,
        max_length=60
    )

    quantidade: float = Field(
        ...,
        gt=0
    )


# ============================================================
# ENCERRAR SESSÃO / LOCALIZAÇÃO
#
# localizacao_vazia:
#
# False
# → comportamento normal
#
# True
# → operador confirma explicitamente que não existe
#   nenhum item físico na posição.
# ============================================================

class EncerrarSessaoEntrada(BaseModel):

    id_sessao: int = Field(
        ...,
        gt=0
    )

    localizacao_vazia: bool = False