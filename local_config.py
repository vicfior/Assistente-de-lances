from __future__ import annotations

import json
from pathlib import Path


SECRETS_FILE = Path("local_secrets.json")


def load_local_secrets() -> dict:
    if not SECRETS_FILE.exists():
        return {}

    try:
        return json.loads(SECRETS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
