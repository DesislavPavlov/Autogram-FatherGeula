"""One-time: get a Google Drive refresh token for the GitHub Actions secrets.

Run on any computer with a browser:
    pip install google-auth-oauthlib
    python get_refresh_token.py client_secret.json

client_secret.json = the "Desktop app" OAuth client you download from
Google Cloud Console → APIs & Services → Credentials.
Sign in with the Google account that owns FatherGeula/VO.
"""
import json, sys
from google_auth_oauthlib.flow import InstalledAppFlow

flow = InstalledAppFlow.from_client_secrets_file(sys.argv[1], ["https://www.googleapis.com/auth/drive"])
creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
info = json.load(open(sys.argv[1]))
info = info.get("installed") or info.get("web")
print("\nAdd these three as GitHub repo secrets:\n")
print("GDRIVE_CLIENT_ID     =", info["client_id"])
print("GDRIVE_CLIENT_SECRET =", info["client_secret"])
print("GDRIVE_REFRESH_TOKEN =", creds.refresh_token)
