import requests
import sys


# ============================================================
# CONFIGURAÇÕES
# ============================================================

BASE_URL = "http://127.0.0.1:8000"

ID_INVENTARIO = 13
ID_RODADA = 25
LOCALIZACAO = "01RETN00101"


# ============================================================
# UTILITÁRIOS
# ============================================================

def titulo(texto):
    print("\n" + "=" * 70)
    print(texto)
    print("=" * 70)


def validar(resposta, etapa):

    if resposta.status_code not in (200, 201):

        print(f"\n[ERRO] {etapa}")
        print("Status:", resposta.status_code)

        try:
            print(resposta.json())
        except Exception:
            print(resposta.text)

        sys.exit(1)

    print(f"[OK] {etapa}")

    return resposta.json()


# ============================================================
# 1. ABRIR SESSÃO
# ============================================================

titulo("1. ABRINDO SESSÃO")

payload = {
    "id_inventario": ID_INVENTARIO,
    "id_rodada": ID_RODADA,
    "localizacao": LOCALIZACAO,
}

resposta = requests.post(
    f"{BASE_URL}/localizacoes/iniciar",
    json=payload,
)

dados_sessao = validar(
    resposta,
    "Sessão aberta"
)

ID_SESSAO = dados_sessao["id_sessao"]

print("ID Sessão:", ID_SESSAO)


# ============================================================
# 2. REGISTRAR CONTAGENS
#
# Cenário:
#
# Todos os itens serão contados corretamente,
# EXCETO o código 70226087.
#
# O estoque possui:
#
# 70226087 / RETN = 1
#
# Mas vamos informar:
#
# 70226087 / LOTE-ERRADO = 1
#
# Resultado esperado:
#
# 70226087 / RETN
# -> FALTA
#
# 70226087 / LOTE-ERRADO
# -> SOBRA
# ============================================================

titulo("2. REGISTRANDO CONTAGENS")

contagens = [
    {
        "codigo": "70200630",
        "lote": "RETN",
        "quantidade": 1,
    },
    {
        "codigo": "70214176",
        "lote": "RETN",
        "quantidade": 3,
    },
    {
        "codigo": "70218384",
        "lote": "RETN",
        "quantidade": 4,
    },
    {
        "codigo": "70220725",
        "lote": "RETN",
        "quantidade": 2,
    },

    # ========================================================
    # TESTE PROPOSITAL DE LOTE INCORRETO
    # ========================================================

    {
        "codigo": "70226087",
        "lote": "LOTE-ERRADO",
        "quantidade": 1,
    },

    {
        "codigo": "70239464",
        "lote": "RETN",
        "quantidade": 1,
    },
]


# ============================================================
# 3. SALVAR CONTAGENS
# ============================================================

for item in contagens:

    payload = {
        "id_sessao": ID_SESSAO,
        "codigo": item["codigo"],
        "lote": item["lote"],
        "quantidade": item["quantidade"],
        "usuario": "dev",
    }

    resposta = requests.post(
        f"{BASE_URL}/contagens",
        json=payload,
    )

    validar(
        resposta,
        f'{item["codigo"]} / {item["lote"]}'
    )


# ============================================================
# 4. LISTAR CONTAGENS
# ============================================================

titulo("3. VALIDANDO CONTAGENS")

resposta = requests.get(
    f"{BASE_URL}/sessoes/{ID_SESSAO}/contagens"
)

dados_contagens = validar(
    resposta,
    "Consulta das contagens"
)

total_registros = dados_contagens.get(
    "total_registros",
    0
)

print(
    "Total registros:",
    total_registros
)


# ============================================================
# VALIDAR QUANTIDADE DE REGISTROS
# ============================================================

if total_registros != 6:

    print(
        "\n[FALHOU] "
        "Era esperado exatamente 6 registros de contagem."
    )

    sys.exit(1)


# ============================================================
# 5. ENCERRAR LOCALIZAÇÃO
# ============================================================

titulo("4. ENCERRANDO SESSÃO")

payload = {
    "id_sessao": ID_SESSAO,
    "usuario": "dev",
}

resposta = requests.post(
    f"{BASE_URL}/localizacoes/encerrar",
    json=payload,
)

validar(
    resposta,
    "Sessão encerrada"
)


# ============================================================
# 6. ANALISAR RESULTADO
# ============================================================

titulo("5. ANALISANDO RESULTADO")

resposta = requests.get(
    f"{BASE_URL}/sessoes/{ID_SESSAO}/analise"
)

analise = validar(
    resposta,
    "Análise concluída"
)


