from __future__ import annotations

import os
import threading
from getpass import getpass
from typing import Optional

from browser import BrowserAutomation, CandidateField
from local_config import load_local_secrets
from logger import setup_logger
from monitor import AuctionMonitor, MonitorStats
from notifier import EmailNotifier, NotificationService
from validators import ValidationError, validate_user_input


LOGGER = setup_logger()


def build_default_form_data() -> dict:
    """
    Constroi um dicionario com os valores padrao para a interface do usuario.

    O dicionario contem os seguintes campos:
    - user_name: nome do usuario que esta executando o programa.
    - source_url: URL da pagina de leilao a ser monitorada.
    - selector: seletor CSS ou XPath do campo dinamico a ser monitorado.
    - selector_type: tipo de seletor (css, xpath, smart).
    - interval_seconds: intervalo de tempo em segundos entre verificacoes.
    - timeout_seconds: tempo de espera em segundos para a abertura da pagina.
    - target_url: URL da pagina alvo que sera enviada a notificacao.
    - target_input_selector: seletor CSS ou XPath do campo de entrada na pagina alvo.
    - target_button_selector: seletor CSS ou XPath do botao de envio na pagina alvo.
    - email_sender: endereco de email do remetente.
    - email_recipient: endereco de email do destinatario.
    - smtp_server: Servidor SMTP do remetente.
    - smtp_port: Porta SMTP do remetente.
    - email_password: Senha ou App Password do remetente.

    :return: Um dicionario com os valores padrao para a interface do usuario.
    """
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
    """
    Descobre os campos dinamicos em uma pagina de leilao.

    Recebe uma URL e um timeout em segundos e retorna uma lista de objetos 
    CandidateField que representam os campos 
    dinamicos encontrados na pagina.

    :param url: URL da pagina de leilao a ser analisada.
    :param timeout_seconds: Tempo de espera em segundos para a abertura da pagina.
    :return: Uma lista de objetos CandidateField que representam 
    os campos dinamicos encontrados na pagina.
    """
    with BrowserAutomation(timeout_seconds=timeout_seconds, headless=True) as browser:
        return browser.discover_candidate_fields(url)


