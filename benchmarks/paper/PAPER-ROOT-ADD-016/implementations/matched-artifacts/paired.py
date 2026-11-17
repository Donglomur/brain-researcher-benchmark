"""Trusted-operator paired artifact interface; never executes participant code.

Only CLI uses the frozen authentic specification. Packet is an internal seam for
small generated controls, not an untrusted alternate-spec entrypoint.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import uuid

HERE = Path(__file__).resolve().parent
SPEC_SHA = '48dcebc6b2687b07cabf18dec00441f489e002d8c1d45c2958246bca0b40798c'
FILES_SHA = 'cd334f0f0e83f96f3f1bf00baf741e7b792970585cb11bff69279c188bc376f0'
SCORER_SHA = 'a622dc6b7780e49b20879fdf5fddb76aac62d6a20c1b93be993b57d0000ee99a'


def need(ok, text):
    if not ok:
        raise ValueError(text)


def pin(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()


def unique(pairs):
    result = {}
    for key, value in pairs:
        need(key not in result, 'Duplicate JSON key')
        result[key] = value
    return result


def decode(raw):
    def invalid(value):
        raise ValueError('Nonfinite JSON constant: ' + value)
    return json.loads(raw, object_pairs_hook=unique, parse_constant=invalid)


def unlinked(path):
    path = Path(path).absolute()
    need('..' not in path.parts and not any(p.is_symlink() for p in (path, *path.parents)), 'Unlinked canonical path')
    return path


def load_source(name, path, digest):
    path = unlinked(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 < before.st_size <= 100000, 'Bounded source')
        raw = stream.read(100001)
        after = os.fstat(stream.fileno())
        need((before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
             (after.st_size, after.st_mtime_ns, after.st_ctime_ns), 'Stable source')
    need(pin(raw)['sha256'] == digest, 'Exact trusted module')
    spec = importlib.util.spec_from_loader(name, loader=None, origin=str(path))
    module = importlib.util.module_from_spec(spec)
    module.__file__ = str(path)
    exec(compile(raw, str(path), 'exec'), module.__dict__)
    return module


F = load_source('_cardiac_pair_files', HERE / 'files.py', FILES_SHA)
REPOSITORY = HERE.parents[1]
S = load_source('_cardiac_pair_summary', REPOSITORY / 'components/cardiac-six-model-summary/summary_score.py', SCORER_SHA)


def relative(name):
    need(type(name) is str and name and '\\' not in name and not any(ord(c) < 32 for c in name), 'Safe relative name')
    p = Path(name)
    need(not p.is_absolute() and '..' not in p.parts and p.as_posix() == name, 'Canonical relative name')
    return p


def fresh(path, sources):
    path = unlinked(path)
    need(path.parent.is_dir() and not path.exists(), 'Fresh output with existing parent')
    for source in sources:
        source = unlinked(source)
        need(path != source and path not in source.parents and source not in path.parents, 'Separate output/source roots')
    return path


def write(path, raw, mode=0o600):
    path = unlinked(path)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    return pin(raw)


class Packet:
    def __init__(self, spec, repository, bundle=HERE, operands=None):
        self.spec = spec
        self.roots = {'repository': unlinked(repository), 'bundle': unlinked(bundle)}
        if operands is not None:
            self.roots['operands'] = unlinked(operands)
        need(spec['schema'] == 'cardiac_matched_packet_v1' and spec['candidate_id'] == 'PAPER-ROOT-ADD-016', 'Exact task')
        need(set(spec['common']).isdisjoint(spec['B_only']), 'Disjoint packet roles')
        for name, item in (spec['common'] | spec['B_only']).items():
            relative(name); self.source(item)
            need(Path(name).name not in ('model.py', 'posterior_summary.py'), 'No developer numerical helpers')
        self.spec_pin = pin(encoded(spec))

    def source(self, item):
        need(type(item) is dict and set(item) == {'root', 'path', 'bytes', 'sha256'}, 'Exact source descriptor')
        need(item['root'] in self.roots and type(item['bytes']) is int and 0 < item['bytes'] <= 42000000, 'Bounded source identity')
        need(type(item['sha256']) is str and len(item['sha256']) == 64 and all(c in '0123456789abcdef' for c in item['sha256']), 'SHA256')
        return self.roots[item['root']] / relative(item['path'])

    def members(self, condition):
        need(condition in ('A', 'B'), 'Exact condition')
        return self.spec['common'] | (self.spec['B_only'] if condition == 'B' else {})

    def roster(self, condition):
        return {name: {k: item[k] for k in ('bytes', 'sha256')} for name, item in sorted(self.members(condition).items())}

    def request(self, condition, pair_id):
        need(type(pair_id) is str and len(pair_id) == 32 and all(c in '0123456789abcdef' for c in pair_id), 'Pair nonce')
        return {'schema': 'cardiac_condition_request_v1', 'candidate_id': self.spec['candidate_id'],
                'pair_id': pair_id, 'condition': condition, 'spec': self.spec_pin,
                'packet': pin(encoded(self.roster(condition))), 'scope': self.spec['scope'],
                'execution_policy': self.spec['execution_policy'],
                'evidence_kind': 'trusted external artifacts; no authoring/execution attestation'}

    def receipt(self, pair_id):
        return {'schema': 'cardiac_pair_materialization_v1', 'pair_id': pair_id, 'spec': self.spec_pin,
                'requests': {c: self.request(c, pair_id) for c in ('A', 'B')},
                'scorer': self.spec['scorer'], 'reference': self.spec['reference']}

    def checked_read(self, item, cap=200000):
        raw = F.read(self.source(item), cap)
        need(pin(raw) == {k: item[k] for k in ('bytes', 'sha256')}, 'Exact source bytes')
        return raw

    def copy(self, item, destination):
        source = self.source(item)
        stream, before = F.stream(source, item['bytes'])
        digest = hashlib.sha256(); count = 0
        with stream:
            fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o444)
            with os.fdopen(fd, 'wb') as out:
                while True:
                    block = stream.read(65536)
                    if not block: break
                    count += len(block); need(count <= item['bytes'], 'Source grew')
                    digest.update(block); out.write(block)
                F.stable(before, os.fstat(stream.fileno()))
                out.flush(); os.fsync(out.fileno())
        need({'bytes': count, 'sha256': digest.hexdigest()} == {k: item[k] for k in ('bytes', 'sha256')}, 'Exact complete copied source')

    def bounded_pin(self, source, cap):
        stream, before = F.stream(source, cap)
        count = 0; digest = hashlib.sha256()
        with stream:
            while True:
                block = stream.read(min(65536, cap - count + 1))
                if not block: break
                count += len(block); need(count <= cap, 'Packet file grew beyond exact extent')
                digest.update(block)
            F.stable(before, os.fstat(stream.fileno()))
        return {'bytes': count, 'sha256': digest.hexdigest()}

    def build(self, output):
        output = fresh(output, self.roots.values()); output.mkdir(mode=0o700)
        # Failure leaves its owned partial tree, but never a success receipt.
        pair_id = uuid.uuid4().hex
        for condition in ('A', 'B'):
            dest = output / condition; dest.mkdir(mode=0o700)
            for name, item in sorted(self.members(condition).items()):
                target = dest / relative(name); target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                self.copy(item, target)
            self.audit(dest, condition)
            for folder, dirs, _ in os.walk(dest, topdown=False): os.chmod(folder, 0o500)
            write(output / (condition + '.request.json'), encoded(self.request(condition, pair_id)), mode=0o444)
        write(output / 'receipt.json', encoded(self.receipt(pair_id)))
        return self.receipt(pair_id)

    def audit(self, folder, condition):
        folder = unlinked(folder); wanted = self.roster(condition)
        need(folder.is_dir(), 'Packet directory')
        observed = set(); directories = set()
        permitted_dirs = {str(p) for name in wanted for p in relative(name).parents if str(p) != '.'}
        for parent, dirs, names in os.walk(folder, followlinks=False):
            for name in dirs:
                p = unlinked(Path(parent) / name); directories.add(p.relative_to(folder).as_posix())
                need(len(directories) <= len(permitted_dirs), 'No extra packet directories')
            for name in names:
                p = unlinked(Path(parent) / name); rel = p.relative_to(folder).as_posix()
                need(rel in wanted and rel not in observed, 'No undeclared packet asset')
                observed.add(rel)
                need(self.bounded_pin(p, wanted[rel]['bytes']) == wanted[rel], 'Packet byte identity')
        need(observed == set(wanted) and directories == permitted_dirs, 'Complete exact packet tree')

    def pair(self, folder):
        folder = unlinked(folder)
        receipt = decode(F.read(folder / 'receipt.json', 100000))
        need(receipt == self.receipt(receipt.get('pair_id')), 'Exact pair/scorer/reference binding')
        for condition in ('A', 'B'):
            need(decode(F.read(folder / (condition + '.request.json'), 20000)) == receipt['requests'][condition], 'Exact issued condition request')
        return receipt

    def capture(self, pair_folder, condition, request, program, summary, output):
        receipt = self.pair(pair_folder); expected = receipt['requests'][condition]
        need(decode(F.read(request, 20000)) == expected, 'Condition request mismatch')
        self.audit(Path(pair_folder) / condition, condition)
        program = unlinked(program); summary = unlinked(summary)
        raw_program = F.read(program, 131072); raw_summary = F.read(summary, 200000)
        value = S.validate(decode(raw_summary))
        need(value['input_sha256'] == self.spec['scope']['input_sha256'], 'Complete exact input identity')
        out = fresh(output, [*self.roots.values(), Path(pair_folder), program, summary]); out.mkdir(mode=0o700)
        bound = {'schema': 'cardiac_condition_capture_v1', 'request': expected,
                 'program': write(out / 'program.py', raw_program), 'summary': write(out / 'summary.json', raw_summary)}
        write(out / 'capture.json', encoded(bound))
        return bound

    def score_pair(self, pair_folder, a_capture, b_capture, output):
        receipt = self.pair(pair_folder)
        output = fresh(output, [*self.roots.values(), Path(pair_folder), Path(a_capture), Path(b_capture)])
        candidates = {}; captures = {}
        # Validate and snapshot BOTH complete candidate artifacts before target access.
        for condition, directory in (('A', a_capture), ('B', b_capture)):
            directory = unlinked(directory)
            self.audit(Path(pair_folder) / condition, condition)
            bound = decode(F.read(directory / 'capture.json', 30000))
            need(type(bound) is dict and set(bound) == {'schema', 'request', 'program', 'summary'} and
                 bound['schema'] == 'cardiac_condition_capture_v1' and bound['request'] == receipt['requests'][condition], 'Exact captured condition')
            program = F.read(directory / 'program.py', 131072)
            raw = F.read(directory / 'summary.json', 200000)
            need(pin(program) == bound['program'] and pin(raw) == bound['summary'], 'Captured artifact drift')
            candidate = S.validate(decode(raw))
            need(candidate['input_sha256'] == self.spec['scope']['input_sha256'], 'Exact input before target access')
            candidates[condition] = candidate; captures[condition] = bound
        need(unlinked(a_capture) != unlinked(b_capture), 'Separate condition captures')
        need(self.spec['scorer']['sha256'] == SCORER_SHA, 'Unchanged selected scorer')
        reference = S.validate(decode(self.checked_read(self.spec['reference'])))
        result = {'schema': 'cardiac_matched_artifact_scores_v1', 'pair': receipt, 'captures': captures,
                  'scores': {c: S.score(candidates[c], reference) for c in ('A', 'B')},
                  'qualification': 'artifact interface only; no code-benefit, execution-isolation, convergence or new readiness claim'}
        write(output, encoded(result)); return result


def configured(operands, reference_binding):
    """Bind an operator's admitted private reference; no target body is opened."""
    raw = F.read(HERE / 'PACKET_SPEC.json', 100000)
    need(pin(raw)['sha256'] == SPEC_SHA, 'Frozen authentic packet specification')
    spec = decode(raw)
    binding = decode(F.read(reference_binding, 20000))
    need(type(binding) is dict and set(binding) == {'schema', 'benchmark_id', 'input_sha256', 'reference'},
         'Exact operator reference binding')
    need(binding['schema'] == 'cardiac_private_reference_binding_v1' and
         binding['benchmark_id'] == spec['candidate_id'] and
         binding['input_sha256'] == spec['scope']['input_sha256'], 'Same full scientific task')
    row = binding['reference']
    need(type(row) is dict and set(row) == {'path', 'bytes', 'sha256'}, 'Private reference descriptor')
    need(type(row['bytes']) is int and 0 < row['bytes'] <= 200000, 'Bounded private reference')
    spec['reference'] = {'root': 'operands', **row}
    result = Packet(spec, REPOSITORY, HERE, operands)
    result.source(spec['reference'])  # Path/hash schema only; never opens the target.
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--operands', required=True, type=Path)
    parser.add_argument('--reference-binding', required=True, type=Path)
    sub = parser.add_subparsers(dest='command', required=True)
    b = sub.add_parser('build'); b.add_argument('--out', required=True, type=Path)
    c = sub.add_parser('capture')
    for name in ('pair', 'request', 'program', 'summary', 'out'): c.add_argument('--' + name, required=True, type=Path)
    c.add_argument('--condition', choices=('A', 'B'), required=True)
    s = sub.add_parser('score-pair')
    for name in ('pair', 'a', 'b', 'out'): s.add_argument('--' + name, required=True, type=Path)
    args = parser.parse_args(); p = configured(args.operands, args.reference_binding)
    if args.command == 'build': p.build(args.out)
    elif args.command == 'capture': p.capture(args.pair, args.condition, args.request, args.program, args.summary, args.out)
    else: p.score_pair(args.pair, args.a, args.b, args.out)


if __name__ == '__main__': main()
