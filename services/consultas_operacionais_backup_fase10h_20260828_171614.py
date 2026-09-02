from fastapi import HTTPException
from domain.exceptions import NotFoundError


# ============================================================
# NORMALIZAÇÃO
# ============================================================

def _texto(valor):

    if valor is None:
        return None

    return str(valor).strip()


# ============================================================
# LISTAR INVENTÁRIOS
# ============================================================

def listar_inventarios(
    cursor,
    status: str | None = None,
    tipo: str | None = None,
    cliente_id: int | None = None
):

    filtros = []
    parametros = []

    if status:

        filtros.append(
            "I.Status = ?"
        )

        parametros.append(
            status.strip().upper()
        )

    if tipo:

        filtros.append(
            "I.Tipo = ?"
        )

        parametros.append(
            tipo.strip().upper()
        )

    if cliente_id is not None:

        filtros.append(
            "I.ClienteId = ?"
        )

        parametros.append(
            cliente_id
        )

    where = ""

    if filtros:

        where = (
            "WHERE "
            +
            " AND ".join(filtros)
        )

    cursor.execute(
        f"""
        SELECT
            I.ID_Inventario,
            I.CodigoInventario,
            I.Tipo,
            I.Cliente,
            I.ClienteId,
            I.Descricao,
            I.cArmazem,
            I.RodadaAtual,
            I.Status,
            I.DataHoraInicio,
            I.DataHoraFim,
            I.CriadoPor,
            I.FinalizadoPor,

            (
                SELECT COUNT(*)

                FROM dbo.RodadasInventario R

                WHERE
                    R.ID_Inventario =
                    I.ID_Inventario
            ) AS TotalRodadas

        FROM dbo.Inventarios I

        {where}

        ORDER BY
            I.ID_Inventario DESC
        """,
        tuple(parametros)
    )

    linhas = cursor.fetchall()

    return [
        {
            "id_inventario":
                linha.ID_Inventario,

            "codigo_inventario":
                linha.CodigoInventario,

            "tipo":
                linha.Tipo,

            "cliente":
                linha.Cliente,

            "cliente_id":
                linha.ClienteId,

            "descricao":
                linha.Descricao,

            "armazem":
                linha.cArmazem,

            "rodada_atual":
                linha.RodadaAtual,

            "status":
                linha.Status,

            "data_hora_inicio":
                linha.DataHoraInicio,

            "data_hora_fim":
                linha.DataHoraFim,

            "criado_por":
                linha.CriadoPor,

            "finalizado_por":
                linha.FinalizadoPor,

            "total_rodadas":
                linha.TotalRodadas
        }
        for linha in linhas
    ]


# ============================================================
# DETALHE DO INVENTÁRIO
# ============================================================

def consultar_inventario(
    cursor,
    id_inventario: int
):

    cursor.execute(
        """
        SELECT
            ID_Inventario,
            CodigoInventario,
            Tipo,
            Cliente,
            ClienteId,
            Descricao,
            cArmazem,
            RodadaAtual,
            Status,
            DataHoraInicio,
            DataHoraFim,
            CriadoPor,
            DataHoraCriacao,
            FinalizadoPor

        FROM dbo.Inventarios

        WHERE ID_Inventario = ?
        """,
        id_inventario
    )

    linha = cursor.fetchone()

    if not linha:

        raise NotFoundError(
            "Inventário não encontrado."
        )

    return {
        "id_inventario":
            linha.ID_Inventario,

        "codigo_inventario":
            linha.CodigoInventario,

        "tipo":
            linha.Tipo,

        "cliente":
            linha.Cliente,

        "cliente_id":
            linha.ClienteId,

        "descricao":
            linha.Descricao,

        "armazem":
            linha.cArmazem,

        "rodada_atual":
            linha.RodadaAtual,

        "status":
            linha.Status,

        "data_hora_inicio":
            linha.DataHoraInicio,

        "data_hora_fim":
            linha.DataHoraFim,

        "criado_por":
            linha.CriadoPor,

        "data_hora_criacao":
            linha.DataHoraCriacao,

        "finalizado_por":
            linha.FinalizadoPor
    }


# ============================================================
# RODADA ATUAL
# ============================================================

