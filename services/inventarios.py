from domain.exceptions import BusinessRuleViolation

from services.configuracoes_inventario import (
    obter_configuracao_inventario,
    obter_tipo_rodada_configurada,
)


# ============================================================
# NORMALIZAÇÃO
# ============================================================

def _texto(valor):

    if valor is None:
        return ""

    return str(valor).strip()


def _upper(valor):

    return _texto(valor).upper()


# ============================================================
# CRIAR INVENTÁRIO
#
# Responsabilidades:
#
# - validar dados principais
# - validar configuração ativa ClienteId + Tipo
# - impedir código duplicado
# - criar dbo.Inventarios
# - criar Rodada 1
#
# Commit é responsabilidade do router.
# ============================================================

def criar_inventario(
    cursor,
    codigo_inventario: str,
    tipo: str,
    cliente_id: int,
    cliente: str,
    descricao: str | None,
    armazem: str,
    usuario: str
):

    codigo = _upper(
        codigo_inventario
    )

    tipo = _upper(
        tipo
    )

    cliente = _texto(
        cliente
    )

    descricao = (
        _texto(descricao)
        if descricao
        else None
    )

    armazem = _upper(
        armazem
    )

    usuario = _texto(
        usuario
    )

    # ========================================================
    # 1. VALIDAÇÕES
    # ========================================================

    if not codigo:

        raise BusinessRuleViolation(
            "Código do inventário obrigatório."
        )

    if tipo not in (
        "OFICIAL",
        "ROTATIVO"
    ):

        raise BusinessRuleViolation(
            "Tipo de inventário inválido. "
                "Valores permitidos: OFICIAL ou ROTATIVO."
        )

    if cliente_id <= 0:

        raise BusinessRuleViolation(
            "ClienteId inválido."
        )

    if not cliente:

        raise BusinessRuleViolation(
            "Cliente obrigatório."
        )

    if not armazem:

        raise BusinessRuleViolation(
            "Armazém obrigatório."
        )

    if not usuario:

        raise BusinessRuleViolation(
            "Usuário responsável obrigatório."
        )

    # ========================================================
    # 2. CONFIGURAÇÃO ATIVA
    # ========================================================

    configuracao = (
        obter_configuracao_inventario(
            cursor=cursor,
            cliente_id=cliente_id,
            tipo_inventario=tipo
        )
    )

    tipo_r1 = (
        obter_tipo_rodada_configurada(
            cursor=cursor,
            cliente_id=cliente_id,
            tipo_inventario=tipo,
            numero_rodada=1
        )
    )

    if tipo_r1 == "NAO_CONFIGURADA":

        raise BusinessRuleViolation(
            "A Rodada 1 não está configurada "
                "para este cliente e tipo de inventário."
        )

    # ========================================================
    # 3. CÓDIGO DUPLICADO
    # ========================================================

    cursor.execute(
        """
        SELECT TOP 1
            ID_Inventario

        FROM dbo.Inventarios

        WHERE UPPER(
            LTRIM(
                RTRIM(CodigoInventario)
            )
        ) = ?
        """,
        codigo
    )

    existente = cursor.fetchone()

    if existente:

        raise BusinessRuleViolation(
            "Já existe um inventário com "
                "este código."
        )

    # ========================================================
    # 4. CRIA INVENTÁRIO
    # ========================================================

    cursor.execute(
        """
        INSERT INTO dbo.Inventarios
        (
            CodigoInventario,
            Tipo,
            Cliente,
            Descricao,
            RodadaAtual,
            Status,
            DataHoraInicio,
            DataHoraFim,
            CriadoPor,
            DataHoraCriacao,
            ClienteId,
            cArmazem,
            FinalizadoPor,
            EmAnaliseGestor,
            DataHoraEncaminhamentoGestor,
            EncaminhadoGestorPor
        )

        OUTPUT
            INSERTED.ID_Inventario,
            INSERTED.DataHoraInicio,
            INSERTED.DataHoraCriacao

        VALUES
        (
            ?,
            ?,
            ?,
            ?,
            1,
            'ABERTO',
            SYSDATETIME(),
            NULL,
            ?,
            SYSDATETIME(),
            ?,
            ?,
            NULL,
            0,
            NULL,
            NULL
        )
        """,
        (
            codigo,
            tipo,
            cliente,
            descricao,
            usuario,
            cliente_id,
            armazem
        )
    )

    inventario = cursor.fetchone()

    # ========================================================
    # 5. CRIA RODADA 1
    # ========================================================

    cursor.execute(
        """
        INSERT INTO dbo.RodadasInventario
        (
            ID_Inventario,
            NumeroRodada,
            Status,
            DataHoraInicio,
            DataHoraFim,
            CriadoPor,
            DataHoraCriacao
        )

        OUTPUT
            INSERTED.ID_Rodada,
            INSERTED.NumeroRodada,
            INSERTED.Status,
            INSERTED.DataHoraInicio,
            INSERTED.DataHoraCriacao

        VALUES
        (
            ?,
            1,
            'ABERTA',
            SYSDATETIME(),
            NULL,
            ?,
            SYSDATETIME()
        )
        """,
        (
            inventario.ID_Inventario,
            usuario
        )
    )

    rodada = cursor.fetchone()

    # ========================================================
    # 6. RETORNO
    # ========================================================

    return {
        "sucesso":
            True,

        "id_inventario":
            inventario.ID_Inventario,

        "codigo_inventario":
            codigo,

        "tipo":
            tipo,

        "cliente_id":
            cliente_id,

        "cliente":
            cliente,

        "descricao":
            descricao,

        "armazem":
            armazem,

        "status":
            "ABERTO",

        "rodada_atual":
            1,

        "id_rodada":
            rodada.ID_Rodada,

        "numero_rodada":
            rodada.NumeroRodada,

        "status_rodada":
            rodada.Status,

        "tipo_rodada":
            tipo_r1,

        "criado_por":
            usuario,

        "data_hora_inicio":
            inventario.DataHoraInicio,

        "data_hora_criacao":
            inventario.DataHoraCriacao,

        "configuracao": {
            "id_configuracao":
                configuracao[
                    "id_configuracao"
                ],

            "rodadas_iniciais":
                configuracao[
                    "rodadas_iniciais"
                ],

            "max_rodadas":
                configuracao[
                    "max_rodadas"
                ],

            "contagem_cega":
                configuracao[
                    "contagem_cega"
                ]
        },

        "proximo_passo":
            "DEFINIR_ESCOPO"
    }
