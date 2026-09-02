import requests
import sys


# ============================================================
# CONFIGURAÇÕES
# ============================================================

BASE_URL = "http://127.0.0.1:8000"

ID_INVENTARIO = 13
ID_RODADA = 25
LOCALIZACAO = "01PLAQUETA"

CODIGO = "TESTE-ZERO-001"
LOTE = "LOTE-ZERO"
QUANTIDADE = 1


# ============================================================
# UTILITÁRIOS
# ============================================================

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
    "Não foi possível abrir a sessão."
)

ID_SESSAO = sessao["id_sessao"]

print("\nID Sessão:", ID_SESSAO)


# ============================================================
# 2. REGISTRAR ITEM COM SALDO ZERO
# ============================================================

titulo("2. REGISTRANDO ITEM COM SALDO ZERO")

payload = {
    "id_sessao": ID_SESSAO,
    "codigo": CODIGO,
    "lote": LOTE,
    "quantidade": QUANTIDADE,
    "usuario": "dev",
}

resposta = requests.post(
    f"{BASE_URL}/contagens",
    json=payload,
)

validar(
    resposta,
    "Não foi possível registrar a contagem."
)


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

validar(
    resposta,
    "Não foi possível encerrar a sessão."
)


# ============================================================
# 4. ANALISAR RESULTADO
# ============================================================

titulo("4. ANALISANDO RESULTADO")

resposta = requests.get(
    f"{BASE_URL}/sessoes/{ID_SESSAO}/analise"
)

analise = validar(
    resposta,
    "Não foi possível executar a análise."
)


# ============================================================
# 5. LOCALIZAR ITEM
# ============================================================

item_teste = None

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
        item_teste = item
        break


# ============================================================
# 6. VALIDAR EXISTÊNCIA
# ============================================================

titulo("RESULTADO")

if item_teste is None:

    print(
        f"[FALHOU] {CODIGO} / {LOTE} "
        "não apareceu na análise."
    )

    sys.exit(1)


# ============================================================
# 7. EXIBIR RESULTADO
# ============================================================

print("Localização:", item_teste.get("localizacao"))
print("Código:", item_teste.get("codigo"))
print("Lote:", item_teste.get("lote"))
print("Estoque:", item_teste.get("qtd_estoque"))
print("Contado:", item_teste.get("qtd_contada"))
print("Diferença:", item_teste.get("diferenca"))

print(
    "Existe no snapshot:",
    item_teste.get("existe_no_snapshot")
)

print("Status:", item_teste.get("status"))

print(
    "Subtipo:",
    item_teste.get("subtipo_divergencia")
)

print(
    "Localizações esperadas:",
    item_teste.get("localizacoes_esperadas")
)


# ============================================================
# 8. ASSERTIVAS
# ============================================================

teste_ok = (
    float(
        item_teste.get(
            "qtd_estoque",
            -999
        )
    ) == 0

    and

    float(
        item_teste.get(
            "qtd_contada",
            -999
        )
    ) == 1

    and

    float(
        item_teste.get(
            "diferenca",
            -999
        )
    ) == 1

    and

    item_teste.get(
        "existe_no_snapshot"
    ) is True

    and

    item_teste.get(
        "status"
    ) == "DIVERGÊNCIA"

    and

    item_teste.get(
        "subtipo_divergencia"
    ) == "ITEM_SEM_SALDO"

    and

    item_teste.get(
        "localizacoes_esperadas"
    ) == []
)


# ============================================================
# 9. RESULTADO FINAL
# ============================================================

if teste_ok:

    print(
        "\n[APROVADO] "
        "Item existente no snapshot com saldo zero "
        "foi classificado corretamente."
    )

    print("\nRegra validada:")

    print(
        "SALDO ZERO + CONTAGEM FÍSICA > 0 "
        "-> DIVERGÊNCIA / ITEM_SEM_SALDO"
    )

    sys.exit(0)


print(
    "\n[FALHOU] "
    "O item com saldo zero não foi "
    "classificado conforme esperado."
)

print("\nEsperado:")

print("Estoque: 0")
print("Contado: 1")
print("Diferença: 1")
print("Existe no snapshot: True")
print("Status: DIVERGÊNCIA")
print("Subtipo: ITEM_SEM_SALDO")
print("Localizações esperadas: []")

sys.exit(1)