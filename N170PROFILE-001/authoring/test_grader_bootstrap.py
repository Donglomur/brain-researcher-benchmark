"""Source-free authority/anti-shadow fixtures; excluded from production scoring."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import types

import pytest

import grader_bootstrap as boot


BASE = 'n170_fixture_base'
CHILD = 'n170_fixture_child'


@pytest.fixture
def code(tmp_path, monkeypatch):
    root = tmp_path / 'private'
    root.mkdir()
    raw = {BASE: b'VALUE = 17\n', CHILD: b'import n170_fixture_base\nVALUE = n170_fixture_base.VALUE + 1\n'}
    pins = {}
    for name, body in raw.items():
        (root / (name + '.py')).write_bytes(body)
        pins[name] = hashlib.sha256(body).hexdigest()
        monkeypatch.setitem(sys.modules, name, types.ModuleType('old_' + name))
    return root, pins


def test_authenticated_bytes_replace_cached_public_modules(code):
    root, pins = code
    sys.modules[BASE].VALUE = -999
    loaded = boot._load(root, pins)
    assert loaded[BASE].VALUE == 17 and loaded[CHILD].VALUE == 18
    assert loaded[CHILD].n170_fixture_base is loaded[BASE]
    assert Path(loaded[BASE].__file__).parent == root


def test_contaminated_cwd_public_modules_and_bytecode_are_ignored(code, tmp_path, monkeypatch):
    root, pins = code
    public = tmp_path / 'public'; public.mkdir()
    for name in pins:
        (public / (name + '.py')).write_text('raise RuntimeError("public shadow executed")\n')
        (root / (name + '.pyc')).write_bytes(b'malicious or stale legacy bytecode')
        cached = Path(importlib.util.cache_from_source(str(root / (name + '.py'))))
        cached.parent.mkdir(exist_ok=True)
        cached.write_bytes(b'malicious or stale cached bytecode')
    monkeypatch.chdir(public)
    monkeypatch.syspath_prepend(str(public))
    assert boot._load(root, pins)[CHILD].VALUE == 18


def test_final_digest_failure_prevents_every_module_execution(code, tmp_path):
    root, pins = code
    sentinel = tmp_path / 'executed'
    raw = ('from pathlib import Path\nPath(' + repr(str(sentinel)) + ').write_text("bad")\n').encode()
    (root / (BASE + '.py')).write_bytes(raw)
    pins[BASE] = hashlib.sha256(raw).hexdigest()
    (root / (CHILD + '.py')).write_text('VALUE = 999\n')
    old = dict((name, sys.modules[name]) for name in pins)
    with pytest.raises(ValueError, match='private_code_sha256'):
        boot._load(root, pins)
    assert not sentinel.exists()
    assert all(sys.modules[name] is old[name] for name in pins)


def test_all_code_compiles_before_any_module_executes(code, tmp_path):
    root, pins = code
    sentinel = tmp_path / 'executed'
    values = {BASE: ('from pathlib import Path\nPath(' + repr(str(sentinel)) + ').write_text("bad")\n').encode(),
              CHILD: b'def broken(:\n'}
    for name, raw in values.items():
        (root / (name + '.py')).write_bytes(raw); pins[name] = hashlib.sha256(raw).hexdigest()
    with pytest.raises(SyntaxError):boot._load(root, pins)
    assert not sentinel.exists()


def test_execution_failure_restores_previous_module_cache(code):
    root, pins = code
    old = {name: sys.modules[name] for name in pins}
    raw = b'raise RuntimeError("manufactured import failure")\n'
    (root / (CHILD + '.py')).write_bytes(raw); pins[CHILD] = hashlib.sha256(raw).hexdigest()
    with pytest.raises(RuntimeError, match='manufactured import failure'):boot._load(root, pins)
    assert all(sys.modules[name] is old[name] for name in pins)


def test_no_module_or_acceptance_cache_reuse(code):
    root, pins = code
    first = boot._load(root, pins)
    first[BASE].VALUE = -1
    second = boot._load(root, pins)
    assert second[BASE].VALUE == 17 and first[BASE] is not second[BASE]
    (root / (BASE + '.py')).write_text('VALUE = 88\n')
    with pytest.raises(ValueError, match='private_code_sha256'):boot._load(root, pins)


@pytest.mark.parametrize('kind', ['member_symlink', 'parent_symlink', 'missing', 'directory', 'empty', 'too_large'])
def test_private_files_are_bounded_regular_nonsymlinks(code, tmp_path, kind):
    root, pins = code
    path = root / (BASE + '.py')
    if kind == 'member_symlink':
        target = tmp_path / 'target.py'; target.write_bytes(path.read_bytes()); path.unlink(); path.symlink_to(target)
    elif kind == 'parent_symlink':
        link = tmp_path / 'alias'; link.symlink_to(root); root = link
    elif kind == 'missing':path.unlink()
    elif kind == 'directory':path.unlink(); path.mkdir()
    elif kind == 'empty':path.write_bytes(b'')
    else:path.write_bytes(b'x' * (boot.MAX_CODE_BYTES + 1))
    with pytest.raises((ValueError, OSError)):boot._load(root, pins)


@pytest.mark.parametrize('name,digest', [('../escape', 'a'*64), ('valid', None), ('valid', 'A'*64), ('valid', 'x')])
def test_module_and_pin_formats_fail_closed(tmp_path, name, digest):
    with pytest.raises(ValueError):boot._load(tmp_path, {name: digest})


def test_private_root_must_be_absolute_and_nontraversing(tmp_path):
    for root in ('relative', str(tmp_path) + '/../elsewhere'):
        with pytest.raises(ValueError):boot._load(root, {BASE: 'a'*64})


@pytest.fixture
def documents(tmp_path, monkeypatch):
    private = tmp_path / 'private'; private.mkdir()
    public = tmp_path / 'app'; public.mkdir()
    monkeypatch.setattr(boot, '__file__', str(private / 'grader_bootstrap.py'))
    pins = {}; paths = {}
    for key in ('manifest_path', 'method_path', 'schema_path'):
        filename = key + '.json'; raw = json.dumps({'key': key}).encode()
        (private / filename).write_bytes(raw); (public / filename).write_bytes(raw)
        pins[key] = (filename, hashlib.sha256(raw).hexdigest()); paths[key] = str(public / filename)
    monkeypatch.setattr(boot, 'DOCUMENT_PINS', pins)
    reader = types.SimpleNamespace(read_bytes=lambda path, *, limit, sha256: boot._read(path, sha256))
    return private, public, paths, reader


def test_documents_check_public_bytes_but_return_only_private_paths(documents):
    private, public, paths, reader = documents
    result = boot.authenticated_documents(paths, reader)
    assert set(result) == set(paths)
    assert all(Path(value).parent == private for value in result.values())
    assert all(Path(value).parent == public for value in paths.values())


@pytest.mark.parametrize('location', ['public', 'private'])
@pytest.mark.parametrize('key', ['manifest_path', 'method_path', 'schema_path'])
def test_each_document_copy_is_pinned(documents, location, key):
    private, public, paths, reader = documents
    path = Path(paths[key]) if location == 'public' else private / boot.DOCUMENT_PINS[key][0]
    path.write_text('{"changed":true}')
    with pytest.raises(ValueError, match='private_code_sha256'):
        boot.authenticated_documents(paths, reader)


@pytest.mark.parametrize('kind', ['source', 'source_child', 'source_parent', 'code', 'code_child', 'code_parent', 'doc_parent'])
def test_grader_output_overlap_is_rejected(tmp_path, kind):
    source = tmp_path / 'data' / 'source'; source.mkdir(parents=True)
    code = tmp_path / 'private' / 'tests'; code.mkdir(parents=True)
    doc = tmp_path / 'app' / 'method.json'; doc.parent.mkdir(); doc.write_text('{}')
    paths = {'source': source, 'source_child': source/'out', 'source_parent': source.parent,
             'code': code, 'code_child': code/'out', 'code_parent': code.parent, 'doc_parent': doc.parent}
    out = paths[kind]; out.mkdir(exist_ok=True)
    with pytest.raises(ValueError):boot.disjoint_output(out, source, [doc], code)
    assert not (out/'failure_report.json').exists()


def test_grader_allows_output_next_to_public_documents(tmp_path):
    source = tmp_path/'data'; source.mkdir()
    code = tmp_path/'tests'; code.mkdir()
    doc = tmp_path/'method.json'; doc.write_text('{}')
    out = tmp_path/'output'; out.mkdir()
    assert boot.disjoint_output(out, source, [doc], code) == out
