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


def validar_json(resposta):
    try:
        return resposta.json()
    except Exception:
        return None


# ============================================================
# 1. ABRIR / RECUPERAR SESSÃO
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

dados = validar_json(resposta)

print("HTTP:", resposta.status_code)
print("Resposta:", dados)

if resposta.status_code not in (200, 201):
    print("\n[FALHOU] Não foi possível abrir a sessão.")
    sys.exit(1)

ID_SESSAO = dados.get("id_sessao")

print("ID Sessão:", ID_SESSAO)


# ============================================================
# 2. GARANTIR PELO MENOS UMA CONTAGEM
# ============================================================

titulo("2. REGISTRANDO CONTAGEM")

payload = {
    "id_sessao": ID_SESSAO,
    "codigo": "71256360",
    "lote": "3007849339 - 220",
    "quantidade": 1,
    "usuario": "dev",
}

resposta = requests.post(
    f"{BASE_URL}/contagens",
    json=payload,
)

print("HTTP:", resposta.status_code)
print("Resposta:", validar_json(resposta))

if resposta.status_code not in (200, 201):
    print("\n[FALHOU] Não foi possível registrar a contagem.")
    sys.exit(1)


# ============================================================
# 3. PRIMEIRO ENCERRAMENTO
# ============================================================

titulo("3. PRIMEIRO ENCERRAMENTO")

payload = {
    "id_sessao": ID_SESSAO,
    "usuario": "dev",
}

resposta_1 = requests.post(
    f"{BASE_URL}/localizacoes/encerrar",
    json=payload,
)

dados_1 = validar_json(resposta_1)

print("HTTP:", resposta_1.status_code)
print("Resposta:", dados_1)

if resposta_1.status_code not in (200, 201):
    print("\n[FALHOU] Primeiro encerramento falhou.")
    sys.exit(1)


# ============================================================
# 4. SEGUNDO ENCERRAMENTO
# ============================================================

titulo("4. SEGUNDO ENCERRAMENTO")

resposta_2 = requests.post(
    f"{BASE_URL}/localizacoes/encerrar",
    json=payload,
)

dados_2 = validar_json(resposta_2)

print("HTTP:", resposta_2.status_code)
print("Resposta:", dados_2)


# ============================================================
# 5. AVALIAR COMPORTAMENTO
# ============================================================

titulo("RESULTADO")

# Aceitável:
# - retornar 200 informando que já estava encerrada
# - retornar 400/409 bloqueando nova finalização
#
# Não aceitável:
# - criar novo processamento
# - alterar data/hora de encerramento
# - duplicar registros

if resposta_2.status_code in (400, 409):

    print(
        "\n[APROVADO] "
        "A API bloqueou o segundo encerramento."
    )

    sys.exit(0)


if resposta_2.status_code in (200, 201):

    status_1 = None
    status_2 = None

    if dados_1:
        status_1 = dados_1.get("status")

    if dados_2:
        status_2 = dados_2.get("status")

    if (
        status_1 == "ENCERRADA"
        and
        status_2 == "ENCERRADA"
    ):

        print(
            "\n[APROVADO] "
            "O encerramento é idempotente."
        )

        print(
            "A segunda chamada manteve "
            "a sessão encerrada."
        )

        sys.exit(0)


print(
    "\n[FALHOU] "
    "O segundo encerramento apresentou "
    "comportamento inesperado."
)

sys.exit(1)