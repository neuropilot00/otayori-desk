from __future__ import annotations

import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from .web_catalog import CatalogError, CatalogService
from .web_push import PushSubscriptionError, WebPushNotifier


class _BetaHTTPServer(ThreadingHTTPServer):
    def __init__(self, address: tuple[str, int], handler: type[BaseHTTPRequestHandler], catalog: CatalogService, push_notifier: WebPushNotifier | None = None) -> None:
        super().__init__(address, handler)
        self.catalog = catalog
        self.push_notifier = push_notifier


class BetaRequestHandler(BaseHTTPRequestHandler):
    server: _BetaHTTPServer
    protocol_version = "HTTP/1.1"

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        parsed = urlparse(self.path)
        try:
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
            if parsed.path == "/api/push/config":
                self._send_json(self.server.push_notifier.config() if self.server.push_notifier else {"enabled": False, "sending_enabled": False, "public_key": None})
                return
            self._send_static(parsed.path)
        except CatalogError as exc:
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
        except Exception as exc:  # Keep the local beta usable when one upstream has an unexpected response.
            self._send_json({"error": f"unexpected server error: {exc.__class__.__name__}"}, status=HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        parsed = urlparse(self.path)
        if parsed.path == "/api/push/subscribe":
            try:
                if not self.server.push_notifier:
                    raise PushSubscriptionError("push is not configured")
                payload = self._read_json_body()
                subscription = payload.get("subscription")
                if not isinstance(subscription, dict):
                    raise PushSubscriptionError("subscription is required")
                count = self.server.push_notifier.subscribe(subscription, payload.get("scope", {}))
                self._send_json({"ok": True, "subscription_count": count})
            except PushSubscriptionError as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            except Exception as exc:
                self._send_json({"error": f"unexpected server error: {exc.__class__.__name__}"}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
            return
        if parsed.path != "/api/refresh":
            self._send_json({"error": "not found"}, status=HTTPStatus.NOT_FOUND)
            return
        try:
            self._send_json(self._notices_payload(parse_qs(parsed.query), force_refresh=True))
        except CatalogError as exc:
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
        except Exception as exc:
            self._send_json({"error": f"unexpected server error: {exc.__class__.__name__}"}, status=HTTPStatus.INTERNAL_SERVER_ERROR)

    def _config_payload(self) -> dict[str, Any]:
        sources = self.server.catalog.source_options()
        default_source = next((source for source in sources if source["id"] == "sakurano"), sources[0] if sources else None)
        return {
            "product": "おたより desk",
            "description": "お子さまの学校のお知らせを迷わず確認する保護者向けベータ",
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
        refresh = force_refresh or self._query_value(query, "refresh") in {"1", "true", "yes"}
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
        warnings = [warning for result in results for warning in result.warnings]
        return {
            "scanned_at": max(result.scanned_at for result in results),
            "source_count": len(results),
            "notice_count": len(notices),
            "notices": notices,
            "warnings": warnings,
            "filters": {"source_id": source_id or "all", "level": level or "all", "ward": ward or "all", "grade": grade or "default", "feed": feed_group or "all", "group": source_group or "all"},
            "cache_ttl_seconds": self.server.catalog.cache_ttl_seconds,
            "refreshed": force_refresh or refresh,
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
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise PushSubscriptionError("invalid request body") from exc
        if length <= 0 or length > 100_000:
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
            self._send_security_headers()
            self.end_headers()
            self.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError):
            return

    def _send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self._send_security_headers()
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            return

    def _send_security_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'")

    def log_message(self, format: str, *args: object) -> None:
        # Keep the terminal readable; API errors are returned to the browser and CLI caller.
        return


def run_server(catalog: CatalogService, host: str = "127.0.0.1", port: int = 8765, settings: Any | None = None) -> None:
    push_notifier = WebPushNotifier(catalog, settings) if settings is not None else None
    server = _BetaHTTPServer((host, port), BetaRequestHandler, catalog, push_notifier)
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
        server.server_close()
