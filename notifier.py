from __future__ import annotations

import smtplib
from email.message import EmailMessage
from typing import Optional

from browser import BrowserAutomation


class EmailNotifier:
    def __init__(
        self,
        smtp_server: str,
        smtp_port: int,
        sender_email: str,
        sender_password: str,
        logger,
    ) -> None:
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.sender_email = sender_email
        self.sender_password = sender_password
        self.logger = logger

    def send_email(self, recipient: str, subject: str, body: str) -> None:
        message = EmailMessage()
        message["From"] = self.sender_email
        message["To"] = recipient
        message["Subject"] = subject
        message.set_content(body)

        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=30) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(message)
        except smtplib.SMTPAuthenticationError as exc:
            raise RuntimeError(
                "Falha ao autenticar no email remetente. Para Gmail, use uma App Password valida."
            ) from exc

        self.logger.info("Notificacao por email enviada para %s", recipient)


class NotificationService:
    def __init__(self, logger, email_notifier: Optional[EmailNotifier] = None) -> None:
        self.logger = logger
        self.email_notifier = email_notifier

    def build_message(self, old_value: str, new_value: str) -> str:
        return f"Valor alterado:\nAnterior: {old_value}\nNovo: {new_value}"

    def build_confirmation_message(
        self,
        monitored_label: str,
        current_value: str,
        source_url: str,
        field_content: str,
    ) -> str:
        return (
            "Monitoramento iniciado com sucesso.\n"
            f"Campo monitorado: {monitored_label}\n"
            f"Valor atual: {current_value}\n"
            "Conteudo completo encontrado no elemento:\n"
            f"{field_content}\n"
            f"Pagina monitorada: {source_url}"
        )

    def notify_external_page(
        self,
        browser: BrowserAutomation,
        target_url: str,
        input_selector: str,
        button_selector: str,
        old_value: str,
        new_value: str,
    ) -> str:
        message = self.build_message(old_value, new_value)
        browser.post_update(target_url, input_selector, button_selector, message)
        self.logger.info("Mensagem enviada para pagina publica %s", target_url)
        return message

    def notify_email(self, recipient: str, old_value: str, new_value: str) -> None:
        if not self.email_notifier:
            self.logger.warning("Servico de email nao configurado; notificacao ignorada.")
            return

        subject = "Alteracao detectada em leilao"
        body = self.build_message(old_value, new_value)
        try:
            self.email_notifier.send_email(recipient, subject, body)
        except Exception as exc:
            self.logger.error("Falha ao enviar notificacao por email: %s", exc)

    def send_confirmation_email(
        self,
        recipient: str,
        monitored_label: str,
        current_value: str,
        source_url: str,
        field_content: str,
    ) -> None:
        if not self.email_notifier:
            self.logger.warning("Servico de email nao configurado; confirmacao ignorada.")
            return

        subject = "Confirmacao de monitoramento"
        body = self.build_confirmation_message(
            monitored_label=monitored_label,
            current_value=current_value,
            source_url=source_url,
            field_content=field_content,
        )
        try:
            self.email_notifier.send_email(recipient, subject, body)
        except Exception as exc:
            self.logger.error("Falha ao enviar email de confirmacao: %s", exc)

    def notify_all(
        self,
        browser: BrowserAutomation,
        recipient: str,
        old_value: str,
        new_value: str,
        target_url: str = "",
        input_selector: str = "",
        button_selector: str = "",
    ) -> None:
        if target_url and input_selector and button_selector:
            self.notify_external_page(
                browser=browser,
                target_url=target_url,
                input_selector=input_selector,
                button_selector=button_selector,
                old_value=old_value,
                new_value=new_value,
            )

        self.notify_email(recipient=recipient, old_value=old_value, new_value=new_value)
