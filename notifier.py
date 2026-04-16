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
        """
        Initialize the EmailNotifier with the SMTP server and port, sender email and password, and logger.

        :param smtp_server: The SMTP server to use for sending emails.
        :param smtp_port: The SMTP server port to use for sending emails.
        :param sender_email: The email address of the sender.
        :param sender_password: The password of the sender email.
        :param logger: The logger to use for logging events.
        """
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.sender_email = sender_email
        self.sender_password = sender_password
        self.logger = logger

    def send_email(self, recipient: str, subject: str, body: str) -> None:
        """
        Envia uma notificacao por email para o destinatario especificado.

        :param recipient: O endereco de email do destinatario.
        :param subject: O assunto da mensagem.
        :param body: O conteudo da mensagem.
        :raises RuntimeError: Se houver falha ao autenticar no email remetente.
        """
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
        """
        Construi uma mensagem de notificacao com o valor anterior e novo.

        :param old_value: O valor anterior do campo monitorado.
        :param new_value: O valor novo do campo monitorado.
        :return: A mensagem de notificacao construida.
        """
        return f"Valor alterado:\nAnterior: {old_value}\nNovo: {new_value}"

    def build_confirmation_message(
        self,
        monitored_label: str,
        current_value: str,
        source_url: str,
        field_content: str,
    ) -> str:
        """
        Constrói uma mensagem de confirmação de início de monitoramento com o valor atual, conteúdo do elemento e URL da página monitorada.

        :param monitored_label: O nome do campo monitorado.
        :param current_value: O valor atual do campo monitorado.
        :param source_url: A URL da pagina monitorada.
        :param field_content: O conteudo completo encontrado no elemento monitorado.
        :return: A mensagem de confirmacao construida.
        """
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
        """
        Envia uma notificacao por email para o destinatario especificado.

        :param browser: O objeto BrowserAutomation que sera usado para enviar a notificacao.
        :param target_url: A URL da pagina publica que sera enviada a notificacao.
        :param input_selector: O seletor do campo de entrada na pagina publica.
        :param button_selector: O seletor do botao de envio na pagina publica.
        :param old_value: O valor anterior do campo monitorado.
        :param new_value: O valor novo do campo monitorado.
        :return: A mensagem de notificacao construida.
        :raises RuntimeError: Se houver falha ao autenticar no email remetente.
        """
        message = self.build_message(old_value, new_value)
        browser.post_update(target_url, input_selector, button_selector, message)
        self.logger.info("Mensagem enviada para pagina publica %s", target_url)
        return message

    def notify_email(self, recipient: str, old_value: str, new_value: str) -> None:
        """
        Envia uma notificacao por email para o destinatario especificado.

        :param recipient: O endereco de email do destinatario.
        :param old_value: O valor anterior do campo monitorado.
        :param new_value: O valor novo do campo monitorado.
        :raises RuntimeError: Se houver falha ao autenticar no email remetente.
        """
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
        """
        Envia uma notificacao por email para o destinatario especificado com o valor atual, conteudo do elemento e URL da pagina monitorada.

        :param recipient: O endereco de email do destinatario.
        :param monitored_label: O nome do campo monitorado.
        :param current_value: O valor atual do campo monitorado.
        :param source_url: A URL da pagina monitorada.
        :param field_content: O conteudo completo encontrado no elemento monitorado.
        :raises RuntimeError: Se houver falha ao autenticar no email remetente.
        """
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
        """
        Envia notificacoes por email e pela pagina publica para o destinatario especificado.

        :param browser: O objeto BrowserAutomation que sera usado para enviar a notificacao por pagina publica.
        :param recipient: O endereco de email do destinatario.
        :param old_value: O valor anterior do campo monitorado.
        :param new_value: O valor novo do campo monitorado.
        :param target_url: A URL da pagina publica que sera enviada a notificacao.
        :param input_selector: O seletor do campo de entrada na pagina publica.
        :param button_selector: O seletor do botao de envio na pagina publica.
        :raises RuntimeError: Se houver falha ao autenticar no email remetente.
        """
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
