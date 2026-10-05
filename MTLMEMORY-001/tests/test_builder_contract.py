"""Bounded source-free independent builder mechanics and evidence safety."""
from pathlib import Path
import numpy as np
import h5py
import pytest
import build_reference as b


@pytest.mark.parametrize('spikes,expected',[
    ([1.7,.2,.2,.1,1.699],3),([.2,1.7],1),([],0),([1.7,.2,1.,.2,1.7],3)])
def test_unsorted_multiset_half_open(spikes,expected):
    source=np.array(spikes,dtype=float);before=source.copy()
    assert b.count_intervals(source,[0]).tolist()==[expected]
    assert np.array_equal(source,before)


@pytest.mark.parametrize('bad',[np.nan,np.inf,-np.inf])
def test_nonfinite_times_fail(bad):
    with pytest.raises(AssertionError):b.count_intervals([bad],[0])
    with pytest.raises(AssertionError):b.count_intervals([0],[bad])


@pytest.mark.parametrize('mode',['inside_source','same','existing','symlink_leaf','dangling','symlink_ancestor'])
def test_evidence_guards(tmp_path,mode):
    source=tmp_path/'source';source.mkdir();original=source/'original';original.write_bytes(b'original')
    output=tmp_path/'new.npz';report=tmp_path/'new.json'
    if mode=='inside_source':output=source/'new.npz'
    elif mode=='same':report=output
    elif mode=='existing':output.write_bytes(b'prior')
    elif mode=='symlink_leaf':output.symlink_to(original)
    elif mode=='dangling':output.symlink_to(tmp_path/'missing')
    else:
        (tmp_path/'alias').symlink_to(source,target_is_directory=True);output=tmp_path/'alias'/'new.npz'
    with pytest.raises(AssertionError):b.destinations(output,report,source)
    assert original.read_bytes()==b'original' and not (source/'new.npz').exists()


def test_valid_destinations_do_not_write(tmp_path):
    source=tmp_path/'source';source.mkdir()
    b.destinations(tmp_path/'new'/'bank.npz',tmp_path/'report.json',source)
    assert not (tmp_path/'new').exists()


@pytest.mark.parametrize('values',[[True],[1.5],[2**64-1]])
def test_invalid_source_integers(values):
    with pytest.raises(AssertionError):b.ints(np.asarray(values))


@pytest.mark.parametrize('values,n,total',[([3,2],2,2),([1],2,1),([2],1,3)])
def test_bad_ragged_offsets(values,n,total):
    with pytest.raises(AssertionError):b.ends(np.array(values),n,total)


def test_wrong_source_pin_before_body_read(tmp_path):
    source=tmp_path/'source';source.mkdir();(source/'source_manifest.json').write_text('{}')
    with pytest.raises(AssertionError,match='manifest'):b.load_inputs(source,tmp_path/'absent-method')


def test_no_oracle_numerical_imports():
    code=Path(b.__file__).read_text()
    assert 'import compute' not in code and 'from solution' not in code and 'independent_originals' not in code


def synthetic_hdf(path):
    """Constructed HDF5 parser fixture; never an authoritative source bank."""
    with h5py.File(path,'w') as f:
        def put(key,value):
            if isinstance(value,str) or isinstance(value,list) and value and isinstance(value[0],str):
                return f.create_dataset(key,data=value,dtype=h5py.string_dtype('utf8'))
            return f.create_dataset(key,data=value)
        f.attrs['nwb_version']='2-fixture'
        for key,value in [('general/subject/subject_id','fixture-subject'),('identifier','fixture-id'),
                          ('session_start_time','fixture-date'),('timestamps_reference_time','fixture-clock'),
                          ('general/data_collection','learning: 22, recognition: 34')]:put(key,value)
        on=np.array([100.,104.,200.,204.,208.,212.]);off=on+1.;end=on+2.
        phases=['learn','learn','recog','recog','recog','recog'];labels=['NA','NA','0','1','0','1']
        put('intervals/trials/id',np.array([91,21,54,33,37,48]))
        put('intervals/trials/stim_phase',phases)
        lab=put('intervals/trials/new_old_labels_recog',labels);lab.attrs['description']='0 == Old, 1 == New'
        put('intervals/trials/external_image_file',['D:/a/x','D:/b/x','D:/c/x','D:/a/x','D:/d/z','D:/missing/old'])
        for name,data in [('start_time',on),('stim_on_time',on),('stim_off_time',off),('stop_time',end)]:put('intervals/trials/'+name,data)
        times=np.column_stack([on,off,end]).ravel();put('acquisition/events/timestamps',times)
        put('acquisition/events/data',['1.0','2.0','6.0']*6)
        put('acquisition/experiment_ids/data',np.repeat([22,22,34,34,34,34],3))
        put('acquisition/experiment_ids/timestamps',times)
        f['acquisition/experiment_ids'].attrs['description']='The learning trials are demarcated by: 22. The recognition trials are demarcated by: 34.'
        put('general/extracellular_ephys/electrodes/id',np.array([900,800]))
        put('general/extracellular_ephys/electrodes/origChannel',np.array([11,41]))
        put('general/extracellular_ephys/electrodes/location',['visual','RightAmygdala'])
        put('units/id',np.array([20,2]));put('units/electrodes_index',np.array([1,2]))
        links=put('units/electrodes',np.array([1,0]));links.attrs['table']=f['general/extracellular_ephys/electrodes'].ref
        put('units/spike_times',np.array([201.7,200.2,200.2,201.,99.,204.2]))
        put('units/spike_times_index',np.array([5,6]))
    return dict(path='fixture.nwb',participant='fixture-subject',asset_id='fixture',sha256='0'*64)


