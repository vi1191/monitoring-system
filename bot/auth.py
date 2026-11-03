# auth.py
import json
import os

from config import CACHE_FILE

CRED_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "credentials.json")

def _load_all() -> dict:
    if not os.path.exists(CRED_FILE):
        return {}
    try:
        with open(CRED_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def _save_all(data: dict) -> None:
    with open(CRED_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# --- ЕТС ---
def load_credentials():
    data = _load_all()
    return data.get("ets_login", ""), data.get("ets_pass", "")

def save_credentials(login: str, password: str) -> None:
    data = _load_all()
    data["ets_login"] = login
    data["ets_pass"] = password
    _save_all(data)

# --- ЕСТП (логин/пароль) ---
def load_estp_credentials():
    data = _load_all()
    return data.get("estp_login", ""), data.get("estp_pass", "")

def save_estp_credentials(login: str, password: str) -> None:
    data = _load_all()
    data["estp_login"] = login
    data["estp_pass"] = password
    _save_all(data)

# --- ЕСТП (Сотрудник ФИО+Тел) ---  <-- ЭТО НОВОЕ
def load_estp_employee():
    data = _load_all()
    return data.get("estp_employee", "")

def save_estp_employee(employee_str: str) -> None:
    data = _load_all()
    data["estp_employee"] = employee_str
    _save_all(data)