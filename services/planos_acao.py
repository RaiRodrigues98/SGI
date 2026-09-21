from domain.exceptions import (
    BusinessRuleViolation,
    ConflictError,
    InvalidStateError,
    NotFoundError,
)


def _txt(valor):
    if valor is None:
        return None
    return str(valor).strip()


def _id_positivo(valor, nome):
    try:
        valor = int(valor)
    except (TypeError, ValueError):
        raise BusinessRuleViolation(f"{nome} invÃ¡lido.")
    if valor <= 0:
        raise BusinessRuleViolation(f"{nome} invÃ¡lido.")
    return valor


def _obrigatorio(valor, nome, limite):
    texto = _txt(valor)
    if not texto:
        raise BusinessRuleViolation(f"{nome} Ã© obrigatÃ³rio.")
    if len(texto) > limite:
        raise BusinessRuleViolation(
            f"{nome} deve possuir no mÃ¡ximo {limite} caracteres."
        )
    return texto


def _opcional(valor, nome, limite):
    texto = _txt(valor)
    if not texto:
        return None
    if len(texto) > limite:
        raise BusinessRuleViolation(
            f"{nome} deve possuir no mÃ¡ximo {limite} caracteres."
        )
    return texto


def _dict_row(cursor, row):
    if row is None:
        return None
    return dict(zip((c[0] for c in cursor.description), row))


def _buscar_analise(cursor, id_analise, bloquear=False):
    hint = " WITH (UPDLOCK, HOLDLOCK)" if bloquear else ""
    cursor.execute(
        f"""
        SELECT
            ID_Analise AS id_analise,
            ID_Ocorrencia AS id_ocorrencia,
            CategoriaCausa AS categoria_causa,
            CausaRaiz AS causa_raiz,
            Observacao AS observacao,
            Status AS status,
            AnalisadoPor AS analisado_por,
            DataHoraAnalise AS data_hora_analise,
            DataHoraCriacao AS data_hora_criacao,
            DataHoraAtualizacao AS data_hora_atualizacao,
            AtualizadoPor AS atualizado_por,
            EncerradoPor AS encerrado_por,
            DataHoraEncerramento AS data_hora_encerramento
        FROM dbo.AnalisesOcorrencia{hint}
        WHERE ID_Analise = ?
        """,
        id_analise,
    )
    return _dict_row(cursor, cursor.fetchone())


def criar_analise_ocorrencia(
    cursor, id_ocorrencia, categoria_causa, causa_raiz, observacao, ator
):
    id_ocorrencia = _id_positivo(id_ocorrencia, "ID da ocorrÃªncia")
    categoria_causa = _obrigatorio(categoria_causa, "Categoria da causa", 50)
    causa_raiz = _obrigatorio(causa_raiz, "Causa raiz", 2000)
    observacao = _opcional(observacao, "ObservaÃ§Ã£o", 2000)
    ator = _obrigatorio(ator, "UsuÃ¡rio autenticado", 100)

    # O lock na ocorrÃªncia serializa a criaÃ§Ã£o por ID_Ocorrencia.
    cursor.execute(
        """
        SELECT ID_Ocorrencia
        FROM dbo.OcorrenciasDivergencia WITH (UPDLOCK, HOLDLOCK)
        WHERE ID_Ocorrencia = ?
        """,
        id_ocorrencia,
    )
    if cursor.fetchone() is None:
        raise NotFoundError("OcorrÃªncia nÃ£o encontrada.")

    cursor.execute(
        """
        SELECT ID_Analise
        FROM dbo.AnalisesOcorrencia WITH (UPDLOCK, HOLDLOCK)
        WHERE ID_Ocorrencia = ?
          AND Status = 'ATIVA'
        """,
        id_ocorrencia,
    )
    if cursor.fetchone() is not None:
        raise ConflictError("A ocorrÃªncia jÃ¡ possui uma anÃ¡lise ativa.")

    cursor.execute(
        """
        INSERT INTO dbo.AnalisesOcorrencia
        (
            ID_Ocorrencia,
            CategoriaCausa,
            CausaRaiz,
            Observacao,
            Status,
            AnalisadoPor,
            DataHoraAnalise,
            DataHoraCriacao
        )
        OUTPUT INSERTED.ID_Analise
        VALUES (?, ?, ?, ?, 'ATIVA', ?, SYSDATETIME(), SYSDATETIME())
        """,
        id_ocorrencia,
        categoria_causa,
        causa_raiz,
        observacao,
        ator,
    )
    id_analise = cursor.fetchone()[0]
    return _buscar_analise(cursor, id_analise)


