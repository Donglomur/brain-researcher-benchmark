"""Manufactured source bundles and real public math only; never originals."""
from dataclasses import replace
import csv
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess

import numpy as np
import pytest

import compute as m
from test_source_reader import case, repin


def sha(raw): return hashlib.sha256(raw).hexdigest()


@pytest.fixture
def writer_case(case, tmp_path):
    kernel = Path(os.environ.get('FCSTAB_TEST_KERNEL', Path(__file__).resolve().parents[1]/'environment'/'selection_kernel.py')).absolute()
    schema = dict(task_id='FCSTAB-001', files=list(m.FILES), limits=dict(m.CAPS))
    method = dict(task_id='FCSTAB-001', status='manufactured_only')
    for name, data in [('method_contract.json', method), ('output_schema.json', schema)]:
        (case['docs']/name).write_bytes(json.dumps(data).encode())
    case['policy'] = replace(case['policy'], method_sha=sha((case['docs']/'method_contract.json').read_bytes()),
                            schema_sha=sha((case['docs']/'output_schema.json').read_bytes()), kernel_sha=sha(kernel.read_bytes()))
    case.update(kernel=kernel, output=tmp_path/'results'/'output', schema=schema)
    return case


def run(case):
    return m._run(case['root'], case['docs']/'source_manifest.json', case['docs']/'method_contract.json',
                  case['docs']/'output_schema.json', case['docs']/'subject_ids.txt', case['kernel'],
                  case['output'], policy=case['policy'])


def load_outputs(case):
    root = case['output']
    with np.load(root/'connectivity.npz', allow_pickle=False) as data:
        arrays = {key: data[key] for key in data.files}
    with (root/'stability.csv').open(newline='') as stream: rows = list(csv.DictReader(stream))
    return arrays, rows, json.loads((root/'selection_evidence.json').read_text()), json.loads((root/'summary.json').read_text())


def alter_schema(case, key, value):
    case['schema']['limits'][key] = value
    raw = json.dumps(case['schema']).encode(); (case['docs']/'output_schema.json').write_bytes(raw)
    case['policy'] = replace(case['policy'], schema_sha=sha(raw))


def test_complete_five_files_full_precision_and_undefined_statuses(writer_case):
    c = writer_case; before = {str(p):p.read_bytes() for p in c['root'].rglob('*') if p.is_file()}
    report = run(c); arrays, rows, evidence, summary = load_outputs(c)
    assert report['status'] == 'complete' and set(p.name for p in c['output'].iterdir()) == set(m.FILES)
    assert report['n_subjects'] == 2 and report['n_edges'] == 1
    assert set(arrays) == {'subject_ids','segment_ids','roi_ids','common_roi_mask','edge_roi_i','edge_roi_j','fisher_z'}
    assert arrays['subject_ids'].tolist() == ['50003','50004']
    assert arrays['segment_ids'].tolist() == ['first','second','full']
    assert arrays['common_roi_mask'].tolist() == [True,False,True] and arrays['fisher_z'].shape == (2,3,1)
    assert arrays['edge_roi_i'].tolist() == [1] and arrays['edge_roi_j'].tolist() == [3]
    assert list(rows[0]) == list(m.CSV_COLUMNS) and all(int(r['n_edges']) == 1 for r in rows)
    assert evidence['status'] == summary['status'] == 'complete' and evidence['seed'] == 0
    assert evidence['pins'] == summary['pins']
    assert evidence['schema_version'] == 'fcstab-selection-v3' and summary['schema_version'] == 'fcstab-summary-v3'
    assert len(summary['cohort']) == 2 and len(summary['source_files']) == 4
    observed = summary['source_observed']
    assert observed['total_frames'] == 10 and observed['n_phenotype_rows'] == 5
    assert (observed['n_named_phenotype_rows'], observed['n_no_filename_rows'], observed['n_selected_derivatives']) == (4,1,2)
    assert observed['persons']['Pitt_0050003']['segment_support']['first'] == [True,False,True]
    assert observed['persons']['Pitt_0050003']['exact_constant_mask']['full'] == [False,True,False]
    assert observed['clock'] == dict(TR_verified=False,frame_order='original source row order')
    for group in summary['selection_schemes'].values():
        assert group['inference_status'] == 'source_zero_variance'
        assert group['t'] is group['p'] is group['ci95_lo'] is group['ci95_hi'] is None
    assert summary['reliability']['edge_pearson']['mean'] is None
    assert summary['reliability']['edge_pearson']['n_undefined'] == 2
    assert summary['equivalence']['equivalent_within_margin'] is None
    assert all(Path(path).read_bytes() == raw for path, raw in before.items())
    assert report['total_output_bytes'] == sum(p.stat().st_size for p in c['output'].iterdir())
    assert 'not ICC' in (c['output']/'findings.md').read_text()


