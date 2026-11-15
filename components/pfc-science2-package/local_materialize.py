"""Local-only adapter for the accepted PFC materializer; no Docker or science.

The unchanged registry-reference materializer remains available. This
adapter deliberately admits *local config IDs*, solely for separately admitted
classic-builder builds. It does not claim a registry digest or image readiness.
"""
from pathlib import Path
import hashlib
import json
import re
import sys
import types

BASE_PATH = Path(__file__).absolute().with_name('materialize.py')
BASE_BYTES = 10878
BASE_SHA256 = 'd674975d9e79ffc21a54965206e1dc3d5b5050524123e33a8cca524c992eb755'
NOTICE_PINS = {
    'ATTRIBUTION.md': (3143, 'b76176457083b74790bdd42889e5d14401f6e8898533e61c2fe5e222392a6c9c'),
    'PUBLIC_LINEAGE.json': (3783, 'ddd3152dd547a80a31708a6f350bf817c49b38fb8f7ec85a4cee1b36c907e6d3'),
    'DANDI_TERMS.md': (3347, '99eea9766e4f54fb03371ef418a642d08f6641c07f2f25fad7d71d2ce66edff9'),
    'RELEASE_NOTES.md': (3022, '20dae021788290c317b0e44101ac8a32bf0091547b7c14d2abc5bfadc173a755'),
}
PUBLIC_MANIFEST_PIN = (4131, 'b8b44a37639fe46d38ceb5dfc5a79a54578035ac7eba461b5c0e1a6dc6fedf21')
LOCAL_ID = re.compile(r'sha256:[0-9a-f]{64}\Z')
SCHEMA = 'PFC_SCIENCE2_LOCAL_CONFIG_MATERIALIZE_V1'
SOURCE_ROOT = Path(__file__).absolute().parent


