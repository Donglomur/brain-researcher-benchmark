"""NEURAL100 report-support companion; frozen scientific calculations unchanged."""
import argparse
import builtins
import hashlib
import json
import os
from pathlib import Path
import stat
import types

HERE = Path(__file__).resolve().parent
SOURCE_NAMES = ('artifact_io', 'report_contract', 'grade', 'analysis_core', 'data_adapter')
SUPPORT_NAMES = {'participants', 'defined_participants', 'defined_draws'}


class SourceError(ValueError):
    pass


def need(condition, message):
    if not condition:
        raise SourceError(message)


def canonical(path):
    path = Path(path).absolute()
    need('..' not in path.parts and all(not p.is_symlink() for p in (path, *path.parents)),
         'Unlinked canonical operator path required')
    return path


def capture(path, cap):
    path = canonical(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
             and 0 < before.st_size <= cap, 'Bounded ordinary single-link file required')
        chunks, count = [], 0
        while count <= cap:
            chunk = os.read(fd, min(1048576, cap + 1 - count))
            if not chunk:
                break
            chunks.append(chunk)
            count += len(chunk)
        after, named = os.fstat(fd), os.lstat(path)
        fields = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns', 'st_nlink')
        need(all(getattr(before, k) == getattr(after, k) == getattr(named, k) for k in fields)
             and count == before.st_size and stat.S_ISREG(named.st_mode), 'Changed source capture')
        return b''.join(chunks)
    finally:
        os.close(fd)


def strict(raw):
    def pairs(items):
        value = {}
        for key, item in items:
            need(key not in value, 'Duplicate JSON key')
            value[key] = item
        return value
    return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                      parse_constant=lambda _: need(False, 'Nonfinite JSON'))


class FrozenSources:
    """Capture pinned code once; resolve its local imports without sys.path edits."""
    def __init__(self, package):
        self.package = canonical(package)
        self.lock = strict(capture(HERE / 'SOURCE_LOCK.json', 20000))
        need(self.lock['schema'] == 'neural100_support_source_lock_v1'
             and self.lock['task_id'] == 'NEURAL-100', 'Frozen source identity')
        self.raw, self.modules = {}, {}
        for name, pin in self.lock['files'].items():
            need(not Path(name).is_absolute() and '..' not in Path(name).parts, 'Source member path')
            raw = capture(self.package / name, 200000)
            need(type(pin['bytes']) is int and len(raw) == pin['bytes']
                 and hashlib.sha256(raw).hexdigest() == pin['sha256'], 'Frozen source digest: ' + name)
            self.raw[name] = raw
        need(strict(self.raw['DELIVERY_MANIFEST.json'])['source_manifest']
             == self.lock['original_source_descriptor'], 'Original source descriptor binding')
        self.roster = strict(self.raw['public/ROSTER.json'])
        self.binding = strict(self.raw['private/PACKET_BINDING.json'])
        need(self.binding['task_id'] == 'NEURAL-100' and self.binding['roster'] == self.roster,
             'Fixed public/private roster join')

    def module(self, name):
        need(name in SOURCE_NAMES, 'Unknown frozen module')
        if name not in self.modules:
            local = types.ModuleType('neural100_support_frozen_' + name)
            local.__file__ = str(self.package / 'private' / (name + '.py'))
            namespace = dict(vars(builtins))
            original_import = builtins.__import__

            def importer(target, globals=None, locals=None, fromlist=(), level=0):
                if level == 0 and target in SOURCE_NAMES:
                    return self.module(target)
                return original_import(target, globals, locals, fromlist, level)

            namespace['__import__'] = importer
            local.__dict__['__builtins__'] = namespace
            self.modules[name] = local
            try:
                exec(compile(self.raw['private/' + name + '.py'], local.__file__, 'exec'), local.__dict__)
            except BaseException:
                del self.modules[name]
                raise
        return self.modules[name]


def validate_roster(roster, invalid):
    def check(ok, message):
        if not ok:
            raise invalid(message)
    check(type(roster) is list and len(roster) == 47, 'Complete47 recording roster')
    check(all(type(r) is dict and set(r) == {'recording_id', 'participant_id', 'area'}
              and all(type(r[k]) is str and r[k] for k in r)
              and r['area'] in ('A1', 'A2') for r in roster), 'Exact roster identities')
    check(len({r['recording_id'] for r in roster}) == 47
          and len({r['participant_id'] for r in roster}) == 41
          and {r['area'] for r in roster} == {'A1', 'A2'}, 'Full47/41/two-area cohort')


