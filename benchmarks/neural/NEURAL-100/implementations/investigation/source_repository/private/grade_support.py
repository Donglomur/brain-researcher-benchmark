"""NEURAL100 operator entrypoint: frozen full-panel support admission and grading.

The external operator supplies the expected full export descriptor SHA256.
Only the manifest alias/bootstrap is new; guard v2 and every original member
are preserved. Scientific execution requires separately selected resources.
"""
import argparse
import hashlib
import os
from pathlib import Path
import stat
import types


SUPPORT = 'private/support_consistency'
ENTRY = 'private/grade_support.py'
DOC = 'public/SUPPORT_OPERATOR.md'
PARENT = SUPPORT + '/parent_export_manifest.json'
GUARD = SUPPORT + '/guard.py'
LOCK = SUPPORT + '/SOURCE_LOCK.json'
SOURCE_DESCRIPTOR = 'authoring/delivery-20261105/neural100/support-delivery-v1/delivery_manifest.json'
GRADE_INTERFACE = ('python -I -B private/grade_support.py --package <absolute-package> '
                   '--export-sha256 <operator-pinned-export-sha256> --submission <report> '
                   '--mode grade --packet <absolute-package>/public/input --output <fresh>')
FIXED = {
    GUARD: (12383, 'b2468187d47405e94aed1223fb99261e71846d14ccd8bec2c1d1e9dd8f284562'),
    LOCK: (1818, '6d64f794d07c88cc300cd6751ca3aa6db52d39bdf5be44c8c257d48472d788bf'),
    PARENT: (50538, '6d24f94102c5c3be8a98c38763870edd068915f9f644eff8b2c51a5dd1f3b8b0'),
}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def capture(path, cap):
    """Bounded bootstrap source capture, before executing the pinned companion."""
    path = Path(path).absolute()
    need('..' not in path.parts and all(not p.is_symlink() for p in (path, *path.parents)),
         'Unlinked canonical operator path required')
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


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def hex_digest(value):
    return type(value) is str and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def start(package, expected_export_sha256):
    """Verify source/metadata only. Never open prepared arrays or compute reference."""
    package = Path(package).absolute()
    need(hex_digest(expected_export_sha256), 'Explicit operator-pinned export SHA256 required')
    guard_raw = capture(package / GUARD, 20000)
    need((len(guard_raw), digest(guard_raw)) == FIXED[GUARD], 'Reviewed companion digest')
    guard = types.ModuleType('neural100_delivery_guard')
    guard.__file__ = str(package / GUARD)
    exec(compile(guard_raw, guard.__file__, 'exec'), guard.__dict__)
    package = guard.canonical(package)
    manifest_raw = capture(package / 'DELIVERY_MANIFEST.json', 300000)
    need(digest(manifest_raw) == expected_export_sha256, 'Operator export digest mismatch')
    current = guard.strict(manifest_raw)
    extras = {GUARD: guard_raw}
    for target in (LOCK, PARENT, ENTRY, DOC):
        extras[target] = capture(package / target, 200000)
        if target in FIXED:
            need((len(extras[target]), digest(extras[target])) == FIXED[target], 'Frozen alias/source digest')
    # The installed entrypoint must be this executing source, not a same-named
    # unbound helper from another checkout. External pinning remains essential.
    need(guard.canonical(Path(__file__)) == package / ENTRY, 'Run the installed package entrypoint')
    parent, lock = guard.strict(extras[PARENT]), guard.strict(extras[LOCK])
    need(parent['schema'] == current['schema'] == 'neurobench_delivery_export_v1'
         and parent['task_ids'] == current['task_ids'] == ['NEURAL-100']
         and parent['visibility'] == current['visibility'] == 'all', 'Complete operator export required')
    need(lock['schema'] == 'neural100_support_source_lock_v1' and lock['task_id'] == 'NEURAL-100'
         and parent['source_manifest'] == lock['original_source_descriptor'], 'Frozen parent provenance')
    old_rows = parent['files']
    need(len(old_rows) == 177 and len({r['target'] for r in old_rows}) == 177, 'Full parent177 required')
    wanted = {r['target']: r for r in old_rows}
    for target, raw in extras.items():
        need(target not in wanted, 'Addition must not replace any original member')
        wanted[target] = {'target': target, 'bytes': len(raw), 'sha256': digest(raw),
                          'visibility': 'public' if target == DOC else 'private',
                          'role': 'task_source' if target in (DOC, ENTRY, GUARD) else 'contract_metadata'}
    need(type(current['files']) is list and len(current['files']) == 182
         and len({r['target'] for r in current['files']}) == 182
         and {r['target']: r for r in current['files']} == wanted,
         'Exact177 unchanged members plus five bound additions required')
    need(current['source_manifest']['path'] == SOURCE_DESCRIPTOR
         and type(current['source_manifest']['bytes']) is int and current['source_manifest']['bytes'] > 0
         and hex_digest(current['source_manifest']['sha256']), 'Successor source descriptor binding')
    need(current['interfaces']['grade'] == GRADE_INTERFACE, 'Selected guarded grading interface required')
    for key in ('asset_bindings', 'historical_qualification', 'distribution', 'scope'):
        need(current[key] == parent[key], 'Original identity/scope/history preserved: ' + key)

    # Construct the unchanged frozen loader with a single logical-path alias.
    # Module execution/import isolation stays in its reviewed module() method.
    sources = guard.FrozenSources.__new__(guard.FrozenSources)
    sources.package, sources.lock, sources.raw, sources.modules = package, lock, {}, {}
    for name, pin in lock['files'].items():
        need(not Path(name).is_absolute() and '..' not in Path(name).parts, 'Frozen member path')
        raw = extras[PARENT] if name == 'DELIVERY_MANIFEST.json' else capture(package / name, 200000)
        need(type(pin['bytes']) is int and len(raw) == pin['bytes'] and digest(raw) == pin['sha256'],
             'Frozen original source digest: ' + name)
        sources.raw[name] = raw
    sources.roster = guard.strict(sources.raw['public/ROSTER.json'])
    sources.binding = guard.strict(sources.raw['private/PACKET_BINDING.json'])
    need(sources.binding['task_id'] == 'NEURAL-100' and sources.binding['roster'] == sources.roster,
         'Original public/private roster join')
    return guard, sources


