"""
Fluxo "Esqueci minha senha" do SGI.

Seguranca:
- token aleatorio (secrets.token_urlsafe) -> ~43 chars
- apenas o SHA-256 do token e persistido
- expiracao curta (PASSWORD_RESET_EXPIRA_MINUTOS)
- uso unico
- tokens anteriores do mesmo usuario sao invalidados
- resposta generica na solicitacao (evita enumeracao)
"""

import hashlib
import os
import secrets
from datetime import datetime, timedelta

from domain.exceptions import (
    BusinessRuleViolation,
    NotFoundError,
)

from services.email import enviar_email
from services.usuarios import alterar_senha_usuario


_EXPIRACAO_PADRAO_MIN = 30


def _expiracao_minutos() -> int:
    valor = os.getenv("PASSWORD_RESET_EXPIRA_MINUTOS")
    if not valor:
        return _EXPIRACAO_PADRAO_MIN
    try:
        minutos = int(valor)
    except ValueError:
        return _EXPIRACAO_PADRAO_MIN
    if minutos <= 0:
        return _EXPIRACAO_PADRAO_MIN
    return minutos


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _url_frontend_reset(token: str) -> str:
    base = os.getenv("FRONTEND_URL", "http://127.0.0.1:8080").rstrip("/")
    return f"{base}/reset-senha?token={token}"


def _buscar_usuario_por_email(cursor, email: str):
    cursor.execute(
        """
        SELECT TOP 1
            ID_Usuario,
            Nome,
            Email,
            Ativo

        FROM dbo.Usuarios

        WHERE
            Email IS NOT NULL
            AND LOWER(LTRIM(RTRIM(Email))) = ?
        """,
        email.strip().lower()
    )
    return cursor.fetchone()


def solicitar_redefinicao_senha(
    cursor,
    email: str,
    ip_solicitante: str | None = None,
    user_agent: str | None = None
) -> dict:

    email_normalizado = (email or "").strip().lower()

    if not email_normalizado:
        raise BusinessRuleViolation("E-mail obrigatorio.")

    usuario = _buscar_usuario_por_email(cursor, email_normalizado)

    mensagem_generica = (
        "Se o e-mail informado estiver cadastrado, "
        "enviaremos as instrucoes de recuperacao."
    )

    if not usuario:
        return {"sucesso": True, "mensagem": mensagem_generica}

    if not bool(usuario.Ativo):
        return {"sucesso": True, "mensagem": mensagem_generica}

    cursor.execute(
        """
        UPDATE dbo.PasswordResetTokens
        SET
            Utilizado = 1,
            DataHoraUso = SYSDATETIME()
        WHERE
            ID_Usuario = ?
            AND Utilizado = 0
        """,
        usuario.ID_Usuario
    )

    token_claro = secrets.token_urlsafe(32)
    token_hash = _hash_token(token_claro)
    expira_em = datetime.utcnow() + timedelta(minutes=_expiracao_minutos())

    cursor.execute(
        """
        INSERT INTO dbo.PasswordResetTokens
        (
            ID_Usuario,
            TokenHash,
            DataHoraCriacao,
            DataHoraExpiraEm,
            Utilizado,
            IP_Solicitante,
            UserAgent
        )
        VALUES
        (
            ?,
            ?,
            SYSDATETIME(),
            ?,
            0,
            ?,
            ?
        )
        """,
        (
            usuario.ID_Usuario,
            token_hash,
            expira_em,
            ip_solicitante,
            (user_agent[:400] if user_agent else None)
        )
    )

    link = _url_frontend_reset(token_claro)
    expira_min = _expiracao_minutos()
    assunto = "SGI | Redefinicao de senha"

    corpo_texto = (
        f"Ola, {usuario.Nome}.\n\n"
        "Recebemos uma solicitacao para redefinir a senha "
        "da sua conta no SGI.\n\n"
        f"Use o link abaixo para criar uma nova senha "
        f"(valido por {expira_min} minutos):\n\n"
        f"{link}\n\n"
        "Se voce nao solicitou esta alteracao, ignore este e-mail "
        "- sua senha permanecera a mesma.\n\n"
        "SGI | Sistema de Gestao de Inventario - Alzarsilog"
    )

    corpo_html = f"""
    <div style="font-family:Segoe UI,Arial,sans-serif;max-width:560px;margin:0 auto;color:#0f172a;">
      <h2 style="color:#0f172a;">SGI | Redefinicao de senha</h2>
      <p>Ola, <strong>{usuario.Nome}</strong>.</p>
      <p>Recebemos uma solicitacao para redefinir a senha da sua conta no SGI.</p>
      <p>
        <a href="{link}"
           style="display:inline-block;background:#0f172a;color:#fff;padding:12px 20px;border-radius:6px;text-decoration:none;font-weight:600;">
          Criar nova senha
        </a>
      </p>
      <p style="color:#64748b;font-size:13px;">
        Este link e valido por <strong>{expira_min} minutos</strong>.
        Se voce nao solicitou esta alteracao, ignore este e-mail.
      </p>
      <hr style="border:none;border-top:1px solid #e2e8f0;margin:24px 0;" />
      <p style="color:#94a3b8;font-size:12px;">
        SGI | Sistema de Gestao de Inventario - Alzarsilog
      </p>
    </div>
    """

    enviar_email(
        destinatario=usuario.Email,
        assunto=assunto,
        corpo_texto=corpo_texto,
        corpo_html=corpo_html
    )

    return {"sucesso": True, "mensagem": mensagem_generica}


def redefinir_senha_com_token(
    cursor,
    token: str,
    nova_senha: str
) -> dict:

    token = (str(token) if token is not None else "").strip()

    if not token:
        raise BusinessRuleViolation("Token obrigatorio.")

    nova_senha = str(nova_senha) if nova_senha is not None else ""

    if len(nova_senha) < 8:
        raise BusinessRuleViolation(
            "A nova senha deve ter ao menos 8 caracteres."
        )

    token_hash = _hash_token(token)

    cursor.execute(
        """
        SELECT TOP 1
            ID_PasswordResetToken,
            ID_Usuario,
            DataHoraExpiraEm,
            Utilizado

        FROM dbo.PasswordResetTokens

        WHERE TokenHash = ?
        """,
        token_hash
    )

    registro = cursor.fetchone()

    if not registro:
        raise NotFoundError("Token invalido ou expirado.")

    if bool(registro.Utilizado):
        raise BusinessRuleViolation(
            "Este link ja foi utilizado. Solicite um novo."
        )

    expira_em = registro.DataHoraExpiraEm

    if expira_em and datetime.utcnow() > expira_em:
        raise BusinessRuleViolation(
            "Este link expirou. Solicite um novo."
        )

    alterar_senha_usuario(
        cursor=cursor,
        id_usuario=registro.ID_Usuario,
        nova_senha=nova_senha
    )

    cursor.execute(
        """
        UPDATE dbo.PasswordResetTokens
        SET
            Utilizado = 1,
            DataHoraUso = SYSDATETIME()
        WHERE ID_PasswordResetToken = ?
        """,
        registro.ID_PasswordResetToken
    )

    return {"sucesso": True, "mensagem": "Senha redefinida com sucesso."}


