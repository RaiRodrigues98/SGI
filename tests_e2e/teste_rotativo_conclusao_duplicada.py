import requests
import sys


BASE_URL = "http://127.0.0.1:8000"

ID_SESSAO = 65
USUARIO = "dev"


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
# 1. PRIMEIRA CONCLUSÃO
# ============================================================

titulo("1. PRIMEIRA CONCLUSÃO DA LOCALIZAÇÃO")

payload = {
    "id_sessao": ID_SESSAO,
    "usuario": USUARIO,
}

resposta_1 = requests.post(
    f"{BASE_URL}/rotativo/ciclos/localizacoes/concluir",
    json=payload,
)

dados_1 = json_seguro(resposta_1)

print("HTTP:", resposta_1.status_code)
print("Resposta:", dados_1)


if resposta_1.status_code not in (200, 201):

    print(
        "\n[FALHOU] "
        "A primeira conclusão da localização falhou."
    )

    sys.exit(1)


# ============================================================
# 2. SEGUNDA CONCLUSÃO
# ============================================================

titulo("2. SEGUNDA CONCLUSÃO DA MESMA LOCALIZAÇÃO")

resposta_2 = requests.post(
    f"{BASE_URL}/rotativo/ciclos/localizacoes/concluir",
    json=payload,
)

dados_2 = json_seguro(resposta_2)

print("HTTP:", resposta_2.status_code)
print("Resposta:", dados_2)


# ============================================================
# 3. AVALIAR RESULTADO
# ============================================================

titulo("RESULTADO")


# ------------------------------------------------------------
# CASO A
# Bloqueio explícito
# ------------------------------------------------------------

if resposta_2.status_code in (400, 409):

    print(
        "\n[APROVADO] "
        "A API bloqueou a conclusão duplicada."
    )

    sys.exit(0)


# ------------------------------------------------------------
# CASO B
# Idempotência
# ------------------------------------------------------------

if resposta_2.status_code in (200, 201):

    if dados_2:

        registrado = dados_2.get("registrado")
        motivo = dados_2.get("motivo")

        if (
            registrado is False
            or motivo
            in (
                "LOCALIZACAO_JA_CONTADA",
                "LOCALIZACAO_JA_PROCESSADA",
                "SESSAO_JA_REGISTRADA",
            )
        ):

            print(
                "\n[APROVADO] "
                "A API tratou a segunda conclusão "
                "de forma idempotente."
            )

            print(
                "Motivo:",
                motivo
            )

            sys.exit(0)


print(
    "\n[FALHOU] "
    "A segunda conclusão apresentou "
    "comportamento inesperado."
)

print(
    "\nVerifique se houve:"
)

print(
    "- duplicidade em HistoricoContagens"
)

print(
    "- incremento duplicado de cobertura"
)

print(
    "- duplicidade de processamento da localização"
)

sys.exit(1)