def consultar_analise_ocorrencia(cursor, id_ocorrencia):
    id_ocorrencia = _id_positivo(id_ocorrencia, "ID da ocorrÃªncia")

    cursor.execute(
        """
        SELECT ID_Ocorrencia
        FROM dbo.OcorrenciasDivergencia
        WHERE ID_Ocorrencia = ?
        """,
        id_ocorrencia,
    )
    if cursor.fetchone() is None:
        raise NotFoundError("OcorrÃªncia nÃ£o encontrada.")

    cursor.execute(
        """
        SELECT TOP (1)
            ID_Analise AS id_analise,
            ID_Ocorrencia AS id_ocorrencia,
            CategoriaCausa AS categoria_causa,
            CausaRaiz AS causa_raiz,
            Observacao AS observacao,
            Status AS status,
            AnalisadoPor AS analisado_por,
            DataHoraAnalise AS data_hora_analise,
            DataHoraCriacao AS data_hora_criacao,
            DataHoraAtualizacao AS data_hora_atualizacao,
            AtualizadoPor AS atualizado_por,
            EncerradoPor AS encerrado_por,
            DataHoraEncerramento AS data_hora_encerramento
        FROM dbo.AnalisesOcorrencia
        WHERE ID_Ocorrencia = ?
        ORDER BY
            CASE WHEN Status = 'ATIVA' THEN 0 ELSE 1 END,
            ID_Analise DESC
        """,
        id_ocorrencia,
    )
    analise = _dict_row(cursor, cursor.fetchone())
    if analise is None:
        raise NotFoundError("AnÃ¡lise da ocorrÃªncia nÃ£o encontrada.")
    return analise


def atualizar_analise(
    cursor, id_analise, categoria_causa, causa_raiz, observacao, ator
):
    id_analise = _id_positivo(id_analise, "ID da anÃ¡lise")
    categoria_causa = _obrigatorio(categoria_causa, "Categoria da causa", 50)
    causa_raiz = _obrigatorio(causa_raiz, "Causa raiz", 2000)
    observacao = _opcional(observacao, "ObservaÃ§Ã£o", 2000)
    ator = _obrigatorio(ator, "UsuÃ¡rio autenticado", 100)

    atual = _buscar_analise(cursor, id_analise, bloquear=True)
    if atual is None:
        raise NotFoundError("AnÃ¡lise nÃ£o encontrada.")
    if atual["status"] != "ATIVA":
        raise InvalidStateError("Somente uma anÃ¡lise ativa pode ser alterada.")

    cursor.execute(
        """
        UPDATE dbo.AnalisesOcorrencia
        SET
            CategoriaCausa = ?,
            CausaRaiz = ?,
            Observacao = ?,
            AtualizadoPor = ?,
            DataHoraAtualizacao = SYSDATETIME()
        WHERE ID_Analise = ?
          AND Status = 'ATIVA'
        """,
        categoria_causa,
        causa_raiz,
        observacao,
        ator,
        id_analise,
    )
    if cursor.rowcount != 1:
        raise ConflictError("A anÃ¡lise foi alterada por outra operaÃ§Ã£o.")

    return _buscar_analise(cursor, id_analise)


def encerrar_analise(cursor, id_analise, ator):
    id_analise = _id_positivo(id_analise, "ID da anÃ¡lise")
    ator = _obrigatorio(ator, "UsuÃ¡rio autenticado", 100)

    atual = _buscar_analise(cursor, id_analise, bloquear=True)
    if atual is None:
        raise NotFoundError("AnÃ¡lise nÃ£o encontrada.")
    if atual["status"] != "ATIVA":
        raise InvalidStateError("A anÃ¡lise jÃ¡ estÃ¡ encerrada.")

    cursor.execute(
        """
        UPDATE dbo.AnalisesOcorrencia
        SET
            Status = 'ENCERRADA',
            AtualizadoPor = ?,
            DataHoraAtualizacao = SYSDATETIME(),
            EncerradoPor = ?,
            DataHoraEncerramento = SYSDATETIME()
        WHERE ID_Analise = ?
          AND Status = 'ATIVA'
        """,
        ator,
        ator,
        id_analise,
    )
    if cursor.rowcount != 1:
        raise ConflictError("A anÃ¡lise foi alterada por outra operaÃ§Ã£o.")

    return _buscar_analise(cursor, id_analise)

