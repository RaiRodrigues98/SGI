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


def validar(resposta, etapa):

    if resposta.status_code not in (200, 201):

        print(f"\n[ERRO] {etapa}")
        print("Status:", resposta.status_code)

        try:
            print(resposta.json())
        except Exception:
            print(resposta.text)

        sys.exit(1)

    print(f"[OK] {etapa}")

    return resposta.json()


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

sessao = validar(
    resposta,
    "Sessão aberta"
)

ID_SESSAO = sessao["id_sessao"]

print("ID Sessão:", ID_SESSAO)


# ============================================================
# 2. SALVAR CONTAGEM CORRETA
# ============================================================

titulo("2. REGISTRANDO CONTAGEM CORRETA")

payload = {
    "id_sessao": ID_SESSAO,
    "codigo": "71554091",
    "lote": "3007863031 - 40",
    "quantidade": 2,
    "usuario": "dev",
}

resposta = requests.post(
    f"{BASE_URL}/contagens",
    json=payload,
)

contagem_correta = validar(
    resposta,
    "Contagem correta registrada"
)


# ============================================================
# 3. SALVAR CONTAGEM ERRADA
#
# Essa segunda bipagem será cancelada.
# ============================================================

titulo("3. REGISTRANDO CONTAGEM QUE SERÁ CANCELADA")

payload = {
    "id_sessao": ID_SESSAO,
    "codigo": "71554091",
    "lote": "3007863031 - 40",
    "quantidade": 5,
    "usuario": "dev",
}

resposta = requests.post(
    f"{BASE_URL}/contagens",
    json=payload,
)

contagem_errada = validar(
    resposta,
    "Contagem adicional registrada"
)


ID_CONTAGEM_CANCELAR = (
    contagem_errada.get("id_contagem")
)

if not ID_CONTAGEM_CANCELAR:

    print(
        "\n[FALHOU] "
        "A API não retornou id_contagem."
    )

    print(contagem_errada)

    sys.exit(1)


print(
    "ID a cancelar:",
    ID_CONTAGEM_CANCELAR
)


# ============================================================
# 4. CANCELAR
# ============================================================

titulo("4. CANCELANDO CONTAGEM")

resposta = requests.patch(
    (
        f"{BASE_URL}/contagens/"
        f"{ID_CONTAGEM_CANCELAR}/cancelar"
    )
)

cancelamento = validar(
    resposta,
    "Contagem cancelada"
)

print(
    "Retorno:",
    cancelamento
)


# ============================================================
# 5. LISTAR CONTAGENS
# ============================================================

titulo("5. VALIDANDO REGISTROS")

resposta = requests.get(
    f"{BASE_URL}/sessoes/{ID_SESSAO}/contagens"
)

dados = validar(
    resposta,
    "Consulta das contagens"
)

for item in dados.get("contagens", []):

    print(
        item.get("id_contagem"),
        item.get("quantidade"),
        item.get("status")
    )


# ============================================================
# 6. ENCERRAR
# ============================================================

titulo("6. ENCERRANDO SESSÃO")

payload = {
    "id_sessao": ID_SESSAO,
    "usuario": "dev",
}

resposta = requests.post(
    f"{BASE_URL}/localizacoes/encerrar",
    json=payload,
)

validar(
    resposta,
    "Sessão encerrada"
)


# ============================================================
# 7. ANALISAR
# ============================================================

titulo("7. ANALISANDO RESULTADO")

resposta = requests.get(
    f"{BASE_URL}/sessoes/{ID_SESSAO}/analise"
)

analise = validar(
    resposta,
    "Análise concluída"
)


# ============================================================
# 8. LOCALIZAR ITEM
# ============================================================

item_teste = None

for item in analise.get("itens", []):

    if (
        str(item.get("codigo")).strip() == "71554091"
        and
        str(item.get("lote")).strip() == "3007863031 - 40"
    ):
        item_teste = item
        break


if item_teste is None:

    print(
        "\n[FALHOU] "
        "Item não apareceu na análise."
    )

    sys.exit(1)


# ============================================================
# 9. RESULTADO
#
# Se o cancelamento estiver funcionando:
#
# Contagem ativa = 2
# Contagem cancelada = 5
#
# A análise deve usar SOMENTE 2.
# ============================================================

titulo("RESULTADO")

print(
    "Estoque:",
    item_teste.get("qtd_estoque")
)

print(
    "Contado:",
    item_teste.get("qtd_contada")
)

print(
    "Diferença:",
    item_teste.get("diferenca")
)

print(
    "Status:",
    item_teste.get("status")
)


teste_ok = (
    float(
        item_teste.get(
            "qtd_estoque",
            0
        )
    ) == 2
    and
    float(
        item_teste.get(
            "qtd_contada",
            0
        )
    ) == 2
    and
    float(
        item_teste.get(
            "diferenca",
            0
        )
    ) == 0
    and
    item_teste.get(
        "status"
    ) == "OK"
)


if teste_ok:

    print(
        "\n[APROVADO] "
        "Contagem cancelada foi "
        "desconsiderada corretamente."
    )

    sys.exit(0)


print(
    "\n[FALHOU] "
    "A contagem cancelada ainda está "
    "influenciando a análise."
)

sys.exit(1)