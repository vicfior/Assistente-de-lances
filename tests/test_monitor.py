import smtplib

from browser import BrowserAutomation, ElementSnapshot
from monitor import AuctionMonitor
from notifier import EmailNotifier, NotificationService
from validators import ValidationError, validate_selector_type, validate_timeout, validate_url, validate_user_input


class FakeBrowser:
    def __init__(self, snapshots):
        self.snapshots = snapshots
        self.index = 0
        self.posts = []

    def get_field_value(self, url, selector, selector_type):
        value = self.snapshots[self.index]
        if self.index < len(self.snapshots) - 1:
            self.index += 1
        return ElementSnapshot(
            value=value,
            locator_description=f"{selector_type}:{selector}",
            content_preview=f"Conteudo de {selector}: {value}",
        )

    def post_update(self, url, input_selector, button_selector, message):
        self.posts.append(
            {
                "url": url,
                "input_selector": input_selector,
                "button_selector": button_selector,
                "message": message,
            }
        )


class FakeLogger:
    def __init__(self):
        self.messages = []

    def info(self, message, *args):
        self.messages.append(("info", message % args if args else message))

    def warning(self, message, *args):
        self.messages.append(("warning", message % args if args else message))

    def error(self, message, *args):
        self.messages.append(("error", message % args if args else message))

    def exception(self, message, *args):
        self.messages.append(("exception", message % args if args else message))


class FakeEmailNotifier:
    def __init__(self):
        self.sent_messages = []

    def send_email(self, recipient, subject, body):
        self.sent_messages.append(
            {
                "recipient": recipient,
                "subject": subject,
                "body": body,
            }
        )


class FailingEmailNotifier:
    def send_email(self, recipient, subject, body):
        raise RuntimeError("Falha simulada de email")


def test_validate_url_accepts_https():
    assert validate_url("https://example.com/item/1") == "https://example.com/item/1"


def test_validate_url_rejects_invalid_string():
    try:
        validate_url("not-a-url")
    except ValidationError:
        assert True
    else:
        assert False, "Era esperado ValidationError para URL invalida"


def test_validate_timeout_rejects_large_values():
    try:
        validate_timeout(301)
    except ValidationError:
        assert True
    else:
        assert False, "Era esperado ValidationError para timeout acima do limite"


def test_validate_selector_type_accepts_text():
    assert validate_selector_type("text") == "text"


def test_validate_selector_type_accepts_smart():
    assert validate_selector_type("smart") == "smart"


def test_browser_builds_smart_candidates_from_slug():
    browser = BrowserAutomation()

    assert browser._build_smart_candidates("cotacoes/cambio/") == ["cotacoes/cambio/", "cotacoes", "cambio"]


def test_browser_builds_smart_candidates_with_synonym():
    browser = BrowserAutomation()

    assert browser._build_smart_candidates("dollar") == ["dollar", "dolar"]


def test_browser_detects_numeric_signal():
    browser = BrowserAutomation()

    assert browser._contains_numeric_signal("Dolar 5,67")
    assert not browser._contains_numeric_signal("Cotacoes | Site | Investimentos")


def test_browser_extracts_label_from_numeric_line():
    browser = BrowserAutomation()

    assert browser._extract_label_from_line("Dolar 5,67") == "Dolar"


def test_browser_extracts_first_numeric_value_from_block():
    browser = BrowserAutomation()

    content = "COMPRA 5,159 VENDA 5,159 MAXIMO 5,194 MINIMO 5,139 VARIACAO 0,05 %"
    assert browser._extract_value_from_text(content, "Dolar") == "5,159"


def test_browser_prefers_compra_value_for_generic_currency_block():
    browser = BrowserAutomation()

    content = (
        "CAMBIO\n"
        "Dolar Comercial\n"
        "COMPRA 5,159\n"
        "VENDA 5,159\n"
        "Euro 5,951\n"
        "Peso Argentino 0,004"
    )
    assert browser._extract_value_from_text(content, "cambio") == "5,159"


def test_browser_ignores_phone_like_value_when_extracting_price():
    browser = BrowserAutomation()

    content = "Dolar Comercial: Cotacao de Hoje - UOL Economia | Assine UOL | 4003-6118"
    assert browser._extract_price_candidates(content) == []


def test_browser_cleans_content_text():
    browser = BrowserAutomation()

    raw_text = "COMPRA   5,159\n\nVENDA 5,159  \n"
    assert browser._clean_content_text(raw_text) == "COMPRA 5,159\nVENDA 5,159"


def test_browser_rejects_unhelpful_labels():
    browser = BrowserAutomation()

    assert not browser._is_meaningful_label("Reference #.ea.aeea")
    assert not browser._is_meaningful_label("Investimentos")
    assert browser._is_meaningful_label("Dolar")


