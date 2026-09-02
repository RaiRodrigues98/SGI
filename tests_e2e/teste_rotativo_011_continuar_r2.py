import requests


BASE_URL = "http://127.0.0.1:8000"

ID_INVENTARIO = 21
ID_RODADA_R2 = 42

LOCALIZACAO = "01PLAQUETA"
USUARIO = "teste_e2e"


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
        raise SystemExit(
            f"\n[FALHOU] {etapa}"
        )

    return dados


# ============================================================
# 1. ABRIR R2
# ============================================================

titulo("1. ABRINDO R2")

resposta = requests.post(
    f"{BASE_URL}/localizacoes/iniciar",
    json={
        "id_inventario": ID_INVENTARIO,
        "id_rodada": ID_RODADA_R2,
        "localizacao": LOCALIZACAO
    }
)

dados = validar(
    resposta,
    "Falha ao abrir R2."
)

ID_SESSAO_R2 = dados["id_sessao"]

print(
    "\nID Sessão R2:",
    ID_SESSAO_R2
)


# ============================================================
# 2. ITEM A
#
# WMS = 2
# R1 = 1
# R2 = 2
# ESPERADO => RESOLVIDO_R2
# ============================================================

titulo("2. ITEM A - CORRIGINDO NA R2")

resposta = requests.post(
    f"{BASE_URL}/contagens",
    json={
        "id_sessao": ID_SESSAO_R2,
        "codigo": "71554091",
        "lote": "3007863031 - 40",
        "quantidade": 2,
        "usuario": USUARIO
    }
)

validar(
    resposta,
    "Falha ao contar item A."
)


# ============================================================
# 3. ITEM B
#
# WMS = 1
# R1 = 2
# R2 = 2
# ESPERADO => DIVERGENCIA_CONFIRMADA
# ============================================================

titulo("3. ITEM B - REPETINDO DIVERGÊNCIA")

resposta = requests.post(
    f"{BASE_URL}/contagens",
    json={
        "id_sessao": ID_SESSAO_R2,
        "codigo": "71554091",
        "lote": "3007863574 - 30",
        "quantidade": 2,
        "usuario": USUARIO
    }
)

validar(
    resposta,
    "Falha ao contar item B."
)


# ============================================================
# 4. ENCERRAR R2
# ============================================================

titulo("4. ENCERRANDO R2")

resposta = requests.post(
    f"{BASE_URL}/localizacoes/encerrar",
    json={
        "id_sessao": ID_SESSAO_R2,
        "usuario": USUARIO
    }
)

validar(
    resposta,
    "Falha ao encerrar R2."
)


# ============================================================
# 5. ANALISAR R2
# ============================================================

titulo("5. ANALISANDO R2")

resposta = requests.get(
    f"{BASE_URL}/sessoes/{ID_SESSAO_R2}/analise"
)

analise = validar(
    resposta,
    "Falha ao analisar R2."
)

itens = analise.get(
    "itens",
    []
)

for item in itens:

    print(
        "\nCódigo:",
        item.get("codigo")
    )

    print(
        "Lote:",
        item.get("lote")
    )

    print(
        "Estoque:",
        item.get("qtd_estoque")
    )

    print(
        "R2:",
        item.get("qtd_contada")
    )

    print(
        "Diferença:",
        item.get("diferenca")
    )

    print(
        "Status:",
        item.get("status")
    )


# ============================================================
# 6. VALIDAR R2
# ============================================================

titulo("6. VALIDANDO R2")

item_resolvido = next(
    (
        item
        for item in itens
        if item.get("lote")
        == "3007863031 - 40"
    ),
    None
)

item_confirmado = next(
    (
        item
        for item in itens
        if item.get("lote")
        == "3007863574 - 30"
    ),
    None
)

if not item_resolvido:
    raise SystemExit(
        "[FALHOU] Item resolvido não encontrado."
    )

if not item_confirmado:
    raise SystemExit(
        "[FALHOU] Item divergente não encontrado."
    )

if item_resolvido.get("status") != "OK":
    raise SystemExit(
        "[FALHOU] Item A deveria ficar OK."
    )

if item_confirmado.get("status") == "OK":
    raise SystemExit(
        "[FALHOU] Item B deveria continuar divergente."
    )

print(
    "\n[OK] R2 validada."
)


# ============================================================
# 7. FINALIZAR INVENTÁRIO
# ============================================================

titulo("7. FINALIZANDO INVENTÁRIO")

resposta = requests.post(
    (
        f"{BASE_URL}/inventarios/"
        f"{ID_INVENTARIO}/rodadas/proxima"
    )
)

finalizacao = validar(
    resposta,
    "Falha ao finalizar inventário."
)


# ============================================================
# 8. RESUMO FINAL
# ============================================================

titulo("8. RESULTADO FINAL")

proxima = finalizacao.get(
    "proxima_rodada",
    {}
)

resumo_r2 = proxima.get(
    "resumo_r2",
    {}
)

resultado_final = proxima.get(
    "resultado_final",
    {}
)

fechamento = resultado_final.get(
    "fechamento_recontagens",
    {}
)

print(
    "Resolvidos R2:",
    resumo_r2.get("resolvidos_r2")
)

print(
    "Divergências confirmadas:",
    resumo_r2.get(
        "divergencias_confirmadas"
    )
)

print(
    "Inconsistências R1/R2:",
    resumo_r2.get(
        "inconsistencias_r1_r2"
    )
)

print(
    "Ocorrências resolvidas:",
    fechamento.get(
        "ocorrencias_resolvidas"
    )
)

print(
    "Divergências confirmadas fechamento:",
    fechamento.get(
        "divergencias_confirmadas"
    )
)

print(
    "Decisões concluídas:",
    fechamento.get(
        "decisoes_concluidas"
    )
)

print(
    "\n[APROVADO] TESTE-CICLO-011 concluído."
)