# ============================================================
# REGRAS DE INVENTÁRIO POR CLIENTE
#
# Objetivo:
# Centralizar as regras específicas de contagem/recontagem
# sem espalhar lógica pelos routers e services.
#
# Futuramente isso pode ser migrado para tabela no banco.
# ============================================================


# ============================================================
# REGRAS DOS CLIENTES
# ============================================================

REGRAS_CLIENTES = {

    # ========================================================
    # ALZARSILOG
    # ClienteId = 53
    # ========================================================

    53: {
        "nome_cliente": "ALZARSILOG",

        # ====================================================
        # INVENTÁRIO OFICIAL
        #
        # R1 = completa
        # R2 = completa
        #
        # R3+ = somente divergências
        #
        # O gestor pode decidir finalizar antes de atingir
        # o número máximo de rodadas.
        # ====================================================

        "oficial": {

            "rodadas_iniciais": 2,

            # Limite técnico.
            # Não significa que todas precisam acontecer.
            "max_rodadas": 6,

            "tipos_rodadas": {
                1: "COMPLETA",
                2: "COMPLETA",
                3: "DIVERGENCIAS",
                4: "DIVERGENCIAS",
                5: "DIVERGENCIAS",
                6: "DIVERGENCIAS",
            },

            # Localização não participa da conciliação
            # quantitativa no inventário oficial.
            #
            # Chave analítica:
            # Código + Lote
            "considera_localizacao": False,

            # Operador não visualiza saldo esperado.
            "contagem_cega": True,

            # Nas rodadas de divergência:
            # o sistema identifica Código+Lote divergente
            # e gera o escopo operacional por localização.
            "recontagem_por_localizacao": True,

            # Permite ao gestor encerrar o inventário mesmo
            # antes da última rodada configurada.
            "permite_finalizacao_gestor": True,
        },

        # ====================================================
        # INVENTÁRIO ROTATIVO
        # ====================================================

        "rotativo": {

            "rodadas_iniciais": 1,

            "max_rodadas": 1,

            "tipos_rodadas": {
                1: "COMPLETA",
            },

            # No rotativo, localização participa da análise.
            #
            # Chave:
            # Localização + Código + Lote
            "considera_localizacao": True,

            "contagem_cega": True,

            "recontagem_por_localizacao": False,

            "permite_finalizacao_gestor": True,
        },
    },
}


# ============================================================
# REGRA PADRÃO
#
# Usada temporariamente para cliente ainda não configurado.
#
# OFICIAL:
# R1 completa
# R2 divergências
#
# ROTATIVO:
# R1 completa
# ============================================================

REGRA_PADRAO = {

    "nome_cliente": "PADRAO",

    "oficial": {

        "rodadas_iniciais": 1,

        "max_rodadas": 2,

        "tipos_rodadas": {
            1: "COMPLETA",
            2: "DIVERGENCIAS",
        },

        "considera_localizacao": False,

        "contagem_cega": True,

        "recontagem_por_localizacao": True,

        "permite_finalizacao_gestor": True,
    },

    "rotativo": {

        "rodadas_iniciais": 1,

        "max_rodadas": 1,

        "tipos_rodadas": {
            1: "COMPLETA",
        },

        "considera_localizacao": True,

        "contagem_cega": True,

        "recontagem_por_localizacao": False,

        "permite_finalizacao_gestor": True,
    },
}


# ============================================================
# BUSCAR REGRA COMPLETA DO CLIENTE
# ============================================================

def obter_regra_cliente(
    cliente_id: int
) -> dict:

    if cliente_id is None:
        return REGRA_PADRAO

    return REGRAS_CLIENTES.get(
        cliente_id,
        REGRA_PADRAO
    )


# ============================================================
# BUSCAR REGRA PELO TIPO DE INVENTÁRIO
#
# Valores esperados:
#
# ROTATIVO
# OFICIAL
# ============================================================

def obter_regra_inventario(
    cliente_id: int,
    tipo_inventario: str
) -> dict:

    regra_cliente = obter_regra_cliente(
        cliente_id
    )

    tipo = (
        str(tipo_inventario)
        .strip()
        .lower()
        if tipo_inventario
        else ""
    )

    if tipo not in (
        "rotativo",
        "oficial"
    ):

        raise ValueError(
            f"Tipo de inventário inválido: "
            f"{tipo_inventario}"
        )

    return regra_cliente[tipo]


