from pydantic import BaseModel, Field


class InventarioCriacaoEntrada(BaseModel):

    codigo_inventario: str = Field(
        ...,
        min_length=1,
        max_length=60
    )

    tipo: str = Field(
        ...,
        min_length=1,
        max_length=20
    )

    cliente_id: int = Field(
        ...,
        gt=0
    )

    cliente: str = Field(
        ...,
        min_length=1,
        max_length=120
    )

    descricao: str | None = Field(
        default=None,
        max_length=255
    )

    armazem: str = Field(
        ...,
        min_length=1,
        max_length=60
    )
