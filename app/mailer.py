"""Email sending (SMTP).

Three backends, chosen by config.MAIL_BACKEND:
  smtp     real email through your SMTP account (set MAIL_USERNAME in .env)
  console  prints the email in the terminal, so you can develop without an account
  memory   keeps messages in a list (used by the automated tests)

Sending never blocks or breaks a page: real emails go out on a background
thread, and any failure is only written to the log.
"""
import smtplib
import threading
from email.message import EmailMessage

from flask import current_app, render_template

OUTBOX_LIMIT = 100


def _deliver_smtp(config: dict, message: EmailMessage, logger) -> None:
    try:
        if config["MAIL_USE_SSL"]:
            server = smtplib.SMTP_SSL(config["MAIL_SERVER"], config["MAIL_PORT"], timeout=15)
        else:
            server = smtplib.SMTP(config["MAIL_SERVER"], config["MAIL_PORT"], timeout=15)
        with server:
            if config["MAIL_USE_TLS"] and not config["MAIL_USE_SSL"]:
                server.starttls()
            if config["MAIL_USERNAME"]:
                server.login(config["MAIL_USERNAME"], config["MAIL_PASSWORD"])
            server.send_message(message)
    except Exception as error:  # noqa: BLE001 - a mail problem must never crash the site
        logger.error("Could not send email to %s: %s", message["To"], error)


def send_email(to: str, subject: str, heading: str, lines: list,
               button_url: str = None, button_label: str = None) -> None:
    """Build a plain-text + HTML email and send it with the configured backend."""
    app = current_app._get_current_object()
    context = {"subject": subject, "heading": heading, "lines": lines,
               "button_url": button_url, "button_label": button_label}
    html = render_template("emails/message.html", **context)
    text = "\n\n".join([heading, *lines] + ([f"{button_label}: {button_url}"] if button_url else []))
    text += "\n\n-- PrintWise"

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = app.config["MAIL_FROM"]
    message["To"] = to
    message.set_content(text)
    message.add_alternative(html, subtype="html")

    backend = app.config["MAIL_BACKEND"]
    if backend == "memory":
        outbox = app.extensions.setdefault("outbox", [])
        outbox.append({"to": to, "subject": subject, "body": text, "url": button_url})
        del outbox[:-OUTBOX_LIMIT]
    elif backend == "console":
        print(f"\n----- EMAIL (console mode) -----\nTo: {to}\nSubject: {subject}\n\n{text}\n--------------------------------\n",
              flush=True)
    else:
        config = {k: app.config[k] for k in (
            "MAIL_SERVER", "MAIL_PORT", "MAIL_USE_TLS", "MAIL_USE_SSL", "MAIL_USERNAME", "MAIL_PASSWORD")}
        threading.Thread(target=_deliver_smtp, args=(config, message, app.logger), daemon=True).start()
