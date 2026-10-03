import copy
import io
import json
import os
from pathlib import Path
import zipfile
import numpy as np
import pytest

@pytest.fixture
def bundle(modules,manufactured,tmp_path):
    ref=modules['source_reference'].reconstruct(manufactured['data'],manufactured['documents'])
    path=modules['writer_v2'].write(ref,tmp_path/'output',protected=(manufactured['data'],manufactured['documents']))
    return ref,path

def test_roundtrip_proof(modules,bundle):
    ref,path=bundle
    assert modules['proof_v2'].validate_output_directory(path,ref)['status']=='verified'

def test_coherent_axes_rows_metadata_permutations(modules,bundle):
    ref,path=bundle;actual=modules['artifact_reader'].read_output(path);a=actual['arrays']
    ui=np.arange(len(a['unit_ids']))[::-1];bi=np.arange(20)[::-1];di=np.arange(300)[::-1]
    a['unit_ids']=a['unit_ids'][ui];a['bin_ids']=a['bin_ids'][bi];a['draw_ids']=a['draw_ids'][di]
    a['occupancy_seconds']=a['occupancy_seconds'][bi]
    a['raw_counts']=a['raw_counts'][np.ix_(ui,bi)]
    a['shifted_counts']=a['shifted_counts'][np.ix_(ui,di,bi)]
    for key in ('shift_offsets_seconds','shift_defined'):a[key]=a[key][np.ix_(ui,di)]
    actual['rows'].reverse();actual['metadata']['all_units'].reverse()
    actual['metadata']['harmless_software']={'version':'different descriptive text'}
    actual['findings']='A different honest interpretation, without required keywords.'
    assert modules['proof_v2'].verify(actual,ref)['status']=='verified'

def test_six_decimal_derived_receipts_own_headline(modules,bundle):
    ref,path=bundle;actual=modules['artifact_reader'].read_output(path);rows=[]
    for row in actual['rows']:
        numeric=dict(row);numeric['n_spikes']=int(row['n_spikes'])
        for key in modules['proof_v2'].FLOAT_FIELDS:
            row[key]=format(float(row[key]),'.6f') if row[key] else ''
            numeric[key]=float(row[key]) if row[key] else None
        rows.append(numeric)
    actual['results']=modules['information_kernel'].summarize(rows)
    assert modules['proof_v2'].verify(actual,ref)['status']=='verified'

def test_accepted_occupancy_drives_own_tie_p_not_canonical_endpoint(modules,bundle,tmp_path):
    ref,_=bundle;ref=copy.deepcopy(ref);a=ref['arrays'];n=len(a['unit_ids'])
    a['occupancy_seconds']=np.r_[100.,100.,np.zeros(18)]
    a['raw_counts'][:]=0;a['raw_counts'][:,0]=100
    a['shifted_counts'][:]=0;a['shifted_counts'][:,:,1]=100;a['shift_defined'][:]=True
    accepted=copy.deepcopy(ref);accepted['arrays']['occupancy_seconds'][0]-=1e-10
    original=modules['information_kernel'].replay(a['occupancy_seconds'],a['raw_counts'],a['shifted_counts'],a['unit_ids'])
    assert original[0]['p_upper']==1.
    path=modules['writer_v2'].write(accepted,tmp_path/'own-output')
    actual=modules['artifact_reader'].read_output(path)
    assert float(actual['rows'][0]['p_upper'])==pytest.approx(1/301)
    assert modules['proof_v2'].verify(actual,ref)['status']=='verified'

@pytest.mark.parametrize('change',['count','null_count','offset','mask','unit_alias','duplicate_unit','lost_unit',
                                   'occupancy','zero_support','headline','source_hash','unit_ledger',
                                   'pilot','fractional_count','false_schema','nonempty_null'])
def test_mutations_rejected(modules,bundle,change):
    ref,path=bundle;actual=modules['artifact_reader'].read_output(path);a=actual['arrays']
    if change=='count':a['raw_counts'][0,0]+=1
    elif change=='null_count':a['shifted_counts'][0,0,0]+=1
    elif change=='offset':a['shift_offsets_seconds'][0,0]+=.01
    elif change=='mask':a['shift_defined'][0,0]=not a['shift_defined'][0,0]
    elif change=='unit_alias':a['unit_ids'][0]='0002'
    elif change=='duplicate_unit':actual['rows'][1]['unit_id']=actual['rows'][0]['unit_id']
    elif change=='lost_unit':actual['rows'].pop()
    elif change=='occupancy':a['occupancy_seconds'][0]+=.1
    elif change=='zero_support':
        ref=copy.deepcopy(ref);ref['arrays']['occupancy_seconds'][0]=0
    elif change=='headline':actual['results']['mean_raw_bits_per_spike']+=.1
    elif change=='source_hash':actual['metadata']['pins']['source_manifest_sha256']='0'*64
    elif change=='unit_ledger':actual['metadata']['all_units'].pop()
    elif change=='pilot':ref=copy.deepcopy(ref);ref['status']='resource_pilot'
    elif change=='fractional_count':a['raw_counts']=a['raw_counts'].astype(float)
    elif change=='false_schema':actual['results']['schema_version']='fake'
    else:actual['rows'][0]['raw_bits_per_spike']=''
    with pytest.raises(ValueError):modules['proof_v2'].verify(actual,ref)

