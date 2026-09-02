from domain.exceptions import (
    BusinessRuleViolation,
    ConflictError,
    NotFoundError,
)

from application.exceptions import ApplicationError

from services.seguranca import (
    gerar_hash_senha,
)


# ============================================================
# NORMALIZAÇÃO
# ============================================================

def _texto(valor):

    if valor is None:
        return ""

    return str(valor).strip()


def _login(valor):

    return (
        _texto(valor)
        .lower()
    )


def _email(valor):

    valor = _texto(valor)

    if not valor:
        return None

    return valor.lower()


# ============================================================
# SERIALIZAR USUÁRIO
#
# IMPORTANTE:
# SenhaHash nunca é retornada.
# ============================================================

def _usuario_dict(linha):

    return {
        "id_usuario":
            linha.ID_Usuario,

        "nome":
            linha.Nome,

        "login":
            linha.Login,

        "email":
            linha.Email,

        "ativo":
            bool(
                linha.Ativo
            ),

        "data_hora_criacao":
            linha.DataHoraCriacao,

        "data_hora_atualizacao":
            linha.DataHoraAtualizacao,

        "ultimo_login":
            linha.UltimoLogin
    }


# ============================================================
# CRIAR USUÁRIO
# ============================================================

def criar_usuario(
    cursor,
    nome: str,
    login: str,
    email: str | None,
    senha: str,
    ativo: bool = True
):

    nome = _texto(
        nome
    )

    login = _login(
        login
    )

    email = _email(
        email
    )

    senha = (
        str(senha)
        if senha is not None
        else ""
    )

    if not nome:

        raise BusinessRuleViolation(
            "Nome obrigatório."
        )

    if not login:

        raise BusinessRuleViolation(
            "Login obrigatório."
        )

    if not senha:

        raise BusinessRuleViolation(
            "Senha obrigatória."
        )

    # ========================================================
    # LOGIN DUPLICADO
    # ========================================================

    cursor.execute(
        """
        SELECT TOP 1
            ID_Usuario

        FROM dbo.Usuarios

        WHERE
            LOWER(
                LTRIM(
                    RTRIM(Login)
                )
            ) = ?
        """,
        login
    )

    if cursor.fetchone():

        raise ConflictError(
            "Já existe um usuário com este login."
        )

    # ========================================================
    # EMAIL DUPLICADO
    # ========================================================

    if email:

        cursor.execute(
            """
            SELECT TOP 1
                ID_Usuario

            FROM dbo.Usuarios

            WHERE
                Email IS NOT NULL

                AND LOWER(
                    LTRIM(
                        RTRIM(Email)
                    )
                ) = ?
            """,
            email
        )

        if cursor.fetchone():

            raise ConflictError(
                "Já existe um usuário com este e-mail."
            )

    # ========================================================
    # HASH DA SENHA
    # ========================================================

    try:

        senha_hash = gerar_hash_senha(
            senha
        )

    except Exception as erro:

        raise ApplicationError(
            "Não foi possível processar "
            f"a senha: {erro}"
        )

    # ========================================================
    # INSERT
    # ========================================================

    cursor.execute(
        """
        INSERT INTO dbo.Usuarios
        (
            Nome,
            Login,
            Email,
            SenhaHash,
            Ativo
        )

        OUTPUT
            INSERTED.ID_Usuario,
            INSERTED.Nome,
            INSERTED.Login,
            INSERTED.Email,
            INSERTED.Ativo,
            INSERTED.DataHoraCriacao,
            INSERTED.DataHoraAtualizacao,
            INSERTED.UltimoLogin

        VALUES
        (
            ?,
            ?,
            ?,
            ?,
            ?
        )
        """,
        (
            nome,
            login,
            email,
            senha_hash,
            ativo
        )
    )

    usuario = (
        cursor.fetchone()
    )

    return {
        "sucesso":
            True,

        "mensagem":
            "Usuário criado com sucesso.",

        "usuario":
            _usuario_dict(
                usuario
            )
    }


# ============================================================
# LISTAR USUÁRIOS
# ============================================================

def listar_usuarios(
    cursor,
    ativo: bool | None = None
):

    filtros = []
    parametros = []

    if ativo is not None:

        filtros.append(
            "U.Ativo = ?"
        )

        parametros.append(
            ativo
        )

    where = ""

    if filtros:

        where = (
            "WHERE "
            +
            " AND ".join(
                filtros
            )
        )

    cursor.execute(
        f"""
        SELECT
            U.ID_Usuario,
            U.Nome,
            U.Login,
            U.Email,
            U.Ativo,
            U.DataHoraCriacao,
            U.DataHoraAtualizacao,
            U.UltimoLogin

        FROM dbo.Usuarios U

        {where}

        ORDER BY
            U.Nome,
            U.ID_Usuario
        """,
        tuple(
            parametros
        )
    )

    linhas = (
        cursor.fetchall()
    )

    return [
        _usuario_dict(
            linha
        )
        for linha in linhas
    ]


# ============================================================
# CONSULTAR USUÁRIO
# ============================================================

