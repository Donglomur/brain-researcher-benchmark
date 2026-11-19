"""Full ABR numeric delivery and case-local views; source only until selected.

The accepted NativeTarget/Pair/scorer code is not changed.  A separately pinned,
private, read-only f64le scratch descriptor replaces its gzip seek/read backend
after one complete authenticated expansion.  No function here opens targets.
This operator adapter is not a candidate sandbox or a model execution route.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import html
import json
import os
from pathlib import Path
import stat
import time
import types


IMPLEMENTATION_PIN = (31191, '502d99158a16f87511bba36106a0c0b206947907ff93fc61cbb9bffaf89f4aa1')
RASTER_PIN = (8179, 'b8cc040978a38104a9adc7747748411e4abe61aa9df9c5a6cdd3c00902dd2a18')
DOCUMENTS_PIN = (3489, '455d5777bd6e49162055cbccfff079689517d8934bebc1a6adf4e49ee0c7b754')
COMPLETE_PIN = (22643, '507b7e77a2a4d09f5056e6191efe34db7092ca4eab70a4880e425ae7eade1972')
MODE = 'abr-release-annotation-code-agreement-zero-support-v1'
CASE_COUNT, TRACE_COUNT, SAMPLES_PER_TRACE = 936, 16226, 1953
TOTAL_SAMPLES = 31689378
SCRATCH_BYTES = TOTAL_SAMPLES * 8
MIB = 1024 ** 2
PACKET_LIMIT = 16 * MIB
NUMERIC_TOTAL_LIMIT = 1024 * MIB
INDEX_LIMIT = 2 * MIB
ROSTER_LIMIT = 16 * MIB
MANIFEST_LIMIT = 64 * 1024
PAGE_LIMIT = 4 * MIB
VIEW_LIMIT = 384 * MIB
# One private scratch, all numeric packets, and complete bounded metadata.
PREPARE_LIMIT = SCRATCH_BYTES + NUMERIC_TOTAL_LIMIT + 24 * MIB
MAX_TRACES_PER_CASE = 256
MAX_PAGES_PER_CASE = 86
TOTAL_PAGE_LIMIT = (TRACE_COUNT + 2 * CASE_COUNT) // 3
HOLDS = {'candidate_delivery_admitted': False, 'authentic_scoring_admitted': False,
         'scientifically_qualified': False, 'new_benchmark_count': 0}


def need(condition, message):
    if not condition:
        raise ValueError(message)


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def digest(body):
    return hashlib.sha256(body).hexdigest()


def identity(st):
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)


def ordinary_path(path):
    path = Path(path).absolute()
    for part in (path, *path.parents):
        need(not part.is_symlink(), 'symlink in operator path')
    return path


def pinned_bytes(path, pin, cap):
    path = ordinary_path(path)
    need(type(pin) in (tuple, list) and len(pin) == 2 and type(pin[0]) is int and 0 <= pin[0] <= cap, 'file pin/cap')
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == pin[0], 'ordinary pinned file required')
        body = stream.read(pin[0] + 1)
        need(len(body) == pin[0] and digest(body) == pin[1], 'file pin differs')
        need(identity(before) == identity(os.fstat(stream.fileno())), 'file changed during read')
    return body


def load_sources(implementation_path, raster_path, documents_path):
    """Called only by a separately selected operator invocation, never on import."""
    raw = pinned_bytes(implementation_path, IMPLEMENTATION_PIN, 65536)
    release = types.ModuleType('abr_delivery_accepted_release')
    release.__file__ = str(ordinary_path(implementation_path))
    exec(compile(raw, release.__file__, 'exec'), release.__dict__)
    raw = pinned_bytes(raster_path, RASTER_PIN, 16384)
    raster = types.ModuleType('abr_delivery_accepted_raster')
    exec(compile(raw, str(raster_path), 'exec'), raster.__dict__)
    documents = pinned_bytes(documents_path, DOCUMENTS_PIN, 4096)
    need(release.COMPLETE_PIN == COMPLETE_PIN and release.MODE == MODE, 'accepted source contract differs')
    return release, raster, documents


class Budget:
    """Failure-inclusive requested publication bytes; not physical I/O or RAM."""
    def __init__(self, limit, deadline):
        need(type(limit) is int and limit > 0, 'positive artifact limit')
        self.limit, self.deadline = limit, deadline
        self.requested = self.confirmed = 0

    def check_time(self):
        need(time.monotonic() < self.deadline, 'selected operation deadline exceeded')

    def reserve(self, size):
        self.check_time()
        need(type(size) is int and size >= 0 and self.requested + size <= self.limit, 'selected artifact budget exceeded')
        self.requested += size

    def put(self, path, body, cap):
        need(type(body) is bytes and len(body) <= cap, 'publication body cap')
        self.reserve(len(body))
        path = ordinary_path(path)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        self.confirmed += len(body)
        return {'bytes': len(body), 'sha256': digest(body)}


class ScratchReader:
    """Bounded random access on one retained, authenticated read-only descriptor."""
    def __init__(self, stream, expected_bytes):
        self.stream = stream
        self.before = os.fstat(stream.fileno())
        need(stat.S_ISREG(self.before.st_mode) and self.before.st_nlink == 1 and self.before.st_size == expected_bytes, 'scratch extent/type')
        self.extent = expected_bytes
        self.position = 0

    def check(self):
        need(identity(self.before) == identity(os.fstat(self.stream.fileno())), 'scratch descriptor changed')

    def seek(self, offset):
        self.check()
        need(type(offset) is int and 0 <= offset <= self.extent and offset % 8 == 0, 'scratch seek bounds')
        result = self.stream.seek(offset)
        need(result == offset, 'scratch seek position')
        self.position = offset
        self.check()
        return result

    def read(self, size):
        self.check()
        need(type(size) is int and 0 <= size <= SAMPLES_PER_TRACE * 8 and self.position + size <= self.extent, 'scratch read bounds')
        raw = self.stream.read(size)
        need(len(raw) == size, 'short scratch read')
        self.position += size
        self.check()
        return raw


def _install_scratch(release, target, scratch_path, pin):
    need(pin[0] == SCRATCH_BYTES, 'complete scratch extent')
    stream = target._stack.enter_context(release.pinned_open(scratch_path, tuple(pin)))
    target._waveforms = ScratchReader(stream, SCRATCH_BYTES)
    # The original gzip object remains in the accepted target's ExitStack.  Its
    # compressed descriptor retains the original complete-file pin and stat guard.
    need(target.packet.__func__ is release.NativeTarget.packet, 'native packet method changed')
    return target


def expand_once(release, target, scratch_path, budget):
    """One gzip traversal, exact full extent plus EOF, never per-trace gzip seek."""
    target._verify_observation_source()
    need(target.roster.samples == SAMPLES_PER_TRACE and target.roster.trace_count == TRACE_COUNT and target.roster.total_samples == TOTAL_SAMPLES, 'complete native population')
    need(target._waveforms.tell() == 0, 'scratch expansion requires a fresh native reader')
    scratch_path = ordinary_path(scratch_path)
    budget.reserve(SCRATCH_BYTES)
    fd = os.open(scratch_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    sha = hashlib.sha256()
    observed = 0
    with os.fdopen(fd, 'wb') as stream:
        while observed < SCRATCH_BYTES:
            budget.check_time()
            raw = target._waveforms.read(min(MIB, SCRATCH_BYTES - observed))
            need(bool(raw), 'short complete waveform expansion')
            stream.write(raw)
            sha.update(raw)
            observed += len(raw)
        need(target._waveforms.read(1) == b'', 'extra complete waveform samples')
        stream.flush()
        os.fsync(stream.fileno())
    need(observed == SCRATCH_BYTES, 'waveform expansion extent differs')
    os.chmod(scratch_path, 0o400)
    budget.confirmed += observed
    pin = (observed, sha.hexdigest())
    return _install_scratch(release, target, scratch_path, pin), pin


def _fresh_directory(path):
    path = ordinary_path(path)
    need(path.parent.is_dir() and not path.exists(), 'fresh destination with existing ordinary parent required')
    path.mkdir(mode=0o700)
    return path


def _roster_record(release, target, case_id, body):
    packet = release.decode(body)
    release.validate_packet(packet)
    meta = target.roster.cases[case_id]
    need(packet['case_id'] == case_id and [t['trace_id'] for t in packet['traces']] == meta['trace_ids'], 'packet does not conserve observed trace roster')
    count = len(packet['traces'])
    need(1 <= count <= MAX_TRACES_PER_CASE, 'native variable trace bound')
    for t in packet['traces']:
        need(len(t['samples']) == SAMPLES_PER_TRACE, 'native sample extent changed')
        need(all(type(v) is float for v in t['samples']), 'native f64 sample representation changed')
    pages = release.panels(packet)
    need(len(pages) == (count + 2) // 3 <= MAX_PAGES_PER_CASE, 'complete page enumeration')
    return {'case_id': case_id, 'packet_path': 'public/cases/' + case_id + '.json',
            'packet_pin': [len(body), digest(body)], 'trace_count': count,
            'sample_count': count * SAMPLES_PER_TRACE, 'page_count': len(pages)}


def prepare(release, documents, native_root, destination, budget):
    """Prepare all 936 public packets; retain original order and a private spool.

    Failure leaves owned partial output and no COMPLETE.json.  No caller may use
    a partially prepared cohort or substitute generated cases for this route.
    """
    root = _fresh_directory(destination)
    for name in ('private', 'operator', 'public', 'public/cases'):
        (root / name).mkdir(mode=0o700)
    target = None
    try:
        target = release.NativeTarget(native_root)
        target, scratch_pin = expand_once(release, target, root / 'private/waveforms.f64le', budget)
        budget.put(root / 'public/COMMON_DOCUMENTATION.txt', documents, 4096)
        rows, numeric_bytes, total_pages = [], 0, 0
        for cid in target.roster.ids:
            budget.check_time()
            packet = target.packet(cid)  # Exact accepted method, now ordinary-file seeks.
            body = release.canonical(packet)
            need(len(body) <= PACKET_LIMIT, 'whole case exceeds selected packet capacity; no truncation')
            row = _roster_record(release, target, cid, body)
            numeric_bytes += len(body)
            need(numeric_bytes <= NUMERIC_TOTAL_LIMIT, 'complete numeric store capacity exceeded')
            budget.put(root / row['packet_path'], body, PACKET_LIMIT)
            rows.append(row)
            total_pages += row['page_count']
        need(len(rows) == CASE_COUNT and sum(r['trace_count'] for r in rows) == TRACE_COUNT and sum(r['sample_count'] for r in rows) == TOTAL_SAMPLES, 'complete numeric denominator')
        need(total_pages <= TOTAL_PAGE_LIMIT, 'complete page bound')
        target._verify_observation_source()
        roster = {'cases': list(target.roster.cases.values()), 'traces': list(target.roster.traces.values())}
        roster_body = release.canonical(roster)
        need(digest(roster_body) == target.roster.identity, 'prepared public roster identity differs')
        roster_pin = budget.put(root / 'operator/ROSTER.json', roster_body, ROSTER_LIMIT)
        index = {'schema': 'abr-complete-public-packet-index-v1', 'mode': MODE,
                 'source_complete_sha256': COMPLETE_PIN[1], 'roster_sha256': target.roster.identity,
                 'case_count': CASE_COUNT, 'trace_count': TRACE_COUNT, 'sample_count': TOTAL_SAMPLES,
                 'page_count': total_pages, 'cases': rows,
                 'index_access': 'operator only; expose exactly one fresh case to either arm'}
        index_pin = budget.put(root / 'operator/INDEX.json', release.canonical(index), INDEX_LIMIT)
        scratch = {'schema': 'abr-private-sequential-waveform-spool-v1', 'source_complete_sha256': COMPLETE_PIN[1],
                   'source_waveform_pin': list(target.pins[release.TARGET_KEYS[2]]), 'scratch_pin': list(scratch_pin),
                   'source_gzip_expansions': 1, 'format': 'f64le', 'sample_count': TOTAL_SAMPLES,
                   'use': 'private operator backend only; no target labels or candidate mount'}
        scratch_doc_pin = budget.put(root / 'private/SCRATCH.json', release.canonical(scratch), MANIFEST_LIMIT)
        # Stable first-observed tie breaking: no target labels or case omission.
        capacity_case = max(rows, key=lambda r: (r['trace_count'], r['packet_pin'][0]))
        largest_packet = max(rows, key=lambda r: r['packet_pin'][0])
        manifest = {'schema': 'abr-complete-delivery-preparation-v1', 'mode': MODE,
                    'native_complete_pin': list(COMPLETE_PIN), 'implementation_pin': list(IMPLEMENTATION_PIN),
                    'raster_pin': list(RASTER_PIN), 'documents_pin': list(DOCUMENTS_PIN),
                    'index_pin': index_pin, 'roster_pin': roster_pin, 'scratch_descriptor_pin': scratch_doc_pin,
                    'cases': CASE_COUNT, 'traces': TRACE_COUNT, 'samples': TOTAL_SAMPLES,
                    'numeric_bytes': numeric_bytes, 'pages_available_on_demand': total_pages,
                    'pages_materialized': 0, 'representation': 'same complete canonical packet and complete raw-axis page enumeration',
                    'capacity_view_case_id': capacity_case['case_id'],
                    'capacity_view_selection': 'max(trace_count,packet_bytes), first observed case on exact tie',
                    'maximum_packet_case_id': largest_packet['case_id'], 'maximum_packet_bytes': largest_packet['packet_pin'][0],
                    'maximum_case_traces': capacity_case['trace_count'], 'maximum_case_pages': capacity_case['page_count'],
                    'minimum_case_traces': min(r['trace_count'] for r in rows),
                    'population_statement': '104 animals in fixed authenticated native seal; no private animal/target projection opened here',
                    'source_gzip_expansions': 1, 'protected_target_open_count': 0,
                    'requested_bytes_before_manifest': budget.requested,
                    'confirmed_bytes_before_manifest': budget.confirmed, **HOLDS}
        # Finish the accepted descriptor lifetime before announcing completeness.
        target.close()
        target = None
        budget.put(root / 'COMPLETE.json', release.canonical(manifest), MANIFEST_LIMIT)
        return manifest
    except BaseException:
        # A hard failure intentionally leaves no completion claim. The outer
        # selected operation owns failure capture and all partial-output costs.
        raise
    finally:
        if target is not None:
            target.close()


def _pin(row):
    return (row['bytes'], row['sha256'])


def open_store(release, root, complete_pin):
    """An externally frozen completion pin is mandatory; no trust-on-first-use."""
    root = ordinary_path(root)
    m = release.decode(pinned_bytes(root / 'COMPLETE.json', complete_pin, MANIFEST_LIMIT))
    need(m['schema'] == 'abr-complete-delivery-preparation-v1' and m['mode'] == MODE and
         m['native_complete_pin'] == list(COMPLETE_PIN) and m['implementation_pin'] == list(IMPLEMENTATION_PIN) and
         m['raster_pin'] == list(RASTER_PIN) and m['documents_pin'] == list(DOCUMENTS_PIN), 'prepared store source identity')
    need(m['cases'] == CASE_COUNT and m['traces'] == TRACE_COUNT and m['samples'] == TOTAL_SAMPLES, 'prepared complete denominator')
    for key, value in HOLDS.items():
        need(m[key] == value, 'prepared store qualification flag changed')
    index = release.decode(pinned_bytes(root / 'operator/INDEX.json', _pin(m['index_pin']), INDEX_LIMIT))
    need(index['source_complete_sha256'] == COMPLETE_PIN[1] and len(index['cases']) == CASE_COUNT, 'prepared index identity')
    records = {}
    for row in index['cases']:
        cid = release.opaque(row['case_id'])
        need(cid not in records and row['packet_path'] == 'public/cases/' + cid + '.json', 'prepared index duplicate/path')
        need(1 <= row['trace_count'] <= MAX_TRACES_PER_CASE and row['sample_count'] == row['trace_count'] * SAMPLES_PER_TRACE and
             row['page_count'] == (row['trace_count'] + 2) // 3, 'prepared variable case extent')
        records[cid] = row
    need(sum(r['trace_count'] for r in records.values()) == TRACE_COUNT and sum(r['sample_count'] for r in records.values()) == TOTAL_SAMPLES and
         sum(r['page_count'] for r in records.values()) == m['pages_available_on_demand'] <= TOTAL_PAGE_LIMIT, 'prepared index totals')
    documents = pinned_bytes(root / 'public/COMMON_DOCUMENTATION.txt', DOCUMENTS_PIN, 4096)
    return root, m, index, records, documents


def load_roster(release, root, manifest, index):
    """Reconstruct the accepted Roster from public metadata, never private IDs."""
    raw = pinned_bytes(Path(root) / 'operator/ROSTER.json', _pin(manifest['roster_pin']), ROSTER_LIMIT)
    need(digest(raw) == index['roster_sha256'], 'public roster digest differs')
    value = release.decode(raw)
    need(type(value) is dict and set(value) == {'cases', 'traces'}, 'public roster fields differ')
    roster = release.Roster(value['cases'], value['traces'])
    need(roster.identity == index['roster_sha256'] and list(roster.ids) == [r['case_id'] for r in index['cases']], 'observed roster order differs')
    return roster


def public_packet(release, root, records, case_id):
    """Exactly one pinned canonical packet; caller confines candidate access."""
    need(case_id in records, 'unknown observed case')
    row = records[case_id]
    raw = pinned_bytes(Path(root) / row['packet_path'], row['packet_pin'], PACKET_LIMIT)
    packet = release.decode(raw)
    release.validate_packet(packet)
    need(packet['case_id'] == case_id and len(packet['traces']) == row['trace_count'] and
         all(len(t['samples']) == SAMPLES_PER_TRACE for t in packet['traces']), 'prepared packet extent differs')
    need(release.canonical(packet) == raw, 'prepared packet is not canonical')
    return raw, packet


@contextlib.contextmanager
def prepared_native(release, native_root, store_root, store_complete_pin):
    """Return the genuine accepted NativeTarget for Pair and label-last scoring.

    Reauthentication hashes the compressed source; it does not decompress it.
    The private spool is freshly hashed once, retained read-only and stat-checked
    on every trace seek/read. Pair's exact native provider guard remains active.
    """
    root, manifest, index, rows, _ = open_store(release, store_root, store_complete_pin)
    target = release.NativeTarget(native_root)
    try:
        need(target.roster.identity == index['roster_sha256'] and list(target.roster.ids) == list(rows), 'prepared native roster changed')
        scratch = release.decode(pinned_bytes(root / 'private/SCRATCH.json', _pin(manifest['scratch_descriptor_pin']), MANIFEST_LIMIT))
        need(scratch['source_complete_sha256'] == COMPLETE_PIN[1] and scratch['source_waveform_pin'] == list(target.pins[release.TARGET_KEYS[2]]) and
             scratch['sample_count'] == TOTAL_SAMPLES and scratch['format'] == 'f64le', 'private scratch source identity')
        _install_scratch(release, target, root / 'private/waveforms.f64le', scratch['scratch_pin'])
        yield target
    finally:
        target.close()


def case_view(release, raster, store_root, store_complete_pin, case_id, destination, budget):
    """One candidate case folder: exact numeric input, instructions, all pages.

    No original/native bundle or private scratch/label path is read by this route.
    No server, script, network reference, filter, resampling or viewport omission.
    """
    root, manifest, _, rows, documents = open_store(release, store_root, store_complete_pin)
    need(case_id in rows, 'unknown observed case')
    row = rows[case_id]
    raw, packet = public_packet(release, root, rows, case_id)
    destination = _fresh_directory(destination)
    budget.put(destination / 'numeric.json', raw, PACKET_LIMIT)
    budget.put(destination / 'COMMON_DOCUMENTATION.txt', documents, 4096)
    pages = []
    drawn = 0
    for page in range(row['page_count']):
        budget.check_time()
        image, meta = release.render(packet, page, raster)
        expected = list(range(page * 3, min((page + 1) * 3, row['trace_count'])))
        need(meta['trace_indices'] == expected and meta['samples_drawn'] == len(expected) * SAMPLES_PER_TRACE, 'rendered complete sample/page coverage')
        name = 'page-' + str(page + 1).zfill(3) + '.png'
        pin = budget.put(destination / name, image, PAGE_LIMIT)
        pages.append({'path': name, 'pin': pin, **meta})
        drawn += meta['samples_drawn']
    need(drawn == row['sample_count'], 'complete case visual coverage differs')
    view = {'schema': 'abr-one-case-complete-view-v1', 'case_id': case_id,
            'packet_pin': row['packet_pin'], 'documents_pin': list(DOCUMENTS_PIN),
            'trace_count': row['trace_count'], 'sample_count': drawn, 'pages': pages,
            'precision': 'Full numeric packet is authoritative; all samples rasterized with possible shared pixels.',
            'context_status': 'No model context capacity or participant delivery qualification inferred.', **HOLDS}
    budget.put(destination / 'VIEW.json', release.canonical(view), MANIFEST_LIMIT)
    elements = ['<!doctype html><html lang="en"><meta charset="utf-8">',
                '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; img-src \'self\'; style-src \'unsafe-inline\'">',
                '<title>ABR complete case</title><style>body{font-family:system-ui;max-width:1400px;margin:auto}img{max-width:100%;height:auto}pre{white-space:pre-wrap}</style>',
                '<h1>ABR case ' + html.escape(case_id) + '</h1>',
                '<p><a href="numeric.json">Complete numeric packet</a> · <a href="COMMON_DOCUMENTATION.txt">Common instructions</a></p>',
                '<p>Sample index and native raw values. All recorded traces and all 1,953 samples per trace are retained. Numeric values are authoritative.</p>',
                '<pre>' + html.escape(documents.decode('utf-8')) + '</pre>']
    for page in pages:
        elements.append('<p>Page ' + str(page['page'] + 1) + ' of ' + str(len(pages)) + '</p><img src="' + page['path'] + '" alt="Complete raw-axis trace page">')
    elements.append('</html>')
    budget.put(destination / 'index.html', ('\n'.join(elements) + '\n').encode(), MANIFEST_LIMIT)
    return view


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--implementation', required=True)
    parser.add_argument('--raster', required=True)
    parser.add_argument('--documents', required=True)
    parser.add_argument('--deadline-seconds', required=True, type=float)
    sub = parser.add_subparsers(dest='operation', required=True)
    prep = sub.add_parser('prepare')
    prep.add_argument('--native-root', required=True)
    prep.add_argument('--output', required=True)
    view = sub.add_parser('view')
    view.add_argument('--store', required=True)
    view.add_argument('--store-complete-bytes', required=True, type=int)
    view.add_argument('--store-complete-sha256', required=True)
    view.add_argument('--case-id', required=True)
    view.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    need(0 < args.deadline_seconds <= 3600, 'finite selected deadline must be at most one hour')
    origin = time.monotonic()
    release, raster, documents = load_sources(args.implementation, args.raster, args.documents)
    budget = Budget(PREPARE_LIMIT if args.operation == 'prepare' else VIEW_LIMIT, origin + args.deadline_seconds)
    if args.operation == 'prepare':
        prepare(release, documents, args.native_root, args.output, budget)
    else:
        case_view(release, raster, args.store, (args.store_complete_bytes, args.store_complete_sha256), args.case_id, args.output, budget)
    print(json.dumps({'status': 'complete_operator_artifact', 'operation': args.operation,
                      'requested_bytes': budget.requested, 'confirmed_bytes': budget.confirmed,
                      'elapsed_seconds': time.monotonic() - origin, **HOLDS}, sort_keys=True))


if __name__ == '__main__':
    main()
