import requests
import sys

BASE_URL = "http://127.0.0.1:8000"

ID_INVENTARIO = 13
ID_RODADA = 25
LOCALIZACAO = "01RETN00101"


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
# 2. ITENS CORRETOS
# ============================================================

titulo("2. REGISTRANDO ITENS CORRETOS")

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
    {
        "codigo": "70226087",
        "lote": "RETN",
        "quantidade": 1,
    },
    {
        "codigo": "70239464",
        "lote": "RETN",
        "quantidade": 1,
    },
]


# ============================================================
# 3. ITEM INESPERADO
#
# Este será nosso teste de SOBRA.
# ============================================================

contagens.append(
    {
        "codigo": "99999999",
        "lote": "TESTE",
        "quantidade": 2,
    }
)


# ============================================================
# 4. SALVAR CONTAGENS
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
# 5. LISTAR CONTAGENS
# ============================================================

titulo("3. VALIDANDO CONTAGENS")

resposta = requests.get(
    f"{BASE_URL}/sessoes/{ID_SESSAO}/contagens"
)

dados_contagens = validar(
    resposta,
    "Consulta das contagens"
)

print(
    "Total registros:",
    dados_contagens.get(
        "total_registros"
    )
)


# ============================================================
# 6. ENCERRAR LOCALIZAÇÃO
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
# 7. ANALISAR
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
# 8. LOCALIZAR SOBRA
# ============================================================

sobra_encontrada = None

for item in analise.get(
    "itens",
    []
):

    if (
        item.get("codigo") == "99999999"
        and
        item.get("lote") == "TESTE"
    ):
        sobra_encontrada = item
        break


# ============================================================
# 9. RESULTADO DO TESTE
# ============================================================

titulo("RESULTADO")

if sobra_encontrada is None:

    print(
        "[FALHOU] Item inesperado não apareceu "
        "na análise."
    )

    sys.exit(1)


print(
    "Código:",
    sobra_encontrada.get(
        "codigo"
    )
)

print(
    "Lote:",
    sobra_encontrada.get(
        "lote"
    )
)

print(
    "Estoque:",
    sobra_encontrada.get(
        "qtd_estoque"
    )
)

print(
    "Contado:",
    sobra_encontrada.get(
        "qtd_contada"
    )
)

print(
    "Diferença:",
    sobra_encontrada.get(
        "diferenca"
    )
)

print(
    "Status:",
    sobra_encontrada.get(
        "status"
    )
)


if (
    sobra_encontrada.get(
        "qtd_estoque"
    ) == 0
    and
    sobra_encontrada.get(
        "qtd_contada"
    ) == 2
    and
    sobra_encontrada.get(
        "diferenca"
    ) == 2
    and
    sobra_encontrada.get(
        "status"
    ) == "SOBRA"
):

    print(
        "\n[APROVADO] "
        "Motor identificou SOBRA corretamente."
    )

else:

    print(
        "\n[FALHOU] "
        "O comportamento da SOBRA não foi "
        "o esperado."
    )

    sys.exit(1)