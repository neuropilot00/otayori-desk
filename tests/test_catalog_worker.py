from __future__ import annotations

import io
import json
import traceback
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

import requests

from sakurano_line_notifier import catalog_worker as worker
from sakurano_line_notifier.config import Settings
from sakurano_line_notifier.web_catalog import CatalogError, CatalogNotice, CatalogResult, _parse_source


URL = "https://catalog.example/api/internal/catalog"
TOKEN = "unit-test-secret-not-for-logs-12345678"
ROOT = Path(__file__).resolve().parents[1]


def response(status=200, body=None):
    result = Mock(status_code=status)
    result.json.return_value = {"ok": True, "imported": True} if body is None else body
    return result


def source(source_id, *, enabled=True, driver="scheduled", grade="全学年"):
    return SimpleNamespace(id=source_id, enabled=enabled, collection_driver=driver, default_grade=grade)


class CatalogSyncClientTests(unittest.TestCase):
    def setUp(self):
        factory = patch.object(worker.requests, "Session")
        self.session = factory.start().return_value
        self.addCleanup(factory.stop)
        sleep = patch.object(worker.time, "sleep")
        self.sleep = sleep.start()
        self.addCleanup(sleep.stop)
        self.client = worker.CatalogSyncClient(URL, TOKEN)
        self.addCleanup(self.client.close)
        self.payload = {"version": 1, "source_id": "city", "notices": []}

    def test_fixed_https_endpoint_and_token_validation(self):
        urls = ["", "http://catalog.example/api/internal/catalog", "https://catalog.example/",
                URL + "/", URL + "?token=x", URL + "?", URL + "#fragment", URL + "#",
                "https://user:password@catalog.example/api/internal/catalog",
                "https://catalog.example:80/api/internal/catalog",
                "https://catalog.example:bad/api/internal/catalog", "https://[bad/api/internal/catalog",
                " " + URL, URL + "\n", "https://catalog.example\\evil/api/internal/catalog"]
        for url in urls:
            with self.subTest(url=url), self.assertRaisesRegex(ValueError, "invalid sync URL"):
                worker.validate_sync_config(url, TOKEN)
        for token in ["", "a" * 31, "a" * 4097, TOKEN + "\n", TOKEN + "\r", TOKEN + " ", "あ" * 32]:
            with self.subTest(length=len(token)), self.assertRaisesRegex(ValueError, "invalid sync token"):
                worker.validate_sync_config(URL, token)
        worker.validate_sync_config(URL, "a" * 32)
        worker.validate_sync_config("https://catalog.example:443/api/internal/catalog", TOKEN)
        self.session.post.assert_not_called()

    def test_no_environment_credentials_redirects_or_unbounded_timeout(self):
        reply = response()
        self.session.post.return_value = reply
        self.assertTrue(self.client.upload(self.payload))
        self.assertIs(self.session.trust_env, False)
        self.session.post.assert_called_once_with(
            URL, json=self.payload,
            headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
            allow_redirects=False, timeout=(5, 30),
        )
        self.assertNotIn(TOKEN, json.dumps(self.payload))
        reply.close.assert_called_once()
        self.sleep.assert_not_called()

    def test_idempotent_noop_is_success(self):
        self.session.post.return_value = response(body={"ok": True, "imported": False})
        self.assertFalse(self.client.upload(self.payload))

    def test_redirects_and_other_non_retryable_statuses_are_rejected(self):
        for status in (201, 204, 301, 302, 303, 307, 308, 400, 401, 403, 404, 409, 422):
            with self.subTest(status=status):
                reply = response(status)
                reply.headers = {"Location": "https://other.example/steal"}
                self.session.post.reset_mock()
                self.session.post.return_value = reply
                with self.assertRaises(worker.UploadError) as error:
                    self.client.upload(self.payload)
                self.assertEqual((error.exception.kind, error.exception.status), ("http", status))
                self.session.post.assert_called_once()
                reply.json.assert_not_called()
                reply.close.assert_called_once()
        self.sleep.assert_not_called()

    def test_429_and_every_5xx_retry_twice_with_bounded_backoff(self):
        for status in (429, 500, 501, 502, 503, 504, 599):
            with self.subTest(status=status):
                replies = [response(status), response(status), response()]
                self.session.post.reset_mock()
                self.session.post.side_effect = replies
                self.sleep.reset_mock()
                self.assertTrue(self.client.upload(self.payload))
                self.assertEqual(self.session.post.call_count, 3)
                self.assertEqual(self.sleep.call_args_list, [call(1), call(2)])
                for reply in replies:
                    reply.close.assert_called_once()

    def test_retry_exhaustion_reports_only_http_status(self):
        self.session.post.side_effect = [response(503), response(503), response(503)]
        with self.assertRaises(worker.UploadError) as error:
            self.client.upload(self.payload)
        self.assertEqual((error.exception.kind, error.exception.status), ("http", 503))
        self.assertEqual(self.session.post.call_count, 3)
        self.assertEqual(self.sleep.call_args_list, [call(1), call(2)])

    def test_network_errors_retry_and_never_expose_exception_context(self):
        for error_class in (requests.ConnectionError, requests.ConnectTimeout, requests.ReadTimeout):
            with self.subTest(error_class=error_class.__name__):
                self.session.post.reset_mock()
                self.sleep.reset_mock()
                self.session.post.side_effect = error_class(f"{TOKEN} {URL} private response")
                try:
                    self.client.upload(self.payload)
                except worker.UploadError as error:
                    self.assertEqual(error.kind, "network")
                    rendered = "".join(traceback.format_exception(error))
                    self.assertNotIn(TOKEN, rendered)
                    self.assertNotIn(URL, rendered)
                    self.assertNotIn("private response", rendered)
                else:
                    self.fail("network errors must fail closed")
                self.assertEqual(self.session.post.call_count, 3)
                self.assertEqual(self.sleep.call_args_list, [call(1), call(2)])

    def test_network_retry_can_recover(self):
        self.session.post.side_effect = [requests.Timeout(TOKEN), response()]
        self.assertTrue(self.client.upload(self.payload))
        self.assertEqual(self.session.post.call_count, 2)
        self.sleep.assert_called_once_with(1)

    def test_request_errors_other_than_network_are_not_retried(self):
        self.session.post.side_effect = requests.RequestException(TOKEN)
        with self.assertRaises(worker.UploadError) as error:
            self.client.upload(self.payload)
        self.assertEqual(error.exception.kind, "request")
        self.session.post.assert_called_once()
        self.sleep.assert_not_called()

    def test_200_requires_explicit_contract_not_just_http_success(self):
        for body in ({}, {"ok": False, "imported": True}, {"ok": 1, "imported": True},
                     {"ok": True}, {"ok": True, "imported": 1}, {"ok": True, "imported": "false"}, []):
            with self.subTest(body=body):
                reply = response(body=body)
                self.session.post.reset_mock()
                self.session.post.return_value = reply
                with self.assertRaises(worker.UploadError) as error:
                    self.client.upload(self.payload)
                self.assertEqual(error.exception.kind, "response")
                self.session.post.assert_called_once()
                reply.close.assert_called_once()
        self.sleep.assert_not_called()

    def test_invalid_json_is_not_retried_or_logged(self):
        reply = response()
        reply.json.side_effect = ValueError(TOKEN)
        self.session.post.return_value = reply
        with self.assertRaises(worker.UploadError) as error:
            self.client.upload(self.payload)
        self.assertEqual(error.exception.kind, "response")
        self.assertNotIn(TOKEN, str(error.exception))
        self.session.post.assert_called_once()
        reply.close.assert_called_once()


