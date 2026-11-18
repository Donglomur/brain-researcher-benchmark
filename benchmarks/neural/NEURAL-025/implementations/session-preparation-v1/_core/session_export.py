"""Append-only, bounded NPY export; incomplete files are visibly partial.

Only two evaluation arrays are retained. Source/read/fit policies are external.
The completed collection receipt is the admission gate even if a late failure
occurs after one rename. No abort removes or overwrites an earlier artifact.
"""
import hashlib
import io
import os
from pathlib import Path
import numpy as np


class ExportRefusal(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise ExportRefusal(message)


class SessionSink:
    def __init__(self, directory, trial_count, roi_count, *, max_output_bytes):
        require(type(trial_count) is int and 0 < trial_count <= 372 and
                type(roi_count) is int and 0 < roi_count <= 565 and
                type(max_output_bytes) is int and 0 < max_output_bytes <= 94371840,
                'Explicit bounded export dimensions and byte cap')
        self.root = Path(directory)
        require(self.root.is_absolute() and all(not p.is_symlink() for p in (self.root, *self.root.parents)) and
                self.root.is_dir(), 'Existing ordinary reserved output directory')
        self.n, self.rois, self.cap = trial_count, roi_count, max_output_bytes
        self.attempted_bytes, self.index, self.finished, self.aborted = 0, 0, False, False
        self.close_errors = []
        self.streams = {}
        try:
            for name, width in (('neural', roi_count), ('joint', 24)):
                shape = (trial_count, 51, width)
                buffer = io.BytesIO()
                np.lib.format.write_array_header_1_0(buffer,
                    {'descr': '<f8', 'fortran_order': False, 'shape': shape})
                header = buffer.getvalue()
                require(len(header) <= 4096, 'Bounded NPY header')
                partial = self.root / (name + '_evaluation.npy.partial')
                final = self.root / (name + '_evaluation.npy')
                require(not final.exists(), 'Existing final export refused')
                fd = os.open(partial, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
                self.streams[name] = {'fd': fd, 'partial': partial, 'final': final,
                    'path': partial, 'shape': list(shape), 'bytes': 0,
                    'sha': hashlib.sha256(), 'header_bytes': len(header), 'closed': False}
                self._write(self.streams[name], header)
            required = sum(s['header_bytes'] + trial_count * 51 * s['shape'][2] * 8
                           for s in self.streams.values())
            require(required <= self.cap, 'Complete session output exceeds declared cap')
        except BaseException:
            self.abort()
            raise

    def _write(self, stream, body):
        require(type(body) is bytes and len(body) <= 1048576 and
                self.attempted_bytes + len(body) <= self.cap, 'Bounded incremental output request')
        # Charge the whole attempted body before an OS write, preserving failure
        # costs. This is a logical budget, not a physical storage-traffic meter.
        self.attempted_bytes += len(body)
        view = memoryview(body)
        while view:
            n = os.write(stream['fd'], view)
            require(n > 0, 'Short export write')
            stream['sha'].update(view[:n])
            stream['bytes'] += n
            view = view[n:]

    def write_trial(self, index, neural_eval, joint_eval):
        require(not self.finished and not self.aborted and type(index) is int and index == self.index and index < self.n,
                'Strict consecutive evaluation-trial write order')
        payloads = []
        for name, value, width in (('neural', neural_eval, self.rois), ('joint', joint_eval, 24)):
            require(type(value) is np.ndarray and value.dtype == np.dtype('float64') and
                    value.shape == (51, width) and bool(np.isfinite(value).all()), 'Exact finite evaluation matrix')
            require(not self.streams[name]['closed'], 'Closed partial export')
            payloads.append((name, value.astype('<f8', copy=False).tobytes(order='C')))
        for name, body in payloads:
            self._write(self.streams[name], body)
        self.index += 1
        return {'index': index, 'neural_values_sha256': hashlib.sha256(payloads[0][1]).hexdigest(),
                'joint_values_sha256': hashlib.sha256(payloads[1][1]).hexdigest(),
                'payload_bytes': sum(len(b) for _, b in payloads)}

    def finish(self):
        require(not self.finished and not self.aborted and self.index == self.n,
                'Every eligible trial must be written before finalization')
        result = {'completed': True, 'trial_count': self.n}
        for name, s in self.streams.items():
            require(s['bytes'] == s['header_bytes'] + self.n * 51 * s['shape'][2] * 8,
                    'Complete NPY byte extent required')
            os.fsync(s['fd'])
            s['closed'] = True
            try:
                os.close(s['fd'])
            except OSError as exc:
                self.close_errors.append({'stream': name, 'kind': type(exc).__name__,
                                          'detail': str(exc)[:256]})
                raise
            require(not s['final'].exists(), 'No final export overwrite')
            os.rename(s['partial'], s['final'])
            s['path'] = s['final']
            result[name] = {'path': str(s['path']), 'shape': s['shape'], 'dtype': '<f8',
                'order': 'C', 'bytes': s['bytes'], 'sha256': s['sha'].hexdigest()}
        self.finished = True
        result['cumulative_attempted_write_bytes'] = self.attempted_bytes
        return result

    def abort(self):
        records, errors = {}, list(self.close_errors)
        self.aborted = True
        for name, s in self.streams.items():
            if not s['closed']:
                try:
                    os.close(s['fd'])
                except OSError as exc:
                    errors.append({'stream': name, 'kind': type(exc).__name__, 'detail': str(exc)[:256]})
                # Never reuse/reclose a descriptor after an ambiguous close
                # failure; continue attempting cleanup of every other stream.
                s['closed'] = True
            records[name] = {'path': str(s['path']), 'bytes': s['bytes'],
                             'observed_sha256': s['sha'].hexdigest(), 'authoritative': False}
        self.close_errors = errors
        return {'completed': False, 'complete_trial_prefix': self.index,
                'cumulative_attempted_write_bytes': self.attempted_bytes, 'files': records,
                'cleanup_errors': errors, 'all_owned_closes_reported_success': not errors}
