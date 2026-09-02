import requests
import sys


# ============================================================
# CONFIGURAÇÕES
# ============================================================

BASE_URL = "http://127.0.0.1:8000"

ID_INVENTARIO = 13
ID_RODADA = 25
LOCALIZACAO = "01PLAQUETA"


# ============================================================
# UTILITÁRIOS
# ============================================================

def titulo(texto):
    print("\n" + "=" * 70)
    print(texto)
    print("=" * 70)


def mostrar_resposta(resposta):
    print("HTTP:", resposta.status_code)

    try:
        dados = resposta.json()
        print("Resposta:", dados)
        return dados

    except Exception:
        print("Resposta:", resposta.text)
        return None


# ============================================================
# 1. PRIMEIRA ABERTURA
# ============================================================

titulo("1. ABRINDO PRIMEIRA SESSÃO")

payload = {
    "id_inventario": ID_INVENTARIO,
    "id_rodada": ID_RODADA,
    "localizacao": LOCALIZACAO,
}

resposta_1 = requests.post(
    f"{BASE_URL}/localizacoes/iniciar",
    json=payload,
)

dados_1 = mostrar_resposta(resposta_1)


if resposta_1.status_code not in (200, 201):

    print(
        "\n[FALHOU] "
        "Não foi possível abrir a primeira sessão."
    )

    sys.exit(1)


ID_SESSAO_1 = dados_1.get("id_sessao")


if not ID_SESSAO_1:

    print(
        "\n[FALHOU] "
        "Primeira abertura não retornou id_sessao."
    )

    sys.exit(1)


print(
    "\nPrimeira sessão:",
    ID_SESSAO_1
)


# ============================================================
# 2. SEGUNDA ABERTURA
#
# NÃO encerramos a primeira.
#
# Tentamos abrir exatamente:
#
# mesmo inventário
# mesma rodada
# mesma localização
# ============================================================

titulo("2. TENTANDO ABRIR A MESMA LOCALIZAÇÃO NOVAMENTE")

resposta_2 = requests.post(
    f"{BASE_URL}/localizacoes/iniciar",
    json=payload,
)

dados_2 = mostrar_resposta(resposta_2)


# ============================================================
# 3. CLASSIFICAR COMPORTAMENTO
# ============================================================

titulo("3. ANALISANDO COMPORTAMENTO")


# ------------------------------------------------------------
# CASO A
# API rejeitou a segunda abertura.
#
# Exemplo:
# HTTP 400
# HTTP 409
# ------------------------------------------------------------

if resposta_2.status_code in (400, 409):

    print(
        "\n[APROVADO] "
        "A API bloqueou a abertura duplicada."
    )

    print(
        "Regra observada: "
        "uma localização não pode possuir "
        "duas sessões abertas simultaneamente."
    )

    sys.exit(0)


# ------------------------------------------------------------
# Qualquer outro erro inesperado
# ------------------------------------------------------------

if resposta_2.status_code not in (200, 201):

    print(
        "\n[FALHOU] "
        "A segunda tentativa retornou um "
        "HTTP inesperado."
    )

    sys.exit(1)


# ------------------------------------------------------------
# A segunda chamada retornou sucesso.
#
# Agora precisamos saber se reutilizou a sessão
# ou criou uma nova.
# ------------------------------------------------------------

if not dados_2:

    print(
        "\n[FALHOU] "
        "Segunda abertura retornou sucesso "
        "sem JSON válido."
    )

    sys.exit(1)


ID_SESSAO_2 = dados_2.get("id_sessao")


print(
    "\nSessão primeira chamada:",
    ID_SESSAO_1
)

print(
    "Sessão segunda chamada:",
    ID_SESSAO_2
)


# ============================================================
# 4. REUTILIZAÇÃO
# ============================================================

if ID_SESSAO_2 == ID_SESSAO_1:

    print(
        "\n[APROVADO] "
        "A API reutilizou a sessão que já "
        "estava aberta."
    )

    print(
        "\nComportamento idempotente:"
    )

    print(
        "POST /localizacoes/iniciar"
    )

    print(
        "não criou sessão duplicada."
    )

    sys.exit(0)


# ============================================================
# 5. DUPLICIDADE REAL
# ============================================================

print(
    "\n[FALHOU] "
    "A API criou duas sessões diferentes "
    "para a mesma localização."
)

print(
    "\nSessão 1:",
    ID_SESSAO_1
)

print(
    "Sessão 2:",
    ID_SESSAO_2
)

print(
    "\nIsso representa risco de:"
)

print(
    "- duplicidade de contagem"
)

print(
    "- conflito de operadores"
)

print(
    "- dupla conciliação"
)

print(
    "- histórico inconsistente"
)

print(
    "- processamento duplicado da localização"
)

sys.exit(1)