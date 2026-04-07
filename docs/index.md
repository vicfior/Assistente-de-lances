# Documentacao do Assistente de Lances

## Visao geral

O sistema monitora um campo dinamico em uma pagina Web e executa duas acoes quando detecta alteracao:

1. Publica uma mensagem em outra pagina publica.
2. Envia notificacao por email.

## Configuracao para leigos

O fluxo recomendado e usar a interface web com:

```bash
streamlit run app.py
```

No Windows, tambem existe o arquivo `iniciar_interface_web.bat`.

Na interface:

1. Informe a URL da pagina monitorada.
2. No campo monitorado, tente primeiro um texto visivel da propria pagina.
3. Selecione `Texto visivel na pagina`.
4. Informe o email remetente, o destinatario e a senha ou App Password.
5. Preencha a pagina publica de destino e seus seletores.

## Modulos

### `main.py`

Responsavel pela interface CLI e pela interface Web com Streamlit.

### `app.py`

Ponto de entrada simplificado para abrir a interface web sem depender de variavel de ambiente.

### `monitor.py`

Contem a logica de captura recorrente de valores e deteccao de mudancas.

### `browser.py`

Centraliza automacao com Playwright, leitura de campos dinamicos e interacao com paginas publicas. Agora aceita localizacao por `text`, `css`, `xpath` e `regex`.

### `notifier.py`

Envia notificacoes externas por pagina Web e por email SMTP.

### `validators.py`

Valida entradas obrigatorias, URL, timeout, nome e configuracoes SMTP.

### `logger.py`

Configura logs rotativos em arquivo e console.

## Fluxo de execucao

1. Usuario informa os dados da tarefa.
2. Entradas sao validadas.
3. O navegador carrega a pagina monitorada.
4. O sistema localiza o elemento configurado.
5. O valor e comparado continuamente.
6. Ao detectar alteracao:
   - monta a mensagem com valor anterior e novo;
   - envia a mensagem para outra pagina;
   - envia o email de notificacao.

## Logs

O sistema registra:

- acoes iniciadas pelo usuario;
- localizacao do campo monitorado;
- alteracoes detectadas;
- erros e excecoes;
- encerramento do monitoramento.

## Riscos e limitacoes

- Paginas protegidas por captcha, anti-bot ou login avancado podem exigir adaptacoes.
- O uso de Gmail por interface Web e menos estavel do que SMTP.
- Regex opera sobre o texto bruto consolidado da pagina e pode capturar mais de uma ocorrencia se o padrao for amplo.
