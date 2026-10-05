"""Synthetic source-layout/filter/support fixtures, not a real-data reference."""
import copy
from pathlib import Path
import sys
import json
import numpy as np
import pytest
from scipy.io import savemat
sys.path.insert(0,str(Path(__file__).parent))
import independent_source as s

@pytest.mark.parametrize('value,expected',[(211,'211'),(211.,'211'),('211','211'),('211.0','211.0'),('label211','label211'),('boundary','boundary')])
def test_type_preservation(value,expected):
    assert s.event_type(value)==expected

@pytest.mark.parametrize('value',[True,211.5,np.nan,[],[1,2]])
def test_malformed_event_type(value):
    with pytest.raises((ValueError,TypeError)):s.event_type(value)

@pytest.mark.parametrize('row,expected',[({},(None,'absent')),({'duration':[]},(None,'empty')),({'duration':np.nan},(None,'nonfinite')),({'duration':42},(42.,'finite'))])
def test_duration_semantics(row,expected):
    assert s.duration(row)==expected

def test_source_ties_to_even():
    rows,_,_=s.source_support(1,[{'type':201,'latency':2.5},{'type':201,'latency':3.5}],100)
    assert [row['event_sample'] for row in rows]==[2,2]

def test_boundary_duplicate_and_edge_markers_preserved():
    events=[{'type':'boundary','latency':.5},{'type':-99,'latency':500.5,'duration':999},
            {'type':'boundary','latency':500.5},{'type':'boundary','latency':1000.5},
            {'type':211,'latency':401},{'type':221,'latency':701},{'type':211,'latency':21}]
    rows,segments,trials=s.source_support(1,events,1000)
    assert len(rows)==7 and len(segments)==2
    assert [(r['start_sample'],r['end_sample_exclusive']) for r in segments]==[(0,500),(500,1000)]
    assert [r['drop_reason'] for r in trials]==['boundary_crossing','','out_of_data']
    assert trials[0]['segment_id']==0 and trials[1]['segment_id']==1
    assert rows[1]['duration_samples']==999 and rows[1]['event_sample'] is None

@pytest.mark.parametrize('latency',[500,500.25,-.5,1001.5,np.nan])
def test_ambiguous_boundary_stops(latency):
    with pytest.raises(ValueError):s.source_support(1,[{'type':'boundary','latency':latency}],1000)

def test_duplicate_target_rounding_stops():
    with pytest.raises(ValueError,match='Duplicate'):
        s.source_support(1,[{'type':211,'latency':201.1},{'type':221,'latency':201.2}],1000)

def test_original_event_order_not_sorted():
    rows,_,_=s.source_support(1,[{'type':201,'latency':400},{'type':201,'latency':200}],1000)
    assert [r['event_sample'] for r in rows]==[399,199]
    assert [r['event_index'] for r in rows]==[0,1]

def test_exact_epoch_half_open_support_edges():
    _,_,trials=s.source_support(1,[{'type':211,'latency':52},{'type':221,'latency':795},{'type':211,'latency':796}],1000)
    assert [r['status'] for r in trials]==['retained','retained','dropped']
    assert trials[1]['epoch_end_sample_exclusive']==1000

def test_fir_formula_symmetry_and_length():
    kernel=s.coefficients()
    def lp(n,frequency):
        t=np.arange(n);h=(2*frequency/256)*np.sinc((2*frequency/256)*(t-(n-1)/2))*(.54-.46*np.cos(2*np.pi*t/(n-1)))
        return h/h.sum()
    manual=-lp(8449,.05);manual[4168:4281]+=lp(113,33.75)
    np.testing.assert_allclose(kernel,manual,atol=1e-15,rtol=1e-14)
    np.testing.assert_allclose(kernel,kernel[::-1],atol=1e-15,rtol=0)

