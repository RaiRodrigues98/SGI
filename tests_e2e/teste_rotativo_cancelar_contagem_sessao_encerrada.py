import requests
import sys


BASE_URL = "http://127.0.0.1:8000"

ID_INVENTARIO = 13
ID_RODADA = 25
LOCALIZACAO = "01REIT00101"


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
# 2. REGISTRAR UMA CONTAGEM
# ============================================================

titulo("2. REGISTRANDO CONTAGEM")

payload = {
    "id_sessao": ID_SESSAO,
    "codigo": "70194232",
    "lote": "REIT",
    "quantidade": 1,
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
    print("\n[FALHOU] Não foi possível registrar a contagem.")
    sys.exit(1)

ID_CONTAGEM = dados_contagem.get("id_contagem")

if not ID_CONTAGEM:
    print("\n[FALHOU] id_contagem não retornado.")
    sys.exit(1)

print("ID Contagem:", ID_CONTAGEM)


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

dados_encerramento = json_seguro(resposta)

print("HTTP:", resposta.status_code)
print("Resposta:", dados_encerramento)

if resposta.status_code not in (200, 201):
    print("\n[FALHOU] Não foi possível encerrar a sessão.")
    sys.exit(1)


# ============================================================
# 4. TENTAR CANCELAR APÓS ENCERRAMENTO
# ============================================================

titulo("4. TENTANDO CANCELAR CONTAGEM APÓS ENCERRAMENTO")

resposta = requests.patch(
    f"{BASE_URL}/contagens/{ID_CONTAGEM}/cancelar"
)

dados_cancelamento = json_seguro(resposta)

print("HTTP:", resposta.status_code)
print("Resposta:", dados_cancelamento)


# ============================================================
# 5. AVALIAR RESULTADO
# ============================================================

titulo("RESULTADO")

if resposta.status_code in (400, 409):

    print(
        "\n[APROVADO] "
        "A API bloqueou o cancelamento de contagem "
        "em sessão encerrada."
    )

    if dados_cancelamento:
        print(
            "Detalhe:",
            dados_cancelamento.get("detail")
        )

    sys.exit(0)


if resposta.status_code in (200, 201):

    if dados_cancelamento:

        sucesso = dados_cancelamento.get("sucesso")

        if sucesso is False:

            print(
                "\n[APROVADO] "
                "A API recusou o cancelamento "
                "sem alterar a contagem."
            )

            print(
                "Motivo:",
                dados_cancelamento.get("motivo")
            )

            sys.exit(0)


print(
    "\n[FALHOU] "
    "A API permitiu cancelar uma contagem "
    "depois que a sessão já estava encerrada."
)

print(
    "\nRiscos:"
)

print(
    "- alteração retroativa da conciliação"
)

print(
    "- inconsistência entre histórico e contagens"
)

print(
    "- mudança do resultado após fechamento"
)

print(
    "- perda de rastreabilidade"
)

sys.exit(1)