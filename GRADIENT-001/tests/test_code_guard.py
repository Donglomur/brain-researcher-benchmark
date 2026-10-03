"""Manufactured-only entrypoint fixtures; not imported by production scoring.

No NumPy/NIfTI, original source, gradient arrays or scientific replay. Parent
must review/authorize execution separately. Fake modules are tiny plain text.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import types

import pytest

HERE = Path(__file__).absolute().parent
spec = importlib.util.spec_from_file_location('draft_code_guard', HERE / 'code_guard.py')
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


@pytest.fixture
def fake(tmp_path):
    private, public = tmp_path / 'private', tmp_path / 'public'
    private.mkdir(); public.mkdir()
    code = {'fixture_alpha': b'VALUE = 17\n',
            'fixture_beta': b'import fixture_alpha\nVALUE = fixture_alpha.VALUE + 1\n'}
    pins = {}
    for name, raw in code.items():
        (private / (name + '.py')).write_bytes(raw)
        pins[name] = sha(raw)
    document_pins, public_paths = {}, {}
    for name in ('manifest_path', 'method_path', 'schema_path'):
        filename = name + '.json'
        raw = json.dumps({'fake_only': name}).encode()
        (private / filename).write_bytes(raw)
        (public / filename).write_bytes(raw)
        document_pins[name] = (filename, sha(raw))
        public_paths[name] = str(public / filename)
    before = {key: sys.modules.get(key) for key in pins}
    present = {key: key in sys.modules for key in pins}
    yield private, pins, document_pins, public_paths
    for key in pins:
        if present[key]: sys.modules[key] = before[key]
        else: sys.modules.pop(key, None)


def test_complete_closure_executes_authenticated_bytes(fake):
    context = g.load_closure(*fake)
    assert context['modules']['fixture_beta'].VALUE == 18
    assert context['document_bytes']['method_path'] == b'{"fake_only": "method_path"}'
    g.recheck(context)


@pytest.mark.parametrize('which', ['first_code', 'last_code', 'private_doc', 'public_doc'])
def test_all_hashes_precede_any_module_execution(fake, tmp_path, which):
    root, pins, docs, public = fake
    marker = tmp_path / 'executed'
    first = ("from pathlib import Path\nPath(" + repr(str(marker)) + ").touch()\n").encode()
    (root / 'fixture_alpha.py').write_bytes(first)
    pins['fixture_alpha'] = sha(first)
    target = {'first_code': root / 'fixture_alpha.py', 'last_code': root / 'fixture_beta.py',
              'private_doc': root / docs['method_path'][0], 'public_doc': Path(public['method_path'])}[which]
    target.write_bytes(target.read_bytes() + b' ')
    with pytest.raises(ValueError, match='sha256_mismatch'):
        g.load_closure(*fake)
    assert not marker.exists()


def test_complete_compilation_precedes_execution(fake, tmp_path):
    root, pins, _, _ = fake
    marker = tmp_path / 'executed'
    first = ("from pathlib import Path\nPath(" + repr(str(marker)) + ").touch()\n").encode()
    (root / 'fixture_alpha.py').write_bytes(first); pins['fixture_alpha'] = sha(first)
    invalid = b'def not valid Python!\n'
    (root / 'fixture_beta.py').write_bytes(invalid); pins['fixture_beta'] = sha(invalid)
    with pytest.raises(SyntaxError): g.load_closure(*fake)
    assert not marker.exists()


@pytest.mark.parametrize('pin', [None, '', 'A' * 64, 'g' * 64, '0' * 63, True])
def test_unfrozen_or_invalid_pin_rejected(fake, pin):
    root, pins, _, _ = fake
    pins['fixture_alpha'] = pin
    with pytest.raises(ValueError, match='unfrozen_sha256_pin'): g.load_closure(*fake)


def test_cached_public_and_cwd_modules_do_not_supply_authority(fake, tmp_path, monkeypatch):
    attack = tmp_path / 'public_attack'; attack.mkdir()
    (attack / 'fixture_alpha.py').write_text('raise RuntimeError("public executed")\n')
    (attack / '__pycache__').mkdir()
    (attack / '__pycache__' / 'fixture_alpha.cpython-312.pyc').write_bytes(b'fake pyc')
    monkeypatch.chdir(attack); monkeypatch.syspath_prepend(str(attack))
    cached = types.ModuleType('fixture_alpha'); cached.VALUE = -1000
    monkeypatch.setitem(sys.modules, 'fixture_alpha', cached)
    assert g.load_closure(*fake)['modules']['fixture_beta'].VALUE == 18


def test_failed_execution_restores_prior_modules(fake, monkeypatch):
    root, pins, _, _ = fake
    prior = types.ModuleType('fixture_alpha'); prior.VALUE = 900
    monkeypatch.setitem(sys.modules, 'fixture_alpha', prior)
    sys.modules.pop('fixture_beta', None)
    failure = b'raise RuntimeError("manufactured first failure")\n'
    (root / 'fixture_beta.py').write_bytes(failure); pins['fixture_beta'] = sha(failure)
    with pytest.raises(RuntimeError, match='manufactured first failure'): g.load_closure(*fake)
    assert sys.modules['fixture_alpha'] is prior
    assert 'fixture_beta' not in sys.modules


def test_wrong_dependency_order_cannot_import_public_code(fake, tmp_path, monkeypatch):
    root, pins, docs, public = fake
    attack = tmp_path / 'attack'; attack.mkdir()
    (attack / 'fixture_alpha.py').write_text('VALUE=999\n')
    monkeypatch.syspath_prepend(str(attack))
    with pytest.raises(AttributeError):
        g.load_closure(root, dict(reversed(tuple(pins.items()))), docs, public)


def test_authenticated_buffer_is_used_when_file_changes_before_exec(fake, monkeypatch):
    root, _, _, _ = fake
    real_compile = compile
    changed = False
    def rewriting_compile(raw, filename, mode):
        nonlocal changed
        if not changed:
            (root / 'fixture_alpha.py').write_bytes(b'VALUE = -777\n')
            changed = True
        return real_compile(raw, filename, mode)
    monkeypatch.setattr(g, 'compile', rewriting_compile, raising=False)
    context = g.load_closure(*fake)
    assert context['modules']['fixture_beta'].VALUE == 18
    with pytest.raises(ValueError, match='sha256_mismatch'): g.recheck(context)


@pytest.mark.parametrize('target', ['module', 'private_doc', 'public_doc'])
def test_late_authority_change_rejected(fake, target):
    context = g.load_closure(*fake)
    root, _, docs, public = fake
    path = {'module': root / 'fixture_beta.py', 'private_doc': root / docs['schema_path'][0],
            'public_doc': Path(public['schema_path'])}[target]
    path.write_bytes(path.read_bytes() + b' ')
    with pytest.raises(ValueError, match='sha256_mismatch'): g.recheck(context)


@pytest.mark.parametrize('where', ['module', 'document', 'parent'])
def test_symlink_paths_rejected(fake, tmp_path, where):
    root, pins, docs, public = fake
    if where == 'parent':
        link = tmp_path / 'linked_private'; link.symlink_to(root, target_is_directory=True)
        args = (link, pins, docs, public)
    else:
        target = root / ('fixture_alpha.py' if where == 'module' else docs['method_path'][0])
        retained = tmp_path / 'retained'; target.rename(retained); target.symlink_to(retained)
        args = fake
    with pytest.raises(ValueError, match='symlink'): g.load_closure(*args)


@pytest.mark.parametrize('path', ['relative/file', '/tmp/../file', '/tmp/./file', '/tmp/nul\0file'])
def test_unsafe_lexical_paths(path):
    with pytest.raises(ValueError): g.safe_path(path)


@pytest.mark.parametrize('name', ['../module', '/module', 'module.py', 'module-name', ''])
def test_unsafe_module_names(fake, name):
    root, _, docs, public = fake
    with pytest.raises(ValueError, match='module_name'):
        g.load_closure(root, {name: '0' * 64}, docs, public)


def test_regular_empty_oversized_and_fifo_boundaries(tmp_path):
    empty = tmp_path / 'empty'; empty.touch()
    with pytest.raises(ValueError, match='bounded_regular'): g.pinned_bytes(empty, sha(b''), 10)
    large = tmp_path / 'large'; large.write_bytes(b'123')
    with pytest.raises(ValueError, match='bounded_regular'): g.pinned_bytes(large, sha(b'123'), 2)
    import os
    fifo = tmp_path / 'fifo'; os.mkfifo(fifo)
    with pytest.raises(ValueError, match='bounded_regular'): g.pinned_bytes(fifo, '0' * 64, 10)


def test_safe_sibling_output_and_protected_ancestors(tmp_path):
    data, code, app = (tmp_path / x for x in ('data', 'code', 'app'))
    for item in (data, code, app): item.mkdir()
    doc = app / 'method.json'; doc.write_text('{}')
    out = app / 'output'
    assert g.disjoint_output(out, data, code, [doc]) == out
    for bad in (data, data / 'inside', code, code / 'inside', tmp_path, app, doc):
        with pytest.raises(ValueError, match='output_overlaps'):
            g.disjoint_output(bad, data, code, [doc])


def test_required_files_extras_and_late_dangling_failure(tmp_path):
    out = tmp_path / 'output'; out.mkdir()
    (out / 'result.json').write_text('{}')
    (out / 'harmless.txt').write_text('description')
    assert g.output_inventory(out, require_files=('result.json',)) == out
    (out / 'failure_report.json').symlink_to(out / 'missing')
    with pytest.raises(ValueError, match='authoritative_failure'): g.output_inventory(out, require_files=('result.json',))


def test_missing_required_and_special_extra_rejected(tmp_path):
    out = tmp_path / 'output'; out.mkdir()
    with pytest.raises(ValueError, match='missing_required'): g.output_inventory(out, require_files=('result.json',))
    (out / 'result.json').write_text('{}')
    (out / 'extra').symlink_to(out / 'result.json')
    with pytest.raises(ValueError, match='nonregular'): g.output_inventory(out, require_files=('result.json',))


def test_output_count_bound(tmp_path):
    out = tmp_path / 'output'; out.mkdir()
    for i in range(1001): (out / str(i)).touch()
    with pytest.raises(ValueError, match='entry_cap'): g.output_inventory(out, require_files=())


def test_output_total_byte_bound_without_payload_allocation(tmp_path):
    out = tmp_path / 'output'; out.mkdir()
    with (out / 'sparse').open('wb') as stream: stream.truncate(256 * 2**20 + 1)
    with pytest.raises(ValueError, match='total_cap'): g.output_inventory(out, require_files=())


def wrapper(name, monkeypatch):
    monkeypatch.setitem(sys.modules, 'code_guard', g)
    if name not in ('grader_bootstrap', 'oracle_bootstrap'):
        raise ValueError('explicit_wrapper_fixture_name')
    candidates = [HERE / (name + '.py')]
    if name == 'oracle_bootstrap': candidates.append(HERE.parent / 'solution' / (name + '.py'))
    found = [path for path in candidates if path.is_file() and not path.is_symlink()]
    if len(found) != 1: raise ValueError('exactly_one_draft_or_installed_wrapper_layout')
    item = importlib.util.spec_from_file_location('draft_' + name, found[0])
    module = importlib.util.module_from_spec(item)
    item.loader.exec_module(module)
    return module


@pytest.mark.parametrize('name', ['grader_bootstrap', 'oracle_bootstrap'])
def test_wrapper_import_is_inert_and_pins_fail_closed(name, fake, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('no closure loading at import')
    monkeypatch.setattr(g, 'load_closure', forbidden)
    module = wrapper(name, monkeypatch)
    monkeypatch.setattr(module, 'MODULE_PINS', dict.fromkeys(module.MODULE_ORDER))
    assert all(pin is None for pin in module.MODULE_PINS.values())
    assert module.DOCUMENT_PINS['method_path'][1] == 'c6575d9cc8a9f8d422dc3ec88c2a7aefa6ca971757180517948d2466fefce872'
    root, _, docs, public = fake
    with pytest.raises(ValueError, match='unfrozen_sha256_pin'):
        # Direct utility call, not the temporarily replaced load_closure.
        g.pinned_bytes(root / 'fixture_alpha.py', next(iter(module.MODULE_PINS.values())), g.CODE_CAP)


def fake_context(tmp_path, module, monkeypatch):
    data, code, public = (tmp_path / x for x in ('source', 'code', 'app'))
    for directory in (data, code, public): directory.mkdir()
    paths, public_paths = {}, {}
    for key, (name, _) in module.DOCUMENT_PINS.items():
        paths[key], public_paths[key] = str(code / name), str(public / name)
        Path(paths[key]).write_text('{}'); Path(public_paths[key]).write_text('{}')
    monkeypatch.setattr(module, 'DATA_DIR', str(data))
    monkeypatch.setattr(module, 'PUBLIC_DOCUMENTS', public_paths)
    return {'private_dir': code, 'private_documents': paths, 'modules': {}}, public / 'output'


@pytest.mark.parametrize('late_marker', [False, True])
def test_production_has_one_reconstruction_and_rejects_late_failure(tmp_path, monkeypatch, late_marker):
    module = wrapper('grader_bootstrap', monkeypatch)
    context, output = fake_context(tmp_path, module, monkeypatch)
    output.mkdir()
    for name in module.REQUIRED: (output / name).write_text('manufactured placeholder')
    monkeypatch.setattr(module, 'OUTPUT_DIR', str(output))
    calls, basis = [], object()
    def reconstruct(**kwargs):
        calls.append(('reconstruct', kwargs)); return basis
    def validate(path, reference):
        assert path == output and reference is basis
        if late_marker: (output / 'failure_report.json').symlink_to(output / 'missing')
        calls.append(('validate', None)); return {'status': 'accepted'}
    context['modules'] = {'source_reference': types.SimpleNamespace(
        reconstruct=reconstruct, authenticate_source=lambda path: calls.append(('source_recheck', path))),
        'proof_of_work': types.SimpleNamespace(validate=validate)}
    monkeypatch.setattr(module, 'load_private', lambda: context)
    monkeypatch.setattr(g, 'recheck', lambda arg: calls.append(('authority_recheck', arg)))
    for name in ('GRADIENT_DIR', 'GRADIENT_REFERENCE', 'OUTPUT_DIR', 'METHOD_CONTRACT', 'OUTPUT_SCHEMA'):
        monkeypatch.setenv(name, '/untrusted/not-used')
    if late_marker:
        with pytest.raises(ValueError, match='authoritative_failure_marker'): module.grade()
    else:
        assert module.grade() == {'status': 'accepted'}
    assert [call[0] for call in calls] == ['reconstruct', 'validate', 'source_recheck', 'authority_recheck']
    assert calls[0][1] == {'data_dir': module.DATA_DIR,
                           'method_path': context['private_documents']['method_path'],
                           'schema_path': context['private_documents']['schema_path']}


@pytest.mark.parametrize('precreated', [False, True])
def test_late_oracle_failure_marks_owned_new_or_precreated_output(tmp_path, monkeypatch, precreated):
    module = wrapper('oracle_bootstrap', monkeypatch)
    context, output = fake_context(tmp_path, module, monkeypatch)
    if precreated:
        output.mkdir()
    def compute(args):
        assert args.data_dir == module.DATA_DIR
        if precreated:
            assert output.is_dir() and not list(output.iterdir())
        else:
            output.mkdir()
        for name in module.REQUIRED: (output / name).write_text('manufactured placeholder')
        return {'status': 'ok'}
    context['modules'] = {'compute': types.SimpleNamespace(run=compute),
                          'source_reader': types.SimpleNamespace(authenticate=lambda *args: None)}
    monkeypatch.setattr(g, 'load_closure', lambda *args: context)
    def changed(_): raise ValueError('manufactured late change')
    monkeypatch.setattr(g, 'recheck', changed)
    with pytest.raises(ValueError, match='manufactured late change'): module.run(str(output))
    marker = json.loads((output / 'failure_report.json').read_text())
    assert marker['status'] == 'failed_precondition' and 'late change' in marker['reason']


def test_oracle_rejects_protected_output_without_input_write(tmp_path, monkeypatch):
    module = wrapper('oracle_bootstrap', monkeypatch)
    context, _ = fake_context(tmp_path, module, monkeypatch)
    monkeypatch.setattr(g, 'load_closure', lambda *args: context)
    with pytest.raises(ValueError, match='output_overlaps_source_or_code'):
        module.run(module.DATA_DIR)
    assert list(Path(module.DATA_DIR).iterdir()) == []
