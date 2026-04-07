# Assistente de Lances para Sites de Leilao

Aplicacao em Python para monitorar dinamicamente um campo em uma pagina de leilao, detectar mudancas, publicar a alteracao em outra pagina publica e enviar notificacoes por email.

## Funcionalidades

- Recebe URL, seletor e configuracoes do usuario.
- Aceita `text`, `css`, `xpath` e `regex` para localizar o campo dinamico.
- Registra logs de execucao, erros, alteracoes detectadas e a posicao/localizacao do campo.
- Monitora continuamente o valor e dispara automacoes quando detecta mudanca.
- Interage com uma segunda pagina publica, preenchendo uma mensagem e clicando em um botao.
- Envia notificacao por email via SMTP, incluindo Gmail com App Password.
- Oferece CLI interativa e interface Web com Streamlit.
- Inclui testes automatizados com `pytest`.

## Estrutura

```text
.
|-- app.py
|-- main.py
|-- monitor.py
|-- browser.py
|-- notifier.py
|-- logger.py
|-- validators.py
|-- iniciar_interface_web.bat
|-- tests/
|   `-- test_monitor.py
|-- docs/
|   `-- index.md
|-- requirements.txt
`-- README.md
```

## Instalacao

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

## Execucao CLI

```bash
python main.py
```

## Execucao Web

```bash
streamlit run app.py
```

No Windows, tambem e possivel iniciar a interface por `iniciar_interface_web.bat`.

## Configuracao de email

Para Gmail, use:

- SMTP server: `smtp.gmail.com`
- SMTP port: `587`
- App Password informada na interface ou pela variavel de ambiente `AUCTION_ASSISTANT_SMTP_PASSWORD`

## Big O

- Monitoramento: `O(c)` para `c` ciclos de verificacao.
- Parsing da pagina: `O(n)` sobre o tamanho do HTML/texto processado.
- Deteccao de mudancas: `O(1)` para comparar o valor anterior com o novo.

## Testes

```bash
pytest
```

## Documentacao

```bash
mkdocs build
mkdocs serve
```

## Observacoes importantes

- O sistema continua validando URL, timeout, email e campos obrigatorios para evitar falhas por entrada invalida.
- O tipo `text` foi adicionado como alternativa aos seletores tecnicos `css`, `xpath` e `regex`.
- A automacao da pagina de destino depende dos seletores corretos do formulario publico escolhido.
- O monitoramento registra eventos em `logs/auction_assistant.log`.
