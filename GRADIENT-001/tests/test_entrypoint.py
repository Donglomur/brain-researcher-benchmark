"""Manufactured entrypoint tests only; no task/source/scientific imports.

The nested pytest test executes one tiny fabricated assertion and a toy CTRF
option plugin. It never reconstructs data or executes the production test.
All filesystem writes are confined to pytest-owned tmp_path fixtures.
"""
import hashlib
import importlib.util
from pathlib import Path
import sys
import types
import xml.etree.ElementTree as ET

import pytest


HERE = Path(__file__).absolute().parent
spec = importlib.util.spec_from_file_location('draft_entrypoint', HERE/'entrypoint.py')
e = importlib.util.module_from_spec(spec)
spec.loader.exec_module(e)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def shell_fixture_path(name):
    if name not in ('test.sh', 'solve.sh'): raise ValueError('explicit_shell_fixture_name')
    candidates = [HERE/name]
    if name == 'solve.sh': candidates.append(HERE.parent/'solution'/name)
    found = [path for path in candidates if path.is_file() and not path.is_symlink()]
    if len(found) != 1: raise ValueError('exactly_one_draft_or_installed_shell_layout')
    return found[0]


@pytest.fixture
def fake(tmp_path):
    root = tmp_path/'entries'; root.mkdir()
    bodies = {'entry_alpha': b'VALUE=17\n',
              'entry_beta': b'import entry_alpha\nVALUE=entry_alpha.VALUE+1\n'}
    for name, raw in bodies.items(): (root/(name+'.py')).write_bytes(raw)
    pins = {name: sha(raw) for name, raw in bodies.items()}
    prior = {name: sys.modules.get(name) for name in pins}
    present = {name: name in sys.modules for name in pins}
    yield root, pins
    for name in pins:
        if present[name]: sys.modules[name] = prior[name]
        else: sys.modules.pop(name, None)


def test_retained_dependency_first_closure(fake):
    context = e.load_entries(*fake)
    assert context['modules']['entry_beta'].VALUE == 18
    e.recheck_entries(context)
    e.restore_entries(context)


@pytest.mark.parametrize('which', ['entry_alpha', 'entry_beta'])
def test_all_authentication_precedes_execution(fake, tmp_path, which):
    root, pins = fake; marker = tmp_path/'unwanted-exec'
    raw = ('from pathlib import Path\nPath('+repr(str(marker))+').touch()\nVALUE=17\n').encode()
    (root/'entry_alpha.py').write_bytes(raw); pins['entry_alpha'] = sha(raw)
    path = root/(which+'.py'); path.write_bytes(path.read_bytes()+b' ')
    with pytest.raises(ValueError, match='entrypoint_sha256'): e.load_entries(root, pins)
    assert not marker.exists()


def test_all_compile_precedes_exec(fake, tmp_path):
    root, pins = fake; marker = tmp_path/'unwanted-exec'
    raw = ('from pathlib import Path\nPath('+repr(str(marker))+').touch()\n').encode()
    (root/'entry_alpha.py').write_bytes(raw); pins['entry_alpha'] = sha(raw)
    raw = b'not valid Python!\n'
    (root/'entry_beta.py').write_bytes(raw); pins['entry_beta'] = sha(raw)
    with pytest.raises(SyntaxError): e.load_entries(root, pins)
    assert not marker.exists()


def test_stale_module_and_wrong_order_never_import_mutable_fallback(fake, tmp_path, monkeypatch):
    root, pins = fake
    cached = types.ModuleType('entry_alpha'); cached.VALUE = -1
    monkeypatch.setitem(sys.modules, 'entry_alpha', cached)
    attack = tmp_path/'attack'; attack.mkdir()
    (attack/'entry_alpha.py').write_text('raise AssertionError("mutable fallback")\n')
    monkeypatch.syspath_prepend(str(attack))
    context = e.load_entries(root, pins)
    assert context['modules']['entry_beta'].VALUE == 18
    e.restore_entries(context)
    assert sys.modules['entry_alpha'] is cached
    with pytest.raises(AttributeError): e.load_entries(root, dict(reversed(list(pins.items()))))
    assert sys.modules['entry_alpha'] is cached


def test_exec_failure_restores_all_modules(fake, monkeypatch):
    root, pins = fake; prior = types.ModuleType('entry_alpha')
    monkeypatch.setitem(sys.modules, 'entry_alpha', prior)
    monkeypatch.delitem(sys.modules, 'entry_beta', raising=False)
    raw = b'raise RuntimeError("fixture failure")\n'
    (root/'entry_beta.py').write_bytes(raw); pins['entry_beta'] = sha(raw)
    with pytest.raises(RuntimeError, match='fixture failure'): e.load_entries(root, pins)
    assert sys.modules['entry_alpha'] is prior and 'entry_beta' not in sys.modules