class CatalogWorkerTests(unittest.TestCase):
    def setUp(self):
        self.service = Mock()
        self.service.sources = [source("city")]
        self.service._scan_source.side_effect = lambda item, grade: SimpleNamespace(source=item, notices=("notice",))
        self.client = Mock()

    def run_worker(self):
        output = io.StringIO()
        with redirect_stdout(output), redirect_stderr(output):
            code = worker.run(self.service, self.client)
        self.assertNotIn(TOKEN, output.getvalue())
        self.assertNotIn(URL, output.getvalue())
        rows = [json.loads(line) for line in output.getvalue().splitlines()]
        for row in rows:
            self.assertLessEqual(set(row), {"source_id", "count", "status", "kind", "http_status"})
        return code, rows

    @patch.object(worker, "snapshot_payload", side_effect=lambda result: {"source_id": result.source.id, "notices": []})
    def test_only_enabled_scheduled_sources_scan_directly_with_default_grade(self, snapshot):
        chosen = source("chosen", grade="3年生")
        self.service.sources = [chosen, source("disabled", enabled=False), source("server", driver="server")]
        with patch.object(worker, "ThreadPoolExecutor", wraps=ThreadPoolExecutor) as pool:
            code, rows = self.run_worker()
        self.assertEqual(code, 0)
        self.assertEqual(rows, [{"source_id": "chosen", "count": 1, "status": "success"}])
        pool.assert_called_once_with(max_workers=4)
        self.service._scan_source.assert_called_once_with(chosen, "3年生")
        self.service.get_source.assert_not_called()
        self.client.upload.assert_called_once_with({"source_id": "chosen", "notices": []})
        snapshot.assert_called_once()

    @patch.object(worker, "snapshot_payload")
    def test_successful_sources_upload_despite_scan_snapshot_and_http_failures(self, snapshot):
        self.service.sources = [source(item) for item in ("scan-failed", "warning", "original-only", "upload-failed", "ok")]

        def scan(item, grade):
            if item.id == "scan-failed":
                raise RuntimeError(f"{TOKEN} {URL}")
            return SimpleNamespace(source=item, notices=("notice",))

        def serialize(result):
            if result.source.id in {"warning", "original-only"}:
                raise CatalogError(f"{TOKEN} {URL}")
            return {"source_id": result.source.id, "notices": []}

        def upload(payload):
            if payload["source_id"] == "upload-failed":
                raise worker.UploadError("http", 403)

        self.service._scan_source.side_effect = scan
        snapshot.side_effect = serialize
        self.client.upload.side_effect = upload
        code, rows = self.run_worker()
        self.assertEqual(code, 1)
        indexed = {row["source_id"]: row for row in rows}
        self.assertEqual(indexed["ok"]["status"], "success")
        self.assertEqual(indexed["scan-failed"]["kind"], "collection")
        self.assertEqual(indexed["warning"]["kind"], "snapshot")
        self.assertEqual(indexed["original-only"]["kind"], "snapshot")
        self.assertEqual(indexed["upload-failed"]["http_status"], 403)
        self.assertCountEqual([item.args[0]["source_id"] for item in self.client.upload.call_args_list], ["upload-failed", "ok"])

    @patch.object(worker, "snapshot_payload", return_value={"notices": []})
    def test_unexpected_upload_exception_is_sanitized(self, snapshot):
        self.client.upload.side_effect = requests.RequestException(f"{TOKEN} {URL}")
        code, rows = self.run_worker()
        self.assertEqual(code, 1)
        self.assertEqual(rows[0]["kind"], "upload")

    def test_no_matching_sources_is_failure_not_false_success(self):
        self.service.sources = [source("disabled", enabled=False)]
        code, rows = self.run_worker()
        self.assertEqual(code, 1)
        self.assertEqual(rows[0]["kind"], "no_scheduled_sources")
        self.client.upload.assert_not_called()

    def test_real_snapshot_serializer_blocks_warnings_and_original_only(self):
        configured = _parse_source({
            "id": "city", "name": "市", "ward": "武蔵野市", "level": "小学校",
            "page_url": "https://city.example/info.html", "mode": "html_page",
            "collection_driver": "scheduled", "default_grade": "全学年", "grades": ["全学年"],
        }, 0)
        notice = CatalogNotice(
            id="a" * 20, source_id="city", source_name="市", ward="武蔵野市", level="小学校",
            grade="全学年", title="入会案内", kind="document", url=configured.page_url,
            text="申込みのお知らせ", content_hash="b" * 64, date_label="更新資料", published_label="",
            source_group="municipality", feed_group="notices",
        )
        result = CatalogResult(configured, "全学年", "2026-10-01T00:00:00+00:00", (notice,), discovered_count=1)
        self.service.sources = [configured]
        for incomplete in (replace(result, warnings=(f"{TOKEN} {URL}",)),
                           replace(result, notices=(replace(notice, extraction_status="original_only"),)),
                           replace(result, refreshing=True)):
            with self.subTest(warnings=bool(incomplete.warnings), refreshing=incomplete.refreshing):
                self.service._scan_source.side_effect = None
                self.service._scan_source.return_value = incomplete
                code, rows = self.run_worker()
                self.assertEqual(code, 1)
                self.assertEqual(rows[0]["kind"], "snapshot")
        self.client.upload.assert_not_called()
        self.service._scan_source.return_value = result
        code, rows = self.run_worker()
        self.assertEqual(code, 0)
        payload = self.client.upload.call_args.args[0]
        self.assertEqual(payload["version"], 1)
        self.assertEqual(payload["notices"][0]["text"], notice.text)
        self.assertEqual(payload["source_id"], "city")
        self.assertEqual(len(payload["source_fingerprint"]), 64)
        self.assertNotIn(TOKEN, json.dumps(payload))

    def test_main_disables_cache_closes_resources_and_does_not_set_server_flag(self):
        settings = replace(Settings.load(ROOT / "config.json"), web_catalog_cache_path=Path("should-not-be-created.sqlite3"))
        environment = {"CATALOG_SYNC_URL": URL, "CATALOG_SYNC_TOKEN": TOKEN}
        with patch.dict(worker.os.environ, environment, clear=True), patch("sys.argv", ["catalog_worker"]), \
             patch.object(worker.Settings, "load", return_value=settings) as load, \
             patch.object(worker, "CatalogService", return_value=self.service) as service, \
             patch.object(worker, "CatalogSyncClient", return_value=self.client) as client, \
             patch.object(worker, "run", return_value=1) as run:
            self.assertEqual(worker.main(), 1)
            self.assertNotIn("WEB_SCHEDULED_COLLECTION", worker.os.environ)
        client.assert_called_once_with(URL, TOKEN)
        load.assert_called_once_with(Path("config.json"))
        self.assertIsNone(service.call_args.args[0].web_catalog_cache_path)
        self.assertEqual(service.call_args.args[1], Path("sources.json"))
        run.assert_called_once_with(self.service, self.client)
        self.service.close.assert_called_once()
        self.client.close.assert_called_once()

    def test_missing_secrets_fail_before_collection_without_traceback(self):
        output = io.StringIO()
        with patch.dict(worker.os.environ, {}, clear=True), patch("sys.argv", ["catalog_worker"]), \
             patch.object(worker, "CatalogService") as service, redirect_stdout(output), redirect_stderr(output):
            self.assertEqual(worker.main(), 1)
        service.assert_not_called()
        self.assertEqual(json.loads(output.getvalue()), {"source_id": "-", "count": 0, "status": "failure", "kind": "worker"})

    def test_configuration_exceptions_never_print_secrets(self):
        output = io.StringIO()
        with patch("sys.argv", ["catalog_worker"]), patch.object(worker, "CatalogSyncClient", return_value=self.client), \
             patch.object(worker.Settings, "load", side_effect=RuntimeError(f"{TOKEN} {URL}")), \
             redirect_stdout(output), redirect_stderr(output):
            self.assertEqual(worker.main(), 1)
        self.assertNotIn(TOKEN, output.getvalue())
        self.assertNotIn(URL, output.getvalue())
        self.client.close.assert_called_once()

    def test_workflow_is_main_only_half_hourly_and_scopes_secrets_to_worker(self):
        workflow = (ROOT / ".github/workflows/catalog-sync.yml").read_text(encoding="utf-8")
        self.assertIn("cron: '7,37 * * * *'", workflow)
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("github.ref == 'refs/heads/main'", workflow)
        self.assertIn("github.event_name == 'schedule' || github.event_name == 'workflow_dispatch'", workflow)
        self.assertIn("contents: read", workflow)
        self.assertIn("persist-credentials: false", workflow)
        self.assertIn("ref: main", workflow)
        self.assertIn("cancel-in-progress: false", workflow)
        self.assertIn("timeout-minutes: 10", workflow)
        self.assertIn("actions/checkout@v7.0.1", workflow)
        self.assertIn("actions/setup-python@v7.0.0", workflow)
        self.assertIn("python-version: '3.12'", workflow)
        worker_step = workflow.split("- name: Collect and publish verified public catalog snapshots", 1)[1]
        self.assertIn("CATALOG_SYNC_URL: ${{ secrets.CATALOG_SYNC_URL }}", worker_step)
        self.assertIn("CATALOG_SYNC_TOKEN: ${{ secrets.CATALOG_SYNC_TOKEN }}", worker_step)
        self.assertIn("python -m sakurano_line_notifier.catalog_worker", worker_step)
        self.assertNotIn("WEB_SCHEDULED_COLLECTION", workflow)
        self.assertNotIn("pull_request", workflow)
        self.assertNotIn("apt-get", workflow)


if __name__ == "__main__":
    unittest.main()
