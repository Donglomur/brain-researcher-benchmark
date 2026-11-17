"""Truthful original/streaming preparation admission and descriptor composition.

Admission opens no signal, key, annotation, assessment, record-receipt target,
TRAIN or VALIDATION bodies. Operator detection projection is a separate API.
This module does not qualify sources, providers, process custody or references.
"""
import argparse
import builtins
from collections.abc import Mapping
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import time
import types

LOCK = {'bytes': 270520, 'sha256': '7485ba994f8d0a33f596e68d6f552d0849d911dd9c971bf9fbeee77dad1c4111'}
ORIGINAL_MANIFEST = {'bytes': 1630, 'sha256': 'ad64dcbe1f9543725f2e4720ad974a608c512e8a2c833adad37dfd23119baef9'}
VENDOR_PIN = {'bytes': 1236, 'sha256': '415942846657b0eae7381da13703dceec1ec6200f39552f20f5e15077918a859'}
RECORDS_PIN = {'bytes': 13056, 'sha256': '72b640d6a3fef4b40de255933d1403823d1655c56f93d69761105a653798fc08'}
DETECTION_PIN = {'bytes': 20531, 'sha256': '76ef4eaa8ff13e382f6a308192f16da5fb67f0221a86ec44bf9cee1cfb237b66'}
SCORER_PIN = {'bytes': 13273, 'sha256': 'e72a814446744f1ca5ecb7b581c702c671983b4280ee876347d36016d8edd0c5'}
REFERENCE_SOURCES = {
    'common.py': {'bytes': 10788, 'sha256': '78af855c91d81efd3e2eede6c01677a0d718fe54f51d567319f6adf7209d13a2'},
    'schedule.py': {'bytes': 5536, 'sha256': 'a9dfd82d7cece92521e28cb378ef8624506294ff12c19f9300ddd400174a3d8a'},
    'arrays.py': {'bytes': 1739, 'sha256': '755535f44c96a9b435322707faf52414416d723bdf9dd68a7768763c61d0bce1'},
    'reference_study.py': {'bytes': 19251, 'sha256': '8bfaca554e263a674b5389195cc1c416a8befda91380073efbc2fac2e0620d35'}}
COUNTERS = ('read_bytes', 'write_bytes', 'input_bytes', 'attempts')
PAYLOADS = ('public/panel.json', 'public/metadata.json', 'private/assessment.json',
            'private/SOURCE_PROVENANCE.json', 'private/VIEWS.json')
META_CAP = 32 * 1048576
EVENT_CAP = 65536


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def exact(value, keys):
    need(type(value) is dict and set(value) == set(keys), 'exact fields: ' + ','.join(keys))
    return value


def integer(value, lo=0, hi=2**63 - 1):
    need(type(value) is int and lo <= value <= hi, 'strict bounded integer')
    return value


def finite(value):
    need(type(value) in (int, float) and math.isfinite(value), 'finite number, not bool')
    return value


def same(a, b):
    if type(a) is not type(b):
        return False
    if type(a) is dict:
        return a.keys() == b.keys() and all(type(k) is str and same(a[k], b[k]) for k in a)
    if type(a) is list:
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    if type(a) is float:
        return math.isfinite(a) and math.isfinite(b) and a.hex() == b.hex()
    return type(a) in (str, int, bool, type(None)) and a == b


def encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False,
                      separators=(',', ':')).encode() + b'\n'


def parse(body):
    need(type(body) is bytes, 'immutable captured bytes')
    def pairs(rows):
        result = {}
        for k, v in rows:
            need(k not in result, 'duplicate JSON key')
            result[k] = v
        return result
    def bad(_):
        raise ValueError('nonfinite JSON')
    return json.loads(body.decode(), object_pairs_hook=pairs, parse_constant=bad)


def pin(body):
    need(type(body) is bytes, 'immutable bytes to pin')
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def digest(value):
    need(type(value) is str and re.fullmatch(r'[0-9a-f]{64}', value), '64 hex digest')
    return value


def ident(value):
    need(type(value) is str and re.fullmatch(r'[0-9a-f]{24}', value), '24 hex identity')
    return value


def descriptor(value, located=False):
    exact(value, ('path', 'bytes', 'sha256') if located else ('bytes', 'sha256'))
    integer(value['bytes'], 1)
    digest(value['sha256'])
    if located:
        absolute(value['path'])
    return value


def bare(value):
    return {k: value[k] for k in ('bytes', 'sha256')}