def test_browser_detects_blocked_page_text():
    browser = BrowserAutomation()

    assert browser._looks_like_blocked_page("Reference #18.abc123")
    assert not browser._looks_like_blocked_page("COMPRA 5,159 VENDA 5,159")


def test_validate_user_input_allows_missing_public_page_fields():
    validated = validate_user_input(
        {
            "user_name": "Ana",
            "source_url": "https://example.com",
            "selector": "PETR4",
            "selector_type": "smart",
            "interval_seconds": 5,
            "timeout_seconds": 15,
            "target_url": "",
            "target_input_selector": "",
            "target_button_selector": "",
            "email_sender": "origem@example.com",
            "email_recipient": "destino@example.com",
            "smtp_server": "smtp.gmail.com",
            "smtp_port": 587,
        }
    )

    assert validated.target_url == ""


def test_detect_change_returns_event():
    logger = FakeLogger()
    monitor = AuctionMonitor(browser=FakeBrowser(["10"]), logger=logger, sleep_func=lambda _: None)

    event = monitor.detect_change("10", "20", "css=.value")

    assert event is not None
    assert event.old_value == "10"
    assert event.new_value == "20"


def test_monitor_triggers_callback_when_value_changes():
    logger = FakeLogger()
    browser = FakeBrowser(["10", "10", "15"])
    monitor = AuctionMonitor(browser=browser, logger=logger, sleep_func=lambda _: None)
    captured = []
    snapshots = []

    monitor.monitor(
        url="https://example.com",
        selector=".price",
        selector_type="css",
        interval_seconds=0.01,
        on_change=captured.append,
        max_cycles=2,
        on_stats=lambda stats: snapshots.append((stats.checks_performed, stats.current_value, stats.changes_detected)),
    )

    assert len(captured) == 1
    assert captured[0].old_value == "10"
    assert captured[0].new_value == "15"
    assert snapshots[-1] == (3, "15", 1)


def test_notification_service_posts_message_to_public_page():
    logger = FakeLogger()
    browser = FakeBrowser(["10"])
    service = NotificationService(logger=logger)

    message = service.notify_external_page(
        browser=browser,
        target_url="https://example.com/public-form",
        input_selector="#message",
        button_selector="#send",
        old_value="100",
        new_value="120",
    )

    assert "Anterior: 100" in message
    assert "Novo: 120" in message
    assert browser.posts[0]["url"] == "https://example.com/public-form"


def test_notification_service_sends_confirmation_email():
    logger = FakeLogger()
    email_notifier = FakeEmailNotifier()
    service = NotificationService(logger=logger, email_notifier=email_notifier)

    service.send_confirmation_email(
        recipient="destino@example.com",
        monitored_label="PETR4",
        current_value="R$ 32,10",
        source_url="https://example.com/acao",
        field_content="PETR4 | Ultimo preco R$ 32,10 | Variacao +0,50%",
    )

    assert email_notifier.sent_messages[0]["recipient"] == "destino@example.com"
    assert email_notifier.sent_messages[0]["subject"] == "Confirmacao de monitoramento"
    assert "PETR4" in email_notifier.sent_messages[0]["body"]
    assert "R$ 32,10" in email_notifier.sent_messages[0]["body"]
    assert "Conteudo completo encontrado no elemento" in email_notifier.sent_messages[0]["body"]


def test_notification_service_ignores_confirmation_email_failure():
    logger = FakeLogger()
    service = NotificationService(logger=logger, email_notifier=FailingEmailNotifier())

    service.send_confirmation_email(
        recipient="destino@example.com",
        monitored_label="PETR4",
        current_value="R$ 32,10",
        source_url="https://example.com/acao",
        field_content="PETR4 | Ultimo preco R$ 32,10 | Variacao +0,50%",
    )

    assert any(level == "error" and "confirmacao" in message for level, message in logger.messages)


def test_email_notifier_raises_friendly_message_for_auth_error(monkeypatch):
    class FakeSMTP:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def starttls(self):
            return None

        def login(self, sender, password):
            raise smtplib.SMTPAuthenticationError(535, b"bad credentials")

        def send_message(self, message):
            return None

    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    logger = FakeLogger()
    notifier = EmailNotifier(
        smtp_server="smtp.gmail.com",
        smtp_port=587,
        sender_email="origem@example.com",
        sender_password="senha",
        logger=logger,
    )

    try:
        notifier.send_email("destino@example.com", "Teste", "Mensagem")
    except RuntimeError as exc:
        assert "App Password" in str(exc)
    else:
        assert False, "Era esperado erro amigavel para falha de autenticacao SMTP"
