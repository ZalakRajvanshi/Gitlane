"""Config — loads .env and settings.json"""
import os, json
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR  = Path(__file__).parent.parent
DATA_DIR  = BASE_DIR / "data"
LOGS_DIR  = BASE_DIR / "logs"
WEB_DIR   = BASE_DIR / "web"
CFG_FILE  = BASE_DIR / "settings.json"

load_dotenv(BASE_DIR / ".env", override=True)

DEFAULTS = {
    "github_username": "",
    "groq_model": "llama3-70b-8192",
    "timezone": "Asia/Kolkata",
    "notify_on_boot": True,
    "web_port": 7123,
    "sprint_days": 7,
    "streak_warning_days": 2,
    "max_commits": 60,
    "onboarded": False,
}

def load() -> dict:
    cfg = DEFAULTS.copy()
    if CFG_FILE.exists():
        cfg.update(json.loads(CFG_FILE.read_text()))
    return cfg

def save(cfg: dict):
    DATA_DIR.mkdir(exist_ok=True)
    CFG_FILE.write_text(json.dumps(cfg, indent=2))

def groq_key() -> str:
    # Try env var first
    k = os.getenv("GROQ_API_KEY", "").strip()
    if k:
        return k
    # Direct file read as fallback — works in any thread/subprocess context
    env_file = BASE_DIR / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("GROQ_API_KEY="):
                k = line.split("=", 1)[1].strip()
                if k:
                    os.environ["GROQ_API_KEY"] = k
                    return k
    raise ValueError("GROQ_API_KEY missing from .env")

def github_token() -> str:
    t = os.getenv("GITHUB_TOKEN", "").strip()
    if t:
        return t
    env_file = BASE_DIR / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("GITHUB_TOKEN="):
                t = line.split("=", 1)[1].strip()
                if t:
                    os.environ["GITHUB_TOKEN"] = t
                    return t
    return ""
