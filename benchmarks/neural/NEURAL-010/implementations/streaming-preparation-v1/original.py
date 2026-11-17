"""Pinned original NEURAL-010 semantics; no native library import at import time.

Only the operator CLI constructs Original. Generated controls use a separate
backend and cannot change the production source lock or original closure.
"""
import builtins
import hashlib
import hmac
import json
import os
from pathlib import Path
import stat
import time
import types

LOCK = {'bytes': 270520, 'sha256': '7485ba994f8d0a33f596e68d6f552d0849d911dd9c971bf9fbeee77dad1c4111'}
MANIFEST = {'bytes': 1630, 'sha256': 'ad64dcbe1f9543725f2e4720ad974a608c512e8a2c833adad37dfd23119baef9'}
NAMES = {'entry.py', 'prepare.py', 'storage.py', 'views.py', 'VENDOR_BINDINGS.json',
         'vendor/edf_adapter.py', 'vendor/reconcile_annotations.py', 'vendor/io_contract.py',
         'vendor/event_protocol.py', 'vendor/scorer.py'}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False,
                      separators=(',', ':')).encode() + b'\n'


def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def strict(body):
    def pairs(items):
        result = {}
        for k, v in items:
            need(k not in result, 'duplicate JSON key')
            result[k] = v
        return result
    def bad(_):
        raise ValueError('nonfinite JSON')
    return json.loads(body.decode(), object_pairs_hook=pairs, parse_constant=bad)


def path(value):
    need(type(value) is str and value.startswith('/') and not value.startswith('//')
         and '\x00' not in value and str(Path(value)) == value
         and all(x not in ('', '.', '..') for x in value.split('/')[1:]), 'canonical absolute path')
    p = Path(value)
    for q in [p, *p.parents]:
        need(not q.is_symlink(), 'no symlink component')
    return p


