"""
Email Notifier - Envio de alertas por email via Gmail SMTP
==========================================================
Envia notificações de alertas críticos do pipeline.

USO:
    from src.core.email_notifier import EmailNotifier

    notifier = EmailNotifier()
    notifier.send_alert(
        severidade="critical",
        titulo="Pipeline falhou",
        mensagem="A execução X falhou com erro Y",
        dados={"run_id": "123", "erro": "timeout"}
    )

CONFIGURAÇÃO:
    Usa as MESMAS variáveis de ambiente do GitHub Actions:
    - EMAIL_ADDRESS: Seu email do Gmail
    - EMAIL_APP_PASSWORD: Senha de App do Gmail (16 caracteres)

    OU variáveis alternativas:
    - GMAIL_USER / GMAIL_APP_PASSWORD
    - ALERT_EMAIL_TO (se diferente do remetente)

CRIAR SENHA DE APP:
    1. Ative "Verificação em duas etapas" na sua conta Google
    2. Acesse: https://myaccount.google.com/apppasswords
    3. Crie uma senha de app para "Email"
    4. Use essa senha de 16 caracteres (sem espaços)
"""

import os
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
import json

logger = logging.getLogger(__name__)


class EmailNotifier:
    """Notificador de alertas por email via Gmail SMTP."""

    def __init__(self):
        # Tentar variáveis do GitHub Actions primeiro, depois alternativas
        self.gmail_user = (
            os.getenv("EMAIL_ADDRESS") or
            os.getenv("GMAIL_USER")
        )
        self.gmail_password = (
            os.getenv("EMAIL_APP_PASSWORD") or
            os.getenv("GMAIL_APP_PASSWORD")
        )
        self.email_to = (
            os.getenv("ALERT_EMAIL_TO") or
            self.gmail_user  # Envia para si mesmo se não especificado
        )

        # Verificar se está configurado
        self.enabled = bool(self.gmail_user and self.gmail_password)

        if self.enabled:
            logger.info(f"[EmailNotifier] Gmail SMTP configurado: {self.gmail_user}")
        else:
            if not self.gmail_user:
                logger.info("[EmailNotifier] EMAIL_ADDRESS não configurado - emails desativados")
            if not self.gmail_password:
                logger.info("[EmailNotifier] EMAIL_APP_PASSWORD não configurado - emails desativados")

    def send_alert(
        self,
        severidade: str,
        titulo: str,
        mensagem: str,
        dados: Optional[dict] = None,
        run_id: Optional[str] = None
    ) -> bool:
        """
        Envia alerta por email via Gmail SMTP.

        Args:
            severidade: "info", "warning", "critical"
            titulo: Título do alerta
            mensagem: Mensagem detalhada
            dados: Dados adicionais (JSON)
            run_id: ID da execução

        Returns:
            True se enviado com sucesso, False caso contrário
        """
        if not self.enabled:
            logger.debug("[EmailNotifier] Email desativado, pulando envio")
            return False

        # Só envia email para alertas críticos e warnings
        if severidade not in ["critical", "warning"]:
            logger.debug(f"[EmailNotifier] Alerta {severidade} ignorado (só critical/warning)")
            return False

        try:
            # Montar email
            msg = MIMEMultipart("alternative")

            # Emoji no assunto baseado na severidade
            emoji = "🔴" if severidade == "critical" else "🟡"
            msg["Subject"] = f"{emoji} [Ache Sucatas] {titulo}"
            msg["From"] = f"Ache Sucatas <{self.gmail_user}>"
            msg["To"] = self.email_to

            # Corpo em HTML
            html_content = self._build_html(severidade, titulo, mensagem, dados, run_id)
            msg.attach(MIMEText(html_content, "html"))

            # Corpo em texto (fallback)
            text_content = self._build_text(severidade, titulo, mensagem, dados, run_id)
            msg.attach(MIMEText(text_content, "plain"))

            # Enviar via Gmail SMTP
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(self.gmail_user, self.gmail_password)
                server.sendmail(self.gmail_user, self.email_to, msg.as_string())

            logger.info(f"[EmailNotifier] Email enviado: {titulo}")
            return True

        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"[EmailNotifier] Erro de autenticação Gmail: {e}")
            logger.error("[EmailNotifier] Verifique EMAIL_ADDRESS e EMAIL_APP_PASSWORD")
            return False
        except Exception as e:
            logger.error(f"[EmailNotifier] Erro ao enviar email: {e}")
            return False

    def _build_text(
        self,
        severidade: str,
        titulo: str,
        mensagem: str,
        dados: Optional[dict],
        run_id: Optional[str]
    ) -> str:
        """Monta o texto plano do email."""
        text = f"""
ALERTA {severidade.upper()}: {titulo}
{'=' * 50}

{mensagem}
"""
        if run_id:
            text += f"\nRun ID: {run_id}"

        if dados:
            text += f"\n\nDados:\n{json.dumps(dados, indent=2, ensure_ascii=False)}"

        text += """

---
Este email foi enviado automaticamente pelo sistema Ache Sucatas.
Para gerenciar alertas, acesse o Dashboard de Pipeline.
"""
        return text

    def _build_html(
        self,
        severidade: str,
        titulo: str,
        mensagem: str,
        dados: Optional[dict],
        run_id: Optional[str]
    ) -> str:
        """Monta o HTML do email de alerta."""

        # Cores por severidade
        colors = {
            "critical": {"bg": "#fee2e2", "border": "#ef4444", "text": "#991b1b"},
            "warning": {"bg": "#fef3c7", "border": "#f59e0b", "text": "#92400e"},
            "info": {"bg": "#dbeafe", "border": "#3b82f6", "text": "#1e40af"},
        }
        color = colors.get(severidade, colors["info"])

        # Dados formatados
        dados_html = ""
        if dados:
            dados_html = f"""
            <div style="margin-top: 16px; padding: 12px; background: #f3f4f6; border-radius: 4px;">
                <strong>Dados:</strong>
                <pre style="margin: 8px 0 0 0; font-size: 12px; overflow-x: auto;">{json.dumps(dados, indent=2, ensure_ascii=False)}</pre>
            </div>
            """

        run_html = ""
        if run_id:
            run_html = f'<p style="margin: 8px 0; font-size: 12px; color: #6b7280;">Run ID: <code>{run_id}</code></p>'

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
        </head>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 20px; background: #f9fafb;">
            <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">

                <!-- Header -->
                <div style="padding: 20px; background: {color['bg']}; border-left: 4px solid {color['border']};">
                    <h1 style="margin: 0; font-size: 18px; color: {color['text']};">
                        {severidade.upper()}: {titulo}
                    </h1>
                </div>

                <!-- Content -->
                <div style="padding: 20px;">
                    <p style="margin: 0 0 16px 0; color: #374151; line-height: 1.5;">
                        {mensagem}
                    </p>

                    {run_html}
                    {dados_html}
                </div>

                <!-- Footer -->
                <div style="padding: 16px 20px; background: #f9fafb; border-top: 1px solid #e5e7eb;">
                    <p style="margin: 0; font-size: 12px; color: #9ca3af;">
                        Este email foi enviado automaticamente pelo sistema Ache Sucatas.
                    </p>
                </div>

            </div>
        </body>
        </html>
        """


# Instância global para uso simplificado
_notifier: Optional[EmailNotifier] = None


def get_notifier() -> EmailNotifier:
    """Retorna instância singleton do notificador."""
    global _notifier
    if _notifier is None:
        _notifier = EmailNotifier()
    return _notifier


def send_alert_email(
    severidade: str,
    titulo: str,
    mensagem: str,
    dados: Optional[dict] = None,
    run_id: Optional[str] = None
) -> bool:
    """
    Função de conveniência para enviar alerta por email.

    Exemplo:
        send_alert_email(
            severidade="critical",
            titulo="Taxa de quarentena crítica",
            mensagem="A taxa está em 45%, acima do limite de 30%",
            dados={"taxa": 45, "limite": 30},
            run_id="20260125T123456Z_abc123"
        )
    """
    return get_notifier().send_alert(severidade, titulo, mensagem, dados, run_id)
