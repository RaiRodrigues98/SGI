from domain.exceptions import BusinessRuleViolation, NotFoundError
from fastapi import HTTPException


# ============================================================
# NORMALIZAÇÃO
# ============================================================

def _normalizar_texto(valor):

    if valor is None:
        return ""

    return str(valor).strip()


def _normalizar_tipo(valor):

    return (
        _normalizar_texto(valor)
        .upper()
    )


# ============================================================
# CONFIGURAÇÃO PADRÃO
#
# Utilizada caso determinada configuração opcional ainda
# não exista para o cliente/tipo.
#
# IMPORTANTE:
# lote_selecao_automatica permanece SEMPRE False.
# ============================================================

CONFIGURACAO_PADRAO = {

    "localizacao_obrigatoria": True,
    "localizacao_validar_estoque": True,

    "codigo_obrigatorio": True,
    "codigo_validar_estoque": False,

    "lote_obrigatorio_quando_existir": True,
    "lote_validar_codigo": True,
    "lote_selecao_automatica": False,

    "quantidade_obrigatoria": True,
    "quantidade_minima": 0,
    "quantidade_maxima": 999,
}


# ============================================================
# VERIFICA EXISTÊNCIA DA TABELA
# ============================================================

def _validar_tabela_configuracao(
    cursor
):

    cursor.execute(
        """
        SELECT OBJECT_ID(
            'dbo.ConfiguracoesOperacionaisInventario',
            'U'
        )
        """
    )

    tabela = cursor.fetchone()[0]

    if tabela is None:

        raise HTTPException(
            status_code=500,
            detail=(
                "A tabela "
                "dbo.ConfiguracoesOperacionaisInventario "
                "ainda não foi criada."
            )
        )


# ============================================================
# BUSCAR CONFIGURAÇÃO
# ============================================================

def obter_configuracao_operacional(
    cursor,
    cliente_id: int,
    tipo_inventario: str
):

    if cliente_id <= 0:

                raise BusinessRuleViolation(
            "Cliente inválido."
        )

    tipo = _normalizar_tipo(
        tipo_inventario
    )

    if tipo not in (
        "OFICIAL",
        "ROTATIVO"
    ):

                raise BusinessRuleViolation(
            "Tipo de inventário inválido. Utilize OFICIAL ou ROTATIVO."
        )

    _validar_tabela_configuracao(
        cursor
    )

    cursor.execute(
        """
        SELECT TOP 1

            ID_ConfiguracaoOperacional,
            ClienteId,
            TipoInventario,

            LocalizacaoObrigatoria,
            LocalizacaoValidarEstoque,

            CodigoObrigatorio,
            CodigoValidarEstoque,

            LoteObrigatorioQuandoExistir,
            LoteValidarCodigo,

            QuantidadeObrigatoria,
            QuantidadeMinima,
            QuantidadeMaxima,

            Ativo,
            AtualizadoPor,
            DataHoraAtualizacao

        FROM dbo.ConfiguracoesOperacionaisInventario

        WHERE
            ClienteId = ?
            AND UPPER(
                LTRIM(
                    RTRIM(TipoInventario)
                )
            ) = ?
            AND Ativo = 1

        ORDER BY
            ID_ConfiguracaoOperacional DESC
        """,
        (
            cliente_id,
            tipo
        )
    )

    linha = cursor.fetchone()

    # ========================================================
    # CONFIGURAÇÃO PADRÃO
    # ========================================================

    if not linha:

        return {
            "id_configuracao":
                None,

            "cliente_id":
                cliente_id,

            "tipo_inventario":
                tipo,

            "origem":
                "PADRAO",

            "localizacao": {
                "obrigatoria":
                    CONFIGURACAO_PADRAO[
                        "localizacao_obrigatoria"
                    ],

                "validar_estoque":
                    CONFIGURACAO_PADRAO[
                        "localizacao_validar_estoque"
                    ]
            },

            "codigo": {
                "obrigatorio":
                    CONFIGURACAO_PADRAO[
                        "codigo_obrigatorio"
                    ],

                "validar_estoque":
                    CONFIGURACAO_PADRAO[
                        "codigo_validar_estoque"
                    ]
            },

            "lote": {
                "obrigatorio_quando_existir":
                    CONFIGURACAO_PADRAO[
                        "lote_obrigatorio_quando_existir"
                    ],

                "validar_codigo":
                    CONFIGURACAO_PADRAO[
                        "lote_validar_codigo"
                    ],

                # REGRA FIXA DO SGI
                "selecao_automatica":
                    False
            },

            "quantidade": {
                "obrigatoria":
                    CONFIGURACAO_PADRAO[
                        "quantidade_obrigatoria"
                    ],

                "minimo":
                    CONFIGURACAO_PADRAO[
                        "quantidade_minima"
                    ],

                "maximo":
                    CONFIGURACAO_PADRAO[
                        "quantidade_maxima"
                    ]
            },

            "atualizado_por":
                None,

            "data_hora_atualizacao":
                None
        }

    # ========================================================
    # CONFIGURAÇÃO DO BANCO
    # ========================================================

    return {
        "id_configuracao":
            linha.ID_ConfiguracaoOperacional,

        "cliente_id":
            linha.ClienteId,

        "tipo_inventario":
            _normalizar_tipo(
                linha.TipoInventario
            ),

        "origem":
            "CLIENTE",

        "localizacao": {
            "obrigatoria":
                bool(
                    linha.LocalizacaoObrigatoria
                ),

            "validar_estoque":
                bool(
                    linha.LocalizacaoValidarEstoque
                )
        },

        "codigo": {
            "obrigatorio":
                bool(
                    linha.CodigoObrigatorio
                ),

            "validar_estoque":
                bool(
                    linha.CodigoValidarEstoque
                )
        },

        "lote": {
            "obrigatorio_quando_existir":
                bool(
                    linha.LoteObrigatorioQuandoExistir
                ),

            "validar_codigo":
                bool(
                    linha.LoteValidarCodigo
                ),

            # =================================================
            # REGRA DE SEGURANÇA OPERACIONAL
            #
            # Mesmo que futuramente alguma coluna seja criada
            # no banco, o backend não permite seleção
            # automática de lote.
            # =================================================
            "selecao_automatica":
                False
        },

        "quantidade": {
            "obrigatoria":
                bool(
                    linha.QuantidadeObrigatoria
                ),

            "minimo":
                linha.QuantidadeMinima,

            "maximo":
                linha.QuantidadeMaxima
        },

        "atualizado_por":
            linha.AtualizadoPor,

        "data_hora_atualizacao":
            linha.DataHoraAtualizacao
    }


