"""Generated relocation checks; invoked only after CI authenticates every member."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types


def main():
    # The outside CI bootstrap provides the already authenticated byte mapping.
    bodies = globals().get('_SOURCE_BODIES')
    manifest_body = globals().get('_MANIFEST_BODY')
    if not isinstance(bodies, dict) or not isinstance(manifest_body, bytes):
        raise RuntimeError('invoke through the manifest-authenticating CI bootstrap')
    with tempfile.TemporaryDirectory(prefix='ccep public relocation ') as tmp:
        root = Path(tmp) / 'component with spaces'
        root.mkdir()
        for name, body in bodies.items():
            (root / name).write_bytes(body)
        (root / 'COMPONENT_SOURCE.json').write_bytes(manifest_body)
        validator = types.ModuleType('validate_metadata')
        validator.__file__ = str(root / 'validate_metadata.py')
        exec(compile(bodies['validate_metadata.py'], validator.__file__, 'exec'), validator.__dict__)
        previous = sys.modules.get('validate_metadata')
        sys.modules['validate_metadata'] = validator
        try:
            fixtures = types.ModuleType('invented_fixture_definitions')
            fixtures.__file__ = str(root / 'test_metadata.py')
            exec(compile(bodies['test_metadata.py'], fixtures.__file__, 'exec'), fixtures.__dict__)
            binding, packets = fixtures.fixture()
        finally:
            if previous is None:
                sys.modules.pop('validate_metadata', None)
            else:
                sys.modules['validate_metadata'] = previous
        binding_path = root / 'invented binding.json'
        binding_path.write_text(json.dumps(binding), encoding='utf-8')
        packet_paths = []
        for i, packet in enumerate(packets):
            path = root / ('invented packet '+str(i)+'.json')
            path.write_text(json.dumps(packet), encoding='utf-8')
            packet_paths.append(str(path))
        report = root / 'invented report.json'
        argv = [sys.executable, '-I', '-S', '-B', str(root / 'validate_metadata.py'),
                '--binding', str(binding_path), '--packets', *packet_paths, '--report', str(report)]
        env = {'PATH': os.environ.get('PATH', ''), 'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONHASHSEED': '0'}
        result = subprocess.run(argv, cwd=root, env=env, capture_output=True, text=True, timeout=10, check=True)
        result_summary = json.loads(result.stdout)
        observed = json.loads(report.read_text(encoding='utf-8'))
        assert result_summary == {'five_recordings_inspected': True, 'scientifically_qualified': False}
        assert len(observed['recordings_in_operator_order']) == 5
        assert observed['recordings_in_operator_order'][0]['channels'][0]['segments'][0]['declared_native_sample_end_exclusive'] == '9007199254740998'
        before = report.read_bytes()
        result = subprocess.run(argv, cwd=root, env=env, capture_output=True, text=True, timeout=10)
        assert result.returncode != 0 and report.read_bytes() == before
        # A duplicated recording cannot replace an omitted member of the full roster.
        Path(packet_paths[-1]).write_text(json.dumps(packets[0]), encoding='utf-8')
        argv[-1] = str(root / 'must-not-exist.json')
        result = subprocess.run(argv, cwd=root, env=env, capture_output=True, text=True, timeout=10)
        assert result.returncode != 0 and not Path(argv[-1]).exists()
        print(json.dumps({'generated_relocation_checks': 3, 'native_runs': 0, 'authentic_packets': 0}))


if __name__ == '__main__':
    main()
