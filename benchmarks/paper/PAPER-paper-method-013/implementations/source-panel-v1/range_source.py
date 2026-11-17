"""Bounded, identity-checked inspection of official Allen movie HDF5 files.

Uses the existing selective-intake approach: exact HTTP 206 ranges, no whole
file fallback, and a cumulative transfer cap. Inspecting a header does not
authenticate a paper crop or frame origin. Acquisition requires a separate
shared resource reservation; this module cannot grant one.
"""
from __future__ import annotations

import argparse
import hashlib
import http.client
import io
import json
from pathlib import Path
import urllib.request

IDS = ("501271265", "501704220", "524691284", "531006860", "603516552",
       "604145810", "607040613", "669233895", "671162628", "679353932")
PREFIX = "https://allen-brain-observatory.s3.us-west-2.amazonaws.com/visual-coding-2p/ophys_movies/"


class RangeSource(io.RawIOBase):
    """Seekable HTTP object with exact range/ETag checks and no implicit retries."""

    def __init__(self, url, size, etag, *, max_bytes=1048576, max_read=262144,
                 opener=urllib.request.urlopen):
        super().__init__()
        if not isinstance(size, int) or size <= 0:
            raise ValueError("positive object length required")
        if not isinstance(etag, str) or not etag.startswith('"') or not etag.endswith('"'):
            raise ValueError("strong quoted ETag required")
        if max_bytes <= 0 or max_read <= 0:
            raise ValueError("positive transfer budgets required")
        self.url, self.size, self.etag = url, size, etag
        self.max_bytes, self.max_read, self.opener = max_bytes, max_read, opener
        self.pos, self.transferred, self.requests = 0, 0, []
        self.failed = False

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, offset, whence=0):
        self._checkClosed()
        if whence not in (0, 1, 2):
            raise ValueError("invalid seek origin")
        position = offset + (0 if whence == 0 else self.pos if whence == 1 else self.size)
        if not 0 <= position <= self.size:
            raise ValueError("seek outside object")
        self.pos = position
        return position

    def read(self, n=-1):
        self._checkClosed()
        if self.failed:
            raise ValueError("range source is failed; create a separately budgeted source")
        n = self.size - self.pos if n < 0 else min(n, self.size - self.pos)
        if n == 0:
            return b""
        if n > self.max_read or self.transferred + n > self.max_bytes:
            raise ValueError("range transfer budget exceeded before request")
        start, stop = self.pos, self.pos + n - 1
        request = urllib.request.Request(self.url, headers={
            "Range": f"bytes={start}-{stop}", "If-Match": self.etag,
            "Accept-Encoding": "identity", "User-Agent": "DeepCaImX-source-inspection/1"})
        row = {"start": start, "stop_inclusive": stop, "bytes": 0, "status": "failed"}
        self.requests.append(row)
        with self.opener(request, timeout=30) as response:
            if response.status != 206:
                raise ValueError("server must return HTTP 206; whole-object fallback forbidden")
            expected = f"bytes {start}-{stop}/{self.size}"
            if response.headers.get("Content-Range") != expected:
                raise ValueError("range extent or total object length changed")
            if response.headers.get("ETag") != self.etag:
                raise ValueError("object ETag changed")
            if response.headers.get("Content-Encoding") not in (None, "identity"):
                raise ValueError("encoded response refused")
            if int(response.headers.get("Content-Length", "-1")) != n:
                raise ValueError("range Content-Length mismatch")
            # Exact declared body length keeps transfer within the reservation.
            try:
                body = response.read(n)
            except http.client.IncompleteRead as exc:
                self.transferred += len(exc.partial)
                row["bytes"] = len(exc.partial)
                self.failed = True
                raise ValueError("truncated range response") from exc
            except Exception:
                # Bytes already acquired may be unavailable from the exception.
                # Charge the whole requested extent conservatively and fail stop.
                self.transferred += n
                row.update(bytes=n, accounting="conservative_requested_extent")
                self.failed = True
                raise
            self.transferred += len(body)
            row["bytes"] = len(body)
            if len(body) != n:
                self.failed = True
                raise ValueError("truncated range response")
        row.update(status="complete", sha256=hashlib.sha256(body).hexdigest())
        self.pos += n
        return body

    def readinto(self, target):
        data = self.read(len(target))
        target[:len(data)] = data
        return len(data)


def inspect_movie(recording_id, *, max_bytes=1048576):
    """Read only HDF metadata, recording actual ranges and object identity."""
    import h5py

    if recording_id not in IDS:
        raise ValueError("not an original panel recording")
    url = PREFIX + f"ophys_experiment_{recording_id}.h5"
    request = urllib.request.Request(url, method="HEAD", headers={"Accept-Encoding": "identity"})
    with urllib.request.urlopen(request, timeout=30) as response:
        if response.status != 200 or response.headers.get("Accept-Ranges") != "bytes":
            raise ValueError("official object does not advertise byte ranges")
        size, etag = int(response.headers["Content-Length"]), response.headers["ETag"]
    source = RangeSource(url, size, etag, max_bytes=max_bytes)
    receipt = {"recording_id": recording_id, "url": url, "object_bytes": size,
               "etag": etag, "scope": "HDF_structural_inspection_no_dataset_array_evaluation", "datasets": [],
               "source_paper_mapping_authenticated": False}
    try:
        with h5py.File(source, "r") as f:
            # The official Allen guide names data. Avoid visititems: HDF object
            # information traversal can scan the entire chunk index as well.
            obj = f["data"]
            if not isinstance(obj, h5py.Dataset):
                raise ValueError("official data path is not a dataset")
            receipt["datasets"].append({"name": "data", "shape": list(obj.shape),
                "dtype": str(obj.dtype), "chunks": obj.chunks,
                "compression": obj.compression, "offset": obj.id.get_offset(),
                "storage_bytes": obj.id.get_storage_size() if obj.chunks is None else None})
        receipt["status"] = "complete"
    except Exception as exc:
        receipt.update(status="failed", error=f"{type(exc).__name__}: {exc}")
    finally:
        receipt.update(transferred_bytes=source.transferred, ranges=source.requests)
        source.close()
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recording-id", required=True, choices=IDS)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--max-bytes", type=int, default=1048576)
    args = parser.parse_args()
    # Refuse existing outputs before making any network request.
    with args.output.open("x") as stream:
        result = inspect_movie(args.recording_id, max_bytes=args.max_bytes)
        json.dump(result, stream, indent=2)
        stream.write("\n")
    if result["status"] != "complete":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
