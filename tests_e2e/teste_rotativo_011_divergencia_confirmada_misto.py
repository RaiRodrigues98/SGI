import requests
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from database import get_connection


# ============================================================
# CONFIGURAÇÕES
# ============================================================

BASE_URL = "http://127.0.0.1:8000"

ID_INVENTARIO = 21
ID_RODADA_R1 = 41

LOCALIZACAO = "01PLAQUETA"

USUARIO = "teste_e2e"


# ============================================================
# FUNÇÕES
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
        raise SystemExit(
            f"\n[FALHOU] {etapa}"
        )

    return dados


# ============================================================
# 0. PREPARANDO ESCOPO E SNAPSHOT
# ============================================================

titulo("0. PREPARANDO ESCOPO E SNAPSHOT")

conn = get_connection()
cursor = conn.cursor()

# ============================================================
# 0.1 VALIDAR / INSERIR LOCALIZAÇÃO NO ESCOPO
# ============================================================

cursor.execute(
    """
    SELECT COUNT(*)
    FROM dbo.InventarioEscopoLocalizacoes
    WHERE
        ID_Inventario = ?
        AND UPPER(
            LTRIM(
                RTRIM(
                    Localizacao
                )
            )
        ) = ?
    """,
    (
        ID_INVENTARIO,
        LOCALIZACAO.upper()
    )
)

total_escopo = int(
    cursor.fetchone()[0]
)

if total_escopo == 0:

    cursor.execute(
        """
        INSERT INTO dbo.InventarioEscopoLocalizacoes
        (
            ID_Inventario,
            Localizacao,
            Selecionado
        )
        VALUES
        (
            ?,
            ?,
            1
        )
        """,
        (
            ID_INVENTARIO,
            LOCALIZACAO
        )
    )

    conn.commit()

    print(
        "[OK] Localização adicionada ao escopo."
    )

else:

    # Garante que permaneça selecionada
    cursor.execute(
        """
        UPDATE dbo.InventarioEscopoLocalizacoes

        SET
            Selecionado = 1

        WHERE
            ID_Inventario = ?
            AND UPPER(
                LTRIM(
                    RTRIM(
                        Localizacao
                    )
                )
            ) = ?
        """,
        (
            ID_INVENTARIO,
            LOCALIZACAO.upper()
        )
    )

    conn.commit()

    print(
        "[OK] Localização já existe no escopo."
    )


# ============================================================
# 0.2 VALIDAR SNAPSHOT
# ============================================================

cursor.execute(
    """
    SELECT COUNT(*)
    FROM dbo.InventarioEstoqueSnapshot
    WHERE ID_Inventario = ?
    """,
    (
        ID_INVENTARIO,
    )
)

total_snapshot = int(
    cursor.fetchone()[0]
)


# ============================================================
# 0.3 GERAR SNAPSHOT SE NECESSÁRIO
# ============================================================

if total_snapshot == 0:

    print(
        "Snapshot ainda não existe. Gerando..."
    )

    resposta = requests.post(
        (
            f"{BASE_URL}/inventarios/"
            f"{ID_INVENTARIO}/snapshot"
        ),
        json={}
    )

    validar(
        resposta,
        "Falha ao gerar snapshot."
    )

    print(
        "[OK] Snapshot criado."
    )

else:

    print(
        f"[OK] Snapshot já existe com "
        f"{total_snapshot} registro(s)."
    )


# ============================================================
# 0.4 VALIDAR SNAPSHOT DA LOCALIZAÇÃO
# ============================================================

cursor.execute(
    """
    SELECT
        Codigo,
        Lote,
        SaldoInventario

    FROM dbo.InventarioEstoqueSnapshot

    WHERE
        ID_Inventario = ?
        AND UPPER(
            LTRIM(
                RTRIM(
                    Localizacao
                )
            )
        ) = ?

    ORDER BY
        Codigo,
        Lote
    """,
    (
        ID_INVENTARIO,
        LOCALIZACAO.upper()
    )
)

snapshot_itens = cursor.fetchall()

if not snapshot_itens:

    conn.close()

    raise SystemExit(
        "\n[FALHOU] Nenhum item encontrado "
        "no snapshot da localização."
    )


print(
    "\nItens no snapshot:"
)

for item in snapshot_itens:

    print(
        item.Codigo,
        "|",
        item.Lote,
        "| estoque =",
        float(
            item.SaldoInventario
        )
    )


