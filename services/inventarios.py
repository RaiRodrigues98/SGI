from domain.exceptions import (
    BusinessRuleViolation,
    ConflictError,
    NotFoundError,
)

from services.configuracoes_inventario import (
    obter_configuracao_inventario,
    obter_tipo_rodada_configurada,
)


from services.configuracoes_inventario_aplicadas import (
    criar_configuracao_aplicada,
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
    # 4. IMPEDE MAIS DE UM INVENTÁRIO ATIVO NO ARMAZÉM
    #
    # FINALIZADO e CANCELADO liberam o armazém.
    # Qualquer outro status mantém o armazém ocupado.
    #
    # UPDLOCK + HOLDLOCK protege contra duas criações
    # simultâneas para o mesmo armazém.
    # ========================================================

    cursor.execute(
        """
        SELECT TOP 1
            ID_Inventario,
            CodigoInventario,
            Tipo,
            Status,
            cArmazem

        FROM dbo.Inventarios WITH (
            UPDLOCK,
            HOLDLOCK
        )

        WHERE
            UPPER(
                LTRIM(
                    RTRIM(cArmazem)
                )
            ) = ?

            AND UPPER(
                LTRIM(
                    RTRIM(Status)
                )
            ) NOT IN (
                'FINALIZADO',
                'CANCELADO'
            )

        ORDER BY ID_Inventario DESC
        """,
        armazem
    )

    inventario_ativo = cursor.fetchone()

    if inventario_ativo:

        codigo_ativo = _texto(
            inventario_ativo.CodigoInventario
        )

        status_ativo = _upper(
            inventario_ativo.Status
        )

        raise ConflictError(
            f"O armazém {armazem} já possui o inventário "
            f"{codigo_ativo} em andamento, com status "
            f"{status_ativo}. Finalize ou cancele esse "
            "inventário antes de criar outro."
        )
    # ========================================================
    # 5. CRIA INVENTÁRIO
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

    if not inventario:
        raise BusinessRuleViolation(
            "Não foi possível obter o inventário criado."
        )

    # ========================================================
    # 6. COPIA E CONGELA A CONFIGURAÇÃO
    # ========================================================

    configuracao = criar_configuracao_aplicada(
        cursor=cursor,
        id_inventario=int(
            inventario.ID_Inventario
        ),
        usuario=usuario
    )

    rodada_1_configurada = next(
        (
            rodada
            for rodada in configuracao["rodadas"]
            if rodada["numero_rodada"] == 1
        ),
        None
    )

    if not rodada_1_configurada:
        raise BusinessRuleViolation(
            "A Rodada 1 não está configurada "
            "para este inventário."
        )

    tipo_r1 = rodada_1_configurada[
        "tipo_rodada"
    ]

    # ========================================================
    # 7. CRIA RODADA 1
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
    # 7. RETORNO
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



# ============================================================
# CANCELAR INVENTARIO
#
# Commit e responsabilidade do router.
# ============================================================

def cancelar_inventario(
    cursor,
    id_inventario: int,
    motivo: str,
    usuario: str,
):

    if not isinstance(id_inventario, int) or id_inventario <= 0:
        raise BusinessRuleViolation(
            "Invent\u00e1rio inv\u00e1lido."
        )

    motivo_normalizado = _texto(motivo)
    usuario_normalizado = _texto(usuario)

    if not motivo_normalizado:
        raise BusinessRuleViolation(
            "O motivo do cancelamento \u00e9 obrigat\u00f3rio."
        )

    if not usuario_normalizado:
        raise BusinessRuleViolation(
            "Usu\u00e1rio respons\u00e1vel pelo cancelamento "
            "n\u00e3o informado."
        )

    cursor.execute(
        """
        SELECT
            ID_Inventario,
            CodigoInventario,
            Status,
            CanceladoPor,
            MotivoCancelamento,
            DataHoraCancelamento
        FROM dbo.Inventarios WITH (UPDLOCK, ROWLOCK)
        WHERE ID_Inventario = ?
        """,
        id_inventario,
    )

    inventario = cursor.fetchone()

    if not inventario:
        raise NotFoundError(
            "Invent\u00e1rio n\u00e3o encontrado."
        )

    status_atual = _upper(
        inventario.Status
    )

    # Idempotencia
    if status_atual == "CANCELADO":
        return {
            "sucesso": True,
            "id_inventario":
                inventario.ID_Inventario,
            "codigo_inventario":
                inventario.CodigoInventario,
            "status":
                "CANCELADO",
            "cancelado_por":
                inventario.CanceladoPor,
            "motivo_cancelamento":
                inventario.MotivoCancelamento,
            "data_hora_cancelamento":
                inventario.DataHoraCancelamento,
            "mensagem":
                "Invent\u00e1rio j\u00e1 estava cancelado.",
        }

    if status_atual == "FINALIZADO":
        raise BusinessRuleViolation(
            "Invent\u00e1rio finalizado n\u00e3o pode ser "
            "cancelado."
        )

    if status_atual != "ABERTO":
        raise BusinessRuleViolation(
            "Somente invent\u00e1rio com status ABERTO "
            "pode ser cancelado."
        )

    cursor.execute(
        """
        UPDATE dbo.Inventarios
        SET
            Status = 'CANCELADO',
            DataHoraFim = SYSDATETIME(),
            CanceladoPor = ?,
            MotivoCancelamento = ?,
            DataHoraCancelamento = SYSDATETIME()
        WHERE ID_Inventario = ?
        """,
        usuario_normalizado,
        motivo_normalizado,
        id_inventario,
    )

    if cursor.rowcount != 1:
        raise BusinessRuleViolation(
            "N\u00e3o foi poss\u00edvel cancelar o invent\u00e1rio."
        )

    cursor.execute(
        """
        SELECT
            ID_Inventario,
            CodigoInventario,
            Status,
            CanceladoPor,
            MotivoCancelamento,
            DataHoraCancelamento
        FROM dbo.Inventarios
        WHERE ID_Inventario = ?
        """,
        id_inventario,
    )

    cancelado = cursor.fetchone()

    return {
        "sucesso": True,
        "id_inventario":
            cancelado.ID_Inventario,
        "codigo_inventario":
            cancelado.CodigoInventario,
        "status":
            cancelado.Status,
        "cancelado_por":
            cancelado.CanceladoPor,
        "motivo_cancelamento":
            cancelado.MotivoCancelamento,
        "data_hora_cancelamento":
            cancelado.DataHoraCancelamento,
        "mensagem":
            "Invent\u00e1rio cancelado com sucesso.",
    }
