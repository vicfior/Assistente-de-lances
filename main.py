from __future__ import annotations

import os
import threading
from getpass import getpass
from typing import Optional

from browser import BrowserAutomation, CandidateField
from logger import setup_logger
from local_config import load_local_secrets
from monitor import AuctionMonitor, MonitorStats
from notifier import EmailNotifier, NotificationService
from validators import ValidationError, validate_user_input


LOGGER = setup_logger()


def build_default_form_data() -> dict:
    local_secrets = load_local_secrets()
    return {
        "user_name": "",
        "source_url": "",
        "selector": "",
        "selector_type": "smart",
        "interval_seconds": 5.0,
        "timeout_seconds": 15.0,
        "target_url": "",
        "target_input_selector": "",
        "target_button_selector": "",
        "email_sender": local_secrets.get("email_sender", ""),
        "email_recipient": "",
        "smtp_server": local_secrets.get("smtp_server", "smtp.gmail.com"),
        "smtp_port": local_secrets.get("smtp_port", 587),
        "email_password": local_secrets.get("email_password", ""),
    }


def discover_page_candidates(url: str, timeout_seconds: float) -> list[CandidateField]:
    with BrowserAutomation(timeout_seconds=timeout_seconds, headless=True) as browser:
        return browser.discover_candidate_fields(url)


def run_monitoring(
    form_data: dict,
    on_stats=None,
    stop_event: Optional[threading.Event] = None,
) -> MonitorStats:
    validated = validate_user_input(form_data)
    local_secrets = load_local_secrets()
    smtp_password = (
        form_data.get("email_password")
        or local_secrets.get("email_password")
        or os.getenv("AUCTION_ASSISTANT_SMTP_PASSWORD")
        or getpass("Senha/App Password do email remetente: ")
    )

    email_notifier = EmailNotifier(
        smtp_server=validated.smtp_server,
        smtp_port=validated.smtp_port,
        sender_email=validated.email_sender,
        sender_password=smtp_password,
        logger=LOGGER,
    )
    notification_service = NotificationService(LOGGER, email_notifier)

    with BrowserAutomation(timeout_seconds=validated.timeout_seconds, headless=True) as browser:
        monitor = AuctionMonitor(browser, LOGGER)

        def handle_change(event) -> None:
            notification_service.notify_all(
                browser=browser,
                recipient=validated.email_recipient,
                target_url=validated.target_url,
                input_selector=validated.target_input_selector,
                button_selector=validated.target_button_selector,
                old_value=event.old_value,
                new_value=event.new_value,
            )

        def handle_initialized(snapshot, stats) -> None:
            notification_service.send_confirmation_email(
                recipient=validated.email_recipient,
                monitored_label=stats.monitored_label,
                current_value=snapshot.value,
                source_url=validated.source_url,
                field_content=snapshot.content_preview or snapshot.locator_description,
            )

        return monitor.monitor(
            url=validated.source_url,
            selector=validated.selector,
            selector_type=validated.selector_type,
            interval_seconds=validated.interval_seconds,
            on_change=handle_change,
            on_stats=on_stats,
            on_initialized=handle_initialized,
            stop_event=stop_event,
        )


def run_cli() -> None:
    print("Assistente de Lances para Sites de Leilao")
    form_data = {
        "user_name": input("Nome do usuario: "),
        "source_url": input("URL a monitorar: "),
        "selector": input("Nome do item/acao a monitorar: "),
        "selector_type": input("Modo de localizacao [smart/text/css/xpath/regex]: ") or "smart",
        "interval_seconds": input("Intervalo de monitoramento em segundos: "),
        "timeout_seconds": input("Timeout da pagina em segundos: "),
        "target_url": input("URL da pagina publica para interacao [opcional]: "),
        "target_input_selector": input("Seletor do campo de texto [opcional]: "),
        "target_button_selector": input("Seletor do botao [opcional]: "),
        "email_sender": input("Email remetente: "),
        "email_recipient": input("Email destinatario: "),
        "smtp_server": input("SMTP server [smtp.gmail.com]: ") or "smtp.gmail.com",
        "smtp_port": input("SMTP port [587]: ") or "587",
        "email_password": "",
    }

    try:
        run_monitoring(form_data)
    except ValidationError as exc:
        LOGGER.error("Falha de validacao: %s", exc)
        print(f"Erro de validacao: {exc}")
    except Exception as exc:
        LOGGER.exception("Erro nao tratado na execucao CLI: %s", exc)
        print(f"Erro durante execucao: {exc}")


