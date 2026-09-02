from pydantic import BaseModel, Field


class ConfiguracaoOperacionalEntrada(BaseModel):

    validar_localizacao_escopo: bool

    permitir_localizacao_vazia: bool

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
