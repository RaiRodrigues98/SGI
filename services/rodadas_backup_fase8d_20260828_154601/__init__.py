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

from .candidatos_oficial import (
    _buscar_candidatos_r3,
    _buscar_candidatos_recontagem_anterior,
)

__all__ += [
    "_buscar_candidatos_r3",
    "_buscar_candidatos_recontagem_anterior",
]

from .gestor import (
    _buscar_itens_nova_recontagem_gestor,
    _existem_decisoes_gestor_ativas,
    _buscar_candidatos_gestor,
)

__all__ += [
    "_buscar_itens_nova_recontagem_gestor",
    "_existem_decisoes_gestor_ativas",
    "_buscar_candidatos_gestor",
]

from .lifecycle import (
    _finalizar_rodada_atual,
)

from .finalizacao_rotativo import (
    _encerrar_inventario_rotativo_apos_r1_sem_recontagem,
    _encerrar_inventario_rotativo_apos_r2,
)

__all__ += [
    "_finalizar_rodada_atual",
    "_encerrar_inventario_rotativo_apos_r1_sem_recontagem",
    "_encerrar_inventario_rotativo_apos_r2",
]

from .preview import (
    visualizar_proxima_rodada,
)

__all__ += [
    "visualizar_proxima_rodada",
]

from .criacao import (
    criar_proxima_rodada,
)

__all__ += [
    "criar_proxima_rodada",
]
