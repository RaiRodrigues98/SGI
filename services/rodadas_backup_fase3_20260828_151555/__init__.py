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

from .candidatos_rotativo import (
    _validar_divergencias_r1_rotativo_tratadas,
    _buscar_colunas_tabela,
    _resolver_coluna_quantidade_rotativo,
    _buscar_candidatos_r2_rotativo,
)

__all__ += [
    "_validar_divergencias_r1_rotativo_tratadas",
    "_buscar_colunas_tabela",
    "_resolver_coluna_quantidade_rotativo",
    "_buscar_candidatos_r2_rotativo",
]