# ============================================================
# 7. LOCALIZAR DIVERGÊNCIAS DE LOTE
# ============================================================

falta_lote_original = None
sobra_lote_errado = None


for item in analise.get(
    "itens",
    []
):

    codigo = str(
        item.get(
            "codigo",
            ""
        )
    ).strip()

    lote = str(
        item.get(
            "lote",
            ""
        )
    ).strip()

    # --------------------------------------------------------
    # Lote correto existente no estoque,
    # mas que não foi contado.
    # --------------------------------------------------------

    if (
        codigo == "70226087"
        and
        lote == "RETN"
    ):

        falta_lote_original = item

    # --------------------------------------------------------
    # Lote incorreto informado na contagem.
    # --------------------------------------------------------

    if (
        codigo == "70226087"
        and
        lote == "LOTE-ERRADO"
    ):

        sobra_lote_errado = item


# ============================================================
# 8. RESULTADO
# ============================================================

titulo("RESULTADO")


# ============================================================
# VALIDAR FALTA DO LOTE ORIGINAL
# ============================================================

if falta_lote_original is None:

    print(
        "[FALHOU] "
        "O lote original RETN não apareceu na análise."
    )

    sys.exit(1)


print("\nLOTE ORIGINAL:")

print(
    "Código:",
    falta_lote_original.get(
        "codigo"
    )
)

print(
    "Lote:",
    falta_lote_original.get(
        "lote"
    )
)

print(
    "Estoque:",
    falta_lote_original.get(
        "qtd_estoque"
    )
)

print(
    "Contado:",
    falta_lote_original.get(
        "qtd_contada"
    )
)

print(
    "Diferença:",
    falta_lote_original.get(
        "diferenca"
    )
)

print(
    "Status:",
    falta_lote_original.get(
        "status"
    )
)


# ============================================================
# VALIDAR SOBRA DO LOTE ERRADO
# ============================================================

if sobra_lote_errado is None:

    print(
        "\n[FALHOU] "
        "O lote incorreto LOTE-ERRADO não apareceu "
        "na análise."
    )

    sys.exit(1)


print("\nLOTE INCORRETO:")

print(
    "Código:",
    sobra_lote_errado.get(
        "codigo"
    )
)

print(
    "Lote:",
    sobra_lote_errado.get(
        "lote"
    )
)

print(
    "Estoque:",
    sobra_lote_errado.get(
        "qtd_estoque"
    )
)

print(
    "Contado:",
    sobra_lote_errado.get(
        "qtd_contada"
    )
)

print(
    "Diferença:",
    sobra_lote_errado.get(
        "diferenca"
    )
)

print(
    "Status:",
    sobra_lote_errado.get(
        "status"
    )
)


# ============================================================
# 9. VALIDAR RESULTADO ESPERADO
# ============================================================

teste_falta_ok = (
    float(
        falta_lote_original.get(
            "qtd_estoque",
            0
        )
    ) == 1
    and
    float(
        falta_lote_original.get(
            "qtd_contada",
            0
        )
    ) == 0
    and
    float(
        falta_lote_original.get(
            "diferenca",
            0
        )
    ) == -1
    and
    falta_lote_original.get(
        "status"
    ) == "FALTA"
)


teste_sobra_ok = (
    float(
        sobra_lote_errado.get(
            "qtd_estoque",
            0
        )
    ) == 0
    and
    float(
        sobra_lote_errado.get(
            "qtd_contada",
            0
        )
    ) == 1
    and
    float(
        sobra_lote_errado.get(
            "diferenca",
            0
        )
    ) == 1
    and
    sobra_lote_errado.get(
        "status"
    ) == "SOBRA"
)


# ============================================================
# 10. RESULTADO FINAL
# ============================================================

if (
    teste_falta_ok
    and
    teste_sobra_ok
):

    print(
        "\n[APROVADO] "
        "Motor identificou lote incorreto corretamente."
    )

    print(
        "\nRegra validada:"
    )

    print(
        "LOCALIZACAO + CODIGO + LOTE"
    )

    print(
        "\nResultado:"
    )

    print(
        "70226087 / RETN "
        "-> FALTA"
    )

    print(
        "70226087 / LOTE-ERRADO "
        "-> SOBRA"
    )

    sys.exit(0)


print(
    "\n[FALHOU] "
    "O comportamento para lote incorreto "
    "não foi o esperado."
)

if not teste_falta_ok:

    print(
        "- Falha na validação do lote original."
    )

if not teste_sobra_ok:

    print(
        "- Falha na validação do lote incorreto."
    )

sys.exit(1)