"""Generated transport failures and source-layout controls; no network/data."""
import http.client
import importlib.util
import io
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location("range_source", Path(__file__).parents[1] / "range_source.py")
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


class Response(io.BytesIO):
    def __init__(self, body=b"abcd", **headers):
        super().__init__(body)
        self.status = 206
        self.headers = {"Content-Range": "bytes 0-3/16", "Content-Length": "4", "ETag": '"v1"', **headers}


class RangeTests(unittest.TestCase):
    def source(self, response, **kwargs):
        self.calls = []
        def open_(request, timeout):
            self.calls.append(request)
            return response
        return M.RangeSource("https://example.invalid/movie", 16, '"v1"', opener=open_, **kwargs)

    def test_exact_range_and_identity(self):
        s = self.source(Response())
        self.assertEqual(s.read(4), b"abcd")
        self.assertEqual(s.tell(), 4)
        self.assertEqual(s.transferred, 4)
        self.assertEqual(self.calls[0].get_header("If-match"), '"v1"')
        self.assertEqual(self.calls[0].get_header("Range"), "bytes=0-3")

    def test_full_response_rejected_without_body_read(self):
        response = Response(); response.status = 200
        s = self.source(response)
        with self.assertRaisesRegex(ValueError, "206"):
            s.read(4)
        self.assertEqual(s.transferred, 0)

    def test_changed_etag_and_wrong_extent_rejected(self):
        for headers in ({"ETag": '"v2"'}, {"Content-Range": "bytes 1-4/16"},
                        {"Content-Length": "8"}, {"Content-Encoding": "gzip"}):
            with self.subTest(headers=headers):
                s = self.source(Response(**headers))
                with self.assertRaises(ValueError):
                    s.read(4)
                self.assertEqual(s.transferred, 0)

    def test_budget_refuses_before_network(self):
        for kwargs in ({"max_bytes": 3}, {"max_read": 3}):
            s = self.source(Response(), **kwargs)
            with self.assertRaisesRegex(ValueError, "budget"):
                s.read(4)
            self.assertEqual(self.calls, [])

    def test_partial_body_is_charged_and_source_fails_closed(self):
        class Partial(Response):
            def read(self, size):
                raise http.client.IncompleteRead(b"ab", 2)
        s = self.source(Partial())
        with self.assertRaisesRegex(ValueError, "truncated"):
            s.read(4)
        self.assertEqual(s.transferred, 2)
        self.assertEqual(s.requests[0]["bytes"], 2)
        with self.assertRaisesRegex(ValueError, "failed"):
            s.read(4)
        self.assertEqual(len(self.calls), 1)

    def test_unmeasurable_error_charges_request_extent(self):
        class Broken(Response):
            def read(self, size):
                raise OSError("transport error")
        s = self.source(Broken())
        with self.assertRaises(OSError):
            s.read(4)
        self.assertEqual(s.transferred, 4)
        with self.assertRaisesRegex(ValueError, "failed"):
            s.read(4)

    def test_short_read_and_closed_stream(self):
        s = self.source(Response(b"ab"))
        with self.assertRaisesRegex(ValueError, "truncated"):
            s.read(4)
        self.assertEqual(s.transferred, 2)
        s.close()
        with self.assertRaises(ValueError):
            s.read(1)
        with self.assertRaises(ValueError):
            s.seek(0)


if __name__ == "__main__":
    unittest.main()
