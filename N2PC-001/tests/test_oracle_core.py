"""Manufactured oracle event/filter/own-epoch tests; no original data."""
import json
from pathlib import Path
import subprocess
import sys
import numpy as np
import pytest
from scipy.signal import fftconvolve

SOLUTION=Path(__file__).resolve().parents[1]/'solution'
sys.path.insert(0,str(SOLUTION))
import core
import compute

@pytest.fixture
def contract():
    return json.loads((SOLUTION.parent/'environment/method_contract.json').read_text())

def metadata(events=None,n=5000,subject=1):
    return dict(subject=subject,n_samples=n,events=events if events is not None else [dict(type=111,latency=1001),dict(type=121,latency=2001)],
                observed=dict(subject=subject,n_source_events=0,n_bad_annotations=0))

def manufactured(subjects=(1,),counts=((3,1),),amplitudes=((4,2,1,3),)):
    trials=[];blocks=[]
    for subject,(nl,nr),(l7,l8,r7,r8) in zip(subjects,counts,amplitudes):
        events=[dict(type=111 if i<nl else 121,latency=1001+i*1000) for i in range(nl+nr)]
        _,rows,_,_=core.annotate_and_select(metadata(events,n=1000*(len(events)+2),subject=subject))
        trials.extend(rows)
        for i,row in enumerate(rows):
            block=np.full((2,667),7.0+i)
            block[:,core.WINDOW]+=np.array([l7,l8] if row['target_field']=='left' else [r7,r8])[:,None]
            block[:,0]+=1000
            blocks.append(block)
    arrays=dict(subject=np.array([r['subject'] for r in trials],dtype=np.int64),
                source_event_index=np.array([r['source_event_index'] for r in trials],dtype=np.int64),
                channel_labels=np.array(['PO7','PO8']),sample_offsets=core.OFFSETS.copy(),
                epochs_uv=np.stack(blocks) if blocks else np.empty((0,2,667)))
    return trials,arrays

def test_frozen_sample_windows(contract):
    assert len(core.OFFSETS)==667 and core.OFFSETS[[0,-1]].tolist()==[-205,461]
    assert core.BASELINE.sum()==205 and core.OFFSETS[core.BASELINE][[0,-1]].tolist()==[-204,0]
    assert core.WINDOW.sum()==103 and core.OFFSETS[core.WINDOW][[0,-1]].tolist()==[205,307]
    assert contract['epochs']['n_samples']==667

@pytest.mark.parametrize('latency,expected',[(1,0),(2,1),(2.5,2),(3.5,2),(-1,-2),(0.5,0)])
def test_clock_ties_even(latency,expected):
    ann,_,_,_=core.annotate_and_select(metadata([dict(type=201,latency=latency)]))
    assert ann[0]['sample']==expected and ann[0]['onset_s']==(latency-1)/1024

@pytest.mark.parametrize('event,expected',[({},('absent',None)),({'duration':None},('empty',None)),
                                         ({'duration':{'source_nonfinite':'nan'}},('nonfinite',None)),({'duration':0},('finite',0.0))])
def test_duration_states(event,expected):
    assert core.duration(event)==expected

@pytest.mark.parametrize('value',['111','BAD boundary',111.25,True,None,{'bad':111},float('nan')])
def test_types_failclosed(value):
    with pytest.raises(ValueError):
        core.annotate_and_select(metadata([dict(type=value,latency=1000)]))

def test_annotations_and_no_behavioral_selection():
    events=[dict(type=c,latency=1001+1000*i,urevent=i+1) for i,c in enumerate((111,201,202,121,999))]
    ann,rows,segments,observed=core.annotate_and_select(metadata(events,n=7000))
    assert len(ann)==5 and [r['source_event_index'] for r in rows]==[0,3]
    assert all(r['retained'] for r in rows) and observed['n_target_left']==observed['n_target_right']==1
    assert observed['event_type_counts']['999']==1 and segments==[[0,7000]]

def test_duplicate_targets_only_fail():
    with pytest.raises(ValueError,match='duplicate_target'):
        core.annotate_and_select(metadata([dict(type=111,latency=1001),dict(type=121,latency=1001)]))
    ann,rows,_,_=core.annotate_and_select(metadata([dict(type=111,latency=1001),dict(type=201,latency=1001)]))
    assert len(ann)==2 and len(rows)==1

