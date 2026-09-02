import requests
import sys


BASE_URL = "http://127.0.0.1:8000"

ID_INVENTARIO = 13
ID_RODADA = 25
LOCALIZACAO = "01REIT00101"
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

dados = json_seguro(resposta)

print("HTTP:", resposta.status_code)
print("Resposta:", dados)

if resposta.status_code not in (200, 201):
    print(
        "\n[FALHOU] "
        "Não foi possível abrir a sessão."
    )
    sys.exit(1)

ID_SESSAO = dados.get("id_sessao")

if not ID_SESSAO:
    print(
        "\n[FALHOU] "
        "A API não retornou id_sessao."
    )
    sys.exit(1)

print("ID Sessão:", ID_SESSAO)


# ============================================================
# 2. CONFIRMAR QUE A SESSÃO ESTÁ ABERTA
# ============================================================

status_sessao = dados.get("status_sessao")

if status_sessao != "ABERTA":
    print(
        "\n[FALHOU] "
        "A sessão deveria estar ABERTA para este teste."
    )
    print("Status recebido:", status_sessao)
    sys.exit(1)


# ============================================================
# 3. TENTAR CONCLUIR SEM ENCERRAR
# ============================================================

titulo("2. TENTANDO CONCLUIR COM SESSÃO ABERTA")

payload = {
    "id_sessao": ID_SESSAO,
    "usuario": USUARIO,
}

resposta = requests.post(
    f"{BASE_URL}/rotativo/ciclos/localizacoes/concluir",
    json=payload,
)

dados_conclusao = json_seguro(resposta)

print("HTTP:", resposta.status_code)
print("Resposta:", dados_conclusao)


# ============================================================
# 4. AVALIAR RESULTADO
# ============================================================

titulo("RESULTADO")


# ============================================================
# COMPORTAMENTO ESPERADO
#
# Deve bloquear enquanto a sessão estiver aberta.
# ============================================================

if resposta.status_code in (400, 409):

    print(
        "\n[APROVADO] "
        "A API bloqueou a conclusão da localização "
        "com a sessão ainda aberta."
    )

    if dados_conclusao:
        print(
            "Detalhe:",
            dados_conclusao.get("detail")
        )

    sys.exit(0)


# ============================================================
# CASO A API RETORNE 200 COM REGISTRADO = FALSE
# ============================================================

if resposta.status_code in (200, 201):

    if dados_conclusao:

        registrado = dados_conclusao.get("registrado")
        motivo = dados_conclusao.get("motivo")

        if registrado is False:

            print(
                "\n[APROVADO] "
                "A API recusou a conclusão "
                "sem registrar a localização."
            )

            print(
                "Motivo:",
                motivo
            )

            sys.exit(0)


# ============================================================
# FALHA
# ============================================================

print(
    "\n[FALHOU] "
    "A API permitiu ou tratou de forma inesperada "
    "a conclusão de uma localização com sessão aberta."
)

print(
    "\nRisco:"
)

print(
    "- localização marcada como CONTADA antes do fim"
)

print(
    "- histórico incompleto"
)

print(
    "- inteligência processada com dados parciais"
)

print(
    "- cobertura do ciclo incorreta"
)

sys.exit(1)