def absolute(value):
    need(type(value) is str and value.startswith('/') and not value.startswith('//')
         and '\x00' not in value and '\\' not in value, 'absolute POSIX path')
    p = Path(value)
    need(str(p) == value and all(v not in ('', '.', '..') for v in value.split('/')[1:]), 'canonical path')
    return p


def located(root, name, value):
    descriptor(value)
    p = root / name
    need(p.is_relative_to(root) and all(x not in ('', '.', '..') for x in name.split('/')), 'confined named operand')
    return {'path': str(p), **value}


class FileIO:
    """Bounded read-only metadata capture; hard containment remains external."""
    def __init__(self, roots, read_bytes, seconds=30):
        self.roots = [absolute(str(p)) for p in roots]
        self.limit = integer(read_bytes, 1, 256 * 1048576)
        self.used = 0
        self.end = time.monotonic() + integer(seconds, 1, 180)
        self.accesses = []

    def charge(self, n):
        integer(n)
        need(time.monotonic() < self.end and self.used + n <= self.limit, 'bounded metadata admission')
        self.used += n

    def checked(self, value):
        p = absolute(str(value))
        need(any(p == r or p.is_relative_to(r) for r in self.roots), 'selected metadata root')
        need(not any(q.is_symlink() for q in [p, *p.parents]), 'no symlink components')
        return p

    def capture(self, desc, role, cap=META_CAP):
        descriptor(desc, True)
        need(desc['bytes'] <= cap, 'bounded operand extent')
        self.charge(desc['bytes'] + 1)
        p = self.checked(desc['path'])
        fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            a = os.fstat(fd)
            need(stat.S_ISREG(a.st_mode) and a.st_nlink == 1 and a.st_size == desc['bytes'], 'ordinary exact metadata')
            output = bytearray()
            while len(output) <= desc['bytes']:
                self.charge(0)
                part = os.read(fd, min(65536, desc['bytes'] + 1 - len(output)))
                if not part:
                    break
                output.extend(part)
            z, named = os.fstat(fd), p.lstat()
            fields = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns', 'st_mode', 'st_nlink')
            need(all(getattr(a, k) == getattr(z, k) == getattr(named, k) for k in fields), 'stable captured metadata')
            output = bytes(output)
            need(same(pin(output), bare(desc)), 'exact metadata hash')
            self.accesses.append({'path': str(p), 'role': role, 'bytes': len(output)})
            return output
        finally:
            os.close(fd)

    def journal_body(self, p, role):
        p = self.checked(p)
        s = p.lstat()
        need(stat.S_ISREG(s.st_mode) and s.st_nlink == 1 and 0 < s.st_size <= EVENT_CAP, 'ordinary bounded journal frame')
        self.charge(s.st_size + 1)
        fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            a = os.fstat(fd)
            fields = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns', 'st_mode', 'st_nlink')
            need(all(getattr(a, k) == getattr(s, k) for k in fields), 'same journal file')
            raw = os.read(fd, s.st_size + 1)
            z, named = os.fstat(fd), p.lstat()
            need(len(raw) == s.st_size and all(getattr(a, k) == getattr(z, k) == getattr(named, k)
                 for k in fields), 'stable complete journal')
            self.accesses.append({'path': str(p), 'role': role, 'bytes': len(raw)})
            return raw
        finally:
            os.close(fd)

    def names(self, root):
        p = self.checked(root)
        need(p.is_dir(), 'ordinary metadata directory')
        names = []
        for q in p.iterdir():
            need(len(names) < 10000 and not q.is_symlink(), 'bounded unlinked metadata namespace')
            names.append(q.name)
        return sorted(names)

    def stat_only(self, desc, role):
        descriptor(desc, True)
        self.charge(0)
        p = self.checked(desc['path'])
        s = p.lstat()
        need(stat.S_ISREG(s.st_mode) and s.st_nlink == 1 and s.st_size == desc['bytes'], 'materialized ordinary exact view extent')
        self.accesses.append({'path': str(p), 'role': role, 'body_opened': False})


def roster(raw):
    need(same(pin(raw), RECORDS_PIN), 'exact complete public RECORDS roster')
    names = raw.decode('ascii').splitlines()
    need(len(names) == 686 and len(set(names)) == 686, 'complete unique source roster')
    result = {}
    for name in names:
        # The exact roster hash, not an invented recording-number grammar,
        # defines membership. Original chb17 basenames include a/b/c suffixes.
        need(re.fullmatch(r'chb[0-9]{2}/[A-Za-z0-9_+.-]+\.edf', name), 'literal original record path')
        case = name.split('/')[0]
        result[name] = 'chb01' if case == 'chb21' else case
    need(len(set(result.values())) == 23, '23 biological source people')
    return result


