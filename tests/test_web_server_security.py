from __future__ import annotations

import http.client
import json
import secrets
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from sakurano_line_notifier.web_server import _BetaHTTPServer, BetaRequestHandler, POLICY_VERSION
from sakurano_line_notifier.web_push import PushSubscriptionError


class FakePush:
    def __init__(self):
        self.owners = {}
        self.test_calls = []

    def subscribe(self, subscription, scope, owner, consent):
        self.owners[owner] = {"scope": scope, "consent_version": consent}

    def export_owner(self, owner):
        return {"subscriptions": [self.owners[owner]] if owner in self.owners else []}

    def owner_status(self, owner):
        return {"subscribed": owner in self.owners, "scopes": []}

    def delete_owner(self, owner):
        self.owners.pop(owner, None)

    def test_subscription(self, owner, endpoint):
        if owner not in self.owners or endpoint != "mock":
            raise PushSubscriptionError("unavailable")
        self.test_calls.append((owner, endpoint))
        return {"provider_accepted": True, "delivery_confirmed": False}


class ServerSecurityTests(unittest.TestCase):
    def setUp(self):
        self.push = FakePush()
        with patch.dict("os.environ", {"WEB_PUBLIC_ORIGIN": "https://test.example"}):
            self.server = _BetaHTTPServer(("127.0.0.1", 0), BetaRequestHandler, SimpleNamespace(source_options=lambda: []), self.push)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def request(self, method, path, payload=None, headers=None):
        connection = http.client.HTTPConnection(*self.server.server_address, timeout=3)
        body = json.dumps(payload) if payload is not None else None
        connection.request(method, path, body, headers or {})
        response = connection.getresponse()
        result = response.status, dict(response.getheaders()), json.loads(response.read())
        connection.close()
        return result

    def post(self, path, payload, cookie=None):
        headers = {"Origin": "https://test.example", "Content-Type": "application/json"}
        if cookie:
            headers["Cookie"] = cookie
        return self.request("POST", path, payload, headers)

    def consent(self):
        return {"subscription": {"endpoint": "mock"}, "scope": {"source_id": "sakurano"}, "consent": True, "consent_version": POLICY_VERSION}

    def test_cross_origin_post_is_rejected_without_mutation(self):
        status, _, _ = self.request("POST", "/api/push/subscribe", self.consent(), {"Origin": "https://evil.example", "Content-Type": "application/json"})
        self.assertEqual(status, 403)
        self.assertFalse(self.push.owners)

    def test_subscription_requires_explicit_current_consent(self):
        payload = self.consent()
        payload.pop("consent")
        status, headers, _ = self.post("/api/push/subscribe", payload)
        self.assertEqual(status, 400)
        self.assertNotIn("Set-Cookie", headers)
        self.assertFalse(self.push.owners)

    def test_device_cookie_owner_isolation_export_delete(self):
        status, headers, payload = self.post("/api/push/subscribe", self.consent())
        self.assertEqual(status, 200)
        self.assertNotIn("subscription_count", payload)
        cookie = headers["Set-Cookie"]
        for flag in ("Secure", "HttpOnly", "SameSite=Strict"):
            self.assertIn(flag, cookie)
        cookie = cookie.split(";", 1)[0]
        self.assertEqual(len(next(iter(self.push.owners))), 64)
        _, _, anonymous = self.request("GET", "/api/privacy/data")
        self.assertEqual(anonymous["subscriptions"], [])
        _, _, owned = self.request("GET", "/api/privacy/data", headers={"Cookie": cookie})
        self.assertEqual(len(owned["subscriptions"]), 1)
        self.post("/api/privacy/delete", {})
        self.assertEqual(len(self.push.owners), 1)
        status, headers, _ = self.post("/api/privacy/delete", {}, cookie)
        self.assertEqual(status, 200)
        self.assertIn("Max-Age=0", headers["Set-Cookie"])
        self.assertFalse(self.push.owners)

    def test_push_test_requires_owner_and_does_not_enroll_or_confirm_delivery(self):
        status, headers, _ = self.post("/api/push/test", {"endpoint": "mock"})
        self.assertEqual(status, 403)
        self.assertNotIn("Set-Cookie", headers)
        self.assertFalse(self.push.test_calls)
        _, headers, _ = self.post("/api/push/subscribe", self.consent())
        cookie = headers["Set-Cookie"].split(";", 1)[0]
        before = dict(self.push.owners)
        status, headers, result = self.post("/api/push/test", {"endpoint": "mock"}, cookie)
        self.assertEqual(status, 200)
        self.assertEqual(result, {"provider_accepted": True, "delivery_confirmed": False})
        self.assertNotIn("Set-Cookie", headers)
        self.assertEqual(self.push.owners, before)
        self.assertEqual(len(self.push.test_calls), 1)
        self.assertEqual(self.post("/api/push/test", {"endpoint": "mock"}, cookie)[0], 429)
        self.assertEqual(len(self.push.test_calls), 1)

    def test_push_test_cannot_use_another_cookie_or_cross_origin(self):
        self.post("/api/push/subscribe", self.consent())
        stranger = "otayori_device=" + secrets.token_urlsafe(32)
        self.assertEqual(self.post("/api/push/test", {"endpoint": "mock"}, stranger)[0], 400)
        self.assertEqual(self.request("POST", "/api/push/test", {"endpoint": "mock"}, {"Origin": "https://evil.example", "Content-Type": "application/json"})[0], 403)
        self.assertEqual(self.request("POST", "/api/push/test", {}, {"Origin": "https://test.example"})[0], 415)
        self.assertFalse(self.push.test_calls)

    def test_free_beta_cannot_enable_payments_from_query(self):
        status, headers, payload = self.request("GET", "/api/pilot?payments=true")
        self.assertEqual(status, 200)
        self.assertFalse(payload["payments_enabled"])
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(headers["X-Frame-Options"], "DENY")

    def test_non_json_posts_rejected(self):
        status, _, _ = self.request("POST", "/api/privacy/delete", {}, {"Origin": "https://test.example"})
        self.assertEqual(status, 415)

    def test_get_refresh_cannot_bypass_mutation_limits(self):
        status, _, _ = self.request("GET", "/api/notices?refresh=true")
        self.assertEqual(status, 400)

    def test_repeated_bad_subscriptions_are_rate_limited(self):
        for _ in range(10):
            self.assertEqual(self.post("/api/push/subscribe", {})[0], 400)
        status, headers, _ = self.post("/api/push/subscribe", {})
        self.assertEqual(status, 429)
        self.assertIn("Retry-After", headers)

    def test_invented_rotating_cookies_cannot_reset_ip_throttle(self):
        for _ in range(10):
            cookie = "otayori_device=" + secrets.token_urlsafe(32)
            self.assertEqual(self.post("/api/push/subscribe", {}, cookie)[0], 400)
        self.assertEqual(self.post("/api/push/subscribe", {}, "otayori_device=" + secrets.token_urlsafe(32))[0], 429)

    def test_error_does_not_leak_secret(self):
        self.push.delete_owner = lambda *_: (_ for _ in ()).throw(RuntimeError("SECRET"))
        _, headers, _ = self.post("/api/push/subscribe", self.consent())
        with self.assertLogs("sakurano_line_notifier.web_server", level="ERROR") as logs:
            status, _, payload = self.post("/api/privacy/delete", {}, headers["Set-Cookie"].split(";", 1)[0])
        self.assertEqual(status, 500)
        self.assertNotIn("SECRET", str(payload) + str(logs.output))


if __name__ == "__main__":
    unittest.main()
