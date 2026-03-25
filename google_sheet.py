import gspread
from oauth2client.service_account import ServiceAccountCredentials

def connect_sheet():

    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]

    creds = ServiceAccountCredentials.from_json_keyfile_name(
        "credentials.json",
        scope
    )

    client = gspread.authorize(creds)

    sheet = client.open("Telegram_Scraped_Data").sheet1

    return sheet


def append_row(data):

    sheet = connect_sheet()

    sheet.append_row([
        data["post_url"],
        data["channel_name"],
        data["views"],
        data["post_description"],
        data["post_status"]
    ])