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
# 2. CONTAGEM
#
# Não contamos o primeiro lote.
#
# Colocamos todas as 3 unidades no segundo lote.
# ============================================================

titulo("2. REGISTRANDO DISTRIBUIÇÃO INCORRETA ENTRE LOTES")

resposta = requests.post(
    f"{BASE_URL}/contagens",
    json={
        "id_sessao": ID_SESSAO,
        "codigo": CODIGO,
        "lote": LOTE_EXCESSO,
        "quantidade": 3,
        "usuario": "dev",
    },
)

validar(
    resposta,
    "Não foi possível registrar a contagem."
)


# ============================================================
# 3. ENCERRAR SESSÃO
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
# 5. LOCALIZAR OS DOIS LOTES
# ============================================================

item_falta = None
item_excesso = None

for item in analise.get("itens", []):

    codigo = str(
        item.get("codigo", "")
    ).strip()

    lote = str(
        item.get("lote", "")
    ).strip()

    if (
        codigo == CODIGO
        and
        lote == LOTE_FALTA
    ):
        item_falta = item

    if (
        codigo == CODIGO
        and
        lote == LOTE_EXCESSO
    ):
        item_excesso = item


titulo("RESULTADO")


if item_falta is None:
    print(
        "\n[FALHOU] "
        "O lote com falta não apareceu."
    )
    sys.exit(1)


if item_excesso is None:
    print(
        "\n[FALHOU] "
        "O lote com excesso não apareceu."
    )
    sys.exit(1)


print("\nLOTE COM FALTA")

print("Lote:", item_falta.get("lote"))
print("Estoque:", item_falta.get("qtd_estoque"))
print("Contado:", item_falta.get("qtd_contada"))
print("Diferença:", item_falta.get("diferenca"))
print("Status:", item_falta.get("status"))
print(
    "Subtipo:",
    item_falta.get("subtipo_divergencia")
)


print("\nLOTE COM EXCESSO")

print("Lote:", item_excesso.get("lote"))
print("Estoque:", item_excesso.get("qtd_estoque"))
print("Contado:", item_excesso.get("qtd_contada"))
print("Diferença:", item_excesso.get("diferenca"))
print("Status:", item_excesso.get("status"))
print(
    "Subtipo:",
    item_excesso.get("subtipo_divergencia")
)


# ============================================================
# 6. VALIDAR QUANTIDADES
# ============================================================

quantidade_total_estoque = (
    float(item_falta.get("qtd_estoque", 0))
    +
    float(item_excesso.get("qtd_estoque", 0))
)

quantidade_total_contada = (
    float(item_falta.get("qtd_contada", 0))
    +
    float(item_excesso.get("qtd_contada", 0))
)


print(
    "\nTotal estoque do código:",
    quantidade_total_estoque
)

print(
    "Total contado do código:",
    quantidade_total_contada
)


# ============================================================
# 7. RESULTADO DO MOTOR ATUAL
#
# Neste momento NÃO exigimos ainda LOTE_INCORRETO.
#
# Queremos primeiro confirmar que:
#
# estoque total = contado total
#
# apesar de existir divergência entre os lotes.
# ============================================================

quantidades_ok = (
    quantidade_total_estoque == 3
    and
    quantidade_total_contada == 3
)

divergencia_lotes_ok = (
    float(
        item_falta.get(
            "diferenca",
            0
        )
    ) == -2

    and

    float(
        item_excesso.get(
            "diferenca",
            0
        )
    ) == 2
)


if (
    quantidades_ok
    and
    divergencia_lotes_ok
):

    print(
        "\n[APROVADO] "
        "Cenário de distribuição incorreta "
        "entre lotes foi reproduzido."
    )

    print(
        "\nDiagnóstico candidato:"
    )

    print(
        "QUANTIDADE TOTAL DO CÓDIGO CORRETA"
    )

    print(
        "+"
    )

    print(
        "DISTRIBUIÇÃO ENTRE LOTES INCORRETA"
    )

    print(
        "="
    )

    print(
        "LOTE_INCORRETO"
    )

    sys.exit(0)


print(
    "\n[FALHOU] "
    "O cenário de lote incorreto não foi reproduzido."
)

sys.exit(1)