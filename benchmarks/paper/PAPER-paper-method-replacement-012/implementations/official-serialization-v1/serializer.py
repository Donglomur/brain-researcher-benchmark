"""Original temporaldata HDF5 serialization, requiring a separately admitted run.

Source construction is not permission to read authentic inputs or write the full
HDF5 population. The public entry point consumes the complete accepted bridge;
there is no convenience subset or model/training/fit operation.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import sys
from types import ModuleType
import uuid

HERE = Path(__file__).resolve().parent
BRIDGE_SHA256 = 'e6548b3ef63c007056899407ac81159731d2265e19af4b6f490a6f5d96ecd4f7'
BRAINSET = 'bugeon_transcriptomic_2022'
MAX_RECEIPT_BYTES = 131072
TOTALS = {'sessions': 17, 'blocks': 69, 'neuron_observations': 10153, 'frames': 500491}


class SerializationError(ValueError):
    """Failure retains created files; progress is conservative output accounting."""
    def __init__(self, message, *, progress=None):
        super().__init__(message)
        self.progress = progress


def need(condition, message):
    if not condition:
        raise SerializationError(message)


def load_bridge():
    path = HERE.parent / 'temporaldata-bridge-v1' / 'bridge.py'
    body = path.read_bytes()
    need(hashlib.sha256(body).hexdigest() == BRIDGE_SHA256, 'frozen temporaldata bridge differs')
    name = '_nuclr_serializer_bridge_' + uuid.uuid4().hex
    module = ModuleType(name)
    module.__file__, module.__package__ = str(path), ''
    sys.modules[name] = module
    try:
        exec(compile(body, str(path), 'exec'), module.__dict__)
    except BaseException:
        del sys.modules[name]
        raise
    return module


class WriteBudget:
    """Separate cumulative logical writes and conservatively reserved file extents.

    Overwrites count again. Reservations occur before I/O and are not refunded
    after short/failed writes or shrinking truncations. This is not physical disk
    allocation, filesystem metadata, RAM, or HDF5 runtime qualification.
    """
    def __init__(self, limit):
        need(type(limit) is int and limit > 0, 'positive explicit HDF5 write budget required')
        self.limit = limit
        self.write_bytes_reserved = 0
        self.extent_bytes_reserved = 0

    def reserve(self, writes, growth):
        need(writes >= 0 and growth >= 0, 'negative write reservation refused')
        need(self.write_bytes_reserved + writes <= self.limit and
             self.extent_bytes_reserved + growth <= self.limit, 'HDF5 output budget exhausted before write')
        self.write_bytes_reserved += writes
        self.extent_bytes_reserved += growth

    def receipt(self):
        return {'limit_bytes': self.limit, 'logical_write_bytes_reserved': self.write_bytes_reserved,
                'extent_bytes_reserved': self.extent_bytes_reserved,
                'physical_allocation_or_wire_bytes': False}


class BoundedFile(io.RawIOBase):
    """Random-access file object for h5py's fileobj driver, owning no input files."""
    def __init__(self, raw, budget):
        super().__init__()
        self.raw, self.budget, self.high_extent = raw, budget, 0

    def readable(self):
        return True

    def writable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        self._checkClosed()
        return self.raw.tell()

    def seek(self, offset, whence=io.SEEK_SET):
        self._checkClosed()
        position = self.raw.seek(offset, whence)
        need(0 <= position <= self.budget.limit, 'HDF5 seek exceeds finite output extent')
        return position

    def readinto(self, target):
        self._checkClosed()
        return self.raw.readinto(target)

    def write(self, value):
        self._checkClosed()
        length = memoryview(value).nbytes
        end = self.tell() + length
        growth = max(0, end - self.high_extent)
        self.budget.reserve(length, growth)
        self.high_extent = max(self.high_extent, end)
        result = self.raw.write(value)
        need(result == length, 'short HDF5 write retained; no automatic retry')
        return result

    def truncate(self, size=None):
        self._checkClosed()
        size = self.tell() if size is None else size
        need(type(size) is int and size >= 0, 'invalid HDF5 truncate extent')
        growth = max(0, size - self.high_extent)
        self.budget.reserve(0, growth)
        self.high_extent = max(self.high_extent, size)
        return self.raw.truncate(size)

    def flush(self):
        if not self.raw.closed:
            self.raw.flush()



def _new_directory(parent_fd, name):
    os.mkdir(name, mode=0o700, dir_fd=parent_fd)
    return os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)