def public_payloads(panel_raw, metadata_raw):
    p, m = parse(panel_raw), parse(metadata_raw)
    exact(p, ('schema_version', 'task_id', 'records'))
    need(type(p['schema_version']) is int and p['schema_version'] == 1 and p['task_id'] == 'NEURAL-009', 'original panel carrier')
    exact(m, ('schema', 'records'))
    need(m['schema'] == 'neural010-target-free-metadata-v1', 'target-free metadata carrier')
    rows, panel = m['records'], {}
    need(type(rows) is list and len(rows) == 686 and type(p['records']) is list and len(p['records']) == 686, 'full 686 support')
    for r in p['records']:
        exact(r, ('recording_id', 'patient_id', 'duration_seconds', 'observed_intervals', 'path', 'bytes', 'sha256'))
        ident(r['recording_id']); ident(r['patient_id']); integer(r['duration_seconds'], 1, 86400)
        need(r['recording_id'] not in panel, 'unique panel record')
        need(same(r['observed_intervals'], [[0, r['duration_seconds']]])
             and r['path'] == 'signals/' + r['recording_id'] + '.h5', 'complete original exposure and opaque projection path')
        descriptor(bare(r))
        panel[r['recording_id']] = r
    need([r['recording_id'] for r in rows] == sorted(panel), 'exact sorted full panel/metadata join')
    people = set()
    for r in rows:
        exact(r, ('recording_id', 'patient_id', 'duration_seconds', 'montage_id', 'channel_count', 'channel_labels', 'source_edf', 'target_free_projection'))
        ident(r['recording_id']); ident(r['patient_id']); integer(r['duration_seconds'], 1, 86400)
        people.add(r['patient_id'])
        q = panel[r['recording_id']]
        need(all(same(r[k], q[k]) for k in ('recording_id', 'patient_id', 'duration_seconds'))
             and same(r['target_free_projection'], bare(q)), 'same source projection/person/duration')
        descriptor(r['source_edf']); descriptor(r['target_free_projection'])
        integer(r['channel_count'], 1, 512)
        labels = r['channel_labels']
        need(type(labels) is list and len(labels) == r['channel_count']
             and all(type(x) is str and 0 < len(x) <= 256 and x.isprintable() for x in labels), 'complete ordered channel multiset')
        need(r['montage_id'] == hashlib.sha256(encoded(sorted(labels))[:-1]).hexdigest(), 'duplicate-preserving montage identity')
    need(len(people) == 23 and sum(r['duration_seconds'] for r in rows) <= 10000000, 'full biological/exposure support')
    return panel, rows, sorted(people)


def view_index(views, people):
    need(type(views) is list and len(views) == 529, 'exact 529 indexed views')
    expected = {p + '/final' for p in people} | {p + '/inner/' + q for p in people for q in people if q != p}
    result = {}
    for v in views:
        exact(v, ('name', 'artifacts'))
        need(type(v['name']) is str and v['name'] in expected and v['name'] not in result, 'exact unique outer/inner view')
        keys = ('TRAIN.json', 'QUERY.json', 'SUPPORT.json', 'VALIDATION.json') if '/inner/' in v['name'] else ('TRAIN.json', 'QUERY.json', 'SUPPORT.json')
        exact(v['artifacts'], keys)
        for desc in v['artifacts'].values():
            descriptor(desc)
            need(desc['bytes'] <= META_CAP, 'bounded original view body')
        result[v['name']] = v['artifacts']
    need(set(result) == expected, 'complete outer/inner view namespace')
    return result


class IndexedViews(Mapping):
    """Selected descriptor resolution never opens label-bearing view bodies."""
    def __init__(self, root, index, io, materialized=None):
        self.root, self.index, self.io = root, index, io
        self.materialized = materialized

    def __iter__(self):
        return iter(self.index)

    def __len__(self):
        return len(self.index)

    def __getitem__(self, name):
        need(name in self.index, 'selected original view only')
        if self.materialized is not None:
            need(name in self.materialized and same(self.materialized[name], self.index[name]), 'upstream exact view materialization completion required')
        result = {k: located(self.root / name, k, desc) for k, desc in self.index[name].items()}
        for key, desc in result.items():
            self.io.stat_only(desc, 'opaque_view_extent:' + key)
        return result