def expected_support(value, roster, contract, np):
    """Derive support from declared dispositions, not from neural observations."""
    validate_roster(roster, contract.Invalid)
    contract.admit(value, roster)
    participants = sorted({r['participant_id'] for r in roster})
    index = {p: i for i, p in enumerate(participants)}
    rng = np.random.Generator(np.random.PCG64(100043))
    draws = rng.integers(0, 41, size=(1000, 41))
    multiplicity = np.asarray([np.bincount(d, minlength=41) for d in draws], dtype=np.int64)
    result = {}
    for condition in contract.CONDITIONS:
        result[condition] = {}
        for area in contract.AREAS:
            grouped = {}
            for row in value['recordings']:
                if row['area'] == area:
                    grouped.setdefault(row['participant_id'], []).append(
                        row['conditions'][condition]['delta_ms'] is not None)
            ordered = sorted(grouped)
            defined = [all(grouped[p]) for p in ordered]
            weights = multiplicity[:, [index[p] for p in ordered]]
            denom = weights.sum(axis=1)
            missing = np.asarray([not state for state in defined], dtype=bool)
            invalid_draw = ((weights[:, missing].sum(axis=1) > 0) if missing.any()
                            else np.zeros(1000, dtype=bool))
            defined_draws = int(((denom > 0) & ~invalid_draw).sum())
            full = bool(ordered) and all(defined)
            result[condition][area] = {
                'participants': len(ordered), 'defined_participants': sum(defined),
                'defined_draws': defined_draws,
                'full_mean_defined': full,
                'observed_only_mean_defined': any(defined),
                'ci_defined': full and defined_draws == 1000,
            }
    return result


def admit(value, roster, contract, np):
    expected = expected_support(value, roster, contract, np)
    for condition in contract.CONDITIONS:
        for area in contract.AREAS:
            got, wanted = value['areas'][condition][area], expected[condition][area]
            prefix = condition + '/' + area + ': '
            for key in SUPPORT_NAMES:
                if got[key] != wanted[key]:
                    raise contract.Invalid(prefix + 'recording-derived ' + key + ' mismatch')
            for field, key in (('full_mean_ms', 'full_mean_defined'),
                               ('observed_only_mean_ms', 'observed_only_mean_defined'),
                               ('ci95_ms', 'ci_defined')):
                if (got[field] is not None) != wanted[key]:
                    raise contract.Invalid(prefix + 'recording-derived ' + field + ' null mismatch')
    return value


def primary_dispositions_match(candidate, expected):
    """Compare every primary status/null/support field; numerical values stay graded."""
    def equal(a, b, key=''):
        if b is None or a is None:
            return a is b
        if isinstance(b, dict):
            return isinstance(a, dict) and set(a) == set(b) and all(equal(a[k], b[k], k) for k in b)
        if isinstance(b, list):
            return isinstance(a, list) and len(a) == len(b) and all(equal(x, y) for x, y in zip(a, b))
        if type(b) in (int, float) and key not in SUPPORT_NAMES:
            return type(a) in (int, float)
        return a == b

    def primary(value):
        return {'recordings': {r['recording_id']: r['conditions']['primary'] for r in value['recordings']},
                'areas': value['areas']['primary']}
    return equal(primary(candidate), primary(expected))


def compare(candidate, expected, grade):
    result = grade.compare(candidate, expected)
    match = primary_dispositions_match(candidate, expected)
    result['primary_support_and_null_dispositions_match'] = match
    if not match:
        result['primary_mae_ms'] = None
    result['support_consistency_companion'] = 'neural100_support_consistency_v1'
    result['primary_support_rule'] = 'All primary recording and area support/status/null fields must match.'
    return result


def evaluate(value, roster, reference_loader, sources, np):
    contract, grade = sources.module('report_contract'), sources.module('grade')
    admit(value, roster, contract, np)
    # Only a complete internally consistent candidate can reach private data.
    try:
        expected = contract.project(reference_loader())
        admit(expected, roster, contract, np)
    except Exception as error:
        raise SourceError('Operator reference failed support consistency') from error
    return compare(value, expected, grade)


def publish(output, result):
    """Publish exclusively after file fsync; observed CLI exit0 is still required.

    A pre-publication failure leaves only .pending. A later unlink/directory
    failure can leave the final path, which alone never proves success.
    """
    output = canonical(output)
    need(not os.path.lexists(output) and output.parent.is_dir(), 'Fresh operator output path')
    pending = output.with_name(output.name + '.pending')
    raw = (json.dumps(result, allow_nan=False, indent=2) + '\n').encode()
    need(len(raw) <= 2000000, 'Bounded output artifact')
    fd = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    os.link(pending, output, follow_symlinks=False)
    pending.unlink()
    directory_fd = os.open(output.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--package', required=True, type=Path)
    p.add_argument('--submission', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--mode', required=True, choices=('admit', 'grade'))
    p.add_argument('--packet', type=Path)
    a = p.parse_args()
    output = canonical(a.output)
    need(not os.path.lexists(output) and output.parent.is_dir(), 'Fresh operator output path')
    sources = FrozenSources(a.package)
    io, contract = sources.module('artifact_io'), sources.module('report_contract')
    import numpy as np
    value = io.decode_json(capture(a.submission, io.MAX_JSON))
    if a.mode == 'admit':
        admit(value, sources.roster, contract, np)
        result = {'task_id': 'NEURAL-100', 'status': 'support_consistent_artifact_only',
                  'recordings': 47, 'participants': 41, 'conditions': 8,
                  'private_reference_calls': 0, 'scientific_qualification_added': False}
    else:
        need(a.packet is not None, 'Explicit packet required for future grading')
        packet = canonical(a.packet)

        def reference():
            adapter, core = sources.module('data_adapter'), sources.module('analysis_core')
            manifest = adapter.load_manifest(packet / 'PREPARED.json', sources.binding['manifest_sha256'])
            return core.analyze(adapter.records(packet, manifest), sources.roster)

        result = evaluate(value, sources.roster, reference, sources, np)
    result['requires_observed_cli_exit_zero'] = True
    publish(output, result)


if __name__ == '__main__':
    main()
