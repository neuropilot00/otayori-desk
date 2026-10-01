from __future__ import annotations

import json
import hashlib
import logging
import mimetypes
import os
import re
import secrets
import socket
import threading
import time
from collections import deque
from http import HTTPStatus
from http.cookies import SimpleCookie, CookieError
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from .web_catalog import CatalogError, CatalogService
from .web_push import PushSubscriptionError, WebPushNotifier

POLICY_VERSION = "2026-10-01"
DEVICE_COOKIE = "otayori_device"
LOGGER = logging.getLogger(__name__)


class _BetaHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 32

    def __init__(self, address: tuple[str, int], handler: type[BaseHTTPRequestHandler], catalog: CatalogService, push_notifier: WebPushNotifier | None = None) -> None:
        super().__init__(address, handler)
        self.catalog = catalog
        self.push_notifier = push_notifier
        self.rate_limiter = _RequestRateLimiter()
        self._slots = threading.BoundedSemaphore(32)
        self.public_origin = os.getenv("WEB_PUBLIC_ORIGIN", "").rstrip("/")
        self.cookie_secure = self.public_origin.startswith("https://")

    def process_request(self, request: socket.socket, client_address: tuple[str, int]) -> None:
        request.settimeout(15)
        if not self._slots.acquire(blocking=False):
            try:
                request.sendall(b"HTTP/1.1 503 Service Unavailable\r\nContent-Length: 0\r\nConnection: close\r\nRetry-After: 5\r\n\r\n")
            except OSError:
                pass
            finally:
                self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self._slots.release()
            raise

    def process_request_thread(self, request: socket.socket, client_address: tuple[str, int]) -> None:
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._slots.release()