def test_own_generated_rows_and_summary_roundtrip(writer_case):
    run(writer_case); arrays, rows, evidence, summary = load_outputs(writer_case)
    kernel = m.source_reader.load_kernel(writer_case['kernel'], writer_case['policy'].kernel_sha)
    pairs = np.column_stack([arrays['edge_roi_i'], arrays['edge_roi_j']])
    replay = kernel.analyze(arrays['fisher_z'], arrays['fisher_z'], arrays['subject_ids'].tolist(), pairs)
    for reported, actual in zip(rows, replay['rows']):
        assert reported['subject_id'] == actual['subject_id']
        for key in m.CSV_COLUMNS[2:]: assert float(reported[key]) == actual[key]
    assert summary['selection_schemes'] == replay['summaries']['selection_schemes']
    assert evidence['subjects'] == [dict(subject_id=sid, **replay['evidence'][sid]) for sid in arrays['subject_ids'].tolist()]


def test_mathematically_finite_active_case_uses_full_kernel_without_stubs(writer_case):
    c = writer_case
    # Both persons have three common columns; second-half patterns differ.
    values = [np.array([[0,1,2],[1,3,0],[2,0,1],[3,2,4],[4,1,2]], float),
              np.array([[0,2,1],[2,0,3],[1,1,0],[4,3,1],[3,1,4]], float)]
    for record, raw in zip([r for r in c['manifest']['files'] if r['role']=='roi_timeseries'], values):
        body = '#1\t#2\t#3\n'+'\n'.join(' '.join(repr(v) for v in row.tolist()) for row in raw)+'\n'
        repin(c, record['path'], body.encode())
    report = run(c); arrays, _, evidence, summary = load_outputs(c)
    assert report['n_edges'] == 3 and arrays['common_roi_mask'].all()
    assert np.isfinite(arrays['fisher_z']).all()
    assert len(evidence['subjects']) == 2 and set(summary['selection_schemes']) == set(m.source_reader.load_kernel(c['kernel'], c['policy'].kernel_sha).SCHEMES)
    assert all(g['n'] == 2 and np.isfinite(g['delta_mean']) for g in summary['selection_schemes'].values())


def test_existing_empty_real_directory_supported(writer_case):
    writer_case['output'].mkdir(parents=True)
    inode = writer_case['output'].stat().st_ino
    assert run(writer_case)['status'] == 'complete'
    assert writer_case['output'].stat().st_ino == inode


@pytest.mark.parametrize('kind', ['file','nested','failure','dangling_failure','symlink_output','ancestor_link'])
def test_preexisting_output_never_overwritten_or_cleaned(writer_case, kind):
    c=writer_case; c['output'].parent.mkdir(parents=True)
    if kind == 'symlink_output': c['output'].symlink_to(c['root'])
    elif kind == 'ancestor_link':
        alias = c['output'].parent/'alias'; alias.symlink_to(c['root']); c['output'] = alias/'new-output'
    else:
        c['output'].mkdir()
        if kind == 'file': (c['output']/'keep').write_bytes(b'original')
        elif kind == 'nested': (c['output']/'nested').mkdir()
        elif kind == 'failure': (c['output']/'failure_report.json').write_bytes(b'original failure')
        else: (c['output']/'failure_report.json').symlink_to('/absent')
    with pytest.raises(ValueError): run(c)
    if kind == 'file': assert (c['output']/'keep').read_bytes() == b'original'
    if kind == 'failure': assert (c['output']/'failure_report.json').read_bytes() == b'original failure'
    if kind == 'dangling_failure': assert (c['output']/'failure_report.json').is_symlink()
    if kind == 'ancestor_link': assert not (c['root']/'new-output').exists()


