"""Exact historical waveform and binary64 text recipe, future execution only.

Copied function bodies from the authenticated direct-signal-v1/build_packet.py.
No original arrays were read or transformed during source preparation.
"""
import json
import numpy as np
LINE_CAP=60000

CHANNELS=('FP1','F3','F7','FC3','C3','C5','P3','P7','P9','PO7','PO3','O1','Oz','Pz','CPz','FP2','Fz','F4','F8','FC4','FCz','Cz','C4','C6','P4','P8','P10','PO8','PO4','O2','HEOG_left','HEOG_right','VEOG_lower')

def need(ok,text):
    if not ok:raise ValueError(text)

def transform(raw):
    need(raw.shape==(200,33,1024)and raw.dtype==np.dtype('float32')and np.isfinite(raw).all(),'Complete finite original epoch geometry')
    ref=(raw[:,CHANNELS.index('P9'),:].astype(np.float64)+raw[:,CHANNELS.index('P10'),:].astype(np.float64))/2
    values=raw[:,[CHANNELS.index('Cz'),CHANNELS.index('Pz')],:].astype(np.float64)-ref[:,None,:]
    values-=values[:,:,:256].mean(axis=2,keepdims=True)
    need(values.shape==(200,2,1024)and values.dtype==np.dtype('float64')and np.isfinite(values).all(),'Complete finite canonical epochs')
    return values

def decimal(value):
    result=format(float(value),'.17g')
    return '-0.0'if result=='-0'else result

def record_bytes(trial_id,channels,label=None):
    need(type(trial_id)is str and len(trial_id)<=48 and channels.shape==(2,1024)and np.isfinite(channels).all(),'One full exact trial')
    wave='['+','.join('['+','.join(decimal(x)for x in row)+']'for row in channels)+']'
    value='{"trial_id":'+json.dumps(trial_id,separators=(',',':'))
    if label is not None:need(type(label)is int and label in(0,1),'Training demonstration label');value+=',"target":'+str(label)
    value+=',"channels":'+wave+'}\n';body=value.encode('utf-8');need(len(body)<=LINE_CAP,'Lossless trial text bound; never truncate')
    parsed=json.loads(body);restored=np.asarray(parsed['channels'],dtype=np.float64)
    need(restored.shape==channels.shape and np.array_equal(restored.view(np.uint64),channels.view(np.uint64)),'Bitwise binary64 text round trip, including signed zero')
    return body,float(np.max(np.abs(restored-channels)))
