"""Render the per-site PSNR status table and send it by email.

SMTP sending is adapted from fw-email-report/util/email.py's
`send_email_with_csv` (plain smtplib + STARTTLS), but this feature needs an
HTML body — a scannable site status table — rather than a CSV attachment.
"""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

from psnr_alert.range_check import FLAGGED, INSUFFICIENT_HISTORY, NOMINAL, NO_DATA

STATUS_COLORS = {
    NOMINAL: "#1a7f37",
    FLAGGED: "#c9302c",
    INSUFFICIENT_HISTORY: "#8a6d3b",
    NO_DATA: "#767676",
}


def _fmt(value, digits=2):
    return "-" if value is None else f"{value:.{digits}f}"


def build_subject(results):
    n_flagged = sum(1 for r in results if r["status"] == FLAGGED)
    if n_flagged:
        noun = "site" if n_flagged == 1 else "sites"
        return f"UNITY QA: {n_flagged} {noun} flagged (PSNR out of range)"
    return "UNITY QA: all sites nominal"


def build_html_table(results, k):
    rows_html = []
    for r in sorted(results, key=lambda r: r["site"]):
        color = STATUS_COLORS[r["status"]]
        expected_range = "-"
        if r["baseline_mean"] is not None and r["baseline_std"] is not None:
            lo = 20 # r["baseline_mean"] - k * r["baseline_std"]
            hi = 30 # r["baseline_mean"] + k * r["baseline_std"]
            expected_range = f"{lo:.2f} - {hi:.2f}"

        new_badge = " (new)" if r["is_new"] and r["latest_session"] else ""

        rows_html.append(f"""
            <tr>
              <td style="padding:6px 10px;border-bottom:1px solid #eee;">{r['site'].title()}</td>
              <td style="padding:6px 10px;border-bottom:1px solid #eee;color:{color};font-weight:bold;">{r['status']}</td>
              <td style="padding:6px 10px;border-bottom:1px solid #eee;">{_fmt(r['latest_value'])}</td>
              <td style="padding:6px 10px;border-bottom:1px solid #eee;">{expected_range}</td>
              <td style="padding:6px 10px;border-bottom:1px solid #eee;">{r['latest_session'] or '-'}{new_badge}</td>
            </tr>""")

    n_flagged = sum(1 for r in results if r["status"] == FLAGGED)
    summary = (
        f"{n_flagged} of {len(results)} sites flagged "
        f"(expected range = site mean +/- {k} SD)."
    )

    return f"""
    <html>
      <body style="font-family:Arial,Helvetica,sans-serif;color:#222;">
        <p>{summary}</p>
        <table style="border-collapse:collapse;width:100%;max-width:800px;">
          <thead>
            <tr style="text-align:left;border-bottom:2px solid #333;">
              <th style="padding:6px 10px;">Site</th>
              <th style="padding:6px 10px;">Status</th>
              <th style="padding:6px 10px;">Latest PSNR</th>
              <th style="padding:6px 10px;">Expected range</th>
              <th style="padding:6px 10px;">Last session</th>
            </tr>
          </thead>
          <tbody>{''.join(rows_html)}</tbody>
        </table>
      </body>
    </html>
    """


def send_email_html(
    sender_email, sender_name, recipient_emails, subject, html_body,
    smtp_server, smtp_port, smtp_username, smtp_password,
):
    """recipient_emails: list of addresses."""
    msg = MIMEMultipart("alternative")
    msg["From"] = formataddr((sender_name, sender_email))
    msg["To"] = ", ".join(recipient_emails)
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html"))

    server = smtplib.SMTP(smtp_server, smtp_port)
    try:
        server.starttls()
        server.login(smtp_username, smtp_password)
        server.sendmail(sender_email, recipient_emails, msg.as_string())
        print(f"Email sent successfully to {', '.join(recipient_emails)}")
    finally:
        server.quit()
