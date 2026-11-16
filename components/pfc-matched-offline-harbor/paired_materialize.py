"""Complete matched PFC task contexts; no Docker, science or model execution.

The production command is a separately selected public-asset materialization.
Source construction tests use only invented complete source/asset fixtures.
"""
from pathlib import Path
import hashlib
import json
import os
import re
import stat
import sys
import tomllib
import types

HERE = Path(__file__).resolve().parent
DONOR = HERE / 'upstream'
HELPER_PIN = (10878, 'd674975d9e79ffc21a54965206e1dc3d5b5050524123e33a8cca524c992eb755')
_HELPERS = None
MANIFEST_SHA = '914881559f331bf06192aebe5fd894b2a53f7ece5e8067101256c0ae637b3b97'
BASE = 'sha256:9aaf44dc64d85d0bbb0ffdd75ff5190ad94eff91d76849d14aea859c930955ff'
TASK = 'tasks/life-sciences/neuroscience/pfc-conditional-reconstruction'
OFFICIAL = ('category_matching.py', 'LICENSE')
NOTICE_PINS = {
    'ATTRIBUTION.md': (3143, 'b76176457083b74790bdd42889e5d14401f6e8898533e61c2fe5e222392a6c9c'),
    'PUBLIC_LINEAGE.json': (3783, 'ddd3152dd547a80a31708a6f350bf817c49b38fb8f7ec85a4cee1b36c907e6d3'),
    'DANDI_TERMS.md': (3347, '99eea9766e4f54fb03371ef418a642d08f6641c07f2f25fad7d71d2ce66edff9'),
    'RELEASE_NOTES.md': (3022, '20dae021788290c317b0e44101ac8a32bf0091547b7c14d2abc5bfadc173a755'),
}
README = b'''# PFC matched offline delivery profile

This is one existing69-case fixed-map conditional reconstruction benchmark with
two information conditions. It is not another scientific endpoint or benchmark ID.
Both conditions receive identical paper, packet, instructions, schema, tools and
budgets. Only B receives the selected official category_matching.py and LICENSE.
The instructions supply the conditional method in both arms: this is method-assisted
reconstruction, not neutral paper-only inference or access to the entire repository.

Fresh independent Harbor agent sessions disable verification. The paired delivery
tool freezes both complete artifacts before emitting separate regrade configs.
Submitted programs are not required or executed in the trusted verifier. The
unchanged exact scorer reads only submission.jsonl and retains all69 cases and
all12 families, including zero/undefined support. Artifacts are ordinary output
correctness evidence; no general reasoning or unseen-data capability is inferred.

The map/categories are supplied. There is no SOM refit, raw-signal interpretation,
new cohort, calibrated population confidence interval or frontier/SOTA claim.
Animal deletions are fixed-map sensitivity analyses. Public data/code and possible
pretraining exposure limit interpretation even when participant networking is off.

Complete context construction is not image admission or native Harbor validation.
The old open Science2 profile and accepted local paired route remain unchanged.
Real author/expert metadata, upstream checks, native A/B isolation, freeze/regrade
transport and model difficulty calibration remain separate requirements. Blank
author fields are deliberately preserved. No build or model trial is implied.
Keep the exact public input notices and official BSD-2-Clause license with B.
'''


def need(ok, message):
    if not ok:
        raise ValueError(message)


def load_helpers():
    global _HELPERS
    if _HELPERS is not None:
        return _HELPERS
    p = DONOR / 'materialize.py'
    need(HELPER_PIN is not None, 'bound helper identity')
    for parent in p.parents:
        need(stat.S_ISDIR(parent.lstat().st_mode), 'ordinary helper ancestors')
    before = p.lstat()
    signature = lambda s: (s.st_dev,s.st_ino,s.st_mode,s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
    need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_size==HELPER_PIN[0],
         'ordinary bounded helper source')
    fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'rb') as stream:
        need(signature(os.fstat(stream.fileno()))==signature(before),'opened helper source')
        raw=stream.read(HELPER_PIN[0]+1)
        need(signature(os.fstat(stream.fileno()))==signature(before),'stable opened helper')
    need(signature(p.lstat())==signature(before) and (len(raw), hashlib.sha256(raw).hexdigest()) == HELPER_PIN,
         'exact already reviewed filesystem helper source')
    m = types.ModuleType('_pfc_pair_donor'); m.__file__ = str(p)
    exec(compile(raw, str(p), 'exec'), m.__dict__)
    _HELPERS = m
    return m


