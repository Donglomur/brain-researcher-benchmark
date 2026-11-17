"""Source-preserving allocation/lifetime changes for the complete NLB panel.

Original NLB tools0.0.3 is MIT licensed; source functions are hash checked and
kept intact on disk. This module changes object lifetimes and neuron scheduling,
never the original time grid, filtering, resampling, trial selection or metric.
"""
import copy
import hashlib
import inspect
import textwrap
import pandas as pd
import numpy as np
import h5py
from pathlib import Path
import glob

_SELECTION={"ids":None}

NWB_SHA256='f30c63a746f043ddde21834cca09588f04c9eeb97df716baac10c5dc3eb7fa31'
TENSOR_SHA256='e79badd983e37fa0c8f0ddbdeb74972ed505ba4672035daca4e8af16a7bc2d9d'


def lifetime_source(source):
    first='''                datas, trial_infos, descriptions, bin_widths = [
                    list(out) for out in zip(*loaded)
                ]'''
    second='''                self.bin_width = bin_widths[0]
                new_index ='''
    if source.count(first)!=1 or source.count(second)!=1:
        raise ValueError('Unexpected original NLB constructor')
    return source.replace(first,first+'\n                del loaded').replace(second,
        '                self.bin_width = bin_widths[0]\n                del datas\n                new_index =')


def loader_source(source):
    old='        data = pd.concat(data_list, axis=1)'
    if source.count(old)!=1:
        raise ValueError('Unexpected original NLB loader')
    source=source.replace(old,old+'\n        del data_list, data_dict, spike_arr, val')
    marker='        for mask, name in zip(masks, ["spikes", "heldout_spikes"]):'
    if source.count(marker)!=1:
        raise ValueError('Unexpected original spike allocation masks')
    insertion='''        if _smc_selection['ids'] is not None:
            masks = [mask & np.isin(units.index, _smc_selection['ids']) for mask in masks]

'''
    return source.replace(marker,insertion+marker)


def column_smooth_resample(dataset, kern_sd, bin_width):
    """Full original time axis; original smoothing then original resample per neuron."""
    columns=[]
    for column in dataset.data.columns:
        single=copy.copy(dataset)
        single.data=dataset.data.loc[:,[column]].copy()
        single.smooth_spk(kern_sd,signal_type=[column[0]],overwrite=True,ignore_nans=True)
        if bin_width!=1:
            single.resample(bin_width)
        columns.append(single.data)
    dataset.data=pd.concat(columns,axis=1)
    dataset.data.sort_index(axis=1,inplace=True)
    dataset.bin_width=bin_width
    return dataset


def _frame_equal(a,b):
    if not a.index.equals(b.index) or not a.columns.equals(b.columns) or not a.dtypes.equals(b.dtypes):
        return False
    for column in a.columns:
        if np.ascontiguousarray(a[column].to_numpy()).tobytes()!=np.ascontiguousarray(b[column].to_numpy()).tobytes():
            return False
    return True


