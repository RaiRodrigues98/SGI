import sys
from pathlib import Path

import requests


# ============================================================
# PYTHON PATH
# ============================================================

ROOT_DIR = Path(__file__).resolve().parents[1]

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(ROOT_DIR)
    )


from database import get_connection


# ============================================================
# CONFIGURAÇÃO
# ============================================================

BASE_URL = "http://127.0.0.1:8000"

ID_INVENTARIO = 17
ID_RODADA_R1 = 34

LOCALIZACAO = "01PLAQUETA"
CODIGO = "71554091"
LOTE = "3007863574 - 30"

QTD_ESTOQUE = 1

# R1 divergente
QTD_R1 = 2

# R2 corrige a divergência
QTD_R2 = 1

USUARIO = "teste_e2e"


# ============================================================
# UTILITÁRIOS
# ============================================================

def titulo(texto):

    print("\n" + "=" * 70)
    print(texto)
    print("=" * 70)


def validar_http(
    resposta,
    etapa,
):

    print(
        "HTTP:",
        resposta.status_code
    )

    try:
        dados = resposta.json()

    except Exception:
        dados = resposta.text

    print(
        "Resposta:",
        dados
    )

    if resposta.status_code not in (
        200,
        201,
    ):

        print(
            f"\n[FALHOU] {etapa}"
        )

        sys.exit(1)

    return dados


def localizar_item(
    analise,
):

    for item in analise.get(
        "itens",
        [],
    ):

        codigo = str(
            item.get(
                "codigo",
                "",
            )
        ).strip()

        lote = str(
            item.get(
                "lote",
                "",
            )
        ).strip()

        if (
            codigo == CODIGO
            and
            lote == LOTE
        ):
            return item

    return None


# ============================================================
# 0. LOCALIZAR ESTADO ATUAL
#
# Este teste foi preparado para continuar o inventário 17,
# que já possui:
# - R1 concluída
# - decisão RECONTAR
# - R2 criada
# - sessão R2 concluída com quantidade 1
#
# Portanto não recriamos R1/R2.
# ============================================================

titulo(
    "0. LOCALIZANDO ESTADO ATUAL"
)

conn = None
cursor = None