# ============================================================
# 0.5 VALIDAR ITENS NECESSÁRIOS PARA O TESTE
# ============================================================

mapa_snapshot = {
    (
        str(item.Codigo).strip(),
        str(item.Lote or "").strip()
    ):
    float(
        item.SaldoInventario
    )

    for item in snapshot_itens
}


itens_esperados = {
    (
        "71256360",
        "3007849339 - 220"
    ): 1.0,

    (
        "71554091",
        "3007863031 - 40"
    ): 2.0,

    (
        "71554091",
        "3007863574 - 30"
    ): 1.0,
}


for chave, quantidade_esperada in itens_esperados.items():

    if chave not in mapa_snapshot:

        conn.close()

        raise SystemExit(
            (
                "\n[FALHOU] Item necessário ao teste "
                f"não existe no snapshot: {chave}"
            )
        )

    quantidade_encontrada = (
        mapa_snapshot[chave]
    )

    if (
        quantidade_encontrada
        !=
        quantidade_esperada
    ):

        conn.close()

        raise SystemExit(
            (
                "\n[FALHOU] Saldo inesperado no snapshot. "
                f"Item={chave} "
                f"Esperado={quantidade_esperada} "
                f"Encontrado={quantidade_encontrada}"
            )
        )


print(
    "\n[OK] Escopo e snapshot preparados."
)

conn.close()

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
# 1. ABRIR R1
# ============================================================

titulo("1. ABRINDO R1")

resposta = requests.post(
    f"{BASE_URL}/localizacoes/iniciar",
    json={
        "id_inventario": ID_INVENTARIO,
        "id_rodada": ID_RODADA_R1,
        "localizacao": LOCALIZACAO
    }
)

dados = validar(
    resposta,
    "Falha ao abrir R1."
)

ID_SESSAO_R1 = dados["id_sessao"]


# ============================================================
# 2. ITEM A - R1 DIVERGENTE
#
# WMS = 2
# R1 = 0
# R2 depois será 2
# => RESOLVIDO_R2
# ============================================================

titulo("2. R1 - ITEM QUE DEVE RESOLVER")

resposta = requests.post(
    f"{BASE_URL}/contagens",
    json={
        "id_sessao": ID_SESSAO_R1,
        "codigo": "71554091",
        "lote": "3007863031 - 40",
        "quantidade": 1,
        "usuario": USUARIO
    }
)

validar(
    resposta,
    "Falha ao contar item A na R1."
)


# ============================================================
# 3. ITEM B - R1 DIVERGENTE
#
# WMS = 1
# R1 = 2
# R2 depois será 2
# => DIVERGENCIA_CONFIRMADA
# ============================================================

titulo("3. R1 - ITEM QUE DEVE CONFIRMAR DIVERGÊNCIA")

resposta = requests.post(
    f"{BASE_URL}/contagens",
    json={
        "id_sessao": ID_SESSAO_R1,
        "codigo": "71554091",
        "lote": "3007863574 - 30",
        "quantidade": 2,
        "usuario": USUARIO
    }
)

validar(
    resposta,
    "Falha ao contar item B na R1."
)


# ============================================================
# 4. TERCEIRO ITEM CORRETO
#
# WMS = 1
# R1 = 1
# ============================================================

titulo("4. R1 - ITEM CORRETO")

resposta = requests.post(
    f"{BASE_URL}/contagens",
    json={
        "id_sessao": ID_SESSAO_R1,
        "codigo": "71256360",
        "lote": "3007849339 - 220",
        "quantidade": 1,
        "usuario": USUARIO
    }
)

validar(
    resposta,
    "Falha ao contar item correto."
)


# ============================================================
# 5. ENCERRAR R1
# ============================================================

titulo("5. ENCERRANDO R1")

resposta = requests.post(
    f"{BASE_URL}/localizacoes/encerrar",
    json={
        "id_sessao": ID_SESSAO_R1,
        "usuario": USUARIO
    }
)

validar(
    resposta,
    "Falha ao encerrar R1."
)


# ============================================================
# 6. ANALISAR R1
# ============================================================

titulo("6. ANALISANDO R1")

resposta = requests.get(
    f"{BASE_URL}/sessoes/{ID_SESSAO_R1}/analise"
)

analise_r1 = validar(
    resposta,
    "Falha ao analisar R1."
)

