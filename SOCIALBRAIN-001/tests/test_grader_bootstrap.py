"""Manufactured authority, anti-shadow and single-pass entrypoint fixtures only."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import types

import pytest


HERE = Path(__file__).parent


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


boot = module('manufactured_socialbrain_bootstrap', 'grader_bootstrap.py')
score = module('manufactured_socialbrain_score', 'score_submission.py')
BASE, CHILD = 'socialbrain_fixture_base', 'socialbrain_fixture_child'


@pytest.fixture
def bundle(tmp_path, monkeypatch):
    private, public = tmp_path / 'private', tmp_path / 'app'
    private.mkdir(); public.mkdir()
    code = {BASE: b'VALUE = 17\n', CHILD: b'import socialbrain_fixture_base\nVALUE = socialbrain_fixture_base.VALUE + 1\n'}
    pins = {}
    for name, raw in code.items():
        (private / (name + '.py')).write_bytes(raw)
        pins[name] = hashlib.sha256(raw).hexdigest()
        monkeypatch.setitem(sys.modules, name, types.ModuleType('old_' + name))
    documents, paths = {}, {}
    for key, (filename, _) in boot.DOCUMENT_PINS.items():
        raw = json.dumps({'document': key}).encode()
        (private / filename).write_bytes(raw); (public / filename).write_bytes(raw)
        documents[key] = (filename, hashlib.sha256(raw).hexdigest())
        paths[key] = str(public / filename)
    return private, pins, documents, paths


def test_same_buffer_modules_replace_stale_cache_and_use_private_documents(bundle):
    private, pins, _, paths = bundle
    old = sys.modules[BASE]; old.VALUE = -999
    loaded = boot._load(*bundle)
    assert loaded['modules'][CHILD].VALUE == 18
    assert loaded['modules'][BASE] is not old
    assert loaded['modules'][CHILD].socialbrain_fixture_base is loaded['modules'][BASE]
    assert all(Path(value).parent == private for value in loaded['documents'].values())
    assert all(Path(value).parent != private for value in paths.values())
    assert loaded['payloads'][BASE] == (private / (BASE + '.py')).read_bytes()
    assert tuple(loaded['modules']) == tuple(pins)


def test_no_sys_path_change_and_cwd_or_bytecode_shadow_ignored(bundle, tmp_path, monkeypatch):
    private, pins, _, _ = bundle
    shadow = tmp_path / 'untrusted'; shadow.mkdir()
    for name in pins:
        (shadow / (name + '.py')).write_text('raise RuntimeError("untrusted code executed")\n')
        (private / (name + '.pyc')).write_bytes(b'not trusted bytecode')
    monkeypatch.chdir(shadow); monkeypatch.syspath_prepend(str(shadow))
    original = list(sys.path)
    assert boot._load(*bundle)['modules'][CHILD].VALUE == 18
    assert sys.path == original


@pytest.mark.parametrize('failure', ['last_code_hash', 'last_code_syntax', 'public_document', 'private_document'])
def test_complete_code_and_document_gate_precedes_every_execution(bundle, tmp_path, failure):
    private, pins, documents, paths = bundle
    sentinel = tmp_path / 'executed'
    first = ('from pathlib import Path\nPath(' + repr(str(sentinel)) + ').touch()\n').encode()
    (private / (BASE + '.py')).write_bytes(first); pins[BASE] = hashlib.sha256(first).hexdigest()
    if failure.startswith('last_code'):
        raw = b'def malformed(:\n' if failure.endswith('syntax') else b'VALUE = -1\n'
        (private / (CHILD + '.py')).write_bytes(raw)
        if failure.endswith('syntax'): pins[CHILD] = hashlib.sha256(raw).hexdigest()
    else:
        path = Path(paths['schema_path']) if failure == 'public_document' else private / documents['schema_path'][0]
        path.write_text('{"wrong":true}')
    with pytest.raises((ValueError, SyntaxError)):
        boot._load(*bundle)
    assert not sentinel.exists()


def test_execution_failure_restores_original_private_module_cache(bundle):
    private, pins, _, _ = bundle
    previous = {name: sys.modules[name] for name in pins}
    raw = b'raise RuntimeError("manufactured import failure")\n'
    (private / (CHILD + '.py')).write_bytes(raw); pins[CHILD] = hashlib.sha256(raw).hexdigest()
    with pytest.raises(RuntimeError, match='manufactured import failure'): boot._load(*bundle)
    assert all(sys.modules[name] is previous[name] for name in pins)


def test_every_load_reauthenticates_without_acceptance_cache(bundle):
    first = boot._load(*bundle); first['modules'][BASE].VALUE = -9
    second = boot._load(*bundle)
    assert second['modules'][BASE].VALUE == 17
    assert second['modules'][BASE] is not first['modules'][BASE]
    (bundle[0] / (BASE + '.py')).write_text('VALUE = 42\n')
    with pytest.raises(ValueError, match='private_sha256'): boot._load(*bundle)


@pytest.mark.parametrize('kind', ['symlink', 'parent_symlink', 'missing', 'directory', 'empty', 'oversize', 'fifo'])
def test_private_code_requires_bounded_regular_nonsymlink_file(bundle, tmp_path, monkeypatch, kind):
    private, pins, documents, paths = bundle
    path = private / (BASE + '.py')
    if kind == 'parent_symlink':
        link = tmp_path / 'alias'; link.symlink_to(private); private = link
    elif kind == 'symlink':
        other = tmp_path / 'other'; other.write_bytes(path.read_bytes()); path.unlink(); path.symlink_to(other)
    elif kind == 'missing': path.unlink()
    elif kind == 'directory': path.unlink(); path.mkdir()
    elif kind == 'empty': path.write_bytes(b'')
    elif kind == 'oversize': monkeypatch.setattr(boot, 'MAX_CODE_BYTES', 1)
    else: path.unlink(); boot.os.mkfifo(path)
    with pytest.raises((ValueError, OSError)): boot._load(private, pins, documents, paths)


@pytest.mark.parametrize('name,digest', [('../escape', 'a'*64), ('valid', None), ('valid', 'A'*64), ('valid', 'x')])
def test_invalid_module_or_unfrozen_pin_before_io(bundle, name, digest):
    private, _, documents, paths = bundle
    with pytest.raises(ValueError): boot._load(private, {name: digest}, documents, paths)


@pytest.mark.parametrize('key', ['manifest_path', 'method_path', 'schema_path'])
@pytest.mark.parametrize('location', ['public', 'private'])
def test_document_change_after_validation_is_rejected(bundle, key, location):
    context = boot._load(*bundle)
    path = Path(context['public_paths'][key] if location == 'public' else context['documents'][key])
    path.write_text('{"changed":true}')
    with pytest.raises(ValueError, match='private_sha256'): boot.recheck_documents(context)


@pytest.mark.parametrize('kind', ['source', 'source_child', 'source_parent', 'private', 'private_child', 'private_parent', 'doc_parent'])
def test_source_code_document_overlap_is_read_only_rejection(tmp_path, kind):
    source = tmp_path / 'data' / 'source'; source.mkdir(parents=True)
    private = tmp_path / 'trusted' / 'tests'; private.mkdir(parents=True)
    doc = tmp_path / 'app' / 'method.json'; doc.parent.mkdir(); doc.write_text('{}')
    choices = {'source': source, 'source_child': source/'output', 'source_parent': source.parent,
        'private': private, 'private_child': private/'output', 'private_parent': private.parent, 'doc_parent': doc.parent}
    out = choices[kind]; out.mkdir(exist_ok=True)
    with pytest.raises(ValueError): boot.disjoint_output(out, source, [doc], private)
    assert not (out/'failure_report.json').exists()


def test_output_sibling_of_public_documents_is_allowed(tmp_path):
    source = tmp_path/'data'; source.mkdir(); private = tmp_path/'tests'; private.mkdir()
    document = tmp_path/'method.json'; document.write_text('{}')
    out = tmp_path/'output'; out.mkdir()
    assert boot.disjoint_output(out, source, [document], private) == out


@pytest.fixture
def authority(monkeypatch):
    pins = {name: hashlib.sha256(name.encode()).hexdigest() for name in boot.MODULE_ORDER}
    documents = {key: (filename, hashlib.sha256(key.encode()).hexdigest())
                 for key, (filename, _) in boot.DOCUMENT_PINS.items()}
    monkeypatch.setattr(boot, 'PRIVATE_PINS', pins); monkeypatch.setattr(boot, 'DOCUMENT_PINS', documents)
    source, method, schema = (documents[key][1] for key in ('manifest_path', 'method_path', 'schema_path'))
    kernel = pins['reporting_kernel']; bound = []
    reference = types.SimpleNamespace(SOURCE_SHA=source, METHOD_SHA=method, SCHEMA_SHA=schema, REPORTING_SHA=kernel,
        MODULE_PINS={key+'.py': pins[key] for key in ('inspect_structure','source_numerics','reporting_kernel')})
    validator = types.SimpleNamespace(SOURCE_SHA=source, METHOD_SHA=method, SCHEMA_SHA=schema, KERNEL_SHA=kernel,
                                     bind_reporting_kernel=bound.append)
    modules = dict.fromkeys(boot.MODULE_ORDER)
    modules.update(source_reference=reference, verify_artifacts=validator,
                   io_contract=types.SimpleNamespace(json_bytes=lambda raw, cap: json.loads(raw)))
    doc = {'method_path': json.dumps({'task_id':'SOCIALBRAIN-001','source':{'source_manifest_sha256':source}}).encode(),
           'schema_path': json.dumps({'task_id':'SOCIALBRAIN-001','source_manifest_sha256':source,
                                     'method_sha256':method,'reporting_kernel_sha256':kernel}).encode()}
    return dict(modules=modules, document_bytes=doc, payloads={'reporting_kernel':b'authenticated kernel bytes'}), bound


def test_all_authority_pins_agree_before_kernel_binding(authority):
    context, bound = authority; boot._authorize(context)
    assert bound == [context['payloads']['reporting_kernel']]


@pytest.mark.parametrize('kind', ['reference_source','reference_method','reference_schema','reference_kernel',
    'validator_source','validator_method','validator_schema','validator_kernel','dependency','document_source','document_method','document_kernel'])
def test_authority_mismatch_blocks_kernel_binding(authority, kind):
    context, bound = authority
    if kind.startswith(('reference_', 'validator_')):
        owner, which = kind.split('_')
        target = context['modules']['source_reference' if owner == 'reference' else 'verify_artifacts']
        field = {'source':'SOURCE_SHA','method':'METHOD_SHA','schema':'SCHEMA_SHA',
                 'kernel':'REPORTING_SHA' if owner == 'reference' else 'KERNEL_SHA'}[which]
        setattr(target, field, '0'*64)
    elif kind == 'dependency': context['modules']['source_reference'].MODULE_PINS['source_numerics.py'] = '0'*64
    else:
        key = {'document_source':'source_manifest_sha256','document_method':'method_sha256',
               'document_kernel':'reporting_kernel_sha256'}[kind]
        value = json.loads(context['document_bytes']['schema_path']); value[key] = '0'*64
        context['document_bytes']['schema_path'] = json.dumps(value).encode()
    with pytest.raises(ValueError): boot._authorize(context)
    assert bound == []


@pytest.fixture
def scoring_stub():
    calls = []; reference = {'status':'complete','sensitive_values':'never print'}
    def reconstruct(**kwargs): calls.append(('reconstruct', kwargs)); return reference
    def validate(output, observed): calls.append(('validate', output, observed)); return {'status':'ok'}
    context = {'documents':{'manifest_path':'/tests/source_manifest.json','method_path':'/tests/method_contract.json',
                            'schema_path':'/tests/output_schema.json'},
               'modules':{'source_reference':types.SimpleNamespace(reconstruct=reconstruct),
                          'verify_artifacts':types.SimpleNamespace(validate_output_directory=validate)}}
    fake = types.SimpleNamespace(__file__='/tests/grader_bootstrap.py', DATA_DIR='/app/data/socialbrain',
        OUTPUT_DIR='/app/output', PUBLIC_DOCUMENTS=boot.PUBLIC_DOCUMENTS,
        disjoint_output=lambda *args: calls.append(('disjoint',args)) or Path('/app/output'),
        load_private=lambda: calls.append(('load',)) or context,
        recheck_documents=lambda value: calls.append(('recheck',value)))
    return fake, context, calls


def test_production_flow_reconstructs_and_validates_exactly_once(scoring_stub, monkeypatch):
    fake, context, calls = scoring_stub
    for key in ('OUTPUT_DIR','SOURCE_MANIFEST','METHOD_PATH','PYTHONPATH'):
        monkeypatch.setenv(key, '/untrusted/override')
    assert score._score(fake) == {'status':'pass','task_id':'SOCIALBRAIN-001'}
    assert [row[0] for row in calls] == ['disjoint','load','reconstruct','validate','recheck']
    assert calls[2][1] == {'data_dir':'/app/data/socialbrain',**context['documents'],'pilot':False}
    assert calls[3][1] == Path('/app/output') and calls[3][2]['status'] == 'complete'


@pytest.mark.parametrize('stage', ['reconstruct','validate','recheck'])
def test_production_failure_propagates_without_retry_or_acceptance_cache(scoring_stub, stage):
    fake, context, calls = scoring_stub
    def fail(*args, **kwargs): calls.append(('failed',stage)); raise ValueError('manufactured failure')
    if stage == 'reconstruct': context['modules']['source_reference'].reconstruct = fail
    elif stage == 'validate': context['modules']['verify_artifacts'].validate_output_directory = fail
    else: fake.recheck_documents = fail
    with pytest.raises(ValueError, match='manufactured failure'): score._score(fake)
    assert calls[-1] == ('failed',stage)
    assert sum(row[0] == 'failed' for row in calls) == 1


def test_bootstrap_same_buffer_pin_ignores_cached_module(tmp_path, monkeypatch):
    path = tmp_path/'grader_bootstrap.py'; raw = b'VALUE = 7\n'; path.write_bytes(raw)
    monkeypatch.setattr(score, '__file__', str(tmp_path/'score_submission.py'))
    monkeypatch.setattr(score, 'BOOTSTRAP_SHA', hashlib.sha256(raw).hexdigest())
    monkeypatch.setitem(sys.modules, 'grader_bootstrap', types.SimpleNamespace(VALUE=-999))
    assert score._load_bootstrap().VALUE == 7
    path.write_bytes(b'VALUE = 8\n')
    with pytest.raises(ValueError, match='bootstrap_sha256'): score._load_bootstrap()


def test_unfrozen_bootstrap_pin_fails_before_read(monkeypatch):
    monkeypatch.setattr(score, 'BOOTSTRAP_SHA', None)
    with pytest.raises(ValueError, match='unfrozen_bootstrap_pin'): score._load_bootstrap()


def test_score_requires_isolation_before_bootstrap(monkeypatch):
    monkeypatch.setattr(score, 'sys', types.SimpleNamespace(flags=types.SimpleNamespace(isolated=0)))
    monkeypatch.setattr(score, '_load_bootstrap', lambda: pytest.fail('bootstrap reached'))
    with pytest.raises(ValueError, match='isolated_python_required'): score.score()


def test_cli_failure_is_nonzero_and_does_not_print_source_values(monkeypatch, capsys):
    def fail(): raise ValueError('private numerical value must not be printed')
    monkeypatch.setattr(score, 'score', fail)
    assert score.main([]) == 1
    assert json.loads(capsys.readouterr().out) == {'status':'fail','error_type':'ValueError'}


def test_cli_success_prints_only_scoring_status(monkeypatch, capsys):
    monkeypatch.setattr(score, 'score', lambda: {'status':'pass','task_id':'SOCIALBRAIN-001'})
    assert score.main([]) == 0
    assert json.loads(capsys.readouterr().out) == {'status':'pass','task_id':'SOCIALBRAIN-001'}


def test_cli_arguments_cannot_override_paths(monkeypatch, capsys):
    monkeypatch.setattr(score, 'score', lambda: pytest.fail('scoring reached'))
    assert score.main(['--output','/untrusted']) == 1
    assert json.loads(capsys.readouterr().out)['error_type'] == 'UnexpectedArguments'
