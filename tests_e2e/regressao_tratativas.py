from datetime import date, timedelta

from database import get_connection
from domain.exceptions import InvalidStateError
from services.planos_acao import (
    atualizar_analise,
    atualizar_plano_acao,
    concluir_plano_acao,
    criar_analise_ocorrencia,
    criar_evidencia_plano,
    criar_plano_acao,
    criar_validacao_eficacia,
    encerrar_analise,
    remover_evidencia_plano,
)


ID_OCORRENCIA = 528
ATOR = "admin"

passou = 0
falhou = 0


def validar(nome, condicao):
    global passou, falhou

    if condicao:
        passou += 1
        print(f"PASS | {nome}")
    else:
        falhou += 1
        print(f"FAIL | {nome}")


conn = get_connection()
cursor = conn.cursor()

try:
    print("=" * 70)
    print("REGRESSAO CURTA - TRATATIVAS")
    print("=" * 70)

    cursor.execute(
        """
        SELECT StatusResolucao
        FROM dbo.OcorrenciasDivergencia
        WHERE ID_Ocorrencia = ?
        """,
        ID_OCORRENCIA,
    )

    status_inicial = cursor.fetchone()[0]

    validar(
        "Ocorrencia inicia DIVERGENCIA_CONFIRMADA",
        status_inicial == "DIVERGENCIA_CONFIRMADA",
    )

    # --------------------------------------------------------
    # ANALISE
    # --------------------------------------------------------

    analise = criar_analise_ocorrencia(
        cursor=cursor,
        id_ocorrencia=ID_OCORRENCIA,
        categoria_causa="PROCESSO",
        causa_raiz="Causa temporaria da regressao.",
        observacao="Teste automatizado.",
        ator=ATOR,
    )

    id_analise = analise["id_analise"]

    validar(
        "Criar analise",
        id_analise is not None,
    )

    atualizar_analise(
        cursor=cursor,
        id_analise=id_analise,
        categoria_causa="PROCESSO",
        causa_raiz="Causa atualizada pela regressao.",
        observacao="Atualizacao automatizada.",
        ator=ATOR,
    )

    cursor.execute(
        """
        SELECT CausaRaiz
        FROM dbo.AnalisesOcorrencia
        WHERE ID_Analise = ?
        """,
        id_analise,
    )

    validar(
        "Atualizar analise",
        cursor.fetchone()[0]
        == "Causa atualizada pela regressao.",
    )

    encerrar_analise(
        cursor=cursor,
        id_analise=id_analise,
        ator=ATOR,
    )

    cursor.execute(
        """
        SELECT Status
        FROM dbo.AnalisesOcorrencia
        WHERE ID_Analise = ?
        """,
        id_analise,
    )

    validar(
        "Encerrar analise",
        cursor.fetchone()[0] == "ENCERRADA",
    )

    # --------------------------------------------------------
    # PLANO
    # --------------------------------------------------------

    plano = criar_plano_acao(
        cursor=cursor,
        id_analise=id_analise,
        descricao_acao="Plano temporario da regressao.",
        responsavel="Rai",
        data_prazo=date.today() + timedelta(days=7),
        prioridade="MEDIA",
        observacao="Teste automatizado.",
        ator=ATOR,
    )

    id_plano = plano["id_plano_acao"]

    validar(
        "Criar plano",
        id_plano is not None,
    )

    atualizar_plano_acao(
        cursor=cursor,
        id_plano=id_plano,
        descricao_acao="Plano atualizado pela regressao.",
        responsavel="Rai",
        data_prazo=date.today() + timedelta(days=7),
        prioridade="ALTA",
        status="EM_ANDAMENTO",
        observacao="Plano atualizado.",
        ator=ATOR,
    )

    cursor.execute(
        """
        SELECT Status, Prioridade
        FROM dbo.PlanosAcaoOcorrencia
        WHERE ID_PlanoAcao = ?
        """,
        id_plano,
    )

    status, prioridade = cursor.fetchone()

    validar(
        "Atualizar plano",
        status == "EM_ANDAMENTO"
        and prioridade == "ALTA",
    )

    # --------------------------------------------------------
    # EVIDENCIA
    # --------------------------------------------------------

    evidencia = criar_evidencia_plano(
        cursor=cursor,
        id_plano=id_plano,
        tipo_evidencia="DOCUMENTO",
        descricao="Evidencia temporaria.",
        referencia_arquivo="regressao://tratativas",
        ator=ATOR,
    )

    id_evidencia = evidencia["id_evidencia"]

    validar(
        "Criar evidencia",
        id_evidencia is not None,
    )

    remover_evidencia_plano(
        cursor=cursor,
        id_evidencia=id_evidencia,
    )

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM dbo.PlanoAcaoEvidencias
        WHERE ID_Evidencia = ?
        """,
        id_evidencia,
    )

    validar(
        "Remover evidencia",
        cursor.fetchone()[0] == 0,
    )

    # --------------------------------------------------------
    # CONCLUSAO DO PLANO
    # --------------------------------------------------------

    concluir_plano_acao(
        cursor=cursor,
        id_plano=id_plano,
        ator=ATOR,
    )

    cursor.execute(
        """
        SELECT Status
        FROM dbo.PlanosAcaoOcorrencia
        WHERE ID_PlanoAcao = ?
        """,
        id_plano,
    )

    validar(
        "Concluir plano",
        cursor.fetchone()[0] == "CONCLUIDO",
    )

    # --------------------------------------------------------
    # CRIA OUTRO PLANO ATIVO TEMPORARIO
    # --------------------------------------------------------

    outro_plano = criar_plano_acao(
        cursor=cursor,
        id_analise=id_analise,
        descricao_acao="Segundo plano ativo da regressao.",
        responsavel="Rai",
        data_prazo=date.today() + timedelta(days=10),
        prioridade="MEDIA",
        observacao="Usado para validar bloqueio de eficacia.",
        ator=ATOR,
    )

    id_outro_plano = outro_plano["id_plano_acao"]

    validar(
        "Criar segundo plano ativo",
        id_outro_plano is not None,
    )

    # --------------------------------------------------------
    # EFICAZ BLOQUEADO POR OUTRO PLANO ATIVO DA OCORRENCIA
    # --------------------------------------------------------

    bloqueado = False

    try:
        criar_validacao_eficacia(
            cursor=cursor,
            id_plano=id_plano,
            resultado="EFICAZ",
            criterio_validacao="Deve bloquear com outro plano ativo.",
            observacao=None,
            ator=ATOR,
        )
    except InvalidStateError:
        bloqueado = True

    validar(
        "EFICAZ bloqueado com outro plano ativo",
        bloqueado,
    )

    # Cancela TEMPORARIAMENTE outros planos ativos.
    cursor.execute(
        """
        UPDATE P
        SET P.Status = 'CANCELADO'
        FROM dbo.PlanosAcaoOcorrencia P
        INNER JOIN dbo.AnalisesOcorrencia A
            ON A.ID_Analise = P.ID_Analise
        WHERE A.ID_Ocorrencia = ?
          AND P.ID_PlanoAcao <> ?
          AND P.Status IN ('ABERTO', 'EM_ANDAMENTO')
        """,
        ID_OCORRENCIA,
        id_plano,
    )

    # --------------------------------------------------------
    # INEFICAZ
    # --------------------------------------------------------

    criar_validacao_eficacia(
        cursor=cursor,
        id_plano=id_plano,
        resultado="INEFICAZ",
        criterio_validacao="Teste regressivo ineficaz.",
        observacao=None,
        ator=ATOR,
    )

    cursor.execute(
        """
        SELECT StatusResolucao
        FROM dbo.OcorrenciasDivergencia
        WHERE ID_Ocorrencia = ?
        """,
        ID_OCORRENCIA,
    )

    validar(
        "INEFICAZ mantem ocorrencia aberta",
        cursor.fetchone()[0]
        == "DIVERGENCIA_CONFIRMADA",
    )

    # --------------------------------------------------------
    # EFICAZ
    # --------------------------------------------------------

    criar_validacao_eficacia(
        cursor=cursor,
        id_plano=id_plano,
        resultado="EFICAZ",
        criterio_validacao="Teste regressivo eficaz.",
        observacao=None,
        ator=ATOR,
    )

    cursor.execute(
        """
        SELECT
            StatusResolucao,
            TipoResolucao,
            ResolvidoPor
        FROM dbo.OcorrenciasDivergencia
        WHERE ID_Ocorrencia = ?
        """,
        ID_OCORRENCIA,
    )

    status, tipo, resolvido_por = cursor.fetchone()

    validar(
        "EFICAZ encerra por eficacia",
        status == "RESOLVIDA_EFICACIA"
        and tipo == "EFICACIA"
        and resolvido_por == ATOR,
    )

finally:
    conn.rollback()
    cursor.close()
    conn.close()

    print()
    print("=" * 70)
    print(f"RESULTADO: PASS {passou} | FAIL {falhou}")
    print("ROLLBACK: EXECUTADO")
    print("=" * 70)

    if falhou:
        raise SystemExit(1)
