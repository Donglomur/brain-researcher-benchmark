"""ABR manual/programme operator session; not a sandbox or provider adapter.

Source preparation only. Invocation is a separately selected operation. The
accepted Pair owns first-final serialization, sealing and arithmetic. This file
adds a write-once journal and reconstructs its RAM state without replaying old
waveform exposures. Candidate execution/transport remains operator-attested.
"""
from __future__ import annotations

import argparse
import contextlib
import fcntl
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import sys
import time
import types

RELEASE_PIN = (31207, '827faa77da9c81a34c1d5b60875ad5446881db564f3671e0a5db2466abb5852e')
REPRESENTATION_PIN = (24833, '38a5185491c0e0edfa0707bb9abb6f9949a19c97554121fc9c0c08bbc37541c9')
NATIVE_COMPLETE_PIN = (22643, '507b7e77a2a4d09f5056e6191efe34db7092ca4eab70a4880e425ae7eade1972')
PROJECTION_PIN = (39816, '2fe03bf9e72e92116c08a64b91b4dc882fbd05913dd3f9eccc35b80557f72ec0')
PROJECTION_NAME = 'private/annotation-projection.jsonl.gz'
ARMS = ('direct', 'programme')
CASES, FINALS = 936, 1872
META_CAP, FINAL_CAP, SCORE_CAP = 65536, 12288, 262144
CAPTURE_LIMIT = 4097


def need(ok, message):
    if not ok:
        raise ValueError(message)


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def digest(body):
    return hashlib.sha256(body).hexdigest()


def pin(body):
    return [len(body), digest(body)]


def decode(body):
    def pairs(items):
        result = {}
        for k, v in items:
            need(k not in result, 'duplicate metadata key')
            result[k] = v
        return result
    def bad(_):
        raise ValueError('nonfinite metadata')
    return json.loads(body, object_pairs_hook=pairs, parse_constant=bad)


def parse_pin(value):
    size, sha = value.split(':', 1)
    need(size.isdecimal() and re.fullmatch('[0-9a-f]{64}', sha), 'pin must be BYTES:SHA256')
    return [int(size), sha]


def ordinary(path):
    path = Path(path).absolute()
    for part in (path, *path.parents):
        need(not part.is_symlink(), 'symlink in operator path')
    return path


def read_bytes(path, cap, expected=None):
    path = ordinary(path)
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | getattr(os, 'O_NOFOLLOW', 0))
    with os.fdopen(fd, 'rb') as f:
        before = os.fstat(f.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size <= cap, 'regular bounded single-link file required')
        body = f.read(cap + 1)
        after = os.fstat(f.fileno())
    attrs = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
    need(len(body) <= cap and all(getattr(before, k) == getattr(after, k) for k in attrs), 'input changed or exceeded cap')
    if expected is not None:
        need(pin(body) == list(expected), 'pinned input differs')
    return body


def read_record(path, cap=META_CAP, expected=None):
    body = read_bytes(path, cap, expected)
    value = decode(body)
    need(canonical(value) == body, 'noncanonical/corrupt journal record')
    return value, pin(body)