# FASE 13.12.3B.2 - PLANOS DE ACAO
from datetime import date as _b2_date

_B2_PRIORIDADES = {"BAIXA", "MEDIA", "ALTA", "CRITICA"}
_B2_STATUS = {"ABERTO", "EM_ANDAMENTO", "CONCLUIDO", "CANCELADO"}
_B2_STATUS_EDITAVEIS = {"ABERTO", "EM_ANDAMENTO", "CANCELADO"}


def _b2_id(valor, campo):
    try:
        numero = int(valor)
    except (TypeError, ValueError):
        raise BusinessRuleViolation(f"{campo} deve ser um inteiro positivo.")
    if numero <= 0:
        raise BusinessRuleViolation(f"{campo} deve ser um inteiro positivo.")
    return numero


def _b2_req(valor, campo, limite):
    texto = "" if valor is None else str(valor).strip()
    if not texto:
        raise BusinessRuleViolation(f"{campo} e obrigatorio.")
    if len(texto) > limite:
        raise BusinessRuleViolation(f"{campo} excede {limite} caracteres.")
    return texto


def _b2_opt(valor, campo, limite):
    if valor is None:
        return None
    texto = str(valor).strip()
    if not texto:
        return None
    if len(texto) > limite:
        raise BusinessRuleViolation(f"{campo} excede {limite} caracteres.")
    return texto


def _b2_prazo(valor):
    if isinstance(valor, _b2_date):
        return valor
    texto = "" if valor is None else str(valor).strip()
    if not texto:
        raise BusinessRuleViolation("DataPrazo e obrigatoria.")
    try:
        return _b2_date.fromisoformat(texto)
    except ValueError:
        raise BusinessRuleViolation("DataPrazo deve estar no formato YYYY-MM-DD.")


def _b2_prioridade(valor):
    valor = _b2_req(valor, "Prioridade", 20).upper()
    if valor not in _B2_PRIORIDADES:
        raise BusinessRuleViolation("Prioridade deve ser BAIXA, MEDIA, ALTA ou CRITICA.")
    return valor


def _b2_status(valor):
    valor = _b2_req(valor, "Status", 20).upper()
    if valor not in _B2_STATUS:
        raise BusinessRuleViolation("Status invalido.")
    return valor


def _b2_dict(cursor, row):
    if row is None:
        return None
    return {d[0]: v for d, v in zip(cursor.description, row)}


def _b2_validar_analise(cursor, id_analise):
    id_analise = _b2_id(id_analise, "ID_Analise")
    cursor.execute("SELECT ID_Analise FROM dbo.AnalisesOcorrencia WHERE ID_Analise = ?", id_analise)
    if cursor.fetchone() is None:
        raise NotFoundError("Analise de ocorrencia nao encontrada.")
    return id_analise


def _b2_buscar_plano(cursor, id_plano, bloquear=False):
    id_plano = _b2_id(id_plano, "ID_PlanoAcao")
    lock = " WITH (UPDLOCK, HOLDLOCK)" if bloquear else ""
    cursor.execute(f"""
        SELECT
            ID_PlanoAcao AS id_plano_acao,
            ID_Analise AS id_analise,
            DescricaoAcao AS descricao_acao,
            Responsavel AS responsavel,
            DataPrazo AS data_prazo,
            Prioridade AS prioridade,
            Status AS status,
            Observacao AS observacao,
            CriadoPor AS criado_por,
            DataHoraCriacao AS data_hora_criacao,
            AtualizadoPor AS atualizado_por,
            DataHoraAtualizacao AS data_hora_atualizacao,
            ConcluidoPor AS concluido_por,
            DataHoraConclusao AS data_hora_conclusao
        FROM dbo.PlanosAcaoOcorrencia{lock}
        WHERE ID_PlanoAcao = ?
    """, id_plano)
    row = cursor.fetchone()
    if row is None:
        raise NotFoundError("Plano de acao nao encontrado.")
    return _b2_dict(cursor, row)


