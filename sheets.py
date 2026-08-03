import logging
import gspread
from google.oauth2.service_account import Credentials

LOG = logging.getLogger(__name__)

SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1Bd7XJPb6c7U315PNx1o4ySyI7qHtDseaRmSqEA1nTLI/edit?gid=589752326#gid=589752326"

def get_team_health_sheet():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]

    creds = Credentials.from_service_account_file("secrets/google.json", scopes=scopes) # type: ignore[reportUnknownMemberType])
    client = gspread.authorize(creds)

    sheet = client.open_by_url(SPREADSHEET_URL).sheet1
    LOG.debug(sheet.get_all_records())
    return sheet