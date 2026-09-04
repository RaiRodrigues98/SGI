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