def criar_plano_acao(cursor, id_analise, descricao_acao, responsavel, data_prazo, prioridade, observacao, ator):
    id_analise = _b2_validar_analise(cursor, id_analise)
    descricao_acao = _b2_req(descricao_acao, "DescricaoAcao", 2000)
    responsavel = _b2_req(responsavel, "Responsavel", 100)
    data_prazo = _b2_prazo(data_prazo)
    prioridade = _b2_prioridade(prioridade)
    observacao = _b2_opt(observacao, "Observacao", 2000)
    ator = _b2_req(ator, "CriadoPor", 100)

    cursor.execute("""
        INSERT INTO dbo.PlanosAcaoOcorrencia
        (ID_Analise, DescricaoAcao, Responsavel, DataPrazo, Prioridade, Status, Observacao, CriadoPor, DataHoraCriacao)
        OUTPUT inserted.ID_PlanoAcao
        VALUES (?, ?, ?, ?, ?, 'ABERTO', ?, ?, SYSDATETIME())
    """, id_analise, descricao_acao, responsavel, data_prazo, prioridade, observacao, ator)

    row = cursor.fetchone()
    if row is None:
        raise ConflictError("Nao foi possivel criar o plano de acao.")
    return _b2_buscar_plano(cursor, int(row[0]))


def listar_planos_acao(cursor, id_analise):
    id_analise = _b2_validar_analise(cursor, id_analise)
    cursor.execute("""
        SELECT
            ID_PlanoAcao AS id_plano_acao,
            ID_Analise AS id_analise,
            DescricaoAcao AS descricao_acao,
            Responsavel AS responsavel,
            DataPrazo AS data_prazo,
            Prioridade AS prioridade,
            Status AS status,
            Observacao AS observacao,
            CriadoPor AS criado_por,
            DataHoraCriacao AS data_hora_criacao,
            AtualizadoPor AS atualizado_por,
            DataHoraAtualizacao AS data_hora_atualizacao,
            ConcluidoPor AS concluido_por,
            DataHoraConclusao AS data_hora_conclusao
        FROM dbo.PlanosAcaoOcorrencia
        WHERE ID_Analise = ?
        ORDER BY DataPrazo, ID_PlanoAcao
    """, id_analise)
    return [_b2_dict(cursor, row) for row in cursor.fetchall()]


def consultar_plano_acao(cursor, id_plano):
    return _b2_buscar_plano(cursor, id_plano)


def atualizar_plano_acao(cursor, id_plano, descricao_acao, responsavel, data_prazo, prioridade, status, observacao, ator):
    id_plano = _b2_id(id_plano, "ID_PlanoAcao")
    atual = _b2_buscar_plano(cursor, id_plano, bloquear=True)
    atual_status = str(atual["status"]).strip().upper()

    if atual_status in {"CONCLUIDO", "CANCELADO"}:
        raise InvalidStateError(f"Plano de acao {atual_status} nao pode ser alterado.")

    descricao_acao = _b2_req(descricao_acao, "DescricaoAcao", 2000)
    responsavel = _b2_req(responsavel, "Responsavel", 100)
    data_prazo = _b2_prazo(data_prazo)
    prioridade = _b2_prioridade(prioridade)
    novo_status = _b2_status(status)
    observacao = _b2_opt(observacao, "Observacao", 2000)
    ator = _b2_req(ator, "AtualizadoPor", 100)

    if novo_status == "CONCLUIDO":
        raise BusinessRuleViolation("Use o endpoint de conclusao para concluir o plano de acao.")
    if novo_status not in _B2_STATUS_EDITAVEIS:
        raise BusinessRuleViolation("Status de atualizacao invalido.")

    cursor.execute("""
        UPDATE dbo.PlanosAcaoOcorrencia
        SET DescricaoAcao = ?, Responsavel = ?, DataPrazo = ?, Prioridade = ?, Status = ?,
            Observacao = ?, AtualizadoPor = ?, DataHoraAtualizacao = SYSDATETIME()
        WHERE ID_PlanoAcao = ?
    """, descricao_acao, responsavel, data_prazo, prioridade, novo_status, observacao, ator, id_plano)

    if cursor.rowcount != 1:
        raise ConflictError("Plano de acao nao foi atualizado.")
    return _b2_buscar_plano(cursor, id_plano)


