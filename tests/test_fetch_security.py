from __future__ import annotations

import socket
import unittest
from unittest.mock import Mock, patch

from sakurano_line_notifier.fetcher import FetchError, HttpFetcher


class FetchSecurityTests(unittest.TestCase):
    def fetcher(self):
        self.session = Mock()
        self.session.headers = {}
        return HttpFetcher(session=self.session, allowed_hosts={"school.example"}, max_attempts=1, max_document_bytes=10)

    def response(self, status=200, content=b"safe", headers=None):
        result = Mock(status_code=status, headers=headers or {})
        result.iter_content.return_value = iter([content])
        return result

    def public_dns(self):
        return patch("socket.getaddrinfo", return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))])

    def test_private_ip_is_never_fetched(self):
        fetcher = self.fetcher()
        with patch("socket.getaddrinfo", return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))]):
            with self.assertRaises(FetchError):
                fetcher.fetch_document("https://school.example/test.pdf")
        self.session.get.assert_not_called()

    def test_unreviewed_host_is_never_fetched(self):
        fetcher = self.fetcher()
        with self.assertRaises(FetchError):
            fetcher.fetch_document("https://unknown.example/test.pdf")
        self.session.get.assert_not_called()

    def test_redirect_is_revalidated_before_next_request(self):
        fetcher = self.fetcher()
        response = self.response(302, headers={"Location": "https://127.0.0.1/secret"})
        self.session.get.return_value = response
        with self.public_dns(), self.assertRaises(FetchError):
            fetcher.fetch_document("https://school.example/test.pdf")
        self.assertEqual(self.session.get.call_count, 1)
        self.assertFalse(self.session.get.call_args.kwargs["allow_redirects"])
        response.close.assert_called()

    def test_oversized_declared_and_streamed_documents_close_response(self):
        for headers, content in [({"Content-Length": "999999"}, b"x"), ({}, b"x" * 11)]:
            fetcher = self.fetcher()
            response = self.response(headers=headers, content=content)
            self.session.get.return_value = response
            with self.public_dns(), self.assertRaises(FetchError):
                fetcher.fetch_document("https://school.example/test.pdf")
            response.close.assert_called()


if __name__ == "__main__":
    unittest.main()
