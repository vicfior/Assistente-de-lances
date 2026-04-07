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
    candidate = (name or "").strip()
    if len(candidate) < 3:
        raise ValidationError("O nome do usuario deve ter pelo menos 3 caracteres.")
    return candidate


def validate_url(url: str) -> str:
    candidate = (url or "").strip()
    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValidationError("URL invalida. Use http:// ou https://")
    return candidate


def validate_selector(selector: str) -> str:
    candidate = (selector or "").strip()
    if not candidate:
        raise ValidationError("O campo a monitorar nao pode ser vazio.")
    return candidate


def validate_selector_type(selector_type: str) -> str:
    allowed = {"css", "xpath", "regex", "text", "smart"}
    candidate = (selector_type or "").strip().lower()
    if candidate not in allowed:
        raise ValidationError(f"Tipo de seletor invalido. Use um de: {', '.join(sorted(allowed))}.")
    return candidate


def validate_interval(interval: float) -> float:
    if interval <= 0:
        raise ValidationError("O intervalo de monitoramento deve ser maior que zero.")
    return interval


def validate_timeout(timeout: float) -> float:
    if timeout <= 0 or timeout > 300:
        raise ValidationError("O timeout deve estar entre 1 e 300 segundos.")
    return timeout


def validate_port(port: int) -> int:
    if port <= 0 or port > 65535:
        raise ValidationError("Porta SMTP invalida.")
    return port


def validate_user_input(data: dict) -> UserInput:
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


def validate_url_email(email: str) -> str:
    candidate = (email or "").strip()
    if "@" not in candidate or "." not in candidate.split("@")[-1]:
        raise ValidationError("Email invalido.")
    return candidate