def test_compile_uses_authenticated_bytes_and_late_recheck_refuses(fake, monkeypatch):
    root, pins = fake; real_compile = compile
    def change_after_read(raw, filename, mode):
        (root/'entry_alpha.py').write_bytes(b'VALUE=-900\n')
        return real_compile(raw, filename, mode)
    monkeypatch.setattr(e, 'compile', change_after_read, raising=False)
    context = e.load_entries(root, pins)
    assert context['modules']['entry_beta'].VALUE == 18
    with pytest.raises(ValueError, match='entrypoint_sha256'): e.recheck_entries(context)


@pytest.mark.parametrize('pin', [None, '', 'g'*64, 'A'*64, '0'*63, True])
def test_unfrozen_invalid_pin(fake, pin):
    root, pins = fake; pins['entry_alpha'] = pin
    with pytest.raises(ValueError, match='unfrozen_entrypoint_pin'): e.load_entries(root, pins)


@pytest.mark.parametrize('name', ['../a', '/a', 'a.py', 'a-b', ''])
def test_bad_module_name(fake, name):
    with pytest.raises(ValueError, match='entrypoint_module_name'):
        e.load_entries(fake[0], {name: '0'*64})


@pytest.mark.parametrize('kind', ['file_link', 'parent_link', 'empty', 'oversized', 'fifo'])
def test_unsafe_members(tmp_path, kind):
    root = tmp_path/'code'; root.mkdir(); path = root/'entry_alpha.py'; raw = b'VALUE=1\n'
    path.write_bytes(raw)
    if kind == 'file_link':
        target = tmp_path/'retained'; path.rename(target); path.symlink_to(target)
    elif kind == 'parent_link':
        link = tmp_path/'link'; link.symlink_to(root, target_is_directory=True); path = link/path.name
    elif kind == 'empty': path.write_bytes(b'')
    elif kind == 'oversized':
        with path.open('wb') as stream: stream.truncate(e.CODE_CAP+1)
    else:
        import os
        path.unlink(); os.mkfifo(path)
    with pytest.raises(ValueError): e.pinned_bytes(path, sha(raw))


@pytest.mark.parametrize('role,argv', [('bad', ()), ('grader', ['--override']), ('oracle', [1])])
def test_no_generic_cli_authority(role, argv, monkeypatch):
    monkeypatch.setattr(e, 'load_entries', lambda *args: pytest.fail('must reject before code reads'))
    with pytest.raises(ValueError): e.main(role, argv)


def test_oracle_fixed_root_order_forwarding_and_restore(monkeypatch):
    calls = []; previous = sys.argv
    def fake_load(root, pins):
        assert root == Path('/solution') and tuple(pins) == e.ORACLE_ORDER
        return {'modules': {'oracle_bootstrap': types.SimpleNamespace(main=lambda: calls.append(tuple(sys.argv)))}}
    monkeypatch.setattr(e, 'load_entries', fake_load)
    monkeypatch.setattr(e, 'recheck_entries', lambda context: calls.append('recheck'))
    monkeypatch.setattr(e, 'restore_entries', lambda context: calls.append('restore'))
    assert e.main('oracle', ['--output-dir', '/tmp/manufactured']) == 0
    assert calls == [('/solution/oracle_bootstrap.py', '--output-dir', '/tmp/manufactured'), 'recheck', 'restore']
    assert sys.argv is previous


@pytest.mark.parametrize('n_plugins', [0, 2])
def test_only_one_baked_ctrf_plugin(n_plugins, monkeypatch):
    calls = []
    def fake_load(root, pins):
        assert root == Path('/tests') and tuple(pins) == e.GRADER_ORDER
        return {'modules': {'test_outputs': object()}}
    monkeypatch.setattr(e, 'load_entries', fake_load)
    monkeypatch.setattr(e, 'restore_entries', lambda context: calls.append('restore'))
    monkeypatch.setattr(e.importlib.metadata, 'distribution', lambda name: types.SimpleNamespace(
        entry_points=[types.SimpleNamespace(group='pytest11')] * n_plugins))
    with pytest.raises(ValueError, match='exactly_one_baked_ctrf'): e.main('grader')
    assert calls == ['restore']


def test_grader_environment_and_exact_plugin(monkeypatch):
    calls = []; retained = object(); plugin = object()
    monkeypatch.setattr(e, 'load_entries', lambda root, pins: {'modules': {'test_outputs': retained}})
    monkeypatch.setenv('PYTEST_ADDOPTS', '-k not-production')
    monkeypatch.setenv('PYTEST_PLUGINS', 'untrusted_plugin')
    monkeypatch.setattr(e.importlib.metadata, 'distribution', lambda name: types.SimpleNamespace(
        entry_points=[types.SimpleNamespace(group='pytest11', load=lambda: plugin)]))
    def run(pytest_module, test_module, ctrf_plugin):
        import os
        assert test_module is retained and ctrf_plugin is plugin
        assert os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD'] == '1'
        assert 'PYTEST_ADDOPTS' not in os.environ and 'PYTEST_PLUGINS' not in os.environ
        return 0
    monkeypatch.setattr(e, 'production_pytest', run)
    monkeypatch.setattr(e, 'recheck_entries', lambda context: calls.append('recheck'))
    monkeypatch.setattr(e, 'restore_entries', lambda context: calls.append('restore'))
    assert e.main('grader') == 0 and calls == ['recheck', 'restore']


