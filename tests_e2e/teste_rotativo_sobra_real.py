import requests
import sys


BASE_URL = "http://127.0.0.1:8000"

ID_INVENTARIO = 13
ID_RODADA = 25
LOCALIZACAO = "01PLAQUETA"

CODIGO = "99999999"
LOTE = "TESTE"
QUANTIDADE = 2


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

dados_sessao = json_seguro(resposta)

print("HTTP:", resposta.status_code)
print("Resposta:", dados_sessao)

if resposta.status_code not in (200, 201):
    print("\n[FALHOU] Não foi possível abrir a sessão.")
    sys.exit(1)

ID_SESSAO = dados_sessao.get("id_sessao")

if not ID_SESSAO:
    print("\n[FALHOU] id_sessao não retornado.")
    sys.exit(1)

print("ID Sessão:", ID_SESSAO)


# ============================================================
# 2. REGISTRAR ITEM NÃO EXISTENTE NO SNAPSHOT
# ============================================================

titulo("2. REGISTRANDO ITEM NÃO EXISTENTE")

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

if resposta.status_code not in (200, 201):
    print(
        "\n[FALHOU] "
        "A configuração atual não permitiu registrar "
        "o código não cadastrado."
    )
    sys.exit(1)


# ============================================================
# 3. ENCERRAR SESSÃO
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

print("HTTP:", resposta.status_code)
print("Resposta:", json_seguro(resposta))

if resposta.status_code not in (200, 201):
    print("\n[FALHOU] Não foi possível encerrar a sessão.")
    sys.exit(1)


# ============================================================
# 4. ANALISAR
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
# 5. LOCALIZAR ITEM
# ============================================================

item_teste = None

for item in analise.get("itens", []):

    if (
        str(item.get("codigo")).strip() == CODIGO
        and
        str(item.get("lote")).strip() == LOTE
    ):
        item_teste = item
        break


titulo("RESULTADO")

if item_teste is None:
    print(
        "\n[FALHOU] "
        "O item não apareceu na análise."
    )
    sys.exit(1)


print("Localização:", item_teste.get("localizacao"))
print("Código:", item_teste.get("codigo"))
print("Lote:", item_teste.get("lote"))
print("Estoque:", item_teste.get("qtd_estoque"))
print("Contado:", item_teste.get("qtd_contada"))
print("Diferença:", item_teste.get("diferenca"))
print("Status:", item_teste.get("status"))
print(
    "Localizações esperadas:",
    item_teste.get("localizacoes_esperadas")
)


teste_ok = (
    float(item_teste.get("qtd_estoque", 0)) == 0
    and
    float(item_teste.get("qtd_contada", 0)) == 2
    and
    float(item_teste.get("diferenca", 0)) == 2
    and
    item_teste.get("status") == "SOBRA"
    and
    not item_teste.get("localizacoes_esperadas")
)


if teste_ok:

    print(
        "\n[APROVADO] "
        "Sobra verdadeira continuou sendo "
        "classificada como SOBRA."
    )

    sys.exit(0)


print(
    "\n[FALHOU] "
    "A nova regra de localização incorreta "
    "interferiu na classificação de SOBRA."
)

sys.exit(1)