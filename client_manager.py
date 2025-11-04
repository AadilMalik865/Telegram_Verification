# client_manager.py
import os, asyncio
from telethon import TelegramClient
import nest_asyncio

nest_asyncio.apply()

API_ID = 29670565
API_HASH = "ede130708ffc720e331e404db9fe623c"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SESSION_DIR = os.path.join(BASE_DIR, "sessions")
os.makedirs(SESSION_DIR, exist_ok=True)

# ✅ Single global event loop
loop = asyncio.get_event_loop()

clients = {}

def get_client(phone):
    """
    Returns a singleton TelegramClient per phone number
    """
    if phone not in clients:
        session_path = os.path.join(SESSION_DIR, phone)
        clients[phone] = TelegramClient(session_path, API_ID, API_HASH, loop=loop)
        loop.run_until_complete(clients[phone].connect())
    return clients[phone]

def run_async(coro):
    """
    Safe runner for coroutines
    """
    return loop.run_until_complete(coro)
