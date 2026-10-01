from __future__ import annotations

import random
import time
from dataclasses import dataclass

import requests


class LineApiError(RuntimeError):
    """Raised when LINE rejects a push request or remains unavailable."""


@dataclass(frozen=True)
class PushResult:
    status_code: int
    request_id: str | None
    accepted_via_retry: bool = False


class LineClient:
    ENDPOINT = "https://api.line.me/v2/bot/message/push"

    def __init__(
        self,
        channel_access_token: str,
        recipient: str,
        timeout_seconds: float = 30,
        session: requests.Session | None = None,
        max_attempts: int = 4,
    ) -> None:
        if not channel_access_token:
            raise ValueError("LINE channel access token is required")
        if not recipient:
            raise ValueError("LINE recipient is required")
        self.channel_access_token = channel_access_token
        self.recipient = recipient
        self.timeout_seconds = timeout_seconds
        self.session = session or requests.Session()
        self.max_attempts = max_attempts

    def push_text(self, text: str, retry_key: str) -> PushResult:
        if not text.strip():
            raise ValueError("LINE message must not be empty")
        if len(text) > 5_000:
            raise ValueError("LINE text messages are limited to 5,000 characters")
        payload = {"to": self.recipient, "messages": [{"type": "text", "text": text}]}
        headers = {
            "Authorization": f"Bearer {self.channel_access_token}",
            "Content-Type": "application/json",
            "X-Line-Retry-Key": retry_key,
        }

        for attempt in range(self.max_attempts):
            try:
                response = self.session.post(
                    self.ENDPOINT,
                    json=payload,
                    headers=headers,
                    timeout=(5, self.timeout_seconds),
                )
            except requests.RequestException as exc:
                if attempt == self.max_attempts - 1:
                    raise LineApiError(f"LINE request failed: {exc.__class__.__name__}") from exc
                self._backoff(attempt)
                continue

            request_id = response.headers.get("x-line-request-id")
            if 200 <= response.status_code < 300:
                return PushResult(response.status_code, request_id)
            if response.status_code == 409:
                # LINE documents 409 as the response when this retry key was
                # already accepted. Treating it as success completes the local
                # state transition without sending the message a second time.
                return PushResult(response.status_code, request_id, accepted_via_retry=True)

            if response.status_code in {429, 500, 502, 503, 504} and attempt < self.max_attempts - 1:
                retry_after = response.headers.get("Retry-After")
                response.close()
                self._backoff(attempt, retry_after)
                continue

            message = self._error_message(response)
            response.close()
            raise LineApiError(f"LINE returned HTTP {response.status_code}: {message}")
        raise LineApiError("LINE request did not complete")

    @staticmethod
    def _error_message(response: requests.Response) -> str:
        try:
            payload = response.json()
            if isinstance(payload, dict) and payload.get("message"):
                return str(payload["message"])
        except ValueError:
            pass
        return "no error detail"

    @staticmethod
    def _backoff(attempt: int, retry_after: str | None = None) -> None:
        try:
            server_delay = float(retry_after) if retry_after else 0.0
        except ValueError:
            server_delay = 0.0
        server_delay = min(30.0, max(0.0, server_delay))
        delay = max(server_delay, min(30.0, (2**attempt) + random.uniform(0, 0.25)))
        time.sleep(delay)