def test_independent_hdf_identity_counts_and_diagnostics(tmp_path):
    p=tmp_path/'synthetic.nwb';source=synthetic_hdf(p)
    session,trials,units,response,obs=b.read_asset(p,source)
    assert session['n_source_units']==2 and session['n_mtl_units']==1
    assert [u['unit_id'] for u in units]==[20,2] and units[0]['electrode_id']==800
    assert response[0][2].tolist()==[3,0,0,0]
    assert trials[2]['trial_id']==54 and not trials[2]['image_in_learning']
    assert trials[-1]['source_label']==1 and not trials[-1]['image_in_learning']
    assert obs['n_unordered_units']==1 and obs['duplicate_timestamp_occurrences']==1
    assert obs['phase_experiment_ids']==dict(learn=22,recog=34)
    assert obs['spike_times_literal_unit'] is None


@pytest.mark.parametrize('mode',['nonfinite','unknown_label','wrong_target','ambiguous_region','duplicate_id','wrong_phase'])
def test_original_source_parser_rejects_malformed_fixture(tmp_path,mode):
    p=tmp_path/'synthetic.nwb';source=synthetic_hdf(p)
    with h5py.File(p,'r+') as f:
        if mode=='nonfinite':f['units/spike_times'][0]=np.nan
        elif mode=='unknown_label':f['intervals/trials/new_old_labels_recog'][2]='unknown'
        elif mode=='wrong_target':f['units/electrodes'].attrs['table']=f['intervals/trials'].ref
        elif mode=='ambiguous_region':f['general/extracellular_ephys/electrodes/location'][1]='Hippocampus Amygdala'
        elif mode=='duplicate_id':f['units/id'][1]=20
        else:f['acquisition/experiment_ids/data'][6]=99
    with pytest.raises(AssertionError):b.read_asset(p,source)


def change_stop_and_original_ttl(path,row,new_stop):
    with h5py.File(path,'r+') as f:
        old=float(f['intervals/trials/stop_time'][row]); f['intervals/trials/stop_time'][row]=new_stop
        times=f['acquisition/events/timestamps'][:];tokens=f['acquisition/events/data'].asstr()[:]
        exp=f['acquisition/experiment_ids/data'][:]
        index=np.flatnonzero((times==old)&(tokens=='6.0'))
        assert len(index)==1
        times[index[0]]=new_stop;order=np.argsort(times,kind='stable')
        f['acquisition/events/timestamps'][:]=times[order]
        f['acquisition/experiment_ids/timestamps'][:]=times[order]
        f['acquisition/events/data'][:]=tokens[order]
        f['acquisition/experiment_ids/data'][:]=exp[order]


@pytest.mark.parametrize('stop',[99.75,100.5])
def test_learning_end_violation_retained_losslessly(tmp_path,stop):
    p=tmp_path/'synthetic.nwb';source=synthetic_hdf(p);change_stop_and_original_ttl(p,0,stop)
    _,trials,_,response,obs=b.read_asset(p,source)
    assert trials[0]['stop_time_s']==stop and not trials[0]['included']
    assert obs['n_learning_temporal_order_violations']==1
    assert obs['n_recognition_temporal_order_violations']==0
    assert response[0][2].tolist()==[3,0,0,0]


@pytest.mark.parametrize('stop',[199.75,200.5])
def test_recognition_end_violation_remains_precondition(tmp_path,stop):
    p=tmp_path/'synthetic.nwb';source=synthetic_hdf(p);change_stop_and_original_ttl(p,2,stop)
    with pytest.raises(AssertionError,match='recognition trial end'):b.read_asset(p,source)


@pytest.mark.parametrize('column,value',[('start_time',99.9),('stim_off_time',99.),('stop_time',float('nan'))])
def test_other_learning_time_preconditions_remain(tmp_path,column,value):
    p=tmp_path/'synthetic.nwb';source=synthetic_hdf(p)
    with h5py.File(p,'r+') as f:f['intervals/trials/'+column][0]=value
    with pytest.raises(AssertionError):b.read_asset(p,source)