def streaming_lineage(selection, receipt, index, rows, source_roster, io):
    config_desc = selection['configuration']
    descriptor(config_desc, True)
    workspace, anchor = absolute(selection['workspace_root']), absolute(selection['anchor_root'])
    need(workspace != anchor and not workspace.is_relative_to(anchor) and not anchor.is_relative_to(workspace), 'disjoint independent anchor')
    need(config_desc['path'] == str(workspace / 'CONFIG.json'), 'literal selected configuration')
    config_raw = io.capture(config_desc, 'streaming_configuration', 1048576)
    anchor_config = located(anchor, 'CONFIG.json', bare(config_desc))
    need(io.capture(anchor_config, 'independent_configuration', 1048576) == config_raw, 'independent configuration agreement')
    config = parse(config_raw)
    exact(config, ('schema', 'root', 'anchor', 'clock_domain', 'monotonic_start', 'monotonic_end', 'limits', 'backend_identity', 'invocation_ledger'))
    need(config['schema'] == 'neural010-streaming-config-v1' and config['root'] == str(workspace)
         and config['anchor'] == str(anchor), 'selected streaming storage identity')
    need(type(config['clock_domain']) is str and config['clock_domain'], 'recorded original clock domain')
    start, end = finite(config['monotonic_start']), finite(config['monotonic_end'])
    need(start < end, 'fixed original preparation deadline')
    limits = config['limits']
    exact(limits, (*COUNTERS, 'operation_seconds', 'whole_seconds', 'project_peak_bytes', 'minimum_free_bytes', 'max_events'))
    for v in limits.values(): integer(v, 1)
    need(limits['max_events'] <= 10000 and same(end, start + limits['whole_seconds']), 'fixed source budget/deadline')
    identity = config['backend_identity']
    exact(identity, ('route', 'lock', 'original_source_manifest', 'request', 'bindings', 'annotation_bytes'))
    need(identity['route'] == 'neural010-streaming-original-semantics-v1'
         and same(identity['lock'], LOCK) and same(identity['original_source_manifest'], ORIGINAL_MANIFEST), 'pinned original semantic source route')
    descriptor(identity['annotation_bytes'])
    # Validate namespace metadata, never dereference the annotation/key paths.
    request = identity['request']
    exact(request, ('original_source_root', 'lock_path', 'metadata_root', 'metadata_pins', 'key_path'))
    for key in ('original_source_root', 'lock_path', 'metadata_root', 'key_path'): absolute(request[key])
    cases = {name.split('/')[0] for name in source_roster}
    expected_metadata = {'RECORDS', 'RECORDS-WITH-SEIZURES', 'chb07_19.edf.seizures'}
    expected_metadata.update(c + '-summary.txt' for c in cases)
    expected_metadata.update(c + '-index.html' for c in cases)
    need(type(request['metadata_pins']) is dict and set(request['metadata_pins']) == expected_metadata,
         'complete original metadata pin namespace')
    for p in request['metadata_pins'].values(): descriptor(p)
    need(same(request['metadata_pins']['RECORDS'], RECORDS_PIN), 'original constructor public roster pin')
    bindings = identity['bindings']
    need(type(bindings) is list and len(bindings) == 686, 'complete source bindings')
    by_source, biological, reverse = {}, {}, {}
    metadata = {r['recording_id']: r for r in rows}
    for b in bindings:
        exact(b, ('source_path', 'recording_id', 'patient_id'))
        ident(b['recording_id']); ident(b['patient_id'])
        need(b['source_path'] in source_roster and b['source_path'] not in by_source
             and b['recording_id'] in metadata and metadata[b['recording_id']]['patient_id'] == b['patient_id'], 'complete metadata/source binding')
        person = source_roster[b['source_path']]
        need(biological.setdefault(person, b['patient_id']) == b['patient_id']
             and reverse.setdefault(b['patient_id'], person) == person, 'chb01/chb21 same biological person')
        by_source[b['source_path']] = b
    need(set(by_source) == set(source_roster) and len({b['recording_id'] for b in bindings}) == 686, 'all exact original records bound')
    expected_root = workspace / 'prepared'
    need(selection['public_root'] == str(expected_root / 'public')
         and selection['private_root'] == str(expected_root / 'private'), 'complete published payload root')
    checkpoint = selection['checkpoint']
    exact(checkpoint, ('sequence', 'sha256', 'total'))
    integer(checkpoint['sequence'], 1, limits['max_events']); digest(checkpoint['sha256'])
    exact(checkpoint['total'], COUNTERS)
    for v in checkpoint['total'].values(): integer(v)
    names = io.names(workspace / 'journal')
    need(names == io.names(anchor / 'journal') == [f'{i:08d}.json' for i in range(1, checkpoint['sequence'] + 1)], 'exact independently selected current journal inventory')
    total = {k: 0 for k in COUNTERS}
    previous, previous_clock = config_desc['sha256'], start
    attempts, completed, cleaned = {}, {}, set()
    final_intent = published = None
    view_intents, materialized = {}, {}
    for i, name in enumerate(names, 1):
        raw = io.journal_body(workspace / 'journal' / name, 'source_journal')
        need(io.capture(located(anchor / 'journal', name, pin(raw)), 'independent_journal', EVENT_CAP) == raw, 'anchored complete frame')
        e = parse(raw)
        exact(e, ('sequence', 'previous', 'kind', 'data', 'charge', 'total', 'clock'))
        need(type(e['sequence']) is int and e['sequence'] == i and e['previous'] == previous, 'exact journal chain')
        need((i == 1) == (e['kind'] == 'genesis'), 'one genesis first')
        clock = finite(e['clock']); need(previous_clock <= clock < end, 'fixed-domain source event time')
        previous_clock = clock
        exact(e['charge'], COUNTERS); exact(e['total'], COUNTERS)
        for k in COUNTERS:
            total[k] += integer(e['charge'][k]); need(total[k] <= limits[k], 'source cumulative reservation cap')
        need(same(e['total'], total), 'no refunded source reservation')
        k, d = e['kind'], e['data']; need(type(d) is dict, 'bounded metadata event data')
        if k == 'genesis':
            need(i == 1 and same(d.get('configuration'), bare(config_desc)), 'bound source genesis')
        elif k in ('open', 'verify'):
            need(i > 1, 'genesis first')
        elif k == 'begin':
            exact(d, ('record', 'external_source'))
            need(final_intent is None and d['record'] in by_source and d['record'] not in completed
                 and not any(a['status'] == 'active' for a in attempts.values()), 'legal single source attempt')
            absolute(d['external_source'])
            attempts[str(i)] = {'record': d['record'], 'status': 'active', 'staged': None, 'cleanup': None}
        elif k == 'staged':
            exact(d, ('attempt', 'source', 'stamp')); a = attempts[d['attempt']]
            need(a['status'] == 'active' and a['staged'] is None, 'one source authentication')
            descriptor(d['source']); need(type(d['stamp']) is list and len(d['stamp']) == 5, 'source inode identity')
            for v in d['stamp']: integer(v)
            r = metadata[by_source[a['record']]['recording_id']]
            need(same(d['source'], r['source_edf']), 'exact staged/public source descriptor')
            a['staged'], a['stamp'] = d['source'], d['stamp']
        elif k == 'commit':
            exact(d, ('attempt', 'receipt')); a = attempts[d['attempt']]
            need(a['status'] == 'active' and a['staged'] is not None and a['record'] not in completed, 'authenticated committed source')
            descriptor(d['receipt']); need(d['receipt']['bytes'] <= 262144, 'bounded unopened private record receipt')
            a['status'] = 'complete'; completed[a['record']] = d['attempt']
        elif k == 'abort':
            exact(d, ('attempt', 'quiescence_evidence')); a = attempts[d['attempt']]
            need(a['status'] == 'active', 'abort only unresolved source'); descriptor(d['quiescence_evidence'])
            a['status'] = 'aborted'
        elif k == 'cleanup_intent':
            exact(d, ('attempt', 'source', 'stamp')); a = attempts[d['attempt']]
            need(a['status'] == 'complete' and a['cleanup'] is None and same(d['source'], a['staged'])
                 and same(d['stamp'], a['stamp']), 'durable committed owned cleanup')
            a['cleanup'] = d
        elif k == 'cleaned':
            exact(d, ('attempt',)); a = attempts[d['attempt']]
            need(a['status'] == 'complete' and a['cleanup'] is not None and d['attempt'] not in cleaned, 'exact cleanup acknowledgment')
            cleaned.add(d['attempt'])
        elif k == 'final_intent':
            exact(d, ('payloads', 'records', 'people', 'views'))
            need(final_intent is None and set(completed) == set(source_roster)
                 and set(completed.values()) <= cleaned and not any(a['status'] == 'active' for a in attempts.values()), 'full 686 committed and retired cohort')
            need(same({x: d[x] for x in ('records', 'people', 'views')}, {'records': 686, 'people': 23, 'views': 529})
                 and same(d['payloads'], receipt['payloads']), 'full exact final payload intent')
            final_intent = d
        elif k == 'published':
            exact(d, ('receipt',))
            need(final_intent is not None and published is None and same(d['receipt'], bare(selection['receipt'])), 'actual selected source publication')
            published = d
        elif k in ('view_intent', 'view_complete'):
            exact(d, ('name', 'artifacts'))
            need(published is not None and d['name'] in index and same(d['artifacts'], index[d['name']]), 'exact postpublication original view')
            if k == 'view_intent': view_intents[d['name']] = d['artifacts']
            else:
                need(d['name'] in view_intents and same(view_intents[d['name']], d['artifacts']), 'view completion follows exact intent')
                materialized[d['name']] = d['artifacts']
        else:
            raise ValueError('unknown source journal transition')
        previous = pin(raw)['sha256']
    need(published is not None and same(total, checkpoint['total']) and previous == checkpoint['sha256'], 'selected independent current complete checkpoint')
    need(same(receipt['configuration'], bare(config_desc))
         and same(receipt['final_intent'], pin(encoded(final_intent))), 'receipt/configuration/final-intent identity')
    return materialized, {'configuration': bare(config_desc), 'checkpoint': checkpoint,
                           'completed_source_records': len(completed), 'assessment_opened': False}