def concluir_plano_acao(cursor, id_plano, ator):
    id_plano = _b2_id(id_plano, "ID_PlanoAcao")
    atual = _b2_buscar_plano(cursor, id_plano, bloquear=True)
    status = str(atual["status"]).strip().upper()

    if status == "CONCLUIDO":
        raise InvalidStateError("Plano de acao ja esta concluido.")
    if status == "CANCELADO":
        raise InvalidStateError("Plano de acao cancelado nao pode ser concluido.")
    if status not in {"ABERTO", "EM_ANDAMENTO"}:
        raise InvalidStateError(f"Plano de acao em status {status} nao pode ser concluido.")

    ator = _b2_req(ator, "ConcluidoPor", 100)
    cursor.execute("""
        UPDATE dbo.PlanosAcaoOcorrencia
        SET Status = 'CONCLUIDO', AtualizadoPor = ?, DataHoraAtualizacao = SYSDATETIME(),
            ConcluidoPor = ?, DataHoraConclusao = SYSDATETIME()
        WHERE ID_PlanoAcao = ?
    """, ator, ator, id_plano)

    if cursor.rowcount != 1:
        raise ConflictError("Plano de acao nao foi concluido.")
    return _b2_buscar_plano(cursor, id_plano)

# FASE 13.12.3B.3 - EVIDENCIAS


def _b3_buscar_evidencia(cursor, id_evidencia, bloquear=False):
    id_evidencia = _b2_id(id_evidencia, "ID_Evidencia")
    lock = " WITH (UPDLOCK, HOLDLOCK)" if bloquear else ""

    cursor.execute(
        f"""
        SELECT
            ID_Evidencia AS id_evidencia,
            ID_PlanoAcao AS id_plano_acao,
            TipoEvidencia AS tipo_evidencia,
            Descricao AS descricao,
            ReferenciaArquivo AS referencia_arquivo,
            CriadoPor AS criado_por,
            DataHoraCriacao AS data_hora_criacao
        FROM dbo.PlanoAcaoEvidencias{lock}
        WHERE ID_Evidencia = ?
        """,
        id_evidencia,
    )

    row = cursor.fetchone()

    if row is None:
        raise NotFoundError("Evidencia nao encontrada.")

    return _b2_dict(cursor, row)


def criar_evidencia_plano(
    cursor,
    id_plano,
    tipo_evidencia,
    descricao,
    referencia_arquivo,
    ator,
):
    id_plano = _b2_id(id_plano, "ID_PlanoAcao")
    _b2_buscar_plano(cursor, id_plano)

    tipo_evidencia = _b2_req(
        tipo_evidencia,
        "TipoEvidencia",
        30,
    )
    descricao = _b2_opt(
        descricao,
        "Descricao",
        1000,
    )
    referencia_arquivo = _b2_opt(
        referencia_arquivo,
        "ReferenciaArquivo",
        1000,
    )
    ator = _b2_req(ator, "CriadoPor", 100)

    if descricao is None and referencia_arquivo is None:
        raise BusinessRuleViolation(
            "Informe Descricao ou ReferenciaArquivo."
        )

    cursor.execute(
        """
        INSERT INTO dbo.PlanoAcaoEvidencias
        (
            ID_PlanoAcao,
            TipoEvidencia,
            Descricao,
            ReferenciaArquivo,
            CriadoPor,
            DataHoraCriacao
        )
        OUTPUT inserted.ID_Evidencia
        VALUES
        (
            ?,
            ?,
            ?,
            ?,
            ?,
            SYSDATETIME()
        )
        """,
        id_plano,
        tipo_evidencia,
        descricao,
        referencia_arquivo,
        ator,
    )

    row = cursor.fetchone()

    if row is None:
        raise ConflictError("Nao foi possivel criar a evidencia.")

    return _b3_buscar_evidencia(cursor, int(row[0]))