@pytest.mark.parametrize('length',[1,2,51,200,1000])
def test_segment_convolution_direct(length):
    raw=np.random.default_rng(42).normal(size=(3,length))
    _,segments,_=s.source_support(1,[],length)
    actual=s.filter_segments(raw,segments)
    pad=min(8449,length)-1
    referenced=raw[0]-(raw[1]+raw[2])/2
    expected=np.convolve(np.pad(referenced,(pad,pad),mode='edge'),s.coefficients(),'full')[pad+4224:pad+4224+length]
    np.testing.assert_allclose(actual,expected,atol=1e-12,rtol=1e-12)

def test_segment_filter_does_not_bridge_boundary():
    raw=np.zeros((3,600));raw[0,300:]=50
    _,segments,_=s.source_support(1,[{'type':'boundary','latency':300.5}],600)
    actual=s.filter_segments(raw,segments)
    np.testing.assert_allclose(actual[:300],0,atol=1e-12)

def test_nonfinite_readout_fails():
    _,segments,_=s.source_support(1,[],3)
    raw=np.zeros((3,3));raw[0,1]=np.nan
    with pytest.raises(ValueError):s.filter_segments(raw,segments)

def test_constant_epoch_baseline_and_no_condition_failure():
    _,_,trials=s.source_support(1,[{'type':211,'latency':201},{'type':221,'latency':601}],1000)
    curves,row,epochs,indices=s.measurements(1,np.full(1000,7.),trials)
    assert row['n400_uv']==0 and np.all(epochs==0)
    assert [r['baseline_uv'] for r in trials]==[7.,7.]
    with pytest.raises(ValueError,match='missing retained condition'):
        s.measurements(1,np.zeros(1000),copy.deepcopy(trials[:1]))

def test_builder_no_oracle_import_or_network():
    text=(Path(__file__).parent/'independent_source.py').read_text()+(Path(__file__).parent/'build_reference.py').read_text()
    assert 'solution.compute' not in text and 'requests.' not in text and 'urllib' not in text

def test_source_pair_channel_fast_fortran_layout(tmp_path):
    # Artificial metadata/storage fixture; never a benchmark reference.
    n=1000
    raw=np.arange(33*n,dtype=np.float32).reshape(33,n)
    fdt=tmp_path/'1_N400_shifted_ds.fdt'
    raw.T.astype('<f4').tofile(fdt)
    set_path=tmp_path/'1_N400_shifted_ds.set'
    eeg=dict(data=fdt.name,datfile=fdt.name,pnts=n,nbchan=33,srate=256,trials=1,
             chanlocs=[{'labels':name} for name in s.CHANNELS],ref='common',history='unchanged history\n',
             event=[{'type':211,'latency':201},{'type':221,'latency':601}],
             icaweights=[],icasphere=[],icawinv=[],icachansind=[])
    savemat(set_path,{'EEG':eeg})
    selected,ledger,segments,trials,info=s.read_subject({'paths':{(1,'set'):set_path,(1,'fdt'):fdt}},1)
    np.testing.assert_array_equal(selected,raw[[14,8,26]])
    assert info['n_source_events']==2 and info['n_retained_target_epochs']==2
    assert info['history_sha256']==s.hashlib.sha256(eeg['history'].encode()).hexdigest()

def test_changed_manifest_fails_before_source_read(tmp_path):
    (tmp_path/'data_manifest.json').write_text('{"subjects": [1]}')
    contract=Path(__file__).resolve().parents[1]/'environment/method_contract.json'
    with pytest.raises(ValueError,match='fingerprint'):
        s.load_inputs(tmp_path,contract)

def test_published_method_and_source_pins_are_exact():
    env=Path(__file__).resolve().parents[1]/'environment'
    assert s.digest(env/'method_contract.json')==s.METHOD_SHA256
    assert s.digest(env/'data_manifest.json')==s.MANIFEST_SHA256

def test_reference_report_overwrite_precondition_precedes_build():
    text=(Path(__file__).parent/'build_reference.py').read_text()
    assert text.index('if args.report and args.report.exists()')<text.index('report=build(args.data_dir')
