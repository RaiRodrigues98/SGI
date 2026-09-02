import os
import sys
import requests

BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from database import get_connection


BASE_URL = "http://127.0.0.1:8000"

# Ajuste estes IDs se o TESTE-CICLO-012 receber outros valores.
ID_INVENTARIO = 22
ID_RODADA_R1 = 43

LOCALIZACAO = "01PLAQUETA"
ARMAZEM = "ML007"
USUARIO = "dev"


ITEM_OK_1 = {
    "codigo": "71256360",
    "lote": "3007849339 - 220",
    "estoque": 1,
    "r1": 1,
}

ITEM_OK_2 = {
    "codigo": "71554091",
    "lote": "3007863031 - 40",
    "estoque": 2,
    "r1": 2,
}

ITEM_DIVERGENTE = {
    "codigo": "71554091",
    "lote": "3007863574 - 30",
    "estoque": 1,
    "r1": 2,
    "r2": 3,
}


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
# 0. PREPARAR / VALIDAR INVENTÁRIO, ESCOPO E SNAPSHOT
# ============================================================

titulo("0. PREPARANDO ESCOPO E SNAPSHOT")

conn = get_connection()
cursor = conn.cursor()

try:
    cursor.execute(
        """
        SELECT
            ID_Inventario,
            CodigoInventario,
            Tipo,
            Status,
            RodadaAtual
        FROM dbo.Inventarios
        WHERE ID_Inventario = ?
        """,
        ID_INVENTARIO,
    )

    inventario = cursor.fetchone()

    if not inventario:
        raise SystemExit(
            (
                f"\n[FALHOU] Inventário {ID_INVENTARIO} não existe.\n"
                "Crie primeiro o TESTE-CICLO-012 e ajuste "
                "ID_INVENTARIO e ID_RODADA_R1 no início do arquivo."
            )
        )

    print(
        f"[OK] Inventário encontrado: "
        f"{inventario.CodigoInventario}"
    )

    if str(inventario.Tipo).strip().upper() != "ROTATIVO":
        raise SystemExit(
            "\n[FALHOU] O inventário informado não é ROTATIVO."
        )

    if str(inventario.Status).strip().upper() != "ABERTO":
        raise SystemExit(
            (
                "\n[FALHOU] O inventário precisa estar ABERTO. "
                f"Status atual: {inventario.Status}"
            )
        )

    cursor.execute(
        """
        SELECT
            ID_Rodada,
            ID_Inventario,
            NumeroRodada,
            Status
        FROM dbo.RodadasInventario
        WHERE
            ID_Rodada = ?
            AND ID_Inventario = ?
        """,
        (
            ID_RODADA_R1,
            ID_INVENTARIO,
        )
    )

    rodada = cursor.fetchone()

    if not rodada:
        raise SystemExit(
            (
                f"\n[FALHOU] A rodada {ID_RODADA_R1} "
                f"não pertence ao inventário {ID_INVENTARIO}."
            )
        )

    if int(rodada.NumeroRodada) != 1:
        raise SystemExit(
            (
                "\n[FALHOU] A rodada informada não é R1. "
                f"NumeroRodada={rodada.NumeroRodada}"
            )
        )

    print(
        f"[OK] R1 encontrada: "
        f"{rodada.ID_Rodada}"
    )

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM dbo.InventarioEscopoLocalizacoes
        WHERE
            ID_Inventario = ?
            AND UPPER(LTRIM(RTRIM(Localizacao))) =
                UPPER(LTRIM(RTRIM(?)))
        """,
        (
            ID_INVENTARIO,
            LOCALIZACAO,
        )
    )

    existe_escopo = int(cursor.fetchone()[0])

    if existe_escopo == 0:
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
                LOCALIZACAO,
            )
        )

        print("[OK] Localização inserida no escopo.")

    else:
        cursor.execute(
            """
            UPDATE dbo.InventarioEscopoLocalizacoes
            SET Selecionado = 1
            WHERE
                ID_Inventario = ?
                AND UPPER(LTRIM(RTRIM(Localizacao))) =
                    UPPER(LTRIM(RTRIM(?)))
            """,
            (
                ID_INVENTARIO,
                LOCALIZACAO,
            )
        )

        print("[OK] Localização já existe no escopo.")

    conn.commit()

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM dbo.InventarioEstoqueSnapshot
        WHERE ID_Inventario = ?
        """,
        ID_INVENTARIO,
    )

    total_snapshot = int(cursor.fetchone()[0])

    if total_snapshot == 0:
        cursor.execute(
            """
            INSERT INTO dbo.InventarioEstoqueSnapshot
            (
                ID_Inventario,
                ID_Origem,
                cArmazem,
                Localizacao,
                Codigo,
                Lote,
                Descricao,
                Unidade,
                Categoria,
                Validade,
                qArmazenado,
                qReservado,
                SaldoInventario,
                DataHoraSnapshot
            )
            SELECT
                ?,
                ID_Origem,
                cArmazem,
                Localizacao,
                Codigo,
                Lote,
                Descricao,
                Unidade,
                Categoria,
                Validade,
                qArmazenado,
                qReservado,
                SaldoInventario,
                SYSDATETIME()
            FROM dbo.InventarioEstoqueSnapshot
            WHERE
                ID_Inventario = 21
                AND UPPER(LTRIM(RTRIM(Localizacao))) =
                    UPPER(LTRIM(RTRIM(?)))
            """,
            (
                ID_INVENTARIO,
                LOCALIZACAO,
            )
        )

        registros_copiados = int(cursor.rowcount or 0)

        if registros_copiados <= 0:
            conn.rollback()
            raise SystemExit(
                "\n[FALHOU] Não foi possível copiar o snapshot do inventário 21."
            )

        conn.commit()

        print(
            f"[OK] Snapshot copiado: "
            f"{registros_copiados} registro(s)."
        )

    else:
        print(
            f"[OK] Snapshot já possui "
            f"{total_snapshot} registro(s)."
        )

    cursor.execute(
        """
        SELECT
            Codigo,
            Lote,
            SaldoInventario
        FROM dbo.InventarioEstoqueSnapshot
        WHERE
            ID_Inventario = ?
            AND UPPER(LTRIM(RTRIM(Localizacao))) =
                UPPER(LTRIM(RTRIM(?)))
        ORDER BY
            Codigo,
            Lote
        """,
        (
            ID_INVENTARIO,
            LOCALIZACAO,
        )
    )

    snapshot_itens = cursor.fetchall()

    if not snapshot_itens:
        raise SystemExit(
            "\n[FALHOU] Nenhum item encontrado no snapshot."
        )

    print("\nItens no snapshot:")

    mapa_snapshot = {}

    for item in snapshot_itens:
        chave = (
            str(item.Codigo).strip(),
            str(item.Lote or "").strip(),
        )

        saldo = float(item.SaldoInventario or 0)
        mapa_snapshot[chave] = saldo

        print(
            f"{chave[0]} | "
            f"{chave[1]} | "
            f"estoque = {saldo}"
        )

    itens_esperados = {
        (ITEM_OK_1["codigo"], ITEM_OK_1["lote"]): float(ITEM_OK_1["estoque"]),
        (ITEM_OK_2["codigo"], ITEM_OK_2["lote"]): float(ITEM_OK_2["estoque"]),
        (
            ITEM_DIVERGENTE["codigo"],
            ITEM_DIVERGENTE["lote"],
        ): float(ITEM_DIVERGENTE["estoque"]),
    }

    for chave, saldo_esperado in itens_esperados.items():
        if chave not in mapa_snapshot:
            raise SystemExit(
                (
                    "\n[FALHOU] Item necessário ao teste "
                    f"não encontrado no snapshot: {chave}"
                )
            )

        saldo_encontrado = mapa_snapshot[chave]

        if saldo_encontrado != saldo_esperado:
            raise SystemExit(
                (
                    "\n[FALHOU] Saldo inesperado no snapshot. "
                    f"Item={chave} "
                    f"Esperado={saldo_esperado} "
                    f"Encontrado={saldo_encontrado}"
                )
            )

    print("\n[OK] Escopo e snapshot preparados.")

