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

ID_INVENTARIO = 19
ID_RODADA_R1 = 37

LOCALIZACAO = "01PLAQUETA"
CODIGO = "71554091"
LOTE = "3007863574 - 30"

QTD_ESTOQUE = 1.0

# R1 deve gerar divergência
QTD_R1 = 2.0

# R2 deve corrigir a divergência
QTD_R2 = 1.0

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
    codigos_validos=(200, 201),
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

    if resposta.status_code not in codigos_validos:

        print(
            f"\n[FALHOU] {etapa}"
        )

        sys.exit(1)

    return dados


def falhar(mensagem):

    print(
        f"\n[FALHOU] {mensagem}"
    )

    sys.exit(1)


def obter_item_analise(dados):

    itens = dados.get(
        "itens",
        []
    )

    for item in itens:

        if (
            item.get("localizacao") == LOCALIZACAO
            and
            item.get("codigo") == CODIGO
            and
            item.get("lote") == LOTE
        ):
            return item

    return None


# ============================================================
# CONEXÃO
# ============================================================

conn = get_connection()
cursor = conn.cursor()


try:

    # ========================================================
    # 0. VALIDANDO INVENTÁRIO
    # ========================================================

    titulo(
        "0. VALIDANDO INVENTÁRIO"
    )

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
        (
            ID_INVENTARIO,
        )
    )

    inventario = cursor.fetchone()

    if not inventario:

        falhar(
            "Inventário 19 não encontrado."
        )

    print(
        "ID Inventário:",
        inventario.ID_Inventario
    )

    print(
        "Código:",
        inventario.CodigoInventario
    )

    print(
        "Tipo:",
        inventario.Tipo
    )

    print(
        "Status:",
        inventario.Status
    )

    print(
        "Rodada atual:",
        inventario.RodadaAtual
    )

    if inventario.Status != "ABERTO":

        falhar(
            "O inventário não está ABERTO."
        )

    if int(inventario.RodadaAtual) != 1:

        falhar(
            "O inventário não está na R1."
        )


    # ========================================================
    # 1. PREPARANDO ESCOPO
    # ========================================================

    titulo(
        "1. PREPARANDO ESCOPO"
    )

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM dbo.InventarioEscopoLocalizacoes
        WHERE
            ID_Inventario = ?
            AND Localizacao = ?
        """,
        (
            ID_INVENTARIO,
            LOCALIZACAO
        )
    )

    existe_escopo = int(
        cursor.fetchone()[0]
    )

    if existe_escopo == 0:

        cursor.execute(
            """
            INSERT INTO dbo.InventarioEscopoLocalizacoes
            (
                ID_Inventario,
                Localizacao
            )
            VALUES
            (
                ?,
                ?
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

        print(
            "[OK] Localização já existe no escopo."
        )


            # ========================================================
    # 2. VALIDANDO / CRIANDO SNAPSHOT
    # ========================================================

    titulo(
        "2. VALIDANDO / CRIANDO SNAPSHOT"
    )

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

    if total_snapshot > 0:

        print(
            f"[OK] Snapshot já existe com "
            f"{total_snapshot} registro(s)."
        )

    else:

        resposta = requests.post(
            (
                f"{BASE_URL}/inventarios/"
                f"{ID_INVENTARIO}/snapshot"
            ),
            json={}
        )

        dados_snapshot = validar_http(
            resposta,
            "Falha ao criar snapshot."
        )

        print(
            "[OK] Snapshot criado."
        )
    # ========================================================
    # 3. VALIDANDO ITEM NO SNAPSHOT
    # ========================================================

    titulo(
        "3. VALIDANDO ITEM NO SNAPSHOT"
    )

    cursor.execute(
        """
        SELECT TOP 1
            Localizacao,
            Codigo,
            Lote,
            SaldoInventario
        FROM dbo.InventarioEstoqueSnapshot
        WHERE
            ID_Inventario = ?
            AND Localizacao = ?
            AND Codigo = ?
            AND Lote = ?
        """,
        (
            ID_INVENTARIO,
            LOCALIZACAO,
            CODIGO,
            LOTE
        )
    )

    snapshot = cursor.fetchone()

    if not snapshot:

        falhar(
            "Item não encontrado no snapshot."
        )

    qtd_snapshot = float(
        snapshot.SaldoInventario or 0
    )

    print(
        "Localização:",
        snapshot.Localizacao
    )

    print(
        "Código:",
        snapshot.Codigo
    )

    print(
        "Lote:",
        snapshot.Lote
    )

    print(
        "Quantidade estoque:",
        qtd_snapshot
    )

    if qtd_snapshot != QTD_ESTOQUE:

        falhar(
            (
                "Quantidade do snapshot diferente "
                f"do esperado. Esperado={QTD_ESTOQUE} "
                f"Encontrado={qtd_snapshot}"
            )
        )

    print(
        "[OK] Snapshot validado."
    )
        # ========================================================
    # 4. ABRINDO SESSÃO R1
    # ========================================================

    titulo(
        "4. ABRINDO SESSÃO R1"
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

    dados_r1 = validar_http(
        resposta,
        "Falha ao abrir sessão R1."
    )

    ID_SESSAO_R1 = dados_r1[
        "id_sessao"
    ]

    print(
        "\nID Sessão R1:",
        ID_SESSAO_R1
    )


    # ========================================================
    # 5. CONTAGEM DIVERGENTE R1
    # ========================================================

    titulo(
        "5. CONTANDO 2 UNIDADES NA R1"
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

    dados_contagem_r1 = validar_http(
        resposta,
        "Falha ao registrar contagem R1."
    )

    print(
        "\nID Contagem R1:",
        dados_contagem_r1.get(
            "id_contagem"
        )
    )
        # ========================================================
    # 6. ENCERRANDO SESSÃO R1
    # ========================================================

    titulo(
        "6. ENCERRANDO SESSÃO R1"
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
        "Falha ao encerrar sessão R1."
    )


    # ========================================================
    # 7. ANALISANDO R1
    # ========================================================

    titulo(
        "7. ANALISANDO R1"
    )

    resposta = requests.get(
        (
            f"{BASE_URL}/sessoes/"
            f"{ID_SESSAO_R1}/analise"
        )
    )

    analise_r1 = validar_http(
        resposta,
        "Falha ao analisar R1."
    )

    item_r1 = obter_item_analise(
        analise_r1
    )

    if not item_r1:

        falhar(
            "Item não encontrado na análise R1."
        )

    print(
        "\nEstoque:",
        item_r1.get(
            "qtd_estoque"
        )
    )

    print(
        "Contado R1:",
        item_r1.get(
            "qtd_contada"
        )
    )

    print(
        "Diferença:",
        item_r1.get(
            "diferenca"
        )
    )

    print(
        "Status:",
        item_r1.get(
            "status"
        )
    )

    if item_r1.get(
        "status"
    ) != "DIVERGÊNCIA":

        falhar(
            "A R1 deveria estar divergente."
        )

    if float(
        item_r1.get(
            "diferenca",
            0
        )
    ) != 1.0:

        falhar(
            "Diferença da R1 deveria ser 1."
        )

    if not item_r1.get(
        "requer_decisao"
    ):

        falhar(
            "A divergência deveria requerer decisão."
        )

    print(
        "[OK] Divergência R1 criada."
    )


    # ========================================================
    # 8. DECISÃO RECONTAR
    # ========================================================

    titulo(
        "8. REGISTRANDO DECISÃO RECONTAR"
    )

    resposta = requests.post(
        (
            f"{BASE_URL}/inventarios/"
            f"{ID_INVENTARIO}/rotativo/decisoes"
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
                "RECONTAR",

            "justificativa":
                (
                    "Teste E2E regressão: "
                    "recontagem para validar "
                    "divergência da R1."
                ),

            "usuario":
                USUARIO
        }
    )

    dados_decisao = validar_http(
        resposta,
        "Falha ao registrar decisão RECONTAR."
    )

    ID_DECISAO = dados_decisao.get(
        "id_decisao_rotativo"
    )

    ID_OCORRENCIA = dados_decisao.get(
        "id_ocorrencia"
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
        "Pendente recontagem:",
        dados_decisao.get(
            "pendente_recontagem"
        )
    )

    if dados_decisao.get(
        "decisao"
    ) != "RECONTAR":

        falhar(
            "Decisão diferente de RECONTAR."
        )

    if not dados_decisao.get(
        "pendente_recontagem"
    ):

        falhar(
            "Item deveria estar pendente de recontagem."
        )


    # ========================================================
    # 9. GERANDO R2
    # ========================================================

    titulo(
        "9. GERANDO R2"
    )

    resposta = requests.post(
        (
            f"{BASE_URL}/inventarios/"
            f"{ID_INVENTARIO}/proxima-rodada"
        )
    )

    dados_proxima = validar_http(
        resposta,
        "Falha ao gerar R2."
    )

    proxima = dados_proxima.get(
        "proxima_rodada",
        dados_proxima
    )

    ID_RODADA_R2 = proxima.get(
        "id_rodada"
    )

    NUMERO_R2 = proxima.get(
        "numero_rodada"
    )

    print(
        "\nID Rodada R2:",
        ID_RODADA_R2
    )

    print(
        "Número rodada:",
        NUMERO_R2
    )

    print(
        "Tipo:",
        proxima.get(
            "tipo_rodada"
        )
    )

    print(
        "Itens gerados:",
        proxima.get(
            "itens_gerados"
        )
    )

    print(
        "Localizações:",
        proxima.get(
            "localizacoes"
        )
    )

    if NUMERO_R2 != 2:

        falhar(
            "A próxima rodada deveria ser R2."
        )

    if proxima.get(
        "tipo_rodada"
    ) != "DIVERGENCIAS":

        falhar(
            "A R2 deveria ser DIVERGENCIAS."
        )

    if int(
        proxima.get(
            "itens_gerados",
            0
        )
    ) != 1:

        falhar(
            "A R2 deveria possuir exatamente 1 item."
        )


    # ========================================================
    # 10. ABRINDO SESSÃO R2
    # ========================================================

    titulo(
        "10. ABRINDO SESSÃO R2"
    )

    resposta = requests.post(
        f"{BASE_URL}/sessoes/abrir",
        json={
            "id_inventario":
                ID_INVENTARIO,

            "localizacao":
                LOCALIZACAO,

            "usuario":
                USUARIO
        }
    )

    dados_sessao_r2 = validar_http(
        resposta,
        "Falha ao abrir sessão R2."
    )

    ID_SESSAO_R2 = dados_sessao_r2[
        "id_sessao"
    ]

    print(
        "\nID Sessão R2:",
        ID_SESSAO_R2
    )

    print(
        "Rodada:",
        dados_sessao_r2.get(
            "numero_rodada"
        )
    )

    print(
        "Tipo operação:",
        dados_sessao_r2.get(
            "tipo_operacao"
        )
    )

    if dados_sessao_r2.get(
        "numero_rodada"
    ) != 2:

        falhar(
            "Sessão deveria pertencer à R2."
        )


    # ========================================================
    # 11. R2 CORRIGE A DIVERGÊNCIA
    # ========================================================

    titulo(
        "11. CONTANDO 1 UNIDADE NA R2"
    )

    resposta = requests.post(
        (
            f"{BASE_URL}/sessoes/"
            f"{ID_SESSAO_R2}/contagens"
        ),
        json={
            "codigo":
                CODIGO,

            "lote":
                LOTE,

            "quantidade":
                QTD_R2,

            "usuario":
                USUARIO
        }
    )

    validar_http(
        resposta,
        "Falha ao registrar contagem R2."
    )


    # ========================================================
    # 12. ENCERRANDO SESSÃO R2
    # ========================================================

    titulo(
        "12. ENCERRANDO SESSÃO R2"
    )

    resposta = requests.post(
        (
            f"{BASE_URL}/sessoes/"
            f"{ID_SESSAO_R2}/encerrar"
        ),
        json={
            "usuario":
                USUARIO
        }
    )

    validar_http(
        resposta,
        "Falha ao encerrar sessão R2."
    )


    # ========================================================
    # 13. ANALISANDO R2
    # ========================================================

    titulo(
        "13. ANALISANDO R2"
    )

    resposta = requests.get(
        (
            f"{BASE_URL}/sessoes/"
            f"{ID_SESSAO_R2}/analise"
        )
    )

    analise_r2 = validar_http(
        resposta,
        "Falha ao analisar R2."
    )

    item_r2 = obter_item_analise(
        analise_r2
    )

    if not item_r2:

        falhar(
            "Item não encontrado na análise R2."
        )

    print(
        "\nEstoque:",
        item_r2.get(
            "qtd_estoque"
        )
    )

    print(
        "Contado R2:",
        item_r2.get(
            "qtd_contada"
        )
    )

    print(
        "Diferença:",
        item_r2.get(
            "diferenca"
        )
    )

    print(
        "Status:",
        item_r2.get(
            "status"
        )
    )

    if item_r2.get(
        "status"
    ) != "OK":

        falhar(
            "A R2 deveria corrigir a divergência."
        )

    if float(
        item_r2.get(
            "diferenca",
            999
        )
    ) != 0.0:

        falhar(
            "Diferença final da R2 deveria ser zero."
        )

    print(
        "[OK] R2 corrigiu a divergência."
    )


    # ========================================================
    # 14. FINALIZANDO INVENTÁRIO
    # ========================================================

    titulo(
        "14. FINALIZANDO INVENTÁRIO"
    )

    resposta = requests.post(
        (
            f"{BASE_URL}/inventarios/"
            f"{ID_INVENTARIO}/proxima-rodada"
        )
    )

    dados_finalizacao = validar_http(
        resposta,
        "Falha ao finalizar inventário."
    )

    proxima_final = dados_finalizacao.get(
        "proxima_rodada",
        dados_finalizacao
    )

    print(
        "\nEncerrado:",
        proxima_final.get(
            "encerrado"
        )
    )

    print(
        "Status inventário:",
        proxima_final.get(
            "status_inventario"
        )
    )

    print(
        "Status rodada:",
        proxima_final.get(
            "status_rodada"
        )
    )

    print(
        "Motivo:",
        proxima_final.get(
            "motivo"
        )
    )

    if not proxima_final.get(
        "encerrado"
    ):

        falhar(
            "O inventário deveria ter sido encerrado."
        )

    if proxima_final.get(
        "status_inventario"
    ) != "FINALIZADO":

        falhar(
            "Status do inventário deveria ser FINALIZADO."
        )


    # ========================================================
    # 15. VALIDANDO ESTADO FINAL NO BANCO
    # ========================================================

    titulo(
        "15. VALIDANDO ESTADO FINAL NO BANCO"
    )

    cursor.execute(
        """
        SELECT
            Status,
            RodadaAtual
        FROM dbo.Inventarios
        WHERE ID_Inventario = ?
        """,
        (
            ID_INVENTARIO,
        )
    )

    estado_inventario = cursor.fetchone()

    print(
        "\nINVENTÁRIO"
    )

    print(
        "Status:",
        estado_inventario.Status
    )

    print(
        "Rodada Atual:",
        estado_inventario.RodadaAtual
    )


    # ========================================================
    # OCORRÊNCIA
    # ========================================================

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
        FROM dbo.InventarioDivergenciasOcorrencias
        WHERE ID_Ocorrencia = ?
        """,
        (
            ID_OCORRENCIA,
        )
    )

    ocorrencia = cursor.fetchone()

    if not ocorrencia:

        falhar(
            "Ocorrência não encontrada."
        )

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
        "ID Inventário resolução:",
        ocorrencia.ID_InventarioResolucao
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
        "Observação:",
        ocorrencia.ObservacaoResolucao
    )

    print(
        "Resolvido por:",
        ocorrencia.ResolvidoPor
    )

    print(
        "Data resolução:",
        ocorrencia.DataHoraResolucao
    )


    # ========================================================
    # DECISÃO
    # ========================================================

    cursor.execute(
        """
        SELECT
            ID_DecisaoRotativo,
            Decisao,
            Status
        FROM dbo.DecisoesRotativo
        WHERE ID_DecisaoRotativo = ?
        """,
        (
            ID_DECISAO,
        )
    )

    decisao = cursor.fetchone()

    if not decisao:

        falhar(
            "Decisão rotativa não encontrada."
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


    # ========================================================
    # RESULTADO FINAL
    # ========================================================

    cursor.execute(
        """
        SELECT TOP 1
            Localizacao,
            Codigo,
            Lote,
            QuantidadeEstoque,
            QuantidadeFinal,
            DiferencaFinal,
            StatusFinal,
            OrigemQuantidade,
            RodadaFinal
        FROM dbo.InventarioResultadoFinal
        WHERE
            ID_Inventario = ?
            AND Localizacao = ?
            AND Codigo = ?
            AND Lote = ?
        """,
        (
            ID_INVENTARIO,
            LOCALIZACAO,
            CODIGO,
            LOTE
        )
    )

    resultado = cursor.fetchone()

    if not resultado:

        falhar(
            "Resultado final não encontrado."
        )

    print(
        "\nRESULTADO FINAL"
    )

    print(
        "Localização:",
        resultado.Localizacao
    )

    print(
        "Código:",
        resultado.Codigo
    )

    print(
        "Lote:",
        resultado.Lote
    )

    print(
        "Estoque:",
        resultado.QuantidadeEstoque
    )

    print(
        "Quantidade Final:",
        resultado.QuantidadeFinal
    )

    print(
        "Diferença Final:",
        resultado.DiferencaFinal
    )

    print(
        "Status Final:",
        resultado.StatusFinal
    )

    print(
        "Origem Quantidade:",
        resultado.OrigemQuantidade
    )

    print(
        "Rodada Final:",
        resultado.RodadaFinal
    )


    # ========================================================
    # 16. ASSERTS FINAIS
    # ========================================================

    titulo(
        "16. VALIDANDO REGRESSÃO"
    )

    erros = []

    if estado_inventario.Status != "FINALIZADO":

        erros.append(
            (
                "Inventário deveria estar "
                "FINALIZADO."
            )
        )

    if int(
        estado_inventario.RodadaAtual
    ) != 2:

        erros.append(
            "RodadaAtual deveria ser 2."
        )

    if (
        ocorrencia.StatusResolucao
        != "RESOLVIDA_RECONTAGEM"
    ):

        erros.append(
            (
                "Ocorrência deveria estar "
                "RESOLVIDA_RECONTAGEM."
            )
        )

    if (
        ocorrencia.TipoResolucao
        != "RECONTAGEM"
    ):

        erros.append(
            (
                "TipoResolucao deveria ser "
                "RECONTAGEM."
            )
        )

    if (
        ocorrencia.ID_InventarioResolucao
        != ID_INVENTARIO
    ):

        erros.append(
            (
                "ID_InventarioResolucao "
                "incorreto."
            )
        )

    if (
        ocorrencia.ID_RodadaResolucao
        != ID_RODADA_R2
    ):

        erros.append(
            (
                "ID_RodadaResolucao "
                "deveria apontar para R2."
            )
        )

    if decisao.Status != "CONCLUIDA":

        erros.append(
            (
                "Decisão RECONTAR deveria "
                "estar CONCLUIDA."
            )
        )

    if float(
        resultado.QuantidadeEstoque
    ) != QTD_ESTOQUE:

        erros.append(
            "QuantidadeEstoque incorreta."
        )

    if float(
        resultado.QuantidadeFinal
    ) != QTD_R2:

        erros.append(
            "QuantidadeFinal incorreta."
        )

    if float(
        resultado.DiferencaFinal
    ) != 0.0:

        erros.append(
            "DiferencaFinal deveria ser zero."
        )

    if resultado.StatusFinal != "OK":

        erros.append(
            "StatusFinal deveria ser OK."
        )

    if int(
        resultado.RodadaFinal
    ) != 2:

        erros.append(
            "RodadaFinal deveria ser 2."
        )

    if erros:

        print(
            "\n[FALHOU] Foram encontradas "
            "inconsistências:"
        )

        for erro in erros:

            print(
                "-",
                erro
            )

        sys.exit(1)


    # ========================================================
    # RESULTADO
    # ========================================================

    titulo(
        "RESULTADO"
    )

    print(
        "[APROVADO] Regressão do fluxo "
        "R1 -> RECONTAR -> R2 -> FINALIZAÇÃO."
    )

    print()

    print(
        "Regra validada:"
    )

    print(
        "R1 DIVERGENTE"
    )

    print(
        "+"
    )

    print(
        "RECONTAR"
    )

    print(
        "+"
    )

    print(
        "R2 CORRIGE"
    )

    print(
        "="
    )

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
        "INVENTÁRIO = FINALIZADO"
    )


finally:

    try:
        cursor.close()

    except Exception:
        pass

    try:
        conn.close()

    except Exception:
        pass