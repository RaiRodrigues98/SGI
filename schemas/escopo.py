from pydantic import BaseModel


class EscopoLocalizacoesEntrada(BaseModel):
    localizacoes: list[str]
    criado_por: str | None = None
