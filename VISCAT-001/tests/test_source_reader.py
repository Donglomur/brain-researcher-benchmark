"""Manufactured HDF5 only: no released NWB data are loaded by this module."""
from pathlib import Path
import h5py
import numpy as np
import pytest
import fixture_support as f
import source_reference as s


def make_source(path):
    ref = f.manufactured_reference(np.arange(1, 6))
    rows = ref['trials']; record = dict(path='sub-fixture/session.nwb', participant='fixture-subject', asset_id='fake', sha256='a'*64)
    text = h5py.string_dtype('utf-8')
    with h5py.File(path, 'w') as h:
        h.attrs['nwb_version'] = '2.2.5'
        for key, value in {'general/subject/subject_id':'fixture-subject', 'general/data_collection':'learning: 1, recognition: 2',
                           'identifier':'fake-session', 'session_start_time':'fake-time', 'timestamps_reference_time':'fake-time'}.items():
            h.create_dataset(key, data=value, dtype=text)
        events = sorted((row[field], code, 1 if row['stim_phase']=='learn' else 2) for row in rows
                        for field, code in [('stim_on_time_s',1),('stim_off_time_s',2),('stop_time_s',6)])
        for name in ['events','experiment_ids']:
            group = h.require_group('acquisition/'+name)
            group.create_dataset('timestamps', data=[e[0] for e in events]).attrs['unit']='seconds'
            if name=='events': group.create_dataset('data', data=[str(e[1])+'.0' for e in events], dtype=text)
            else:
                group.create_dataset('data', data=[e[2] for e in events])
                group.attrs['description']='The learning trials are demarcated by: 1. The recognition trials are demarcated by: 2.'
        trials=h.require_group('intervals/trials')
        for name, field in [('id','trial_id'),('stimCategory','category_code')]:
            trials.create_dataset(name,data=[r[field] for r in rows],dtype='uint8' if name=='stimCategory' else 'int64')
        for name, field in [('stim_phase','stim_phase'),('new_old_labels_recog','source_label_token'),('external_image_file','external_image_file'),('category_name','category_name')]:
            trials.create_dataset(name,data=[r[field] for r in rows],dtype=text)
        trials['new_old_labels_recog'].attrs['description']='0 == Old, 1 == New'
        for name in ['start_time','stim_on_time','stim_off_time','stop_time']:
            trials.create_dataset(name,data=[r[name+'_s'] for r in rows])
        electrodes=h.require_group('general/extracellular_ephys/electrodes')
        electrodes.create_dataset('id',data=[101,203]); electrodes.create_dataset('origChannel',data=[7,9])
        electrodes.create_dataset('location',data=['Left Hippocampus','Cortex'],dtype=text)
        units=h.require_group('units'); units.create_dataset('id',data=[10,9])
        links=units.create_dataset('electrodes',data=[0,1]); links.attrs['table']=electrodes.ref
        units.create_dataset('electrodes_index',data=[1,2])
        # The first recognition onset is 120; repeated lower-end values count twice,
        # the upper endpoint is excluded, and raw storage is intentionally unsorted.
        units.create_dataset('spike_times',data=[121.7,120.2,120.2,121.,1.])
        units.create_dataset('spike_times_index',data=[4,5])
    return ref['method'], record


def test_original_reader_manufactured_complete(tmp_path):
    path=tmp_path/'synthetic.nwb'; method,record=make_source(path)
    session,trials,units,responses,observed=s.read_asset(path,record,method)
    assert session['n_mtl_units']==1 and len(units)==2 and len(trials)==10
    assert responses[0][2].tolist()==[3,0,0,0,0]
    assert observed['raw_adjacent_inversions']==1 and observed['duplicate_timestamp_occurrences']==1
    assert observed['raw_adjacent_duplicate_spikes']==1
    assert observed['category_code_dtype']=='uint8' and observed['spike_times_literal_unit'] is None
    assert units[0]['electrode_id']==101 and units[0]['original_channel']==7


