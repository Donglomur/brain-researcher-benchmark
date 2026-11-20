"""Compile an explicit one-phase assisted VALID owner from exact retained source.

This writes a fresh private source tree only. It starts no process, opens no
neural data, changes no published source, and does not qualify execution.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import stat

HERE = Path(__file__).absolute().parent
OWNER_REL = Path('benchmarks/paper/PAPER-SMC-RNN-2024/implementations/aggregate-owner-v1')
OWNER_SOURCE = {'bytes': 7569, 'sha256': '44026e04ca813e3a22a893b848c2249d642559c49d75d76e3173fa1966e27a86'}
OWNER_FILES = {'common.py', 'legacy.py', 'cli_custody.py', 'journal.py', 'process_owner.py',
               'group_bootstrap.py', 'trusted_controller.py', 'owned_episode.py', 'controller.py',
               'runner.py', 'cgroup.py'}
PHASES = ('validation_reference',)
PATCHES = {
    'common.py': [
        ("CONDITIONS = ('paper_data', 'paper_data_author_code_and_weights')",
         "CONDITIONS = ('validation_reference',)"),
        ("PAIR_SECONDS = {'reproduction': 173760, 'improvement': 22560}",
         "PAIR_SECONDS = {'reproduction': 173760, 'improvement': 22560, 'restricted_validation_reference': 11280}"),
    ],
    'process_owner.py': [
        ("PAIR_SECONDS = {'reproduction': 173760, 'improvement': 22560}",
         "PAIR_SECONDS = {'reproduction': 173760, 'improvement': 22560, 'restricted_validation_reference': 11280}"),
    ],
    'cgroup.py': [
        ("PHASES = ('paper_data', 'paper_data_author_code_and_weights')",
         "PHASES = ('validation_reference',)"),
    ],
    'journal.py': [
        ("'action': 'held_attempt', 'role': 'A' if phase == CONDITIONS[0] else 'B',",
         "'action': 'held_attempt', 'role': 'B',"),
    ],
    'owned_episode.py': [
        ("exposure = {'schema': 'osl_transport_exposure_v1', 'role': 'A' if index == 0 else 'B',",
         "exposure = {'schema': 'osl_transport_exposure_v1', 'role': 'B',"),
    ],
}


def need(value, message):
    if not value:
        raise ValueError(message)


def encode(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()


def pin(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def canonical(value):
    result = Path(value).absolute()
    need(str(result) == str(value) and '..' not in result.parts
         and not any(p.is_symlink() for p in (result, *result.parents)), 'Canonical unlinked source/output path')
    return result


def descriptor(value):
    import re
    need(type(value) is dict and set(value) == {'bytes', 'sha256'}
         and type(value['bytes']) is int and 0 < value['bytes'] <= 1024**2
         and type(value['sha256']) is str and re.fullmatch('[0-9a-f]{64}', value['sha256']),
         'Exact bounded source descriptor')
    return value


def source(path, expected=None):
    path = canonical(path)
    if expected is not None:
        descriptor(expected)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 < before.st_size <= 1024**2,
             'Ordinary single-link bounded source')
        need(expected is None or before.st_size == expected['bytes'], 'Exact source extent before read')
        raw = stream.read(1024**2 + 1)
        after, named = os.fstat(stream.fileno()), path.lstat()
    fields = ('st_dev', 'st_ino', 'st_mode', 'st_nlink', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
    need(len(raw) == before.st_size and all(getattr(before, k) == getattr(after, k) == getattr(named, k)
                                          for k in fields), 'Stable source before compilation')
    need(expected is None or pin(raw) == expected, 'Exact retained/component source bytes')
    return raw


def decode(raw):
    def unique(items):
        result = {}
        for key, value in items:
            need(key not in result, 'Duplicate source JSON key')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=unique,
                      parse_constant=lambda _: need(False, 'Finite source JSON'))


def component_sources(component_root, expected=None):
    root = canonical(component_root)
    raw = source(root / 'SOURCE.json', expected)
    manifest = decode(raw)
    need(type(manifest) is dict and manifest.get('schema') == 'smc_validation_owned_component_v1'
         and type(manifest.get('files')) is dict and 1 <= len(manifest['files']) <= 128,
         'Bounded closed VALID owned component manifest')
    required = {'validation_core.py', 'validation_episode.py', 'validation_overlay.py', 'validation_legacy.py',
                'validation_owner.py', 'BINDINGS.json', 'DEPLOYMENT_BINDING.json', 'VALIDATION_TASK.json'}
    need(required <= set(manifest['files']) and 'SOURCE.json' not in manifest['files'],
         'Complete VALID source without self-hash')
    bodies = {}
    for name, expected_file in manifest['files'].items():
        rel = Path(name)
        need(type(name) is str and not rel.is_absolute() and '..' not in rel.parts
             and str(rel) == name and name not in ('', '.'), 'Canonical local component member')
        bodies[name] = source(root / rel, expected_file)
    return pin(raw), manifest, bodies


def derive_custody_runner(raw):
    """Append a no-target custody command using the retained grade admission prefix.

    The source bytes are authenticated by derive_owner_sources before this exact
    occurrence-checked derivation. The execute and grade bodies remain intact.
    """
    start = b'def grade(owner_folder, result_sha256, target, evaluator, output, scratch_bytes):\n'
    first = b'    folder = ordinary(owner_folder)\n'
    boundary = b'    return legacy.load()._grade_from_owned_pair('
    need(raw.count(start) == 1 and raw.count(boundary) == 1, 'Exact retained grade boundary')
    at = raw.index(start)
    body_start = raw.index(first, at)
    body_end = raw.index(boundary, body_start)
    prefix = raw[body_start:body_end]
    need(prefix.endswith(b'    validate_aggregate_completion(folder, result, invocation)\n'),
         'Complete original aggregate/Provider/controller proof prefix')
    custody = (b'def custody(owner_folder, result_sha256, output):\n'
               b'    """Original complete closure admission, then a VALID prediction handoff only."""\n'
               + prefix + b'    return legacy.load().admit_closed_prediction(folder, result, invocation, output)\n\n\n')
    main = b'def main():\n'
    need(raw.count(main) == 1 and b'def custody(' not in raw, 'One new distinct custody entry')
    result = raw.replace(main, custody + main, 1)
    parse = b'    args = p.parse_args()\n'
    parser = (b"    handoff = sub.add_parser('custody')\n"
              b"    for name in ('owner', 'output'):\n"
              b"        handoff.add_argument('--' + name, type=Path, required=True)\n"
              b"    handoff.add_argument('--result-sha256', required=True)\n")
    need(result.count(parse) == 1, 'One retained argument parsing site')
    result = result.replace(parse, parser + parse, 1)
    branch = b"    else:\n        result = grade(args.owner, args.result_sha256, args.target, args.evaluator, args.output, args.scratch_bytes)\n"
    new_branch = (b"    elif args.action == 'custody':\n"
                  b"        result = custody(args.owner, args.result_sha256, args.output)\n" + branch)
    need(result.count(branch) == 1, 'One unchanged retained grade dispatch')
    return result.replace(branch, new_branch, 1)


def derive_owner_sources(originals, manifest, legacy_raw):
    """Exact occurrence-checked source derivation, not runtime monkeypatching."""
    need(type(originals) is dict and set(originals) == OWNER_FILES
         and manifest.get('schema') == 'smc_aggregate_owner_source_v1'
         and set(manifest.get('files', {})) == OWNER_FILES, 'Exact original owner member set')
    for name, raw in originals.items():
        need(pin(raw) == descriptor(manifest['files'][name]), 'Unchanged authenticated original before derivation')
    derived, changes = dict(originals), []
    for name, pairs in PATCHES.items():
        raw = originals[name]
        for before, after in pairs:
            old, new = before.encode(), after.encode()
            need(raw.count(old) == 1 and raw.count(new) == 0, 'One exact source occurrence: ' + name)
            raw = raw.replace(old, new, 1)
        derived[name] = raw
        changes.append({'file': name, 'original': pin(originals[name]), 'derived': pin(raw),
                        'replacements': [{'before': a, 'after': b, 'occurrences': 1} for a, b in pairs]})
    need(type(legacy_raw) is bytes and 0 < len(legacy_raw) <= 65536, 'Bounded explicit reference loader')
    derived['legacy.py'] = legacy_raw
    changes.append({'file': 'legacy.py', 'original': pin(originals['legacy.py']),
                    'derived': pin(legacy_raw), 'replacement': 'source-selected validation_legacy.py'})
    derived['runner.py'] = derive_custody_runner(originals['runner.py'])
    changes.append({'file': 'runner.py', 'original': pin(originals['runner.py']),
                    'derived': pin(derived['runner.py']),
                    'derivation': 'append custody with unchanged grade proof prefix through validate_aggregate_completion; append custody CLI; execute and grade unchanged'})
    return derived, changes


def planned_sources(repository_root, component_root, expected_component=None):
    repository_root, component_root = canonical(repository_root), canonical(component_root)
    component_pin, component, component_bodies = component_sources(component_root, expected_component)
    # This compiler itself must be the one frozen in the component source.
    need(source(Path(__file__).absolute()) == component_bodies['validation_overlay.py'],
         'Executing compiler equals source-selected compiler')
    original_root = repository_root / OWNER_REL
    original_raw = source(original_root / 'SOURCE.json', OWNER_SOURCE)
    manifest = decode(original_raw)
    need(set(manifest['files']) == OWNER_FILES, 'Exact retained owner roster')
    originals = {name: source(original_root / name, expected) for name, expected in manifest['files'].items()}
    bodies, changes = derive_owner_sources(originals, manifest, component_bodies['validation_legacy.py'])
    composition = {'schema': 'smc_validation_owned_owner_composition_v1',
        'repository_root': str(repository_root), 'component_root': str(component_root),
        'component_source': component_pin, 'episode': component['files']['validation_episode.py'],
        'retained_owner_source': OWNER_SOURCE}
    bodies['COMPOSITION.json'] = encode(composition)
    overlay = {'schema': 'smc_validation_owned_owner_overlay_v1',
        'files': {name: pin(raw) for name, raw in sorted(bodies.items())},
        'retained_owner_source': OWNER_SOURCE, 'component_source': component_pin,
        'phases': list(PHASES), 'phase_roles': {phase: 'B' for phase in PHASES},
        'material_access': 'paper_data_author_code_and_weights',
        'outcome': 'restricted_validation_reference', 'pair_seconds': 11280, 'derivations': changes}
    bodies['SOURCE.json'] = encode(overlay)
    return bodies, composition


def verify_overlay(owner_root):
    """Recompute the exact derivation before runtime admission; read source only."""
    owner_root = canonical(owner_root)
    composition = decode(source(owner_root / 'COMPOSITION.json'))
    need(type(composition) is dict and set(composition) == {'schema', 'repository_root', 'component_root',
         'component_source', 'episode', 'retained_owner_source'}
         and composition['schema'] == 'smc_validation_owned_owner_composition_v1'
         and composition['retained_owner_source'] == OWNER_SOURCE, 'Exact reference owner composition')
    bodies, expected = planned_sources(composition['repository_root'], composition['component_root'],
                                      descriptor(composition['component_source']))
    need(composition == expected, 'Reference episode and component source are joined')
    need({p.name for p in owner_root.iterdir()} == set(bodies), 'Closed physical owner source inventory')
    for name, raw in bodies.items():
        need(source(owner_root / name, pin(raw)) == raw, 'Only exact allowed owner source derivations')
    return {'source': pin(bodies['SOURCE.json']), 'composition': composition}


def build_overlay(repository_root, output, *, max_bytes):
    repository_root, output = canonical(repository_root), canonical(output)
    need(type(max_bytes) is int and max_bytes > 0 and not output.exists() and output.parent.is_dir(),
         'Fresh output under an existing parent and finite precharged cap')
    roots = (repository_root, HERE)
    need(not any(output.is_relative_to(root) or root.is_relative_to(output) for root in roots)
         and not any((p / '.git').exists() for p in (output.parent, *output.parent.parents)),
         'External private compilation outside original source and Git')
    bodies, composition = planned_sources(repository_root, HERE)
    total = sum(len(raw) for raw in bodies.values())
    need(total <= max_bytes, 'Complete derived source precharged before any mkdir')
    folder = output / OWNER_REL
    folder.mkdir(parents=True, mode=0o700)
    for name, raw in sorted(bodies.items()):
        fd = os.open(folder / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o444)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw)
            os.fchmod(stream.fileno(), 0o444)
            stream.flush()
            os.fsync(stream.fileno())
    fd = os.open(folder, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    result = verify_overlay(folder)
    return {'schema': 'smc_validation_owned_owner_overlay_materialization_v1',
        'path': str(folder), 'source': result['source'], 'component_source': composition['component_source'],
        'files': len(bodies), 'bytes': total, 'phases': list(PHASES),
        'phase_roles': {phase: 'B' for phase in PHASES}, 'material_access': 'paper_data_author_code_and_weights',
        'unchanged_owner_primitives': sorted(OWNER_FILES - set(PATCHES) - {'legacy.py', 'runner.py'}),
        'transport_modified': False, 'runtime_monkeypatching': False,
        'execution_performed': False, 'native_runtime_qualified': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--max-bytes', type=int, required=True)
    args = parser.parse_args()
    print(encode(build_overlay(args.repository_root, args.output, max_bytes=args.max_bytes)).decode(), end='')
