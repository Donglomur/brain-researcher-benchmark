"""Read complete NuCLR owner metadata across canonical JSON serialization.

This additive reader uses the source projection's explicit metadata row order.
It does not rewrite the frozen producer, owner documents, arrays or split IDs.
Metadata validation alone is not authentic asset or scientific qualification.
"""
from __future__ import annotations

import builtins
from copy import deepcopy
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
from types import ModuleType, SimpleNamespace
import uuid

READER_POLICY = 'nuclr_source_metadata_row_order_reader_v2'
PRODUCER_COMMIT = '492095676c8b60f361c3263af8b1d7868b43d782'
PINS = {
    'dependencies.py': 'dd6e5ebb232a69bab341329b825c94b3a1e610a34a990e416de6ccbcb5fa6d1b',
    'native.py': '855355f0f095d53e1ce08059dd9ee3951e015dfeafd84bdc923c366a82ad3cd5',
}
DOCUMENTS = {'COMPLETE.json': 65536, 'native-manifest.json': 32 * 1024**2,
             'joined-panels.json': 32 * 1024**2}


class MetadataError(ValueError):
    pass


def need(value, message):
    if not value:
        raise MetadataError(message)


def read_bound(path, maximum, expected_sha256):
    need(type(expected_sha256) is str and len(expected_sha256) == 64 and
         all(c in '0123456789abcdef' for c in expected_sha256), 'exact expected file SHA256 required')
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    with os.fdopen(fd, 'rb') as handle:
        before = os.fstat(fd)
        identity = lambda x: (x.st_dev, x.st_ino, x.st_size, x.st_mtime_ns, x.st_ctime_ns)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size <= maximum,
             'bounded ordinary unaliased metadata file required')
        body = handle.read(maximum + 1)
        need(len(body) == before.st_size <= maximum and identity(before) == identity(os.fstat(fd)),
             'metadata changed or exceeded extent')
    need(hashlib.sha256(body).hexdigest() == expected_sha256, 'exact metadata file digest differs')
    return body


def decode(body):
    def pairs(rows):
        result = {}
        for key, value in rows:
            need(key not in result, 'duplicate metadata JSON key')
            result[key] = value
        return result
    return json.loads(body, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(MetadataError('nonfinite metadata JSON')))


@lru_cache(maxsize=1)
def frozen_native():
    """Load exact v1 source privately, without changing its global functions."""
    root = Path(__file__).resolve().parents[1] / 'native-inputs-v1'
    namespace = '_nuclr_metadata_reader_' + uuid.uuid4().hex
    original_import = builtins.__import__
    modules = {}
    for filename in ('dependencies.py', 'native.py'):
        path = root / filename
        body = read_bound(path, 1024**2, PINS[filename])
        name = namespace + '.' + path.stem
        module = ModuleType(name)
        module.__file__, module.__package__ = str(path), namespace
        def importer(name, globals=None, locals=None, fromlist=(), level=0):
            if level == 0 and name == 'dependencies':
                return modules['dependencies']
            return original_import(name, globals, locals, fromlist, level)
        module.__dict__['__builtins__'] = dict(vars(builtins), __import__=importer)
        sys.modules[name] = module
        try:
            exec(compile(body, str(path), 'exec'), module.__dict__)
        except BaseException:
            del sys.modules[name]
            raise
        modules[path.stem] = module
    return modules['native']


def restore_source_order(projection):
    """Use the source label-frame row list, never JSON object iteration order."""
    need(type(projection) is dict and type(projection.get('label_map')) is dict and
         type(projection.get('metadata')) is list, 'source projection map and row list required')
    rows = projection['metadata']
    need(all(type(row) is dict and type(row.get('id')) is str and row['id'] for row in rows),
         'explicit source metadata IDs required')
    ordered = [row['id'] for row in rows]
    need(len(ordered) == len(set(ordered)) == len(projection['label_map']) and
         set(ordered) == set(projection['label_map']), 'source metadata order must cover label map exactly once')
    result = deepcopy(projection)
    result['label_map'] = {uid: result['label_map'][uid] for uid in ordered}
    return result


