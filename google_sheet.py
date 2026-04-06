# google_sheet.py
import gspread
from google.oauth2.service_account import Credentials

# -------------------------------
# CONFIGURATION
# -------------------------------
SERVICE_ACCOUNT_FILE = "service_account.json"
SHEET_ID = "1Zq4CdKa2vPODiL-cfxaFmzYvP4gXP-DsLFx5hOnAf5g"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# -------------------------------
# SETUP CLIENT
# -------------------------------
credentials = Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE,
    scopes=SCOPES
)

gc = gspread.authorize(credentials)

try:
    sheet = gc.open_by_key(SHEET_ID).sheet1
except Exception as e:
    print(f"❌ Could not open sheet: {e}")
    sheet = None

# -------------------------------
# FUNCTIONS
# -------------------------------
def clear_sheet():
    """Clear all rows in Google Sheet except header."""
    if sheet:
        try:
            # Clear all existing content
            sheet.clear()

            # Resize to 1 row (keep only header row)
            sheet.resize(rows=1)

            # Re-add header
            sheet.append_row(['post_url', 'channel_url', 'post_description', 'post_upload_date', 'post_status'])
            print("✅ Google Sheet cleared and header reset")
        except Exception as e:
            print(f"❌ Failed to clear Google Sheet: {e}")

def append_row(row_data):
    """Append a row to Google Sheet."""
    if sheet is None:
        print("❌ Sheet not initialized, skipping append.")
        return
    try:
        values = [
            row_data.get('post_url', ''),
            row_data.get('channel_url', ''),
            row_data.get('post_description', ''),
            row_data.get('post_upload_date', ''),
            row_data.get('post_status', '')
        ]
        sheet.append_row(values)
        print(f"✅ Row appended: {values[0]}")
    except Exception as e:
        print(f"❌ Failed to append row: {e}")