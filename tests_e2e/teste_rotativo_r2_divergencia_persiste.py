import requests
import sys
from pathlib import Path


# ============================================================
# CONFIGURA PYTHON PATH
# ============================================================

ROOT_DIR = Path(__file__).resolve().parents[1]

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(ROOT_DIR)
    )


from database import get_connection

from services.finalizacao_rotativo import (
    consolidar_resultado_final_rotativo,
    _resolver_recontagens_rotativo,
)


# ============================================================
# CONFIGURAÇÃO
#
# TROQUE PELOS IDs DO NOVO CENÁRIO
# ============================================================

BASE_URL = "http://127.0.0.1:8000"

ID_INVENTARIO = 14

ID_RODADA_R1 = 28
ID_RODADA_R2 = 29

ID_OCORRENCIA = 6
ID_DECISAO = 6

LOCALIZACAO = "01PLAQUETA"

CODIGO = "71554091"
LOTE = "3007863574 - 30"

QUANTIDADE_R2 = 2


def titulo(texto):

    print("\n" + "=" * 70)
    print(texto)
    print("=" * 70)


def validar_http(
    resposta,
    etapa
):

    print("HTTP:", resposta.status_code)

    try:
        dados = resposta.json()

    except Exception:
        dados = resposta.text

    print("Resposta:", dados)

    if resposta.status_code not in (
        200,
        201
    ):

        print(
            f"\n[FALHOU] {etapa}"
        )

        sys.exit(1)

    return dados


# ============================================================
# 1. ABRIR SESSÃO DA R2
# ============================================================

titulo(
    "1. ABRINDO SESSÃO DA R2"
)

resposta = requests.post(
    f"{BASE_URL}/localizacoes/iniciar",
    json={
        "id_inventario":
            ID_INVENTARIO,

        "id_rodada":
            ID_RODADA_R2,

        "localizacao":
            LOCALIZACAO,
    },
)

sessao = validar_http(
    resposta,
    "Não foi possível abrir a sessão da R2."
)

ID_SESSAO = sessao[
    "id_sessao"
]

print(
    "\nID Sessão:",
    ID_SESSAO
)


# ============================================================
# 2. CONTAGEM R2 AINDA DIVERGENTE
# ============================================================

titulo(
    "2. REGISTRANDO CONTAGEM DIVERGENTE NA R2"
)

resposta = requests.post(
    f"{BASE_URL}/contagens",
    json={
        "id_sessao":
            ID_SESSAO,

        "codigo":
            CODIGO,

        "lote":
            LOTE,

        "quantidade":
            QUANTIDADE_R2,

        "usuario":
            "dev",
    },
)

validar_http(
    resposta,
    "Não foi possível registrar a contagem da R2."
)


# ============================================================
# 3. ENCERRAR SESSÃO
# ============================================================

titulo(
    "3. ENCERRANDO SESSÃO DA R2"
)

resposta = requests.post(
    f"{BASE_URL}/localizacoes/encerrar",
    json={
        "id_sessao":
            ID_SESSAO,

        "usuario":
            "dev",
    },
)

validar_http(
    resposta,
    "Não foi possível encerrar a sessão da R2."
)


# ============================================================
# 4. ANALISAR R2
# ============================================================

titulo(
    "4. ANALISANDO RESULTADO DA R2"
)

resposta = requests.get(
    f"{BASE_URL}/sessoes/{ID_SESSAO}/analise"
)

analise = validar_http(
    resposta,
    "Não foi possível analisar a R2."
)


# ============================================================
# 5. LOCALIZAR ITEM
# ============================================================

item_alvo = None

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

    if (
        codigo == CODIGO
        and
        lote == LOTE
    ):

        item_alvo = item
        break


if item_alvo is None:

    titulo("RESULTADO")

    print(
        "[FALHOU] "
        "O item não apareceu na análise da R2."
    )

    sys.exit(1)


estoque = float(
    item_alvo.get(
        "qtd_estoque",
        0
    )
)

contado = float(
    item_alvo.get(
        "qtd_contada",
        0
    )
)

diferenca = float(
    item_alvo.get(
        "diferenca",
        0
    )
)

status = item_alvo.get(
    "status"
)

subtipo = item_alvo.get(
    "subtipo_divergencia"
)


print(
    "\nLocalização:",
    item_alvo.get(
        "localizacao"
    )
)

print(
    "Código:",
    item_alvo.get(
        "codigo"
    )
)

print(
    "Lote:",
    item_alvo.get(
        "lote"
    )
)

print(
    "Estoque:",
    estoque
)

print(
    "Contado R2:",
    contado
)

print(
    "Diferença:",
    diferenca
)

print(
    "Status:",
    status
)

print(
    "Subtipo:",
    subtipo
)


# ============================================================
# 6. GARANTIR QUE O CENÁRIO É DIVERGENTE
# ============================================================

titulo(
    "5. VALIDANDO QUE A DIVERGÊNCIA PERSISTE"
)

if abs(
    diferenca
) <= 0.0001:

    print(
        "[FALHOU] "
        "A R2 ficou OK. "
        "Este cenário não testa divergência persistente."
    )

    sys.exit(1)


if status == "OK":

    print(
        "[FALHOU] "
        "A análise marcou o item como OK "
        "mesmo com diferença."
    )

    sys.exit(1)


print(
    "[OK] A R2 continua divergente."
)


# ============================================================
# 7. CONSOLIDAR RESULTADO FINAL
#
# A função de resolução usa InventarioResultadoFinal.
# Portanto, primeiro precisamos consolidar.
# ============================================================

