"""Create a frozen portable request; no Docker, authentic body or model execution.

The owner supplies authorized existing assets and pinned host/runtime facts.
This command authenticates this source lock only. Assets are authenticated by
the separately selected owner before its first container is created.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).absolute().parent))
from deployment import (absolute, decode, read_pin, descriptor,
    authenticate_source_graph, validate_request_metadata)
from profile import PROFILE, IMAGE, PACKET, SCIENCE, ASSISTANCE, OFFICIAL, RUNTIME_FILES, EXECUTION_SCOPE


def body(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n').encode()


def put(path, raw):
    if len(raw) > 1048576:
        raise ValueError('bounded ordinary request metadata')
    fd = os.open(absolute(str(path)), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    except BaseException:
        # Never erase a partial immutable request or replace an earlier attempt.
        raise
    return {'path': str(path), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def construct(config, lock_pin, here, policy_path):
    if set(config) != {'schema', 'attempt', 'deployment', 'assets', 'programs', 'compatibility'} or config['schema'] != 'PFC_PORTABLE_DEPLOYMENT_V1':
        raise ValueError('complete owner deployment configuration')
    lock = decode(read_pin(lock_pin))
    pins = {row['relative_path']: {'path': str(here.parent / row['relative_path']),
            'bytes': row['bytes'], 'sha256': row['sha256']} for row in lock['files']}
    assets = config['assets']
    if set(assets) != {'packet', 'paper.xml', 'category_matching.py', 'LICENSE', 'source_input_selection'}:
        raise ValueError('all five owner-provided assets are required')
    p = {'schema': 'PFC_PORTABLE_PARTICIPANT_POLICY_V1', 'profile': PROFILE, 'image': IMAGE,
         'packet': assets['packet'], 'source_input_selection': assets['source_input_selection'],
         'scorer_sources': {name: pins['package/science/' + name] for name in SCIENCE},
         'common_assistance': {name: (assets[name] if name == 'paper.xml' else pins['package/instructions/' + name])
                               for name in ASSISTANCE},
         'additional_B_assistance': {name: assets[name] for name in OFFICIAL},
         'inherited_owner': pins['package/lifecycle_owner.py'],
         'inherited_outer': pins['package/lifecycle_outer.py'],
         'negative_source': pins['package/science/make_negative_submission.py'],
         'assistance_interpretation': 'Method-assisted A; B adds one selected official source/license. Same baseline validates interfaces, not assistance effect.',
         'rights': 'Owner-provided authorized assets; source package grants no new data redistribution rights.'}
    raw = body(p)
    pp = {'path': str(policy_path), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
    r = {'schema': 'PFC_PORTABLE_PARTICIPANT_REQUEST_V1', 'attempt': config['attempt'],
         'deployment': config['deployment'], 'programs': config['programs'], 'policy': pp,
         'source_lock': lock_pin, 'source_files': {name: pins['package/' + name] for name in RUNTIME_FILES},
         'compatibility': config['compatibility'],
         'execution_scope': EXECUTION_SCOPE}
    validate_request_metadata(r, p, here)
    authenticate_source_graph(r, here)
    return p, r


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--config-bytes', required=True, type=int)
    parser.add_argument('--config-sha256', required=True)
    parser.add_argument('--source-lock', required=True)
    parser.add_argument('--source-lock-bytes', required=True, type=int)
    parser.add_argument('--source-lock-sha256', required=True)
    parser.add_argument('--output-directory', required=True)
    args = parser.parse_args()
    config = decode(read_pin({'path': args.config, 'bytes': args.config_bytes, 'sha256': args.config_sha256}))
    lock = {'path': args.source_lock, 'bytes': args.source_lock_bytes, 'sha256': args.source_lock_sha256}
    output = absolute(args.output_directory)
    if output.exists():
        raise FileExistsError('Fresh request directory required: ' + str(output))
    p, r = construct(config, lock, Path(__file__).absolute().parent, output / 'POLICY.json')
    output.mkdir(mode=0o700, exist_ok=False)
    put(output / 'POLICY.json', body(p))
    pin = put(output / 'REQUEST.json', body(r))
    print(json.dumps({'request': pin, 'execution': False, 'assets_read': False}, sort_keys=True))


if __name__ == '__main__':
    main()
