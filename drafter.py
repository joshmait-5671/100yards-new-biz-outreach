import logging
from datetime import date

import anthropic

from gmail_client import GmailClient

logger = logging.getLogger(__name__)

SUMMARY_TO = "josh.mait@gmail.com"


class Drafter:
    def __init__(self, gmail: GmailClient, client: anthropic.Anthropic):
        self.gmail = gmail
        self.client = client

    def _draft_email_body(self, contact: dict) -> str:
        research = contact.get("research", {})
        hook = research.get("personalization_hook", "")
        current_role = research.get("current_role", "")
        current_company = research.get("current_company", contact.get("company", ""))
        recent_news = research.get("recent_news", "")
        conversation_summary = contact.get("conversation_summary", "")
        last_contact = contact.get("last_contact_date", "a while back")

        context_lines = [f"You previously connected about: {conversation_summary}"]
        if hook:
            context_lines.append(f"Recent context to reference: {hook}")
        if recent_news:
            context_lines.append(f"Recent news: {recent_news}")
        if current_role and current_company:
            context_lines.append(f"They are currently: {current_role} at {current_company}")

        context = "\n".join(context_lines)

        prompt = f"""Write a short reactivation email from Josh Mait to {contact['name']}.

Context:
{context}
Last contact: {last_contact}

Rules:
- Under 100 words (strict)
- Casual and warm, like texting a former colleague
- Reference the original conversation naturally
- Mention the personalization hook if there is one
- No hard sell, no corporate language, no buzzwords
- End with a soft CTA: grab a coffee, quick catch-up call
- Sign off as Josh
- Do not use em dashes

Return only the email body text, no subject line, no JSON."""

        response = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()

    def create_all_drafts(self, enriched_contacts: list[dict]) -> list[dict]:
        results = []
        for contact in enriched_contacts:
            name = contact.get("name", "Unknown")
            email = contact.get("email", "")
            logger.info(f"Drafting email for {name}...")

            body = self._draft_email_body(contact)
            subject = f"Reconnecting - {name.split()[0] if name else 'Hey'}"

            draft_id = self.gmail.create_draft(to=email, subject=subject, body=body)
            logger.info(f"Draft created for {name}: {draft_id}")

            results.append(
                {
                    "contact": contact,
                    "draft_id": draft_id,
                    "email_body": body,
                    "subject": subject,
                }
            )
        return results

    def _build_summary(self, draft_results: list[dict]) -> str:
        today = date.today().strftime("%B %d, %Y")
        lines = [
            f"100 YARDS Outreach Summary - {today}",
            "=" * 50,
            "",
            f"4 Gmail drafts were created. Review and send from your Drafts folder.",
            "https://mail.google.com/mail/#drafts",
            "",
        ]

        for i, r in enumerate(draft_results, 1):
            c = r["contact"]
            research = c.get("research", {})
            lines += [
                f"{i}. {c.get('name')} | {research.get('current_role', '')} at {research.get('current_company', c.get('company', ''))}",
                f"   Email: {c.get('email')}",
                f"   Why selected: {c.get('why_selected', '')}",
                f"   Web research confidence: {research.get('confidence', 'low')}",
            ]
            if research.get("personalization_hook"):
                lines.append(f"   Hook used: {research['personalization_hook']}")
            if research.get("linkedin_url"):
                lines.append(f"   LinkedIn: {research['linkedin_url']}")
            lines += [
                f"   Draft ID: {r['draft_id']}",
                f"   Preview: {r['email_body'][:120]}...",
                "",
            ]

        lines += [
            "---",
            "Note: railway.toml cron runs at 13:00 UTC (9am EDT). Adjust to 14:00 UTC during winter (EST).",
        ]

        return "\n".join(lines)

    def create_summary_draft(self, draft_results: list[dict]) -> str:
        today = date.today().strftime("%B %d, %Y")
        body = self._build_summary(draft_results)
        draft_id = self.gmail.create_draft(
            to=SUMMARY_TO,
            subject=f"100 YARDS Outreach - {today}",
            body=body,
        )
        logger.info(f"Summary draft created: {draft_id}")
        return draft_id