def listar_evidencias_plano(cursor, id_plano):
    id_plano = _b2_id(id_plano, "ID_PlanoAcao")
    _b2_buscar_plano(cursor, id_plano)

    cursor.execute(
        """
        SELECT
            ID_Evidencia AS id_evidencia,
            ID_PlanoAcao AS id_plano_acao,
            TipoEvidencia AS tipo_evidencia,
            Descricao AS descricao,
            ReferenciaArquivo AS referencia_arquivo,
            CriadoPor AS criado_por,
            DataHoraCriacao AS data_hora_criacao
        FROM dbo.PlanoAcaoEvidencias
        WHERE ID_PlanoAcao = ?
        ORDER BY DataHoraCriacao DESC, ID_Evidencia DESC
        """,
        id_plano,
    )

    rows = cursor.fetchall()

    return [
        _b2_dict(cursor, row)
        for row in rows
    ]


def remover_evidencia_plano(cursor, id_evidencia):
    id_evidencia = _b2_id(id_evidencia, "ID_Evidencia")

    evidencia = _b3_buscar_evidencia(
        cursor,
        id_evidencia,
        bloquear=True,
    )

    cursor.execute(
        """
        DELETE FROM dbo.PlanoAcaoEvidencias
        WHERE ID_Evidencia = ?
        """,
        id_evidencia,
    )

    if cursor.rowcount != 1:
        raise ConflictError("Evidencia nao foi removida.")

    return evidencia

# ============================================================
# FASE 13.12.3B.4 - VALIDACAO DE EFICACIA
# ============================================================