def _start_background_monitoring(form_data: dict, state) -> None:
    stop_event = threading.Event()
    state["stop_event"] = stop_event
    state["running"] = True
    state["error"] = ""
    state["last_message"] = "Monitoramento iniciado."
    state["stats"] = None

    def update_stats(stats: MonitorStats) -> None:
        state["stats"] = {
            "started_at": stats.started_at,
            "monitored_label": stats.monitored_label,
            "checks_performed": stats.checks_performed,
            "changes_detected": stats.changes_detected,
            "current_value": stats.current_value,
            "initial_value": stats.initial_value,
            "last_change_at": stats.last_change_at,
            "locator_description": stats.locator_description,
        }

    def worker() -> None:
        try:
            update_stats(run_monitoring(form_data, on_stats=update_stats, stop_event=stop_event))
            if stop_event.is_set():
                state["last_message"] = "Monitoramento interrompido."
            else:
                state["last_message"] = "Monitoramento finalizado."
        except ValidationError as exc:
            state["error"] = str(exc)
            LOGGER.error("Falha de validacao na UI: %s", exc)
        except Exception as exc:
            state["error"] = str(exc)
            LOGGER.exception("Erro nao tratado na interface web: %s", exc)
        finally:
            state["running"] = False

    thread = threading.Thread(target=worker, daemon=True)
    state["thread"] = thread
    thread.start()


