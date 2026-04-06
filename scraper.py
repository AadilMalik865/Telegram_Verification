import csv
import os
import tempfile
import re
from telethon.tl.types import PeerChannel
from client_manager import get_client
from google_sheet import append_row, clear_sheet

BASE_DIR = tempfile.gettempdir()

def extract_channel_info_from_url(url):
    """Extract channel or user info from a Telegram URL."""
    if not url or not url.strip():
        return None, None, None

    # Private channel post
    private_match = re.match(r'https://t.me/c/(\d+)(?:/(\d+))?', url)
    if private_match:
        channel_id = int(private_match.group(1))
        msg_id = int(private_match.group(2)) if private_match.group(2) else None
        return channel_id, msg_id, True

    # Public post
    public_post_match = re.match(r'https://t.me/([a-zA-Z0-9_]+)/(\d+)', url)
    if public_post_match:
        username = public_post_match.group(1)
        msg_id = int(public_post_match.group(2))
        return username, msg_id, False

    # Public channel/user profile
    public_profile_match = re.match(r'https://t.me/([a-zA-Z0-9_]+)$', url)
    if public_profile_match:
        username = public_profile_match.group(1)
        return username, None, False

    return None, None, None


async def fetch_messages(post_urls, phone, logger=print, stop_event=None):
    """Fetch messages from Telegram URLs, write CSV, append to Google Sheet."""
    client = get_client(phone)
    logger(f"📡 Checking {len(post_urls)} URLs…")

    from client_manager import normalize_phone
    key = normalize_phone(phone)
    file_name = f"telegram_data_{key}.csv" if key else "telegram_data.csv"
    file_path = os.path.join(BASE_DIR, file_name)

    # CLEAR PREVIOUS DATA IN GOOGLE SHEET
    try:
        clear_sheet()
        logger("🧹 Cleared old Google Sheet data")
    except Exception as e:
        logger(f"⚠️ Could not clear Google Sheet: {e}")

    # Open CSV for writing
    with open(file_path, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                'post_url',
                'channel_url',
                'post_description',
                'post_upload_date',
                'post_status'
            ]
        )
        writer.writeheader()

        for url in post_urls:
            if stop_event and stop_event.is_set():
                logger("🛑 Stop signal received, stopping...")
                return file_path

            if not url.strip():
                row_data = {
                    'post_url': url,
                    'channel_url': "N/A",
                    'post_description': "Empty URL",
                    'post_upload_date': "N/A",
                    'post_status': "Dead"
                }
                writer.writerow(row_data)
                append_row(row_data)
                continue

            try:
                channel_identifier, msg_id, is_private = extract_channel_info_from_url(url)
                
                if not channel_identifier:
                    row_data = {
                        'post_url': url,
                        'channel_url': "N/A",
                        'post_description': "Invalid URL",
                        'post_upload_date': "N/A",
                        'post_status': "Dead"
                    }
                    writer.writerow(row_data)
                    append_row(row_data)
                    continue

                # Fetch channel/user entity
                entity = None
                channel_url = "N/A"

                try:
                    if is_private:
                        entity = await client.get_entity(PeerChannel(channel_identifier))
                        channel_url = f"https://t.me/c/{channel_identifier}"
                    else:
                        entity = await client.get_entity(channel_identifier)
                        channel_url = f"https://t.me/{channel_identifier}"
                except Exception:
                    entity = None

                post_description = "No description"
                post_upload_date = "N/A"
                status = "Dead"

                # Fetch message if msg_id provided
                if msg_id and entity:
                    try:
                        message = await client.get_messages(entity, ids=msg_id)

                        if message:
                            post_description = message.text if message.text else post_description
                            post_upload_date = message.date.strftime("%Y-%m-%d %H:%M:%S") if message.date else post_upload_date

                        # Check for copyright infringement
                        if re.search(r"copyright infringement", post_description, re.IGNORECASE):
                            status = "Dead"
                        else:
                            status = "Active"

                    except Exception:
                        post_description = "Message not found"
                        status = "Dead"

                elif entity:
                    post_description = "No specific post provided"
                    status = "Active"

                else:
                    post_description = "Entity not found"
                    status = "Dead"

                # Final adjustments
                if channel_url == "N/A":
                    status = "User Has Not Joined Channel"

                elif (not post_description) or post_description.lower() in ["no description", "message not found"]:
                    status = "Active" if post_upload_date != "N/A" else "Dead"

                # Prepare row and save
                row_data = {
                    'post_url': url,
                    'channel_url': channel_url,
                    'post_description': post_description,
                    'post_upload_date': post_upload_date,
                    'post_status': status
                }

                writer.writerow(row_data)
                
                try:
                    append_row(row_data)  # send to Google Sheet
                except Exception as e:
                    logger(f"Google Sheet Error: {e}")

                logger(f"{url} → post_status: {status}")

            except Exception as e:
                row_data = {
                    'post_url': url,
                    'channel_url': "N/A",
                    'post_description': f"Error: {e}",
                    'post_upload_date': "N/A",
                    'post_status': "Dead"
                }
                writer.writerow(row_data)
                try:
                    append_row(row_data)
                except Exception as e:
                    logger(f"Google Sheet Error: {e}")

                logger(f"❌ Error processing {url}: {e}")

    return file_path