def consultar_usuario(
    cursor,
    id_usuario: int
):

    if id_usuario <= 0:

        raise BusinessRuleViolation(
            "Usuário inválido."
        )

    cursor.execute(
        """
        SELECT
            ID_Usuario,
            Nome,
            Login,
            Email,
            Ativo,
            DataHoraCriacao,
            DataHoraAtualizacao,
            UltimoLogin

        FROM dbo.Usuarios

        WHERE ID_Usuario = ?
        """,
        id_usuario
    )

    usuario = (
        cursor.fetchone()
    )

    if not usuario:

        raise NotFoundError(
            "Usuário não encontrado."
        )

    return _usuario_dict(
        usuario
    )


# ============================================================
# ATUALIZAR USUÁRIO
# ============================================================

def atualizar_usuario(
    cursor,
    id_usuario: int,
    nome: str,
    email: str | None,
    ativo: bool
):

    if id_usuario <= 0:

        raise BusinessRuleViolation(
            "Usuário inválido."
        )

    nome = _texto(
        nome
    )

    email = _email(
        email
    )

    if not nome:

        raise BusinessRuleViolation(
            "Nome obrigatório."
        )

    # ========================================================
    # USUÁRIO EXISTE?
    # ========================================================

    cursor.execute(
        """
        SELECT TOP 1
            ID_Usuario

        FROM dbo.Usuarios

        WHERE ID_Usuario = ?
        """,
        id_usuario
    )

    if not cursor.fetchone():

        raise NotFoundError(
            "Usuário não encontrado."
        )

    # ========================================================
    # EMAIL DUPLICADO EM OUTRO USUÁRIO
    # ========================================================

    if email:

        cursor.execute(
            """
            SELECT TOP 1
                ID_Usuario

            FROM dbo.Usuarios

            WHERE
                ID_Usuario <> ?

                AND Email IS NOT NULL

                AND LOWER(
                    LTRIM(
                        RTRIM(Email)
                    )
                ) = ?
            """,
            (
                id_usuario,
                email
            )
        )

        if cursor.fetchone():

            raise ConflictError(
                "Já existe outro usuário com este e-mail."
            )

    # ========================================================
    # UPDATE
    # ========================================================

    cursor.execute(
        """
        UPDATE dbo.Usuarios

        SET
            Nome = ?,
            Email = ?,
            Ativo = ?,
            DataHoraAtualizacao =
                SYSDATETIME()

        WHERE ID_Usuario = ?
        """,
        (
            nome,
            email,
            ativo,
            id_usuario
        )
    )

    if cursor.rowcount == 0:

        raise BusinessRuleViolation(
            "Não foi possível atualizar o usuário."
        )

    return {
        "sucesso":
            True,

        "mensagem":
            "Usuário atualizado com sucesso.",

        "usuario":
            consultar_usuario(
                cursor=cursor,
                id_usuario=id_usuario
            )
    }


# ============================================================
# ALTERAR SENHA
# ============================================================

def alterar_senha_usuario(
    cursor,
    id_usuario: int,
    nova_senha: str
):

    if id_usuario <= 0:

        raise BusinessRuleViolation(
            "Usuário inválido."
        )

    nova_senha = (
        str(nova_senha)
        if nova_senha is not None
        else ""
    )

    if not nova_senha:

        raise BusinessRuleViolation(
            "Nova senha obrigatória."
        )

    # ========================================================
    # USUÁRIO EXISTE?
    # ========================================================

    cursor.execute(
        """
        SELECT TOP 1
            ID_Usuario

        FROM dbo.Usuarios

        WHERE ID_Usuario = ?
        """,
        id_usuario
    )

    if not cursor.fetchone():

        raise NotFoundError(
            "Usuário não encontrado."
        )

    # ========================================================
    # NOVO HASH
    # ========================================================

    senha_hash = (
        gerar_hash_senha(
            nova_senha
        )
    )

    cursor.execute(
        """
        UPDATE dbo.Usuarios

        SET
            SenhaHash = ?,
            DataHoraAtualizacao =
                SYSDATETIME()

        WHERE ID_Usuario = ?
        """,
        (
            senha_hash,
            id_usuario
        )
    )

    return {
        "sucesso":
            True,

        "id_usuario":
            id_usuario,

        "mensagem":
            "Senha alterada com sucesso."
    }


# ============================================================
# LISTAR PERFIS DO USUÁRIO
# ============================================================

def listar_perfis_usuario(
    cursor,
    id_usuario: int
):

    consultar_usuario(
        cursor=cursor,
        id_usuario=id_usuario
    )

    cursor.execute(
        """
        SELECT
            P.ID_Perfil,
            P.Nome,
            P.Descricao,

            UP.Ativo

        FROM dbo.UsuarioPerfis UP

        INNER JOIN dbo.Perfis P
            ON P.ID_Perfil =
               UP.ID_Perfil

        WHERE
            UP.ID_Usuario = ?
            AND UP.Ativo = 1
            AND P.Ativo = 1

        ORDER BY
            P.Nome
        """,
        id_usuario
    )

    linhas = (
        cursor.fetchall()
    )

    return [
        {
            "id_perfil":
                linha.ID_Perfil,

            "nome":
                linha.Nome,

            "descricao":
                linha.Descricao,

            "ativo":
                bool(
                    linha.Ativo
                )
        }
        for linha in linhas
    ]