def consultar_rodada_atual(
    cursor,
    id_inventario: int
):

    cursor.execute(
        """
        SELECT
            I.ID_Inventario,
            I.CodigoInventario,
            I.Tipo,
            I.RodadaAtual,

            R.ID_Rodada,
            R.NumeroRodada,
            R.Status,
            R.DataHoraInicio

        FROM dbo.Inventarios I

        LEFT JOIN dbo.RodadasInventario R
            ON R.ID_Inventario =
               I.ID_Inventario

           AND R.NumeroRodada =
               I.RodadaAtual

        WHERE I.ID_Inventario = ?
        """,
        id_inventario
    )

    linha = cursor.fetchone()

    if not linha:

        raise NotFoundError(
            "Inventário não encontrado."
        )

    if linha.ID_Rodada is None:

        raise NotFoundError(
            "Rodada atual não encontrada."
        )

    return {
        "id_inventario":
            linha.ID_Inventario,

        "codigo_inventario":
            linha.CodigoInventario,

        "tipo_inventario":
            linha.Tipo,

        "rodada_atual":
            linha.RodadaAtual,

        "id_rodada":
            linha.ID_Rodada,

        "numero_rodada":
            linha.NumeroRodada,

        "status":
            linha.Status,

        "data_hora_inicio":
            linha.DataHoraInicio
    }


# ============================================================
# LOCALIZAÇÕES DO INVENTÁRIO
# ============================================================

def consultar_localizacoes_inventario(
    cursor,
    id_inventario: int
):

    inventario = consultar_inventario(
        cursor=cursor,
        id_inventario=id_inventario
    )

    tipo = (
        inventario["tipo"]
        .strip()
        .upper()
    )

    rodada_atual = (
        inventario["rodada_atual"]
    )

    cursor.execute(
        """
        SELECT TOP 1
            ID_Rodada

        FROM dbo.RodadasInventario

        WHERE
            ID_Inventario = ?
            AND NumeroRodada = ?
        """,
        (
            id_inventario,
            rodada_atual
        )
    )

    rodada = cursor.fetchone()

    id_rodada = (
        rodada.ID_Rodada
        if rodada
        else None
    )

    # ========================================================
    # ROTATIVO / RODADAS COMPLETAS
    # ========================================================

    if (
        tipo == "ROTATIVO"
        or rodada_atual <= 2
    ):

        cursor.execute(
            """
            SELECT
                E.Localizacao AS Localizacao,

                E.Selecionado,

                UltimaSessao.ID_Sessao,
                UltimaSessao.Status AS StatusSessao

            FROM dbo.InventarioEscopoLocalizacoes E

            OUTER APPLY
            (
                SELECT TOP 1
                    S.ID_Sessao,
                    S.Status

                FROM dbo.SessoesContagem S

                WHERE
                    S.ID_Inventario = E.ID_Inventario
                    AND S.ID_Rodada = ?
                    AND S.Localizacao = E.Localizacao

                ORDER BY
                    S.ID_Sessao DESC
            ) UltimaSessao

            WHERE
                E.ID_Inventario = ?
                AND E.Selecionado = 1

            ORDER BY
                E.Localizacao
            """,
            (
                id_rodada,
                id_inventario
            )
        )

        linhas = cursor.fetchall()

        resultado = []

        for linha in linhas:

            if linha.ID_Sessao is None:

                status = "PENDENTE"

            elif linha.StatusSessao == "ABERTA":

                status = "EM_CONTAGEM"

            else:

                status = "CONCLUIDA"

            resultado.append(
                {
                    "localizacao":
                        linha.Localizacao,

                    "id_sessao":
                        linha.ID_Sessao,

                    "status":
                        status
                }
            )

        return {
            "id_inventario":
                id_inventario,

            "tipo":
                tipo,

            "rodada_atual":
                rodada_atual,

            "id_rodada":
                id_rodada,

            "localizacoes":
                resultado
        }

    # ========================================================
    # OFICIAL R3+
    # ========================================================

    cursor.execute(
        """
        SELECT
            RL.ID_RodadaLocalizacao,
            RL.Localizacao,
            RL.Status

        FROM dbo.RodadaLocalizacoes RL

        WHERE
            RL.ID_Inventario = ?
            AND RL.ID_Rodada = ?

        ORDER BY
            RL.Localizacao
        """,
        (
            id_inventario,
            id_rodada
        )
    )

    linhas = cursor.fetchall()

    return {
        "id_inventario":
            id_inventario,

        "tipo":
            tipo,

        "rodada_atual":
            rodada_atual,

        "id_rodada":
            id_rodada,

        "localizacoes": [
            {
                "id_rodada_localizacao":
                    linha.ID_RodadaLocalizacao,

                "localizacao":
                    linha.Localizacao,

                "status":
                    linha.Status
            }
            for linha in linhas
        ]
    }