@pytest.mark.parametrize('outcome', ['pass', 'skip', 'failure'])
def test_real_pytest_collects_retained_module_only(tmp_path, monkeypatch, outcome):
    monkeypatch.setenv('PYTEST_DISABLE_PLUGIN_AUTOLOAD', '1')
    monkeypatch.delenv('PYTEST_ADDOPTS', raising=False); monkeypatch.delenv('PYTEST_PLUGINS', raising=False)
    root = tmp_path/'tiny'; root.mkdir(); path = root/'test_outputs.py'
    lines = {'pass': 'assert 2+2==4', 'skip': 'import pytest; pytest.skip("manufactured")',
             'failure': 'assert False, "manufactured"'}
    raw = ('def test_source_bound_gradient():\n    '+lines[outcome]+'\n').encode()
    path.write_bytes(raw)
    context = e.load_entries(root, {'test_outputs': sha(raw)})
    try:
        # Pytest enumerates sibling test files even for a single explicit node.
        # No sibling, non-test helper, package or conftest may execute.
        path.write_text('raise AssertionError("reopened mutable test file")\n')
        (root/'conftest.py').write_text('raise AssertionError("unapproved conftest")\n')
        marker = tmp_path/'unapproved-module-executed'
        poison = ('from pathlib import Path\nPath('+repr(str(marker))+').touch()\n'
                  'raise AssertionError("unapproved sibling or package")\n')
        for filename in ('test_sibling.py', 'test_outputs_backup.py', 'helper.py'):
            (root/filename).write_text(poison)
        nested = root/'nested'; nested.mkdir()
        for filename in ('__init__.py', 'test_nested.py', 'conftest.py'):
            (nested/filename).write_text(poison)
        logs = tmp_path/'logs'; logs.mkdir(); before = list(sys.path)
        class ToyCTRF:
            def pytest_addoption(self, parser): parser.addoption('--ctrf', action='store')
        if outcome == 'skip':
            with pytest.raises(ValueError, match='one_passed_production_call_required'):
                e.production_pytest(pytest, context['modules']['test_outputs'], ToyCTRF(), logs=logs)
        else:
            status = e.production_pytest(pytest, context['modules']['test_outputs'], ToyCTRF(), logs=logs)
            assert status == (0 if outcome == 'pass' else 1)
        assert sys.path == before
        assert not marker.exists()
        cases = ET.parse(logs/'junit.xml').findall('.//testcase')
        assert len(cases) == 1 and cases[0].attrib['name'] == e.TEST_NAME
    finally:
        e.restore_entries(context)


@pytest.mark.parametrize('script,role', [('test.sh', 'grader'), ('solve.sh', 'oracle')])
@pytest.mark.parametrize('mode', ['unfrozen', 'valid', 'wrong_hash', 'symlink'])
def test_shell_embedded_loader_has_no_mutable_imports(tmp_path, monkeypatch, script, role, mode):
    text = shell_fixture_path(script).read_text()
    assert 'python3 -I -B -' in text and 'sys.path.insert' not in text
    body = text.split("<<'PY'\n", 1)[1].split('\nPY\n', 1)[0]
    path = tmp_path/'entrypoint.py'
    raw = b'CALL=None\ndef main(role, argv=()):\n    global CALL\n    CALL=(role,list(argv))\n    return 7\n'
    path.write_bytes(raw)
    # Explicit fixture-only relocation; production exposes no such parameter.
    body = body.replace("Path('/tests/entrypoint.py')", 'Path('+repr(str(path))+')')
    body = body.replace("Path('/solution/entrypoint.py')", 'Path('+repr(str(path))+')')
    import re
    fixture_pin = None if mode == 'unfrozen' else sha(raw)
    body = re.sub(r'^PIN = .*$', 'PIN = '+repr(fixture_pin), body, count=1, flags=re.MULTILINE)
    if mode == 'wrong_hash': path.write_bytes(raw+b' ')
    elif mode == 'symlink':
        saved = tmp_path/'saved'; path.rename(saved); path.symlink_to(saved)
    monkeypatch.setattr(sys, 'argv', ['-', '--output-dir', '/tmp/manufactured'])
    namespace = {}
    if mode == 'valid':
        with pytest.raises(SystemExit) as stopped: exec(compile(body, '<manufactured shell loader>', 'exec'), namespace)
        assert stopped.value.code == 7
        assert namespace['module'].CALL == (role, [] if role == 'grader' else sys.argv[1:])
    else:
        with pytest.raises(ValueError): exec(compile(body, '<manufactured shell loader>', 'exec'), namespace)