def _digest_file(file):
    file.seek(0)
    digest, length = hashlib.sha256(), 0
    while chunk := file.read(65536):
        digest.update(chunk)
        length += len(chunk)
    return digest.hexdigest(), length


def _identity(value):
    return (value.st_dev, value.st_ino, value.st_mode, value.st_nlink,
            value.st_size, value.st_mtime_ns, value.st_ctime_ns)


def _serialize_stream(items, *, root_fd, expected_sessions, expected_totals,
                      runtime, h5py_module, budget, source_identity, authentic):
    """Private mechanics seam; generated controls inject explicit library doubles.

    Public construction supplies only the accepted iterator and complete source
    population. This function alone establishes no source custody or runtime proof.
    """
    expected_sessions = tuple(expected_sessions)
    need(len(expected_sessions) == len(set(expected_sessions)) and
         all(type(sid) is str and re.fullmatch(r'[A-Za-z0-9_-]+', sid) for sid in expected_sessions),
         'unique safe source session identifiers required')
    records, totals = [], {key: 0 for key in TOTALS}
    receipt_accounting = {'reserved_bytes': 0, 'body_bytes': 0,
                          'attempted': False, 'completed': False}
    processed_fd = brainset_fd = None
    try:
        processed_fd = _new_directory(root_fd, 'processed')
        brainset_fd = _new_directory(processed_fd, BRAINSET)
        iterator = iter(items)
        while True:
            try:
                item = next(iterator)
            except StopIteration:
                break
            index = len(records)
            need(index < len(expected_sessions) and item.session_id == expected_sessions[index],
                 'complete source session sequence differs')
            provenance = item.provenance
            need(provenance.get('session_id') == item.session_id and
                 provenance.get('schema') == 'nuclr-owner-temporaldata-session-v1' and
                 provenance.get('contains_owner_only_transcriptomic_labels') is True and
                 provenance.get('hdf5_serialized') is False,
                 'unmodified owner bridge session provenance required')
            for key in ('blocks', 'neuron_observations', 'frames'):
                need(type(provenance.get(key)) is int and provenance[key] > 0,
                     'complete positive session accounting required')
            if authentic:
                for key in ('input_manifest_sha256', 'prior_input_acceptance_sha256',
                            'selection_receipt_sha256'):
                    need(provenance.get(key) == source_identity[key], 'accepted input identity differs')
            name = item.session_id + '.h5'
            fd = os.open(name, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=brainset_fd)
            with os.fdopen(fd, 'r+b', buffering=0) as raw:
                bounded = BoundedFile(raw, budget)
                try:
                    # Close HDF5 before the Python file object, including failures.
                    with h5py_module.File(bounded, 'w', driver='fileobj') as handle:
                        item.data.to_hdf5(handle, serialize_fn_map=runtime.serialize_fn_map)
                    bounded.flush()
                    os.fsync(raw.fileno())
                    before = os.fstat(raw.fileno())
                    need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1,
                         'ordinary single-link HDF5 output required')
                    digest, extent = _digest_file(raw)
                    after = os.fstat(raw.fileno())
                    named = os.stat(name, dir_fd=brainset_fd, follow_symlinks=False)
                    need(_identity(before) == _identity(after) == _identity(named) and
                         extent == after.st_size, 'HDF5 output changed or pathname was replaced')
                finally:
                    bounded.close()
            records.append({'session_id': item.session_id,
                            'relative_path': 'processed/' + BRAINSET + '/' + name,
                            'sha256': digest, 'bytes': extent, 'bridge_provenance': dict(provenance)})
            totals['sessions'] += 1
            for key in ('blocks', 'neuron_observations', 'frames'):
                totals[key] += provenance[key]
            # The accepted generator drops its retained buffers on resume. Do not
            # hold the previous item while the generator assembles the next one.
            del item, provenance
        need(tuple(record['session_id'] for record in records) == expected_sessions and
             totals == expected_totals, 'incomplete original population; no serialized receipt')
        receipt = {
            'schema': 'nuclr-original-hdf5-serialization-v1',
            'status': 'serialized_pending_real_runtime_and_readback_qualification',
            'source_identity': source_identity, 'authentic_input_custody': authentic,
            'complete_original_representation': authentic, 'counts': totals,
            'files': records, 'hdf5_budget': budget.receipt(),
            'receipt_separate_maximum_bytes': MAX_RECEIPT_BYTES,
            'receipt_write_reserved_bytes': MAX_RECEIPT_BYTES,
            'contains_owner_only_transcriptomic_labels': True,
            'participant_delivery_authorized': False, 'loaded_source_tree_authenticated': False,
            'runtime_qualified': False, 'hdf5_readback_verified': False,
            'original_loader_verified': False, 'reference_trained': False,
            'historical_reference_reproduced': False, 'scientific_qualification': False,
        }
        body = (json.dumps(receipt, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()
        need(len(body) <= MAX_RECEIPT_BYTES, 'serialization receipt exceeds separate bound')
        # Reserve the fixed maximum before opening; failures never refund it.
        receipt_accounting.update(reserved_bytes=MAX_RECEIPT_BYTES,
                                  body_bytes=len(body), attempted=True)
        fd = os.open('SERIALIZED.json', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                     0o600, dir_fd=root_fd)
        with os.fdopen(fd, 'wb') as handle:
            need(handle.write(body) == len(body), 'short receipt write; output retained')
            handle.flush()
            os.fsync(handle.fileno())
        receipt_accounting['completed'] = True
        return receipt
    except Exception as exc:
        raise SerializationError('serialization failed; retain outputs and do not retry: ' + str(exc),
                                 progress={'completed_files': records, 'completed_counts': totals,
                                           'hdf5_budget': budget.receipt(),
                                           'receipt_accounting': receipt_accounting,
                                           'partial_outputs_retained': True}) from exc
    finally:
        if brainset_fd is not None:
            os.close(brainset_fd)
        if processed_fd is not None:
            os.close(processed_fd)


def write_accepted_sessions(selection, route, output_root, *, max_write_bytes):
    """Read ALL accepted arrays and serialize once, only under a future admitted run.

    The output directory must not exist; its existing parent must be outside the
    entire protected native preparation tree. All outputs are owner-only. The
    supplied budget must include repeated HDF5 metadata writes, not only final
    file sizes; SERIALIZED.json has a separate fixed 128 KiB maximum. A failed run
    is never resumed, cleaned up or silently retried by this function.
    """
    budget = WriteBudget(max_write_bytes)
    bridge = load_bridge()
    need(hashlib.sha256(Path(route.__file__).read_bytes()).hexdigest() == bridge.ROUTE_SHA256,
         'original current route source differs')
    route._check_selection(selection)
    binding = selection._binding
    need(binding.binding_role == 'accepted_owner_input_metadata' and
         selection.receipt['label_level'] == 'subclass' and selection.receipt['panel'] == 'transductive' and
         len(selection._selected_projection['label_map']) == 1500,
         'accepted complete five-subclass ordinary-transductive selection required')
    sessions = binding._inputs.manifest['sessions']
    totals = {'sessions': len(sessions), 'blocks': sum(len(s['experiments']) for s in sessions),
              'neuron_observations': sum(s['neurons'] for s in sessions),
              'frames': sum(s['frames'] for s in sessions)}
    need(totals == TOTALS, 'complete original representation required before opening outputs')
    path = Path(output_root)
    need(path.anchor == os.sep and '..' not in path.parts and path.name,
         'absolute new output directory required')
    protected, identity = route._protected_directory(binding._protected_run_root)
    need(identity == binding._protected_run_identity and not path.is_relative_to(protected),
         'protected native preparation directory refused or changed')
    runtime = bridge.load_source_runtime()
    import h5py
    source_identity = {'bridge_sha256': BRIDGE_SHA256,
                       'serializer_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                       'input_manifest_sha256': binding.canonical_manifest_sha256,
                       'prior_input_acceptance_sha256': binding.independent_acceptance_sha256,
                       'selection_receipt_sha256': selection.receipt_sha256,
                       'h5py_version': h5py.__version__,
                       'source_library_declarations': runtime.provenance}
    parent_fd = route._open_directory_without_symlinks(path.parent, forbidden_identity=identity)
    root_fd = None
    try:
        root_fd = _new_directory(parent_fd, path.name)
        return _serialize_stream(bridge.iter_accepted_sessions(selection, route, runtime), root_fd=root_fd,
                                 expected_sessions=[s['session_id'] for s in sessions], expected_totals=TOTALS,
                                 runtime=runtime, h5py_module=h5py, budget=budget,
                                 source_identity=source_identity, authentic=True)
    finally:
        if root_fd is not None:
            os.close(root_fd)
        os.close(parent_fd)