def run_monitoring(
    form_data: dict,
    on_stats=None,
    stop_event: Optional[threading.Event] = None,
) -> MonitorStats:
    """
    Executa o monitoramento de uma pagina de leilao.

    Recebe um dicionario com os valores de entrada do usuario e opcionalmente uma funcao de 
    callback para atualizar os valores de estatistica e 
    um evento de parada para interromper o monitoramento.

    :param form_data: Dicionario com os valores de entrada do usuario.
    :param on_stats: Funcao de callback para atualizar os valores de estatistica.
    :param stop_event: Opcionalmente, um evento de parada para interromper o monitoramento.
    :return: Um objeto MonitorStats com as informacoes de estatistica do monitoramento.

    :raises ValidationError: Se os valores de entrada do usuario forem invalidos.
    """
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

    with BrowserAutomation(
        timeout_seconds=validated.timeout_seconds, headless=True
    ) as browser:
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
                field_content=snapshot.content_preview
                or snapshot.locator_description,
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
    """
    Executa a interface de linha de comando para o Assistente de Lances.

    Pede ao usuario informar as configuracoes do monitoramento e executa o fluxo de
    monitoramento.

    :raises ValidationError: Se as entradas do usuario forem invalidas.
    :raises Exception: Se ocorrer um erro nao tratado durante a execucao.
    """
    print("Assistente de Lances para Sites de Leilao")
    form_data = {
        "user_name": input("Nome do usuario: "),
        "source_url": input("URL a monitorar: "),
        "selector": input("Nome do item/acao a monitorar: "),
        "selector_type": input(
            "Modo de localizacao [smart/text/css/xpath/regex]: "
        ) or "smart",
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


def _start_background_monitoring(form_data: dict, state: dict) -> None:
    """
    Inicia o monitoramento em segundo plano.

    A funcao _start_background_monitoring inicia o monitoramento em segundo plano,
    criando um thread que executa o fluxo de monitoramento.

    :param form_data: Dicionario com configuracoes do monitoramento.
    :param state: Dicionario que armazena o estado do monitoramento.
    """
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
            update_stats(
                run_monitoring(
                    form_data, on_stats=update_stats, stop_event=stop_event
                )
            )
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

def test_email_connection(form_data: dict) -> None:
    """
    Testa a conexão SMTP com o email

    Esta função testa se a conexão SMTP com o email esta funcionando para ter certeza que os dados serão
    enviados

    :param form_data: Dicionario com configuracoes do monitoramento.
    :raises ValidationError: Se as entradas do usuario forem invalidas.
    """
    
    local_secrets = load_local_secrets()
    
    
    smtp_password = (
        local_secrets.get("email_password")
        or os.getenv("AUCTION_ASSISTANT_SMTP_PASSWORD")
    )
    
    if not smtp_password:
        raise ValueError("Senha não encontrada. Verifique o arquivo local_secrets.json ou defina a variável de ambiente.")
    
    if not form_data["email_recipient"]:
        raise ValueError("e-mail destinatario não encontrado")

    
    email_notifier = EmailNotifier(
        smtp_server=form_data["smtp_server"],
        smtp_port=int(form_data["smtp_port"]),
        sender_email=form_data["email_sender"],
        sender_password=smtp_password,
        logger=LOGGER,
    )
    
    
    email_notifier.send_email(
        recipient= form_data["email_recipient"],
        subject="Teste do Assistente de Leilões",
        body="O e-mail remetente esta configurado corretamente."
    )


def run_streamlit() -> None:
    """
    Executa a interface web para o Assistente de Lances.

    Utiliza a biblioteca Streamlit para criar uma interface interativa para o usuario
    informar as configuracoes do monitoramento e executar o fluxo de monitoramento.

    :raises ValidationError: Se as entradas do usuario forem invalidas.
    :raises Exception: Se ocorrer um erro nao tratado durante a execucao.
    """
    import streamlit as st

    st.set_page_config(
        page_title="Auction Assistant", page_icon="PS", layout="centered"
    )
    st.title("Assistente de Lances para Sites de Leilao")
    st.write(
        "Informe a URL e o nome do item que deseja monitorar. A interface tenta "
        "localizar o valor automaticamente, envia avisos por email e registra "
        "estatisticas da execucao."
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
            st.session_state.candidate_fields = discover_page_candidates(
                discovery_url, form_defaults["timeout_seconds"]
            )
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
        st.success(
            f"Item selecionado para monitoramento: {selected_candidate.label}"
        )
    else:
        selected_candidate = None
        st.caption(
            "Clique em Analisar para listar automaticamente os itens "
            "encontrados com valor numerico."
        )

    with st.form("auction_form"):
        form_data = {
            "user_name": st.text_input(
                "Seu nome", value=form_defaults["user_name"]
            ),
            "source_url": st.text_input(
                "URL da pagina a monitorar",
                value=discovery_url or form_defaults["source_url"],
            ),
            "selector": st.text_input(
                "Nome exato da acao, moeda ou item que deseja acompanhar",
                value=selected_candidate.label
                if selected_candidate
                else form_defaults["selector"],
                help=(
                    "Exemplo: PETR4, VALE3, Dolar, Euro, Lance atual ou nome do "
                    "lote. Evite termos genericos como cotacoes."
                ),
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
            "email_sender": st.text_input(
                "Email que vai enviar os avisos",
                value=form_defaults["email_sender"],
            ),
            "email_recipient": st.text_input(
                "Email que vai receber os avisos",
                value=form_defaults["email_recipient"],
            ),
            "email_password": form_defaults["email_password"],
            "smtp_server": st.text_input(
                "Servidor SMTP", value=form_defaults["smtp_server"]
            ),
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
            target_url = st.text_input(
                "URL da pagina publica para interacao (opcional)"
            )
            target_input_selector = st.text_input(
                "Seletor do campo de texto (opcional)"
            )
            target_button_selector = st.text_input("Seletor do botao (opcional)")

        form_data["selector_type"] = advanced_type
        if selected_candidate is not None:
            form_data["selector"] = selected_candidate.label
        form_data["target_url"] = target_url
        form_data["target_input_selector"] = target_input_selector
        form_data["target_button_selector"] = target_button_selector

        #submitted = st.form_submit_button("Iniciar monitoramento")

        col_test1, col_test2 = st.columns(2)
        with col_test1:
            submitted = st.form_submit_button("Iniciar monitoramento")
        with col_test2:
            test_email = st.form_submit_button("Testar Conexão de E-mail")

    
    if test_email:
        with st.spinner("Testando conexão SMTP e enviando e-mail."):
            try:
                
                test_email_connection(form_data)
                st.success("E-mail de teste enviado com sucesso.")
            except Exception as exc:
                st.error(f"Falha no envio: {exc}")

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

        st.text_input(
            "Item monitorado", value=stats.get("monitored_label", ""), disabled=True
        )
        st.text_input(
            "Valor inicial", value=stats.get("initial_value", ""), disabled=True
        )
        st.text_input(
            "Ultima alteracao",
            value=stats.get("last_change_at", ""),
            disabled=True,
        )
        st.text_area(
            "Localizacao encontrada",
            value=stats.get("locator_description", ""),
            disabled=True,
            height=120,
        )
    else:
        st.caption(
            "As estatisticas aparecerao aqui depois que a primeira leitura for concluida."
        )


if __name__ == "__main__":
    mode = os.getenv("AUCTION_ASSISTANT_MODE", "cli").lower()
    if mode == "web":
        run_streamlit()
    else:
        run_cli()