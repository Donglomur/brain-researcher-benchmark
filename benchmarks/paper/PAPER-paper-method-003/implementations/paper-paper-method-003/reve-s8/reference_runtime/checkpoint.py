"""Passive optimizer/RNG serialization, without pickle or executable payloads."""
import random
import numpy as np
import torch
from .catalog import need

def pack(value,tensors,prefix):
    if isinstance(value,torch.Tensor):
        key=prefix;need(key not in tensors,'unique passive checkpoint tensor');tensors[key]=value.detach().cpu().clone();return {'tensor':key}
    if isinstance(value,np.ndarray):
        key=prefix;need(key not in tensors,'unique passive checkpoint tensor');tensors[key]=torch.as_tensor(value.astype('int64') if value.dtype.kind=='u' else value.copy());return {'numpy_tensor':key,'dtype':str(value.dtype)}
    if isinstance(value,dict):return {'mapping':[[type(k).__name__,k,pack(v,tensors,prefix+'.'+str(i))] for i,(k,v) in enumerate(value.items())]}
    if isinstance(value,(tuple,list)):return {type(value).__name__:[pack(v,tensors,prefix+'.'+str(i)) for i,v in enumerate(value)]}
    need(value is None or type(value)in(str,int,float,bool),'passive scalar checkpoint');return {'scalar':value}

def unpack(value,tensors):
    if 'tensor' in value:return tensors[value['tensor']].clone()
    if 'numpy_tensor' in value:return tensors[value['numpy_tensor']].numpy().astype(value['dtype'])
    if 'mapping' in value:return {(int(k) if kind=='int' else k):unpack(v,tensors) for kind,k,v in value['mapping']}
    if 'tuple' in value:return tuple(unpack(v,tensors) for v in value['tuple'])
    if 'list' in value:return [unpack(v,tensors) for v in value['list']]
    return value['scalar']

def capture(optimizer,generator,device):
    tensors={};tree=pack({'optimizer':optimizer.state_dict(),'python_rng':random.getstate(),'numpy_rng':np.random.get_state(),'torch_rng':torch.get_rng_state(),'generator_rng':generator.get_state(),'cuda_rng':torch.cuda.get_rng_state(device) if device=='cuda' else None},tensors,'training')
    return tensors,tree

def restore(optimizer,generator,device,tensors,tree):
    state=unpack(tree,tensors);optimizer.load_state_dict(state['optimizer']);random.setstate(state['python_rng']);np.random.set_state(state['numpy_rng']);torch.set_rng_state(state['torch_rng']);generator.set_state(state['generator_rng'])
    if device=='cuda':need(state['cuda_rng'] is not None,'exact CUDA RNG state');torch.cuda.set_rng_state(state['cuda_rng'],device)