itens_r1 = analise_r1.get("itens", [])

for item in itens_r1:
    print(
        item.get("codigo"),
        item.get("lote"),
        "Estoque:",
        item.get("qtd_estoque"),
        "R1:",
        item.get("qtd_contada"),
        "Status:",
        item.get("status")
    )


# ============================================================
# 7. REGISTRAR RECONTAR NOS DIVERGENTES
# ============================================================

titulo("7. REGISTRANDO DECISÕES RECONTAR")

divergentes = [
    item
    for item in itens_r1
    if item.get("requer_decisao")
]

for item in divergentes:

    resposta = requests.post(
        (
            f"{BASE_URL}/inventarios/"
            f"{ID_INVENTARIO}/decisoes-rotativo"
        ),
        json={
            "id_rodada": ID_RODADA_R1,
            "localizacao": item["localizacao"],
            "codigo": item["codigo"],
            "lote": item["lote"],
            "decisao": "RECONTAR",
            "justificativa": (
                "Teste E2E para validar resolução "
                "e divergência confirmada na R2."
            )
        }
    )

    validar(
        resposta,
        "Falha ao registrar RECONTAR."
    )


# ============================================================
# 8. GERAR R2
# ============================================================

titulo("8. GERANDO R2")

resposta = requests.post(
    (
        f"{BASE_URL}/inventarios/"
        f"{ID_INVENTARIO}/rodadas/proxima"
    )
)

dados_r2 = validar(
    resposta,
    "Falha ao gerar R2."
)

ID_RODADA_R2 = (
    dados_r2["proxima_rodada"]["id_rodada"]
)

print(
    "ID R2:",
    ID_RODADA_R2
)


# ============================================================
# 9. ABRIR R2
# ============================================================

titulo("9. ABRINDO R2")

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


# ============================================================
# 10. R2 - ITEM A CORRIGE
#
# WMS = 2
# R1 = 0
# R2 = 2
# ============================================================

titulo("10. R2 - ITEM A CORRIGE")

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
    "Falha na contagem R2 item A."
)


# ============================================================
# 11. R2 - ITEM B REPETE DIVERGÊNCIA
#
# WMS = 1
# R1 = 2
# R2 = 2
# ============================================================

titulo("11. R2 - ITEM B REPETE DIVERGÊNCIA")

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
    "Falha na contagem R2 item B."
)


# ============================================================
# 12. ENCERRAR R2
# ============================================================

titulo("12. ENCERRANDO R2")

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
# 13. ANALISAR R2
# ============================================================

titulo("13. ANALISANDO R2")

resposta = requests.get(
    f"{BASE_URL}/sessoes/{ID_SESSAO_R2}/analise"
)

analise_r2 = validar(
    resposta,
    "Falha ao analisar R2."
)

itens_r2 = analise_r2.get("itens", [])

for item in itens_r2:

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
# 14. VALIDAR R2
# ============================================================

titulo("14. VALIDANDO CENÁRIO")

item_resolvido = next(
    (
        item
        for item in itens_r2
        if (
            item.get("lote")
            ==
            "3007863031 - 40"
        )
    ),
    None
)

item_confirmado = next(
    (
        item
        for item in itens_r2
        if (
            item.get("lote")
            ==
            "3007863574 - 30"
        )
    ),
    None
)

if not item_resolvido:
    raise SystemExit(
        "[FALHOU] Item resolvido não encontrado."
    )

if not item_confirmado:
    raise SystemExit(
        "[FALHOU] Item confirmado não encontrado."
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
# 15. FINALIZAR INVENTÁRIO
# ============================================================

titulo("15. FINALIZANDO INVENTÁRIO")

resposta = requests.post(
    (
        f"{BASE_URL}/inventarios/"
        f"{ID_INVENTARIO}/proxima-rodada"
    )
)

finalizacao = validar(
    resposta,
    "Falha ao finalizar inventário."
)

print(
    "\nFinalização:",
    finalizacao
)


# ============================================================
# 16. RESULTADO
# ============================================================

titulo("16. RESULTADO FINAL")

proxima = finalizacao.get(
    "proxima_rodada",
    {}
)

resumo_r2 = proxima.get(
    "resumo_r2",
    {}
)

fechamento = (
    proxima
    .get("resultado_final", {})
    .get("fechamento_recontagens", {})
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
    "\n[APROVADO] Cenário executado."
)