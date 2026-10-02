"""Writer/path/CLI fixtures on manufactured Reference dictionaries only.

Assignment is explicitly stubbed here; generator conformance is covered by the
separately qualified test_oracle_core, not inferred from these IO tests.
"""
import csv
import json
import os
from pathlib import Path
import subprocess
import warnings

import numpy as np
import pytest

import compute


def basis():
    ids=np.arange(1,401,dtype=np.int64)
    points=np.column_stack((ids,ids+2,ids+5)).astype(float)
    points=100*points/np.linalg.norm(points,axis=1)[:,None]
    return dict(parcel_ids=ids,labels=[f'parcel{i}' for i in ids],networks=['Vis']*400,
                hemisphere=np.repeat([0,1],200),support_n=np.ones(400,dtype=np.int64),
                support_sha256=['a'*64]*400,centroids=points,
                maps=np.column_stack((np.sin(ids/13),np.cos(ids/11))),source_observed={'synthetic':True},
                source_files=[dict(path='synthetic',role='notice',size_bytes=1,sha256='d'*64)],
                pins=dict(source_manifest_sha256='1'*64,method_contract_sha256='2'*64,output_schema_sha256='3'*64))


def fake_spins(xyz,hemi,ids,*,method,seed,count):
    # Honest writer fixture, not a stand-in for scientific generator validation.
    return dict(parcel_ids=ids.copy(),rotation_ids=np.arange(count,dtype=np.int64),centroids=xyz.copy(),
                hemisphere=hemi.copy(),spin_parcel_ids=np.tile(ids[:,None],(1,count)),
                attempts=np.ones(count,dtype=np.int64),retained_duplicate=np.ones(count,dtype=bool),
                assignment_cost=np.zeros((400,count)))


def setup(tmp_path,monkeypatch):
    data=tmp_path/'inputs';data.mkdir()
    docs=[]
    for name in ('source','method','schema'):
        path=tmp_path/(name+'.json');path.write_text('{}');docs.append(path)
    args=compute.parser().parse_args(['--data-dir',str(data),'--manifest-path',str(docs[0]),
        '--method-path',str(docs[1]),'--schema-path',str(docs[2]),'--output-dir',str(tmp_path/'output'),
        '--private-dir',str(tmp_path/'private'),'--n-permutations','100'])
    reference=basis()
    monkeypatch.setattr(compute.source,'load_sources',lambda *a:reference)
    monkeypatch.setattr(compute.core,'generate_spins',fake_spins)
    return args,reference


def test_complete_five_artifact_writer(tmp_path,monkeypatch):
    args,reference=setup(tmp_path,monkeypatch);result=compute.run(args)
    output=Path(args.output_dir)
    assert set(p.name for p in output.iterdir())==set(compute.FILES)
    assert result['status']=='complete' and result['n_parcels']==400
    with (output/'parcels.csv').open() as handle:rows=list(csv.DictReader(handle))
    assert len(rows)==400 and set(rows[0])==set(compute.FIELDS)
    np.testing.assert_array_equal([[float(row['gradient2']),float(row['thickness'])] for row in rows],reference['maps'])
    with np.load(output/'spin_evidence.npz',allow_pickle=False) as values:
        assert set(values)==set(compute.ARRAYS)
        assert values['spin_parcel_ids'].shape==(400,100)
    results=json.loads((output/'results.json').read_text())
    assert results['n_null_defined']==100 and results['p_spin_numerator']==101 and results['p_spin_denominator']==101
    metadata=json.loads((output/'run_metadata.json').read_text())
    assert metadata['status']=='ok' and metadata['warnings']==[]
    assert metadata['analysis_observed']['remapped_gradient']==dict(n_expected=100,n_active=100)
    assert set(p.name for p in Path(args.private_dir).iterdir())=={'source_primitives.npz','source_identity.json','spin_diagnostics.npz','report.json'}


@pytest.mark.parametrize('method',['original','vasa','hungarian'])
def test_declared_alternatives_reach_generator(tmp_path,monkeypatch,method):
    args,_=setup(tmp_path,monkeypatch);args.spin_method=method;args.seed=2**32-1;seen=[]
    def generate(*a,**kw):seen.append(kw);return fake_spins(*a,**kw)
    monkeypatch.setattr(compute.core,'generate_spins',generate)
    result=compute.run(args)
    assert seen==[dict(method=method,seed=2**32-1,count=100)]
    assert result['spin_method']==method and result['seed']==2**32-1


def test_captured_actual_warning_is_public_and_private(tmp_path,monkeypatch):
    args,_=setup(tmp_path,monkeypatch)
    def generate(*a,**kw):warnings.warn('manufactured warning',UserWarning);return fake_spins(*a,**kw)
    monkeypatch.setattr(compute.core,'generate_spins',generate)
    compute.run(args)
    for path in (Path(args.output_dir)/'run_metadata.json',Path(args.private_dir)/'report.json'):
        assert json.loads(path.read_text())['warnings']==['manufactured warning']


