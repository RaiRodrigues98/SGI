import requests
import sys


BASE_URL = "http://127.0.0.1:8000"

ID_INVENTARIO = 13
ID_RODADA = 25
LOCALIZACAO = "01PLAQUETA"

CODIGO = "71554091"

LOTE_FALTA = "3007863031 - 40"
LOTE_EXCESSO = "3007863574 - 30"


def titulo(texto):
    print("\n" + "=" * 70)
    print(texto)
    print("=" * 70)


def validar(resposta, etapa):
    print("HTTP:", resposta.status_code)

    try:
        dados = resposta.json()
    except Exception:
        dados = resposta.text

    print("Resposta:", dados)

    if resposta.status_code not in (200, 201):
        print(f"\n[ERRO] {etapa}")
        sys.exit(1)

    return dados


# ============================================================
# 1. ABRIR SESSÃO
# ============================================================

titulo("1. ABRINDO SESSÃO")

resposta = requests.post(
    f"{BASE_URL}/localizacoes/iniciar",
    json={
        "id_inventario": ID_INVENTARIO,
        "id_rodada": ID_RODADA,
        "localizacao": LOCALIZACAO,
    },
)

sessao = validar(
    resposta,
    "Não foi possível abrir a sessão."
)

ID_SESSAO = sessao["id_sessao"]

print("\nID Sessão:", ID_SESSAO)


# ============================================================
# 2. REGISTRAR CONTAGEM
#
# Estoque:
# A = 2
# B = 1
# Total = 3
#
# Contagem:
# A = 0
# B = 4
# Total = 4
# ============================================================

titulo("2. REGISTRANDO LOTE + QUANTIDADE INCORRETOS")

resposta = requests.post(
    f"{BASE_URL}/contagens",
    json={
        "id_sessao": ID_SESSAO,
        "codigo": CODIGO,
        "lote": LOTE_EXCESSO,
        "quantidade": 4,
        "usuario": "dev",
    },
)

validar(
    resposta,
    "Não foi possível registrar a contagem."
)


# ============================================================
# 3. ENCERRAR
# ============================================================

titulo("3. ENCERRANDO SESSÃO")

resposta = requests.post(
    f"{BASE_URL}/localizacoes/encerrar",
    json={
        "id_sessao": ID_SESSAO,
        "usuario": "dev",
    },
)

validar(
    resposta,
    "Não foi possível encerrar a sessão."
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
    "Não foi possível analisar a sessão."
)


# ============================================================
# 5. LOCALIZAR LOTES
# ============================================================

item_falta = None
item_excesso = None

for item in analise.get("itens", []):

    if (
        str(item.get("codigo")).strip() == CODIGO
        and
        str(item.get("lote")).strip() == LOTE_FALTA
    ):
        item_falta = item

    if (
        str(item.get("codigo")).strip() == CODIGO
        and
        str(item.get("lote")).strip() == LOTE_EXCESSO
    ):
        item_excesso = item


titulo("RESULTADO")

if not item_falta or not item_excesso:
    print("\n[FALHOU] Não foi possível localizar os dois lotes.")
    sys.exit(1)


print("\nLOTE COM FALTA")
print("Lote:", item_falta.get("lote"))
print("Estoque:", item_falta.get("qtd_estoque"))
print("Contado:", item_falta.get("qtd_contada"))
print("Diferença:", item_falta.get("diferenca"))
print("Status:", item_falta.get("status"))
print("Subtipo:", item_falta.get("subtipo_divergencia"))


print("\nLOTE COM EXCESSO")
print("Lote:", item_excesso.get("lote"))
print("Estoque:", item_excesso.get("qtd_estoque"))
print("Contado:", item_excesso.get("qtd_contada"))
print("Diferença:", item_excesso.get("diferenca"))
print("Status:", item_excesso.get("status"))
print("Subtipo:", item_excesso.get("subtipo_divergencia"))


# ============================================================
# 6. VALIDAR TOTAL DO CÓDIGO
# ============================================================

total_estoque = (
    float(item_falta.get("qtd_estoque", 0))
    +
    float(item_excesso.get("qtd_estoque", 0))
)

total_contado = (
    float(item_falta.get("qtd_contada", 0))
    +
    float(item_excesso.get("qtd_contada", 0))
)

diferenca_total = (
    total_contado
    -
    total_estoque
)


print("\nTotal estoque:", total_estoque)
print("Total contado:", total_contado)
print("Diferença total:", diferenca_total)


# ============================================================
# 7. VALIDAÇÃO DO CENÁRIO
#
# Ainda NÃO exigimos LOTE_E_QUANTIDADE.
#
# Primeiro provamos que:
# - existe redistribuição entre lotes
# - e existe divergência total do código
# ============================================================

cenario_ok = (
    float(item_falta.get("diferenca", 0)) == -2
    and
    float(item_excesso.get("diferenca", 0)) == 3
    and
    total_estoque == 3
    and
    total_contado == 4
    and
    diferenca_total == 1
)


if cenario_ok:

    print(
        "\n[APROVADO] "
        "Cenário combinado de lote + quantidade foi reproduzido."
    )

    print("\nDiagnóstico candidato:")

    print(
        "DISTRIBUIÇÃO ENTRE LOTES INCORRETA"
    )

    print(
        "+"
    )

    print(
        "QUANTIDADE TOTAL DO CÓDIGO INCORRETA"
    )

    print(
        "="
    )

    print(
        "LOTE_E_QUANTIDADE"
    )

    sys.exit(0)


print(
    "\n[FALHOU] "
    "O cenário combinado não foi reproduzido corretamente."
)

sys.exit(1)