import requests
import sys


BASE_URL = "http://127.0.0.1:8000"

ID_INVENTARIO = 13
ID_RODADA = 25
LOCALIZACAO = "01PLAQUETA"


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

sessao = validar(
    resposta,
    "Sessão aberta"
)

ID_SESSAO = sessao["id_sessao"]

print("ID Sessão:", ID_SESSAO)


# ============================================================
# 2. CONTAGEM
#
# Estoque:
#
# 71256360 / 3007849339 - 220 = 1
# 71554091 / 3007863031 - 40 = 2
# 71554091 / 3007863574 - 30 = 1
#
# Vamos contar 4 no lote que deveria ter 2.
#
# Resultado esperado:
# estoque = 2
# contado = 4
# diferença = +2
# status = DIVERGÊNCIA
# ============================================================

titulo("2. REGISTRANDO CONTAGENS")

contagens = [
    {
        "codigo": "71256360",
        "lote": "3007849339 - 220",
        "quantidade": 1,
    },
    {
        "codigo": "71554091",
        "lote": "3007863031 - 40",
        "quantidade": 4,
    },
    {
        "codigo": "71554091",
        "lote": "3007863574 - 30",
        "quantidade": 1,
    },
]


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
# 3. ENCERRAR
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

validar(
    resposta,
    "Sessão encerrada"
)


# ============================================================
# 4. ANALISAR
# ============================================================

titulo("4. ANALISANDO RESULTADO")

resposta = requests.get(
    f"{BASE_URL}/sessoes/{ID_SESSAO}/analise"
)

analise = validar(
    resposta,
    "Análise concluída"
)


# ============================================================
# 5. LOCALIZAR ITEM
# ============================================================

item_teste = None

for item in analise.get("itens", []):

    if (
        str(item.get("codigo")).strip() == "71554091"
        and
        str(item.get("lote")).strip() == "3007863031 - 40"
    ):
        item_teste = item
        break


if item_teste is None:

    print(
        "\n[FALHOU] "
        "Item de teste não apareceu na análise."
    )

    sys.exit(1)


# ============================================================
# 6. RESULTADO
# ============================================================

titulo("RESULTADO")

print(
    "Código:",
    item_teste.get("codigo")
)

print(
    "Lote:",
    item_teste.get("lote")
)

print(
    "Estoque:",
    item_teste.get("qtd_estoque")
)

print(
    "Contado:",
    item_teste.get("qtd_contada")
)

print(
    "Diferença:",
    item_teste.get("diferenca")
)

print(
    "Status:",
    item_teste.get("status")
)


teste_ok = (
    float(
        item_teste.get(
            "qtd_estoque",
            0
        )
    ) == 2
    and
    float(
        item_teste.get(
            "qtd_contada",
            0
        )
    ) == 4
    and
    float(
        item_teste.get(
            "diferenca",
            0
        )
    ) == 2
    and
    item_teste.get(
        "status"
    ) == "DIVERGÊNCIA"
)


if teste_ok:

    print(
        "\n[APROVADO] "
        "Quantidade acima do estoque "
        "foi classificada corretamente."
    )

    sys.exit(0)


print(
    "\n[FALHOU] "
    "Quantidade maior não foi classificada "
    "como esperado."
)

sys.exit(1)