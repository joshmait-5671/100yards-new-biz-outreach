"""
One-time local script to generate Gmail OAuth tokens for Railway.

Usage:
  1. Create a Google Cloud project and enable the Gmail API
  2. Create OAuth 2.0 credentials (Desktop app type)
  3. Download the JSON and set GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET as env vars,
     OR paste the path to the downloaded JSON file when prompted
  4. Run: python auth_setup.py
  5. Complete the browser flow
  6. Copy the printed env vars into Railway's environment settings

Never run this on Railway. This is a local setup tool only.
"""

import json
import os
import sys

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
]


def main():
    client_id = os.environ.get("GMAIL_CLIENT_ID")
    client_secret = os.environ.get("GMAIL_CLIENT_SECRET")

    if client_id and client_secret:
        client_config = {
            "installed": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["http://localhost"],
            }
        }
        flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    else:
        secrets_path = input(
            "Path to your downloaded Google OAuth client secrets JSON file: "
        ).strip()
        if not os.path.exists(secrets_path):
            print(f"File not found: {secrets_path}")
            sys.exit(1)
        flow = InstalledAppFlow.from_client_secrets_file(secrets_path, SCOPES)

    print("\nOpening browser for Google OAuth flow...")
    creds: Credentials = flow.run_local_server(port=0)

    print("\n" + "=" * 60)
    print("SUCCESS. Set these environment variables in Railway:")
    print("=" * 60)
    print(f"\nGMAIL_CLIENT_ID={creds.client_id}")
    print(f"GMAIL_CLIENT_SECRET={creds.client_secret}")
    print(f"GMAIL_REFRESH_TOKEN={creds.refresh_token}")
    print("\n" + "=" * 60)
    print("Keep these values secret. Never commit them to git.")


if __name__ == "__main__":
    main()
