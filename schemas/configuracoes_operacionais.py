from typing import Literal

from pydantic import BaseModel, Field


class ConfiguracaoOperacionalEntrada(BaseModel):

    validar_localizacao_escopo: bool

    permitir_localizacao_vazia: bool

    permitir_reabertura_localizacao: bool

    permitir_alteracao_escopo_apos_snapshot: bool

    codigo_livre: bool

    permitir_codigo_nao_cadastrado: bool

    permitir_item_fora_localizacao: bool

    lote_obrigatorio_se_existir: bool

    validar_lote_codigo: bool

    validar_lote_localizacao: bool

    quantidade_minima: float = Field(
        ge=0
    )

    quantidade_maxima: float = Field(
        gt=0
    )

    contagem_cega: bool

    considera_localizacao_conciliacao: bool

    recontagem_por_localizacao: bool

    rodadas_iniciais: int = Field(
        ge=1
    )

    max_rodadas: int = Field(
        ge=1
    )

    permitir_gestor_antecipado: bool

    limite_itens_gestor_antecipado: int = Field(
        ge=0
    )

    divergencia_bloqueia_finalizacao: bool

    ativa: bool = True

class ConfiguracaoRodadaEntrada(BaseModel):

    numero_rodada: int = Field(
        ge=1
    )

    tipo_rodada: Literal[
        "COMPLETA",
        "DIVERGENCIAS",
        "GESTOR",
    ]

class CriarConfiguracaoInventarioEntrada(
    ConfiguracaoOperacionalEntrada
):

    rodadas: list[
        ConfiguracaoRodadaEntrada
    ]


class ConfiguracoesRodadasEntrada(BaseModel):

    rodadas_iniciais: int = Field(
        ge=1
    )

    max_rodadas: int = Field(
        ge=1
    )

    rodadas: list[
        ConfiguracaoRodadaEntrada
    ]



class AtualizarConfiguracaoInventarioAplicadaEntrada(
    ConfiguracaoOperacionalEntrada
):
    versao_esperada: int = Field(
        ge=1
    )

    motivo: str = Field(
        min_length=5,
        max_length=500
    )

    localizacao_obrigatoria: bool
    localizacao_validar_estoque: bool

    codigo_obrigatorio: bool
    codigo_validar_estoque: bool

    lote_obrigatorio_quando_existir: bool
    lote_validar_codigo: bool

    quantidade_obrigatoria: bool

    quantidade_operacional_minima: float = Field(
        ge=0
    )

    quantidade_operacional_maxima: float = Field(
        gt=0
    )

    rodadas: list[
        ConfiguracaoRodadaEntrada
    ]
