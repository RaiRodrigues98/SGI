from pydantic import BaseModel


class DecisaoRotativoEntrada(BaseModel):
    id_rodada: int
    localizacao: str
    codigo: str
    lote: str | None = None
    decisao: str
    justificativa: str | None = None