def bounded_dataset(fpath,prefix='',skip_fields=None,bin_width=20,kern_sd=None,block_size=16):
    """All source times/fields/units, allocation by complete neuron columns only."""
    from nlb_tools.nwb_interface import NWBDataset
    path=Path(fpath)
    files=sorted(path.glob(prefix+'*.nwb')) if path.is_dir() else [path]
    identifiers=set();sentinels=set()
    for filename in files:
        with h5py.File(filename,'r') as handle:
            ids=handle['units/id'][()]
            heldout=handle['units/heldout'][()].astype(bool)
            identifiers.update(int(x) for x in ids)
            for mask in [~heldout,heldout]:
                if mask.any():sentinels.add(int(ids[np.flatnonzero(mask)[0]]))
    if not identifiers or not sentinels:raise ValueError('Expected nonempty source units')
    identifiers=sorted(identifiers)
    blocks=[identifiers[i:i+block_size] for i in range(0,len(identifiers),block_size)]
    columns=[];seen=set();reference=None;reference_shared=None
    try:
        for block in blocks:
            _SELECTION['ids']=sorted(set(block)|sentinels)
            current=NWBDataset(str(path),prefix,skip_fields=skip_fields or [])
            if kern_sd is None:current.resample(bin_width)
            else:current=column_smooth_resample(current,kern_sd,bin_width)
            spike_cols=[c for c in current.data.columns if c[0] in ['spikes','heldout_spikes']]
            shared=[c for c in current.data.columns if c not in spike_cols or int(c[1]) in sentinels]
            if reference is None:
                reference=current
                reference_shared=current.data.loc[:,shared].copy()
                common=[c for c in current.data.columns if c not in spike_cols]
                if common:columns.append(current.data.loc[:,common].copy())
            else:
                if not current.trial_info.equals(reference.trial_info) or current.descriptions!=reference.descriptions or not _frame_equal(reference_shared,current.data.loc[:,shared]):
                    raise ValueError('Block changed native times, metadata, behavior or representative sentinel')
            selected=[c for c in spike_cols if c not in seen]
            columns.append(current.data.loc[:,selected].copy())
            seen.update(selected)
        if len(seen)!=len(identifiers):raise ValueError('Incomplete source neuron coverage')
        reference.data=pd.concat(columns,axis=1)
        reference.data.sort_index(axis=1,inplace=True)
        reference.bin_width=bin_width
        reference.smc_memory_blocks={'block_size':block_size,'blocks':len(blocks),
            'complete_unit_count':len(identifiers),'representative_sentinel_count':len(sentinels),
            'all_block_indices_metadata_behavior_sentinels_equal':True,
            'smoothing_before_resample':kern_sd is not None}
        return reference
    finally:
        _SELECTION['ids']=None


def psth_source(source):
    start=source.index('    # Reload dataset and smooth spikes')
    end=source.index('    # Make mask for valid trials',start)
    new="""    # Complete columns, full original time axis, same native smoothing/resampling.
    ti = dataset.trial_info
    neur = dataset.data[['spikes', 'heldout_spikes']].columns
    dataset = _smc_bounded_dataset(dataset.fpath, dataset.prefix,
        skip_fields=['force', 'hand_pos', 'hand_vel', 'finger_pos', 'finger_vel', 'eye_pos', 'cursor_pos', 'muscle_len', 'muscle_vel', 'joint_ang', 'joint_vel'],
        bin_width=dataset.bin_width, kern_sd=kern_sd)
    dataset.trial_info = ti
    dataset.data = dataset.data.loc[:, neur].sort_index(axis=1)

"""
    return source[:start]+new+source[end:]


def install_memory_preparation():
    import nlb_tools.nwb_interface as nwb
    import nlb_tools.make_tensors as tensors
    for module,digest in [(nwb,NWB_SHA256),(tensors,TENSOR_SHA256)]:
        with open(module.__file__,'rb') as handle:
            if hashlib.sha256(handle.read()).hexdigest()!=digest:
                raise ValueError('Unexpected NLB source for memory-only patch')
    original_load=nwb.NWBDataset.load
    namespace=original_load.__globals__.copy()
    namespace['_smc_selection']=_SELECTION
    exec(compile(textwrap.dedent(loader_source(inspect.getsource(original_load))),
                 '<nlb-loader-lifetime-only>','exec'),namespace)
    nwb.NWBDataset.load=namespace['load']
    original=nwb.NWBDataset.__init__
    namespace=original.__globals__.copy()
    code=textwrap.dedent(lifetime_source(inspect.getsource(original)))
    exec(compile(code,'<nlb-constructor-lifetime-only>','exec'),namespace)
    nwb.NWBDataset.__init__=namespace['__init__']
    # Preserve the same original smooth_column function and order without processes.
    nwb._poolmap=lambda f,X,**kwargs:list(map(f,X))
    original_psth=tensors._make_psth
    namespace=original_psth.__globals__.copy()
    namespace['_smc_bounded_dataset']=bounded_dataset
    exec(compile(psth_source(inspect.getsource(original_psth)),
                 '<nlb-column-scheduled-psth>','exec'),namespace)
    tensors._make_psth=namespace['_make_psth']
    return original,original_psth
