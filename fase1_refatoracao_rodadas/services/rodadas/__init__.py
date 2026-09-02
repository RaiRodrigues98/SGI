"""
Pacote de domínio operacional de rodadas.

A refatoração é incremental. Durante a transição,
services.rodadas_service permanece como fachada compatível.
"""

from .itens import _inserir_rodada_item
from .localizacoes import (
    _buscar_localizacoes_snapshot_item,
    _buscar_localizacoes_contagem_item,
    _buscar_localizacoes_para_item,
    _inserir_rodada_localizacao,
    sincronizar_localizacoes_recontagem,
)

__all__ = [
    "_inserir_rodada_item",
    "_buscar_localizacoes_snapshot_item",
    "_buscar_localizacoes_contagem_item",
    "_buscar_localizacoes_para_item",
    "_inserir_rodada_localizacao",
    "sincronizar_localizacoes_recontagem",
]