finally:
    cursor.close()
    conn.close()


# ============================================================
# 1. ABRIR R1
# ============================================================

titulo("1. ABRINDO R1")

resposta = requests.post(
    f"{BASE_URL}/localizacoes/iniciar",
    json={
        "id_inventario": ID_INVENTARIO,
        "id_rodada": ID_RODADA_R1,
        "localizacao": LOCALIZACAO,
    },
)

dados = validar(
    resposta,
    "Falha ao abrir R1.",
)

ID_SESSAO_R1 = dados["id_sessao"]

print("\nID Sessão R1:", ID_SESSAO_R1)


# ============================================================
# 2. R1 - ITEM CORRETO 1
# ============================================================

titulo("2. R1 - ITEM CORRETO 1")

resposta = requests.post(
    f"{BASE_URL}/contagens",
    json={
        "id_sessao": ID_SESSAO_R1,
        "codigo": ITEM_OK_1["codigo"],
        "lote": ITEM_OK_1["lote"],
        "quantidade": ITEM_OK_1["r1"],
        "usuario": USUARIO,
    },
)

validar(
    resposta,
    "Falha ao contar item correto 1.",
)


# ============================================================
# 3. R1 - ITEM CORRETO 2
# ============================================================

titulo("3. R1 - ITEM CORRETO 2")

