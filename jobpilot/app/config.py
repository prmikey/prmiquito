import os
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
ROOT_DIR = APP_DIR.parent


def _load_dotenv() -> None:
    env_file = ROOT_DIR / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


_load_dotenv()

OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "http://localhost:11434/v1").rstrip("/")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "ollama")
LLM_MODEL = os.environ.get("LLM_MODEL", "hermes3")
DB_PATH = ROOT_DIR / os.environ.get("JOBPILOT_DB", "data/jobpilot.db")
CRAWL_INTERVAL_HOURS = float(os.environ.get("CRAWL_INTERVAL_HOURS", "4"))
PORT = int(os.environ.get("PORT", "8300"))
COMPANIES_FILE = ROOT_DIR / "companies.json"
