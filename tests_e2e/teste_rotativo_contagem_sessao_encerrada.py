import requests
import sys


BASE_URL = "http://127.0.0.1:8000"

ID_SESSAO = 65


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
# 1. TENTAR SALVAR CONTAGEM EM SESSÃO ENCERRADA
# ============================================================

titulo("1. TENTANDO SALVAR CONTAGEM EM SESSÃO ENCERRADA")

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

dados = json_seguro(resposta)

print("HTTP:", resposta.status_code)
print("Resposta:", dados)


# ============================================================
# 2. AVALIAR RESULTADO
# ============================================================

titulo("RESULTADO")


# ------------------------------------------------------------
# Comportamento esperado:
# sessão encerrada não pode receber novas contagens.
# ------------------------------------------------------------

if resposta.status_code in (400, 409):

    print(
        "\n[APROVADO] "
        "A API bloqueou nova contagem "
        "em sessão encerrada."
    )

    if dados:
        print(
            "Detalhe:",
            dados.get("detail")
        )

    sys.exit(0)


# ------------------------------------------------------------
# Também aceitamos 200 com sucesso=false,
# caso essa seja a convenção do endpoint.
# ------------------------------------------------------------

if resposta.status_code in (200, 201):

    if dados:

        sucesso = dados.get("sucesso")

        if sucesso is False:

            print(
                "\n[APROVADO] "
                "A API recusou a nova contagem "
                "sem alterar a sessão."
            )

            print(
                "Motivo:",
                dados.get("motivo")
            )

            sys.exit(0)


# ============================================================
# FALHA
# ============================================================

print(
    "\n[FALHOU] "
    "A API permitiu registrar uma nova contagem "
    "em uma sessão já encerrada."
)

print(
    "\nIsso pode causar:"
)

print(
    "- alteração retroativa do resultado"
)

print(
    "- divergência entre histórico e análise"
)

print(
    "- mudança de quantidade após fechamento"
)

print(
    "- perda de rastreabilidade"
)

sys.exit(1)