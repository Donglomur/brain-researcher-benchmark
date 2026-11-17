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
    return source.replace(old,old+'\n        del data_list, data_dict, spike_arr, val')


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


def psth_source(source):
    old="""    dataset.smooth_spk(kern_sd, signal_type=['spikes', 'heldout_spikes'], overwrite=True, ignore_nans=True)
    if bin_width != 1:
        dataset.resample(bin_width)"""
    if source.count(old)!=1:
        raise ValueError('Unexpected original NLB PSTH prelude')
    return source.replace(old,'    dataset = _smc_column_smooth_resample(dataset, kern_sd, bin_width)')


def install_memory_preparation():
    import nlb_tools.nwb_interface as nwb
    import nlb_tools.make_tensors as tensors
    for module,digest in [(nwb,NWB_SHA256),(tensors,TENSOR_SHA256)]:
        with open(module.__file__,'rb') as handle:
            if hashlib.file_digest(handle,'sha256').hexdigest()!=digest:
                raise ValueError('Unexpected NLB source for memory-only patch')
    original_load=nwb.NWBDataset.load
    namespace=original_load.__globals__.copy()
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
    namespace['_smc_column_smooth_resample']=column_smooth_resample
    exec(compile(psth_source(inspect.getsource(original_psth)),
                 '<nlb-column-scheduled-psth>','exec'),namespace)
    tensors._make_psth=namespace['_make_psth']
    return original,original_psth
