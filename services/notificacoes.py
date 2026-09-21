from domain.exceptions import NotFoundError


def _serializar(linha):
    return {
        "id_notificacao": linha.ID_Notificacao,
        "tipo": linha.Tipo,
        "titulo": linha.Titulo,
        "mensagem": linha.Mensagem,
        "prioridade": linha.Prioridade,
        "entidade_tipo": linha.EntidadeTipo,
        "entidade_id": linha.EntidadeId,
        "id_inventario": linha.ID_Inventario,
        "url": linha.URL,
        "lida": bool(linha.Lida),
        "data_leitura": linha.DataLeitura,
        "data_criacao": linha.DataCriacao,
        "id_usuario_ator": linha.ID_UsuarioAtor,
        "nome_usuario_ator": linha.NomeUsuarioAtor,
    }


def criar_por_permissao(
    cursor,
    codigo_permissao: str,
    id_usuario_ator: int | None,
    tipo: str,
    titulo: str,
    mensagem: str,
    prioridade: str,
    entidade_tipo: str | None,
    entidade_id: int | None,
    id_inventario: int | None,
    url: str | None,
    chave_dedupe: str,
    excluir_ator: bool = True,
):
    codigo_permissao = codigo_permissao.strip().upper()

    sql_exclusao = ""
    parametros = [codigo_permissao]

    if excluir_ator and id_usuario_ator:
        sql_exclusao = "AND U.ID_Usuario <> ?"
        parametros.append(id_usuario_ator)

    cursor.execute(
        f"""
        SELECT DISTINCT U.ID_Usuario
        FROM dbo.Usuarios U
        INNER JOIN dbo.UsuarioPerfis UP
            ON UP.ID_Usuario = U.ID_Usuario
           AND UP.Ativo = 1
        INNER JOIN dbo.Perfis P
            ON P.ID_Perfil = UP.ID_Perfil
           AND P.Ativo = 1
        INNER JOIN dbo.PerfilPermissoes PP
            ON PP.ID_Perfil = P.ID_Perfil
        INNER JOIN dbo.Permissoes PE
            ON PE.ID_Permissao = PP.ID_Permissao
           AND PE.Ativo = 1
        WHERE
            U.Ativo = 1
            AND PE.Codigo = ?
            {sql_exclusao}
        """,
        tuple(parametros),
    )

    destinatarios = [
        int(linha.ID_Usuario)
        for linha in cursor.fetchall()
    ]

    criadas = 0

    for id_destinatario in destinatarios:
        cursor.execute(
            """
            INSERT INTO dbo.Notificacoes
            (
                ID_UsuarioDestinatario,
                ID_UsuarioAtor,
                Tipo,
                Titulo,
                Mensagem,
                Prioridade,
                EntidadeTipo,
                EntidadeId,
                ID_Inventario,
                URL,
                ChaveDedupe
            )
            SELECT
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            WHERE NOT EXISTS
            (
                SELECT 1
                FROM dbo.Notificacoes WITH (UPDLOCK, HOLDLOCK)
                WHERE
                    ID_UsuarioDestinatario = ?
                    AND ChaveDedupe = ?
            )
            """,
            (
                id_destinatario,
                id_usuario_ator,
                tipo,
                titulo,
                mensagem,
                prioridade,
                entidade_tipo,
                entidade_id,
                id_inventario,
                url,
                chave_dedupe,
                id_destinatario,
                chave_dedupe,
            ),
        )

        if cursor.rowcount > 0:
            criadas += 1

    return {
        "destinatarios_localizados": len(destinatarios),
        "notificacoes_criadas": criadas,
    }


def listar(
    cursor,
    id_usuario: int,
    somente_nao_lidas: bool = False,
    limite: int = 30,
):
    limite = max(1, min(int(limite), 100))

    filtro = "AND N.Lida = 0" if somente_nao_lidas else ""

    cursor.execute(
        f"""
        SELECT TOP ({limite})
            N.ID_Notificacao,
            N.Tipo,
            N.Titulo,
            N.Mensagem,
            N.Prioridade,
            N.EntidadeTipo,
            N.EntidadeId,
            N.ID_Inventario,
            N.URL,
            N.Lida,
            N.DataLeitura,
            N.DataCriacao,
            N.ID_UsuarioAtor,
            UA.Nome AS NomeUsuarioAtor
        FROM dbo.Notificacoes N
        LEFT JOIN dbo.Usuarios UA
            ON UA.ID_Usuario = N.ID_UsuarioAtor
        WHERE
            N.ID_UsuarioDestinatario = ?
            {filtro}
        ORDER BY
            N.Lida ASC,
            N.DataCriacao DESC,
            N.ID_Notificacao DESC
        """,
        id_usuario,
    )

    return [
        _serializar(linha)
        for linha in cursor.fetchall()
    ]


def contar_nao_lidas(cursor, id_usuario: int):
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM dbo.Notificacoes
        WHERE
            ID_UsuarioDestinatario = ?
            AND Lida = 0
        """,
        id_usuario,
    )

    return int(cursor.fetchone()[0])


def marcar_como_lida(
    cursor,
    id_notificacao: int,
    id_usuario: int,
):
    cursor.execute(
        """
        UPDATE dbo.Notificacoes
        SET
            Lida = 1,
            DataLeitura = COALESCE(DataLeitura, SYSDATETIME())
        WHERE
            ID_Notificacao = ?
            AND ID_UsuarioDestinatario = ?
        """,
        (id_notificacao, id_usuario),
    )

    if cursor.rowcount == 0:
        raise NotFoundError("Notificação não encontrada.")

    return {
        "sucesso": True,
        "id_notificacao": id_notificacao,
    }


def marcar_todas_como_lidas(cursor, id_usuario: int):
    cursor.execute(
        """
        UPDATE dbo.Notificacoes
        SET
            Lida = 1,
            DataLeitura = SYSDATETIME()
        WHERE
            ID_UsuarioDestinatario = ?
            AND Lida = 0
        """,
        id_usuario,
    )

    return {
        "sucesso": True,
        "quantidade_atualizada": max(cursor.rowcount, 0),
    }