def load_base():
    # The imported code is an exact previously reviewed stdlib-only source body.
    import os
    import stat
    for p in (BASE_PATH, *BASE_PATH.parents):
        if p.is_symlink():
            raise ValueError('base source alias')
    before = BASE_PATH.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size != BASE_BYTES:
        raise ValueError('base source extent/type')
    stamp = lambda s: (s.st_dev, s.st_ino, s.st_mode, s.st_nlink, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
    fd = os.open(BASE_PATH, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        if stamp(before) != stamp(os.fstat(stream.fileno())):
            raise ValueError('base source opened identity')
        body = stream.read(BASE_BYTES + 1)
        after_fd = os.fstat(stream.fileno())
    if (len(body), hashlib.sha256(body).hexdigest()) != (BASE_BYTES, BASE_SHA256):
        raise ValueError('base source pin')
    if not stamp(before) == stamp(after_fd) == stamp(BASE_PATH.lstat()):
        raise ValueError('base source changed')
    module = types.ModuleType('_pfc_local_materializer_base')
    module.__file__ = str(BASE_PATH)
    exec(compile(body, str(BASE_PATH), 'exec'), module.__dict__)
    return module


def disjoint(module, *paths):
    for index, left in enumerate(paths):
        for right in paths[index + 1:]:
            module.require(left != right and left not in right.parents and right not in left.parents,
                           'all release, source, staging and output roots must be disjoint')


def materialize_local(request, module, *, reader=None, notice_pins=None, manifest_pin=None):
    """Test injection is internal only; CLI always uses all production pins."""
    module.require(type(request) is dict and set(request) == {
        'schema', 'execution_selected', 'release_root', 'asset_stage', 'output_root',
        'agent_image_id', 'verifier_image_id'}, 'exact local request fields')
    module.require(request['schema'] == SCHEMA and request['execution_selected'] is True,
                   'explicit selected local materialization')
    for role in ('agent_image_id', 'verifier_image_id'):
        module.require(type(request[role]) is str and LOCAL_ID.fullmatch(request[role]) is not None,
                       'full local image config ID, not tag or registry reference')
    for role in ('release_root', 'asset_stage', 'output_root'):
        module.require(type(request[role]) is str, 'root path string')
    release = module.plain_path(Path(request['release_root']))
    stage = module.plain_path(Path(request['asset_stage']), exists=False)
    output = module.plain_path(Path(request['output_root']), exists=False)
    source = module.plain_path(module.HERE)
    module.require(not stage.exists() and not output.exists(), 'fresh stage and task')
    own_source = module.plain_path(SOURCE_ROOT)
    disjoint(module, release, stage, output)
    # Adjacent or nested source roots are legitimate; every input/output root
    # must still remain separate from both protected source trees.
    for mutable in (release, stage, output):
        for protected in (source, own_source):
            disjoint(module, mutable, protected)
    # Validate target taxonomy before copying anything.
    module.require(output.parts[-4:] == ('tasks', 'life-sciences', 'neuroscience', module.TASK_SLUG),
                   'exact task taxonomy')
    reader = module.Reads() if reader is None else reader
    pins = NOTICE_PINS if notice_pins is None else notice_pins
    manifest_pin = PUBLIC_MANIFEST_PIN if manifest_pin is None else manifest_pin
    module.require(tuple(pins) == module.NOTICE_NAMES, 'exact notice order')
    expected = dict(module.ASSETS, **pins)
    module.require(module.file_roster(release) == set(expected) | {'PUBLIC_ASSET_MANIFEST.json'},
                   'complete nine-file released namespace')
    # Authenticate all nine before the first write; the manifest is provenance,
    # while only the eight selected assets/notices enter materializer staging.
    reader.read(release / 'PUBLIC_ASSET_MANIFEST.json', 262144, manifest_pin)
    bodies = {name: reader.read(release / name, 8388608, pin) for name, pin in expected.items()}
    stage.mkdir(mode=0o700)
    for name, body in sorted(bodies.items()):
        dest = stage / name
        with dest.open('xb') as stream:
            stream.write(body)
        dest.chmod(0o400)
    stage.chmod(0o500)
    # A private module instance receives the one deliberate syntax substitution.
    # All source/asset/namespace/copy/scientific behavior stays in the accepted
    # implementation. Never mutate its source file or public import namespace.
    module.IMAGE = LOCAL_ID
    internal = {
        'schema': 'PFC_SCIENCE2_MATERIALIZE_V1', 'asset_root': str(stage),
        'output_root': str(output), 'agent_image': request['agent_image_id'],
        'verifier_image': request['verifier_image_id'],
        'notices': [{'name': name, 'bytes': pin[0], 'sha256': pin[1]} for name, pin in pins.items()],
    }
    result = module.materialize(internal, reader=reader)
    result['schema'] = 'PFC_SCIENCE2_LOCAL_CONFIG_PACKAGE_V1'
    result['local_config_ids_only'] = True
    result['registry_reference_or_portability_claim'] = False
    result['classic_build_required_before_native_harbor'] = True
    result['base_source_sha256'] = BASE_SHA256
    result['asset_stage'] = str(stage)
    result['release_manifest_authenticated_not_staged'] = True
    result['source_asset_and_output_roots_disjoint'] = True
    result['staged_files'] = [{'path': name, 'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}
                              for name, body in sorted(bodies.items())]
    return result


def main(argv):
    if len(argv) != 3 or not argv[1].isdigit() or not re.fullmatch(r'[0-9a-f]{64}', argv[2]):
        raise ValueError('usage: local_materialize.py REQUEST_PATH EXACT_BYTES SHA256')
    module = load_base()
    reader = module.Reads()
    reader.bytes = BASE_BYTES
    raw = reader.read(Path(argv[0]), 65536, (int(argv[1]), argv[2]))
    result = materialize_local(module.decode(raw), module, reader=reader)
    sys.stdout.buffer.write(module.encode(result))
    sys.stdout.buffer.flush()


if __name__ == '__main__':
    main(sys.argv[1:])
