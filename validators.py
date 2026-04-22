from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse


class ValidationError(ValueError):
    pass


@dataclass
class UserInput:
    user_name: str
    source_url: str
    selector: str
    selector_type: str
    interval_seconds: float
    timeout_seconds: float
    target_url: str
    target_input_selector: str
    target_button_selector: str
    email_sender: str
    email_recipient: str
    smtp_server: str
    smtp_port: int


def validate_name(name: str) -> str:
    """
    Valida o nome do usuario para garantir que tenha pelo menos 3 caracteres.

    :raises ValidationError: Se o nome do usuario for vazio ou tiver menos de 3 caracteres.
    :return: O nome do usuario validado.
    """
    candidate = (name or "").strip()
    if len(candidate) < 3:
        raise ValidationError("O nome do usuario deve ter pelo menos 3 caracteres.")
    return candidate


def validate_url(url: str) -> str:
    """
    Valida uma URL para garantir que esteja no formato correto.
    
    :raises ValidationError: Se a URL for invalida (sem esquema http/https ou sem dominio).
    :return: A URL validada.
    """
    candidate = (url or "").strip()
    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValidationError("URL invalida. Use http:// ou https://")
    return candidate


def validate_selector(selector: str) -> str:
    """
    Valida um seletor de campo dinamico para garantir que tenha pelo menos 1 caractere.

    :raises ValidationError: Se o seletor for vazio.
    :return: O seletor validado.
    """
    candidate = (selector or "").strip()
    if not candidate:
        raise ValidationError("O campo a monitorar nao pode ser vazio.")
    return candidate


def validate_selector_type(selector_type: str) -> str:
    """
    Valida o tipo de seletor de campo dinamico.

    :param selector_type: O tipo de seletor a ser validado.
    :raises ValidationError: Se o tipo de seletor for invalido.
    :return: O tipo de seletor validado.
    """
    allowed = {"css", "xpath", "regex", "text", "smart"}
    candidate = (selector_type or "").strip().lower()
    if candidate not in allowed:
        raise ValidationError(f"Tipo de seletor invalido. Use um de: {', '.join(sorted(allowed))}.")
    return candidate


def validate_interval(interval: float) -> float:
    """
    Valida o intervalo de monitoramento.

    :raises ValidationError: Se o intervalo for menor ou igual a zero.
    :return: O intervalo de monitoramento validado.
    """
    if interval <= 0:
        raise ValidationError("O intervalo de monitoramento deve ser maior que zero.")
    return interval


def validate_timeout(timeout: float) -> float:
    """
    Valida o timeout de monitoramento.

    :param timeout: O timeout a ser validado em segundos.
    :raises ValidationError: Se o timeout for menor ou igual a zero ou maior que 300 segundos.
    :return: O timeout de monitoramento validado.
    """
    if timeout <= 0 or timeout > 300:
        raise ValidationError("O timeout deve estar entre 1 e 300 segundos.")
    return timeout


def validate_port(port: int) -> int:
    """
    Valida a porta SMTP.

    :param port: A porta a ser validada.
    :raises ValidationError: Se a porta for menor ou igual a zero ou maior que 65535.
    :return: A porta SMTP validada.
    """
    if port <= 0 or port > 65535:
        raise ValidationError("Porta SMTP invalida.")
    return port

def validate_url_email(email: str) -> str:
    """
    Valida um endereco de email.

    :param email: O endereco de email a ser validado.
    :raises ValidationError: Se o email for invalido.
    :return: O endereco de email validado.
    """
    candidate = (email or "").strip()

    if not candidate:
        raise ValidationError("O campo email nao pode ser vazio.")
    elif "@" not in candidate or "." not in candidate.split("@")[-1]:
        raise ValidationError("Email invalido.")
    return candidate




def validate_user_input(data: dict) -> UserInput:
    """
    Valida os dados de entrada do usuario e retorna um objeto UserInput.

    Valida os seguintes campos:
    - user_name: O nome do usuario.
    - source_url: A URL da pagina de leilao a ser monitorada.
    - selector: O seletor do campo dinamico a ser monitorado.
    - selector_type: O tipo de seletor do campo dinamico (css, xpath, regex, text, smart).
    - interval_seconds: O intervalo de tempo em segundos entre verificacoes.
    - timeout_seconds: O tempo de espera em segundos para a abertura da pagina.
    - target_url: A URL da pagina publica que sera enviada a notificacao.
    - target_input_selector: O seletor do campo de entrada na pagina publica.
    - target_button_selector: O seletor do botao de envio na pagina publica.
    - email_sender: O endereco de email do remetente.
    - email_recipient: O endereco de email do destinatario.
    - smtp_server: O servidor SMTP do remetente.
    - smtp_port: A porta SMTP do remetente.

    :raises ValidationError: Se houver falha na validacao de algum campo.
    :return: O objeto UserInput com os campos validados.
    """
    target_url = (data.get("target_url") or "").strip()
    target_input_selector = (data.get("target_input_selector") or "").strip()
    target_button_selector = (data.get("target_button_selector") or "").strip()
    has_target_fields = any([target_url, target_input_selector, target_button_selector])

    if has_target_fields and not all([target_url, target_input_selector, target_button_selector]):
        raise ValidationError(
            "Para usar a pagina publica de destino, informe URL, campo de texto e botao."
        )

    return UserInput(
        user_name=validate_name(data["user_name"]),
        source_url=validate_url(data["source_url"]),
        selector=validate_selector(data["selector"]),
        selector_type=validate_selector_type(data["selector_type"]),
        interval_seconds=validate_interval(float(data["interval_seconds"])),
        timeout_seconds=validate_timeout(float(data["timeout_seconds"])),
        target_url=validate_url(target_url) if target_url else "",
        target_input_selector=validate_selector(target_input_selector) if target_input_selector else "",
        target_button_selector=validate_selector(target_button_selector) if target_button_selector else "",
        email_sender=validate_url_email(data["email_sender"]),
        email_recipient=validate_url_email(data["email_recipient"]),
        smtp_server=(data["smtp_server"] or "").strip(),
        smtp_port=validate_port(int(data["smtp_port"])),
    )



