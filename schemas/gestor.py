from typing import Optional

from pydantic import BaseModel, Field


class DecisaoGestorEntrada(BaseModel):

    codigo: str = Field(
        ...,
        min_length=1,
        max_length=60
    )

    lote: Optional[str] = Field(
        default="",
        max_length=60
    )

    decisao: str = Field(
        ...,
        min_length=1,
        max_length=30
    )

    quantidade_aprovada: Optional[float] = Field(
        default=None,
        ge=0
    )

    justificativa: Optional[str] = Field(
        default=None,
        max_length=500
    )
