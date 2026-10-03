import copy
import io
import json
import os
import zipfile
from decimal import Decimal, localcontext
import h5py
import numpy as np
import pytest

def test_full_manufactured_routes_match(modules,manufactured):
    args=(manufactured['data'],manufactured['documents'])
    a=modules['source_reader'].reconstruct(*args);b=modules['source_reference'].reconstruct(*args)
    for k,v in a['arrays'].items():np.testing.assert_array_equal(v,b['arrays'][k])
    for k in ('status','all_units','source_observed','pins','analysis'):assert a[k]==b[k]
    for result in (a,b):
        json.dumps({key:value for key,value in result.items() if key!='arrays'},allow_nan=False)
    assert list(a['arrays']['unit_ids'])==['2','9']
    assert [r['unit_id'] for r in a['all_units']]==['1','2','9','11']
    assert [r['reason'] for r in a['all_units']]==['non_CA1','included','included','insufficient_spikes']
    # RNG index is original numeric-ID rank, not eligible-row index.
    expected=np.random.Generator(np.random.PCG64(np.random.SeedSequence([20250901,1,0]))).uniform(20,80,300)
    np.testing.assert_array_equal(a['arrays']['shift_offsets_seconds'][0],expected)

def test_pilot_only_metadata_selected_id(modules,manufactured):
    for key in ('source_reader','source_reference'):
        result=modules[key].reconstruct(manufactured['data'],manufactured['documents'],pilot=True)
        assert result['status']=='resource_pilot'
        assert list(result['arrays']['unit_ids'])==['2']
        assert sum(r['reason']=='not_pilot_unit' for r in result['all_units'])==3
        with pytest.raises(ValueError,match='pilot'):modules['writer_v2'].write(result,manufactured['data'].parent/'pilot-output')

def test_gaps_clipping_endpoints_and_no_last_extension(modules):
    t=np.array([0.,.04,.08,.3,.34,.38]);xy=np.array([[0,0],[1,1],[2,2],[3,3],[4,4],[5,5]],float)
    a=modules['source_reader'].geometry(t,xy,[.02,.36])
    b=modules['source_reference'].prepare_tracking(t,xy,[.02,.36],.1)
    np.testing.assert_array_equal(a['occupancy_seconds'],b[5])
    assert a['valid'].tolist()==[True,True,False,True,True]
    assert a['occupancy_seconds'].sum()==pytest.approx(.12)
    spikes=np.array([-.1,0,.02,.04,.079,.08,.15,.3,.34,.359,.36,.38,.4])
    ca=modules['source_reader'].counts(spikes,a);cb=modules['source_reference'].histogram(spikes,b)
    np.testing.assert_array_equal(ca,cb);assert ca.sum()==6

@pytest.mark.parametrize('kind',['constant_x','constant_y','duplicate_clock','nonfinite_clock','no_valid'])
def test_tracking_fail_closed(modules,kind):
    t=np.array([0.,.04,.08]);q=np.array([[0.,0.],[1.,1.],[2.,2.]])
    if kind=='constant_x':q[:,0]=0
    elif kind=='constant_y':q[:,1]=0
    elif kind=='duplicate_clock':t[1]=t[0]
    elif kind=='nonfinite_clock':t[1]=np.nan
    else:q[:]=np.nan
    for call in (lambda:modules['source_reader'].geometry(t,q,[0,.08]),
                 lambda:modules['source_reference'].prepare_tracking(t,q,[0,.08],.1)):
        with pytest.raises(ValueError):call()

def test_nonfinite_endpoint_excludes_adjacent_intervals(modules):
    t=np.arange(8)*.04;q=np.column_stack((np.arange(8),np.arange(8))).astype(float);q[3,0]=np.nan
    a=modules['source_reader'].geometry(t,q,[0,.28])
    b=modules['source_reference'].prepare_tracking(t,q,[0,.28],.1)
    assert a['valid'].tolist()==[True,True,False,False,True,True,True]
    np.testing.assert_array_equal(a['occupancy_seconds'],b[5])

def test_scale_translation_invariant_bins(modules):
    t=np.arange(21)*.04;q=np.column_stack((np.arange(21)%4,np.arange(21)%5)).astype(float)
    a=modules['source_reader'].geometry(t,q,[0,.8])
    b=modules['source_reader'].geometry(t,q*np.array([.01,1e6])+[5.,-100.],[0,.8])
    np.testing.assert_array_equal(a['bins'],b['bins'])
    np.testing.assert_array_equal(a['occupancy_seconds'],b['occupancy_seconds'])

