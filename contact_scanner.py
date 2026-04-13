import json
import logging
from datetime import datetime, timedelta

import anthropic

from gmail_client import GmailClient

logger = logging.getLogger(__name__)

OWNER_EMAILS = {"josh.mait@gmail.com", "joshmait@100yardstogo.com"}

EXCLUDE_DOMAINS = {
    "noreply",
    "no-reply",
    "notifications",
    "mailer",
    "bounce",
    "donotreply",
    "auto",
    "support",
    "info",
    "help",
    "newsletter",
    "updates",
}


def _build_query() -> str:
    today = datetime.today()
    floor = today - timedelta(days=180)
    ceiling = today - timedelta(days=365 * 3 + 180)
    after = ceiling.strftime("%Y/%m/%d")
    before = floor.strftime("%Y/%m/%d")
    return (
        f"after:{after} before:{before} "
        "-category:promotions -category:social -category:updates "
        "-unsubscribe -noreply -no-reply -donotreply "
        "(proposal OR quote OR project OR contract OR partnership OR "
        "intro OR introduce OR meeting OR opportunity OR follow-up OR "
        "\"follow up\" OR discuss OR pitch OR scope OR brief OR engage)"
    )


def _is_external_participant(email_addr: str) -> bool:
    addr = email_addr.lower().strip()
    if "<" in addr:
        addr = addr.split("<")[1].rstrip(">").strip()
    if "@" not in addr:
        return False
    local, domain = addr.split("@", 1)
    if any(addr.endswith(f"@{d}.com") or addr.endswith(f"@{d}") for d in OWNER_EMAILS):
        return False
    if addr in OWNER_EMAILS:
        return False
    if any(keyword in local for keyword in EXCLUDE_DOMAINS):
        return False
    return True


class ContactScanner:
    def __init__(self, gmail: GmailClient, client: anthropic.Anthropic):
        self.gmail = gmail
        self.client = client

    def scan_cold_contacts(self, max_threads: int = 300) -> list[dict]:
        query = _build_query()
        logger.info(f"Scanning threads with query: {query}")

        raw_threads = self.gmail.search_threads(query, max_results=max_threads)
        logger.info(f"Found {len(raw_threads)} raw threads")

        if not raw_threads:
            return []

        thread_ids = [t["threadId"] for t in raw_threads]
        threads = self.gmail.batch_get_thread_metadata(thread_ids)

        # Keep only threads with external participants and real back-and-forth
        filtered = []
        for t in threads:
            external = [p for p in t["participants"] if _is_external_participant(p)]
            if external and t["message_count"] >= 2:
                t["external_participants"] = external
                filtered.append(t)

        logger.info(f"{len(filtered)} threads pass external-participant filter")
        return filtered

    def select_best_contacts(self, threads: list[dict]) -> list[dict]:
        if not threads:
            raise ValueError("No candidate threads to analyze")

        # Trim to most recent 200 if there are too many
        threads_to_analyze = threads[:200]

        thread_summaries = []
        for t in threads_to_analyze:
            thread_summaries.append(
                f"- Subject: {t['subject']}\n"
                f"  Date range: {t['first_date']} to {t['last_date']}\n"
                f"  Messages: {t['message_count']}\n"
                f"  Participants: {', '.join(t['external_participants'][:3])}\n"
                f"  Snippet: {t['snippet'][:200]}"
            )

        threads_text = "\n\n".join(thread_summaries)

        prompt = f"""You are helping Josh Mait, founder of 100 YARDS, a creative branding and marketing agency, identify the best contacts for a warm reactivation outreach campaign.

Here are {len(threads_to_analyze)} past email thread summaries from his inbox. These are conversations that happened 6 months to 3+ years ago and have since gone quiet.

{threads_text}

Select exactly 4 contacts that are the best candidates for reactivation. Prioritize:
- People who had genuine back-and-forth conversation (multiple messages, real engagement)
- Founders, CMOs, marketing directors, or business owners (not recruiters, vendors, or press)
- Conversations about potential projects, partnerships, or client work that ended positively but just went cold
- A mix of industries and time periods

Exclude:
- Automated systems, noreply addresses, or newsletters
- Anyone who explicitly declined or gave negative signals
- Recruiters or job-related threads
- Internal team members

Return a JSON array of exactly 4 objects. Each object must have these fields:
- name: full name of the contact (infer from email if needed)
- email: their email address
- company: their company name (infer from email domain if needed)
- thread_subject: the email subject
- last_contact_date: approximate date of last message
- why_selected: 1-2 sentences on why this is a good reactivation target
- conversation_summary: 2-3 sentences summarizing what was discussed

Return ONLY the JSON array, no other text."""

        response = self.client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = response.content[0].text.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        contacts = json.loads(raw)
        logger.info(
            f"Claude selected {len(contacts)} contacts: "
            + ", ".join(c.get("name", "?") for c in contacts)
        )
        return contacts
