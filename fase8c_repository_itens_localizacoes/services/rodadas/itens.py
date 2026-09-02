"""
Operações de itens vinculados às rodadas.

Fase 1 da refatoração de services.rodadas_service.

IMPORTANTE:
- extração estrutural;
- nenhuma regra de negócio alterada;
- SQL preservado;
- assinatura das funções preservada.
"""

from services.rodadas.repositories.item_repository import (
    inserir_item_se_ausente,
)



def _normalizar_texto(valor):

    if valor is None:
        return ""

    return str(valor).strip()


def _normalizar_lote(valor):

    return _normalizar_texto(valor)


def _inserir_rodada_item(
    cursor,
    id_inventario: int,
    id_rodada: int,
    codigo: str,
    lote: str,
    motivo: str
):

    codigo = _normalizar_texto(
        codigo
    )

    lote = _normalizar_lote(
        lote
    )

    inserir_item_se_ausente(
        cursor=cursor,
        id_inventario=id_inventario,
        id_rodada=id_rodada,
        codigo=codigo,
        lote=lote,
        motivo=motivo
    )
