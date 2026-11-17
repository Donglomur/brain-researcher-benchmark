"""Owner-controlled future author replay; never accepts candidate result objects.

The caller must admit the runtime and separately authorize native computation.
This module does not install packages, provision a runtime, or access a network.
"""
import argparse
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

HERE = Path(__file__).resolve().parent
PROFILE = HERE.parent / 'nider-full120-reconstruction-profile-v1'
PINS = {
    'workbook': ('ef13337351bac9f9fd10d693a81f768633a87a62c8742ad3279528b7f7667498', 63870),
    'script': ('caa4ac8a0ee84821c19df5fc26c4a7527ef164c6f48f19e2deed3d0a888cd334', 18666),
    'lock': ('c39c34f524eabcf2b72df5900fee43df504b49652ae956ed9c5d5a93a45c1064', 60147),
    'schema': ('b6e220d597f2848c83f78c25cd981980888856431701441f426c329e555b9e22', None),
    'interface': ('79b3a6be47c1240ba0f19389da5b03251e86502e91d30b38b1ed25281161f07c', None),
    'comparator': ('1c24ec4f2fc5d722541e9231268af21218672ee9453f309110acecffaf5833bf', 11093),
    'reporting_core': ('8f87075849eece5320354fb05e5f1fa37eb3f541a0b9d8e924c79f9073e35963', None),
}
SPANS = tuple((n, n) for n in range(13, 20)) + ((28, 28), (29, 29),
    (73, 73), (74, 74), (75, 75), (77, 82), (86, 129), (131, 138),
    (140, 140), (141, 141), (149, 149), (153, 153), (216, 216), (219, 219),
    (262, 262), (265, 265))


def require(ok, code):
    if not ok:
        raise ValueError(code)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read_pinned(path, key):
    path = Path(path)
    require(path.is_file() and not path.is_symlink(), 'regular_input_required:' + key)
    raw = path.read_bytes()
    digest, size = PINS[key]
    require(sha(raw) == digest and (size is None or len(raw) == size), 'source_identity:' + key)
    return raw


def expression_manifest(script):
    # Exact whole-file authentication precedes line interpretation.
    require(sha(script) == PINS['script'][0], 'source_identity:script')
    lines = script.decode('utf-8').splitlines(keepends=True)
    return [{'start': a, 'end': b, 'sha256': sha(''.join(lines[a-1:b]).encode())}
            for a, b in SPANS]


def public_contract():
    paths = {'schema': PROFILE / 'participant/FIELD_SCHEMA.json',
             'interface': PROFILE / 'participant/OUTPUT_INTERFACE.json',
             'comparator': PROFILE / 'comparator/extended_score.py',
             'reporting_core': PROFILE / 'comparator/reporting_core.py'}
    return {key: read_pinned(path, key) for key, path in paths.items()}


def load_validator(contract):
    # Execute only authenticated sibling bytes, avoiding ambient import shadowing.
    modules = {}
    prior = sys.modules.get('reporting_core')
    try:
        for key, name in [('reporting_core', 'reporting_core'), ('comparator', '_nider_pinned_score')]:
            require(sha(contract[key]) == PINS[key][0], 'validator_identity:' + key)
            module = importlib.util.module_from_spec(importlib.util.spec_from_loader(name, loader=None))
            exec(compile(contract[key], '<authenticated ' + name + '>', 'exec'), module.__dict__)
            modules[key] = module
            if key == 'reporting_core':
                sys.modules[name] = module
    finally:
        if prior is None:
            sys.modules.pop('reporting_core', None)
        else:
            sys.modules['reporting_core'] = prior
    return modules['reporting_core'], modules['comparator']


def validate_output(raw, arm, contract):
    require(type(raw) is bytes and len(raw) <= 65536, 'output_extent')
    decoder, validator = load_validator(contract)
    doc = decoder.decode_numeric_json(raw)
    result = validator.validate(doc, arm, PINS['workbook'][0])
    for row, _ in result.values():
        order = [unit['retained_row'] for unit in row['membership']]
        require(order == sorted(order), 'ordered_membership_required')
    return doc


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + '\n').encode()


def clean_environment():
    # A clean process cannot inherit R startup/settings hooks or implicit workers.
    env = {k: v for k, v in os.environ.items() if not k.startswith(('R_', 'RENV_'))}
    env.update({'RENV_CONFIG_AUTOLOADER_ENABLED': 'FALSE', 'RENV_CONFIG_AUTO_SNAPSHOT': 'FALSE',
                'OMP_NUM_THREADS': '1', 'OPENBLAS_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1',
                'VECLIB_MAXIMUM_THREADS': '1', 'RCPP_PARALLEL_NUM_THREADS': '1'})
    return env


