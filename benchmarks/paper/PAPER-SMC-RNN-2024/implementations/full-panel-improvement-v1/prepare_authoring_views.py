#!/usr/bin/env python3
"""Prepare the two SMC pretest development views; never run an author or model.

Trusted material-operator entry point. The accepted exporter owns admission and
copying. This bridge binds its two outputs for a later controlled authoring
process; it neither launches that process nor attests to its isolation.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import stat
import types

SOURCE_SHA = '2da9e6ee5c8cc47fd5440a3edbc3eeb275020359f6f7fd5d456c6f86d2c96b4f'
PAIR_SHA = 'c4ae0e6509fc74bd68561b0031aae38bf74a08c5f053718bd9349effd9720b22'
CONDITIONS = ('paper_data', 'paper_data_author_code_and_weights')
MAX_BYTES = 32 * 1024**2
RECEIPT_CAP = 65536
EXPECTED = {
    'paper_data': {'manifest_bytes': 2724, 'manifest_sha256': 'c3330dc5af3a696e5e0773201b31ed72244e07e317622041ec75a76b2a131554', 'files': 14, 'bytes': 13335439},
    'paper_data_author_code_and_weights': {'manifest_bytes': 11060, 'manifest_sha256': '198a94b9e26858bf163d3df600932f3837235222d18c4cbbdaceb4b27c6cb50d', 'files': 54, 'bytes': 17047578},
}


def load_api(repository_root, component_root):
    """Execute the authenticated source snapshot, avoiding a second path read."""
    path = Path(component_root).absolute() / 'benchmark.py'
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('Unlinked accepted component required')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as handle:
        before = os.fstat(handle.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size != 43093:
            raise ValueError('Exact accepted full-panel source required')
        body = handle.read(43094)
        after = os.fstat(handle.fileno())
    keys = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
    if (any(getattr(before, k) != getattr(after, k) for k in keys)
            or hashlib.sha256(body).hexdigest() != SOURCE_SHA):
        raise ValueError('Accepted full-panel source changed')
    module = types.ModuleType('_smc_pretest_accepted_exporter')
    module.__file__ = str(path)
    exec(compile(body, str(path), 'exec'), module.__dict__)
    return module.FullPanelAPI(repository_root, component_root)


def prepare_views(api, pair_path, output, *, max_bytes, reserve_bytes):
    """Exactly two existing development calls, without inference release."""
    if (type(max_bytes) is not int or max_bytes != MAX_BYTES
            or type(reserve_bytes) is not int or reserve_bytes < 0):
        raise ValueError('Selected 32 MiB complete material cap and finite reserve required')
    output = Path(output).absolute()
    if '..' in output.parts or any(p.is_symlink() for p in (output, *output.parents)):
        raise ValueError('Unlinked canonical output required')
    output = api._outside(output, Path(pair_path).parent)
    prospective = sum(row['bytes'] for row in EXPECTED.values()) + RECEIPT_CAP
    if prospective > max_bytes or shutil.disk_usage(output.parent).free < max_bytes + reserve_bytes:
        raise ValueError('Complete paired preparation exceeds capacity')
    # Fresh output is also the once-only claim. Preserve any partial view on
    # failure; do not silently retry or erase the first condition.
    output.mkdir(mode=0o700)
    views = {}
    for condition in CONDITIONS:
        record = api.prepare_development_view(pair_path, PAIR_SHA, api.task_path,
            api.task_sha256, condition, output / condition, max_bytes=max_bytes)
        manifest = output / condition / 'development_manifest.json'
        expected = EXPECTED[condition]
        saved, digest = api.read_json(manifest, expected['manifest_sha256'])
        if (saved != record or manifest.stat().st_size != expected['manifest_bytes']
                or len(record['files']) + 1 != expected['files']
                or sum(row['bytes'] for row in record['files']) + expected['manifest_bytes'] != expected['bytes']
                or record['excluded_paths'] != ['inputs/mc_maze/test/eval_input_20ms.h5']
                or record['test_input_delivered'] is not False):
            raise ValueError('Development output differs from the selected metadata plan')
        # prepare_development_view has already authenticated each staged file.
        # Do not repeat complete pair/HDF5 admission merely to make a receipt.
        views[condition] = {'root': str(output / condition),
            'manifest_path': str(manifest), 'manifest_sha256': digest,
            'files': expected['files'], 'bytes': expected['bytes']}
    receipt = {'schema': 'smc_paired_pretest_authoring_materials_v1',
        'task_id': 'PAPER-SMC-RNN-2024',
        'inference_condition_id': 'full_panel_offline_transductive_v1',
        'pair_sha256': PAIR_SHA, 'exporter_sha256': SOURCE_SHA,
        'task_sha256': api.task_sha256, 'views': views,
        'material_preparation_only': True, 'test_input_delivered': False,
        'authoring_process_started': False, 'authoring_resources_measured': False,
        'pre_test_authoring_isolation_verified': False,
        'candidate_or_model_execution': False, 'AI_result': False,
        'next_boundary': 'Only the matching development root may enter each separately controlled authoring process. Freeze both methods, assets, seeds and adaptation procedures before either TEST input release. Actual full-panel adaptation may occur after freeze.'}
    body = (json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False) + '\n').encode()
    if len(body) > RECEIPT_CAP:
        raise ValueError('Bounded paired receipt required')
    api.io.write_new_json(output / 'AUTHORING_HANDOFF.json', receipt)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', required=True, type=Path)
    args = parser.parse_args()
    if not args.request.is_file() or args.request.stat().st_size > 65536:
        raise ValueError('Bounded trusted operator request required')
    request = json.loads(args.request.read_text())
    if set(request) != {'repository_root', 'component_root', 'pair_path', 'output', 'max_bytes', 'reserve_bytes'}:
        raise ValueError('Exact trusted preparation arguments required')
    api = load_api(request.pop('repository_root'), request.pop('component_root'))
    print(json.dumps(prepare_views(api, **request), indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
