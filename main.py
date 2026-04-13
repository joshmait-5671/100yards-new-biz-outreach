import logging
import os
import sys
import traceback
from datetime import datetime

import anthropic

from contact_scanner import ContactScanner
from drafter import Drafter
from gmail_client import GmailClient
from researcher import Researcher

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
    force=True,
)
logger = logging.getLogger(__name__)

REQUIRED_ENV_VARS = [
    "ANTHROPIC_API_KEY",
    "GMAIL_CLIENT_ID",
    "GMAIL_CLIENT_SECRET",
    "GMAIL_REFRESH_TOKEN",
]


def validate_env() -> None:
    missing = [v for v in REQUIRED_ENV_VARS if not os.environ.get(v)]
    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
    for v in REQUIRED_ENV_VARS:
        masked = os.environ[v][:6] + "..." if len(os.environ[v]) > 6 else "***"
        logger.info(f"  {v}: {masked}")


def main() -> None:
    start = datetime.now()
    logger.info("Starting 100yards-new-biz-outreach run")

    validate_env()

    gmail = GmailClient()
    anthropic_client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    scanner = ContactScanner(gmail, anthropic_client)
    researcher = Researcher(anthropic_client)
    drafter = Drafter(gmail, anthropic_client)

    # Step 1: Scan Gmail for cold contacts
    threads = scanner.scan_cold_contacts(max_threads=300)
    if not threads:
        logger.warning("No candidate threads found. Exiting.")
        sys.exit(0)

    # Step 2: Let Claude select the best 4
    contacts = scanner.select_best_contacts(threads)

    # Step 3: Research each contact
    enriched = researcher.research_all_contacts(contacts)

    # Step 4: Create drafts
    draft_results = drafter.create_all_drafts(enriched)

    # Step 5: Create summary draft
    drafter.create_summary_draft(draft_results)

    elapsed = (datetime.now() - start).seconds
    logger.info(
        f"Run complete. 4 outreach drafts + 1 summary draft created. Elapsed: {elapsed}s"
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logger.error("Run failed with unhandled exception:")
        logger.error(traceback.format_exc())
        sys.exit(1)
