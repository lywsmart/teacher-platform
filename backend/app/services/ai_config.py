import tempfile
from pathlib import Path

from app.core.config import get_settings


def key_path() -> Path:
    return get_settings().storage_root / ".private" / "deepseek.key"


def configured_key() -> tuple[str, str | None]:
    try:
        return key_path().read_text(encoding="ascii"), "admin"
    except FileNotFoundError:
        key = get_settings().deepseek_api_key
        return key, "environment" if key else None


def save_key(key: str) -> None:
    path = key_path()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.NamedTemporaryFile(mode="w", encoding="ascii", dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(key)
            stream.close()
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)


def clear_key() -> None:
    key_path().unlink(missing_ok=True)
