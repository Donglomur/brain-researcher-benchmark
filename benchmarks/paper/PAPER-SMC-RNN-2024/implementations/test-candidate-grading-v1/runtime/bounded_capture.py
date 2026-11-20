"""Bounded active pipe capture for this task's trusted owned controllers.

Raw retained head/tail bytes are separate artifacts. Storage truncation, read
ceiling exhaustion, and missing EOF are distinct and always explicit.
"""
import hashlib
import json
import os
from pathlib import Path
import selectors
import time


class Lane:
    def __init__(self, cap):
        self.cap = cap
        self.total = 0
        self.full = bytearray()
        self.head = None
        self.tail = bytearray()
        self.digest = hashlib.sha256()
        self.eof = False

    def add(self, value):
        self.total += len(value)
        self.digest.update(value)
        if self.head is None and len(self.full) + len(value) <= self.cap:
            self.full.extend(value)
            return
        half = self.cap // 2
        if self.head is None:
            joined = bytes(self.full) + value
            self.head = joined[:half]
            self.tail = bytearray(joined[-half:])
            self.full.clear()
        else:
            self.tail.extend(value)
            if len(self.tail) > half:
                del self.tail[:-half]

    def retained(self):
        return bytes(self.full) if self.head is None else self.head + bytes(self.tail)

    def summary(self):
        retained = self.retained()
        head = len(retained) if self.head is None else len(self.head)
        tail = 0 if self.head is None else len(self.tail)
        return {'observed_bytes': self.total, 'retained_bytes': len(retained),
                'storage_truncated': self.total > len(retained), 'eof_observed': self.eof,
                'observed_sha256': self.digest.hexdigest(),
                'digest_covers_complete_stream': self.eof,
                'segments': [{'stream_offset': 0, 'artifact_offset': 0, 'bytes': head}]
                    + ([{'stream_offset': self.total - tail, 'artifact_offset': head, 'bytes': tail}] if tail else [])}


class BoundedCapture:
    def __init__(self, proc, retained_per_stream=65536, read_ceiling=2097152):
        if not 2 <= retained_per_stream <= 65536 or retained_per_stream % 2:
            raise ValueError('Even bounded retention cap')
        if not 1 <= read_ceiling <= 2097152:
            raise ValueError('Bounded combined drain ceiling')
        self.selector = selectors.DefaultSelector()
        self.streams = {'stdout': proc.stdout, 'stderr': proc.stderr}
        self.lanes = {name: Lane(retained_per_stream) for name in self.streams}
        self.read_ceiling = read_ceiling
        self.read_bytes = 0
        self.read_ceiling_exhausted = False
        self.closed_without_eof = False
        self.closed = False
        self.close_errors = []
        try:
            for name, stream in self.streams.items():
                if stream is None:
                    raise ValueError('Owned stdout/stderr pipes required')
                os.set_blocking(stream.fileno(), False)
                self.selector.register(stream, selectors.EVENT_READ, name)
        except BaseException:
            self.close()
            raise

    def pump(self, timeout=.025):
        if self.closed or self.read_ceiling_exhausted:
            return
        for key, _ in self.selector.select(max(0, min(.025, timeout))):
            remaining = self.read_ceiling - self.read_bytes
            if remaining <= 0:
                self.read_ceiling_exhausted = True
                return
            try:
                chunk = os.read(key.fileobj.fileno(), min(16384, remaining))
            except BlockingIOError:
                continue
            if not chunk:
                self.lanes[key.data].eof = True
                self.selector.unregister(key.fileobj)
            else:
                self.lanes[key.data].add(chunk)
                self.read_bytes += len(chunk)
                if self.read_bytes >= self.read_ceiling:
                    # Without another read, exact-ceiling EOF is unknown.
                    self.read_ceiling_exhausted = True
                    return

    def finish(self, proc, end):
        """Called only after the owner attempts to stop its exact process group."""
        while proc.poll() is None or self.selector.get_map():
            remaining = end - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('Owned capture closure deadline')
            if self.read_ceiling_exhausted:
                self.closed_without_eof = any(not lane.eof for lane in self.lanes.values())
                for stream in self.streams.values():
                    if stream is not None and not stream.closed:
                        stream.close()
                self.selector.close()
                self.closed = True
                proc.wait(timeout=remaining)
                return
            self.pump(min(.025, remaining))
        proc.wait(timeout=max(.001, end - time.monotonic()))

    def summary(self):
        return {'schema': 'neural067-bounded-active-capture/v1',
                'combined_observed_bytes': self.read_bytes, 'read_ceiling': self.read_ceiling,
                'read_ceiling_exhausted': self.read_ceiling_exhausted,
                'closed_without_eof': self.closed_without_eof, 'stream_close_errors': list(self.close_errors),
                'all_eof_observed': all(lane.eof for lane in self.lanes.values()),
                'storage_truncated': any(lane.summary()['storage_truncated'] for lane in self.lanes.values()),
                'streams': {name: lane.summary() for name, lane in self.lanes.items()}}

    def publish(self, folder):
        folder = Path(folder)
        result = self.summary()
        result['artifacts'] = {}
        for name, lane in self.lanes.items():
            body = lane.retained()
            path = folder / (name + '.capture.bin')
            self._write(path, body, 65536)
            result['artifacts'][name] = {'path': str(path), 'bytes': len(body),
                'sha256': hashlib.sha256(body).hexdigest(), 'layout': 'segments in capture metadata; not concatenated full stream when truncated'}
        body = (json.dumps(result, sort_keys=True, indent=2) + '\n').encode()
        path = folder / 'STREAM_CAPTURE.json'
        self._write(path, body, 8192)
        return {'path': str(path), 'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest(),
                'state': {k: result[k] for k in ('all_eof_observed', 'storage_truncated', 'read_ceiling_exhausted', 'combined_observed_bytes')}}

    @staticmethod
    def _write(path, body, cap):
        if len(body) > cap:
            raise ValueError('Bounded capture artifact')
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            view = memoryview(body)
            while view:
                n = os.write(fd, view)
                if n <= 0:
                    raise OSError('Short capture write')
                view = view[n:]
            os.fsync(fd)
        finally:
            os.close(fd)
        fd = os.open(path.parent, os.O_RDONLY)
        try: os.fsync(fd)
        finally: os.close(fd)

    def close(self):
        errors = []
        if not self.closed:
            self.closed = True
            try: self.selector.close()
            except OSError as error: errors.append(type(error).__name__)
        for name, stream in self.streams.items():
            if stream is not None and not stream.closed:
                if not self.lanes[name].eof:
                    self.closed_without_eof = True
                try: stream.close()
                except OSError as error: errors.append(type(error).__name__)
        self.close_errors.extend(errors)
        if errors:
            raise OSError('Capture descriptor closure failed')
