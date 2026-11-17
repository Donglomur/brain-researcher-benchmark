"""Unchanged bounded HTTPS/header primitives extracted from the reviewed Stroop transport.
Donor SHA256676b9c0a8e00df2f413d44bd4844c483d13d586500ac9a6e810332bef92dd700.
No range behavior, object selector or donor acceptance is inherited.
"""
import http.client
HEADER_CAP = 4096
HEADER_LINES = 64

class RangeError(ValueError):
    pass

def need(ok, message):
    if not ok:
        raise RangeError(message)

class _HeaderReader:
    """Bound original consumed status/header lines, including informational replies."""
    def __init__(self, raw):
        self.raw, self.captured, self.lines = raw, bytearray(), 0

    def readline(self, limit=-1):
        left = HEADER_CAP - len(self.captured)
        size = left + 1 if limit < 0 else min(limit, left + 1)
        need(size > 0, 'HTTP header cap')
        line = self.raw.readline(size)
        self.captured.extend(line)
        need(len(self.captured) <= HEADER_CAP, 'HTTP header cap; consumed prefix retained')
        if line not in (b'', b'\r\n', b'\n'):
            self.lines += 1
            need(self.lines <= HEADER_LINES, 'HTTP header/status line count')
        return line

class _Response(http.client.HTTPResponse):
    def begin(self):
        raw = self.fp
        self.header_capture = _HeaderReader(raw)
        self.fp = self.header_capture
        try:
            super().begin()
        finally:
            self.fp = raw

class _Connection(http.client.HTTPSConnection):
    def __init__(self, host, timeout):
        super().__init__(host, timeout=timeout)
        self.observed_response = None
        self.response_class = self._response

    def _response(self, *args, **kwargs):
        self.observed_response = _Response(*args, **kwargs)
        return self.observed_response