class _RequestRateLimiter:
    """Small per-process guard for expensive public mutation endpoints."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._hits: dict[tuple[str, str], deque[float]] = {}

    def allow(self, client_key: str, bucket: str, limit: int, window_seconds: float) -> tuple[bool, int]:
        now = time.monotonic()
        key = (client_key, bucket)
        with self._lock:
            hits = self._hits.setdefault(key, deque())
            while hits and now - hits[0] >= window_seconds:
                hits.popleft()
            if len(hits) >= limit:
                retry_after = max(1, int(window_seconds - (now - hits[0])))
                return False, retry_after
            hits.append(now)
            if len(self._hits) > 2048:
                # Hard bound even under a flood of distinct client keys.
                oldest = min(self._hits, key=lambda item: self._hits[item][-1] if self._hits[item] else 0)
                del self._hits[oldest]
            return True, 0


class BetaRequestHandler(BaseHTTPRequestHandler):
    server: _BetaHTTPServer
    protocol_version = "HTTP/1.1"

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        self.close_connection = True
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/pilot":
                self._send_json({"mode": "free_beta", "payments_enabled": False, "policy_version": POLICY_VERSION, "retention_days": 180, "contact_url": None})
                return
            if parsed.path in {"/api/privacy/data", "/api/push/status"}:
                owner = self._owner_hash()
                notifier = self.server.push_notifier
                if parsed.path == "/api/privacy/data":
                    payload = notifier.export_owner(owner) if owner and notifier else {"subscriptions": []}
                    self._send_json({**payload, "device_only": True, "policy_version": POLICY_VERSION})
                else:
                    self._send_json(notifier.owner_status(owner) if owner and notifier else {"subscribed": False, "scopes": []})
                return
            if parsed.path == "/api/config":
                self._send_json(self._config_payload())
                return
            if parsed.path == "/api/notices":
                self._send_json(self._notices_payload(parse_qs(parsed.query)))
                return
            if parsed.path.startswith("/api/notices/"):
                payload = self._notice_payload(unquote(parsed.path.rsplit("/", 1)[-1]), parse_qs(parsed.query))
                if payload is not None:
                    self._send_json(payload)
                return
            if parsed.path == "/api/health":
                self._send_json({"ok": True, "service": "school-news-beta"})
                return
            if parsed.path == "/api/ready":
                ready = self.server.catalog.storage_ready()
                self._send_json({"ok": ready, "mode": "free_beta"}, status=HTTPStatus.OK if ready else HTTPStatus.SERVICE_UNAVAILABLE)
                return
            if parsed.path == "/api/push/config":
                self._send_json(self.server.push_notifier.config() if self.server.push_notifier else {"enabled": False, "sending_enabled": False, "public_key": None})
                return
            self._send_static(parsed.path)
        except CatalogError as exc:
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
        except Exception as exc:
            self._server_error(exc)

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        # One request per connection also prevents an unread rejected body from
        # being interpreted as the next request (request desynchronization).
        self.close_connection = True
        parsed = urlparse(self.path)
        if parsed.path not in {"/api/push/subscribe", "/api/push/unsubscribe", "/api/privacy/delete", "/api/refresh"}:
            self._send_json({"error": "not found"}, status=HTTPStatus.NOT_FOUND)
            return
        if not self._same_origin():
            self._send_json({"error": "same-origin request required"}, status=HTTPStatus.FORBIDDEN)
            return
        if self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
            self._send_json({"error": "application/json required"}, status=HTTPStatus.UNSUPPORTED_MEDIA_TYPE)
            return
        allowed, retry_after = self.server.rate_limiter.allow("global", "mutations", 60, 60)
        if not allowed:
            self._send_json({"error": "please retry later"}, status=HTTPStatus.TOO_MANY_REQUESTS, retry_after=retry_after)
            return
        if parsed.path in {"/api/push/unsubscribe", "/api/privacy/delete"}:
            try:
                self._read_json_body()
                owner = self._owner_hash()
                if owner and self.server.push_notifier:
                    self.server.push_notifier.delete_owner(owner)
                if parsed.path == "/api/privacy/delete":
                    self._cookie_header = self._device_cookie("", expire=True)
                self._send_json({"ok": True, "device_only": True})
            except PushSubscriptionError as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            except Exception as exc:
                self._server_error(exc)
            return
        if parsed.path == "/api/push/subscribe":
            allowed, retry_after = self.server.rate_limiter.allow(self._client_key(), "push-subscribe", 10, 600)
            if not allowed:
                self._send_json({"error": "too many subscription requests"}, status=HTTPStatus.TOO_MANY_REQUESTS, retry_after=retry_after)
                return
            try:
                if not self.server.push_notifier:
                    raise PushSubscriptionError("push is not configured")
                payload = self._read_json_body()
                subscription = payload.get("subscription")
                if not isinstance(subscription, dict):
                    raise PushSubscriptionError("subscription is required")
                if payload.get("consent") is not True or payload.get("consent_version") != POLICY_VERSION:
                    raise PushSubscriptionError("current notification privacy consent is required")
                owner = self._owner_hash()
                token = None if owner else secrets.token_urlsafe(32)
                owner = owner or hashlib.sha256(token.encode()).hexdigest()
                self.server.push_notifier.subscribe(subscription, payload.get("scope", {}), owner, POLICY_VERSION)
                if token:
                    self._cookie_header = self._device_cookie(token)
                self._send_json({"ok": True})
            except PushSubscriptionError as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            except Exception as exc:
                self._server_error(exc)
            return
        allowed, retry_after = self.server.rate_limiter.allow(self._client_key(), "refresh", 6, 60)
        if not allowed:
            self._send_json({"error": "too many refresh requests"}, status=HTTPStatus.TOO_MANY_REQUESTS, retry_after=retry_after)
            return
        try:
            self._read_json_body()
            self._send_json(self._notices_payload(parse_qs(parsed.query), force_refresh=True))
        except (CatalogError, PushSubscriptionError) as exc:
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
        except Exception as exc:
            self._server_error(exc)

    def _same_origin(self) -> bool:
        origin = self.headers.get("Origin", "")
        if self.headers.get("Sec-Fetch-Site") == "cross-site":
            return False
        if self.server.public_origin:
            return origin == self.server.public_origin
        # Development only; never infer a public origin from spoofable proxy headers.
        parsed = urlparse(origin)
        return parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"} and parsed.netloc == self.headers.get("Host")

    def _owner_hash(self) -> str | None:
        try:
            cookies = SimpleCookie(self.headers.get("Cookie", ""))
            token = cookies[DEVICE_COOKIE].value if DEVICE_COOKIE in cookies else ""
        except CookieError:
            return None
        return hashlib.sha256(token.encode()).hexdigest() if re.fullmatch(r"[A-Za-z0-9_-]{43}", token) else None

    def _device_cookie(self, token: str, expire: bool = False) -> str:
        return f"{DEVICE_COOKIE}={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age={0 if expire else 180 * 86400}" + ("; Secure" if self.server.cookie_secure else "")

    def _server_error(self, exc: Exception) -> None:
        # Never log request bodies, cookie values, URLs, push keys or trace locals.
        incident = secrets.token_hex(6)
        LOGGER.error("request_failed reference=%s type=%s", incident, type(exc).__name__)
        self._send_json({"error": "一時的なエラーです。しばらくしてから再度お試しください。", "reference": incident}, status=HTTPStatus.INTERNAL_SERVER_ERROR)

    def _config_payload(self) -> dict[str, Any]:
        sources = self.server.catalog.source_options()
        default_source = next((source for source in sources if source["id"] == "sakurano"), sources[0] if sources else None)
        return {
            "product": "おたより desk",
            "description": "学校・市・学童のお知らせをまとめて確認する保護者向けベータ",
            "sources": sources,
            "source_count": len(sources),
            "school_count": sum(1 for source in sources if source["source_group"] == "school"),
            "wards": sorted({source["ward"] for source in sources}),
            "levels": ["小学校", "中学校", "高等学校"],
            "grades": ["1年生", "2年生", "3年生", "4年生", "5年生", "6年生", "全学年"],
            "default_source_id": default_source["id"] if default_source else "all",
            "default_grade": default_source["default_grade"] if default_source else "全学年",
            "public_only": True,
        }

    def _notices_payload(self, query: dict[str, list[str]], force_refresh: bool = False) -> dict[str, Any]:
        level = self._query_value(query, "level")
        ward = self._query_value(query, "ward")
        grade = self._query_value(query, "grade")
        source_group = self._query_value(query, "group") or self._query_value(query, "source_group")
        source_id = self._effective_source_id(query, level, ward, source_group)
        feed_group = self._query_value(query, "feed")
        if grade is None and source_id not in {"all", "*"}:
            source = next((item for item in self.server.catalog.source_options() if item["id"] == source_id), None)
            grade = source["default_grade"] if source else None
        if self._query_value(query, "refresh") in {"1", "true", "yes"} and not force_refresh:
            raise CatalogError("更新には画面の更新ボタンを使用してください。")
        refresh = force_refresh
        results = self.server.catalog.get_many(
            source_id=source_id,
            grade=grade,
            level=level,
            ward=ward,
            feed_group=feed_group,
            source_group=source_group,
            refresh=refresh,
        )
        notices = [notice.to_summary() for result in results for notice in result.notices]
        notices.sort(key=lambda notice: (notice["date_label"] != "更新資料", notice["date_label"], notice["source_name"]), reverse=True)
        warnings = [f"{result.source.name}: {warning}" for result in results for warning in result.warnings]
        checked_results = [result for result in results if result.source.coverage_kind != "reference"] or results
        return {
            # A freshly fetched facility reference must not make an old school
            # snapshot look freshly checked. Empty means at least one is unknown.
            "scanned_at": min(result.scanned_at for result in checked_results),
            "source_count": len(results),
            "notice_count": len(notices),
            "reference_count": sum(notice["coverage_kind"] == "reference" for notice in notices),
            "notices": notices,
            "warnings": warnings,
            "filters": {"source_id": source_id or "all", "level": level or "all", "ward": ward or "all", "grade": grade or "default", "feed": feed_group or "all", "group": source_group or "all"},
            "cache_ttl_seconds": self.server.catalog.cache_ttl_seconds,
            "refreshed": force_refresh or refresh,
            "coverage": [result.coverage() for result in results],
            "complete": not warnings,
            "refreshing": any(result.refreshing for result in results),
        }

    def _notice_payload(self, notice_id: str, query: dict[str, list[str]]) -> dict[str, Any] | None:
        notice = self.server.catalog.find_notice(
            notice_id,
            source_id=self._query_value(query, "source_id"),
            grade=self._query_value(query, "grade"),
            level=self._query_value(query, "level"),
            ward=self._query_value(query, "ward"),
            feed_group=self._query_value(query, "feed"),
            source_group=self._query_value(query, "group") or self._query_value(query, "source_group"),
        )
        if notice is None:
            self._send_json({"error": "notice not found"}, status=HTTPStatus.NOT_FOUND)
            return None
        return notice.to_detail()

    def _read_json_body(self) -> dict[str, Any]:
        if self.headers.get("Transfer-Encoding") or len(self.headers.get_all("Content-Length", [])) != 1:
            raise PushSubscriptionError("one Content-Length is required")
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise PushSubscriptionError("invalid request body") from exc
        if length <= 0 or length > 16_384:
            raise PushSubscriptionError("request body is missing or too large")
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PushSubscriptionError("request body must be valid JSON") from exc
        if not isinstance(payload, dict):
            raise PushSubscriptionError("request body must be an object")
        return payload

    @staticmethod
    def _query_value(query: dict[str, list[str]], key: str) -> str | None:
        values = query.get(key, [])
        return values[0].strip() if values and values[0].strip() else None

    def _client_key(self) -> str:
        # Cookies can be invented/rotated by an unauthenticated caller. They
        # identify owned records, but must not reset abuse throttles. Proxy/NAT
        # clients may share this bucket; forwarded headers are not trusted.
        return str(self.client_address[0] or "unknown")

    def _effective_source_id(self, query: dict[str, list[str]], level: str | None, ward: str | None, source_group: str | None = None) -> str:
        requested = self._query_value(query, "source_id")
        if requested in {"all", "*"}:
            return "all"
        default_source_id = self._config_payload()["default_source_id"]
        source_id = requested or default_source_id
        if requested is None:
            return source_id
        source = next((item for item in self.server.catalog.source_options() if item["id"] == source_id), None)
        if source is None:
            return source_id
        if level and level not in {"all", "*", source["level"]}:
            return "all"
        if ward and ward not in {"all", "*", source["ward"]}:
            return "all"
        if source_group and source_group not in {"all", "*", source["source_group"]}:
            return "all"
        return source_id

    def _send_static(self, raw_path: str) -> None:
        project_root = Path(__file__).resolve().parents[1]
        web_root = project_root / "web"
        requested = unquote(raw_path)
        if requested in {"", "/"}:
            requested = "/index.html"
        relative = Path(requested.lstrip("/"))
        if any(part == ".." for part in relative.parts):
            self._send_json({"error": "not found"}, status=HTTPStatus.NOT_FOUND)
            return
        target = (web_root / relative).resolve()
        if web_root.resolve() not in target.parents and target != web_root.resolve():
            self._send_json({"error": "not found"}, status=HTTPStatus.NOT_FOUND)
            return
        if not target.is_file():
            self._send_json({"error": "not found"}, status=HTTPStatus.NOT_FOUND)
            return
        payload = target.read_bytes()
        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        try:
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", f"{content_type}; charset=utf-8" if content_type.startswith("text/") else content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self._send_security_headers()
            self.end_headers()
            self.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError):
            return

    def _send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK, retry_after: int | None = None) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            if getattr(self, "_cookie_header", None):
                self.send_header("Set-Cookie", self._cookie_header)
            if retry_after is not None:
                self.send_header("Retry-After", str(retry_after))
            self._send_security_headers()
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            return

    def _send_security_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=(self)")
        if self.server.cookie_secure:
            self.send_header("Strict-Transport-Security", "max-age=31536000")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'")

    def log_message(self, format: str, *args: object) -> None:
        # Keep the terminal readable; API errors are returned to the browser and CLI caller.
        return


def run_server(catalog: CatalogService, host: str = "127.0.0.1", port: int = 8765, settings: Any | None = None) -> None:
    push_notifier = WebPushNotifier(catalog, settings) if settings is not None else None
    server = _BetaHTTPServer((host, port), BetaRequestHandler, catalog, push_notifier)
    catalog.start_background_refresh(getattr(settings, "web_catalog_refresh_interval_seconds", 900.0) if settings is not None else 900.0)
    if push_notifier:
        push_notifier.start()
    print(f"school-news-beta listening at http://{host}:{port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        if push_notifier:
            push_notifier.stop()
        catalog.close()
        server.server_close()
