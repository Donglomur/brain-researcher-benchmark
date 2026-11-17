#!/usr/bin/env python3
"""Bounded source-equivalence controls; never a paper panel or model score."""
import argparse,copy,json,os,resource,tempfile,time
from pathlib import Path
import numpy as np
import pandas as pd
from nlb_tools.nwb_interface import NWBDataset
import nlb_tools.nwb_interface as nwb
from memory_prepare import install_memory_preparation,column_smooth_resample,bounded_dataset
from prepare import sha,write_json,ensure_external


def same(a,b):
    assert a.bin_width==b.bin_width
    assert a.data.index.equals(b.data.index)
    assert a.data.columns.equals(b.data.columns)
    assert a.data.dtypes.equals(b.data.dtypes)
    assert a.trial_info.equals(b.trial_info)
    assert a.descriptions==b.descriptions
    aa=np.ascontiguousarray(a.data.to_numpy());bb=np.ascontiguousarray(b.data.to_numpy())
    assert aa.dtype==bb.dtype and aa.tobytes()==bb.tobytes()
    return dict(bitwise_equal=True,shape=list(aa.shape),dtype=str(aa.dtype),
                index_equal=True,trial_info_equal=True,descriptions_equal=True)


def generated():
    rng=np.random.default_rng(119)
    for dtype in [np.float32,np.float64]:
        ds=NWBDataset.__new__(NWBDataset)
        columns=pd.MultiIndex.from_tuples([('heldout_spikes',3),('spikes',1),('spikes',2)],names=['signal_type','channel'])
        values=np.abs(rng.normal(size=(1003,3))).astype(dtype)
        values[100:173,1]=np.nan;values[-3:,2]=np.nan
        ds.data=pd.DataFrame(values,index=pd.to_timedelta(np.arange(1003),unit='ms'),columns=columns)
        ds.bin_width=1;ds.trial_info=pd.DataFrame({'trial_id':[1]});ds.descriptions={}
        original=copy.copy(ds);original.data=ds.data.copy()
        original.smooth_spk(70,signal_type=['spikes','heldout_spikes'],overwrite=True,ignore_nans=True)
        original.resample(20)
        bounded=column_smooth_resample(ds,70,20)
        same(original,bounded)
    return {'generated_float32_float64_two_fields_nan_partial_bin':'bitwise_equal'}


def generated_nwb(path):
    from datetime import datetime,timezone
    from pynwb import NWBFile,NWBHDF5IO,TimeSeries
    file=NWBFile('Generated allocation control, not biological evidence','smc-control',datetime(2020,1,1,tzinfo=timezone.utc))
    file.add_unit_column('heldout','Generated source group')
    for uid,held,interval in [(7,False,[0,.98]),(2,False,[.2,.8]),(19,True,[.1,.9]),(4,True,[0,1.0]),(30,False,[0,1.003])]:
        file.add_unit(id=uid,spike_times=[.3,.4],obs_intervals=[interval],heldout=held)
    file.add_trial_column('split','Generated split')
    file.add_trial(start_time=0.,stop_time=1.003,split='train')
    behavior=file.create_processing_module('behavior','Generated support control')
    values=np.arange(2006,dtype=float).reshape(1003,2)/2006
    values[450:470,0]=np.nan
    for name in ['hand_vel','hand_pos']:
        behavior.add(TimeSeries(name=name,data=values,unit='arbitrary',timestamps=np.arange(1003)/1000))
    with NWBHDF5IO(str(path),'w') as io:io.write(file)


p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--test-nwb',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
a=p.parse_args();ensure_external(a.output)
if a.output.exists():raise ValueError('Refuse evidence overwrite')
source_files=['prepare.py','memory_prepare.py','control_memory_preparation.py','preparation_memory.patch']
source_hashes_before={name:sha(Path(__file__).parent/name) for name in source_files}
start=time.monotonic();nwb._poolmap=lambda f,X,**kwargs:list(map(f,X))
report=generated()
# Two copies exercise the original MULTI-FILE seam/time/trial-ID branch, control only.
with tempfile.TemporaryDirectory(prefix='smc-native-control-',dir=a.output.parent) as temp:
    root=Path(temp)
    os.link(a.test_nwb,root/'a.nwb');os.link(a.test_nwb,root/'b.nwb')
    original=NWBDataset(str(root));original.resample(20)
    generated_path=root/'generated-source.nwb'
    generated_nwb(generated_path)
    original_generated=NWBDataset(str(generated_path));original_generated.resample(20)
    install_memory_preparation()
    blocked_generated=bounded_dataset(str(generated_path),bin_width=20,block_size=1)
    report['generated_noncontiguous_ids_unequal_intervals_maxend_behavior']=same(original_generated,blocked_generated)
    generated_path.unlink()
    bounded=bounded_dataset(str(root),bin_width=20)
    report['authentic_two_file_constructor_control']=same(original,bounded)
    del original,bounded
original=NWBDataset(str(a.test_nwb))
original.smooth_spk(70,signal_type=['spikes'],overwrite=True,ignore_nans=True)
original.resample(20)
bounded=bounded_dataset(str(a.test_nwb),bin_width=20,kern_sd=70)
report['authentic_full_test_input_smoothing_control']=same(original,bounded)
r=resource.getrusage(resource.RUSAGE_SELF)
report.update(schema='smc_native_memory_equivalence_v1',input_sha256=sha(a.test_nwb),
    wall_seconds=time.monotonic()-start,cpu_seconds=r.ru_utime+r.ru_stime,maxrss_native_units=r.ru_maxrss,
    scope='Software/source equivalence on authentic input only; duplicate-file case is a control, never the source paper cohort.',
    target_accessed=False,model_inference=False,paper_score=None)
source_hashes_after={name:sha(Path(__file__).parent/name) for name in source_files}
assert source_hashes_before==source_hashes_after
report['source_hashes_before']=source_hashes_before
report['source_hashes_after']=source_hashes_after
report['source_unchanged_during_control']=True
write_json(a.output,report);print(json.dumps(report),flush=True)