@pytest.mark.parametrize('cut',[0,2500,5000])
def test_boundary_endpoints_and_duplicate_cuts(cut):
    _,_,segments,_=core.annotate_and_select(metadata([dict(type=-99,latency=cut+0.5),dict(type=-99,latency=cut+0.5)]))
    assert segments==([[0,2500],[2500,5000]] if cut==2500 else [[0,5000]])

@pytest.mark.parametrize('latency',[2500,2500.25,-0.5,5001.5])
def test_invalid_boundary(latency):
    with pytest.raises(ValueError,match='boundary_half_sample'):
        core.annotate_and_select(metadata([dict(type=-99,latency=latency)]))

@pytest.mark.parametrize('sample,reason,crosses',[(2038,'retained',False),(2039,'boundary_crossing',True),
                                              (2704,'boundary_crossing',True),(2705,'retained',False),(0,'out_of_data',False)])
def test_boundary_halfopen(sample,reason,crosses):
    _,rows,_,_=core.annotate_and_select(metadata([dict(type=-99,latency=2500.5),dict(type=111,latency=sample+1)]))
    assert rows[0]['drop_reason']==reason and rows[0]['crosses_boundary']==crosses

def test_outside_precedes_crossing():
    _,rows,_,_=core.annotate_and_select(metadata([dict(type=-99,latency=100.5),dict(type=111,latency=1)]))
    assert rows[0]['out_of_data'] and rows[0]['crosses_boundary'] and rows[0]['drop_reason']=='out_of_data'

def test_equal_fields_not_trial_pool():
    trials,arrays=manufactured();rows,people,waves,result=core.derive(trials,arrays,[1])
    person=people[0]
    assert person['n_left_trials']==3 and person['n_right_trials']==1
    assert person['contra_uv']==1.5 and person['ipsi_uv']==3.5 and person['n2pc_uv']==-2
    assert person['fixed_po8_minus_po7_pooled_uv']==0
    assert np.mean([r['trial_po8_minus_po7_uv'] for r in rows])==-1
    assert result['n_subjects_negative']==1 and len(waves)==2*667
    assert rows[0]['po7_baseline_uv']==7 and rows[0]['po7_corrected_window_uv']==4

def test_equal_people_not_trial_pool():
    trials,arrays=manufactured(subjects=(1,3),counts=((3,1),(1,1)),
                              amplitudes=((4,2,1,3),(0,6,6,0)))
    rows,people,waves,result=core.derive(trials,arrays,[1,3])
    assert [p['n2pc_uv'] for p in people]==[-2,6]
    assert [p['n_left_trials']+p['n_right_trials'] for p in people]==[4,2]
    assert result['n2pc_amplitude_uv']==2
    pooled=np.mean([row['trial_contra_minus_ipsi_uv'] for row in rows])
    assert pooled!=result['n2pc_amplitude_uv']
    group_window=[w['n2pc_uv'] for w in waves if w['scope']=='group' and 205<=w['sample_offset']<=307]
    assert group_window==[2.0]*103

@pytest.mark.parametrize('values',[(4,2,1,3),(1,3,4,2),(2,2,2,2)])
def test_any_sign_zero_valid(values):
    trials,arrays=manufactured(amplitudes=(values,));_,people,_,result=core.derive(trials,arrays,[1])
    assert result['status']=='ok' and result['analysis_status']=='defined'
    assert result['n_subjects_negative']==int(people[0]['n2pc_uv']<0)

@pytest.mark.parametrize('counts,status',[((0,2),'empty_left'),((2,0),'empty_right'),((0,0),'empty_both')])
def test_empty_support_no_person_drop(counts,status):
    trials,arrays=manufactured(subjects=(1,3),counts=(counts,(1,1)),amplitudes=((1,3,4,2),(1,3,4,2)))
    _,people,waves,result=core.derive(trials,arrays,[1,3])
    assert people[0]['status']==status and len(people)==2 and len(waves)==3*667
    assert result['analysis_status']=='incomplete_field_support' and result['n2pc_amplitude_uv'] is None

