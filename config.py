"""读取项目根目录下的 .env 配置文件。支持多个邮箱账号（EMAIL1_*、EMAIL2_*…）。"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _load_dotenv(path):
    """极简 .env 解析：忽略注释和空行，支持 value 用引号包裹。"""
    values = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        values[key] = value
    return values


_DOTENV = _load_dotenv(BASE_DIR / ".env")


def _get(name, default=None):
    return os.environ.get(name) or _DOTENV.get(name) or default


class Account:
    def __init__(self, address, auth_code, imap_server, imap_port):
        self.address = address
        self.auth_code = auth_code
        self.imap_server = imap_server
        self.imap_port = imap_port


def _load_accounts():
    """读取 EMAIL1_* ~ EMAIL5_*，地址和授权码都填了的才算一个账号。"""
    accounts = []
    for i in range(1, 6):
        addr = _get(f"EMAIL{i}_ADDRESS", "").strip()
        code = _get(f"EMAIL{i}_AUTH_CODE", "").strip()
        if not addr or not code:
            continue
        server = _get(f"EMAIL{i}_SERVER", "").strip() or "imap.163.com"
        port = int(_get(f"EMAIL{i}_PORT", "993"))
        accounts.append(Account(addr, code, server, port))
    return accounts


class Config:
    def __init__(self):
        self.accounts = _load_accounts()
        self.deepseek_api_key = _get("DEEPSEEK_API_KEY", "")
        self.deepseek_model = _get("DEEPSEEK_MODEL", "deepseek-chat")
        self.lookback_days = int(_get("LOOKBACK_DAYS", "2"))
        self.poll_interval_seconds = int(_get("POLL_INTERVAL_SECONDS", "300"))
        self.max_body_chars = int(_get("MAX_BODY_CHARS", "3000"))
        self.store_path = BASE_DIR / _get("STORE_PATH", "data.json")


config = Config()


def missing_fields():
    """返回还没填的必填项。"""
    missing = []
    if not config.accounts:
        missing.append("EMAIL1_ADDRESS + EMAIL1_AUTH_CODE")
    if not config.deepseek_api_key:
        missing.append("DEEPSEEK_API_KEY")
    return missing


def is_configured():
    return not missing_fields()
