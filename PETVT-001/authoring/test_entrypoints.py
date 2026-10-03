"""Manufactured path/authority checks only; never calls source fitting."""
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import warnings

import pytest

ROOT=Path(__file__).resolve().parents[1]


def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);obj=importlib.util.module_from_spec(spec);spec.loader.exec_module(obj);return obj


compute=module('candidate_compute',ROOT/'solution'/'compute_v2.py')
boot=module('candidate_boot',ROOT/'tests'/'grader_bootstrap.py')


def stub(monkeypatch,*,late_failure=False):
    def load(*args):
        warnings.warn('manufactured warning',UserWarning)
        return {'schema':{'limits':{'file_bytes':{'artifact':1024}}}}
    def artifacts(basis):return {'metadata':{'warnings':[]}}
    def write(out,actual):
        (out/'artifact').write_text(json.dumps(actual))
        if late_failure:raise ValueError('manufactured late write failure')
    monkeypatch.setattr(compute,'load_code',lambda:{'source_reader':SimpleNamespace(load=load),
        'output_writer':SimpleNamespace(artifacts=artifacts,write=write)})


def args(tmp_path,output):
    return ['--output',str(output),'--data-dir',str(tmp_path/'source'),
        '--manifest',str(tmp_path/'docs'/'source.json'),'--method',str(tmp_path/'docs'/'method.json'),
        '--schema',str(tmp_path/'docs'/'schema.json')]


def test_warning_strings_and_sibling_documents(tmp_path,monkeypatch):
    stub(monkeypatch);out=tmp_path/'output'
    assert compute.main(args(tmp_path,out))==0
    assert json.loads((out/'artifact').read_text())['metadata']['warnings']==['manufactured warning']


@pytest.mark.parametrize('which',['source','source/nested','docs','docs/source.json'])
def test_protected_output_never_gets_failure_marker(tmp_path,monkeypatch,which):
    stub(monkeypatch);out=tmp_path/which
    assert compute.main(args(tmp_path,out))==1
    assert not(out/'failure_report.json').exists()


def test_ordinary_stale_output_marked_without_overwrite(tmp_path,monkeypatch):
    stub(monkeypatch);out=tmp_path/'output';out.mkdir();(out/'prior').write_text('retain')
    assert compute.main(args(tmp_path,out))==1 and (out/'failure_report.json').exists()
    assert(out/'prior').read_text()=='retain'


def test_late_failure_is_authoritative(tmp_path,monkeypatch):
    stub(monkeypatch,late_failure=True);out=tmp_path/'output'
    assert compute.main(args(tmp_path,out))==1
    assert(out/'artifact').exists()and(out/'failure_report.json').exists()


@pytest.fixture
def private(tmp_path,monkeypatch):
    private=tmp_path/'private';public=tmp_path/'public';private.mkdir();public.mkdir()
    code={'first':b'VALUE = 1\n','second':b'VALUE = 2\n'}
    docs={'source_manifest.json':b'{}\n','method_contract.json':b'{"m":1}\n','output_schema.json':b'{"s":1}\n'}
    for name,raw in code.items():(private/(name+'.py')).write_bytes(raw)
    for name,raw in docs.items():(private/name).write_bytes(raw);(public/name).write_bytes(raw)
    monkeypatch.setattr(boot,'CODE_PINS',{n:hashlib.sha256(v).hexdigest()for n,v in code.items()})
    monkeypatch.setattr(boot,'DOC_PINS',{n:hashlib.sha256(v).hexdigest()for n,v in docs.items()})
    return private,public


def test_private_closure_fresh_modules(private):
    p,public=private;one=boot.load_private(p,public);two=boot.load_private(p,public)
    assert one['modules']['first'].VALUE==1
    assert one['modules']['first']is not two['modules']['first']


@pytest.mark.parametrize('change',['code','private_doc','public_doc','symlink','unfrozen'])
def test_private_auth_fails_before_execution(private,monkeypatch,change):
    p,public=private
    raw=b'raise AssertionError("executed before authentication")\n';(p/'first.py').write_bytes(raw)
    monkeypatch.setitem(boot.CODE_PINS,'first',hashlib.sha256(raw).hexdigest())
    if change=='code':(p/'second.py').write_bytes(b'bad')
    elif change=='private_doc':(p/'source_manifest.json').write_bytes(b'bad')
    elif change=='public_doc':(public/'method_contract.json').write_bytes(b'bad')
    elif change=='symlink':(p/'second.py').unlink();(p/'second.py').symlink_to('/absent')
    else:monkeypatch.setitem(boot.CODE_PINS,'second',None)
    with pytest.raises(ValueError):boot.load_private(p,public)


def test_read_only_atime_change_not_rejected(private):
    p,_=private;path=p/'first.py';pin=boot.CODE_PINS['first']
    assert boot.read_pinned(path,pin,1024)==boot.read_pinned(path,pin,1024)
