"""Source-free oracle entrypoint wiring and failure ownership tests."""
import importlib.util
from pathlib import Path
import types
import pytest

HERE = Path(__file__).absolute().parent
spec = importlib.util.spec_from_file_location('devconn_compute_fixture', HERE / 'compute.py')
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)


@pytest.fixture
def harness(tmp_path, monkeypatch):
    calls = []
    output = tmp_path / 'output'; output.mkdir()
    reference, kernel = object(), object()
    def fresh(value, protected):
        calls.append(('fresh', value, protected)); return output
    def write(ref, value, ker, protected):
        assert ref is reference and ker is kernel
        calls.append(('write', value))
    def adapter(*args):
        calls.append(('source', args)); return reference
    def load(route):
        assert route == 'oracle'; calls.append(('load', route)); return adapter
    def json_write(path, value):
        calls.append(('failure', value)); path.write_text('failure')
    writer = types.SimpleNamespace(fresh_output=fresh, write_artifacts=write, json_write=json_write)
    route = types.SimpleNamespace(load_adapter=load)
    monkeypatch.setattr(c, 'load_helpers', lambda: dict(output_writer=writer, run_source_route=route, reporting_kernel=kernel))
    monkeypatch.delenv('OUTPUT_DIR', raising=False)
    return dict(calls=calls, output=output, writer=writer, route=route)


def test_one_oracle_reconstruction_and_one_serialization(harness):
    c.main()
    assert [x[0] for x in harness['calls']] == ['fresh', 'load', 'source', 'write']
    assert harness['calls'][0][1] == '/app/output'
    assert harness['calls'][2][1] == ('/app/data/devconn', '/app/source_manifest.json',
                                    '/app/method_contract.json', '/app/output_schema.json')


def test_custom_output_is_only_output_override(harness, monkeypatch):
    monkeypatch.setenv('OUTPUT_DIR', str(harness['output']))
    c.main()
    assert harness['calls'][0][1] == str(harness['output'])


def test_preflight_failure_does_not_create_marker(harness):
    def fail(*args): raise ValueError('protected')
    harness['writer'].fresh_output = fail
    with pytest.raises(ValueError): c.main()
    assert not harness['calls'] and not (harness['output'] / 'failure_report.json').exists()


@pytest.mark.parametrize('phase', ['load', 'write'])
def test_owned_failure_has_authoritative_marker(harness, phase):
    def fail(*args, **kwargs): raise ValueError('test')
    if phase == 'load': harness['route'].load_adapter = fail
    else: harness['writer'].write_artifacts = fail
    with pytest.raises(ValueError): c.main()
    assert (harness['output'] / 'failure_report.json').read_text() == 'failure'
    assert [x[0] for x in harness['calls']].count('failure') == 1


def test_existing_failure_is_not_overwritten(harness):
    marker = harness['output'] / 'failure_report.json'; marker.write_text('original')
    def fail(*args): raise ValueError('test')
    harness['route'].load_adapter = fail
    with pytest.raises(ValueError): c.main()
    assert marker.read_text() == 'original'


def test_unfrozen_code_fails_before_file_reads(monkeypatch):
    monkeypatch.setattr(c, 'CODE_PINS', {'missing.py': None})
    with pytest.raises(ValueError, match='unfrozen_solution_pin'): c.load_helpers()


@pytest.mark.parametrize('kind', ['changed', 'symlink'])
def test_code_identity_and_symlink_fail(tmp_path, monkeypatch, kind):
    directory = tmp_path / 'code'; directory.mkdir()
    file = directory / 'helper.py'
    if kind == 'changed': file.write_text('raise RuntimeError("must not execute")')
    else: file.symlink_to(tmp_path / 'absent')
    monkeypatch.setattr(c, '__file__', str(directory / 'compute.py'))
    monkeypatch.setattr(c, 'CODE_PINS', {'helper.py': '0' * 64})
    with pytest.raises(ValueError): c.load_helpers()


def test_fresh_copied_helper_access_time_is_not_identity(tmp_path, monkeypatch):
    import hashlib
    import os
    directory = tmp_path / 'code'; directory.mkdir()
    target = directory / 'helper.py'
    payload = b'VALUE = 42\n'
    target.write_bytes(payload)
    info = target.stat()
    os.utime(target, ns=(1, info.st_mtime_ns))
    monkeypatch.setattr(c, '__file__', str(directory / 'compute.py'))
    monkeypatch.setattr(c, 'CODE_PINS', {'helper.py': hashlib.sha256(payload).hexdigest()})
    assert c.load_helpers()['helper'].VALUE == 42


def test_helper_mtime_change_during_read_is_rejected(tmp_path, monkeypatch):
    import hashlib
    import os
    directory = tmp_path / 'code'; directory.mkdir()
    target = directory / 'helper.py'
    payload = b'raise RuntimeError("must not execute")\n'
    target.write_bytes(payload)
    monkeypatch.setattr(c, '__file__', str(directory / 'compute.py'))
    monkeypatch.setattr(c, 'CODE_PINS', {'helper.py': hashlib.sha256(payload).hexdigest()})
    original = Path.read_bytes
    def changed(path):
        raw = original(path)
        if path == target:
            info = path.stat()
            os.utime(path, ns=(info.st_atime_ns, info.st_mtime_ns + 1_000_000_000))
        return raw
    monkeypatch.setattr(Path, 'read_bytes', changed)
    with pytest.raises(ValueError, match='solution_code_identity'):
        c.load_helpers()
