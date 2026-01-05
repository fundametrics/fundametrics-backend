"""
Failure alerting for Fundametrics platform (email/Slack webhook).

Config-driven via scraper/config/settings.yaml under 'alerts'.
"""

from __future__ import annotations

import json
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
from typing import Any, Dict, Optional

import httpx

from scraper.core.config import Config
from scraper.core.errors import FundametricsError
from scraper.core.observability.logger import get_logger

log = get_logger(__name__)


class AlertManager:
    """Manages dispatch of alerts to configured channels."""

    def __init__(self) -> None:
        self.enabled = Config.get("alerts", "enabled", default=False)
        self.smtp_host = Config.get("alerts", "smtp_host")
        self.smtp_port = Config.get("alerts", "smtp_port", default=587)
        self.smtp_user = Config.get("alerts", "smtp_user")
        self.smtp_password = Config.get("alerts", "smtp_password")
        self.from_email = Config.get("alerts", "from_email")
        self.to_emails = Config.get("alerts", "to_emails", default=[])
        self.slack_webhook_url = Config.get("alerts", "slack_webhook_url")

    def _send_email(self, subject: str, body: str) -> None:
        if not (self.smtp_host and self.smtp_user and self.smtp_password and self.from_email and self.to_emails):
            log.warning("email_alert_skip", reason="missing_config")
            return

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = self.from_email
        msg["To"] = ", ".join(self.to_emails)
        msg.set_content(body)

        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as smtp:
                smtp.starttls()
                smtp.login(self.smtp_user, self.smtp_password)
                smtp.send_message(msg)
            log.info("email_alert_sent", subject=subject, recipients=len(self.to_emails))
        except Exception as exc:
            log.error("email_alert_failed", exc_info=True, subject=subject)

    def _send_slack(self, text: str, blocks: Optional[list[Dict[str, Any]]] = None) -> None:
        if not self.slack_webhook_url:
            log.warning("slack_alert_skip", reason="missing_webhook_url")
            return

        payload: Dict[str, Any] = {"text": text}
        if blocks:
            payload["blocks"] = blocks

        try:
            r = httpx.post(self.slack_webhook_url, json=payload, timeout=10)
            r.raise_for_status()
            log.info("slack_alert_sent", status_code=r.status_code)
        except Exception as exc:
            log.error("slack_alert_failed", exc_info=True)

    def trigger_scrape_error(self, error: ScrapeError) -> None:
        if not self.enabled:
            return
        subject = f"[Fundametrics] ScrapeError: {error.symbol or 'Unknown'}"
        body = f"""
Fundametrics ScrapeError detected

Symbol: {error.symbol or 'N/A'}
Run ID: {error.run_id or 'N/A'}
Source: {getattr(error, 'source', 'N/A')}
Message: {error.message}
Timestamp: {datetime.now(timezone.utc).isoformat()}
Details: {json.dumps(error.details, indent=2)}
""".strip()
        self._send_email(subject, body)
        self._send_slack(
            f":warning: ScrapeError for {error.symbol or 'unknown'}",
            blocks=[
                {"type": "section", "text": {"type": "mrkdwn", "text": f"*ScrapeError*\n*Symbol*: {error.symbol or 'N/A'}\n*Source*: {getattr(error, 'source', 'N/A')}\n*Message*: {error.message}"}},
                {"type": "context", "elements": [{"type": "mrkdwn", "text": f"Timestamp: {datetime.now(timezone.utc).isoformat()}"}]},
            ],
        )

    def trigger_validation_error(self, error: ValidationError) -> None:
        if not self.enabled:
            return
        subject = f"[Fundametrics] ValidationError: {error.symbol or 'Unknown'}"
        body = f"""
Fundametrics ValidationError detected

Symbol: {error.symbol or 'N/A'}
Run ID: {error.run_id or 'N/A'}
Field: {getattr(error, 'field', 'N/A')}
Message: {error.message}
Timestamp: {datetime.now(timezone.utc).isoformat()}
Details: {json.dumps(error.details, indent=2)}
""".strip()
        self._send_email(subject, body)
        self._send_slack(
            f":x: ValidationError for {error.symbol or 'unknown'}",
            blocks=[
                {"type": "section", "text": {"type": "mrkdwn", "text": f"*ValidationError*\n*Symbol*: {error.symbol or 'N/A'}\n*Field*: {getattr(error, 'field', 'N/A')}\n*Message*: {error.message}"}},
                {"type": "context", "elements": [{"type": "mrkdwn", "text": f"Timestamp: {datetime.now(timezone.utc).isoformat()}"}]},
            ],
        )

    def trigger_signal_error(self, error: SignalError) -> None:
        if not self.enabled:
            return
        subject = f"[Fundametrics] SignalError: {error.symbol or 'Unknown'}"
        body = f"""
Fundametrics SignalError detected

Symbol: {error.symbol or 'N/A'}
Run ID: {error.run_id or 'N/A'}
Signal: {getattr(error, 'signal_name', 'N/A')}
Engine: {getattr(error, 'engine', 'N/A')}
Message: {error.message}
Timestamp: {datetime.now(timezone.utc).isoformat()}
Details: {json.dumps(error.details, indent=2)}
""".strip()
        self._send_email(subject, body)
        self._send_slack(
            f":rotating_light: SignalError for {error.symbol or 'unknown'}",
            blocks=[
                {"type": "section", "text": {"type": "mrkdwn", "text": f"*SignalError*\n*Symbol*: {error.symbol or 'N/A'}\n*Signal*: {getattr(error, 'signal_name', 'N/A')}\n*Engine*: {getattr(error, 'engine', 'N/A')}\n*Message*: {error.message}"}},
                {"type": "context", "elements": [{"type": "mrkdwn", "text": f"Timestamp: {datetime.now(timezone.utc).isoformat()}"}]},
            ],
        )

    def trigger_persistence_error(self, error: PersistenceError) -> None:
        if not self.enabled:
            return
        subject = f"[Fundametrics] PersistenceError"
        body = f"""
Fundametrics PersistenceError detected

Symbol: {error.symbol or 'N/A'}
Run ID: {error.run_id or 'N/A'}
Operation: {getattr(error, 'operation', 'N/A')}
Path: {getattr(error, 'path', 'N/A')}
Message: {error.message}
Timestamp: {datetime.now(timezone.utc).isoformat()}
Details: {json.dumps(error.details, indent=2)}
""".strip()
        self._send_email(subject, body)
        self._send_slack(
            f":file_cabinet: PersistenceError",
            blocks=[
                {"type": "section", "text": {"type": "mrkdwn", "text": f"*PersistenceError*\n*Symbol*: {error.symbol or 'N/A'}\n*Operation*: {getattr(error, 'operation', 'N/A')}\n*Path*: {getattr(error, 'path', 'N/A')}\n*Message*: {error.message}"}},
                {"type": "context", "elements": [{"type": "mrkdwn", "text": f"Timestamp: {datetime.now(timezone.utc).isoformat()}"}]},
            ],
        )


# Global singleton for easy import
alerts = AlertManager()