resposta = requests.post(
    f"{BASE_URL}/contagens",
    json={
        "id_sessao": ID_SESSAO_R1,
        "codigo": ITEM_OK_2["codigo"],
        "lote": ITEM_OK_2["lote"],
        "quantidade": ITEM_OK_2["r1"],
        "usuario": USUARIO,
    },
)

validar(
    resposta,
    "Falha ao contar item correto 2.",
)


# ============================================================
# 4. R1 - ITEM DIVERGENTE
# ============================================================

titulo("4. R1 - ITEM DIVERGENTE")

resposta = requests.post(
    f"{BASE_URL}/contagens",
    json={
        "id_sessao": ID_SESSAO_R1,
        "codigo": ITEM_DIVERGENTE["codigo"],
        "lote": ITEM_DIVERGENTE["lote"],
        "quantidade": ITEM_DIVERGENTE["r1"],
        "usuario": USUARIO,
    },
)

validar(
    resposta,
    "Falha ao contar item divergente.",
)


# ============================================================
# 5. ENCERRAR R1
# ============================================================

titulo("5. ENCERRANDO R1")

resposta = requests.post(
    f"{BASE_URL}/localizacoes/encerrar",
    json={
        "id_sessao": ID_SESSAO_R1,
        "usuario": USUARIO,
    },
)

validar(
    resposta,
    "Falha ao encerrar R1.",
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
    "Falha ao analisar R1.",
)

itens_r1 = analise_r1.get("itens", [])

for item in itens_r1:
    print(
        item.get("codigo"),
        "|",
        item.get("lote"),
        "| Estoque:",
        item.get("qtd_estoque"),
        "| R1:",
        item.get("qtd_contada"),
        "| Diferença:",
        item.get("diferenca"),
        "| Status:",
        item.get("status"),
    )


# ============================================================
# 7. VALIDAR DIVERGÊNCIA DA R1
# ============================================================

titulo("7. VALIDANDO DIVERGÊNCIA R1")

item_div_r1 = next(
    (
        item
        for item in itens_r1
        if (
            item.get("codigo") == ITEM_DIVERGENTE["codigo"]
            and item.get("lote") == ITEM_DIVERGENTE["lote"]
        )
    ),
    None,
)

if not item_div_r1:
    raise SystemExit(
        "[FALHOU] Item divergente não encontrado na R1."
    )

if float(item_div_r1.get("diferenca", 0)) == 0:
    raise SystemExit(
        "[FALHOU] Item deveria estar divergente na R1."
    )

print(
    "[OK] Divergência R1 identificada:",
    item_div_r1.get("diferenca"),
)


# ============================================================
# 8. DECISÃO = RECONTAR
# ============================================================

titulo("8. REGISTRANDO DECISÃO RECONTAR")

resposta = requests.post(
    (
        f"{BASE_URL}/inventarios/"
        f"{ID_INVENTARIO}/decisoes-rotativo"
    ),
    json={
        "id_rodada": ID_RODADA_R1,
        "localizacao": LOCALIZACAO,
        "codigo": ITEM_DIVERGENTE["codigo"],
        "lote": ITEM_DIVERGENTE["lote"],
        "decisao": "RECONTAR",
        "justificativa": (
            "Teste E2E 012 - validar "
            "INCONSISTENCIA_R1_R2."
        ),
    },
)

validar(
    resposta,
    "Falha ao registrar decisão RECONTAR.",
)


# ============================================================
# 9. GERAR R2
# ============================================================

titulo("9. GERANDO R2")

resposta = requests.post(
    (
        f"{BASE_URL}/inventarios/"
        f"{ID_INVENTARIO}/rodadas/proxima"
    )
)

dados_r2 = validar(
    resposta,
    "Falha ao gerar R2.",
)

proxima = dados_r2.get("proxima_rodada", {})
ID_RODADA_R2 = proxima.get("id_rodada")

if not ID_RODADA_R2:
    raise SystemExit(
        "[FALHOU] ID da R2 não retornado."
    )

print("\nID Rodada R2:", ID_RODADA_R2)


# ============================================================
# 10. ABRIR R2
# ============================================================

titulo("10. ABRINDO R2")

