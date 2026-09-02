import requests
import sys


BASE_URL = "http://127.0.0.1:8000"

ID_INVENTARIO = 14
ID_RODADA = 28

LOCALIZACAO = "01PLAQUETA"

CODIGO = "71554091"
LOTE = "3007863574 - 30"

# Snapshot esperado = 1
# Vamos contar 2 para gerar divergência +1.
QUANTIDADE_CONTADA = 2


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
        print(f"\n[FALHOU] {etapa}")
        sys.exit(1)

    return dados


# ============================================================
# 1. ABRIR SESSÃO R1
# ============================================================

titulo("1. ABRINDO SESSÃO DA R1")

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
    "Não foi possível abrir a sessão da R1."
)

ID_SESSAO = sessao["id_sessao"]

print("\nID Sessão:", ID_SESSAO)


# ============================================================
# 2. REGISTRAR CONTAGEM DIVERGENTE
# ============================================================

titulo("2. REGISTRANDO CONTAGEM DIVERGENTE")

resposta = requests.post(
    f"{BASE_URL}/contagens",
    json={
        "id_sessao": ID_SESSAO,
        "codigo": CODIGO,
        "lote": LOTE,
        "quantidade": QUANTIDADE_CONTADA,
        "usuario": "dev",
    },
)

validar(
    resposta,
    "Não foi possível registrar a contagem da R1."
)


# ============================================================
# 3. ENCERRAR SESSÃO
# ============================================================

titulo("3. ENCERRANDO SESSÃO DA R1")

resposta = requests.post(
    f"{BASE_URL}/localizacoes/encerrar",
    json={
        "id_sessao": ID_SESSAO,
        "usuario": "dev",
    },
)

validar(
    resposta,
    "Não foi possível encerrar a sessão da R1."
)


# ============================================================
# 4. ANALISAR RESULTADO
# ============================================================

titulo("4. ANALISANDO RESULTADO DA R1")

resposta = requests.get(
    f"{BASE_URL}/sessoes/{ID_SESSAO}/analise"
)

analise = validar(
    resposta,
    "Não foi possível analisar a sessão da R1."
)


# ============================================================
# 5. LOCALIZAR ITEM
# ============================================================

item_alvo = None

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
        lote == LOTE
    ):
        item_alvo = item
        break


titulo("RESULTADO")


if item_alvo is None:

    print(
        "[FALHOU] "
        "O item não apareceu na análise."
    )

    sys.exit(1)


estoque = float(
    item_alvo.get("qtd_estoque", 0)
)

contado = float(
    item_alvo.get("qtd_contada", 0)
)

diferenca = float(
    item_alvo.get("diferenca", 0)
)

status = item_alvo.get("status")

subtipo = item_alvo.get(
    "subtipo_divergencia"
)


print("Localização:", item_alvo.get("localizacao"))
print("Código:", item_alvo.get("codigo"))
print("Lote:", item_alvo.get("lote"))

print("Estoque:", estoque)
print("Contado:", contado)
print("Diferença:", diferenca)

print("Status:", status)
print("Subtipo:", subtipo)

print(
    "Requer decisão:",
    item_alvo.get("requer_decisao")
)

print(
    "Pendente decisão:",
    item_alvo.get("pendente_decisao")
)


# ============================================================
# 6. VALIDAR
# ============================================================

if (
    estoque == 1
    and
    contado == 2
    and
    diferenca == 1
    and
    status != "OK"
    and
    item_alvo.get("requer_decisao") is True
):

    print(
        "\n[APROVADO] "
        "A divergência da R1 foi criada corretamente."
    )

    print(
        "\nPróxima regra:"
    )

    print(
        "DIVERGÊNCIA R1"
    )

    print(
        "→ registrar decisão RECONTAR"
    )

    sys.exit(0)


print(
    "\n[FALHOU] "
    "A R1 não produziu a divergência esperada."
)

sys.exit(1)