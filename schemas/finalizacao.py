from pydantic import BaseModel


class FinalizarInventarioEntrada(BaseModel):
    """
    Body intencionalmente vazio.

    O usuário responsável pela finalização não é recebido
    do frontend. Ele é obtido pelo usuário autenticado
    através de Depends(exigir_permissao(...)).
    """

    pass