def test_other_field_remains():
    trials,arrays=manufactured(counts=((2,0),));_,people,waves,_=core.derive(trials,arrays,[1])
    assert people[0]['left_po7_uv']==4 and people[0]['right_po7_uv'] is None and people[0]['contra_uv'] is None
    assert all(w['left_po7_uv'] is not None and w['right_po7_uv'] is None for w in waves)

def test_baseline_includes_zero_excludes_minus205():
    trials,arrays=manufactured(counts=((1,1),));arrays['epochs_uv'][:,:,core.OFFSETS==0]+=205
    rows,_,_,_=core.derive(trials,arrays,[1])
    assert rows[0]['po7_baseline_uv']==8 and rows[0]['po7_corrected_window_uv']==3

def kernel():
    def lp(length,cut):
        n=np.arange(length,dtype=np.float64);p=2*cut/1024
        h=p*np.sinc(p*(n-(length-1)/2))*(.54-.46*np.cos(2*np.pi*n/(length-1)))
        return h/h.sum()
    h=-lp(33793,.05);start=(33793-451)//2;h[start:start+451]+=lp(451,33.75)
    return h

def direct_filter(x,h):
    n=len(x);e=min(len(h),n)-1
    padded=np.concatenate((2*x[0]-x[1:e+1][::-1],x,2*x[-1]-x[-e-1:-1][::-1])) if e else x
    return fftconvolve(padded,h,mode='full')[e+16896:e+16896+n]

@pytest.mark.parametrize('segments',[[[0,80]],[[0,31],[31,80]],[[0,1],[1,80]]])
def test_mne_filter_independent_formula(contract,segments):
    x=np.random.default_rng(17).normal(size=(30,80))*1e-6;warnings=[]
    actual=core.filter_reference(x,segments,contract,1,warnings);h=kernel();expected=np.empty((2,80))
    for start,stop in segments:
        filtered=np.stack([direct_filter(row[start:stop],h) for row in x])
        expected[:,start:stop]=(filtered[[9,27]]-filtered.mean(axis=0))*1e6
    np.testing.assert_allclose(actual,expected,atol=1e-10,rtol=1e-9)
    assert warnings and all(w['category']=='RuntimeWarning' for w in warnings)

def test_filter_no_cross_boundary_or_eog(contract):
    x=np.zeros((30,80));x[:,40:]=np.arange(30)[:,None]*1e-6
    actual=core.filter_reference(x,[[0,40],[40,80]],contract,1,[])
    assert np.max(np.abs(actual[:,:40]))==0
    with pytest.raises(ValueError,match='30_channel'):
        core.filter_reference(np.zeros((33,80)),[[0,80]],contract,1,[])

def test_emit_eight_files(tmp_path,contract):
    trials,arrays=manufactured();rows,people,waves,result=core.derive(trials,arrays,[1],pilot=True)
    analysis=dict(annotations=core.annotate_and_select(metadata())[0],trials=rows,people=people,waveforms=waves,result=result,metadata={'status':'resource_pilot'},arrays=arrays)
    compute.emit(tmp_path,analysis,contract)
    assert {p.name for p in tmp_path.iterdir()}==set(contract['output_schema']['files'])
    with np.load(tmp_path/'response_epochs.npz',allow_pickle=False) as z:
        assert set(z.files)==set(arrays)
    with pytest.raises(FileExistsError):
        compute.emit(tmp_path,analysis,contract)

def test_pilot_scope():
    trials,arrays=manufactured(subjects=(8,));_,_,_,result=core.derive(trials,arrays,[8],pilot=True)
    assert result['status']=='resource_pilot' and result['subjects']==[8] and result['subject_weighting']=='equal_pilot_scope'

def test_wrapper_forwarding(tmp_path):
    command='exec() { printf "%s\\n" "$@"; }; export -f exec; bash "$1" --pilot-subject 8 --private-dir "$2"'
    private=tmp_path/'not-created'
    proc=subprocess.run(['bash','-c',command,'fixture',str(SOLUTION/'solve.sh'),str(private)],capture_output=True,text=True,timeout=10)
    assert proc.returncode==0 and proc.stdout.splitlines()[-4:]==['--pilot-subject','8','--private-dir',str(private)]
    assert not private.exists()