try:

    conn = get_connection()
    cursor = conn.cursor()

    # --------------------------------------------------------
    # LOCALIZAR R2
    # --------------------------------------------------------

    cursor.execute(
        """
        SELECT
            ID_Rodada,
            NumeroRodada,
            Status

        FROM dbo.RodadasInventario

        WHERE
            ID_Inventario = ?
            AND NumeroRodada = 2
        """,
        ID_INVENTARIO
    )

    rodada_r2 = (
        cursor.fetchone()
    )

    if not rodada_r2:

        print(
            "[FALHOU] R2 não encontrada."
        )

        sys.exit(1)

    ID_RODADA_R2 = (
        rodada_r2.ID_Rodada
    )

    print(
        "ID R2:",
        ID_RODADA_R2
    )

    print(
        "Status R2:",
        rodada_r2.Status
    )

    # --------------------------------------------------------
    # LOCALIZAR DECISÃO
    # --------------------------------------------------------

    cursor.execute(
        """
        SELECT TOP 1
            ID_DecisaoRotativo,
            Decisao,
            Status

        FROM dbo.DecisoesRotativo

        WHERE
            ID_Inventario = ?
            AND ID_Rodada = ?
            AND UPPER(
                LTRIM(
                    RTRIM(Localizacao)
                )
            ) = ?
            AND LTRIM(
                RTRIM(Codigo)
            ) = ?
            AND ISNULL(
                LTRIM(
                    RTRIM(Lote)
                ),
                ''
            ) = ?

        ORDER BY
            ID_DecisaoRotativo DESC
        """,
        (
            ID_INVENTARIO,
            ID_RODADA_R1,
            LOCALIZACAO,
            CODIGO,
            LOTE,
        )
    )

    decisao = (
        cursor.fetchone()
    )

    if not decisao:

        print(
            "[FALHOU] Decisão RECONTAR não encontrada."
        )

        sys.exit(1)

    ID_DECISAO = (
        decisao.ID_DecisaoRotativo
    )

    print(
        "ID Decisão:",
        ID_DECISAO
    )

    print(
        "Decisão:",
        decisao.Decisao
    )

    print(
        "Status decisão:",
        decisao.Status
    )

    # --------------------------------------------------------
    # LOCALIZAR OCORRÊNCIA
    # --------------------------------------------------------

    cursor.execute(
        """
        SELECT TOP 1
            ID_Ocorrencia,
            StatusResolucao

        FROM dbo.OcorrenciasDivergencia

        WHERE
            ID_Inventario = ?
            AND ID_Rodada = ?
            AND UPPER(
                LTRIM(
                    RTRIM(Localizacao)
                )
            ) = ?
            AND LTRIM(
                RTRIM(Codigo)
            ) = ?
            AND ISNULL(
                LTRIM(
                    RTRIM(Lote)
                ),
                ''
            ) = ?

        ORDER BY
            ID_Ocorrencia DESC
        """,
        (
            ID_INVENTARIO,
            ID_RODADA_R1,
            LOCALIZACAO,
            CODIGO,
            LOTE,
        )
    )

    ocorrencia = (
        cursor.fetchone()
    )

    if not ocorrencia:

        print(
            "[FALHOU] Ocorrência não encontrada."
        )

        sys.exit(1)

    ID_OCORRENCIA = (
        ocorrencia.ID_Ocorrencia
    )

    print(
        "ID Ocorrência:",
        ID_OCORRENCIA
    )

    print(
        "Status ocorrência:",
        ocorrencia.StatusResolucao
    )

finally:

    if cursor:
        cursor.close()

    if conn:
        conn.close()


# ============================================================
# 1. VALIDAR ANÁLISE DA R2
# ============================================================

titulo(
    "1. LOCALIZANDO SESSÃO ENCERRADA DA R2"
)

conn = None
cursor = None

