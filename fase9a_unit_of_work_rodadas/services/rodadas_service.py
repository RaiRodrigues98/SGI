"""
Fachada de compatibilidade para serviços de rodadas.

Após a Fase 7, as implementações ficam em services.rodadas.*,
mas imports históricos de services.rodadas_service continuam válidos.
"""

from services.rodadas import (
    _inserir_rodada_item,
    _buscar_localizacoes_snapshot_item,
    _buscar_localizacoes_contagem_item,
    _buscar_localizacoes_para_item,
    _inserir_rodada_localizacao,
    sincronizar_localizacoes_recontagem,
)

from services.rodadas.candidatos_rotativo import (
    _validar_divergencias_r1_rotativo_tratadas,
    _buscar_colunas_tabela,
    _resolver_coluna_quantidade_rotativo,
    _buscar_candidatos_r2_rotativo,
)

from services.rodadas.candidatos_oficial import (
    _buscar_candidatos_r3,
    _buscar_candidatos_recontagem_anterior,
)

from services.rodadas.gestor import (
    _buscar_itens_nova_recontagem_gestor,
    _existem_decisoes_gestor_ativas,
    _buscar_candidatos_gestor,
)

from services.rodadas.lifecycle import (
    _finalizar_rodada_atual,
)

from services.rodadas.finalizacao_rotativo import (
    _encerrar_inventario_rotativo_apos_r1_sem_recontagem,
    _encerrar_inventario_rotativo_apos_r2,
)

from services.rodadas.preview import (
    visualizar_proxima_rodada,
)

from services.rodadas.criacao import (
    criar_proxima_rodada,
)


def _normalizar_texto(valor):

    if valor is None:
        return ""

    return str(valor).strip()


def _normalizar_lote(valor):

    return _normalizar_texto(valor)


def _normalizar_localizacao(valor):

    return (
        _normalizar_texto(valor)
        .upper()
    )


__all__ = [
    "criar_proxima_rodada",
    "visualizar_proxima_rodada",
    "sincronizar_localizacoes_recontagem",
    "_inserir_rodada_item",
    "_buscar_localizacoes_snapshot_item",
    "_buscar_localizacoes_contagem_item",
    "_buscar_localizacoes_para_item",
    "_inserir_rodada_localizacao",
    "_validar_divergencias_r1_rotativo_tratadas",
    "_buscar_colunas_tabela",
    "_resolver_coluna_quantidade_rotativo",
    "_buscar_candidatos_r2_rotativo",
    "_buscar_candidatos_r3",
    "_buscar_candidatos_recontagem_anterior",
    "_buscar_itens_nova_recontagem_gestor",
    "_existem_decisoes_gestor_ativas",
    "_buscar_candidatos_gestor",
    "_finalizar_rodada_atual",
    "_encerrar_inventario_rotativo_apos_r1_sem_recontagem",
    "_encerrar_inventario_rotativo_apos_r2",
]