# ============================================================
# VISÃO OPERACIONAL ATUAL
# ============================================================

def consultar_contagem_atual(
    cursor,
    id_inventario: int
):

    inventario = consultar_inventario(
        cursor=cursor,
        id_inventario=id_inventario
    )

    rodada = consultar_rodada_atual(
        cursor=cursor,
        id_inventario=id_inventario
    )

    localizacoes = (
        consultar_localizacoes_inventario(
            cursor=cursor,
            id_inventario=id_inventario
        )
    )

    lista = (
        localizacoes["localizacoes"]
    )

    pendentes = sum(
        1
        for item in lista
        if item["status"] == "PENDENTE"
    )

    em_contagem = sum(
        1
        for item in lista
        if item["status"] == "EM_CONTAGEM"
    )

    concluidas = sum(
        1
        for item in lista
        if item["status"] == "CONCLUIDA"
    )

    return {
        "id_inventario":
            id_inventario,

        "codigo_inventario":
            inventario[
                "codigo_inventario"
            ],

        "tipo":
            inventario["tipo"],

        "status_inventario":
            inventario["status"],

        "rodada": rodada,

        "resumo_operacional": {
            "total_localizacoes":
                len(lista),

            "pendentes":
                pendentes,

            "em_contagem":
                em_contagem,

            "concluidas":
                concluidas
        },

        "localizacoes":
            lista
    }
# ============================================================
# DETALHE OPERACIONAL DA LOCALIZAÇÃO
#
# Mantém contagem cega:
#
# NÃO retorna:
# - SaldoInventario
# - QtdEstoque
# - Quantidade esperada
#
# Retorna somente informações operacionais e itens já bipados.
# ============================================================

