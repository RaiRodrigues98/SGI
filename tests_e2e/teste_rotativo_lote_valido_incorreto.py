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
# 2. REGISTRAR CONTAGENS
#
# Estoque esperado:
#
# 71256360 / 3007849339 - 220 = 1
#
# 71554091 / 3007863031 - 40 = 2
# 71554091 / 3007863574 - 30 = 1
#
# Teste proposital:
#
# Não contar:
# 71554091 / 3007863031 - 40
#
# Contar 3 unidades em:
# 71554091 / 3007863574 - 30
#
# Resultado esperado:
#
# 3007863031 - 40
# estoque = 2
# contado = 0
# diferença = -2
# status = FALTA
#
# 3007863574 - 30
# estoque = 1
# contado = 3
# diferença = +2
# status = DIVERGÊNCIA
# ============================================================

titulo("2. REGISTRANDO CONTAGENS")

contagens = [
    {
        "codigo": "71256360",
        "lote": "3007849339 - 220",
        "quantidade": 1,
    },
    {
        "codigo": "71554091",
        "lote": "3007863574 - 30",
        "quantidade": 3,
    },
]


for item in contagens:

    payload = {
        "id_sessao": ID_SESSAO,
        "codigo": item["codigo"],
        "lote": item["lote"],
        "quantidade": item["quantidade"],
        "usuario": "dev",
    }

    resposta = requests.post(
        f"{BASE_URL}/contagens",
        json=payload,
    )

    validar(
        resposta,
        f'{item["codigo"]} / {item["lote"]}'
    )


# ============================================================
# 3. VALIDAR CONTAGENS
# ============================================================

titulo("3. VALIDANDO CONTAGENS")

resposta = requests.get(
    f"{BASE_URL}/sessoes/{ID_SESSAO}/contagens"
)

dados_contagens = validar(
    resposta,
    "Consulta das contagens"
)

total_registros = dados_contagens.get(
    "total_registros",
    0
)

print(
    "Total registros:",
    total_registros
)

if total_registros != 2:

    print(
        "\n[FALHOU] "
        "Era esperado exatamente 2 registros."
    )

    sys.exit(1)


# ============================================================
# 4. ENCERRAR SESSÃO
# ============================================================

titulo("4. ENCERRANDO SESSÃO")

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
# 5. ANALISAR RESULTADO
# ============================================================

titulo("5. ANALISANDO RESULTADO")

resposta = requests.get(
    f"{BASE_URL}/sessoes/{ID_SESSAO}/analise"
)

analise = validar(
    resposta,
    "Análise concluída"
)


# ============================================================
# 6. LOCALIZAR OS DOIS LOTES
# ============================================================

falta_lote_original = None
divergencia_lote_destino = None


for item in analise.get(
    "itens",
    []
):

    codigo = str(
        item.get(
            "codigo",
            ""
        )
    ).strip()

    lote = str(
        item.get(
            "lote",
            ""
        )
    ).strip()

    # --------------------------------------------------------
    # Lote esperado, mas não contado
    # --------------------------------------------------------

    if (
        codigo == "71554091"
        and
        lote == "3007863031 - 40"
    ):
        falta_lote_original = item

    # --------------------------------------------------------
    # Lote válido, porém com quantidade acima do esperado
    # --------------------------------------------------------

    if (
        codigo == "71554091"
        and
        lote == "3007863574 - 30"
    ):
        divergencia_lote_destino = item


# ============================================================
# 7. VALIDAR EXISTÊNCIA DOS RESULTADOS
# ============================================================

titulo("RESULTADO")


if falta_lote_original is None:

    print(
        "[FALHOU] "
        "O lote 3007863031 - 40 "
        "não apareceu na análise."
    )

    sys.exit(1)


if divergencia_lote_destino is None:

    print(
        "[FALHOU] "
        "O lote 3007863574 - 30 "
        "não apareceu na análise."
    )

    sys.exit(1)


# ============================================================
# 8. EXIBIR FALTA
# ============================================================

print("\nLOTE QUE FICOU SEM CONTAGEM:")

print(
    "Código:",
    falta_lote_original.get("codigo")
)

print(
    "Lote:",
    falta_lote_original.get("lote")
)

print(
    "Estoque:",
    falta_lote_original.get("qtd_estoque")
)

print(
    "Contado:",
    falta_lote_original.get("qtd_contada")
)

print(
    "Diferença:",
    falta_lote_original.get("diferenca")
)

print(
    "Status:",
    falta_lote_original.get("status")
)


# ============================================================
# 9. EXIBIR DIVERGÊNCIA POSITIVA
# ============================================================

print("\nLOTE QUE RECEBEU QUANTIDADE A MAIS:")

print(
    "Código:",
    divergencia_lote_destino.get("codigo")
)

print(
    "Lote:",
    divergencia_lote_destino.get("lote")
)

print(
    "Estoque:",
    divergencia_lote_destino.get("qtd_estoque")
)

print(
    "Contado:",
    divergencia_lote_destino.get("qtd_contada")
)

print(
    "Diferença:",
    divergencia_lote_destino.get("diferenca")
)

print(
    "Status:",
    divergencia_lote_destino.get("status")
)


# ============================================================
# 10. VALIDAR RESULTADOS
# ============================================================

teste_falta_ok = (
    float(
        falta_lote_original.get(
            "qtd_estoque",
            0
        )
    ) == 2
    and
    float(
        falta_lote_original.get(
            "qtd_contada",
            0
        )
    ) == 0
    and
    float(
        falta_lote_original.get(
            "diferenca",
            0
        )
    ) == -2
    and
    falta_lote_original.get(
        "status"
    ) == "FALTA"
)


teste_divergencia_ok = (
    float(
        divergencia_lote_destino.get(
            "qtd_estoque",
            0
        )
    ) == 1
    and
    float(
        divergencia_lote_destino.get(
            "qtd_contada",
            0
        )
    ) == 3
    and
    float(
        divergencia_lote_destino.get(
            "diferenca",
            0
        )
    ) == 2
    and
    divergencia_lote_destino.get(
        "status"
    ) == "DIVERGÊNCIA"
)


# ============================================================
# 11. RESULTADO FINAL
# ============================================================

if (
    teste_falta_ok
    and
    teste_divergencia_ok
):

    print(
        "\n[APROVADO] "
        "Motor identificou corretamente "
        "a distribuição incorreta entre lotes."
    )

    print(
        "\nRegra validada:"
    )

    print(
        "LOCALIZACAO + CODIGO + LOTE"
    )

    print(
        "\nResultado esperado:"
    )

    print(
        "71554091 / 3007863031 - 40 "
        "-> FALTA"
    )

    print(
        "71554091 / 3007863574 - 30 "
        "-> DIVERGÊNCIA"
    )

    sys.exit(0)


print(
    "\n[FALHOU] "
    "O comportamento para distribuição "
    "incorreta entre lotes não foi o esperado."
)

if not teste_falta_ok:

    print(
        "- Falha na identificação da FALTA."
    )

if not teste_divergencia_ok:

    print(
        "- Falha na identificação da DIVERGÊNCIA positiva."
    )

sys.exit(1)