def descriptor(relative, body):
    return {'path': relative, 'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def derive(common, assets, notices, base):
    """Pure complete-context derivation, with one explicit two-file treatment."""
    need(base == BASE, 'same independently admitted base identity for every image')
    h = load_helpers()
    common = dict(common)
    instruction = common['instruction.md']
    old = b'/official/category_matching.py is available with its license.'
    new = (b'Condition B additionally receives /official/category_matching.py and its license; '
           b'condition A does not. All other inputs, tools and instructions are identical.')
    need(instruction.count(old) == 1, 'exact common instruction availability clause')
    common['instruction.md'] = instruction.replace(old, new)
    need(common['task.toml'].count(b'network_mode = "public"') == 1,
         'exact prior public agent network declaration')
    common['task.toml'] = common['task.toml'].replace(b'network_mode = "public"',
                                                   b'network_mode = "no-network"')
    cfg = tomllib.loads(common['task.toml'].decode())
    need(cfg['environment']['network_mode'] == cfg['verifier']['environment']['network_mode'] == 'no-network',
         'both agent and clean verifier offline')
    need(cfg['agent']['timeout_sec'] == 28800 and cfg['environment']['cpus'] == 1
         and cfg['environment']['memory_mb'] == 4096 and cfg['environment']['gpus'] == 0
         and cfg['artifacts'] == ['/app/output/submission.jsonl'], 'unchanged task budget and artifact')
    common['README.md'] = README
    for role, token in (('environment', '__REVIEWED_PFC_RUNTIME_REFERENCE__'),
                        ('tests', '__REVIEWED_PFC_VERIFIER_RUNTIME_REFERENCE__')):
        template = role + '/Dockerfile.template'
        common[role + '/Dockerfile'] = h.render_dockerfile(common.pop(template), token, base)
    for name, body in assets.items():
        common['environment/assets/' + name] = body
    common['tests/assets/participant-packet.json'] = assets['participant-packet.json']
    for name, body in notices.items():
        common['environment/assets/notices/' + name] = body
        common['tests/assets/notices/' + name] = body
    b = common
    a = dict(b)
    for name in OFFICIAL:
        del a['environment/assets/' + name]
        line = ('COPY assets/' + name + ' /official/' + name + '\n').encode()
        need(a['environment/Dockerfile'].count(line) == 1, 'exact official COPY directive')
        a['environment/Dockerfile'] = a['environment/Dockerfile'].replace(line, b'')
    validate_pair(a, b)
    return {'A': a, 'B': b}


def validate_pair(a, b):
    extra = {'environment/assets/' + n for n in OFFICIAL}
    need(set(b) - set(a) == extra and not set(a) - set(b), 'exact B-only source/license files')
    need(all(a[n] == b[n] for n in a if n != 'environment/Dockerfile'), 'all common bytes identical')
    stripped = b['environment/Dockerfile']
    for name in OFFICIAL:
        stripped = stripped.replace(('COPY assets/' + name + ' /official/' + name + '\n').encode(), b'')
    need(a['environment/Dockerfile'] == stripped, 'only two official COPY differences')
    for arm, files, count in (('A', a, 8), ('B', b, 10)):
        need(len([n for n in files if n.startswith('environment/')]) == count,
             arm + ' complete agent context')
        need(len([n for n in files if n.startswith('tests/')]) == 12, 'complete verifier context')
        need(len(files) == (26 if arm == 'A' else 28), 'complete task namespace')
        forbidden = ('solution/', 'tests/', 'reference', 'owner', 'score.json')
        for n in files:
            if n.startswith('environment/'):
                need(not any(x in n[len('environment/'):] for x in forbidden), 'no protected agent-context member')


def construct(request, *, reader=None):
    h = load_helpers()
    reader = h.Reads(64 * 1024**2) if reader is None else reader
    need(type(request) is dict and set(request) == {'schema', 'execution_selected', 'source_root',
         'asset_root', 'output_root', 'base_image'}, 'exact selected materialization request')
    need(request['schema'] == 'PFC_MATCHED_PAIR_MATERIALIZE_V1' and request['execution_selected'] is True,
         'separate explicit authentic materialization selection')
    source = h.plain_path(request['source_root'])
    asset_root = h.plain_path(request['asset_root'])
    output = h.plain_path(request['output_root'], exists=False)
    need(not os.path.lexists(output), 'fresh paired output namespace')
    for i, left in enumerate((source, asset_root, output)):
        for right in (source, asset_root, output)[i+1:]:
            need(left != right and left not in right.parents and right not in left.parents,
                 'disjoint source, assets and pair roots')
    raw = reader.read(source / 'SOURCE_MANIFEST.json', 262144)
    need(hashlib.sha256(raw).hexdigest() == MANIFEST_SHA, 'exact incumbent source manifest')
    manifest = h.decode(raw)
    need(manifest['schema'] == 'PFC_SCIENCE2_SOURCE_MANIFEST_V1', 'incumbent source schema')
    rows = manifest['files']; names = {r['path'] for r in rows}
    need(len(rows) == len(names) == 15 and h.file_roster(source / 'task') == names,
         'complete incumbent fifteen-source namespace')
    need(h.file_roster(asset_root) == set(h.ASSETS) | set(NOTICE_PINS), 'complete four public assets and notices')
    common = {}
    for row in rows:
        p = Path(row['path'])
        need(not p.is_absolute() and '..' not in p.parts, 'relative frozen source member')
        common[row['path']] = reader.read(source / 'task' / p, 1048576, (row['bytes'], row['sha256']))
    assets = {n: reader.read(asset_root / n, 8388608, pin) for n, pin in h.ASSETS.items()}
    notices = {n: reader.read(asset_root / n, 262144, pin) for n, pin in NOTICE_PINS.items()}
    pair = derive(common, assets, notices, request['base_image'])
    flat = {arm + '/' + TASK + '/' + n: b for arm, files in pair.items() for n, b in files.items()}
    need(sum(map(len, flat.values())) <= 32 * 1024**2, 'complete pair retention extent')
    # All source/asset/difference checks precede the first write. Partial outputs
    # remain after a filesystem failure and are never retried into the same root.
    output.mkdir(mode=0o700)
    for name, body in sorted(flat.items()):
        p = output / name; p.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with p.open('xb') as stream:
            stream.write(body); stream.flush(); os.fsync(stream.fileno())
        p.chmod(0o755 if name.endswith(('solution/solve.sh', 'tests/test.sh')) else 0o644)
    for name, body in flat.items():
        reader.read(output / name, 8388608, (len(body), hashlib.sha256(body).hexdigest()))
    need(h.file_roster(output) == set(flat), 'complete pair output namespace')
    report = {'schema': 'PFC_MATCHED_PAIR_CONTEXTS_V1', 'files': [descriptor(n,b) for n,b in sorted(flat.items())],
              'source_manifest_sha256':MANIFEST_SHA,
              'task_roots': {a: str(output / a / TASK) for a in ('A','B')}, 'base_image': BASE,
              'packet_identity': list(h.ASSETS['participant-packet.json']), 'cases':69,
              'conditions_are_one_benchmark':True, 'scientific_source_unchanged':True,
              'official_code_only_B':True, 'common_task_and_tools_equal':True,
              'managed_body_read_bytes':reader.bytes, 'images_admitted':False,
              'native_isolation_verified':False, 'model_runs':0, 'new_benchmark_ids':0}
    raw = h.encode(report)
    with (output / 'PAIR_MANIFEST.json').open('xb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    (output / 'PAIR_MANIFEST.json').chmod(0o400)
    return report


def main(argv):
    need(len(argv) == 1, 'usage: paired_materialize.py SELECTED_REQUEST.json')
    h = load_helpers(); reader = h.Reads(64 * 1024**2)
    request = h.decode(reader.read(Path(argv[0]), 65536))
    sys.stdout.buffer.write(h.encode(construct(request, reader=reader)))


if __name__ == '__main__':
    main(sys.argv[1:])