def run_report(guard, sources, value, mode, packet, np):
    """Admission precedes the sole private reference callback in grade mode."""
    contract = sources.module('report_contract')
    if mode == 'admit':
        guard.admit(value, sources.roster, contract, np)
        return {'task_id': 'NEURAL-100', 'status': 'support_consistent_artifact_only',
                'recordings': 47, 'participants': 41, 'conditions': 8,
                'private_reference_calls': 0, 'scientific_qualification_added': False}
    need(mode == 'grade' and packet is not None, 'Explicit grade mode and held packet required')
    packet = guard.canonical(packet)

    def reference():
        adapter, core = sources.module('data_adapter'), sources.module('analysis_core')
        manifest = adapter.load_manifest(packet / 'PREPARED.json', sources.binding['manifest_sha256'])
        return core.analyze(adapter.records(packet, manifest), sources.roster)

    return guard.evaluate(value, sources.roster, reference, sources, np)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--package', required=True, type=Path)
    p.add_argument('--export-sha256', required=True)
    p.add_argument('--submission', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--mode', required=True, choices=('admit', 'grade'))
    p.add_argument('--packet', type=Path)
    a = p.parse_args()
    guard, sources = start(a.package, a.export_sha256)
    output = guard.canonical(a.output)
    need(not os.path.lexists(output) and output.parent.is_dir(), 'Fresh operator output path')
    io = sources.module('artifact_io')
    value = io.decode_json(guard.capture(a.submission, io.MAX_JSON))
    import numpy as np
    result = run_report(guard, sources, value, a.mode, a.packet, np)
    result['operator_entrypoint'] = 'neural100_support_delivery_v1'
    result['export_manifest_sha256'] = a.export_sha256
    result['requires_observed_cli_exit_zero'] = True
    guard.publish(output, result)


if __name__ == '__main__':
    main()