def validate_original_receipt(receipt):
    """Shared exact producer metadata contract; no additional body reads."""
    exact(receipt, ('schema', 'status', 'records', 'people', 'source_folders', 'source_roster',
                    'vendor_sources', 'source_manifest', 'panel', 'assessment', 'metadata',
                    'source_provenance', 'annotation_reads', 'views', 'cost_snapshot',
                    'actual_models_or_scores', 'global_assessment_release_authorized'))
    need(receipt.get('schema') == 'neural010-original-preparation-v1'
         and receipt.get('status') == 'prepared_not_runtime_or_scientifically_qualified', 'truthful original receipt')
    need(same({k: receipt[k] for k in ('records', 'people', 'source_folders')}, {'records': 686, 'people': 23, 'source_folders': 24})
         and same(receipt['source_manifest'], ORIGINAL_MANIFEST) and same(receipt['source_roster'], LOCK)
         and receipt['global_assessment_release_authorized'] is False, 'full pinned original preparation')
    need(type(receipt['actual_models_or_scores']) is int and receipt['actual_models_or_scores'] == 0,
         'original source preparation performs no models or scores')
    descriptor(receipt['annotation_reads']); descriptor(receipt['vendor_sources'])
    need(same(receipt['vendor_sources'], VENDOR_PIN), 'exact original vendor binding source')
    cost = receipt['cost_snapshot']
    exact(cost, ('original_origin', 'deadline', 'logical_reserved_read_bytes', 'logical_reserved_write_bytes',
                 'limits', 'physical_IO_or_RSS_measured'))
    exact(cost['limits'], ('read_bytes', 'write_bytes', 'whole_seconds', 'project_peak_bytes'))
    origin, duration = finite(cost['original_origin']), finite(cost['limits']['whole_seconds'])
    need(origin > 0 and duration > 0 and same(finite(cost['deadline']), origin + duration)
         and cost['physical_IO_or_RSS_measured'] is False, 'original preparation clock and logical cost semantics')
    for key in ('read_bytes', 'write_bytes', 'project_peak_bytes'): integer(cost['limits'][key], 1)
    need(integer(cost['logical_reserved_read_bytes']) <= cost['limits']['read_bytes']
         and integer(cost['logical_reserved_write_bytes']) <= cost['limits']['write_bytes'], 'bounded original preparation reservations')
    return (receipt['panel'], receipt['metadata'], receipt['assessment'], receipt['source_provenance'], receipt['views'])