def validate_documents(manifest, joined, completion):
    """Validate supplied documents; this pure boundary does not authenticate files."""
    native = frozen_native()
    need(type(completion) is dict and completion.get('schema') == 'nuclr-native-preparation-complete-v1' and
         completion.get('manifest_sha256') == native.digest(manifest) and
         completion.get('joined_panels_sha256') == native.digest(joined) and
         completion.get('scientific_qualification') is False, 'canonical completion binding differs')
    source, dependencies = native.profile(), native.load_dependencies()
    need(manifest.get('schema') == native.SCHEMA and
         manifest.get('source_profile_sha256') == native.PROFILE_SHA256 and
         manifest.get('order_adoption_sha256') == native.ORDER_ADOPTION_SHA256 and
         manifest.get('split_archive_sha256') == dependencies.splits.ARCHIVE_SHA256 and
         manifest.get('metadata_archive_sha256') == source['metadata_archive']['sha256'] and
         manifest.get('dependencies') == dependencies.pins and
         manifest.get('order_policy') == native.ORDER_POLICY, 'source preparation identities differ')
    sessions = {row['session_id']: row for row in manifest['sessions']}
    assets = {row['source_member']: row for row in manifest['assets']}
    need(len(sessions) == len(manifest['sessions']) == 17 and set(sessions) == set(source['sessions']) and
         len(assets) == len(manifest['assets']) == 257 and
         set(assets) == {row['name'] for row in source['required_members']}, 'complete native population required')
    for sid, definition in source['sessions'].items():
        row = sessions[sid]
        need(row['neurons'] == definition['neurons'] and
             [block['experiment_id'] for block in row['experiments']] == definition['experiments'],
             'complete source experiment or column order differs')
    for row in source['required_members']:
        need(assets[row['name']]['bytes'] == row['bytes'], 'original member byte extent differs')
    neurons = {row['id']: row for row in manifest['neurons']}
    need(len(neurons) == len(manifest['neurons']) == 10153, 'complete source neuron count differs')
    need(type(joined) is list and len(joined) == 9 and all(type(row) is dict for row in joined),
         'all nine original joined projections required')
    projections = [restore_source_order(row['projection']) for row in joined]
    need(native.join_projections(manifest['sessions'], manifest['neurons'], projections) == joined,
         'native panel rows, source order, labels, addresses or topology differ')
    need((manifest.get('subjects'), manifest.get('session_count'), manifest.get('subrecordings'),
          manifest.get('neuron_observations')) == (4, 17, 69, 10153) and
         manifest.get('historical_order_verified') is False and manifest.get('scientific_qualification') is False and
         manifest.get('input_preparation_crops_or_samples') is False and
         all(key in manifest and manifest[key] is None for key in ('downstream_sampler_configuration',
             'downstream_observation_limit_seconds', 'downstream_device_count')),
         'current-release population or scientific claim limit differs')
    need(all(row.get('historical_experiment_order_verified') is False and
             row.get('order_policy') == native.ORDER_POLICY for row in manifest['sessions']) and
         manifest.get('remaining_holds') == [
             'Invalid current E/I inductive split remains refused.',
             'Transductive resample command conflicts with pinned single-split script.',
             'Conference-era artifact equality, native references and protected candidates unqualified.'],
         'frozen producer historical order or remaining holds differ')
    need({(row['projection']['label_level'], row['projection']['panel']) for row in joined
          if not row['topology_audit']['matches_registered_topology']} == {('ei', 'inductive_zero_shot')},
         'original invalid E/I panel disposition differs')
    return SimpleNamespace(manifest=manifest, joined=joined, sessions=sessions, assets=assets, neurons=neurons,
                           receipt_sha256=native.digest(manifest), reader_policy=READER_POLICY)


class NativeInputs:
    """Bind existing complete owner documents to trusted expected file digests.

    This metadata reader never extracts, rewrites or scans scientific arrays.
    Complete asset authentication requires the separate saved-output verifier.
    Individual later block reads retain the unchanged v1 source hash checks.
    """
    def __init__(self, owner_root, *, file_sha256):
        self.root = Path(owner_root)
        need(not os.path.lexists(self.root / 'INCOMPLETE.json'), 'partial preparation refused')
        need(type(file_sha256) is dict and set(file_sha256) == set(DOCUMENTS),
             'all three trusted exact metadata file digests required')
        documents = {name: decode(read_bound(self.root / name, maximum, file_sha256[name]))
                     for name, maximum in DOCUMENTS.items()}
        binding = validate_documents(documents['native-manifest.json'], documents['joined-panels.json'],
                                     documents['COMPLETE.json'])
        self.__dict__.update(vars(binding))
        self.file_sha256 = dict(file_sha256)

    def native_addresses(self, ordered_ids):
        return frozen_native().NativeInputs.native_addresses(self, ordered_ids)

    def read_block(self, session_id, experiment_id, start, stop, *, normalized=True):
        return frozen_native().NativeInputs.read_block(self, session_id, experiment_id, start, stop,
                                                       normalized=normalized)
