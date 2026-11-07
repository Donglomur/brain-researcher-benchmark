"""Read numeric-only prepared inputs, preserving original unit/trial association."""
import gzip
from pathlib import Path
import numpy as np


def load_panel(folder, panel):
    folder=Path(folder)
    if panel not in ('continuous','trials'):raise ValueError('Unknown panel')
    arrays=[]
    for suffix in ('times','offsets'):
        with gzip.open(folder/(panel+'_'+suffix+'.npy.gz'),'rb') as f:
            arrays.append(np.load(f,allow_pickle=False))
    times,offsets=arrays
    records=100000 if panel=='continuous' else 4000000
    if times.ndim!=1 or times.dtype!=np.dtype('<f8') or offsets.shape!=(records+1,) or offsets.dtype!=np.dtype('<i8') or offsets[0]!=0 or offsets[-1]!=len(times) or np.any(np.diff(offsets)<0):
        raise ValueError('Prepared input layout mismatch')
    return times,offsets


def records(times,offsets,start,count):
    return [times[offsets[i]:offsets[i+1]] for i in range(start,start+count)]