@pytest.mark.parametrize('mode',['subject','category_name','category_code','variant','phase','clock','ttl','recog_stop',
                                  'unit_id','ragged','multi_electrode','electrode_row','spike_nan','obs','invalid'])
def test_original_reader_rejects_structural_changes(tmp_path,mode):
    path=tmp_path/'synthetic.nwb'; method,record=make_source(path)
    with h5py.File(path,'r+') as h:
        t=h['intervals/trials']; u=h['units']
        if mode=='subject':h['general/subject/subject_id'][()]='other'
        elif mode=='category_name':t['category_name'][0]='incorrect'
        elif mode=='category_code':t['stimCategory'][0]=0
        elif mode=='variant':t['external_image_file'][0]='unknown\\image.jpg'
        elif mode=='phase':t['stim_phase'][0]='other'
        elif mode=='clock':h['acquisition/experiment_ids/timestamps'][0]+=1
        elif mode=='ttl':h['acquisition/events/data'][0]='7.0'
        elif mode=='recog_stop':t['stop_time'][5]=119.
        elif mode=='unit_id':u['id'][1]=u['id'][0]
        elif mode=='ragged':u['spike_times_index'][0]=10
        elif mode=='multi_electrode':u['electrodes_index'][:]=[2,2]
        elif mode=='electrode_row':u['electrodes'][0]=8
        elif mode=='spike_nan':u['spike_times'][0]=np.nan
        elif mode=='obs':u.create_group('obs_intervals')
        elif mode=='invalid':h.create_group('intervals/invalid_times')
    with pytest.raises(AssertionError):s.read_asset(path,record,method)


def test_learning_stop_anomaly_preserved(tmp_path):
    path=tmp_path/'synthetic.nwb'; method,record=make_source(path)
    with h5py.File(path,'r+') as h:
        # Change both original trial and its literal TTL6, then preserve common sorted clocks.
        h['intervals/trials/stop_time'][0]=99.
        times=h['acquisition/events/timestamps'][:]; times[2]=99.; order=np.argsort(times)
        for name in ['events','experiment_ids']:
            h['acquisition/'+name+'/timestamps'][:]=times[order]
            values=h['acquisition/'+name+'/data'][:];h['acquisition/'+name+'/data'][:]=values[order]
    _,trials,_,_,observed=s.read_asset(path,record,method)
    assert trials[0]['stop_time_s']==99. and observed['n_learning_temporal_order_violations']==1


@pytest.mark.parametrize('mode',['external_link','virtual','external_storage'])
def test_hdf5_external_payload_rejected(tmp_path,mode):
    path=tmp_path/'synthetic.nwb'; method,record=make_source(path)
    with h5py.File(path,'r+') as h:
        if mode=='external_link':h['bad']=h5py.ExternalLink('missing.nwb','/x')
        elif mode=='virtual':
            layout=h5py.VirtualLayout(shape=(1,),dtype='f8');layout[:]=h5py.VirtualSource('missing.nwb','x',shape=(1,))
            h.create_virtual_dataset('bad',layout)
        else:h.create_dataset('bad',(1,),dtype='f8',external=[('missing.raw',0,8)])
    with pytest.raises(AssertionError,match='External|virtual'):s.read_asset(path,record,method)


@pytest.mark.parametrize('mode',['symlink','fifo'])
def test_source_path_not_regular(tmp_path,mode):
    import os
    path=tmp_path/'synthetic.nwb';method,record=make_source(path);bad=tmp_path/'bad'
    if mode=='symlink':bad.symlink_to(path)
    else:os.mkfifo(bad)
    with pytest.raises(AssertionError):s.read_asset(bad,record,method)


@pytest.mark.parametrize('value',[np.iinfo(np.int64).min,np.iinfo(np.int64).max])
def test_integer_dtype_bound_properties(value):
    import category_statistics as c
    assert c.integers(np.asarray([value],dtype=np.int64),'fixture').tolist()==[value]


def test_unsigned_integer_overflow():
    import category_statistics as c
    with pytest.raises(AssertionError,match='overflow'):c.integers(np.asarray([2**63],dtype=np.uint64),'fixture')
