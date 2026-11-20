"""One generated production-callsite regression; no Docker or scientific data.

Run with a fresh canonical external ARTIFACT_DIR. The public fixture is entirely
synthetic. A private campaign may subclass fixtures() to add authenticated saved
metadata without changing production globals or publishing that metadata.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = {'AttachStderr': False, 'AttachStdin': False, 'AttachStdout': False,
            'Domainname': '', 'Hostname': '', 'Image': '', 'OpenStdin': False,
            'StdinOnce': False, 'Tty': False}
ACTIVE = False
HOST = None
HOST_PIN = None
ARTIFACT_ROOT = None
OBSERVATIONS = {'fixture_count': 0, 'admitted_cases': 0, 'rejected_cases': 0,
                'production_inspect_image_calls': 0, 'saved_original_record_calls': 0}


def guard(event, args):
    if not ACTIVE:
        return
    if event in {'subprocess.Popen', 'os.fork', 'os.forkpty', 'os.exec', 'os.posix_spawn',
                 'os.system', 'os.kill', 'os.killpg', 'resource.setrlimit',
                 'socket.connect', 'socket.bind', 'socket.getaddrinfo'}:
        raise AssertionError('Native operation forbidden in image metadata control: ' + event)
    if event == 'import' and args[0].split('.')[0] in {
            'numpy', 'scipy', 'sklearn', 'h5py', 'torch', 'pandas', 'pynwb', 'hdmf'}:
        raise AssertionError('Scientific import forbidden in image metadata control')


sys.addaudithook(guard)


def initialize():
    global ARTIFACT_ROOT
    if ARTIFACT_ROOT is not None:
        return
    value = os.environ.get('ARTIFACT_DIR')
    if not value:
        raise ValueError('Fresh external ARTIFACT_DIR required')
    p = Path(value)
    if not p.is_absolute() or str(p) != value or '..' in p.parts or p.resolve() != p:
        raise ValueError('Canonical absolute ARTIFACT_DIR required')
    if os.path.lexists(p) or not p.parent.is_dir():
        raise ValueError('ARTIFACT_DIR must not exist and its parent must exist')
    sources = [ROOT / n for n in ('runtime', 'adapter', 'controls')]
    if any(p.is_relative_to(s) or s.is_relative_to(p) for s in sources):
        raise ValueError('ARTIFACT_DIR must be disjoint from source directories')
    if any((a / '.git').exists() for a in (p.parent, *p.parent.parents)):
        raise ValueError('ARTIFACT_DIR must be outside every Git worktree')
    p.mkdir(mode=0o700)
    ARTIFACT_ROOT = p


def host():
    global HOST, HOST_PIN
    if HOST is None:
        p = ROOT / 'runtime/historical_grade.py'
        raw = p.read_bytes()
        HOST_PIN = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
        HOST = types.ModuleType('_generated_historical_image_policy')
        HOST.__file__ = str(p)
        exec(compile(raw, str(p), 'exec'), HOST.__dict__)
    return HOST


def closed_record():
    return {'pid': 123, 'returncode': 0, 'errors': [], 'stdout': '', 'stderr': '',
            'cleanup': {'cleanup_complete': True, 'reaped': True, 'group_absence_observed': True,
                        'error': None, 'pid': 123, 'returncode': 0},
            'capture': {'all_eof_observed': True, 'storage_truncated': False,
                        'read_ceiling_exhausted': False, 'closed_without_eof': False,
                        'stream_close_errors': []}}


class ImagePolicyControls(unittest.TestCase):
    def setUp(self):
        global ACTIVE
        initialize()
        ACTIVE = True
        self.addCleanup(self.release_guard)
        self.host = host()

    @staticmethod
    def release_guard():
        global ACTIVE
        ACTIVE = False

    def fixtures(self):
        config = {'Cmd': ['python3'], 'Entrypoint': [''], 'Env': ['FIXTURE=generated'],
                  'Labels': {'generated.example/image': 'synthetic'}, 'OnBuild': None,
                  'User': '65534:65534', 'Volumes': None, 'WorkingDir': '/work'}
        image = {'Id': self.host.IMAGE_ID, 'Os': 'linux', 'Architecture': 'arm64',
                 'Parent': 'sha256:' + '1' * 64, 'RootFS': {'Type': 'layers', 'Layers': ['sha256:' + '2' * 64]},
                 'Size': 4096, 'Config': config}
        provenance = {'image': image, 'allowed_omitted_config_defaults': dict(DEFAULTS),
                      'expected_semantic_config': {**config, **DEFAULTS}}
        return [{'name': 'generated_public', 'provenance': provenance,
                 'witness': {**copy.deepcopy(image), 'Config': {**copy.deepcopy(config), **DEFAULTS}},
                 'record': closed_record(), 'saved_original': False}]

    def invoke(self, fixture, actual, provenance=None, original=False):
        selected = copy.deepcopy(fixture['record'])
        if not original:
            selected['stdout'] = json.dumps(actual, sort_keys=True, allow_nan=False)
        else:
            self.assertEqual(json.loads(selected['stdout']), actual)
            OBSERVATIONS['saved_original_record_calls'] += 1
        test = self
        class Owner:
            def cli(owner, args, deadline, label):
                test.assertEqual(args[:3], ['image', 'inspect', '--format'])
                test.assertEqual(args[-1], test.host.IMAGE_ID)
                test.assertEqual(label, 'historical_image_identity')
                test.assertEqual(deadline, 123.0)
                OBSERVATIONS['production_inspect_image_calls'] += 1
                return selected
        self.host.inspect_image(Owner(), fixture['provenance'] if provenance is None else provenance, 123.0)

    def test_exact_config_default_omissions_and_strict_image_identity(self):
        for fixture in self.fixtures():
            OBSERVATIONS['fixture_count'] += 1
            provenance = fixture['provenance']
            self.assertEqual(provenance['allowed_omitted_config_defaults'], DEFAULTS)
            self.assertEqual(set(provenance['expected_semantic_config']),
                             set(provenance['image']['Config']) | set(DEFAULTS))
            if fixture['saved_original']:
                with self.subTest(fixture=fixture['name'], case='saved_original_exact_record'):
                    self.invoke(fixture, fixture['witness'], original=True)
                    OBSERVATIONS['admitted_cases'] += 1
            # Every subset includes all-present, all-nine-omitted and mixed cases.
            keys = sorted(DEFAULTS)
            for mask in range(1 << len(keys)):
                actual = copy.deepcopy(fixture['witness'])
                actual['Config'] = copy.deepcopy(provenance['expected_semantic_config'])
                for index, key in enumerate(keys):
                    if mask & (1 << index): del actual['Config'][key]
                with self.subTest(fixture=fixture['name'], omitted_mask=mask):
                    self.invoke(fixture, actual)
                    OBSERVATIONS['admitted_cases'] += 1
            full = copy.deepcopy(fixture['witness'])
            full['Config'] = copy.deepcopy(provenance['expected_semantic_config'])
            negatives = []
            for key, expected in DEFAULTS.items():
                bad_values = [True, 0, 0.0, '', None, []] if expected is False else ['changed', False, 0, None, []]
                for index, bad in enumerate(bad_values):
                    value = copy.deepcopy(full); value['Config'][key] = bad
                    negatives.append((key + '/wrong_type_or_value/' + str(index), value))
            for key, bad in [('Cmd', ['changed']), ('Entrypoint', ['/changed']), ('Env', ['CHANGED=1']),
                             ('Labels', {'unexpected': 'changed'}), ('WorkingDir', '/changed'),
                             ('User', '0:0'), ('OnBuild', []), ('Volumes', {})]:
                value = copy.deepcopy(full); value['Config'][key] = bad
                negatives.append(('meaningful_Config/' + key, value))
            value = copy.deepcopy(full); value['Config']['Undeclared'] = None
            negatives.append(('undeclared_Config_field', value))
            value = copy.deepcopy(full); del value['Config']['WorkingDir']
            negatives.append(('missing_meaningful_Config_field', value))
            for key, bad in [('Id', 'sha256:' + '3' * 64), ('Os', 'other'), ('Architecture', 'amd64'),
                             ('Parent', 'sha256:' + '4' * 64), ('RootFS', {'Type': 'layers', 'Layers': []}),
                             ('Size', full['Size'] + 1), ('Size', float(full['Size']))]:
                value = copy.deepcopy(full); value[key] = bad
                negatives.append(('immutable_image/' + key + '/' + type(bad).__name__, value))
            value = copy.deepcopy(full); value['UnexpectedTopLevel'] = False
            negatives.append(('undeclared_image_field', value))
            value = copy.deepcopy(full); value['Config'] = []
            negatives.append(('Config_wrong_type', value))
            for label, actual in negatives:
                with self.subTest(fixture=fixture['name'], reject=label), self.assertRaises((ValueError, TypeError)):
                    self.invoke(fixture, actual)
                OBSERVATIONS['rejected_cases'] += 1


def finish(result, saved_input_pins=None):
    receipt = {'schema': 'smc-historical-image-policy-controls/v1', 'testsRun': result.testsRun,
               'failures': len(result.failures), 'errors': len(result.errors), 'skipped': len(result.skipped),
               'successful': result.wasSuccessful(), 'observations': OBSERVATIONS,
               'host_source': HOST_PIN, 'saved_input_pins': saved_input_pins or {},
               'cumulative_generated_fixture_bytes': 0, 'receipt_bytes': 0,
               'fixture_body_writes': 0, 'native_or_scientific_execution_qualified': False,
               'explicit_boundary': 'Saved/generated Docker CLI responses; actual production inspect_image called unchanged',
               'old_eleven_method_replays': 0}
    for _ in range(8):
        raw = (json.dumps(receipt, sort_keys=True, indent=2) + '\n').encode()
        if len(raw) == receipt['receipt_bytes']: break
        receipt['receipt_bytes'] = receipt['cumulative_generated_fixture_bytes'] = len(raw)
    (ARTIFACT_ROOT / 'CONTROL_RESULT.json').write_bytes(raw)
    print(json.dumps(receipt, sort_keys=True))
    return 0 if result.wasSuccessful() else 1


def main():
    initialize()
    program = unittest.main(exit=False)
    return finish(program.result)


if __name__ == '__main__':
    raise SystemExit(main())
