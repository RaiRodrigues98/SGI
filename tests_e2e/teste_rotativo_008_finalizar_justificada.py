import sys
from pathlib import Path

import requests


ROOT_DIR = Path(__file__).resolve().parents[1]

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


from database import get_connection


BASE_URL = "http://127.0.0.1:8000"

ID_INVENTARIO = 18
ID_RODADA_R1 = 36
ID_DECISAO = 10
ID_OCORRENCIA = 10

LOCALIZACAO = "01PLAQUETA"
CODIGO = "71554091"
LOTE = "3007863574 - 30"


def titulo(texto):
    print("\n" + "=" * 70)
    print(texto)
    print("=" * 70)


# ============================================================
# 1. ESTADO ANTES DA FINALIZAÇÃO
# ============================================================

titulo("1. VALIDANDO ESTADO ATUAL")

conn = get_connection()
cursor = conn.cursor()

cursor.execute(
    """
    SELECT
        Status,
        RodadaAtual
    FROM dbo.Inventarios
    WHERE ID_Inventario = ?
    """,
    ID_INVENTARIO
)

inventario = cursor.fetchone()

print("Status inventário:", inventario.Status)
print("Rodada atual:", inventario.RodadaAtual)


cursor.execute(
    """
    SELECT
        StatusResolucao,
        Justificativa
    FROM dbo.OcorrenciasDivergencia
    WHERE ID_Ocorrencia = ?
    """,
    ID_OCORRENCIA
)

ocorrencia = cursor.fetchone()

print("Status ocorrência:", ocorrencia.StatusResolucao)
print("Justificativa:", ocorrencia.Justificativa)


cursor.execute(
    """
    SELECT
        Decisao,
        Status
    FROM dbo.DecisoesRotativo
    WHERE ID_DecisaoRotativo = ?
    """,
    ID_DECISAO
)

decisao = cursor.fetchone()

print("Decisão:", decisao.Decisao)
print("Status decisão:", decisao.Status)


cursor.close()
conn.close()


# ============================================================
# 2. TENTAR FINALIZAR INVENTÁRIO
# ============================================================

titulo("2. FINALIZANDO INVENTÁRIO")

resposta = requests.post(
    f"{BASE_URL}/inventarios/{ID_INVENTARIO}/rodadas/proxima"
)

print("HTTP:", resposta.status_code)

try:
    dados = resposta.json()
except Exception:
    dados = resposta.text

print("Resposta:", dados)


# ============================================================
# 3. ESTADO DO BANCO APÓS TENTATIVA
# ============================================================

titulo("3. VALIDANDO ESTADO FINAL NO BANCO")

conn = get_connection()
cursor = conn.cursor()


cursor.execute(
    """
    SELECT
        Status,
        RodadaAtual
    FROM dbo.Inventarios
    WHERE ID_Inventario = ?
    """,
    ID_INVENTARIO
)

inventario = cursor.fetchone()

print("\nINVENTÁRIO")
print("Status:", inventario.Status)
print("Rodada Atual:", inventario.RodadaAtual)


cursor.execute(
    """
    SELECT
        StatusResolucao,
        Justificativa,
        TipoResolucao,
        ResolvidoPor,
        DataHoraResolucao
    FROM dbo.OcorrenciasDivergencia
    WHERE ID_Ocorrencia = ?
    """,
    ID_OCORRENCIA
)

ocorrencia = cursor.fetchone()

print("\nOCORRÊNCIA")
print("Status:", ocorrencia.StatusResolucao)
print("Justificativa:", ocorrencia.Justificativa)
print("Tipo resolução:", ocorrencia.TipoResolucao)
print("Resolvido por:", ocorrencia.ResolvidoPor)
print("Data resolução:", ocorrencia.DataHoraResolucao)


cursor.execute(
    """
    SELECT
        Decisao,
        Status
    FROM dbo.DecisoesRotativo
    WHERE ID_DecisaoRotativo = ?
    """,
    ID_DECISAO
)

decisao = cursor.fetchone()

print("\nDECISÃO")
print("Decisão:", decisao.Decisao)
print("Status:", decisao.Status)


cursor.execute(
    """
    SELECT
        Localizacao,
        Codigo,
        Lote,
        QtdEstoque,
        QuantidadeFinal,
        DiferencaFinal,
        StatusFinal,
        RodadaFinal
    FROM dbo.InventarioResultadoFinal
    WHERE
        ID_Inventario = ?
        AND Codigo = ?
        AND ISNULL(Lote, '') = ?
    """,
    (
        ID_INVENTARIO,
        CODIGO,
        LOTE
    )
)

resultado = cursor.fetchone()

print("\nRESULTADO FINAL")

if resultado:

    print("Localização:", resultado.Localizacao)
    print("Código:", resultado.Codigo)
    print("Lote:", resultado.Lote)
    print("Estoque:", resultado.QtdEstoque)
    print("Quantidade Final:", resultado.QuantidadeFinal)
    print("Diferença Final:", resultado.DiferencaFinal)
    print("Status Final:", resultado.StatusFinal)
    print("Rodada Final:", resultado.RodadaFinal)

else:

    print("Nenhum resultado final encontrado.")


cursor.close()
conn.close()


# ============================================================
# RESULTADO
# ============================================================

titulo("RESULTADO")

print("HTTP finalização:", resposta.status_code)
print("Status inventário:", inventario.Status)
print("Status ocorrência:", ocorrencia.StatusResolucao)
print("Status decisão:", decisao.Status)

if resultado:
    print("Resultado final existente: SIM")
else:
    print("Resultado final existente: NÃO")