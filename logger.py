import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


LOG_DIR = Path("logs")
LOG_FILE = LOG_DIR / "auction_assistant.log"


def setup_logger(name: str = "auction_assistant") -> logging.Logger:
    """
    Configura o logger para o assistente de leil oes.

    Parameters
    ----------
    name : str, optional
        O nome do logger a ser criado. O padr o   "auction_assistant".

    Returns
    -------
    logging.Logger
        O logger configurado.

    Notes
    -----
    O logger configurado ir  escrito em um arquivo de log rotativo,
    que ser  substitu do quando atingir 1MB. At 3 arquivos de log
    antigos ser o mantidos. O logger tamb m ir  escrito na sa da padr o.
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    file_handler = RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=3)
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    logger.propagate = False
    return logger