def test_zero_eligible_honest_output(modules,bundle,tmp_path):
    ref,_=bundle;ref=copy.deepcopy(ref);a=ref['arrays']
    for key in ('unit_ids','raw_counts','shifted_counts','shift_offsets_seconds','shift_defined'):a[key]=a[key][:0]
    for row in ref['all_units']:
        if row['eligible']:row['eligible']=False;row['reason']='insufficient_spikes'
    path=modules['writer_v2'].write(ref,tmp_path/'empty')
    actual=modules['artifact_reader'].read_output(path)
    assert actual['results']['status']=='no_eligible_units'
    assert actual['results']['mean_raw_bits_per_spike'] is None
    assert modules['proof_v2'].verify(actual,ref)['status']=='verified'

def test_tolerance_does_not_relax_probability_domain(modules,bundle,monkeypatch):
    ref,path=bundle;actual=modules['artifact_reader'].read_output(path)
    replay=modules['information_kernel'].replay(
        ref['arrays']['occupancy_seconds'],ref['arrays']['raw_counts'],
        ref['arrays']['shifted_counts'],ref['arrays']['unit_ids'])
    for row in replay:row['p_upper']=1.
    monkeypatch.setattr(modules['information_kernel'],'replay',lambda *a,**k:copy.deepcopy(replay))
    for row in actual['rows']:row['p_upper']='1.0000005'
    with pytest.raises(ValueError,match='probability_domain'):
        modules['proof_v2'].verify(actual,ref)

@pytest.mark.parametrize('kind',['symlink','directory','failure_marker','too_many_files','missing'])
def test_output_inventory_guards(modules,bundle,kind):
    ref,path=bundle
    if kind=='symlink':(path/'extra').symlink_to(path/'results.json')
    elif kind=='directory':(path/'extra').mkdir()
    elif kind=='failure_marker':(path/'failure_report.json').symlink_to('/does/not/exist')
    elif kind=='too_many_files':
        for i in range(65):(path/str(i)).write_text('')
    else:(path/'results.json').unlink()
    with pytest.raises(ValueError):modules['artifact_reader'].read_output(path)

def test_harmless_regular_extra_allowed(modules,bundle):
    ref,path=bundle;(path/'notes.txt').write_text('Harmless extra.')
    assert modules['proof_v2'].validate_output_directory(path,ref)['status']=='verified'

def test_late_output_same_size_rewrite(modules,bundle):
    ref,path=bundle;actual=modules['artifact_reader'].read_output(path)
    f=path/'findings.md';raw=f.read_bytes();f.write_bytes(raw.replace(b'Mouse',b'MOUSE',1))
    with pytest.raises(ValueError):modules['artifact_reader'].recheck(actual)

@pytest.mark.parametrize('raw',[b'a,a\n1,2\n',b'unit_id\n1\n',b'',b'unit_id,\n1,2\n'])
def test_csv_bad_headers(modules,raw):
    with pytest.raises(ValueError):modules['artifact_reader'].csv_bytes(raw)

@pytest.mark.parametrize('v',[True,'nan','inf','1e999','',None])
def test_number_rejects_bad_tokens(modules,v):
    with pytest.raises(ValueError):modules['artifact_reader'].number(v)

@pytest.mark.parametrize('v',[True,'1.5','NaN',str(2**64)])
def test_integer_rejects_bad_tokens(modules,v):
    with pytest.raises(ValueError):modules['artifact_reader'].integer(v)

@pytest.mark.parametrize('kind',['object','nonfinite','structured','dimensions','duplicate','path','zero_width_huge'])
def test_npz_defenses(modules,kind):
    buffer=io.BytesIO()
    if kind=='duplicate':
        arr=io.BytesIO();np.save(arr,np.array([1]))
        with zipfile.ZipFile(buffer,'w') as z:
            z.writestr('x.npy',arr.getvalue());z.writestr('x.npy',arr.getvalue())
    elif kind=='path':
        arr=io.BytesIO();np.save(arr,np.array([1]))
        with zipfile.ZipFile(buffer,'w') as z:z.writestr('../x.npy',arr.getvalue())
    elif kind=='zero_width_huge':
        arr=io.BytesIO();np.lib.format.write_array_header_1_0(arr,{'descr':'|S0','fortran_order':False,'shape':(20000000,)})
        with zipfile.ZipFile(buffer,'w') as z:z.writestr('x.npy',arr.getvalue())
    else:
        values={'object':np.array([object()]),'nonfinite':np.array([np.nan]),
                'structured':np.array([(1,)],dtype=[('a','i4')]),'dimensions':np.zeros((1,1,1,1))}
        np.savez(buffer,x=values[kind])
    with pytest.raises(ValueError):modules['artifact_reader'].npz_bytes(buffer.getvalue())

def test_writer_protected_existing_and_failure(modules,bundle,tmp_path,monkeypatch):
    ref,path=bundle;writer=modules['writer_v2']
    with pytest.raises(ValueError):writer.write(ref,path)
    with pytest.raises(ValueError):writer.write(ref,tmp_path/'nested',protected=(tmp_path,))
    def bad(*a,**k):raise ValueError('manufactured_failure')
    monkeypatch.setattr(modules['information_kernel'],'replay',bad)
    output=tmp_path/'failed'
    with pytest.raises(ValueError):writer.write(ref,output)
    assert json.loads((output/'failure_report.json').read_text())['status']=='failed_precondition'