def test_information_decimal_and_uniform(modules):
    k=modules['information_kernel']
    assert k.information(np.array([5,5]),[1,1])==0.
    with localcontext() as c:
        c.prec=70
        expected=sum((Decimal(n)/10)*((Decimal(n)/10)/(Decimal(o)/4)).ln()/Decimal(2).ln()
                     for n,o in zip([9,1],[1,3]))
    assert k.information(np.array([9,1]),[1,3])==pytest.approx(float(expected),abs=1e-14)

def test_information_empty_zero_support_and_type(modules):
    k=modules['information_kernel']
    assert k.information(np.array([0,0]),[1,0]) is None
    with pytest.raises(ValueError):k.information(np.array([0,1]),[1,0])
    with pytest.raises(ValueError):k.information(np.array([1.,0.]),[1,1])
    with pytest.raises(ValueError):k.information(np.array([-1,2]),[1,1])

def test_negative_adjustment_ties_and_undefined(modules):
    k=modules['information_kernel'];o=np.ones(20);raw=np.ones((1,20),dtype='i8')
    shifted=np.zeros((1,300,20),dtype='i8');shifted[:,:,0]=20
    row=k.replay(o,raw,shifted,['1'])[0]
    assert row['shift_adjusted_bits_per_spike']<0 and row['p_upper']==1
    equal=np.repeat(raw[:,None,:],300,axis=1)
    assert k.replay(o,raw,equal,['1'])[0]['p_upper']==1.
    shifted[0,10]=0;row=k.replay(o,raw,shifted,['1'])[0]
    assert row['status']=='undefined_null_draw' and row['null_mean_bits_per_spike'] is None
    assert k.summarize([row])['mean_shift_adjusted_bits_per_spike'] is None
    assert k.summarize([])['status']=='no_eligible_units'

@pytest.mark.parametrize('text',['{"a":1,"a":2}','{"a":NaN}','{"a":1e999}','{"a":[-Infinity]}'])
def test_strict_json(modules,text):
    for key in ('source_io','artifact_reader'):
        fun=modules[key].strict_json if key=='source_io' else modules[key].json_bytes
        with pytest.raises(ValueError):fun(text.encode())

@pytest.mark.parametrize('mutation',['body','extra','internal_manifest','source_symlink','doc_symlink'])
def test_all_source_authentication_before_decode(modules,manufactured,mutation,tmp_path,monkeypatch):
    root=manufactured['data'];docs=manufactured['documents'];source=root/'manufactured.nwb'
    if mutation=='body':
        b=bytearray(source.read_bytes());b[-1]^=1;source.write_bytes(b)
    elif mutation=='extra':(root/'unexpected').write_text('x')
    elif mutation=='internal_manifest':(root/'source_manifest.json').write_text('{}')
    elif mutation=='source_symlink':
        source.unlink();source.symlink_to(docs/'method_contract.json')
    else:
        target=docs/'method_contract.json';target.unlink();target.symlink_to(root/'source_manifest.json')
    monkeypatch.setattr(modules['source_io'],'open_h5',lambda _:pytest.fail('decoder reached before auth'))
    for key in ('source_reader','source_reference'):
        with pytest.raises(ValueError):modules[key].reconstruct(root,docs)

def test_late_source_body_change_detected(modules,manufactured):
    guard=modules['source_io'];context=guard.authenticate(manufactured['data'],manufactured['documents'])
    source=manufactured['data']/'manufactured.nwb';b=bytearray(source.read_bytes());b[-1]^=1;source.write_bytes(b)
    with pytest.raises(ValueError):guard.recheck(context)

def test_hdf5_external_link_and_selected_softlink(modules):
    guard=modules['source_io']
    b=io.BytesIO()
    with h5py.File(b,'w') as f:f['bad']=h5py.ExternalLink('/not/read','data')
    with pytest.raises(ValueError,match='external_link'):guard.open_h5(b.getvalue())
    b=io.BytesIO()
    with h5py.File(b,'w') as f:
        f.create_dataset('real',data=[1]);f['selected']=h5py.SoftLink('/real')
    with guard.open_h5(b.getvalue()) as f:
        with pytest.raises(ValueError,match='nondirect'):guard.direct(f,'/selected')

def test_missing_original_dependency_is_inert_on_import(modules):
    assert callable(modules['source_reader'].reconstruct)
    assert callable(modules['source_reference'].reconstruct)
    assert modules['source_io'].SOURCE_SIZE==61347328
