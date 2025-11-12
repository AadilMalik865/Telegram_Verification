import csv
import os
import tempfile
import re
from telethon.tl.types import PeerChannel
from client_manager import get_client

BASE_DIR = tempfile.gettempdir()

def extract_channel_info_from_url(url):
    """
    Returns (channel_identifier, msg_id, is_private)
    """
    if not url or not url.strip():
        return None, None, None

    private_match = re.match(r'https://t.me/c/(\d+)(?:/(\d+))?', url)
    if private_match:
        channel_id = int(private_match.group(1))
        msg_id = int(private_match.group(2)) if private_match.group(2) else None
        return channel_id, msg_id, True

    public_post_match = re.match(r'https://t.me/([a-zA-Z0-9_]+)/(\d+)', url)
    if public_post_match:
        username = public_post_match.group(1)
        msg_id = int(public_post_match.group(2))
        return username, msg_id, False

    public_profile_match = re.match(r'https://t.me/([a-zA-Z0-9_]+)$', url)
    if public_profile_match:
        username = public_profile_match.group(1)
        return username, None, False

    return None, None, None  # Invalid URL


async def fetch_messages(post_urls, phone, logger=print, stop_event=None):
    client = get_client(phone)
    logger(f"📡 Checking {len(post_urls)} URLs…")

    from client_manager import normalize_phone
    key = normalize_phone(phone)
    file_name = f"telegram_data_{key}.csv" if key else "telegram_data.csv"
    file_path = os.path.join(BASE_DIR, file_name)

    with open(file_path, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(
            file, 
            fieldnames=['post_url', 'channel_name', 'views', 'post_description', 'post_status']
        )
        writer.writeheader()

        for url in post_urls:
            if stop_event and stop_event.is_set():
                logger("🛑 Stop signal received, stopping...")
                return file_path

            if not url or not url.strip():
                writer.writerow({
                    'post_url': "N/A",
                    'channel_name': "N/A",
                    'views': 0,
                    'post_description': "No URL provided",
                    'post_status': "Dead"
                })
                continue

            try:
                channel_identifier, msg_id, is_private = extract_channel_info_from_url(url)

                if not channel_identifier:
                    writer.writerow({
                        'post_url': url,
                        'channel_name': "N/A",
                        'views': 0,
                        'post_description': "Invalid URL",
                        'post_status': "Dead"
                    })
                    logger(f"{url} → URL invalid, marked Dead")
                    continue

                # Fetch channel name
                channel_name = "Unknown"
                entity = None
                try:
                    if is_private:
                        entity = await client.get_entity(PeerChannel(channel_identifier))
                    else:
                        entity = await client.get_entity(channel_identifier)
                    channel_name = getattr(entity, "title", str(channel_identifier))
                except Exception:
                    entity = None

                views = 0
                post_description = "No description"
                status = "Dead"

                # Check message if msg_id provided
                if msg_id and entity:
                    try:
                        message = await client.get_messages(entity, ids=msg_id)
                        if message and message.text:
                            post_description = message.text
                        else:
                            post_description = "No description"

                        views = message.views if message and hasattr(message, "views") else 0

                        # Determine status
                        if (not post_description) or re.search(r"copyright infringement", post_description, re.IGNORECASE):
                            status = "Dead"
                        else:
                            status = "Active"
                    except Exception:
                        post_description = "Message not found"
                        status = "Dead"

                # If no msg_id, check entity existence
                elif entity:
                    post_description = "No specific post provided"
                    status = "Active"  # Entity exists
                else:
                    post_description = "Entity not found"
                    status = "Dead"
                

                # Extra check: if description empty or blocked, mark Dead
                if channel_name == "Unknown":
                    status = "User Has Not Joined Channel"

                # If message was not found or description empty
                elif (not post_description) or post_description.lower() in ["no description", "message not found"]:
                    status = "Dead"

                writer.writerow({
                    'post_url': url,
                    'channel_name': channel_name,
                    'views': views,
                    'post_description': post_description,
                    'post_status': status
                })

                logger(f"{url} → post_status: {status}")

            except Exception as e:
                writer.writerow({
                    'post_url': url,
                    'channel_name': "N/A",
                    'views': 0,
                    'post_description': f"Error: {e}",
                    'post_status': "Dead"
                })
                logger(f"❌ Error processing {url}: {e}")

    return file_path
