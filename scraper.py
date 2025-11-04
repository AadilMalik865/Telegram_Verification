import csv
import os
import tempfile
from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.tl.types import PeerChannel
from client_manager import get_client

BASE_DIR = tempfile.gettempdir()

async def fetch_messages(post_urls, phone, logger=print, stop_event=None):
    """
    Simplified version: only checks if URL is active or dead
    """
    client = get_client(phone)
    logger(f"📡 Checking {len(post_urls)} URLs…")

    # CSV setup
    file_name = "telegram_data.csv"
    file_path = os.path.join(BASE_DIR, file_name)

    with open(file_path, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=['channel_url', 'status'])
        writer.writeheader()

        for url in post_urls:
            if stop_event and stop_event.is_set():
                logger("🛑 Stop signal received, stopping...")
                return file_path

            try:
                # Determine if it's private or public
                if "/c/" in url:  # Private channel
                    channel_id = int(url.split("/c/")[1].split("/")[0])
                    entity = await client.get_entity(PeerChannel(channel_id))
                else:  # Public channel/profile
                    username = url.rstrip("/").split("/")[-1]
                    entity = await client.get_entity(username)

                # If we reach here, entity exists
                status = "active"
                logger(f"✅ {url} is active")

            except Exception as e:
                # If Telegram returns error, mark as dead
                status = "dead"
                logger(f"❌ {url} is dead")

            writer.writerow({'channel_url': url, 'status': status})

    return file_path
