"""Explicit manufactured bootstrap policies, never source values."""
import hashlib
import importlib.util
from pathlib import Path
import sys
import types
import pytest

HERE=Path(__file__).parent

def load(name):
    spec=importlib.util.spec_from_file_location('manufactured_'+name,(HERE/(name+'.py') if (HERE/(name+'.py')).is_file() else HERE.parent/'solution'/(name+'.py')))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def sha(raw):return hashlib.sha256(raw).hexdigest()

def test_closure_authentication_before_exec_and_documents(tmp_path):
    guard=load('code_guard');private=tmp_path/'private';public=tmp_path/'public'
    private.mkdir();public.mkdir()
    raw=b'{"fixed":true}\n'
    for p in (private,public):(p/'method.json').write_bytes(raw)
    (private/'first.py').write_text('VALUE=7\n')
    (private/'second.py').write_text('import first\nVALUE=first.VALUE+1\n')
    pins={n:sha((private/(n+'.py')).read_bytes()) for n in ('first','second')}
    documents={'method':('method.json',sha(raw))};paths={'method':public/'method.json'}
    prior={n:sys.modules.get(n) for n in pins}
    try:
        context=guard.load_closure(private,pins,documents,paths)
        assert context['modules']['second'].VALUE==8
        guard.recheck(context)
        (public/'method.json').write_text('{"fixed":false}')
        with pytest.raises(ValueError):guard.recheck(context)
    finally:
        for n,m in prior.items():
            if m is None:sys.modules.pop(n,None)
            else:sys.modules[n]=m

def test_bootstraps_inert_and_fail_closed(monkeypatch):
    guard=load('code_guard');monkeypatch.setitem(sys.modules,'code_guard',guard)
    for name in ('grader_bootstrap','oracle_bootstrap'):
        module=load(name)
        # Explicit fixture policy remains valid after production pins are bound.
        monkeypatch.setattr(module,'MODULE_PINS',{key:None for key in module.MODULE_PINS})
        with pytest.raises(ValueError,match='unfrozen'):
            guard.load_closure(HERE,module.MODULE_PINS,module.DOCUMENT_PINS,module.PUBLIC_PATHS)

def test_oracle_late_guard_failure_writes_authoritative_marker(tmp_path,monkeypatch):
    guard=load('code_guard');monkeypatch.setitem(sys.modules,'code_guard',guard)
    oracle=load('oracle_bootstrap');output=tmp_path/'output'
    def run(*args):
        output.mkdir();(output/'results.json').write_text('{}')
    context={'modules':{'writer_v2':types.SimpleNamespace(run=run)}}
    monkeypatch.setattr(guard,'load_closure',lambda *a:context)
    monkeypatch.setattr(guard,'recheck',lambda _:(_ for _ in ()).throw(ValueError('late')))
    monkeypatch.setenv('OUTPUT_DIR',str(output))
    with pytest.raises(ValueError,match='late'):oracle.main()
    assert (output/'failure_report.json').is_file()