def publish_new(path, raw):
    # Never overwrite prior scientific results or failed-run evidence.
    with tempfile.NamedTemporaryFile(dir=Path(path).parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
            os.link(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


def retained_bytes(raw, limit=1048576):
    raw = raw or b''
    return {'bytes': len(raw), 'sha256': sha(raw), 'base64': base64.b64encode(raw[:limit]).decode('ascii'),
            'retained_bytes': min(len(raw), limit), 'truncated': len(raw) > limit}


def retain_native_files(root):
    # These owner-private failure bytes may contain scientific values. Never commit them.
    return {name: retained_bytes((root / name).read_bytes()) for name in ('full120.json', 'runtime.json')
            if (root / name).is_file()}


def run(args):
    output, provenance = Path(args.output).resolve(), Path(args.provenance).resolve()
    require(output != provenance and not output.exists() and not provenance.exists(), 'new_distinct_outputs_required')
    require(output.parent.is_dir() and provenance.parent.is_dir(), 'output_parent_missing')
    contract = public_contract()
    source_paths = {'workbook': args.original_workbook, 'script': args.official_script, 'lock': args.renv_lock}
    sources = {key: read_pinned(path, key) for key, path in source_paths.items()}
    manifest = expression_manifest(sources['script'])
    executable = shutil.which(args.rscript)
    require(executable is not None, 'Rscript_missing_no_install_attempted')
    executable = str(Path(executable).resolve())
    require(args.runtime_identity.strip(), 'owner_runtime_identity_required')
    rscript_sha = sha(Path(executable).read_bytes())
    started = time.time()
    with tempfile.TemporaryDirectory(prefix='nider-primary-v2-') as temporary:
        root = Path(temporary)
        source_dir = root / 'data/studyInformation'
        source_dir.mkdir(parents=True)
        (root / '.here').write_bytes(b'')
        paths = {'workbook': source_dir / 'studyInformation_publication.xlsx',
                 'script': root / 'official.R', 'lock': root / 'original-renv.lock',
                 'schema': root / 'FIELD_SCHEMA.json'}
        for key, path in paths.items():
            path.write_bytes((sources | contract)[key])
        implementation_names = ('collector.R', 'source_selection.R', 'replay_primary_dl.R')
        for name in implementation_names:
            (root / name).write_bytes((HERE / name).read_bytes())
        job = {'arm': args.arm, 'pins': {key: PINS[key][0] for key in paths},
               'expressions': manifest,
               'implementation_hashes': {name: sha((root / name).read_bytes())
                                        for name in implementation_names}}
        (root / 'job.json').write_bytes(json_bytes(job))
        command = [executable, '--vanilla', str(root / 'replay_primary_dl.R')]
        record = {'schema': 'nider_primary_dl_provenance_v2',
                  'producer': 'new-source-faithful-collector-v2-not-recovered-legacy-code',
                  'command': command, 'owner_runtime_identity': args.runtime_identity,
                  'owner_runtime_identity_is_external_admission': True,
                  'Rscript': {'path': executable, 'sha256': rscript_sha},
                  'sources': {key: {'sha256': sha(raw), 'bytes': len(raw)}
                              for key, raw in (sources | contract).items()},
                  'implementation': job['implementation_hashes'] |
                                    {'replay_primary_dl.py': sha(Path(__file__).read_bytes())},
                  'expressions': manifest, 'arm': args.arm,
                  'output_published': False,
                  'complete_primary_success': False, 'scientific_agreement_assessed': False}
        try:
            completed = subprocess.run(command, cwd=root, env=clean_environment(),
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=args.timeout)
        except (subprocess.TimeoutExpired, OSError) as error:
            record.update(status='native_process_timeout' if isinstance(error, subprocess.TimeoutExpired)
                          else 'native_launch_failed', error=str(error),
                          elapsed_wall_seconds=time.time() - started,
                          stdout=retained_bytes(getattr(error, 'stdout', None)),
                          stderr=retained_bytes(getattr(error, 'stderr', None)),
                          rejected_native_files=retain_native_files(root))
            publish_new(provenance, json_bytes(record))
            raise
        record.update(returncode=completed.returncode, elapsed_wall_seconds=time.time() - started,
                      stdout=retained_bytes(completed.stdout), stderr=retained_bytes(completed.stderr))
        if completed.returncode:
            record['status'] = 'native_process_failed'
            record['rejected_native_files'] = retain_native_files(root)
            publish_new(provenance, json_bytes(record))
            raise RuntimeError('native process failed; provenance retained')
        try:
            raw = (root / 'full120.json').read_bytes()
            validate_output(raw, args.arm, contract)
            runtime = json.loads((root / 'runtime.json').read_text())
            require(runtime['R_version'] == '4.3.2', 'runtime_record_mismatch')
            require(runtime['evaluated_expression_count'] == len(SPANS), 'expression_count_mismatch')
            record.update(status='direct_DL_component_only', runtime=runtime,
                          output={'sha256': sha(raw), 'bytes': len(raw)})
        except Exception as error:
            record.update(status='output_validation_failed', error=str(error),
                          rejected_native_files=retain_native_files(root))
            publish_new(provenance, json_bytes(record))
            raise
        try:
            publish_new(output, raw)
        except OSError as error:
            record.update(status='output_publication_failed', error=str(error),
                          rejected_native_files=retain_native_files(root))
            publish_new(provenance, json_bytes(record))
            raise
        record['output_published'] = True
        # Provenance is the completion marker; consumers require BOTH pinned files.
        publish_new(provenance, json_bytes(record))
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--original-workbook', required=True)
    parser.add_argument('--official-script', required=True)
    parser.add_argument('--renv-lock', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--provenance', required=True)
    parser.add_argument('--arm', choices=('A', 'B'), required=True)
    parser.add_argument('--rscript', default='Rscript')
    parser.add_argument('--runtime-identity', required=True, help='owner-admitted runtime/image identifier')
    parser.add_argument('--timeout', type=int, default=180)
    args = parser.parse_args()
    require(1 <= args.timeout <= 180, 'bounded_timeout_required')
    run(args)


if __name__ == '__main__':
    main()
