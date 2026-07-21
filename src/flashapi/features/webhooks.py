"""Webhook dispatcher — async delivery with retry."""

from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from typing import Any


class WebhookDispatcher:
    """Dispatches webhook events to configured URLs asynchronously."""

    def __init__(
        self,
        urls: list[str],
        *,
        retry_count: int = 3,
        timeout: int = 10,
    ):
        self._urls = urls
        self._retry_count = retry_count
        self._timeout = timeout
        self.sent = 0
        self.failed = 0
        self.retries = 0

    def dispatch(
        self,
        event: str,
        entity: str,
        entity_id: str | int,
        data: dict[str, Any],
    ) -> None:
        if not self._urls:
            return

        payload = {
            "event": event,
            "entity": entity,
            "entityId": str(entity_id),
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        headers = {
            "Content-Type": "application/json",
            "X-FlashAPI-Event": event,
            "X-FlashAPI-Entity": entity,
        }

        for url in self._urls:
            thread = threading.Thread(
                target=self._send_with_retry,
                args=(url, payload, headers),
                daemon=True,
            )
            thread.start()

    def _send_with_retry(self, url: str, payload: dict, headers: dict) -> None:
        import json
        try:
            import urllib.request
        except ImportError:
            return

        data_bytes = json.dumps(payload).encode("utf-8")

        for attempt in range(self._retry_count + 1):
            try:
                req = urllib.request.Request(
                    url,
                    data=data_bytes,
                    headers=headers,
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=self._timeout):
                    self.sent += 1
                    return
            except Exception:
                if attempt < self._retry_count:
                    self.retries += 1
                    time.sleep(2 ** attempt)
                else:
                    self.failed += 1
