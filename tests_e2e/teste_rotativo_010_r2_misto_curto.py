import requests


BASE_URL = "http://127.0.0.1:8000"

ID_INVENTARIO = 20
ID_RODADA_R2 = 40

LOCALIZACAO = "01PLAQUETA"

USUARIO = "teste_e2e"


def titulo(texto):

    print("\n" + "=" * 70)
    print(texto)
    print("=" * 70)


def validar(resposta):

    print(
        "HTTP:",
        resposta.status_code
    )

    try:
        dados = resposta.json()

    except Exception:
        dados = resposta.text

    print(
        "Resposta:",
        dados
    )

    if resposta.status_code not in (
        200,
        201,
    ):

        raise SystemExit(
            "\n[FALHOU]"
        )

    return dados


# ============================================================
# 1. ABRIR SESSÃO R2
# ============================================================

titulo(
    "1. ABRINDO SESSÃO R2"
)

resposta = requests.post(
    f"{BASE_URL}/localizacoes/iniciar",
    json={
        "id_inventario":
            ID_INVENTARIO,

        "id_rodada":
            ID_RODADA_R2,

        "localizacao":
            LOCALIZACAO
    }
)

dados = validar(
    resposta
)

ID_SESSAO_R2 = dados[
    "id_sessao"
]

print(
    "\nID Sessão R2:",
    ID_SESSAO_R2
)


# ============================================================
# 2. ITEM 1
#
# WMS = 2
# R2 = 2
# ESPERADO = OK
# ============================================================

titulo(
    "2. CONTANDO ITEM QUE DEVE RESOLVER"
)

resposta = requests.post(
    f"{BASE_URL}/contagens",
    json={
        "id_sessao":
            ID_SESSAO_R2,

        "codigo":
            "71554091",

        "lote":
            "3007863031 - 40",

        "quantidade":
            2,

        "usuario":
            USUARIO
    }
)

validar(
    resposta
)


# ============================================================
# 3. ITEM 2
#
# WMS = 1
# R2 = 2
# ESPERADO = CONTINUAR DIVERGENTE
# ============================================================

titulo(
    "3. CONTANDO ITEM QUE DEVE CONTINUAR DIVERGENTE"
)

resposta = requests.post(
    f"{BASE_URL}/contagens",
    json={
        "id_sessao":
            ID_SESSAO_R2,

        "codigo":
            "71554091",

        "lote":
            "3007863574 - 30",

        "quantidade":
            2,

        "usuario":
            USUARIO
    }
)

validar(
    resposta
)


# ============================================================
# 4. ENCERRAR R2
# ============================================================

titulo(
    "4. ENCERRANDO SESSÃO R2"
)

resposta = requests.post(
    f"{BASE_URL}/localizacoes/encerrar",
    json={
        "id_sessao":
            ID_SESSAO_R2,

        "usuario":
            USUARIO
    }
)

validar(
    resposta
)


# ============================================================
# 5. ANALISAR R2
# ============================================================

titulo(
    "5. ANALISANDO R2"
)

resposta = requests.get(
    (
        f"{BASE_URL}/sessoes/"
        f"{ID_SESSAO_R2}/analise"
    )
)

analise = validar(
    resposta
)

itens = analise.get(
    "itens",
    []
)


# ============================================================
# 6. RESUMO
# ============================================================

titulo(
    "6. RESULTADO"
)

for item in itens:

    print(
        "\nCódigo:",
        item.get("codigo")
    )

    print(
        "Lote:",
        item.get("lote")
    )

    print(
        "Estoque:",
        item.get("qtd_estoque")
    )

    print(
        "Contado R2:",
        item.get("qtd_contada")
    )

    print(
        "Diferença:",
        item.get("diferenca")
    )

    print(
        "Status:",
        item.get("status")
    )

    print(
        "Resolvido:",
        item.get("resolvido")
    )


# ============================================================
# 7. VALIDAÇÃO AUTOMÁTICA
# ============================================================

item_resolvido = next(
    (
        item
        for item in itens
        if (
            item.get("codigo")
            ==
            "71554091"

            and

            item.get("lote")
            ==
            "3007863031 - 40"
        )
    ),
    None
)

item_persistente = next(
    (
        item
        for item in itens
        if (
            item.get("codigo")
            ==
            "71554091"

            and

            item.get("lote")
            ==
            "3007863574 - 30"
        )
    ),
    None
)


if not item_resolvido:

    raise SystemExit(
        "\n[FALHOU] Item resolvido não encontrado."
    )


if not item_persistente:

    raise SystemExit(
        "\n[FALHOU] Item divergente não encontrado."
    )


if (
    item_resolvido.get("status")
    !=
    "OK"
):

    raise SystemExit(
        "\n[FALHOU] Primeiro item deveria ficar OK."
    )


if (
    float(
        item_resolvido.get(
            "diferenca",
            999
        )
    )
    !=
    0
):

    raise SystemExit(
        "\n[FALHOU] Primeiro item ainda possui diferença."
    )


if (
    item_persistente.get("status")
    ==
    "OK"
):

    raise SystemExit(
        "\n[FALHOU] Segundo item não deveria ficar OK."
    )


if (
    float(
        item_persistente.get(
            "diferenca",
            0
        )
    )
    !=
    1
):

    raise SystemExit(
        "\n[FALHOU] Diferença esperada do segundo item = 1."
    )


print(
    "\n[APROVADO] R2 mista executada corretamente."
)

print(
    "\nEsperado para finalização:"
)

print(
    "Lote 3007863031 - 40"
    " => RESOLVIDA_RECONTAGEM"
)

print(
    "Lote 3007863574 - 30"
    " => DIVERGENCIA_CONFIRMADA"
)