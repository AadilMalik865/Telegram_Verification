# client_manager.py
import os
import asyncio
import re
from telethon import TelegramClient
import nest_asyncio

nest_asyncio.apply()

API_ID = 29670565
API_HASH = "ede130708ffc720e331e404db9fe623c"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SESSION_DIR = os.path.join(BASE_DIR, "sessions")
os.makedirs(SESSION_DIR, exist_ok=True)

# Single global event loop
loop = asyncio.get_event_loop()

clients = {}

def normalize_phone(phone: str) -> str:
    """
    Normalize phone number to canonical form for session keys:
    - Remove all non-digit characters
    - Ensure it includes country code; if it starts with '0' or lacks country code,
      do NOT try to guess — just keep digits. Caller should pass full number.
    - Return with leading + removed (we'll use digits-only string as filename/key)
    """
    if not phone:
        return ""
    # Remove spaces, parentheses, dashes, plus signs, etc.
    digits = re.sub(r'\D', '', phone)
    return digits  # use digits-only as canonical key

def _session_path_for(phone: str) -> str:
    key = normalize_phone(phone)
    # avoid empty filenames
    fname = key if key else "anon"
    return os.path.join(SESSION_DIR, fname)

def get_client(phone):
    """
    Returns a singleton TelegramClient per normalized phone number
    """
    key = normalize_phone(phone)
    if key not in clients:
        session_path = _session_path_for(key)
        # TelegramClient accepts session string path (without extension)
        clients[key] = TelegramClient(session_path, API_ID, API_HASH, loop=loop)
        # connect synchronously on startup for this client
        run_async(clients[key].connect())
    return clients[key]

def run_async(coro):
    """
    Safe runner for coroutines
    """
    return loop.run_until_complete(coro)

# expose normalize helper for other modules
__all__ = ["get_client", "run_async", "normalize_phone"]
