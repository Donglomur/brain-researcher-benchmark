"""Decode the exact published data-only Torch pickle without importing Torch.

This admits only the observed CPU FloatStorage tensor representation. No general
pickle globals, model classes, persistent IDs or arbitrary storage readers run.
"""
from collections import OrderedDict
import hashlib
import io
import math
import pickle
from pathlib import Path
import struct

INPUT_SHA256='29dffd951853a98615827e7b8f3507907f9e0f0ef67e875410778ab4aadd42ab'
INPUT_BYTES=22_055_089
RATS=('achilles','buddy','cicero','gatsby')


class Primitive(pickle.Unpickler):
    def find_class(self,module,name):
        raise ValueError('global not permitted in primitive pickle')
    def persistent_load(self,pid):
        raise ValueError('persistent object not permitted')


class StorageSpecReader(Primitive):
    def find_class(self,module,name):
        if (module,name)==('torch','FloatStorage'):return 'float32'
        raise ValueError('only recorded FloatStorage type allowed')
    def persistent_load(self,pid):
        if type(pid)!=tuple or len(pid)!=6 or pid[0]!='storage' or pid[1]!='float32' or pid[3]!='cpu' or pid[5] is not None:
            raise ValueError('unsupported storage identity')
        if type(pid[2])!=str or type(pid[4])!=int or not 0<pid[4]<=6_000_000:
            raise ValueError('storage extent')
        return pid


def storage_from_bytes(blob):
    if type(blob)!=bytes or len(blob)>INPUT_BYTES:raise ValueError('bounded storage bytes required')
    stream=io.BytesIO(blob)
    if Primitive(stream).load()!=119547037146038801333356 or Primitive(stream).load()!=1001:
        raise ValueError('unexpected Torch legacy storage header')
    info=Primitive(stream).load()
    if info.get('protocol_version')!=1001 or info.get('little_endian') is not True:
        raise ValueError('unsupported storage byte order/version')
    pid=StorageSpecReader(stream).load()
    if Primitive(stream).load()!=[pid[2]]:raise ValueError('storage key mismatch')
    raw_count=stream.read(8)
    if len(raw_count)!=8 or struct.unpack('<Q',raw_count)[0]!=pid[4]:raise ValueError('storage element count')
    raw=stream.read()
    if len(raw)!=4*pid[4]:raise ValueError('storage payload extent')
    return raw,pid[4]


def rebuild_tensor(storage,offset,shape,stride,requires_grad,hooks,*extra):
    if extra or type(shape)!=tuple or len(shape)!=2 or type(stride)!=tuple:
        raise ValueError('only recorded rank-two tensors allowed')
    if any(type(n)!=int or n<=0 for n in shape) or type(offset)!=int or offset<0 or len(stride)!=2 or any(type(n)!=int or n<=0 for n in stride) or requires_grad is not False or hooks:
        raise ValueError('noncanonical tensor layout or hooks')
    raw,count=storage
    last=offset+sum((n-1)*step for n,step in zip(shape,stride))
    if last>=count:raise ValueError('tensor view exceeds storage')
    return {'shape':shape,'stride':stride,'storage_offset':offset,'storage_elements':count,'dtype':'<f4','raw':raw}


class DataReader(Primitive):
    def find_class(self,module,name):
        allowed={('torch._utils','_rebuild_tensor_v2'):rebuild_tensor,
                 ('torch.storage','_load_from_bytes'):storage_from_bytes,
                 ('collections','OrderedDict'):OrderedDict}
        try:return allowed[module,name]
        except KeyError as error:raise ValueError('unapproved data pickle global') from error


def read_pinned(path):
    path=Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size!=INPUT_BYTES:
        raise ValueError('exact input file required')
    with path.open('rb') as file:raw=file.read(INPUT_BYTES+1)
    if len(raw)!=INPUT_BYTES or hashlib.sha256(raw).hexdigest()!=INPUT_SHA256:
        raise ValueError('input pin mismatch')
    stream=io.BytesIO(raw);data=DataReader(stream).load()
    if stream.read(1):raise ValueError('trailing pickle bytes')
    if type(data)!=dict or tuple(data)!=RATS:raise ValueError('exact four-rat source identity')
    for rat in RATS:
        item=data[rat]
        if type(item)!=dict or set(item)!={'neural','continuous_index'}:raise ValueError('source fields')
        if item['neural']['shape'][0]!=item['continuous_index']['shape'][0] or item['continuous_index']['shape'][1]!=3:
            raise ValueError('time/behavior alignment')
    return data


if __name__=='__main__':
    import json
    root=Path(__file__).resolve().parents[1]
    data=read_pinned(root/'private/input/rat_data.pkl')
    metadata={rat:{name:{key:entry[key] for key in ('shape','dtype','stride','storage_offset','storage_elements')} for name,entry in data[rat].items()} for rat in RATS}
    (root/'source-evidence/INPUT_SCHEMA.json').write_text(json.dumps({'source_sha256':INPUT_SHA256,'arrays':metadata,'tensor_value_output':False,'torch_imported':False,'scientific_operations':0},indent=2)+'\n')
    print(json.dumps(metadata))