def run_streamlit() -> None:
    import streamlit as st

    st.set_page_config(page_title="Auction Assistant", page_icon="PS", layout="centered")
    st.title("Assistente de Lances para Sites de Leilao")
    st.write(
        "Informe a URL e o nome do item que deseja monitorar. A interface tenta localizar o valor automaticamente, envia avisos por email e registra estatisticas da execucao."
    )

    if "monitor_state" not in st.session_state:
        st.session_state.monitor_state = {
            "running": False,
            "thread": None,
            "stop_event": None,
            "stats": None,
            "error": "",
            "last_message": "",
        }
    if "candidate_fields" not in st.session_state:
        st.session_state.candidate_fields = []
    if "candidate_error" not in st.session_state:
        st.session_state.candidate_error = ""

    monitor_state = st.session_state.monitor_state
    form_defaults = build_default_form_data()

    st.subheader("Descobrir itens da pagina")
    discovery_col1, discovery_col2 = st.columns([4, 1])
    with discovery_col1:
        discovery_url = st.text_input(
            "URL para analisar",
            value=form_defaults["source_url"],
            key="discovery_url",
        )
    with discovery_col2:
        discover_clicked = st.button("Analisar")

    if discover_clicked:
        try:
            st.session_state.candidate_fields = discover_page_candidates(discovery_url, form_defaults["timeout_seconds"])
            st.session_state.candidate_error = ""
        except Exception as exc:
            st.session_state.candidate_fields = []
            st.session_state.candidate_error = str(exc)

    if st.session_state.candidate_error:
        st.error(st.session_state.candidate_error)

    if st.session_state.candidate_fields:
        options = {
            f"{item.label} | valor atual: {item.value}": item
            for item in st.session_state.candidate_fields
        }
        selected_option = st.selectbox(
            "Itens encontrados na pagina",
            list(options.keys()),
            key="candidate_selector",
        )
        selected_candidate = options[selected_option]
        st.caption(selected_candidate.context)
        st.success(f"Item selecionado para monitoramento: {selected_candidate.label}")
    else:
        selected_candidate = None
        st.caption("Clique em Analisar para listar automaticamente os itens encontrados com valor numerico.")

    with st.form("auction_form"):
        form_data = {
            "user_name": st.text_input("Seu nome", value=form_defaults["user_name"]),
            "source_url": st.text_input("URL da pagina a monitorar", value=discovery_url or form_defaults["source_url"]),
            "selector": st.text_input(
                "Nome exato da acao, moeda ou item que deseja acompanhar",
                value=selected_candidate.label if selected_candidate else form_defaults["selector"],
                help="Exemplo: PETR4, VALE3, Dolar, Euro, Lance atual ou nome do lote. Evite termos genericos como cotacoes.",
                disabled=selected_candidate is not None,
            ),
            "selector_type": "smart",
            "interval_seconds": st.number_input(
                "Verificar a cada quantos segundos",
                min_value=1.0,
                value=float(form_defaults["interval_seconds"]),
            ),
            "timeout_seconds": st.number_input(
                "Tempo maximo de espera da pagina (s)",
                min_value=1.0,
                max_value=300.0,
                value=float(form_defaults["timeout_seconds"]),
            ),
            "email_sender": st.text_input("Email que vai enviar os avisos", value=form_defaults["email_sender"]),
            "email_recipient": st.text_input(
                "Email que vai receber os avisos",
                value=form_defaults["email_recipient"],
            ),
            "email_password": form_defaults["email_password"],
            "smtp_server": st.text_input("Servidor SMTP", value=form_defaults["smtp_server"]),
            "smtp_port": st.number_input(
                "Porta SMTP",
                min_value=1,
                max_value=65535,
                value=int(form_defaults["smtp_port"]),
            ),
            "target_url": "",
            "target_input_selector": "",
            "target_button_selector": "",
        }

        with st.expander("Configuracao avancada"):
            advanced_type = st.selectbox(
                "Modo de localizacao",
                ["smart", "text", "css", "xpath", "regex"],
                help="Use outro modo apenas se a localizacao automatica nao funcionar.",
            )
            target_url = st.text_input("URL da pagina publica para interacao (opcional)")
            target_input_selector = st.text_input("Seletor do campo de texto (opcional)")
            target_button_selector = st.text_input("Seletor do botao (opcional)")

        form_data["selector_type"] = advanced_type
        if selected_candidate is not None:
            form_data["selector"] = selected_candidate.label
        form_data["target_url"] = target_url
        form_data["target_input_selector"] = target_input_selector
        form_data["target_button_selector"] = target_button_selector

        submitted = st.form_submit_button("Iniciar monitoramento")

    if submitted:
        if monitor_state["running"]:
            st.warning("Ja existe um monitoramento em execucao nesta sessao.")
        else:
            try:
                LOGGER.info(
                    "Usuario %s iniciou monitoramento simplificado da URL %s para %s",
                    form_data.get("user_name", "").strip() or "desconhecido",
                    form_data.get("source_url", "").strip(),
                    form_data.get("selector", "").strip(),
                )
                _start_background_monitoring(form_data, monitor_state)
                st.success("Monitoramento iniciado em segundo plano.")
            except ValidationError as exc:
                st.error(str(exc))

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Atualizar estatisticas"):
            st.rerun()
    with col2:
        if st.button("Parar monitoramento", disabled=not monitor_state["running"]):
            if monitor_state["stop_event"]:
                monitor_state["stop_event"].set()
            st.rerun()

    if monitor_state["last_message"]:
        st.info(monitor_state["last_message"])
    if monitor_state["error"]:
        st.error(monitor_state["error"])

    stats = monitor_state.get("stats")
    if stats:
        st.subheader("Estatisticas")
        metric_col1, metric_col2, metric_col3 = st.columns(3)
        metric_col1.metric("Consultas", stats.get("checks_performed", 0))
        metric_col2.metric("Mudancas", stats.get("changes_detected", 0))
        metric_col3.metric("Valor atual", stats.get("current_value", "-"))

        st.text_input("Item monitorado", value=stats.get("monitored_label", ""), disabled=True)
        st.text_input("Valor inicial", value=stats.get("initial_value", ""), disabled=True)
        st.text_input("Ultima alteracao", value=stats.get("last_change_at", ""), disabled=True)
        st.text_area("Localizacao encontrada", value=stats.get("locator_description", ""), disabled=True, height=120)
    else:
        st.caption("As estatisticas aparecerao aqui depois que a primeira leitura for concluida.")


if __name__ == "__main__":
    mode = os.getenv("AUCTION_ASSISTANT_MODE", "cli").lower()
    if mode == "web":
        run_streamlit()
    else:
        run_cli()
