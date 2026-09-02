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

ID_INVENTARIO = 18
ID_RODADA_R1 = 36

LOCALIZACAO = "01PLAQUETA"
CODIGO = "71554091"
LOTE = "3007863574 - 30"

QTD_ESTOQUE = 1
QTD_R1 = 2

DECISAO = "JUSTIFICAR_DIVERGENCIA"

JUSTIFICATIVA = (
    "Divergência validada operacionalmente."
)

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
    etapa
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
        201
    ):

        print(
            f"\n[FALHOU] {etapa}"
        )

        sys.exit(1)

    return dados


def localizar_item(
    analise
):

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

            return item

    return None


# ============================================================
# 0. PREPARAR ESCOPO + SNAPSHOT
# ============================================================

titulo(
    "0. PREPARANDO ESCOPO E SNAPSHOT"
)

conn = None
cursor = None

try:

    conn = get_connection()
    cursor = conn.cursor()

    # ========================================================
    # ESCOPO
    # ========================================================

    cursor.execute(
        """
        SELECT COUNT(*)

        FROM dbo.InventarioEscopoLocalizacoes

        WHERE
            ID_Inventario = ?

            AND UPPER(
                LTRIM(
                    RTRIM(Localizacao)
                )
            ) = ?
        """,
        (
            ID_INVENTARIO,
            LOCALIZACAO
        )
    )

    existe_escopo = (
        cursor.fetchone()[0] > 0
    )

    if not existe_escopo:

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

        print(
            "[OK] Localização adicionada ao escopo."
        )

    else:

        print(
            "[OK] Localização já estava no escopo."
        )

    # ========================================================
    # SNAPSHOT
    # ========================================================

    cursor.execute(
        """
        SELECT COUNT(*)

        FROM dbo.InventarioEstoqueSnapshot

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
            LOTE
        )
    )

    existe_snapshot = (
        cursor.fetchone()[0] > 0
    )

    if not existe_snapshot:

        cursor.execute(
            """
            INSERT INTO dbo.InventarioEstoqueSnapshot
            (
                ID_Inventario,
                cArmazem,
                Localizacao,
                Codigo,
                Lote,
                Descricao,
                Unidade,
                Categoria,
                qArmazenado,
                qReservado,
                SaldoInventario
            )

            VALUES
            (
                ?,
                'ML007',
                ?,
                ?,
                ?,
                'PLAQUETA 40x40x2 72192400',
                'PC',
                'Equipamentos',
                1,
                0,
                1
            )
            """,
            (
                ID_INVENTARIO,
                LOCALIZACAO,
                CODIGO,
                LOTE
            )
        )

        print(
            "[OK] Snapshot criado."
        )

    else:

        print(
            "[OK] Snapshot já existia."
        )

    conn.commit()


finally:

    if cursor:
        cursor.close()

    if conn:
        conn.close()


# ============================================================
# 1. ABRIR SESSÃO R1
# ============================================================

titulo(
    "1. ABRINDO SESSÃO R1"
)

resposta = requests.post(
    f"{BASE_URL}/localizacoes/iniciar",
    json={
        "id_inventario":
            ID_INVENTARIO,

        "id_rodada":
            ID_RODADA_R1,

        "localizacao":
            LOCALIZACAO
    }
)

sessao_r1 = validar_http(
    resposta,
    "Não foi possível abrir a R1."
)

ID_SESSAO_R1 = (
    sessao_r1["id_sessao"]
)

print(
    "\nID Sessão R1:",
    ID_SESSAO_R1
)


# ============================================================
# 2. CONTAGEM DIVERGENTE R1
# ============================================================

titulo(
    "2. REGISTRANDO CONTAGEM DIVERGENTE NA R1"
)

resposta = requests.post(
    f"{BASE_URL}/contagens",
    json={
        "id_sessao":
            ID_SESSAO_R1,

        "codigo":
            CODIGO,

        "lote":
            LOTE,

        "quantidade":
            QTD_R1,

        "usuario":
            USUARIO
    }
)

validar_http(
    resposta,
    "Falha ao registrar contagem R1."
)


# ============================================================
# 3. ENCERRAR R1
# ============================================================

titulo(
    "3. ENCERRANDO SESSÃO R1"
)

resposta = requests.post(
    f"{BASE_URL}/localizacoes/encerrar",
    json={
        "id_sessao":
            ID_SESSAO_R1,

        "usuario":
            USUARIO
    }
)

validar_http(
    resposta,
    "Falha ao encerrar R1."
)


# ============================================================
# 4. ANALISAR R1
# ============================================================

titulo(
    "4. ANALISANDO R1"
)

resposta = requests.get(
    (
        f"{BASE_URL}"
        f"/sessoes/{ID_SESSAO_R1}/analise"
    )
)

analise_r1 = validar_http(
    resposta,
    "Falha ao analisar R1."
)

item_r1 = localizar_item(
    analise_r1
)

if not item_r1:

    print(
        "\n[FALHOU] "
        "Item não encontrado na análise da R1."
    )

    sys.exit(1)


estoque = float(
    item_r1.get(
        "qtd_estoque",
        0
    )
)

contado = float(
    item_r1.get(
        "qtd_contada",
        0
    )
)

diferenca = float(
    item_r1.get(
        "diferenca",
        0
    )
)

status = str(
    item_r1.get(
        "status",
        ""
    )
).strip().upper()


print(
    "\nEstoque:",
    estoque
)

print(
    "Contado R1:",
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
    "Requer decisão:",
    item_r1.get(
        "requer_decisao"
    )
)

print(
    "Pendente decisão:",
    item_r1.get(
        "pendente_decisao"
    )
)


if (
    estoque != QTD_ESTOQUE
    or
    contado != QTD_R1
    or
    diferenca != 1
    or
    status == "OK"
):

    print(
        "\n[FALHOU] "
        "A R1 não criou a divergência esperada."
    )

    sys.exit(1)


print(
    "[OK] Divergência R1 criada."
)


# ============================================================
# 5. REGISTRAR JUSTIFICAR_DIVERGENCIA
# ============================================================

titulo(
    "5. REGISTRANDO JUSTIFICAR_DIVERGENCIA"
)

resposta = requests.post(
    (
        f"{BASE_URL}"
        f"/inventarios/{ID_INVENTARIO}"
        f"/decisoes-rotativo"
    ),
    json={
        "id_rodada":
            ID_RODADA_R1,

        "localizacao":
            LOCALIZACAO,

        "codigo":
            CODIGO,

        "lote":
            LOTE,

        "decisao":
            DECISAO,

        "justificativa":
            JUSTIFICATIVA,

        "usuario":
            USUARIO
    }
)

dados_decisao = validar_http(
    resposta,
    "Falha ao registrar JUSTIFICAR_DIVERGENCIA."
)

ID_DECISAO = (
    dados_decisao[
        "id_decisao_rotativo"
    ]
)

ID_OCORRENCIA = (
    dados_decisao[
        "id_ocorrencia"
    ]
)


print(
    "\nID Decisão:",
    ID_DECISAO
)

print(
    "ID Ocorrência:",
    ID_OCORRENCIA
)

print(
    "Decisão:",
    dados_decisao.get(
        "decisao"
    )
)

print(
    "Status:",
    dados_decisao.get(
        "status"
    )
)

print(
    "Pendente recontagem:",
    dados_decisao.get(
        "pendente_recontagem"
    )
)

print(
    "Divergência justificada:",
    dados_decisao.get(
        "divergencia_justificada"
    )
)


# ============================================================
# 6. ANALISAR NOVAMENTE APÓS JUSTIFICATIVA
# ============================================================

titulo(
    "6. ANALISANDO ITEM APÓS JUSTIFICATIVA"
)

resposta = requests.get(
    (
        f"{BASE_URL}"
        f"/sessoes/{ID_SESSAO_R1}/analise"
    )
)

analise_pos_decisao = validar_http(
    resposta,
    "Falha ao analisar item após decisão."
)

item_pos_decisao = localizar_item(
    analise_pos_decisao
)

if not item_pos_decisao:

    print(
        "\n[FALHOU] "
        "Item não encontrado após decisão."
    )

    sys.exit(1)


print(
    "\nRequer decisão:",
    item_pos_decisao.get(
        "requer_decisao"
    )
)

print(
    "Pendente decisão:",
    item_pos_decisao.get(
        "pendente_decisao"
    )
)

print(
    "Pendente recontagem:",
    item_pos_decisao.get(
        "pendente_recontagem"
    )
)

print(
    "Divergência justificada:",
    item_pos_decisao.get(
        "divergencia_justificada"
    )
)

print(
    "Decisão:",
    item_pos_decisao
    .get(
        "decisao_rotativo",
        {}
    )
    .get(
        "decisao"
    )
)


# ============================================================
# 7. VALIDAR ESTADO DA JUSTIFICATIVA
# ============================================================

titulo(
    "7. VALIDANDO ESTADO DA JUSTIFICATIVA"
)


analise_ok = (
    item_pos_decisao.get(
        "pendente_decisao"
    )
    is False

    and

    item_pos_decisao.get(
        "pendente_recontagem"
    )
    is False

    and

    item_pos_decisao.get(
        "divergencia_justificada"
    )
    is True

    and

    str(
        item_pos_decisao
        .get(
            "decisao_rotativo",
            {}
        )
        .get(
            "decisao",
            ""
        )
    ).strip().upper()
    ==
    "JUSTIFICAR_DIVERGENCIA"
)


if not analise_ok:

    print(
        "\n[FALHOU] "
        "O item não ficou corretamente justificado."
    )

    sys.exit(1)


print(
    "[OK] Divergência marcada como justificada."
)


# ============================================================
# 8. VALIDAR BANCO ANTES DA PRÓXIMA RODADA
# ============================================================

titulo(
    "8. VALIDANDO BANCO"
)

conn = None
cursor = None

try:

    conn = get_connection()
    cursor = conn.cursor()

    # ========================================================
    # OCORRÊNCIA
    # ========================================================

    cursor.execute(
        """
        SELECT
            ID_Ocorrencia,
            StatusResolucao,
            Justificativa,
            ID_DecisaoRotativo,
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

    # ========================================================
    # DECISÃO
    # ========================================================

    cursor.execute(
        """
        SELECT
            ID_DecisaoRotativo,
            Decisao,
            Justificativa,
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
        "\nOCORRÊNCIA"
    )

    print(
        "ID:",
        ocorrencia.ID_Ocorrencia
    )

    print(
        "Status:",
        ocorrencia.StatusResolucao
    )

    print(
        "Justificativa:",
        ocorrencia.Justificativa
    )

    print(
        "ID Decisão:",
        ocorrencia.ID_DecisaoRotativo
    )

    print(
        "Tipo resolução:",
        ocorrencia.TipoResolucao
    )

    print(
        "Resolvido por:",
        ocorrencia.ResolvidoPor
    )

    print(
        "Data resolução:",
        ocorrencia.DataHoraResolucao
    )


    print(
        "\nDECISÃO"
    )

    print(
        "ID:",
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

    print(
        "Justificativa:",
        decisao.Justificativa
    )


    ocorrencia_ok = (
        str(
            ocorrencia.StatusResolucao
        ).strip().upper()
        ==
        "JUSTIFICADA"

        and

        ocorrencia.ID_DecisaoRotativo
        ==
        ID_DECISAO

        and

        ocorrencia.TipoResolucao
        is None

        and

        ocorrencia.ResolvidoPor
        is None

        and

        ocorrencia.DataHoraResolucao
        is None
    )


    decisao_ok = (
        str(
            decisao.Decisao
        ).strip().upper()
        ==
        "JUSTIFICAR_DIVERGENCIA"

        and

        str(
            decisao.Status
        ).strip().upper()
        ==
        "ATIVA"

        and

        str(
            decisao.Justificativa
        ).strip()
        ==
        JUSTIFICATIVA
    )


    if not (
        ocorrencia_ok
        and
        decisao_ok
    ):

        print(
            "\n[FALHOU] "
            "Banco não corresponde ao estado esperado."
        )

        sys.exit(1)


    print(
        "\n[OK] Banco consistente."
    )


finally:

    if cursor:
        cursor.close()

    if conn:
        conn.close()


# ============================================================
# 9. SOLICITAR PRÓXIMA RODADA
# ============================================================

titulo(
    "9. SOLICITANDO PRÓXIMA RODADA"
)

resposta = requests.post(
    (
        f"{BASE_URL}"
        f"/inventarios/{ID_INVENTARIO}"
        f"/rodadas/proxima"
    )
)

dados_proxima = validar_http(
    resposta,
    "Falha ao processar próxima rodada."
)


# ============================================================
# 10. MOSTRAR DECISÃO DO SISTEMA
# ============================================================

titulo(
    "10. RESULTADO DA PRÓXIMA RODADA"
)

print(
    dados_proxima
)


# ============================================================
# 11. VERIFICAR SE ITEM ENTROU EM R2
#
# Regra principal:
# JUSTIFICAR_DIVERGENCIA não pode gerar recontagem.
# ============================================================

titulo(
    "11. VALIDANDO QUE ITEM NÃO ENTROU EM RECONTAGEM"
)

conn = None
cursor = None

try:

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT COUNT(*)

        FROM dbo.RodadaItens RI

        INNER JOIN dbo.RodadasInventario R
            ON R.ID_Rodada =
               RI.ID_Rodada

        WHERE
            RI.ID_Inventario = ?

            AND R.NumeroRodada = 2

            AND LTRIM(
                RTRIM(RI.Codigo)
            ) = ?

            AND ISNULL(
                LTRIM(
                    RTRIM(RI.Lote)
                ),
                ''
            ) = ?
        """,
        (
            ID_INVENTARIO,
            CODIGO,
            LOTE
        )
    )

    entrou_r2 = int(
        cursor.fetchone()[0]
    )


    print(
        "Quantidade de registros deste item na R2:",
        entrou_r2
    )


    # ========================================================
    # ESTADO DO INVENTÁRIO
    # ========================================================

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


    print(
        "Status inventário:",
        inventario.Status
    )

    print(
        "Rodada atual:",
        inventario.RodadaAtual
    )


    # ========================================================
    # RESULTADO FINAL
    # ========================================================

    titulo(
        "RESULTADO"
    )


    if entrou_r2 != 0:

        print(
            "[FALHOU] "
            "Item JUSTIFICADO entrou indevidamente na R2."
        )

        sys.exit(1)


    print(
        "[APROVADO] "
        "A divergência justificada não foi enviada "
        "indevidamente para recontagem."
    )

    print(
        "\nRegra validada:"
    )

    print(
        "R1 DIVERGENTE"
    )

    print("+")
    print(
        "JUSTIFICAR_DIVERGENCIA"
    )

    print("=")

    print(
        "OCORRÊNCIA JUSTIFICADA"
    )

    print(
        "SEM PENDÊNCIA DE RECONTAGEM"
    )

    print(
        "ITEM NÃO ENTRA NA R2"
    )

    sys.exit(0)


finally:

    if cursor:
        cursor.close()

    if conn:
        conn.close()