def criar_validacao_eficacia(
    cursor,
    id_plano,
    resultado,
    criterio_validacao,
    observacao,
    ator,
):
    id_plano = _b2_id(id_plano, "ID_PlanoAcao")

    plano = _b2_buscar_plano(
        cursor,
        id_plano,
        bloquear=True,
    )

    status_plano = str(
        plano["status"]
    ).strip().upper()

    if status_plano != "CONCLUIDO":
        raise InvalidStateError(
            "Somente plano de acao CONCLUIDO pode receber validacao de eficacia."
        )

    resultado = _b2_req(
        resultado,
        "Resultado",
        20,
    ).upper()

    if resultado not in {"EFICAZ", "INEFICAZ"}:
        raise BusinessRuleViolation(
            "Resultado deve ser EFICAZ ou INEFICAZ."
        )

    criterio_validacao = _b2_req(
        criterio_validacao,
        "CriterioValidacao",
        2000,
    )

    observacao = _b2_opt(
        observacao,
        "Observacao",
        2000,
    )

    ator = _b2_req(
        ator,
        "ValidadoPor",
        100,
    )

    if resultado == "EFICAZ":
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM dbo.PlanosAcaoOcorrencia P
            INNER JOIN dbo.AnalisesOcorrencia A
                ON A.ID_Analise = P.ID_Analise
            WHERE A.ID_Ocorrencia = (
                SELECT ID_Ocorrencia
                FROM dbo.AnalisesOcorrencia
                WHERE ID_Analise = ?
            )
              AND P.ID_PlanoAcao <> ?
              AND P.Status IN ('ABERTO', 'EM_ANDAMENTO')
            """,
            plano["id_analise"],
            id_plano,
        )

        planos_ativos = int(cursor.fetchone()[0])

        if planos_ativos > 0:
            raise InvalidStateError(
                "Nao e possivel encerrar a tratativa: existem outros planos de acao ativos."
            )

    cursor.execute(
        """
        INSERT INTO dbo.ValidacoesEficaciaPlano
        (
            ID_PlanoAcao,
            Resultado,
            CriterioValidacao,
            Observacao,
            ValidadoPor,
            DataHoraValidacao,
            DataHoraCriacao
        )
        OUTPUT inserted.ID_ValidacaoEficacia
        VALUES
        (
            ?,
            ?,
            ?,
            ?,
            ?,
            SYSDATETIME(),
            SYSDATETIME()
        )
        """,
        id_plano,
        resultado,
        criterio_validacao,
        observacao,
        ator,
    )

    row = cursor.fetchone()

    if row is None:
        raise ConflictError(
            "Nao foi possivel registrar a validacao de eficacia."
        )

    id_validacao = int(row[0])

    if resultado == "EFICAZ":
        cursor.execute(
            """
            SELECT
                A.ID_Ocorrencia,
                O.StatusResolucao
            FROM dbo.AnalisesOcorrencia A
            INNER JOIN dbo.OcorrenciasDivergencia O
                ON O.ID_Ocorrencia = A.ID_Ocorrencia
            WHERE A.ID_Analise = ?
            """,
            plano["id_analise"],
        )

        ocorrencia = cursor.fetchone()

        if ocorrencia is None:
            raise NotFoundError(
                "Ocorrencia vinculada ao plano nao encontrada."
            )

        id_ocorrencia = int(ocorrencia[0])
        status_ocorrencia = str(
            ocorrencia[1] or ""
        ).strip().upper()

        if status_ocorrencia != "DIVERGENCIA_CONFIRMADA":
            raise InvalidStateError(
                "Somente ocorrencia com DIVERGENCIA_CONFIRMADA pode ser encerrada por eficacia."
            )

        from services.ocorrencias_divergencia import (
            resolver_ocorrencia_divergencia,
        )

        resolver_ocorrencia_divergencia(
            cursor=cursor,
            id_ocorrencia=id_ocorrencia,
            tipo_resolucao="EFICACIA",
            usuario=ator,
            observacao=(
                f"Encerrada apos validacao de eficacia do plano #{id_plano}."
            ),
        )

    cursor.execute(
        """
        SELECT
            ID_ValidacaoEficacia AS id_validacao_eficacia,
            ID_PlanoAcao AS id_plano_acao,
            Resultado AS resultado,
            CriterioValidacao AS criterio_validacao,
            Observacao AS observacao,
            ValidadoPor AS validado_por,
            DataHoraValidacao AS data_hora_validacao,
            DataHoraCriacao AS data_hora_criacao
        FROM dbo.ValidacoesEficaciaPlano
        WHERE ID_ValidacaoEficacia = ?
        """,
        id_validacao,
    )

    row = cursor.fetchone()

    if row is None:
        raise ConflictError(
            "Validacao criada, mas nao foi possivel consulta-la."
        )

    return _b2_dict(cursor, row)


def listar_validacoes_eficacia(
    cursor,
    id_plano,
):
    id_plano = _b2_id(
        id_plano,
        "ID_PlanoAcao",
    )

    _b2_buscar_plano(
        cursor,
        id_plano,
    )

    cursor.execute(
        """
        SELECT
            ID_ValidacaoEficacia AS id_validacao_eficacia,
            ID_PlanoAcao AS id_plano_acao,
            Resultado AS resultado,
            CriterioValidacao AS criterio_validacao,
            Observacao AS observacao,
            ValidadoPor AS validado_por,
            DataHoraValidacao AS data_hora_validacao,
            DataHoraCriacao AS data_hora_criacao
        FROM dbo.ValidacoesEficaciaPlano
        WHERE ID_PlanoAcao = ?
        ORDER BY
            DataHoraValidacao DESC,
            ID_ValidacaoEficacia DESC
        """,
        id_plano,
    )

    return [
        _b2_dict(cursor, row)
        for row in cursor.fetchall()
    ]


# ============================================================
# FASE 13.12.4A - CONSULTA DE OCORRENCIAS PARA TRATATIVAS
# ============================================================

def listar_ocorrencias_tratativas(
    cursor,
    cliente_id=None,
    id_inventario=None,
    status=None,
    localizacao=None,
    codigo=None,
    somente_pendentes=True,
    page=1,
    page_size=50,
):
    try:
        page = int(page)
        page_size = int(page_size)
    except (TypeError, ValueError):
        raise BusinessRuleViolation("Paginacao invalida.")

    if page < 1:
        raise BusinessRuleViolation("Page deve ser maior ou igual a 1.")

    if page_size < 1 or page_size > 100:
        raise BusinessRuleViolation(
            "PageSize deve estar entre 1 e 100."
        )

    # Tratativas pertencem exclusivamente ao inventario ROTATIVO.
    filtros = [
        "UPPER(LTRIM(RTRIM(O.TipoInventario))) = 'ROTATIVO'"
    ]
    parametros = []

    if cliente_id is not None:
        cliente_id = _b2_id(cliente_id, "ClienteId")
        filtros.append("O.ClienteId = ?")
        parametros.append(cliente_id)

    if id_inventario is not None:
        id_inventario = _b2_id(
            id_inventario,
            "ID_Inventario",
        )
        filtros.append("O.ID_Inventario = ?")
        parametros.append(id_inventario)

    status = _b2_opt(status, "Status", 30)

    if status:
        status = status.upper()
        filtros.append(
            "UPPER(LTRIM(RTRIM(O.StatusResolucao))) = ?"
        )
        parametros.append(status)

    localizacao = _b2_opt(localizacao, "Localizacao", 100)

    if localizacao:
        filtros.append(
            "UPPER(LTRIM(RTRIM(ISNULL(O.Localizacao, '')))) = ?"
        )
        parametros.append(localizacao.upper())

    codigo = _b2_opt(codigo, "Codigo", 100)

    if codigo:
        filtros.append(
            "UPPER(LTRIM(RTRIM(O.Codigo))) = ?"
        )
        parametros.append(codigo.upper())

    if somente_pendentes:
        filtros.append(
            "O.DataHoraResolucao IS NULL"
        )

    where_sql = ""

    if filtros:
        where_sql = "WHERE " + " AND ".join(filtros)

    cursor.execute(
        f"""
        SELECT COUNT(*)
        FROM dbo.OcorrenciasDivergencia O
        {where_sql}
        """,
        tuple(parametros),
    )

    total_registros = int(
        cursor.fetchone()[0]
    )

    total_paginas = (
        (total_registros + page_size - 1)
        // page_size
        if total_registros
        else 0
    )

    offset = (page - 1) * page_size

    consulta_parametros = list(parametros)
    consulta_parametros.extend(
        [offset, page_size]
    )

    cursor.execute(
        f"""
        SELECT
            O.ID_Ocorrencia AS id_ocorrencia,
            O.ClienteId AS cliente_id,
            O.ID_Inventario AS id_inventario,
            O.ID_Rodada AS id_rodada,
            O.TipoInventario AS tipo_inventario,
            O.Localizacao AS localizacao,
            O.Codigo AS codigo,
            O.Lote AS lote,
            O.QtdEstoque AS qtd_estoque,
            O.QtdContada AS qtd_contada,
            O.Diferenca AS diferenca,
            O.TipoDivergencia AS tipo_divergencia,
            O.SubtipoDivergencia AS subtipo_divergencia,
            O.StatusResolucao AS status_resolucao,
            O.Justificativa AS justificativa,
            O.TipoResolucao AS tipo_resolucao,
            O.ObservacaoResolucao AS observacao_resolucao,
            O.CriadoPor AS criado_por,
            O.DataHoraCriacao AS data_hora_criacao,
            O.ResolvidoPor AS resolvido_por,
            O.DataHoraResolucao AS data_hora_resolucao

        FROM dbo.OcorrenciasDivergencia O

        {where_sql}

        ORDER BY
            O.DataHoraCriacao DESC,
            O.ID_Ocorrencia DESC

        OFFSET ? ROWS
        FETCH NEXT ? ROWS ONLY
        """,
        tuple(consulta_parametros),
    )

    ocorrencias = [
        _b2_dict(cursor, row)
        for row in cursor.fetchall()
    ]

    return {
        "filtros": {
            "cliente_id": cliente_id,
            "id_inventario": id_inventario,
            "status": status,
            "localizacao": localizacao,
            "codigo": codigo,
            "somente_pendentes": bool(
                somente_pendentes
            ),
        },
        "paginacao": {
            "page": page,
            "page_size": page_size,
            "total_registros": total_registros,
            "total_paginas": total_paginas,
            "registros_pagina": len(
                ocorrencias
            ),
            "tem_anterior": page > 1,
            "tem_proxima": (
                page < total_paginas
            ),
        },
        "ocorrencias": ocorrencias,
    }