def admit(selection, io, *, require_all_views=False):
    """Downstream label-free admission. Inputs must be independently selected."""
    common = ('schema', 'route', 'receipt', 'public_root', 'private_root', 'records',
              'selected_source_manifest', 'selected_original_roster')
    need(type(selection) is dict and selection.get('route') in ('original', 'streaming'), 'explicit preparation route')
    keys = common if selection['route'] == 'original' else (*common, 'configuration', 'workspace_root', 'anchor_root', 'checkpoint')
    exact(selection, keys)
    need(selection['schema'] == 'neural010-preparation-compatibility-selection-v1'
         and same(selection['selected_source_manifest'], ORIGINAL_MANIFEST)
         and same(selection['selected_original_roster'], LOCK), 'independently selected immutable original sources')
    public, private = absolute(selection['public_root']), absolute(selection['private_root'])
    need(public != private and not public.is_relative_to(private) and not private.is_relative_to(public), 'disjoint public/private preparation')
    descriptor(selection['receipt'], True); descriptor(selection['records'], True)
    need(same(bare(selection['records']), RECORDS_PIN), 'independent public source roster')
    need(absolute(selection['records']['path']).name in ('RECORDS', 'CHBMIT_RECORDS.txt'), 'literal public roster operand')
    route = selection['route']
    expected_receipt = 'PREPARATION.json' if route == 'original' else 'STREAMING_PREPARATION.json'
    need(selection['receipt']['path'] == str(private / expected_receipt), 'route-specific receipt path before capture')
    if route == 'streaming':
        workspace, anchor = absolute(selection['workspace_root']), absolute(selection['anchor_root'])
        need(public == workspace / 'prepared/public' and private == workspace / 'prepared/private', 'literal published namespace before capture')
        need(workspace != anchor and not workspace.is_relative_to(anchor) and not anchor.is_relative_to(workspace), 'independent stream anchor before capture')
    records_raw = io.capture(selection['records'], 'public_roster', 13056)
    source_roster = roster(records_raw)
    receipt = parse(io.capture(selection['receipt'], 'preparation_receipt', META_CAP))
    lineage, materialized = None, None
    if route == 'original':
        need(selection['receipt']['path'] == str(private / 'PREPARATION.json'), 'literal original receipt path')
        pp, mp, ap, sp, views = validate_original_receipt(receipt)
    else:
        need(selection['receipt']['path'] == str(private / 'STREAMING_PREPARATION.json'), 'literal truthful streaming receipt path')
        exact(receipt, ('schema', 'status', 'configuration', 'records', 'people', 'views', 'view_materialization',
                        'payloads', 'final_intent', 'models_or_scores', 'legacy_prepare_executed', 'assessment_release_authorized'))
        need(receipt['schema'] == 'neural010-streaming-preparation-v1'
             and receipt['status'] == 'complete_source_preparation_not_execution_or_scientific_qualification'
             and same({k: receipt[k] for k in ('records', 'people', 'views', 'models_or_scores')},
                      {'records': 686, 'people': 23, 'views': 529, 'models_or_scores': 0})
             and receipt['legacy_prepare_executed'] is False and receipt['assessment_release_authorized'] is False
             and receipt['view_materialization'] == 'lazy_exact_original_bytes', 'truthful complete streaming route')
        exact(receipt['payloads'], PAYLOADS)
        for p in receipt['payloads'].values(): descriptor(p)
        pp, mp = receipt['payloads']['public/panel.json'], receipt['payloads']['public/metadata.json']
        ap, sp = receipt['payloads']['private/assessment.json'], receipt['payloads']['private/SOURCE_PROVENANCE.json']
        view_desc = located(private, 'VIEWS.json', receipt['payloads']['private/VIEWS.json'])
        view_document = parse(io.capture(view_desc, 'target-free_view_index', META_CAP))
        exact(view_document, ('schema', 'views'))
        need(view_document['schema'] == 'neural010-lazy-original-views-v1', 'exact lazy view index carrier')
        views = view_document['views']
    for d in (pp, mp, ap, sp): descriptor(d)
    panel_pin, metadata_pin = located(public, 'panel.json', pp), located(public, 'metadata.json', mp)
    panel_raw = io.capture(panel_pin, 'target-free_panel', META_CAP)
    metadata_raw = io.capture(metadata_pin, 'target-free_metadata', META_CAP)
    panel, rows, people = public_payloads(panel_raw, metadata_raw)
    index = view_index(views, people)
    if route == 'streaming':
        materialized, lineage = streaming_lineage(selection, receipt, index, rows, source_roster, io)
    resolver = IndexedViews(private / 'views', index, io, materialized)
    if require_all_views:
        for name in resolver:
            resolver[name]
    return {'receipt': receipt, 'receipt_pin': selection['receipt'], 'public_root': public,
            'private_root': private, 'rows': rows, 'people': people, 'panel': panel, 'panel_raw': panel_raw,
            'panel_pin': panel_pin, 'metadata_pin': metadata_pin, 'views': resolver,
            'assessment_pin': ap, 'provenance_pin': sp, 'route': route,
            'selection': selection, 'metadata_raw': metadata_raw, 'records_raw': records_raw,
            'compatibility_lineage': lineage, 'all_views_materialized_checked': bool(require_all_views),
            'runtime_or_scientific_qualification': False}


