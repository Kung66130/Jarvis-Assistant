import json
import os
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
ENV_PATH = APP_DIR / ".env"
LEGACY_CONFIG_PATH = APP_DIR / "config.json"
SESSION_MEMORY_PATH = APP_DIR / "session_memory.json"


def load_dotenv(env_path: Path = ENV_PATH) -> None:
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def get_env_value(env_name: str, *, allow_legacy_config: bool = False) -> str | None:
    load_dotenv()
    value = os.getenv(env_name)
    if value:
        return value

    if allow_legacy_config and LEGACY_CONFIG_PATH.exists():
        try:
            legacy_config = json.loads(LEGACY_CONFIG_PATH.read_text(encoding="utf-8"))
            legacy_value = legacy_config.get(env_name)
            if legacy_value:
                return str(legacy_value)
        except (json.JSONDecodeError, OSError):
            return None

    return None


def get_api_key(env_name: str = "GEMINI_API_KEY") -> str | None:
    return get_env_value(env_name, allow_legacy_config=True)


def load_session_memory(max_turns: int = 6) -> list[dict]:
    if not SESSION_MEMORY_PATH.exists():
        return []

    try:
        payload = json.loads(SESSION_MEMORY_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []

    turns = payload.get("turns", [])
    if not isinstance(turns, list):
        return []

    return turns[-max_turns:]


def save_session_memory(turns: list[dict]) -> None:
    payload = {"turns": turns[-12:]}
    SESSION_MEMORY_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