resposta = requests.post(
    f"{BASE_URL}/localizacoes/iniciar",
    json={
        "id_inventario": ID_INVENTARIO,
        "id_rodada": ID_RODADA_R2,
        "localizacao": LOCALIZACAO,
    },
)

dados = validar(
    resposta,
    "Falha ao abrir R2.",
)

ID_SESSAO_R2 = dados["id_sessao"]

print("\nID Sessão R2:", ID_SESSAO_R2)


# ============================================================
# 11. R2 - CONTAGEM DIFERENTE DA R1
# ============================================================

titulo("11. R2 - CONTAGEM DIFERENTE DA R1")

resposta = requests.post(
    f"{BASE_URL}/contagens",
    json={
        "id_sessao": ID_SESSAO_R2,
        "codigo": ITEM_DIVERGENTE["codigo"],
        "lote": ITEM_DIVERGENTE["lote"],
        "quantidade": ITEM_DIVERGENTE["r2"],
        "usuario": USUARIO,
    },
)

validar(
    resposta,
    "Falha ao contar item na R2.",
)


# ============================================================
# 12. ENCERRAR R2
# ============================================================

titulo("12. ENCERRANDO R2")

resposta = requests.post(
    f"{BASE_URL}/localizacoes/encerrar",
    json={
        "id_sessao": ID_SESSAO_R2,
        "usuario": USUARIO,
    },
)

validar(
    resposta,
    "Falha ao encerrar R2.",
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
    "Falha ao analisar R2.",
)

for item in analise_r2.get("itens", []):
    print("\nCódigo:", item.get("codigo"))
    print("Lote:", item.get("lote"))
    print("Estoque:", item.get("qtd_estoque"))
    print("R2:", item.get("qtd_contada"))
    print("Diferença:", item.get("diferenca"))
    print("Status:", item.get("status"))


# ============================================================
# 14. FINALIZAR R2
# ============================================================

titulo("14. FINALIZANDO R2")

resposta = requests.post(
    (
        f"{BASE_URL}/inventarios/"
        f"{ID_INVENTARIO}/rodadas/proxima"
    )
)

finalizacao = validar(
    resposta,
    "Falha ao finalizar R2.",
)

proxima = finalizacao.get("proxima_rodada", {})
resumo_r2 = proxima.get("resumo_r2", {})
itens_fechamento = proxima.get("itens", [])


# ============================================================
# 15. LOCALIZAR ITEM NO FECHAMENTO
# ============================================================

titulo("15. VALIDANDO CLASSIFICAÇÃO")

item_final = next(
    (
        item
        for item in itens_fechamento
        if (
            item.get("codigo") == ITEM_DIVERGENTE["codigo"]
            and item.get("lote") == ITEM_DIVERGENTE["lote"]
        )
    ),
    None,
)

if not item_final:
    raise SystemExit(
        "[FALHOU] Item não encontrado no fechamento."
    )

print("Código:", item_final.get("codigo"))
print("Lote:", item_final.get("lote"))
print("WMS:", item_final.get("qtd_wms_total"))
print("R1:", item_final.get("qtd_r1_total"))
print("R2:", item_final.get("qtd_r2_total"))
print("Classificação:", item_final.get("classificacao"))
print("Requer gestor:", item_final.get("requer_gestor"))
print(
    "Pendente próxima rodada:",
    item_final.get("pendente_proxima_rodada")
)


# ============================================================
# 16. ASSERTS DO TESTE
# ============================================================

titulo("16. RESULTADO DO TESTE")

erros = []

if item_final.get("classificacao") != "INCONSISTENCIA_R1_R2":
    erros.append(
        "classificacao deveria ser INCONSISTENCIA_R1_R2"
    )

if int(resumo_r2.get("inconsistencias_r1_r2", 0)) != 1:
    erros.append(
        "inconsistencias_r1_r2 deveria ser 1"
    )

if int(resumo_r2.get("divergencias_confirmadas", 0)) != 0:
    erros.append(
        "divergencias_confirmadas deveria ser 0"
    )

if int(resumo_r2.get("itens_para_nova_recontagem", 0)) != 1:
    erros.append(
        "itens_para_nova_recontagem deveria ser 1"
    )

if erros:
    print("\n[FALHOU] TESTE-CICLO-012")

    for erro in erros:
        print("-", erro)

    raise SystemExit(1)


print(
    """
[APROVADO] TESTE-CICLO-012

Cenário validado:

WMS = 1
R1  = 2
R2  = 3

R1 != R2
R2 != WMS

Resultado:
INCONSISTENCIA_R1_R2
"""
)
