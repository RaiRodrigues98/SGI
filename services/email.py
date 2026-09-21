"""
Envio de e-mail do SGI.

Modo de operacao (controlado por EMAIL_BACKEND no .env):

- "smtp"    -> envia via SMTP corporativo
- "console" -> NAO envia; imprime o conteudo no terminal
- ausente   -> cai em "console"

Nenhuma dependencia externa: usa apenas smtplib da stdlib.
"""

import os
import smtplib
import ssl
from email.message import EmailMessage


def _backend() -> str:
    return (
        os.getenv("EMAIL_BACKEND", "console")
        .strip()
        .lower()
    )


def _bool_env(chave: str, padrao: bool = False) -> bool:
    valor = os.getenv(chave)
    if valor is None:
        return padrao
    return valor.strip().lower() in ("1", "true", "sim", "yes")


def enviar_email(
    destinatario: str,
    assunto: str,
    corpo_texto: str,
    corpo_html: str | None = None
) -> None:

    backend = _backend()

    if backend != "smtp":
        _imprimir_no_console(
            destinatario=destinatario,
            assunto=assunto,
            corpo_texto=corpo_texto
        )
        return

    host = os.getenv("SMTP_HOST")

    if not host:
        raise RuntimeError(
            "SMTP_HOST nao configurado, mas EMAIL_BACKEND=smtp."
        )

    porta = int(os.getenv("SMTP_PORT", "587"))
    usuario = os.getenv("SMTP_USER")
    senha = os.getenv("SMTP_PASSWORD")
    remetente = os.getenv("SMTP_FROM", usuario or "sgi@alzarsi.local")
    usar_tls = _bool_env("SMTP_USE_TLS", True)

    mensagem = EmailMessage()
    mensagem["From"] = remetente
    mensagem["To"] = destinatario
    mensagem["Subject"] = assunto
    mensagem.set_content(corpo_texto)

    if corpo_html:
        mensagem.add_alternative(corpo_html, subtype="html")

    contexto = ssl.create_default_context()

    with smtplib.SMTP(host, porta, timeout=15) as servidor:
        servidor.ehlo()
        if usar_tls:
            servidor.starttls(context=contexto)
            servidor.ehlo()
        if usuario and senha:
            servidor.login(usuario, senha)
        servidor.send_message(mensagem)


def _imprimir_no_console(
    destinatario: str,
    assunto: str,
    corpo_texto: str
) -> None:
    print()
    print("=" * 72)
    print(
        "[SGI-EMAIL] modo console "
        "(configure EMAIL_BACKEND=smtp para enviar de verdade)"
    )
    print("Para:", destinatario)
    print("Assunto:", assunto)
    print("-" * 72)
    print(corpo_texto)
    print("=" * 72)
    print()