def consultar_detalhe_localizacao(
    cursor,
    id_inventario: int,
    localizacao: str
):

    localizacao = (
        str(localizacao)
        .strip()
        .upper()
    )

    if not localizacao:

        raise HTTPException(
            status_code=400,
            detail="Localização obrigatória."
        )

    # ========================================================
    # 1. INVENTÁRIO
    # ========================================================

    inventario = consultar_inventario(
        cursor=cursor,
        id_inventario=id_inventario
    )

    tipo = (
        str(
            inventario["tipo"]
        )
        .strip()
        .upper()
    )

    rodada_atual = (
        inventario["rodada_atual"]
    )

    # ========================================================
    # 2. RODADA ATUAL
    # ========================================================

    cursor.execute(
        """
        SELECT
            ID_Rodada,
            NumeroRodada,
            Status

        FROM dbo.RodadasInventario

        WHERE
            ID_Inventario = ?
            AND NumeroRodada = ?
        """,
        (
            id_inventario,
            rodada_atual
        )
    )

    rodada = cursor.fetchone()

    if not rodada:

        raise HTTPException(
            status_code=404,
            detail="Rodada atual não encontrada."
        )

    id_rodada = (
        rodada.ID_Rodada
    )

    # ========================================================
    # 3. VALIDA SE LOCALIZAÇÃO PERTENCE À RODADA
    #
    # ROTATIVO / R1 / R2:
    # InventarioEscopoLocalizacoes
    #
    # OFICIAL R3+:
    # RodadaLocalizacoes
    # ========================================================

    if (
        tipo == "ROTATIVO"
        or rodada.NumeroRodada <= 2
    ):

        cursor.execute(
            """
            SELECT TOP 1
                ID_EscopoLocalizacao,
                Selecionado

            FROM dbo.InventarioEscopoLocalizacoes

            WHERE
                ID_Inventario = ?

                AND Localizacao = ?
            """,
            (
                id_inventario,
                localizacao
            )
        )

        escopo = cursor.fetchone()

        if not escopo:

            raise HTTPException(
                status_code=404,
                detail=(
                    "Localização não pertence "
                    "ao escopo deste inventário."
                )
            )

        if not escopo.Selecionado:

            raise HTTPException(
                status_code=400,
                detail=(
                    "Esta localização foi retirada "
                    "do escopo do inventário."
                )
            )

    else:

        cursor.execute(
            """
            SELECT TOP 1
                ID_RodadaLocalizacao,
                Status

            FROM dbo.RodadaLocalizacoes

            WHERE
                ID_Inventario = ?
                AND ID_Rodada = ?

                AND Localizacao = ?
            """,
            (
                id_inventario,
                id_rodada,
                localizacao
            )
        )

        escopo = cursor.fetchone()

        if not escopo:

            raise HTTPException(
                status_code=404,
                detail=(
                    "Localização não pertence "
                    "ao escopo desta rodada."
                )
            )

    # ========================================================
    # 4. BUSCA ÚLTIMA SESSÃO DA LOCALIZAÇÃO
    # ========================================================

    cursor.execute(
        """
        SELECT TOP 1
            ID_Sessao,
            Status,
            DataHoraInicio,
            DataHoraFim,
            LocalizacaoVazia

        FROM dbo.SessoesContagem

        WHERE
            ID_Inventario = ?
            AND ID_Rodada = ?

            AND Localizacao = ?

        ORDER BY
            ID_Sessao DESC
        """,
        (
            id_inventario,
            id_rodada,
            localizacao
        )
    )

    ultima_sessao = (
        cursor.fetchone()
    )

    # ========================================================
    # 5. DEFINE STATUS OPERACIONAL
    # ========================================================

    if not ultima_sessao:

        status_localizacao = (
            "PENDENTE"
        )

        id_sessao_atual = None

        localizacao_vazia = False

    elif ultima_sessao.Status == "ABERTA":

        status_localizacao = (
            "EM_CONTAGEM"
        )

        id_sessao_atual = (
            ultima_sessao.ID_Sessao
        )

        localizacao_vazia = False

    else:

        status_localizacao = (
            "CONCLUIDA"
        )

        id_sessao_atual = (
            ultima_sessao.ID_Sessao
        )

        localizacao_vazia = bool(
            ultima_sessao.LocalizacaoVazia
        )

    # ========================================================
    # 6. BUSCA TODAS AS CONTAGENS ATIVAS DA LOCALIZAÇÃO
    #
    # Importante:
    #
    # Pode existir mais de uma sessão encerrada para a mesma
    # localização. Somamos as contagens válidas da rodada.
    # ========================================================

    cursor.execute(
        """
        SELECT
            C.Codigo AS Codigo,

            ISNULL(C.Lote, '') AS Lote,

            SUM(
                C.Quantidade
            ) AS Quantidade,

            MAX(
                E.Descricao
            ) AS Produto,

            MAX(
                E.Unidade
            ) AS Unidade,

            MAX(
                E.Categoria
            ) AS Categoria

        FROM dbo.Contagens C

        INNER JOIN dbo.SessoesContagem S
            ON S.ID_Sessao =
               C.ID_Sessao

        LEFT JOIN dbo.InventarioEstoqueSnapshot E
            ON E.ID_Inventario =
               S.ID_Inventario

           AND E.Localizacao =
               S.Localizacao

           AND E.Codigo =
               C.Codigo

           AND ISNULL(E.Lote, '') =
               ISNULL(C.Lote, '')

        WHERE
            S.ID_Inventario = ?
            AND S.ID_Rodada = ?

            AND S.Localizacao = ?
            AND S.ValidaParaConsolidacao = 1

            AND C.Status = 'ATIVA'

        GROUP BY
            C.Codigo,

            ISNULL(C.Lote, '')

        ORDER BY
            C.Codigo,

            ISNULL(C.Lote, '')
        """,
        (
            id_inventario,
            id_rodada,
            localizacao
        )
    )

    linhas = cursor.fetchall()

    itens_bipados = []

    quantidade_total = 0.0

    for linha in linhas:

        quantidade = float(
            linha.Quantidade
        )

        quantidade_total += (
            quantidade
        )

        itens_bipados.append(
            {
                "codigo":
                    linha.Codigo,

                "produto":
                    linha.Produto,

                "lote":
                    linha.Lote,

                "unidade":
                    linha.Unidade,

                "categoria":
                    linha.Categoria,

                "quantidade":
                    quantidade
            }
        )

    # ========================================================
    # 7. CONTAGEM DE SESSÕES DA LOCALIZAÇÃO
    # ========================================================

    cursor.execute(
        """
        SELECT
            COUNT(*) AS TotalSessoes,

            SUM(
                CASE
                    WHEN Status = 'ABERTA'
                    THEN 1
                    ELSE 0
                END
            ) AS SessoesAbertas,

            SUM(
                CASE
                    WHEN Status = 'ENCERRADA'
                    THEN 1
                    ELSE 0
                END
            ) AS SessoesEncerradas

        FROM dbo.SessoesContagem

        WHERE
            ID_Inventario = ?
            AND ID_Rodada = ?

            AND Localizacao = ?
        """,
        (
            id_inventario,
            id_rodada,
            localizacao
        )
    )

    resumo_sessoes = (
        cursor.fetchone()
    )

    total_sessoes = int(
        resumo_sessoes.TotalSessoes
        or 0
    )

    sessoes_abertas = int(
        resumo_sessoes.SessoesAbertas
        or 0
    )

    sessoes_encerradas = int(
        resumo_sessoes.SessoesEncerradas
        or 0
    )

    # ========================================================
    # 8. RETORNO
    # ========================================================

    return {
        "id_inventario":
            id_inventario,

        "codigo_inventario":
            inventario[
                "codigo_inventario"
            ],

        "tipo_inventario":
            tipo,

        "status_inventario":
            inventario["status"],

        "id_rodada":
            id_rodada,

        "numero_rodada":
            rodada.NumeroRodada,

        "status_rodada":
            rodada.Status,

        "localizacao":
            localizacao,

        "status_localizacao":
            status_localizacao,

        "id_sessao_atual":
            id_sessao_atual,

        "localizacao_vazia":
            localizacao_vazia,

        "contagem_cega":
            True,

        "resumo": {
            "registros_bipados":
                len(
                    itens_bipados
                ),

            "quantidade_total_bipada":
                quantidade_total,

            "total_sessoes":
                total_sessoes,

            "sessoes_abertas":
                sessoes_abertas,

            "sessoes_encerradas":
                sessoes_encerradas
        },

        "itens_bipados":
            itens_bipados
    }