@pytest.mark.parametrize('target', ['source_child','source_parent','method','kernel','code'])
def test_protected_path_overlap_before_io(writer_case, monkeypatch, target):
    c=writer_case
    c['output'] = {'source_child':c['root']/'output','source_parent':c['root'].parent,'method':c['docs']/'method_contract.json',
                   'kernel':c['kernel'],'code':Path(m.__file__).absolute().parent}[target]
    monkeypatch.setattr(m.source_reader, 'load', lambda *a, **kw: pytest.fail('source loading'))
    with pytest.raises(ValueError): run(c)
    assert not (c['root']/'output').exists()


@pytest.mark.parametrize('pin', ['method_sha','schema_sha','kernel_sha'])
def test_unfrozen_pins_fail_with_marker_before_sources(writer_case, monkeypatch, pin):
    writer_case['policy'] = replace(writer_case['policy'], **{pin:None})
    monkeypatch.setattr(m.source_reader, 'load', lambda *a, **kw: pytest.fail('source loading'))
    with pytest.raises(ValueError, match='unfrozen authority'): run(writer_case)
    marker=json.loads((writer_case['output']/'failure_report.json').read_text())
    assert marker['phase']=='authority_pins' and marker['outputs_complete'] is False


@pytest.mark.parametrize('field', ['method_sha','schema_sha','kernel_sha'])
def test_wrong_pins_cannot_publish_success(writer_case, field):
    writer_case['policy'] = replace(writer_case['policy'], **{field:'0'*64})
    with pytest.raises(ValueError): run(writer_case)
    assert (writer_case['output']/'failure_report.json').is_file()
    assert not (writer_case['output']/'summary.json').exists()


@pytest.mark.parametrize('cap', ['npz_stored_bytes','npz_expanded_bytes','csv_bytes','selection_evidence_json_bytes',
                                'summary_json_bytes','findings_bytes','entire_output_tree_bytes','output_entries','json_depth'])
def test_caps_fail_preserving_failure(writer_case, cap):
    alter_schema(writer_case, cap, 1)
    with pytest.raises(ValueError): run(writer_case)
    assert (writer_case['output']/'failure_report.json').is_file()


@pytest.mark.parametrize('bad', [True, 0, -1, 1.5, 10**10])
def test_schema_caps_typed_and_bounded(writer_case, bad):
    alter_schema(writer_case, 'summary_json_bytes', bad)
    with pytest.raises(ValueError): run(writer_case)
    assert (writer_case['output']/'failure_report.json').is_file()


def test_insufficient_common_support_is_failed_precondition(writer_case):
    raw = b'#1\t#2\t#3\n0 1 1\n1 1 1\n2 1 1\n3 1 1\n4 1 1\n'
    for row in writer_case['manifest']['files']:
        if row['role']=='roi_timeseries': repin(writer_case, row['path'], raw)
    with pytest.raises(ValueError, match='fewer than two common'): run(writer_case)
    marker=json.loads((writer_case['output']/'failure_report.json').read_text())
    assert marker['phase']=='source_support_and_Fisher'


@pytest.mark.parametrize('kind', ['late_write','late_entry','late_marker','late_dangling_marker','late_same_size_rewrite'])
def test_late_failures_never_look_complete(writer_case, monkeypatch, kind):
    real=m.publish
    def publish(root, identity, name, raw, cap):
        if kind=='late_write' and name=='findings.md': raise OSError('manufactured late write')
        real(root, identity, name, raw, cap)
        if name=='findings.md':
            if kind=='late_entry': (root/'unexpected').write_bytes(b'late')
            elif kind=='late_marker': (root/'failure_report.json').write_bytes(b'preserved late marker')
            elif kind=='late_dangling_marker': (root/'failure_report.json').symlink_to('/absent')
            elif kind=='late_same_size_rewrite':
                target=root/'summary.json'; target.write_bytes(b'x'*target.stat().st_size)
    monkeypatch.setattr(m, 'publish', publish)
    with pytest.raises((OSError, ValueError)): run(writer_case)
    root=writer_case['output']
    assert (root/'connectivity.npz').is_file() and os.path.lexists(root/'failure_report.json')
    if kind=='late_marker': assert (root/'failure_report.json').read_bytes()==b'preserved late marker'
    elif kind=='late_dangling_marker': assert (root/'failure_report.json').is_symlink()


