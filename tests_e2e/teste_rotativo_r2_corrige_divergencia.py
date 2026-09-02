import requests
import sys


BASE_URL = "http://127.0.0.1:8000"

ID_INVENTARIO = 13
ID_RODADA = 27

LOCALIZACAO = "01PLAQUETA"

CODIGO = "71554091"
LOTE = "3007863574 - 30"

QUANTIDADE_CORRETA = 1


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
# 1. ABRIR SESSÃO R2
# ============================================================

titulo("1. ABRINDO SESSÃO DA R2")

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
    "Não foi possível abrir a sessão da R2."
)

ID_SESSAO = sessao["id_sessao"]

print("\nID Sessão:", ID_SESSAO)


# ============================================================
# 2. REGISTRAR CONTAGEM CORRETA
# ============================================================

titulo("2. REGISTRANDO CONTAGEM CORRETA NA R2")

resposta = requests.post(
    f"{BASE_URL}/contagens",
    json={
        "id_sessao": ID_SESSAO,
        "codigo": CODIGO,
        "lote": LOTE,
        "quantidade": QUANTIDADE_CORRETA,
        "usuario": "dev",
    },
)

validar(
    resposta,
    "Não foi possível registrar a contagem da R2."
)


# ============================================================
# 3. ENCERRAR SESSÃO
# ============================================================

titulo("3. ENCERRANDO SESSÃO DA R2")

resposta = requests.post(
    f"{BASE_URL}/localizacoes/encerrar",
    json={
        "id_sessao": ID_SESSAO,
        "usuario": "dev",
    },
)

validar(
    resposta,
    "Não foi possível encerrar a sessão da R2."
)


# ============================================================
# 4. ANALISAR RESULTADO
# ============================================================

titulo("4. ANALISANDO RESULTADO DA R2")

resposta = requests.get(
    f"{BASE_URL}/sessoes/{ID_SESSAO}/analise"
)

analise = validar(
    resposta,
    "Não foi possível analisar a sessão da R2."
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
        "\n[FALHOU] "
        "O item recontado não apareceu na análise da R2."
    )

    sys.exit(1)


print("Localização:", item_alvo.get("localizacao"))
print("Código:", item_alvo.get("codigo"))
print("Lote:", item_alvo.get("lote"))
print("Estoque:", item_alvo.get("qtd_estoque"))
print("Contado:", item_alvo.get("qtd_contada"))
print("Diferença:", item_alvo.get("diferenca"))
print("Status:", item_alvo.get("status"))
print(
    "Subtipo:",
    item_alvo.get("subtipo_divergencia")
)
print(
    "Resultado definitivo:",
    item_alvo.get("resultado_definitivo")
)


# ============================================================
# 6. VALIDAÇÃO
# ============================================================

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

resultado_definitivo = bool(
    item_alvo.get(
        "resultado_definitivo",
        False
    )
)


if (
    estoque == 1
    and
    contado == 1
    and
    diferenca == 0
    and
    status == "OK"
    and
    subtipo is None
    and
    resultado_definitivo
):

    print(
        "\n[APROVADO] "
        "A R2 corrigiu a divergência corretamente."
    )

    print(
        "\nRegra validada:"
    )

    print(
        "R1 divergente"
    )

    print(
        "+"
    )

    print(
        "R2 com contagem correta"
    )

    print(
        "="
    )

    print(
        "STATUS OK / DIVERGÊNCIA RESOLVIDA"
    )

    sys.exit(0)


print(
    "\n[FALHOU] "
    "A R2 não retornou o resultado esperado."
)

sys.exit(1)