def export_detection(prepared, detection_root, io):
    """Separate upstream operator projection; provenance stays private."""
    root = absolute(str(detection_root))
    source = io.capture(located(root, 'interface.py', DETECTION_PIN), 'detection_source', 20531)
    module = types.ModuleType('neural010_pinned_detection_bridge')
    module.__file__ = str(root / 'interface.py')
    exec(compile(source, module.__file__, 'exec'), module.__dict__)
    # The preserved detector loader independently captures its pinned sibling
    # scorer. Reserve that exact second read before invoking the original code.
    scorer_root = root.parent / 'scientific-scorer-v2'
    io.capture(located(scorer_root, 'scorer.py', SCORER_PIN), 'scientific_source', 13273)
    io.charge(13274)
    provenance = io.capture(located(prepared['private_root'], 'SOURCE_PROVENANCE.json', prepared['provenance_pin']),
                            'operator_private_provenance', META_CAP)
    expected = {'panel': bare(prepared['panel_pin']), 'metadata': bare(prepared['metadata_pin']),
                'provenance': prepared['provenance_pin']}
    result = module.project_preparation(records_bytes=prepared['records_raw'], panel_bytes=prepared['panel_raw'],
        metadata_bytes=prepared['metadata_raw'], provenance_bytes=provenance, expected=expected)
    return {'schema': 'neural010-compatible-detection-projection-v1', 'source_route': prepared['route'],
            'preparation_receipt': prepared['receipt_pin'], 'projection': result,
            'participant_document': 'projection.support', 'assessment_opened': False,
            'runtime_or_provider_qualified': False}