titulo(
    "6. CONSOLIDANDO RESULTADO FINAL"
)

conn = None
cursor = None


try:

    conn = get_connection()
    cursor = conn.cursor()

    # --------------------------------------------------------
    # Evita reaproveitar resultado final de teste anterior
    # --------------------------------------------------------

    cursor.execute(
        """
        SELECT COUNT(*)

        FROM dbo.InventarioResultadoFinal

        WHERE ID_Inventario = ?
        """,
        ID_INVENTARIO
    )

    resultado_existente = int(
        cursor.fetchone()[0]
    )

    if resultado_existente > 0:

        print(
            "[FALHOU] "
            "Este inventário já possui resultado final. "
            "Use um inventário de teste novo."
        )

        conn.rollback()
        sys.exit(1)


    resultado_final = (
        consolidar_resultado_final_rotativo(
            cursor=cursor,
            id_inventario=ID_INVENTARIO,
            id_rodada_r1=ID_RODADA_R1,
            id_rodada_r2=ID_RODADA_R2,
            usuario="teste_e2e",
        )
    )

    print(
        "Resultado final:",
        resultado_final
    )


    # ========================================================
    # 8. TENTAR RESOLVER RECONTAGENS
    # ========================================================

    titulo(
        "7. TENTANDO RESOLVER RECONTAGEM"
    )

    fechamento = (
        _resolver_recontagens_rotativo(
            cursor=cursor,
            id_inventario=ID_INVENTARIO,
            id_rodada_r1=ID_RODADA_R1,
            id_rodada_r2=ID_RODADA_R2,
            usuario="teste_e2e",
        )
    )

    print(
        "Fechamento:",
        fechamento
    )

    conn.commit()


    # ========================================================
    # 9. VALIDAR OCORRÊNCIA
    # ========================================================

    titulo(
        "8. VALIDANDO OCORRÊNCIA"
    )

    cursor.execute(
        """
        SELECT
            ID_Ocorrencia,
            StatusResolucao,
            ID_InventarioResolucao,
            ID_RodadaResolucao,
            TipoResolucao,
            ResolvidoPor,
            DataHoraResolucao

        FROM dbo.OcorrenciasDivergencia

        WHERE ID_Ocorrencia = ?
        """,
        ID_OCORRENCIA
    )

    ocorrencia = (
        cursor.fetchone()
    )

    if not ocorrencia:

        print(
            "[FALHOU] "
            "Ocorrência não encontrada."
        )

        sys.exit(1)


    print(
        "ID Ocorrência:",
        ocorrencia.ID_Ocorrencia
    )

    print(
        "Status:",
        ocorrencia.StatusResolucao
    )

    print(
        "ID Rodada resolução:",
        ocorrencia.ID_RodadaResolucao
    )

    print(
        "Tipo resolução:",
        ocorrencia.TipoResolucao
    )

    print(
        "Data resolução:",
        ocorrencia.DataHoraResolucao
    )


    # ========================================================
    # 10. VALIDAR DECISÃO
    # ========================================================

    titulo(
        "9. VALIDANDO DECISÃO"
    )

    cursor.execute(
        """
        SELECT
            ID_DecisaoRotativo,
            Decisao,
            Status

        FROM dbo.DecisoesRotativo

        WHERE ID_DecisaoRotativo = ?
        """,
        ID_DECISAO
    )

    decisao = (
        cursor.fetchone()
    )

    if not decisao:

        print(
            "[FALHOU] "
            "Decisão não encontrada."
        )

        sys.exit(1)


    print(
        "ID Decisão:",
        decisao.ID_DecisaoRotativo
    )

    print(
        "Decisão:",
        decisao.Decisao
    )

    print(
        "Status:",
        decisao.Status
    )


    # ========================================================
    # 11. RESULTADO
    # ========================================================

    titulo(
        "RESULTADO"
    )

    fechamento_ok = (
        fechamento.get(
            "ocorrencias_resolvidas"
        ) == 0

        and

        fechamento.get(
            "decisoes_concluidas"
        ) == 0
    )

    ocorrencia_ok = (
        ocorrencia.StatusResolucao
        ==
        "EM_RECONTAGEM"

        and

        ocorrencia.ID_RodadaResolucao
        is None

        and

        ocorrencia.DataHoraResolucao
        is None
    )

    decisao_ok = (
        decisao.Decisao
        ==
        "RECONTAR"

        and

        decisao.Status
        ==
        "ATIVA"
    )


    if (
        fechamento_ok
        and
        ocorrencia_ok
        and
        decisao_ok
    ):

        print(
            "[APROVADO] "
            "A divergência persistente da R2 "
            "não foi resolvida indevidamente."
        )

        print(
            "\nRegra validada:"
        )

        print(
            "R1 DIVERGENTE"
        )

        print("+")
        print(
            "RECONTAR"
        )

        print("+")
        print(
            "R2 AINDA DIVERGENTE"
        )

        print("=")

        print(
            "OCORRÊNCIA CONTINUA EM_RECONTAGEM"
        )

        print(
            "DECISÃO CONTINUA ATIVA"
        )

        sys.exit(0)


    print(
        "[FALHOU] "
        "O sistema encerrou indevidamente "
        "uma divergência que persiste na R2."
    )

    sys.exit(1)


except Exception as erro:

    if conn:
        conn.rollback()

    print(
        "\n[ERRO]"
    )

    print(
        type(
            erro
        ).__name__
    )

    print(
        str(
            erro
        )
    )

    sys.exit(1)


finally:

    if cursor:
        cursor.close()

    if conn:
        conn.close()