# ============================================================
# BUSCAR PRODUTO PARA CONTAGEM CEGA
#
# Retorna dados cadastrais do item no snapshot.
#
# NÃO retorna:
# - SaldoInventario
# - QtdEstoque
# - quantidade esperada
# - diferença
#
# Se o mesmo código possuir vários lotes, todos são retornados.
# ============================================================

def buscar_produto_contagem(
    cursor,
    id_inventario: int,
    codigo: str
):

    codigo = (
        str(codigo).strip()
        if codigo is not None
        else ""
    )

    if not codigo:

        raise HTTPException(
            status_code=400,
            detail="Código obrigatório."
        )

    # ========================================================
    # 1. VALIDA INVENTÁRIO
    # ========================================================

    cursor.execute(
        """
        SELECT
            ID_Inventario,
            CodigoInventario,
            Tipo,
            Status

        FROM dbo.Inventarios

        WHERE ID_Inventario = ?
        """,
        id_inventario
    )

    inventario = cursor.fetchone()

    if not inventario:

        raise HTTPException(
            status_code=404,
            detail="Inventário não encontrado."
        )

   # ============================================================
# VALIDAR LOTE BIPADO
#
# O lote nunca é selecionado automaticamente.
# O operador obrigatoriamente deve bipar.
# ============================================================

def validar_lote_contagem(
    cursor,
    id_inventario: int,
    codigo: str,
    lote: str
):

    codigo = (
        str(codigo).strip()
        if codigo is not None
        else ""
    )

    lote = (
        str(lote).strip()
        if lote is not None
        else ""
    )

    if not codigo:

        raise HTTPException(
            status_code=400,
            detail="Código obrigatório."
        )

    if not lote:

        raise HTTPException(
            status_code=400,
            detail="Lote obrigatório."
        )

    cursor.execute(
        """
        SELECT TOP 1
            Codigo AS Codigo,

            ISNULL(Lote, '') AS Lote,

            Descricao AS Produto,
            Unidade,
            Categoria

        FROM dbo.InventarioEstoqueSnapshot

        WHERE
            ID_Inventario = ?

            AND Codigo = ?

            AND ISNULL(Lote, '') = ?
        """,
        (
            id_inventario,
            codigo,
            lote
        )
    )

    linha = cursor.fetchone()

    if not linha:

        raise HTTPException(
            status_code=404,
            detail=(
                "Lote não encontrado para este código "
                "no inventário."
            )
        )

    return {
        "valido":
            True,

        "id_inventario":
            id_inventario,

        "codigo":
            linha.Codigo,

        "lote":
            linha.Lote,

        "produto":
            linha.Produto,

        "unidade":
            linha.Unidade,

        "categoria":
            linha.Categoria,

        "contagem_cega":
            True,

        "proximo_passo":
            "INFORMAR_QUANTIDADE"
    }