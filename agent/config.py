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
    k = os.getenv("GROQ_API_KEY", "").strip()
    if not k:
        # Re-attempt load in case this is a thread/subprocess context
        from dotenv import load_dotenv
        load_dotenv(BASE_DIR / ".env", override=True)
        k = os.getenv("GROQ_API_KEY", "").strip()
    if not k:
        raise ValueError("GROQ_API_KEY missing from .env")
    return k

def github_token() -> str:
    t = os.getenv("GITHUB_TOKEN", "").strip()
    if not t:
        from dotenv import load_dotenv
        load_dotenv(BASE_DIR / ".env", override=True)
        t = os.getenv("GITHUB_TOKEN", "").strip()
    return t
