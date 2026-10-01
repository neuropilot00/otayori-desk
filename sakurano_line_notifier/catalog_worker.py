"""Collect scheduled public sources and upload verified snapshots; never send push."""
from __future__ import annotations

import argparse
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace
from pathlib import Path
from urllib.parse import urlsplit

import requests

from .catalog_sync import snapshot_payload
from .config import Settings
from .web_catalog import CatalogService


class UploadError(RuntimeError):
    """Safe failure metadata, without request/response details or credentials."""

    def __init__(self, kind: str, status: int | None = None) -> None:
        self.kind = kind
        self.status = status
        super().__init__(kind)


def validate_sync_config(url: str, token: str) -> None:
    try:
        parsed = urlsplit(url)
        valid_url = (
            parsed.scheme == "https" and bool(parsed.hostname)
            and parsed.username is None and parsed.password is None
            and parsed.port in {None, 443}
            and parsed.path == "/api/internal/catalog"
            and not parsed.query and not parsed.fragment
            and not any(char.isspace() or ord(char) < 32 for char in url)
            and not any(char in url for char in "\\?#")
        )
    except ValueError:
        valid_url = False
    if not valid_url:
        raise ValueError("invalid sync URL")
    if not (32 <= len(token) <= 4096 and token.isascii() and all(33 <= ord(char) <= 126 for char in token)):
        raise ValueError("invalid sync token")


class CatalogSyncClient:
    def __init__(self, url: str, token: str) -> None:
        validate_sync_config(url, token)
        self.url = url
        self._token = token
        self.session = requests.Session()
        # Do not forward the bearer token through environment proxies or .netrc.
        self.session.trust_env = False

    def close(self) -> None:
        self.session.close()

    def upload(self, payload: dict) -> bool:
        for attempt in range(3):  # Initial request plus two bounded retries.
            try:
                response = self.session.post(
                    self.url,
                    json=payload,
                    headers={"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"},
                    allow_redirects=False,
                    timeout=(5, 30),
                )
            except (requests.ConnectionError, requests.Timeout):
                if attempt == 2:
                    raise UploadError("network") from None
                time.sleep(2 ** attempt)
                continue
            except requests.RequestException:
                raise UploadError("request") from None

            try:
                status = response.status_code
                if status == 200:
                    try:
                        body = response.json()
                    except ValueError:
                        raise UploadError("response", status) from None
                    if not isinstance(body, dict) or body.get("ok") is not True or type(body.get("imported")) is not bool:
                        raise UploadError("response", status)
                    # imported:false is a valid idempotent acknowledgement.
                    return body["imported"]
                if not (status == 429 or 500 <= status <= 599) or attempt == 2:
                    raise UploadError("http", status)
            finally:
                response.close()
            time.sleep(2 ** attempt)
        raise UploadError("request")


def _log(source_id: str, count: int, status: str, kind: str | None = None, http_status: int | None = None) -> None:
    row = {"source_id": source_id, "count": count, "status": status}
    if kind:
        row["kind"] = kind
    if http_status is not None:
        row["http_status"] = http_status
    print(json.dumps(row, ensure_ascii=False), flush=True)


def run(service: CatalogService, client: CatalogSyncClient) -> int:
    sources = [source for source in service.sources if source.enabled and source.collection_driver == "scheduled"]
    if not sources:
        _log("-", 0, "failure", "no_scheduled_sources")
        return 1
    failed = False
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(service._scan_source, source, source.default_grade): source for source in sources}
        for future in as_completed(futures):
            source = futures[future]
            try:
                result = future.result()
            except Exception:
                # Exception messages can contain URLs, headers or remote body text.
                _log(source.id, 0, "failure", "collection")
                failed = True
                continue
            try:
                payload = snapshot_payload(result)
            except Exception:
                _log(source.id, len(result.notices), "failure", "snapshot")
                failed = True
                continue
            try:
                client.upload(payload)
            except UploadError as exc:
                _log(source.id, len(result.notices), "failure", exc.kind, exc.status)
                failed = True
            except Exception:
                _log(source.id, len(result.notices), "failure", "upload")
                failed = True
            else:
                _log(source.id, len(result.notices), "success")
    return int(failed)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config.json"))
    parser.add_argument("--sources", type=Path, default=Path("sources.json"))
    args = parser.parse_args()
    client = None
    service = None
    try:
        client = CatalogSyncClient(os.getenv("CATALOG_SYNC_URL", ""), os.getenv("CATALOG_SYNC_TOKEN", ""))
        settings = replace(Settings.load(args.config), web_catalog_cache_path=None)
        service = CatalogService(settings, args.sources)
        return run(service, client)
    except Exception:
        _log("-", 0, "failure", "worker")
        return 1
    finally:
        if service is not None:
            service.close()
        if client is not None:
            client.close()


if __name__ == "__main__":
    raise SystemExit(main())