@pytest.mark.parametrize('columns',[(0,),(1,),(0,1)])
def test_inactive_maps_complete_with_null_inference(tmp_path,monkeypatch,columns):
    args,reference=setup(tmp_path,monkeypatch)
    reference['maps'][:,columns]=.37
    compute.run(args)
    results=json.loads((Path(args.output_dir)/'results.json').read_text())
    assert results['status']=='complete' and results['inference_status']=='incomplete_support'
    assert results['p_spin'] is None and results['n_exceedances'] is None and results['p_spin_denominator']==101
    assert 'undefined' in (Path(args.output_dir)/'findings.md').read_text()


@pytest.mark.parametrize('stage',['source','generator','late_report'])
def test_failures_are_preserved_even_after_metadata_success(tmp_path,monkeypatch,stage):
    args,_=setup(tmp_path,monkeypatch)
    def fail(*a,**kw):raise RuntimeError('manufactured failure')
    if stage=='source':monkeypatch.setattr(compute.source,'load_sources',fail)
    elif stage=='generator':monkeypatch.setattr(compute.core,'generate_spins',fail)
    else:
        original=compute.write_json
        def writer(path,document):
            if path.name=='report.json':fail()
            original(path,document)
        monkeypatch.setattr(compute,'write_json',writer)
    with pytest.raises(RuntimeError,match='manufactured'):compute.run(args)
    for root in (Path(args.output_dir),Path(args.private_dir)):
        assert json.loads((root/'failure_report.json').read_text())['status']=='failed'
    if stage!='source':assert (Path(args.private_dir)/'source_primitives.npz').is_file()
    if stage=='late_report':assert json.loads((Path(args.output_dir)/'run_metadata.json').read_text())['status']=='ok'


@pytest.mark.parametrize('case',['output_exists','private_exists','equal','nested','source_nested','source_parent','document_path','code_nested','parent_symlink','output_symlink','relative','dotdot'])
def test_path_guards_precede_source_and_directory_mutation(tmp_path,monkeypatch,case):
    args,_=setup(tmp_path,monkeypatch)
    if case=='output_exists':Path(args.output_dir).mkdir()
    elif case=='private_exists':Path(args.private_dir).mkdir()
    elif case=='equal':args.private_dir=args.output_dir
    elif case=='nested':args.private_dir=str(Path(args.output_dir)/'nested')
    elif case=='source_nested':args.output_dir=str(Path(args.data_dir)/'nested')
    elif case=='source_parent':args.output_dir=str(tmp_path)
    elif case=='document_path':args.output_dir=args.method_path
    elif case=='code_nested':args.output_dir=str(Path(compute.__file__).absolute().parent/'forbidden')
    elif case=='parent_symlink':
        (tmp_path/'link').symlink_to(tmp_path/'inputs',target_is_directory=True);args.output_dir=str(tmp_path/'link'/'nested')
    elif case=='output_symlink':Path(args.output_dir).symlink_to(tmp_path/'absent')
    elif case=='relative':args.output_dir='relative-output'
    elif case=='dotdot':args.output_dir=str(tmp_path)+'/inputs/../out'
    before=sorted(str(p.relative_to(tmp_path)) for p in tmp_path.rglob('*'))
    monkeypatch.setattr(compute.source,'load_sources',lambda *a:pytest.fail('source accessed after invalid path'))
    with pytest.raises(ValueError):compute.run(args)
    assert sorted(str(p.relative_to(tmp_path)) for p in tmp_path.rglob('*'))==before


def test_no_overwrite_after_complete_success(tmp_path,monkeypatch):
    args,_=setup(tmp_path,monkeypatch);compute.run(args)
    before={p.name:p.read_bytes() for p in Path(args.output_dir).iterdir()}
    with pytest.raises(ValueError,match='fresh exclusive'):compute.run(args)
    assert {p.name:p.read_bytes() for p in Path(args.output_dir).iterdir()}==before


@pytest.mark.parametrize('field,value',[('n_permutations',99),('n_permutations',4097),('seed',-1),('spin_method','shuffle')])
def test_configuration_rejects_before_output_creation(tmp_path,monkeypatch,field,value):
    args,_=setup(tmp_path,monkeypatch);setattr(args,field,value)
    with pytest.raises(ValueError):compute.run(args)
    assert not Path(args.output_dir).exists() and not Path(args.private_dir).exists()


def test_default_and_environment_paths(monkeypatch):
    monkeypatch.setenv('OUTPUT_DIR','/manufactured/output');monkeypatch.setenv('DATA_DIR','/manufactured/source')
    args=compute.parser().parse_args([])
    assert (args.spin_method,args.seed,args.n_permutations)==('original',0,1000)
    assert args.output_dir=='/manufactured/output' and args.data_dir=='/manufactured/source'


def test_real_wrapper_print_contract_only(tmp_path):
    script=Path(compute.__file__).with_name('solve.sh')
    result=subprocess.run(['bash',str(script),'--print-contract'],cwd=tmp_path,capture_output=True,text=True,timeout=20,check=True)
    doc=json.loads(result.stdout)
    assert doc['task_id']=='MAPREL-001' and doc['default_n']==1000 and len(doc['artifacts'])==5
    assert not result.stderr and list(tmp_path.iterdir())==[]
