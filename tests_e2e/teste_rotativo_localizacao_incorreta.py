import requests
import sys


BASE_URL = "http://127.0.0.1:8000"

ID_INVENTARIO = 13
ID_RODADA = 25

LOCALIZACAO_CONTAGEM = "01PLAQUETA"

CODIGO = "70194232"
LOTE = "REIT"
QUANTIDADE = 1


def titulo(texto):
    print("\n" + "=" * 70)
    print(texto)
    print("=" * 70)


def json_seguro(resposta):
    try:
        return resposta.json()
    except Exception:
        return None


# ============================================================
# 1. ABRIR SESSÃO
# ============================================================

titulo("1. ABRINDO SESSÃO NA LOCALIZAÇÃO ERRADA")

payload = {
    "id_inventario": ID_INVENTARIO,
    "id_rodada": ID_RODADA,
    "localizacao": LOCALIZACAO_CONTAGEM,
}

resposta = requests.post(
    f"{BASE_URL}/localizacoes/iniciar",
    json=payload,
)

dados_sessao = json_seguro(resposta)

print("HTTP:", resposta.status_code)
print("Resposta:", dados_sessao)

if resposta.status_code not in (200, 201):
    print(
        "\n[FALHOU] Não foi possível abrir a sessão."
    )
    sys.exit(1)

ID_SESSAO = dados_sessao.get("id_sessao")

if not ID_SESSAO:
    print(
        "\n[FALHOU] id_sessao não retornado."
    )
    sys.exit(1)

print("ID Sessão:", ID_SESSAO)


# ============================================================
# 2. TENTAR CONTAR ITEM DE OUTRA LOCALIZAÇÃO
# ============================================================

titulo("2. CONTANDO ITEM DE OUTRA LOCALIZAÇÃO")

payload = {
    "id_sessao": ID_SESSAO,
    "codigo": CODIGO,
    "lote": LOTE,
    "quantidade": QUANTIDADE,
    "usuario": "dev",
}

resposta = requests.post(
    f"{BASE_URL}/contagens",
    json=payload,
)

dados_contagem = json_seguro(resposta)

print("HTTP:", resposta.status_code)
print("Resposta:", dados_contagem)


# ============================================================
# 3. SE A API BLOQUEAR
# ============================================================

if resposta.status_code in (400, 404, 409):

    titulo("RESULTADO")

    print(
        "\n[RESULTADO] "
        "A API bloqueou o item por não pertencer "
        "à localização contada."
    )

    if dados_contagem:
        print(
            "Detalhe:",
            dados_contagem.get("detail")
        )

    print(
        "\nPrecisamos então avaliar se essa é "
        "a regra operacional desejada."
    )

    sys.exit(0)


# ============================================================
# 4. SE A API ACEITAR
# ============================================================

if resposta.status_code not in (200, 201):

    titulo("RESULTADO")

    print(
        "\n[FALHOU] "
        "A API retornou comportamento inesperado."
    )

    sys.exit(1)


ID_CONTAGEM = dados_contagem.get(
    "id_contagem"
)

print(
    "ID Contagem:",
    ID_CONTAGEM
)


# ============================================================
# 5. ENCERRAR SESSÃO
# ============================================================

titulo("3. ENCERRANDO SESSÃO")

payload = {
    "id_sessao": ID_SESSAO,
    "usuario": "dev",
}

resposta = requests.post(
    f"{BASE_URL}/localizacoes/encerrar",
    json=payload,
)

dados_encerramento = json_seguro(resposta)

print("HTTP:", resposta.status_code)
print("Resposta:", dados_encerramento)

if resposta.status_code not in (200, 201):
    print(
        "\n[FALHOU] "
        "Não foi possível encerrar a sessão."
    )
    sys.exit(1)


# ============================================================
# 6. ANALISAR
# ============================================================

titulo("4. ANALISANDO RESULTADO")

resposta = requests.get(
    f"{BASE_URL}/sessoes/{ID_SESSAO}/analise"
)

analise = json_seguro(resposta)

print("HTTP:", resposta.status_code)

if resposta.status_code not in (200, 201):
    print("Resposta:", analise)
    sys.exit(1)


# ============================================================
# 7. LOCALIZAR ITEM ENCONTRADO FORA DA LOCALIZAÇÃO
# ============================================================

item_encontrado = None

for item in analise.get("itens", []):

    if (
        str(item.get("codigo")).strip() == CODIGO
        and
        str(item.get("lote")).strip() == LOTE
    ):
        item_encontrado = item
        break


titulo("RESULTADO")


if item_encontrado is None:

    print(
        "\n[FALHOU] "
        "O item contado não apareceu na análise."
    )

    sys.exit(1)


print(
    "Localização:",
    item_encontrado.get("localizacao")
)

print(
    "Código:",
    item_encontrado.get("codigo")
)

print(
    "Lote:",
    item_encontrado.get("lote")
)

print(
    "Estoque na localização:",
    item_encontrado.get("qtd_estoque")
)

print(
    "Contado:",
    item_encontrado.get("qtd_contada")
)

print(
    "Diferença:",
    item_encontrado.get("diferenca")
)

print(
    "Status atual:",
    item_encontrado.get("status")
)


# ============================================================
# 8. AVALIAÇÃO
# ============================================================

if (
    float(
        item_encontrado.get(
            "qtd_estoque",
            0
        )
    ) == 0
    and
    float(
        item_encontrado.get(
            "qtd_contada",
            0
        )
    ) > 0
):

    print(
        "\n[DETECTADO] "
        "O motor reconheceu que o item não pertence "
        "ao estoque esperado desta localização."
    )

    print(
        "\nAgora precisamos verificar a classificação."
    )

    print(
        "Status retornado:",
        item_encontrado.get("status")
    )

    print(
        "\nSe retornar SOBRA, o cálculo está correto, "
        "mas a classificação operacional pode ser "
        "refinada para LOCALIZACAO_INCORRETA."
    )

    sys.exit(0)


print(
    "\n[FALHOU] "
    "O comportamento do item em localização errada "
    "não foi o esperado."
)

sys.exit(1)