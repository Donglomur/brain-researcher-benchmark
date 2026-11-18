"""Fixed DoSEI metadata inputs for the existing paired assembler.

No import opens data. The caller authenticates this adapter and supplies the
bounded source bytes of the existing reader. This module compiles only that
exact source, never its native Context or GuardContext. load() is an explicitly
admitted future operation; it never opens EEG arrays or invokes participants.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import types

IO_SHA256 = 'bc2891b56bf4640586949137f95d80050d255e70c1314ac08aa2eca28503b228'
IO_PATH = Path('/Users/nicholas/Documents/Codex/benchmark-engineering-evidence/comprehensive-revision-20261116-v2/completion2-v1/dosei/review/verify_saved_eeg_projections.py')
RAW = Path('/Users/nicholas/Documents/Codex/neuroscience-benchmark-data/dosei-native-v2-20261117')
SIGNALS = RAW/'full-eeg-native-v1'
INDICES = RAW/'compact-case-indices-v1'
OBSERVATIONS = RAW/'paired-observations-v1'
TASK = Path('/Users/nicholas/Documents/Codex/neuro-completion2-20261117/dosei/benchmarks/neural/clinical-dosei-responsiveness/implementations')
METADATA_CAP = 33554432
MEMBER_CAP = 131072
ROLES = {
    'cohort': (OBSERVATIONS/'COHORT.json', 'cfb8f868825ac910114f3ccbfa2cd3b0a865ea05d76a2f23d99afba4d3305207', 524288),
    'success': (OBSERVATIONS/'SUCCESS.json', 'b7e23a40b61fcb1622459c621116546c5717aed958910118fa58f1f9f4cb8650', 131072),
    'observations': (OBSERVATIONS/'OBSERVATIONS.provisional.jsonl', '11d3a466e88c0ce6ed08ea8e487c7a8b23327019fe3215881b8f82bcd78021b4', 7521280),
    'index_manifest': (INDICES/'MANIFEST.json', '67a4b89d123e3421f0ba63a17f22d5b9a6abde81419ef77e8e27104f6d59b838', 524288),
    'index_cases': (INDICES/'CASES.provisional.jsonl', 'af97ed83714d6ce362b3f3303acd4a1c60ebc5dba113e651da9e26c9d331cd78', 7296877),
    'key': (INDICES/'case-key.bin', '6a73374a648c7e0ee054207a6b17e62b8d887679591f4ba211518d637a75c775', 32),
    'numeric_cohort': (SIGNALS/'COHORT_SUCCESS.json', '1faf6f9c9d1b5c202c8d80a86fb779c50040f4ca94ab2e6b660984335464a2ed', 131072),
    'numeric_proof': (IO_PATH.parent/'dosei-full-eeg-saved-verification-20261117-v1.json', 'f83503c5a6031c9043579b84bd48ae6925ceb9ace491c2c9abf1198fe00bd202', 262144),
    'accepted_observation_evidence': (TASK/'source-paired-observation-evidence-v1/source-verification.json', '89509823b7cf570d7813868e737db16c7474972314d673fbf0284cad97bf396c', 65536),
}


class InputRefusal(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise InputRefusal(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def decode(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate metadata key')
            result[key] = value
        return result
    def reject(_):
        raise InputRefusal('nonfinite metadata constant')
    return json.loads(raw.decode('ascii'), object_pairs_hook=pairs, parse_constant=reject)


def compact(value):
    require(type(value) is dict and type(value.get('path')) is str and
            type(value.get('bytes')) is int and value['bytes'] > 0 and
            type(value.get('sha256')) is str and re.fullmatch('[0-9a-f]{64}', value['sha256']),
            'exact bounded metadata binding required')
    return {key: value[key] for key in ('path', 'bytes', 'sha256')}


def member_map(rows):
    require(type(rows) is list and len(rows) == 171, 'complete171 member roles required')
    result = {}
    for row in rows:
        rid = row['recording_id']
        require(type(rid) is str and re.fullmatch('[1-9][0-9]*', rid) and rid not in result,
                'unique canonical recording role required')
        result[rid] = row
    return result


def authenticated_reader(source):
    require(type(source) is bytes and 0 < len(source) <= 65536 and digest(source) == IO_SHA256,
            'exact existing reader source required')
    module = types.ModuleType('dosei_fixed_input_reader')
    module.__file__ = str(IO_PATH)
    exec(compile(source, str(IO_PATH), 'exec'), module.__dict__)
    return module


class FixedInputLoader:
    """Host-only single-use loader; output is never a participant message.

    One unchanged Meter covers all nine role bodies and 171 member receipts.
    Source bootstrap, namespace metadata operations and qualification-proof
    loading belong to the existing caller's separate operational accounting.
    Any read, hash, identity, parsing or close failure is terminal. No retry.
    """
    def __init__(self, reader_source_bytes):
        self.io = authenticated_reader(reader_source_bytes)
        require(hasattr(os, 'O_NOFOLLOW') and hasattr(os, 'O_NONBLOCK'), 'supported POSIX no-follow flags required')
        self.meter = self.io.Meter(METADATA_CAP)
        self.roles = dict(ROLES)
        self.signal_root = SIGNALS
        self.private_roots = (SIGNALS, INDICES, OBSERVATIONS)
        self.scope = 'accepted_release_v2'
        self.started = self.closed = self.failed = self.completed = False
        self.opened = set()
        self.completed_files = 0
        self.bootstrap_source_bytes = len(reader_source_bytes)
        self._seen_bindings = {}
        self.reader_close_failures = 0
        self.reader_construction_uncertain = False

    def _roots(self):
        for root in self.private_roots:
            s = root.lstat()
            require(root.is_absolute() and root.parent.resolve() == root.parent and
                    stat.S_ISDIR(s.st_mode) and stat.S_IMODE(s.st_mode) == 0o700 and
                    s.st_uid == os.getuid(), 'fixed private source directory required')

    def _read(self, role, declared=None, rid=None):
        require(self.started and not self.closed and not self.failed, 'metadata session closed or poisoned')
        try:
            if role == 'member':
                require(type(rid) is str and re.fullmatch('[1-9][0-9]*', rid), 'exact recording role')
                path, cap = self.signal_root/f'recording-{rid}.success.json', MEMBER_CAP
                expected = dict(compact(declared))
                require(expected['path'] == str(path), 'member path outside exact recording role')
                if 'closed_file_signature' in declared:
                    expected['closed_file_signature'] = declared['closed_file_signature']
            else:
                require(role in self.roles and rid is None, 'fixed metadata role required')
                path, pin, cap = self.roles[role]
                if declared is None:
                    s = path.lstat()
                    expected = {'path': str(path), 'bytes': s.st_size, 'sha256': pin}
                else:
                    expected = dict(compact(declared))
                    require(expected['path'] == str(path) and expected['sha256'] == pin, 'fixed role binding differs')
                    if 'closed_file_signature' in declared:
                        expected['closed_file_signature'] = declared['closed_file_signature']
            require(str(path) not in self.opened and type(expected['bytes']) is int and
                    0 < expected['bytes'] <= cap, 'single bounded role read required')
            self.opened.add(str(path))
            s = path.lstat()
            require(stat.S_ISREG(s.st_mode) and s.st_nlink == 1 and s.st_uid == os.getuid(),
                    'owned regular single-link metadata file required')
            if path.parent in self.private_roots:
                require(not s.st_mode & 0o077, 'private metadata permissions required')
            # reserve one byte beyond the complete body for Reader.finish's EOF
            # probe; successful empty reads release their provisional charge.
            require(self.meter.charged + expected['bytes'] + 1 <= self.meter.cap,
                    'metadata capacity must retain EOF headroom')
            chunks = []
            try:
                stream = self.io.Reader(path, self.meter, cap, expected)
            except BaseException:
                self.reader_construction_uncertain = True
                raise
            problem = None
            try:
                opened = os.fstat(stream.fd)
                require(self.io.signature(s) == stream.before == self.io.signature(opened),
                        'pre-open and opened metadata identity differs')
                require(stat.S_ISREG(opened.st_mode) and opened.st_nlink == 1 and opened.st_uid == os.getuid(),
                        'owned regular single-link opened metadata required')
                if path.parent in self.private_roots:
                    require(not opened.st_mode & 0o077, 'private opened metadata permissions required')
                while stream.count < expected['bytes']:
                    raw = stream.read(min(1048576, expected['bytes']-stream.count))
                    require(raw, 'short complete metadata body')
                    chunks.append(raw)
                stream.finish()
                observed = dict(stream.before)
            except BaseException as error:
                problem = error
            try:
                stream.close()
            except BaseException as cleanup:
                self.reader_close_failures += 1
                if problem is None or isinstance(problem, Exception) and not isinstance(cleanup, Exception):
                    problem = cleanup
            if problem is not None:
                raise problem
            raw = b''.join(chunks)
            require(len(raw) == expected['bytes'] and digest(raw) == expected['sha256'], 'complete role body differs')
            self._seen_bindings[role if rid is None else 'member:'+rid] = {**compact(expected),
                'observed_signature': observed}
            self.completed_files += 1
            return raw
        except BaseException:
            self.failed = True
            raise

    def load(self):
        require(not self.started, 'single metadata load; no retry')
        self.started = True
        try:
            self._roots()
            blobs = {'cohort': self._read('cohort'), 'success': self._read('success')}
            cohort, success = decode(blobs['cohort']), decode(blobs['success'])
            require(cohort['schema'] == 'dosei_complete_paired_observations_v1' and cohort['status'] == 'complete'
                    and type(cohort['cases']) is int and cohort['cases'] == 7345 and
                    type(cohort['recordings']) is int and cohort['recordings'] == 171,
                    'accepted complete observation cohort required')
            require(success['schema'] == 'dosei_complete_paired_success_v1' and success['status'] == 'succeeded',
                    'accepted complete observation success required')
            require(compact(success['cohort']) == compact(self._seen_bindings['cohort']), 'success/cohort body differs')
            if 'closed_file_signature' in success['cohort']:
                require(success['cohort']['closed_file_signature'] == self._seen_bindings['cohort']['observed_signature'],
                        'accepted cohort closed identity differs')
            require(compact(success['observations']) == compact(cohort['observations']), 'observation role binding differs')
            for role, field in (('observations', 'observations'), ('index_manifest', 'source_index_manifest'),
                                ('index_cases', 'source_case_stream'), ('numeric_cohort', 'numeric_cohort'),
                                ('numeric_proof', 'numeric_verification')):
                blobs[role] = self._read(role, cohort[field])
            index = decode(blobs['index_manifest'])
            blobs['key'] = self._read('key', index['key'])
            require(len(blobs['key']) == 32, 'complete private key required')
            blobs['accepted_observation_evidence'] = self._read('accepted_observation_evidence')
            numeric = decode(blobs['numeric_cohort'])
            cm = member_map(cohort['native_member_bindings'])
            nm = member_map(numeric['complete_member_receipts'])
            im = member_map(index['recordings'])
            require(set(cm) == set(nm) == set(im), 'all171 recording roles must join')
            total = 0
            for rid in cm:
                expected = compact(cm[rid]['receipt'])
                require(expected == compact(nm[rid]['receipt']) == compact(im[rid]['native_receipt']),
                        'cohort/native/index member binding differs')
                require(expected['path'] == str(self.signal_root/f'recording-{rid}.success.json') and
                        expected['bytes'] <= MEMBER_CAP, 'member-only bounded role required')
                total += expected['bytes']
            require(self.meter.charged + total + 1 <= self.meter.cap, 'complete member population exceeds metadata budget')
            members = {}
            for rid in sorted(cm, key=int):
                raw = self._read('member', nm[rid]['receipt'], rid)
                value = decode(raw)
                require(value['schema'] == 'dosei_full_eeg_member_success_v1' and value['status'] == 'succeeded'
                        and value['recording_id'] == rid, 'recording body role differs')
                members[rid] = raw
            require(set(blobs) == set(ROLES) and len(members) == 171 and self.completed_files == 180,
                    'complete fixed assembler data inputs required')
            self.completed = True
            return {'blobs': blobs, 'member_blobs': members}
        except BaseException:
            self.failed = True
            raise
        finally:
            self.closed = True

    def report(self):
        return {'schema': 'dosei_fixed_input_load_report_v1', 'scope': self.scope,
            'visibility': 'trusted_host_only', 'completed': self.completed, 'failed': self.failed,
            'closed': self.closed, 'opened_files': len(self.opened), 'completed_files': self.completed_files,
            'reader_close_failures': self.reader_close_failures,
            'reader_construction_uncertain': self.reader_construction_uncertain,
            'reader_cleanup_confirmed': self.completed,
            'metadata_reads': self.meter.report(), 'supplied_reader_source_bytes': self.bootstrap_source_bytes,
            'bootstrap_and_filesystem_metadata_IO_included_in_meter': False,
            'array_payloads_opened': False, 'participant_or_provider_invoked': False}


def generated_loader(reader_source_bytes, *, roles, signal_root, private_roots):
    """Explicit generated fixture route; authentic admission still has fixed pins.

    The caller may replace only fictional file locations/bindings. This does not
    bypass the existing assembler's fixed authentic release hashes.
    """
    require(type(roles) is dict and set(roles) == set(ROLES), 'complete generated role table')
    require(all(value[1] != ROLES[key][1] for key, value in roles.items()), 'fictional roots must differ')
    value = FixedInputLoader(reader_source_bytes)
    value.roles = dict(roles)
    value.signal_root = Path(signal_root)
    value.private_roots = tuple(Path(p) for p in private_roots)
    value.scope = 'generated_only'
    return value