try:

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT TOP 1
            ID_Sessao

        FROM dbo.SessoesContagem

        WHERE
            ID_Inventario = ?
            AND ID_Rodada = ?
            AND UPPER(
                LTRIM(
                    RTRIM(Localizacao)
                )
            ) = ?
            AND Status = 'ENCERRADA'

        ORDER BY
            ID_Sessao DESC
        """,
        (
            ID_INVENTARIO,
            ID_RODADA_R2,
            LOCALIZACAO,
        )
    )

    sessao = (
        cursor.fetchone()
    )

    if not sessao:

        print(
            "[FALHOU] Sessão encerrada da R2 não encontrada."
        )

        sys.exit(1)

    ID_SESSAO_R2 = (
        sessao.ID_Sessao
    )

    print(
        "ID Sessão R2:",
        ID_SESSAO_R2
    )

finally:

    if cursor:
        cursor.close()

    if conn:
        conn.close()


titulo(
    "2. ANALISANDO R2"
)

resposta = requests.get(
    (
        f"{BASE_URL}"
        f"/sessoes/{ID_SESSAO_R2}/analise"
    )
)

analise_r2 = validar_http(
    resposta,
    "Falha ao analisar R2.",
)

item_r2 = localizar_item(
    analise_r2
)

if not item_r2:

    print(
        "[FALHOU] Item não encontrado na R2."
    )

    sys.exit(1)


estoque = float(
    item_r2.get(
        "qtd_estoque",
        0,
    )
)

contado = float(
    item_r2.get(
        "qtd_contada",
        0,
    )
)

diferenca = float(
    item_r2.get(
        "diferenca",
        0,
    )
)

status = str(
    item_r2.get(
        "status",
        "",
    )
).strip().upper()


print(
    "\nEstoque:",
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


# ============================================================
# 3. VALIDAR QUE A R2 CORRIGIU
# ============================================================

titulo(
    "3. VALIDANDO CORREÇÃO DA R2"
)

if estoque != QTD_ESTOQUE:

    print(
        "[FALHOU] Estoque inesperado."
    )

    sys.exit(1)


if contado != QTD_R2:

    print(
        "[FALHOU] Quantidade R2 inesperada."
    )

    sys.exit(1)


if diferenca != 0:

    print(
        "[FALHOU] "
        "A R2 ainda possui divergência."
    )

    sys.exit(1)


if status != "OK":

    print(
        "[FALHOU] "
        "A R2 não retornou status OK."
    )

    sys.exit(1)


print(
    "[OK] A R2 corrigiu a divergência."
)


# ============================================================
# 4. FINALIZAR INVENTÁRIO
# ============================================================

titulo(
    "4. FINALIZANDO INVENTÁRIO"
)

resposta = requests.post(
    (
        f"{BASE_URL}"
        f"/inventarios/{ID_INVENTARIO}"
        f"/rodadas/proxima"
    )
)

finalizacao = validar_http(
    resposta,
    "Falha na finalização do inventário.",
)

print(
    "\nFinalização:",
    finalizacao
)


# ============================================================
# 5. VALIDAR BANCO
# ============================================================

titulo(
    "5. VALIDANDO ESTADO FINAL NO BANCO"
)

conn = None
cursor = None

try:

    conn = get_connection()
    cursor = conn.cursor()

    # --------------------------------------------------------
    # INVENTÁRIO
    # --------------------------------------------------------

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

    inventario = (
        cursor.fetchone()
    )

    # --------------------------------------------------------
    # OCORRÊNCIA
    # --------------------------------------------------------

    cursor.execute(
        """
        SELECT
            ID_Ocorrencia,
            StatusResolucao,
            ID_InventarioResolucao,
            ID_RodadaResolucao,
            TipoResolucao,
            ObservacaoResolucao,
            ResolvidoPor,
            DataHoraResolucao

        FROM dbo.OcorrenciasDivergencia

        WHERE ID_Ocorrencia = ?
        """,
        ID_OCORRENCIA
    )

    ocorrencia_final = (
        cursor.fetchone()
    )

    # --------------------------------------------------------
    # DECISÃO
    # --------------------------------------------------------

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

    decisao_final = (
        cursor.fetchone()
    )

    # --------------------------------------------------------
    # RESULTADO FINAL
    # --------------------------------------------------------

    cursor.execute(
        """
        SELECT
            Localizacao,
            Codigo,
            Lote,
            QtdEstoque,
            QuantidadeFinal,
            StatusFinal,
            OrigemQuantidade,
            RodadaFinal

        FROM dbo.InventarioResultadoFinal

        WHERE
            ID_Inventario = ?

            AND UPPER(
                LTRIM(
                    RTRIM(Localizacao)
                )
            ) = ?

            AND LTRIM(
                RTRIM(Codigo)
            ) = ?

            AND ISNULL(
                LTRIM(
                    RTRIM(Lote)
                ),
                ''
            ) = ?
        """,
        (
            ID_INVENTARIO,
            LOCALIZACAO,
            CODIGO,
            LOTE,
        )
    )

    resultado_final = (
        cursor.fetchone()
    )


    # ========================================================
    # EXIBIÇÃO
    # ========================================================

    print(
        "\nINVENTÁRIO"
    )

    print(
        "Status:",
        inventario.Status
    )

    print(
        "Rodada Atual:",
        inventario.RodadaAtual
    )


    print(
        "\nOCORRÊNCIA"
    )

    print(
        "ID:",
        ocorrencia_final.ID_Ocorrencia
    )

    print(
        "Status:",
        ocorrencia_final.StatusResolucao
    )

    print(
        "ID Inventário resolução:",
        ocorrencia_final.ID_InventarioResolucao
    )

    print(
        "ID Rodada resolução:",
        ocorrencia_final.ID_RodadaResolucao
    )

    print(
        "Tipo resolução:",
        ocorrencia_final.TipoResolucao
    )

    print(
        "Observação:",
        ocorrencia_final.ObservacaoResolucao
    )

    print(
        "Resolvido por:",
        ocorrencia_final.ResolvidoPor
    )

    print(
        "Data resolução:",
        ocorrencia_final.DataHoraResolucao
    )


    print(
        "\nDECISÃO"
    )

    print(
        "ID:",
        decisao_final.ID_DecisaoRotativo
    )

    print(
        "Decisão:",
        decisao_final.Decisao
    )

    print(
        "Status:",
        decisao_final.Status
    )


    print(
        "\nRESULTADO FINAL"
    )

    print(
        "Estoque:",
        resultado_final.QtdEstoque
    )

    print(
        "Quantidade Final:",
        resultado_final.QuantidadeFinal
    )

    print(
        "Status Final:",
        resultado_final.StatusFinal
    )

    print(
        "Rodada Final:",
        resultado_final.RodadaFinal
    )


    # ========================================================
    # VALIDAR JSON
    # ========================================================

    status_json = (
        finalizacao
        ["proxima_rodada"]
        ["resultado_final"]
        ["itens"][0]
        ["decisao_rotativa"]
        ["status"]
    )

    print(
        "\nStatus decisão no JSON:",
        status_json
    )


    # ========================================================
    # VALIDAÇÕES
    # ========================================================

    inventario_ok = (
        str(
            inventario.Status
        ).strip().upper()
        ==
        "FINALIZADO"

        and

        int(
            inventario.RodadaAtual
        )
        ==
        2
    )


    ocorrencia_ok = (
        str(
            ocorrencia_final.StatusResolucao
        ).strip().upper()
        ==
        "RESOLVIDA_RECONTAGEM"

        and

        ocorrencia_final.ID_InventarioResolucao
        ==
        ID_INVENTARIO

        and

        ocorrencia_final.ID_RodadaResolucao
        ==
        ID_RODADA_R2

        and

        str(
            ocorrencia_final.TipoResolucao
        ).strip().upper()
        ==
        "RECONTAGEM"

        and

        ocorrencia_final.ResolvidoPor
        is not None

        and

        ocorrencia_final.DataHoraResolucao
        is not None
    )


    decisao_ok = (
        str(
            decisao_final.Decisao
        ).strip().upper()
        ==
        "RECONTAR"

        and

        str(
            decisao_final.Status
        ).strip().upper()
        ==
        "CONCLUIDA"
    )


    resultado_ok = (
        float(
            resultado_final.QtdEstoque
        )
        ==
        1

        and

        float(
            resultado_final.QuantidadeFinal
        )
        ==
        1

        and

        str(
            resultado_final.StatusFinal
        ).strip().upper()
        ==
        "OK"

        and

        int(
            resultado_final.RodadaFinal
        )
        ==
        2
    )


    json_ok = (
        str(
            status_json
        ).strip().upper()
        ==
        "CONCLUIDA"
    )


    # ========================================================
    # RESULTADO FINAL
    # ========================================================

    titulo(
        "RESULTADO"
    )

    if (
        inventario_ok
        and
        ocorrencia_ok
        and
        decisao_ok
        and
        resultado_ok
        and
        json_ok
    ):

        print(
            "[APROVADO] "
            "A R2 resolveu corretamente a divergência."
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
            "R2 CORRIGE"
        )

        print("=")

        print(
            "RESOLVIDA_RECONTAGEM"
        )

        print(
            "DECISÃO CONCLUIDA"
        )

        print(
            "RESULTADO FINAL = OK"
        )

        print(
            "JSON = CONCLUIDA"
        )

        sys.exit(0)


    print(
        "[FALHOU] "
        "O estado final não corresponde "
        "à regra esperada."
    )

    sys.exit(1)


finally:

    if cursor:
        cursor.close()

    if conn:
        conn.close()