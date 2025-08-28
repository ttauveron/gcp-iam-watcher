import logging
import os
import requests
import time

from .base import IamChangeEvent, Destination
from .errors import DestinationConfigError


class SlackDestination(Destination):
    def __init__(self):
        self.webhook = os.getenv("SLACK_WEBHOOK_URL")
        self.token = os.getenv("SLACK_TOKEN")
        self.channel = os.getenv("SLACK_CHANNEL")

        if not self.webhook and not (self.token and self.channel):
            raise DestinationConfigError(
                "Slack selected but missing config. Provide SLACK_WEBHOOK_URL "
                "or both SLACK_TOKEN and SLACK_CHANNEL."
            )

    def send(self, e: IamChangeEvent) -> None:
        header = f":information_source: New Role Grant in {e.resource_display or 'Unknown'}"
        lines = [
            header,
            f"*Asset Type:* {e.resource_type}",
            f"*Asset Name:* {e.resource_name}",
        ]
        for g in e.changes:
            lines.append(f"*Role:* {g.role}")
            lines.append(f"*Granted to:* {g.members}")
            if g.condition:
                lines.append(f"*With condition:* {g.condition}")
        if e.logs_url:
            lines.append(f"*<{e.logs_url}|Browse Audit Logs>*")

        text = "\n".join(lines)

        payload = {
            "channel": self.channel,
            "text": text,
            "username": "IAM Notification",
            "unfurl_links": False,
            "unfurl_media": False,
            "icon_emoji": ":identification_card:",
        }

        # retry up to 3 times with exponential backoff
        for attempt in range(3):
            try:
                if self.webhook:
                    resp = requests.post(self.webhook, json={"text": text}, timeout=(3, 10))
                else:  # token+channel
                    resp = requests.post(
                        "https://slack.com/api/chat.postMessage",
                        headers={"Authorization": f"Bearer {self.token}"},
                        json=payload,
                        timeout=(3, 10),
                    )
            except requests.RequestException as e:
                logging.warning("Slack request error (attempt %s): %s", attempt + 1, e)
                if attempt == 2:
                    logging.error("SlackDestination: giving up after 3 attempts.")
                    return
                time.sleep(2 ** attempt)
                continue

            # handle rate limit / transient server errors
            if resp.status_code == 200 and (self.webhook or resp.json().get("ok", False)):
                return
            if resp.status_code in (429, 500, 502, 503, 504):
                retry_after = int(resp.headers.get("Retry-After", "0"))
                sleep_for = max(retry_after, 2 ** attempt)
                logging.warning("SlackDestination: retrying after %s seconds (status %s)", sleep_for, resp.status_code)
                time.sleep(sleep_for)
                continue

            # all other errors = permanent failure
            logging.error("SlackDestination: permanent failure [%s]: %s", resp.status_code, resp.text)
            return