def reference_modules(root, io):
    root = absolute(str(root))
    bodies = {n: io.capture(located(root, n, d), 'reference_source', 30000) for n, d in REFERENCE_SOURCES.items()}
    modules, normal = {}, builtins.__import__
    def importer(name, globals=None, locals=None, fromlist=(), level=0):
        return modules[name] if name in modules else normal(name, globals, locals, fromlist, level)
    for name in ('common', 'schedule', 'arrays', 'reference_study'):
        module = types.ModuleType('neural010_compatible_' + name)
        module.__file__ = str(root / (name + '.py'))
        namespace = dict(vars(builtins)); namespace['__import__'] = importer
        module.__dict__['__builtins__'] = namespace
        exec(compile(bodies[name + '.py'], module.__file__, 'exec'), module.__dict__)
        modules[name] = module
    return modules


def compose_reference_request(prepared, job_id, reference_root, source_identity, worker_limits, io,
                              *, prior_operations=None, feature_bindings=None):
    """Invoke the unchanged original request method; never launch a worker.

    Operators must independently authenticate any prerequisite operations/features.
    This helper does not make unqualified prior outputs trustworthy.
    """
    modules = reference_modules(reference_root, io)
    jobs = (j for j in modules['schedule'].reference_jobs(prepared['rows']) if j['id'] == job_id)
    job = next(jobs, None)
    need(job is not None and next(jobs, None) is None, 'one exact original reference job')
    descriptor(source_identity)
    need(type(worker_limits) is dict, 'selected worker resource limits')
    cls = modules['reference_study'].ReferenceStudy
    study = object.__new__(cls)
    study.p = prepared; study.identity = source_identity; study.limits = worker_limits
    study.ops = {} if prior_operations is None else prior_operations
    study.features = {} if feature_bindings is None else feature_bindings
    request, inputs, opaque = study.request(job)
    return {'job': job, 'request': request, 'inputs': inputs, 'opaque_inputs': opaque,
            'preparation_receipt': prepared['receipt_pin'], 'source_route': prepared['route'],
            'native_execution_performed': False, 'runtime_qualified': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--selection', required=True)
    parser.add_argument('--selection-bytes', type=int, required=True)
    parser.add_argument('--selection-sha256', required=True)
    parser.add_argument('--read-root', action='append', required=True)
    parser.add_argument('--read-bytes', type=int, required=True)
    parser.add_argument('--seconds', type=int, default=30)
    parser.add_argument('--require-all-views', action='store_true')
    parser.add_argument('--view', action='append', default=[])
    args = parser.parse_args()
    io = FileIO(args.read_root, args.read_bytes, args.seconds)
    selection = parse(io.capture({'path': args.selection, 'bytes': args.selection_bytes,
                                  'sha256': args.selection_sha256}, 'selected_admission_request', 1048576))
    prepared = admit(selection, io, require_all_views=args.require_all_views)
    selected = {name: prepared['views'][name] for name in args.view}
    print(json.dumps({'route': prepared['route'], 'preparation_receipt': prepared['receipt_pin'],
        'records': len(prepared['rows']), 'people': len(prepared['people']), 'indexed_views': len(prepared['views']),
        'all_views_materialized_checked': prepared['all_views_materialized_checked'],
        'selected_views': selected, 'reserved_metadata_read_bytes': io.used,
        'assessment_opened': False, 'runtime_or_scientific_qualification': False}, sort_keys=True))


if __name__ == '__main__':
    main()