# ============================================================
# VINCULAR PERFIL AO USUÁRIO
# ============================================================

def vincular_perfil_usuario(
    cursor,
    id_usuario: int,
    id_perfil: int
):

    if id_usuario <= 0:

        raise BusinessRuleViolation(
            "Usuário inválido."
        )

    if id_perfil <= 0:

        raise BusinessRuleViolation(
            "Perfil inválido."
        )

    # ========================================================
    # USUÁRIO
    # ========================================================

    consultar_usuario(
        cursor=cursor,
        id_usuario=id_usuario
    )

    # ========================================================
    # PERFIL
    # ========================================================

    cursor.execute(
        """
        SELECT TOP 1
            ID_Perfil,
            Nome,
            Ativo

        FROM dbo.Perfis

        WHERE ID_Perfil = ?
        """,
        id_perfil
    )

    perfil = (
        cursor.fetchone()
    )

    if not perfil:

        raise NotFoundError(
            "Perfil não encontrado."
        )

    if not bool(
        perfil.Ativo
    ):

        raise BusinessRuleViolation(
            "Não é possível vincular um perfil inativo."
        )

    # ========================================================
    # VÍNCULO EXISTENTE
    # ========================================================

    cursor.execute(
        """
        SELECT TOP 1
            ID_UsuarioPerfil,
            Ativo

        FROM dbo.UsuarioPerfis

        WHERE
            ID_Usuario = ?
            AND ID_Perfil = ?
        """,
        (
            id_usuario,
            id_perfil
        )
    )

    existente = (
        cursor.fetchone()
    )

    if existente:

        if bool(
            existente.Ativo
        ):

            return {
                "sucesso":
                    True,

                "id_usuario":
                    id_usuario,

                "id_perfil":
                    id_perfil,

                "perfil":
                    perfil.Nome,

                "ja_vinculado":
                    True,

                "mensagem":
                    (
                        "O usuário já possui "
                        "este perfil."
                    )
            }

        cursor.execute(
            """
            UPDATE dbo.UsuarioPerfis

            SET
                Ativo = 1

            WHERE
                ID_UsuarioPerfil = ?
            """,
            existente.ID_UsuarioPerfil
        )

    else:

        cursor.execute(
            """
            INSERT INTO dbo.UsuarioPerfis
            (
                ID_Usuario,
                ID_Perfil,
                Ativo
            )

            VALUES
            (
                ?,
                ?,
                1
            )
            """,
            (
                id_usuario,
                id_perfil
            )
        )

    return {
        "sucesso":
            True,

        "id_usuario":
            id_usuario,

        "id_perfil":
            id_perfil,

        "perfil":
            perfil.Nome,

        "ja_vinculado":
            False,

        "mensagem":
            "Perfil vinculado com sucesso."
    }


# ============================================================
# REMOVER PERFIL DO USUÁRIO
# ============================================================

def remover_perfil_usuario(
    cursor,
    id_usuario: int,
    id_perfil: int
):

    cursor.execute(
        """
        UPDATE dbo.UsuarioPerfis

        SET
            Ativo = 0

        WHERE
            ID_Usuario = ?
            AND ID_Perfil = ?
            AND Ativo = 1
        """,
        (
            id_usuario,
            id_perfil
        )
    )

    if cursor.rowcount == 0:

        raise NotFoundError(
            "Vínculo ativo entre usuário e perfil não encontrado."
        )

    return {
        "sucesso":
            True,

        "id_usuario":
            id_usuario,

        "id_perfil":
            id_perfil,

        "mensagem":
            "Perfil removido do usuário."
    }


# ============================================================
# PERMISSÕES EFETIVAS DO USUÁRIO
# ============================================================

def listar_permissoes_usuario(
    cursor,
    id_usuario: int
):

    consultar_usuario(
        cursor=cursor,
        id_usuario=id_usuario
    )

    cursor.execute(
        """
        SELECT DISTINCT
            PE.ID_Permissao,
            PE.Codigo,
            PE.Descricao

        FROM dbo.UsuarioPerfis UP

        INNER JOIN dbo.Perfis P
            ON P.ID_Perfil =
               UP.ID_Perfil

        INNER JOIN dbo.PerfilPermissoes PP
            ON PP.ID_Perfil =
               P.ID_Perfil

        INNER JOIN dbo.Permissoes PE
            ON PE.ID_Permissao =
               PP.ID_Permissao

        WHERE
            UP.ID_Usuario = ?
            AND UP.Ativo = 1
            AND P.Ativo = 1
            AND PE.Ativo = 1

        ORDER BY
            PE.Codigo
        """,
        id_usuario
    )

    linhas = (
        cursor.fetchall()
    )

    return [
        {
            "id_permissao":
                linha.ID_Permissao,

            "codigo":
                linha.Codigo,

            "descricao":
                linha.Descricao
        }
        for linha in linhas
    ]