# ============================================================
# CONFIGURAÇÃO PELO INVENTÁRIO
#
# Essa função será usada principalmente por:
#
# - contagens.py
# - validação de código
# - validação de lote
# - frontend operacional
# ============================================================

def obter_configuracao_operacional_inventario(
    cursor,
    id_inventario: int
):

    if id_inventario <= 0:

                raise BusinessRuleViolation(
            "Inventário inválido."
        )

    cursor.execute(
        """
        SELECT
            ID_Inventario,
            ClienteId,
            Tipo

        FROM dbo.Inventarios

        WHERE ID_Inventario = ?
        """,
        id_inventario
    )

    inventario = cursor.fetchone()

    if not inventario:

                raise NotFoundError(
            "Inventário não encontrado."
        )

    configuracao = (
        obter_configuracao_operacional(
            cursor=cursor,
            cliente_id=inventario.ClienteId,
            tipo_inventario=inventario.Tipo
        )
    )

    configuracao[
        "id_inventario"
    ] = inventario.ID_Inventario

    return configuracao


# ============================================================
# SALVAR / ATUALIZAR CONFIGURAÇÃO
#
# Não realiza COMMIT.
# A transação permanece responsabilidade do router.
# ============================================================

def salvar_configuracao_operacional(
    cursor,
    cliente_id: int,
    tipo_inventario: str,
    localizacao_obrigatoria: bool,
    localizacao_validar_estoque: bool,
    codigo_obrigatorio: bool,
    codigo_validar_estoque: bool,
    lote_obrigatorio_quando_existir: bool,
    lote_validar_codigo: bool,
    quantidade_obrigatoria: bool,
    quantidade_minima: float,
    quantidade_maxima: float,
    usuario: str
):

    if cliente_id <= 0:

                raise BusinessRuleViolation(
            "Cliente inválido."
        )

    tipo = _normalizar_tipo(
        tipo_inventario
    )

    if tipo not in (
        "OFICIAL",
        "ROTATIVO"
    ):

                raise BusinessRuleViolation(
            "Tipo de inventário inválido."
        )

    usuario = _normalizar_texto(
        usuario
    )

    if not usuario:

                raise BusinessRuleViolation(
            "Usuário responsável pela alteração é obrigatório."
        )

    # ========================================================
    # QUANTIDADE
    # ========================================================

    if quantidade_minima < 0:

                raise BusinessRuleViolation(
            "Quantidade mínima não pode ser negativa."
        )

    if quantidade_maxima <= 0:

                raise BusinessRuleViolation(
            "Quantidade máxima deve ser maior que zero."
        )

    if quantidade_minima > quantidade_maxima:

                raise BusinessRuleViolation(
            "Quantidade mínima não pode ser maior que a quantidade máxima."
        )

    _validar_tabela_configuracao(
        cursor
    )

    # ========================================================
    # PROCURA CONFIGURAÇÃO ATIVA
    # ========================================================

    cursor.execute(
        """
        SELECT TOP 1
            ID_ConfiguracaoOperacional

        FROM dbo.ConfiguracoesOperacionaisInventario

        WHERE
            ClienteId = ?
            AND UPPER(
                LTRIM(
                    RTRIM(TipoInventario)
                )
            ) = ?
            AND Ativo = 1

        ORDER BY
            ID_ConfiguracaoOperacional DESC
        """,
        (
            cliente_id,
            tipo
        )
    )

    existente = cursor.fetchone()

    # ========================================================
    # UPDATE
    # ========================================================

    if existente:

        cursor.execute(
            """
            UPDATE dbo.ConfiguracoesOperacionaisInventario

            SET
                LocalizacaoObrigatoria = ?,
                LocalizacaoValidarEstoque = ?,

                CodigoObrigatorio = ?,
                CodigoValidarEstoque = ?,

                LoteObrigatorioQuandoExistir = ?,
                LoteValidarCodigo = ?,

                QuantidadeObrigatoria = ?,
                QuantidadeMinima = ?,
                QuantidadeMaxima = ?,

                AtualizadoPor = ?,
                DataHoraAtualizacao = SYSDATETIME()

            WHERE
                ID_ConfiguracaoOperacional = ?
            """,
            (
                localizacao_obrigatoria,
                localizacao_validar_estoque,

                codigo_obrigatorio,
                codigo_validar_estoque,

                lote_obrigatorio_quando_existir,
                lote_validar_codigo,

                quantidade_obrigatoria,
                quantidade_minima,
                quantidade_maxima,

                usuario,
                existente.ID_ConfiguracaoOperacional
            )
        )

    # ========================================================
    # INSERT
    # ========================================================

    else:

        cursor.execute(
            """
            INSERT INTO dbo.ConfiguracoesOperacionaisInventario
            (
                ClienteId,
                TipoInventario,

                LocalizacaoObrigatoria,
                LocalizacaoValidarEstoque,

                CodigoObrigatorio,
                CodigoValidarEstoque,

                LoteObrigatorioQuandoExistir,
                LoteValidarCodigo,

                QuantidadeObrigatoria,
                QuantidadeMinima,
                QuantidadeMaxima,

                Ativo,
                AtualizadoPor,
                DataHoraAtualizacao
            )

            VALUES
            (
                ?,
                ?,

                ?,
                ?,

                ?,
                ?,

                ?,
                ?,

                ?,
                ?,
                ?,

                1,
                ?,
                SYSDATETIME()
            )
            """,
            (
                cliente_id,
                tipo,

                localizacao_obrigatoria,
                localizacao_validar_estoque,

                codigo_obrigatorio,
                codigo_validar_estoque,

                lote_obrigatorio_quando_existir,
                lote_validar_codigo,

                quantidade_obrigatoria,
                quantidade_minima,
                quantidade_maxima,

                usuario
            )
        )

    # ========================================================
    # RETORNA CONFIGURAÇÃO ATUALIZADA
    # ========================================================

    resultado = (
        obter_configuracao_operacional(
            cursor=cursor,
            cliente_id=cliente_id,
            tipo_inventario=tipo
        )
    )

    resultado["sucesso"] = True

    resultado["mensagem"] = (
        "Configuração operacional "
        "salva com sucesso."
    )

    return resultado