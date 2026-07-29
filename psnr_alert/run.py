"""Orchestration: load PSNR history, classify every site's latest value
against its own baseline, email the summary, and persist last-seen state.

Usage (from repo root, matching how main.py is invoked):
    python -m psnr_alert.run
"""

import os
from pathlib import Path

from dotenv import load_dotenv

from psnr_alert.baseline import (
    leave_one_out_baselines,
    load_history,
    load_state,
    save_state,
    site_roster,
)
from psnr_alert.email_report import build_html_table, build_subject, send_email_html
from psnr_alert.range_check import DEFAULT_K, MIN_HISTORY, evaluate_sites

load_dotenv(Path(__file__).parent / ".env")

CSV_PATH = os.environ.get("PSNR_CSV_PATH", os.path.join("src", "data", "RWE_PSNR.csv"))
SITE_KEY_PATH = os.environ.get(
    "SITE_PHANTOM_KEY_PATH", os.path.join("src", "assets", "site_phantom_key.json")
)
STATE_PATH = os.environ.get(
    "PSNR_BASELINE_STATE_PATH", os.path.join("src", "data", "psnr_baseline.json")
)


def main():
    sender_email = os.environ["SMTP_SENDER_EMAIL"]
    sender_name = os.environ["SMTP_SENDER_NAME"]
    recipient_emails = [
        addr.strip() for addr in os.environ["SMTP_RECIPIENT_EMAIL"].split(",") if addr.strip()
    ]
    smtp_server = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_username = os.environ["SMTP_USERNAME"]
    smtp_password = os.environ["SMTP_PASSWORD"]

    history = load_history(CSV_PATH)
    roster = site_roster(SITE_KEY_PATH)
    previous_state = load_state(STATE_PATH)

    results = evaluate_sites(
        history, roster, previous_state=previous_state, k=DEFAULT_K, min_history=MIN_HISTORY
    )

    subject = build_subject(results)
    html_body = build_html_table(results, DEFAULT_K)

    send_email_html(
        sender_email, sender_name, recipient_emails, subject, html_body,
        smtp_server, smtp_port, smtp_username, smtp_password,
    )

    # Persist last-seen session per (site, segment) so next run knows what's new.
    save_state(STATE_PATH, leave_one_out_baselines(history))


if __name__ == "__main__":
    main()