def test_repeat_attempt_preserves_success_bytes(writer_case):
    run(writer_case); before={p.name:p.read_bytes() for p in writer_case['output'].iterdir()}
    with pytest.raises(ValueError): run(writer_case)
    assert {p.name:p.read_bytes() for p in writer_case['output'].iterdir()}==before


def test_cli_uses_explicit_paths_and_output_environment(monkeypatch, tmp_path, capsys):
    calls=[]
    monkeypatch.setenv('OUTPUT_DIR', str(tmp_path/'out')); monkeypatch.setenv('DATA_DIR', str(tmp_path/'data'))
    monkeypatch.setattr(m, 'run', lambda **kwargs: calls.append(kwargs) or dict(status='complete'))
    assert m.main(['--kernel-path',str(tmp_path/'kernel')]) == 0
    assert calls[0]['output_dir']==str(tmp_path/'out') and calls[0]['data_dir']==str(tmp_path/'data')
    assert calls[0]['kernel_path']==str(tmp_path/'kernel')
    assert json.loads(capsys.readouterr().out)==dict(status='complete')


def test_cli_failure_exit_is_nonzero(monkeypatch, capsys):
    def fail(**unused): raise ValueError('manufactured')
    monkeypatch.setattr(m, 'run', fail)
    assert m.main([])==1 and json.loads(capsys.readouterr().out)['status']=='failed'


def test_module_import_does_not_read_sources_or_create_output(monkeypatch, tmp_path):
    monkeypatch.setenv('OUTPUT_DIR', str(tmp_path/'untouched'))
    monkeypatch.setattr(m.source_reader, 'load', lambda *a, **kw: pytest.fail('source read on import'))
    monkeypatch.setattr(m.source_reader, 'load_kernel', lambda *a, **kw: pytest.fail('kernel read on import'))
    spec=importlib.util.spec_from_file_location('_fcstab_compute_import_fixture', m.__file__)
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    assert not (tmp_path/'untouched').exists()


@pytest.mark.parametrize('forwarded', [[], ['--output-dir','/evidence/with space'], ['--kernel-path','/app/kernel.py','--data-dir','/app/data']])
def test_wrapper_forwards_arguments_to_isolated_bootstrap(tmp_path, forwarded):
    wrapper=tmp_path/'solve.sh'
    wrapper.write_bytes((Path(__file__).resolve().parents[1]/'solution'/'solve.sh').read_bytes())
    (tmp_path/'compute.py').write_text(
        'import json, sys\n'
        'def main():\n'
        '    print(json.dumps({"isolated":sys.flags.isolated,"no_pyc":sys.dont_write_bytecode,"argv":sys.argv[1:]}))\n'
        '    return 0\n')
    # Only the fabricated module exists beside this wrapper; no source reader,
    # original-source mount, or task compute module is reachable via its path.
    result=subprocess.run(['bash',str(wrapper),*forwarded],cwd=tmp_path,
                          capture_output=True,check=True,timeout=10)
    assert json.loads(result.stdout)==dict(isolated=1,no_pyc=True,argv=forwarded)


def test_wrapper_isolated_python_can_import_only_explicit_sibling(tmp_path):
    destination=tmp_path/'manufactured solution'; destination.mkdir()
    wrapper=destination/'solve.sh'
    wrapper.write_bytes((Path(__file__).resolve().parents[1]/'solution'/'solve.sh').read_bytes())
    (destination/'source_reader.py').write_text('VALUE = "manufactured_sibling"\n')
    (destination/'compute.py').write_text(
        'import json, sys, source_reader\n'
        'def main():\n'
        '    print(json.dumps({"isolated":sys.flags.isolated,"sibling":source_reader.VALUE,"argv":sys.argv[1:]}))\n'
        '    return 0\n')
    result=subprocess.run(['bash',str(wrapper),'--output-dir','/unused manufactured'],
                          cwd=tmp_path,capture_output=True,check=True,timeout=10)
    assert json.loads(result.stdout)==dict(isolated=1,sibling='manufactured_sibling',argv=['--output-dir','/unused manufactured'])
