from pydantic import BaseModel, Field


class EncaminharGestorEntrada(BaseModel):

    usuario: str = Field(
        ...,
        min_length=1,
        max_length=100
    )