def sync_dir(path):
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def put(path, value, cap=META_CAP):
    body = canonical(value)
    need(len(body) <= cap, 'journal record cap')
    fd = os.open(ordinary(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    with os.fdopen(fd, 'wb') as f:
        f.write(body)
        f.flush()
        os.fchmod(f.fileno(), 0o400)
        os.fsync(f.fileno())
    sync_dir(Path(path).parent)
    return pin(body)


def mkdir(path):
    path = ordinary(path)
    path.mkdir(mode=0o700)
    sync_dir(path.parent)


def load_module(path, expected, name, cap):
    raw = read_bytes(path, cap, expected)
    module = types.ModuleType(name)
    module.__file__ = str(ordinary(path))
    exec(compile(raw, module.__file__, 'exec'), module.__dict__)
    return module


@contextlib.contextmanager
def locked(root):
    root = ordinary(root)
    fd = os.open(root / 'LOCK', os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0))
    try:
        st = os.fstat(fd)
        need(stat.S_ISREG(st.st_mode) and st.st_nlink == 1 and st.st_size == 0, 'lock file changed')
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield root
    finally:
        os.close(fd)


def sources(config):
    rep = load_module(config['representation'], REPRESENTATION_PIN, 'abr_operator_representation', 65536)
    release, raster, docs = rep.load_sources(config['release'], config['raster'], Path(config['store']) / 'public/COMMON_DOCUMENTATION.txt')
    need(tuple(rep.IMPLEMENTATION_PIN) == RELEASE_PIN, 'representation release pin differs')
    store, manifest, index, records, common = rep.open_store(release, config['store'], config['store_complete_pin'])
    need(docs == common, 'common documents changed')
    roster = rep.load_roster(release, store, manifest, index)
    return rep, release, raster, store, manifest, index, records, common, roster


def init(args):
    root = ordinary(args.session)
    need(root.parent.is_dir() and not root.exists(), 'fresh session with existing parent required')
    store = ordinary(args.store)
    need(root != store and root not in store.parents and store not in root.parents, 'session/store must be disjoint')
    programme = read_bytes(args.programme, 1024**2)
    need(programme, 'empty programme')
    config = {'schema': 'abr-manual-session-v1', 'release': str(ordinary(args.release)),
              'representation': str(ordinary(args.representation)), 'raster': str(ordinary(args.raster)),
              'store': str(store), 'store_complete_pin': parse_pin(args.store_pin),
              'self_pin': pin(read_bytes(__file__, 1024**2)), 'operator_id': args.operator_id,
              'programme_command': args.programme_command,
              'programme_frozen_before_target_exposure': True,
              'custody_kind': 'operator_attestation; no OS/provider enforcement',
              'schedule': 'observed-order lockstep; both arms complete one case before advancing',
              'mode': 'abr-release-annotation-code-agreement-zero-support-v1',
              'native_complete_pin': list(NATIVE_COMPLETE_PIN), 'projection_pin': list(PROJECTION_PIN)}
    need(args.attest_pre_exposure and 0 < len(args.operator_id) <= 256 and 0 < len(args.programme_command) <= 4096, 'pre-exposure freeze attestation and bounded operator/command required')
    rep, release, raster, store, manifest, index, records, docs, roster = sources(config)
    mkdir(root)
    fd = os.open(root / 'LOCK', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(fd)
    sync_dir(root)
    with locked(root):
        mkdir(root / 'slots')
        for arm in ARMS:
            mkdir(root / 'slots' / arm)
        mkdir(root / 'retired')
        provider = lambda cid: rep.public_packet(release, store, records, cid)[1]
        pair = release.Pair(root / 'pair', roster, provider, programme, docs, source_identity=NATIVE_COMPLETE_PIN[1])
        for name in ('PAIR.json', 'programme', 'documents'):
            os.chmod(root / 'pair' / name, 0o400)
        sync_dir(root / 'pair')
        sync_dir(root)
        config.update({'pair_pin': pin(pair._descriptor), 'programme_pin': list(pair._programme_pin),
                       'documents_pin': list(pair._documents_pin), 'roster_sha256': roster.identity,
                       'case_count': CASES, 'required_first_finals': FINALS,
                       'candidate_delivery_admitted': False, 'authentic_scoring_admitted': False,
                       'scientifically_qualified': False, 'new_benchmark_count': 0})
        result = put(root / 'SESSION.json', config)
    return {'session_pin': str(result[0]) + ':' + result[1], 'programme_sha256': config['programme_pin'][1],
            'status': 'frozen_operator_session; no cases exposed or targets opened'}


def expect_keys(value, keys, message):
    need(type(value) is dict and set(value) == set(keys), message)


def attestation(path, arm, cid, exposed, config):
    value = decode(read_bytes(path, 8192))
    keys = {'operator_id', 'participant_id', 'transport_description', 'external_run_reference',
            'fresh_case_context', 'only_current_case_and_common_docs', 'no_targets_or_feedback',
            'arm_rules_observed', 'fixed_programme_used'}
    expect_keys(value, keys, 'operator attestation schema')
    for k in ('operator_id', 'participant_id', 'transport_description', 'external_run_reference'):
        need(type(value[k]) is str and 0 < len(value[k]) <= 1024, 'bounded attestation text required')
    need(value['operator_id'] == config['operator_id'], 'operator differs from frozen session')
    for k in ('fresh_case_context', 'only_current_case_and_common_docs', 'no_targets_or_feedback', 'arm_rules_observed'):
        need(value[k] is True, 'required operator custody attestation missing')
    need(value['fixed_programme_used'] is (arm == 'programme'), 'programme-arm attestation differs')
    return {'kind': 'operator_attested_not_independently_observed', 'arm': arm, 'case_id': cid,
            'view_manifest_pin': exposed['view_manifest_pin'], 'programme_pin': config['programme_pin'],
            'documents_pin': config['documents_pin'], 'statements': value}


class Session:
    def __init__(self, root, expected):
        self.root = ordinary(root)
        self.config, self.config_pin = read_record(self.root / 'SESSION.json', expected=expected)
        c = self.config
        need(c['schema'] == 'abr-manual-session-v1' and c['case_count'] == CASES and c['required_first_finals'] == FINALS, 'session contract differs')
        read_bytes(__file__, 1024**2, c['self_pin'])
        need(c['native_complete_pin'] == list(NATIVE_COMPLETE_PIN) and c['projection_pin'] == list(PROJECTION_PIN), 'source/projection identity differs')
        (self.rep, self.release, self.raster, self.store, self.manifest, self.index,
         self.records, docs, self.roster) = sources(c)
        need(self.roster.identity == c['roster_sha256'], 'session roster changed')
        release = self.release
        pair = object.__new__(release.Pair)
        pair.root, pair.roster, pair.source_identity = self.root / 'pair', self.roster, NATIVE_COMPLETE_PIN[1]
        pair.provider = lambda cid: self.rep.public_packet(release, self.store, self.records, cid)[1]
        pair._descriptor = read_bytes(pair.root / 'PAIR.json', META_CAP, c['pair_pin'])
        descriptor = release.decode(pair._descriptor)
        need(descriptor['source_identity'] == pair.source_identity and descriptor['roster_sha256'] == self.roster.identity and descriptor['case_count'] == CASES, 'Pair descriptor source differs')
        for key, value in release.HOLDS.items():
            need(descriptor[key] == c[key] == value, 'qualification hold changed')
        pair._programme_pin, pair._documents_pin = tuple(c['programme_pin']), tuple(c['documents_pin'])
        need(pair._documents_pin == release.COMMON_DOCUMENTATION_PIN and descriptor['programme_sha256'] == pair._programme_pin[1] and descriptor['documents_sha256'] == pair._documents_pin[1], 'frozen input binding differs')
        read_bytes(pair.root / 'programme', 1024**2, pair._programme_pin)
        need(read_bytes(pair.root / 'documents', 4096, pair._documents_pin) == docs, 'common documents differ')
        pair._next, pair._active, pair._finals, pair._packets = {a: 0 for a in ARMS}, {}, {}, {}
        pair._sealed, pair._scored = None, False
        self.pair, self.exposures = pair, {}
        self._reconstruct()

    def slot(self, arm, position):
        return self.root / 'slots' / arm / str(position).zfill(4)

    def _reconstruct(self):
        pair, release = self.pair, self.release
        allowed_root = {'LOCK', 'SESSION.json', 'pair', 'slots', 'retired', 'view', 'SCORE_STARTED.json', 'SCORE.json'}
        need(set(os.listdir(self.root)) <= allowed_root, 'unexpected session artifact')
        need(set(os.listdir(self.root / 'slots')) == set(ARMS), 'arm directory inventory differs')
        known_finals = set()
        for arm in ARMS:
            folder = self.root / 'slots' / arm
            names = sorted(os.listdir(folder))
            need(names == [str(i).zfill(4) for i in range(len(names))] and len(names) <= CASES, 'noncontiguous slot prefix')
            for i, name in enumerate(names):
                slot = ordinary(folder / name)
                need(slot.is_dir(), 'slot is not ordinary directory')
                present = set(os.listdir(slot))
                need(present <= {'EXPOSURE_STARTED.json', 'EXPOSURE.json', 'CAPTURE_STARTED.json', 'CAPTURE.json'}, 'unknown slot artifact')
                need({'EXPOSURE_STARTED.json', 'EXPOSURE.json'} <= present, 'partial exposure: attempt aborted; no answer reset')
                started, _ = read_record(slot / 'EXPOSURE_STARTED.json')
                exposed, _ = read_record(slot / 'EXPOSURE.json')
                cid = self.roster.ids[i]
                need(started == {'arm': arm, 'case_id': cid, 'position': i, 'session_pin': self.config_pin}, 'exposure start differs')
                row = self.records[cid]
                need(exposed['arm'] == arm and exposed['case_id'] == cid and exposed['position'] == i and exposed['packet_pin'] == row['packet_pin'] and exposed['documents_pin'] == self.config['documents_pin'], 'exposure record differs')
                need(exposed['materialization_only'] is True and exposed['sample_count'] == row['sample_count'] and exposed['page_count'] == row['page_count'], 'view coverage differs')
                self._validate_view_inventory(exposed, row)
                need(cid not in pair._packets or pair._packets[cid] == row['packet_pin'][1], 'paired observation changed')
                pair._packets[cid] = row['packet_pin'][1]
                self.exposures[(arm, i)] = exposed
                other = 'programme' if arm == 'direct' else 'direct'
                if (other, i) in self.exposures:
                    for key in ('view_manifest_pin', 'files'):
                        need(exposed[key] == self.exposures[(other, i)][key], 'arms received different materialized view')
                final_name = arm + '-' + cid + '.json'
                if 'CAPTURE_STARTED.json' in present:
                    need('CAPTURE.json' in present and (pair.root / final_name).exists(), 'partial first-final capture: attempt aborted, slot consumed')
                    capture_start, capture_start_pin = read_record(slot / 'CAPTURE_STARTED.json')
                    capture, _ = read_record(slot / 'CAPTURE.json')
                    need(capture_start['arm'] == arm and capture_start['case_id'] == cid and capture_start['session_pin'] == self.config_pin, 'capture start differs')
                    need(capture['capture_start_pin'] == capture_start_pin and capture['arm'] == arm and capture['case_id'] == cid, 'capture receipt differs')
                    record_raw = read_bytes(pair.root / final_name, FINAL_CAP, capture['final_pin'])
                    record = release.decode(record_raw)
                    need(release.canonical(record) == record_raw and set(record) == {'case_id', 'raw_hex', 'raw_sha256', 'oversized', 'observation_sha256'}, 'corrupt first-final record')
                    need(record['case_id'] == cid and record['observation_sha256'] == row['packet_pin'][1], 'first-final observation differs')
                    retained = bytes.fromhex(record['raw_hex'])
                    need(type(capture['captured_bytes']) is int and 0 <= capture['captured_bytes'] <= CAPTURE_LIMIT and type(record['oversized']) is bool, 'capture extent/type differs')
                    need(record['oversized'] == (capture['captured_bytes'] == CAPTURE_LIMIT), 'oversize binding differs')
                    need(record['raw_sha256'] == capture['captured_buffer_sha256'], 'bounded buffer digest differs')
                    if record['oversized']:
                        need(len(retained) == 4096 and capture['digest_scope'] == 'first_4097_bytes_only; full_response_length_and_digest_unknown', 'overflow scope differs')
                    else:
                        need(len(retained) == capture['captured_bytes'] and digest(retained) == record['raw_sha256'] and capture['digest_scope'] == 'complete_stream_to_EOF_within_4096_bytes', 'retained first-final bytes differ')
                    need(digest(retained) == capture['retained_prefix_sha256'], 'retained response prefix changed')
                    pair._finals[(arm, cid)] = tuple(capture['final_pin'])
                    pair._next[arm] += 1
                    known_finals.add(final_name)
                else:
                    need('CAPTURE.json' not in present and i == len(names) - 1 and not (pair.root / final_name).exists(), 'unstarted or out-of-order final')
                    pair._active[arm] = (cid, row['packet_pin'][1])
        need(abs(pair._next['direct'] - pair._next['programme']) <= 1, 'lockstep order violated')
        for arm, (cid, _) in pair._active.items():
            need(pair._next[arm] == min(pair._next.values()), 'active case skips opposite arm')
        allowed_pair = {'programme', 'documents', 'PAIR.json', 'SEALED.json'} | known_finals
        need(set(os.listdir(pair.root)) <= allowed_pair, 'unclaimed first-final or pair artifact')
        self._check_retirements()
        if (pair.root / 'SEALED.json').exists():
            need(not pair._active and set(pair._next.values()) == {CASES} and len(pair._finals) == FINALS, 'seal without complete first finals')
            sealed, seal_pin = read_record(pair.root / 'SEALED.json')
            expected = {'pair_sha256': digest(pair._descriptor), 'observation_sha256': digest(canonical(pair._packets)),
                        'finals_sha256': digest(canonical({a + ':' + c: p[1] for (a, c), p in pair._finals.items()})), 'first_final_count': FINALS}
            need(sealed == expected, 'seal digest/coverage differs')
            pair._sealed = tuple(seal_pin)
            pair.verify_seal()
        if (self.root / 'SCORE_STARTED.json').exists():
            need(pair._sealed is not None, 'score marker before complete seal')
            start, _ = read_record(self.root / 'SCORE_STARTED.json')
            need(start['seal_pin'] == list(pair._sealed) and start['projection_pin'] == list(PROJECTION_PIN), 'score marker differs')
            pair._scored = True
            if (self.root / 'SCORE.json').exists():
                result, _ = read_record(self.root / 'SCORE.json', SCORE_CAP)
                need(result['session_pin'] == self.config_pin and result['seal_pin'] == list(pair._sealed) and result['projection_pin'] == list(PROJECTION_PIN), 'score envelope differs')
                accepted = result['accepted_pair_result']
                need(accepted['source_kind'] == 'unverified_operator_arithmetic' and accepted['case_count'] == CASES and accepted['animal_count'] == 104, 'arithmetic classification/denominator changed')
                for key, value in release.HOLDS.items():
                    need(accepted[key] == value, 'score qualification hold changed')
        elif (self.root / 'SCORE.json').exists():
            raise ValueError('unstarted score artifact')

    def _validate_view_inventory(self, exposed, row):
        files = exposed['files']
        names = {'numeric.json', 'COMMON_DOCUMENTATION.txt', 'VIEW.json', 'index.html'} | {'page-' + str(i+1).zfill(3) + '.png' for i in range(row['page_count'])}
        need(set(files) == names and files['numeric.json'] == row['packet_pin'] and files['COMMON_DOCUMENTATION.txt'] == self.config['documents_pin'] and files['VIEW.json'] == exposed['view_manifest_pin'], 'complete exported file inventory differs')
        for name, value in files.items():
            need(type(value) is list and len(value) == 2 and type(value[0]) is int and value[0] > 0 and re.fullmatch('[0-9a-f]{64}', value[1]), 'view file pin malformed')
            cap = self.rep.PACKET_LIMIT if name == 'numeric.json' else self.rep.PAGE_LIMIT if name.endswith('.png') else META_CAP
            need(value[0] <= cap, 'view file size exceeds source capacity')

    def _check_retirements(self):
        names = set(os.listdir(self.root / 'retired'))
        allowed = set()
        completed = min(self.pair._next.values())
        for i in range(completed):
            stem = str(i).zfill(4)
            start_path = self.root / 'retired' / (stem + '.START.json')
            done_path = self.root / 'retired' / (stem + '.DONE.json')
            if i < completed - 1:
                need(start_path.exists() and done_path.exists(), 'advanced before prior view retirement')
            if start_path.exists():
                expected = {'position': i, 'case_id': self.roster.ids[i], 'files': self.exposures[('direct', i)]['files']}
                start, start_pin = read_record(start_path)
                need(start == expected, 'retirement source differs')
                allowed.add(start_path.name)
                if done_path.exists():
                    done, _ = read_record(done_path)
                    need(done == {'position': i, 'retirement_start_pin': start_pin, 'retired': True}, 'retirement completion differs')
                    allowed.add(done_path.name)
        need(names == allowed, 'unclaimed or premature retirement artifact')

    def expose(self, arm, seconds):
        pair = self.pair
        need(not pair._scored and pair._sealed is None, 'session sealed/scoring started')
        i = pair._next[arm]
        need(i < CASES and i == min(pair._next.values()) and arm not in pair._active, 'arm already exposed/complete or waiting for other arm')
        if i:
            need((self.root / 'retired' / (str(i-1).zfill(4) + '.DONE.json')).exists(), 'retire previous complete case view first')
        cid, row = self.roster.ids[i], self.records[self.roster.ids[i]]
        slot = self.slot(arm, i)
        mkdir(slot)
        put(slot / 'EXPOSURE_STARTED.json', {'arm': arm, 'case_id': cid, 'position': i, 'session_pin': self.config_pin})
        raw = pair.expose(arm)
        need(pin(raw) == row['packet_pin'], 'accepted Pair packet differs from complete store')
        view_root = self.root / 'view'
        if not view_root.exists():
            mkdir(view_root)
            budget = self.rep.Budget(self.rep.VIEW_LIMIT, time.monotonic() + seconds)
            view = self.rep.case_view(self.release, self.raster, self.store, self.config['store_complete_pin'], cid, view_root / 'content', budget)
            content = view_root / 'content'
            files = {name: pin(read_bytes(content / name, self.rep.PACKET_LIMIT if name == 'numeric.json' else self.rep.PAGE_LIMIT if name.endswith('.png') else META_CAP)) for name in sorted(os.listdir(content))}
            need(view['case_id'] == cid and view['packet_pin'] == row['packet_pin'] and view['sample_count'] == row['sample_count'] and len(view['pages']) == row['page_count'], 'materialized view differs')
            for page in view['pages']:
                need(files[page['path']] == [page['pin']['bytes'], page['pin']['sha256']], 'materialized page differs')
            sync_dir(content)
            put(view_root / 'STATE.json', {'case_id': cid, 'position': i, 'files': files,
                                          'requested_bytes': budget.requested, 'confirmed_bytes': budget.confirmed})
        else:
            state, _ = read_record(view_root / 'STATE.json')
            need(state['case_id'] == cid and state['position'] == i, 'live view belongs to another case')
            files = state['files']
            expected_names = {'numeric.json', 'COMMON_DOCUMENTATION.txt', 'VIEW.json', 'index.html'} | {'page-' + str(j+1).zfill(3) + '.png' for j in range(row['page_count'])}
            need(set(files) == expected_names, 'live view inventory must be case-local before reads')
            self.verify_live_view(files)
        exposed = {'arm': arm, 'case_id': cid, 'position': i, 'packet_pin': row['packet_pin'],
                   'documents_pin': self.config['documents_pin'], 'sample_count': row['sample_count'],
                   'page_count': row['page_count'], 'view_manifest_pin': files['VIEW.json'], 'files': files,
                   'materialization_only': True, 'delivery_or_inspection_proven': False}
        self._validate_view_inventory(exposed, row)
        put(slot / 'EXPOSURE.json', exposed)
        return {'arm': arm, 'case_id': cid, 'view_directory': str(view_root / 'content'),
                'status': 'complete_case_materialized; actual_delivery_requires_operator_attestation'}

    def verify_live_view(self, files):
        folder = self.root / 'view' / 'content'
        need(set(os.listdir(folder)) == set(files), 'live view file inventory differs')
        for name, value in files.items():
            read_bytes(folder / name, value[0], value)

    def capture(self, arm, response, attest_path):
        pair = self.pair
        need(arm in pair._active and pair._sealed is None and not pair._scored, 'no unconsumed active first-final slot')
        i = pair._next[arm]
        cid, _ = pair._active[arm]
        exposed = self.exposures[(arm, i)]
        self.verify_live_view(exposed['files'])
        attested = attestation(attest_path, arm, cid, exposed, self.config)
        slot = self.slot(arm, i)
        start = {'arm': arm, 'case_id': cid, 'session_pin': self.config_pin, 'operator_custody': attested,
                 'read_limit_bytes': CAPTURE_LIMIT, 'attempt_consumed_before_transport_read': True}
        start_pin = put(slot / 'CAPTURE_STARTED.json', start)
        # Any error/interrupt after this marker poisons the attempt. Never retry.
        # Preexisting regular files only. O_NONBLOCK prevents a substituted FIFO
        # from blocking before fstat. An outer owner timeout remains mandatory:
        # regular-file/network-filesystem I/O is not a hard wall-clock boundary.
        need(response != '-', 'stdin is not a supported finite capture transport')
        path = ordinary(response)
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | getattr(os, 'O_NOFOLLOW', 0))
        with os.fdopen(fd, 'rb', buffering=0) as f:
            before = os.fstat(f.fileno())
            need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1, 'response transport must be a preexisting regular single-link file')
            raw = f.read(CAPTURE_LIMIT)
            after = os.fstat(f.fileno())
            need(all(getattr(before, k) == getattr(after, k) for k in ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns')), 'response file changed during bounded capture')
        need(type(raw) is bytes, 'transport did not yield bytes')
        need(len(raw) == min(before.st_size, CAPTURE_LIMIT), 'response transport returned an incomplete expected prefix')
        pair.submit(arm, cid, raw)
        final = pair.root / (arm + '-' + cid + '.json')
        os.chmod(final, 0o400)
        sync_dir(pair.root)
        receipt = {'arm': arm, 'case_id': cid, 'capture_start_pin': start_pin,
                   'final_pin': list(pair._finals[(arm, cid)]), 'captured_bytes': len(raw),
                   'captured_buffer_sha256': digest(raw), 'retained_prefix_sha256': digest(raw[:4096]),
                   'digest_scope': 'first_4097_bytes_only; full_response_length_and_digest_unknown' if len(raw) == CAPTURE_LIMIT else 'complete_stream_to_EOF_within_4096_bytes',
                   'first_final_consumed': True, 'prediction_validity_disclosed': False}
        put(slot / 'CAPTURE.json', receipt)
        return {'accepted_first_final': True, 'arm': arm, 'case_id': cid}

    def retire(self):
        pair = self.pair
        completed = min(pair._next.values())
        need(completed > 0 and not pair._active, 'both arms must finalize current case first')
        i = completed - 1
        stem = str(i).zfill(4)
        start_path = self.root / 'retired' / (stem + '.START.json')
        done_path = self.root / 'retired' / (stem + '.DONE.json')
        if done_path.exists():
            return {'position': i, 'view_retired': True, 'already_complete': True}
        exposed = self.exposures[('direct', i)]
        expected = {'position': i, 'case_id': self.roster.ids[i], 'files': exposed['files']}
        if start_path.exists():
            start, start_pin = read_record(start_path)
            need(start == expected, 'retirement changed')
        else:
            self.verify_live_view(exposed['files'])
            start_pin = put(start_path, expected)
        view = self.root / 'view'
        content = view / 'content'
        if content.exists():
            need(set(os.listdir(content)) <= set(exposed['files']), 'unknown view file; refuse deletion')
            for name, value in exposed['files'].items():
                path = content / name
                if path.exists():
                    read_bytes(path, value[0], value)
                    path.unlink()
                    sync_dir(content)
            content.rmdir()
            sync_dir(view)
        state = view / 'STATE.json'
        if state.exists():
            value, _ = read_record(state)
            need(value['case_id'] == self.roster.ids[i] and value['files'] == exposed['files'], 'view state differs')
            state.unlink()
        if view.exists():
            need(not list(view.iterdir()), 'unknown view artifact; refuse deletion')
            view.rmdir()
            sync_dir(self.root)
        put(done_path, {'position': i, 'retirement_start_pin': start_pin, 'retired': True})
        return {'position': i, 'view_retired': True, 'finals_and_receipts_preserved': True}

    def seal(self):
        need(not self.pair._scored, 'scoring already started')
        if self.pair._sealed is not None:
            return {'sealed': True, 'seal_pin': list(self.pair._sealed), 'first_final_count': FINALS}
        need((self.root / 'retired' / '0935.DONE.json').exists(), 'retire final case view before sealing')
        self.pair.seal()
        sync_dir(self.pair.root)
        os.chmod(self.pair.root / 'SEALED.json', 0o400)
        return {'sealed': True, 'seal_pin': list(self.pair._sealed), 'first_final_count': FINALS}

    def score(self, native_root, attest):
        pair, release = self.pair, self.release
        need(attest and pair._sealed is not None and not pair._scored, 'separate operator scoring attestation and unused complete seal required')
        pair.verify_seal()
        # The metadata may be checked now; annotation bytes remain unopened until
        # the complete-pair seal and durable one-shot score marker both exist.
        native_root = ordinary(native_root)
        complete = release.decode(read_bytes(native_root / 'COMPLETE.json', META_CAP, NATIVE_COMPLETE_PIN))
        need(complete['target_animals'] == 104 and complete['target_cases'] == CASES and complete['candidate_delivery_admitted'] is False, 'native completion population/hold differs')
        entry = complete['files'][PROJECTION_NAME]
        need([entry['bytes'], entry['sha256']] == list(PROJECTION_PIN), 'private projection pin differs')
        put(self.root / 'SCORE_STARTED.json', {'seal_pin': list(pair._sealed), 'projection_pin': list(PROJECTION_PIN),
                                             'operator_attested_separate_scoring_selection': True,
                                             'custody': 'operator-controlled private projection; not NativeTarget.score_sealed identity'})
        with release.pinned_open(native_root / PROJECTION_NAME, PROJECTION_PIN) as stream:
            with gzip.GzipFile(fileobj=stream) as gz:
                references = list(release.jsonl(gz, 2 * 1024**2))
        # Pair.score retains its truthful unverified_operator_arithmetic label and
        # every accepted scientific hold. No fake NativeTarget/provider binding.
        result = pair.score(references)
        envelope = {'schema': 'abr-manual-pinned-projection-result-v1', 'session_pin': self.config_pin,
                    'seal_pin': list(pair._sealed), 'native_complete_pin': list(NATIVE_COMPLETE_PIN),
                    'projection_pin': list(PROJECTION_PIN),
                    'custody_kind': 'operator-attested manual delivery; separately pinned private projection',
                    'native_target_score_sealed_used': False, 'accepted_pair_result': result}
        result_pin = put(self.root / 'SCORE.json', envelope, SCORE_CAP)
        return {'score_result_pin': result_pin, 'status': 'operator_arithmetic_only; all_accepted_holds_preserved'}

    def status(self):
        return {'first_final_counts': self.pair._next, 'required_per_arm': CASES,
                'active_arms': list(self.pair._active), 'sealed': self.pair._sealed is not None,
                'scoring_started': self.pair._scored,
                'scope': 'journal progress only; no prediction validity or target feedback'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='operation', required=True)
    init_parser = sub.add_parser('init')
    for field in ('session', 'store', 'store-pin', 'representation', 'release', 'raster', 'programme', 'operator-id', 'programme-command'):
        init_parser.add_argument('--' + field, required=True)
    init_parser.add_argument('--attest-pre-exposure', action='store_true')
    for name in ('expose', 'capture', 'retire-view', 'seal', 'score', 'status'):
        p = sub.add_parser(name)
        p.add_argument('--session', required=True)
        p.add_argument('--session-pin', required=True)
        if name in ('expose', 'capture'):
            p.add_argument('--arm', choices=ARMS, required=True)
        if name == 'expose':
            p.add_argument('--deadline-seconds', type=float, required=True)
        if name == 'capture':
            p.add_argument('--response', required=True, help='preexisting regular response file only; read at most4097 bytes; external owner timeout required')
            p.add_argument('--attestation', required=True)
        if name == 'score':
            p.add_argument('--native-root', required=True)
            p.add_argument('--attest-separately-selected-scoring', action='store_true')
    args = parser.parse_args(argv)
    if args.operation == 'init':
        result = init(args)
    else:
        if args.operation == 'expose':
            need(math.isfinite(args.deadline_seconds) and 0 < args.deadline_seconds <= 3600, 'finite selected view deadline up to one hour required')
        with locked(args.session) as root:
            session = Session(root, parse_pin(args.session_pin))
            if args.operation == 'expose':
                result = session.expose(args.arm, args.deadline_seconds)
            elif args.operation == 'capture':
                result = session.capture(args.arm, args.response, args.attestation)
            elif args.operation == 'retire-view':
                result = session.retire()
            elif args.operation == 'seal':
                result = session.seal()
            elif args.operation == 'score':
                result = session.score(args.native_root, args.attest_separately_selected_scoring)
            else:
                result = session.status()
    print(json.dumps(result, sort_keys=True, allow_nan=False))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(json.dumps({'status': 'operator_operation_failed_closed', 'reason': str(exc),
                          'instruction': 'Never delete journal/first-final artifacts to retry an answer.'}), file=sys.stderr)
        raise SystemExit(2)