class Bootstrap:
    """Capped metadata preflight, reported separately from signal-operation costs.

    The independent launcher must reserve this 8 MiB / 30 s preflight before
    invocation, including failures before the workspace can be authenticated.
    """
    def __init__(self):
        self.read_bytes = 0
        self.end = time.monotonic() + 30

    def tick(self):
        need(time.monotonic() < self.end, 'bounded metadata preflight')

    def reserve(self, kind, n):
        need(kind == 'read' and type(n) is int and n >= 0, 'metadata-only preflight')
        self.read_bytes += n
        need(self.read_bytes <= 8 * 1048576, 'metadata preflight cap')
        self.tick()

    def read(self, p, expected, cap=1048576):
        need(type(expected) is dict and set(expected) == {'bytes', 'sha256'}
             and type(expected['bytes']) is int and 0 < expected['bytes'] <= cap,
             'bounded metadata descriptor')
        self.reserve('read', expected['bytes'] + 1)
        fd = os.open(path(str(p)), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            a = os.fstat(fd)
            need(stat.S_ISREG(a.st_mode) and a.st_nlink == 1 and a.st_size == expected['bytes'],
                 'ordinary exact metadata file')
            data = bytearray()
            while len(data) <= expected['bytes']:
                part = os.read(fd, min(65536, expected['bytes'] + 1 - len(data)))
                if not part:
                    break
                data.extend(part)
                self.tick()
            z = os.fstat(fd)
            need((a.st_dev, a.st_ino, a.st_size, a.st_mtime_ns, a.st_ctime_ns) ==
                 (z.st_dev, z.st_ino, z.st_size, z.st_mtime_ns, z.st_ctime_ns), 'stable metadata')
            data = bytes(data)
            need(pin(data) == expected, 'exact metadata bytes')
            return data
        finally:
            os.close(fd)


class Original:
    expected_records = 686
    expected_people = 23
    expected_views = 529
    route = 'neural010-streaming-original-semantics-v1'

    def __init__(self, request):
        need(type(request) is dict and set(request) ==
             {'original_source_root', 'lock_path', 'metadata_root', 'metadata_pins', 'key_path'},
             'exact original operand request')
        self.request = request
        self.bootstrap = Bootstrap()
        root = path(request['original_source_root'])
        meta = path(request['metadata_root'])
        lock_path = path(request['lock_path'])
        key_path = path(request['key_path'])
        need(not key_path.is_relative_to(meta) and not key_path.is_relative_to(root),
             'independent private key namespace')
        raw = self.bootstrap.read(root / 'SOURCE_MANIFEST.json', MANIFEST)
        manifest = strict(raw)
        need(manifest['schema'] == 'neural010-preparation-runtime-sources-v1'
             and len(manifest['files']) == len(NAMES)
             and {r['name'] for r in manifest['files']} == NAMES, 'exact original source closure')
        bodies = {r['name']: self.bootstrap.read(root / r['name'],
                  {k: r[k] for k in ('bytes', 'sha256')}) for r in manifest['files']}
        # Original entry authenticates/assembles these same immutable modules.
        entry = types.ModuleType('neural010_original_captured_entry')
        entry.__file__ = str(root / 'entry.py')
        exec(compile(bodies['entry.py'], entry.__file__, 'exec'), entry.__dict__)
        modules = entry.compile_captured(bodies, root)
        self.views = modules['views']
        lock_raw = self.bootstrap.read(lock_path, LOCK, 300000)
        self.lock = strict(lock_raw)
        self.rows = self.lock['records']
        need(self.lock['version'] == '1.0.0' and len(self.rows) == 686
             and len({r['path'] for r in self.rows}) == 686
             and len({r['patient'] for r in self.rows}) == 23
             and len({r['case'] for r in self.rows}) == 24, 'complete original cohort')
        required = {'RECORDS', 'RECORDS-WITH-SEIZURES', 'chb07_19.edf.seizures'}
        required.update(r['path'].split('/')[0] + '-summary.txt' for r in self.lock['summaries'])
        required.update(r['path'].split('/')[0] + '-index.html' for r in self.lock['summaries'])
        pins = request['metadata_pins']
        need(type(pins) is dict and set(pins) == required, 'all 51 original metadata operands')
        need(pins['RECORDS']['sha256'] == self.lock['records_manifest_sha256']
             and pins['RECORDS-WITH-SEIZURES']['sha256'] == self.lock['positive_manifest_sha256'],
             'original inventory pins')
        for row in self.lock['summaries']:
            name = row['path'].split('/')[0] + '-summary.txt'
            need(pins[name] == {k: row[k] for k in ('bytes', 'sha256')}, 'original summary identity')
        # Authenticate every operand even if reconciliation does not use every one.
        for name, expected in sorted(pins.items()):
            self.bootstrap.read(meta / name, expected)
        self.annotation_reads = []
        rec, self.edf, _, _ = modules['prepare'].load_vendor(
            self.bootstrap, meta, pins, self.annotation_reads, bodies)
        self.annotations = rec.compile_annotations(self.lock, meta)['records']
        need(set(self.annotations) == {r['path'] for r in self.rows}, 'complete reconciled annotations')
        # The original secret reader never hashes or serializes key material.
        key = modules['prepare']._secret(key_path, self.bootstrap)
        self.bindings = []
        for row in self.rows:
            self.bindings.append({'source_path': row['path'],
                'recording_id': hmac.new(key, ('record:' + row['path']).encode(), hashlib.sha256).hexdigest()[:24],
                'patient_id': hmac.new(key, ('patient:' + row['patient']).encode(), hashlib.sha256).hexdigest()[:24]})
        del key
        need(len({b['recording_id'] for b in self.bindings}) == 686
             and len({b['patient_id'] for b in self.bindings}) == 23, 'unique complete opaque identities')
        self.identity = {'route': self.route, 'lock': LOCK, 'original_source_manifest': MANIFEST,
                         'request': request, 'bindings': self.bindings,
                         'annotation_bytes': pin(encoded(self.annotations))}

    def project(self, source, destination, row):
        # No alternate verify/header/scaling/array path is provided.
        return self.edf.project(source, destination, row)

    def record(self, row, binding, header, projection):
        duration = header['duration_seconds']
        events = self.annotations[row['path']]['events']
        last = -1
        for a, b in events:
            need(type(a) in (int, float) and type(b) in (int, float)
                 and a == int(a) and b == int(b) and 0 <= a < b <= duration and a >= last,
                 'complete original observed annotation alignment')
            last = b
        labels = [c['label'] for c in header['selected_channels']]
        montage = hashlib.sha256(encoded(sorted(labels))[:-1]).hexdigest()
        rid, pid = binding['recording_id'], binding['patient_id']
        panel = {'recording_id': rid, 'patient_id': pid, 'duration_seconds': duration,
                 'observed_intervals': [[0, duration]], 'path': 'signals/' + rid + '.h5', **projection}
        metadata = {'recording_id': rid, 'patient_id': pid, 'duration_seconds': duration,
                    'montage_id': montage, 'channel_count': len(labels), 'channel_labels': labels,
                    'source_edf': {k: row[k] for k in ('bytes', 'sha256')},
                    'target_free_projection': projection}
        provenance = {'recording_id': rid, 'source_path': row['path'],
                      'source_edf': {k: row[k] for k in ('bytes', 'sha256')}, 'header': header,
                      'annotation_evidence': self.annotations[row['path']]['evidence']}
        return {'panel': panel, 'metadata': metadata, 'target': {'recording_id': rid, 'events': events},
                'provenance': provenance}

    def payloads(self, records):
        need(len(records) == 686, 'no partial cohort publication')
        metadata = sorted((r['metadata'] for r in records), key=lambda r: r['recording_id'])
        self.views.validate_rows(metadata)
        panel = encoded({'schema_version': 1, 'task_id': 'NEURAL-009',
                         'records': sorted((r['panel'] for r in records), key=lambda r: r['recording_id'])})
        assessment = encoded({'schema_version': 1, 'task_id': 'NEURAL-009',
            'panel_sha256': pin(panel)['sha256'],
            'records': sorted((r['target'] for r in records), key=lambda r: r['recording_id'])})
        payloads = {'public/panel.json': panel,
                    'public/metadata.json': encoded({'schema': 'neural010-target-free-metadata-v1', 'records': metadata}),
                    'private/assessment.json': assessment,
                    'private/SOURCE_PROVENANCE.json': encoded({'records': [r['provenance'] for r in records]})}
        # All original views are evaluated and pinned, but duplicate payloads are
        # materialized on demand. Their byte-generation semantics stay unchanged.
        index = []
        for view in self.view_documents(records):
            index.append({'name': view['name'], 'artifacts': {
                n: pin(view[n]) for n in ('TRAIN.json', 'QUERY.json', 'SUPPORT.json', 'VALIDATION.json')
                if view[n] is not None}})
        need(len(index) == 529, 'complete 23 final and 506 inner views')
        payloads['private/VIEWS.json'] = encoded({'schema': 'neural010-lazy-original-views-v1',
                                                 'views': index})
        return payloads

    def view_documents(self, records):
        rows = [r['metadata'] for r in records]
        annotations = {r['target']['recording_id']: r['target']['events'] for r in records}
        yield from self.views.make_views(rows, annotations)
