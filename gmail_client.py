import base64
import logging
import os
from email.mime.text import MIMEText

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
]


class GmailClient:
    def __init__(self):
        creds = Credentials(
            token=None,
            refresh_token=os.environ["GMAIL_REFRESH_TOKEN"],
            token_uri="https://oauth2.googleapis.com/token",
            client_id=os.environ["GMAIL_CLIENT_ID"],
            client_secret=os.environ["GMAIL_CLIENT_SECRET"],
            scopes=SCOPES,
        )
        creds.refresh(Request())
        self.service = build("gmail", "v1", credentials=creds)
        logger.info("Gmail auth: OK")

    def search_threads(self, query: str, max_results: int = 500) -> list[dict]:
        threads = []
        page_token = None
        while len(threads) < max_results:
            batch_size = min(100, max_results - len(threads))
            kwargs = {"userId": "me", "q": query, "maxResults": batch_size}
            if page_token:
                kwargs["pageToken"] = page_token
            response = self.service.users().threads().list(**kwargs).execute()
            batch = response.get("threads", [])
            threads.extend(batch)
            page_token = response.get("nextPageToken")
            if not page_token or not batch:
                break
        return threads

    def get_thread_metadata(self, thread_id: str) -> dict | None:
        try:
            thread = (
                self.service.users()
                .threads()
                .get(
                    userId="me",
                    id=thread_id,
                    format="metadata",
                    metadataHeaders=["From", "To", "Cc", "Subject", "Date"],
                )
                .execute()
            )
        except HttpError as e:
            logger.warning(f"Failed to fetch thread {thread_id}: {e}")
            return None

        messages = thread.get("messages", [])
        if not messages:
            return None

        first_msg = messages[0]
        last_msg = messages[-1]

        def get_header(msg, name):
            for h in msg.get("payload", {}).get("headers", []):
                if h["name"].lower() == name.lower():
                    return h["value"]
            return ""

        participants = set()
        for msg in messages:
            for field in ("From", "To", "Cc"):
                val = get_header(msg, field)
                if val:
                    participants.add(val)

        return {
            "thread_id": thread_id,
            "subject": get_header(first_msg, "Subject"),
            "first_date": get_header(first_msg, "Date"),
            "last_date": get_header(last_msg, "Date"),
            "message_count": len(messages),
            "participants": list(participants),
            "snippet": thread.get("snippet", ""),
        }

    def batch_get_thread_metadata(self, thread_ids: list[str]) -> list[dict]:
        results = []
        # Process in chunks to avoid overwhelming the API
        chunk_size = 50
        for i in range(0, len(thread_ids), chunk_size):
            chunk = thread_ids[i : i + chunk_size]
            for tid in chunk:
                meta = self.get_thread_metadata(tid)
                if meta:
                    results.append(meta)
        return results

    def create_draft(self, to: str, subject: str, body: str) -> str:
        msg = MIMEText(body, "plain")
        msg["to"] = to
        msg["subject"] = subject
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
        draft = (
            self.service.users()
            .drafts()
            .create(userId="me", body={"message": {"raw": raw}})
            .execute()
        )
        return draft["id"]
