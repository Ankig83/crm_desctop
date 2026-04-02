from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path
import sqlite3

from crm_desktop.repositories import settings as settings_repo


def send_with_attachment(
    conn: sqlite3.Connection,
    to_addrs: list[str],
    subject: str,
    body: str,
    attachment_path: Path | None = None,
) -> None:
    host = settings_repo.get(conn, "smtp_host")
    port_s = settings_repo.get(conn, "smtp_port", "587")
    user = settings_repo.get(conn, "smtp_user", "")
    password = settings_repo.get(conn, "smtp_password", "")
    from_addr = settings_repo.get(conn, "smtp_from", "") or user
    use_tls = (settings_repo.get(conn, "smtp_use_tls", "1") or "1").lower() in ("1", "true", "yes")

    if not host or not from_addr:
        raise ValueError("Заполните SMTP (хост и адрес отправителя) в настройках или в переменных окружения CRM_SMTP_*.")

    port = int(port_s or "587")
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = ", ".join(to_addrs)
    msg.set_content(body)

    if attachment_path and Path(attachment_path).is_file():
        data = Path(attachment_path).read_bytes()
        name = Path(attachment_path).name.lower()
        if name.endswith(".txt"):
            msg.add_attachment(data, maintype="text", subtype="plain", filename=Path(attachment_path).name)
        else:
            msg.add_attachment(
                data,
                maintype="application",
                subtype="octet-stream",
                filename=Path(attachment_path).name,
            )

    if use_tls:
        context = ssl.create_default_context()
        with smtplib.SMTP(host, port, timeout=60) as smtp:
            smtp.starttls(context=context)
            if user:
                smtp.login(user, password or "")
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=60) as smtp:
            if user:
                smtp.login(user, password or "")
            smtp.send_message(msg)