# ============================================================
# RETORNA O TIPO DE UMA RODADA
#
# Exemplos:
#
# Cliente 53 / OFICIAL
#
# R1 = COMPLETA
# R2 = COMPLETA
# R3 = DIVERGENCIAS
# R4 = DIVERGENCIAS
# ...
# ============================================================

def obter_tipo_rodada(
    cliente_id: int,
    tipo_inventario: str,
    numero_rodada: int
) -> str:

    regra = obter_regra_inventario(
        cliente_id,
        tipo_inventario
    )

    if numero_rodada <= 0:
        return "NAO_CONFIGURADA"

    tipos = regra.get(
        "tipos_rodadas",
        {}
    )

    return tipos.get(
        numero_rodada,
        "NAO_CONFIGURADA"
    )


# ============================================================
# RETORNA O TIPO DA PRÓXIMA RODADA
# ============================================================

def obter_tipo_proxima_rodada(
    cliente_id: int,
    tipo_inventario: str,
    numero_rodada_atual: int
) -> str:

    regra = obter_regra_inventario(
        cliente_id,
        tipo_inventario
    )

    proxima = (
        numero_rodada_atual + 1
    )

    # --------------------------------------------------------
    # Ultrapassou o limite técnico configurado.
    # --------------------------------------------------------

    if proxima > regra["max_rodadas"]:

        return "FINALIZADO"

    tipo = obter_tipo_rodada(
        cliente_id=cliente_id,
        tipo_inventario=tipo_inventario,
        numero_rodada=proxima
    )

    if tipo == "NAO_CONFIGURADA":

        return "FINALIZADO"

    return tipo


# ============================================================
# VERIFICA SE A RODADA É COMPLETA
# ============================================================

def rodada_eh_completa(
    cliente_id: int,
    tipo_inventario: str,
    numero_rodada: int
) -> bool:

    return (
        obter_tipo_rodada(
            cliente_id=cliente_id,
            tipo_inventario=tipo_inventario,
            numero_rodada=numero_rodada
        )
        ==
        "COMPLETA"
    )


# ============================================================
# VERIFICA SE A RODADA É DE DIVERGÊNCIAS
# ============================================================

def rodada_eh_recontagem(
    cliente_id: int,
    tipo_inventario: str,
    numero_rodada: int
) -> bool:

    return (
        obter_tipo_rodada(
            cliente_id=cliente_id,
            tipo_inventario=tipo_inventario,
            numero_rodada=numero_rodada
        )
        ==
        "DIVERGENCIAS"
    )


# ============================================================
# VERIFICA SE PODE EXISTIR PRÓXIMA RODADA
#
# Atenção:
#
# Isso verifica apenas o limite configurado.
#
# Não significa que a próxima rodada DEVE ser criada.
# O gestor pode decidir finalizar antes.
# ============================================================

def pode_criar_proxima_rodada(
    cliente_id: int,
    tipo_inventario: str,
    numero_rodada_atual: int
) -> bool:

    regra = obter_regra_inventario(
        cliente_id,
        tipo_inventario
    )

    if (
        numero_rodada_atual
        >=
        regra["max_rodadas"]
    ):
        return False

    proxima = (
        numero_rodada_atual + 1
    )

    return (
        obter_tipo_rodada(
            cliente_id=cliente_id,
            tipo_inventario=tipo_inventario,
            numero_rodada=proxima
        )
        !=
        "NAO_CONFIGURADA"
    )


# ============================================================
# VERIFICA SE O GESTOR PODE FINALIZAR MANUALMENTE
# ============================================================

def permite_finalizacao_gestor(
    cliente_id: int,
    tipo_inventario: str
) -> bool:

    regra = obter_regra_inventario(
        cliente_id,
        tipo_inventario
    )

    return bool(
        regra.get(
            "permite_finalizacao_gestor",
            False
        )
    )


# ============================================================
# VERIFICA SE É CONTAGEM CEGA
# ============================================================

def inventario_tem_contagem_cega(
    cliente_id: int,
    tipo_inventario: str
) -> bool:

    regra = obter_regra_inventario(
        cliente_id,
        tipo_inventario
    )

    return bool(
        regra.get(
            "contagem_cega",
            True
        )
    )


# ============================================================
# VERIFICA SE RECONTAGEM USA LOCALIZAÇÃO
# ============================================================

def recontagem_por_localizacao(
    cliente_id: int,
    tipo_inventario: str
) -> bool:

    regra = obter_regra_inventario(
        cliente_id,
        tipo_inventario
    )

    return bool(
        regra.get(
            "recontagem_por_localizacao",
            False
        )
    )