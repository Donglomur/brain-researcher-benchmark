"""Complete MAT-v5 loading/census on an already installed numerical runtime.

This is a new prospective host route. It does not run or qualify the historical
Docker runtime inventory. Importing this module reads no original data.
"""
from dataclasses import dataclass
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import struct
import types

HERE=Path(__file__).resolve().parent
SOURCE={'bytes':180725660,
        'sha256':'3db6c47e61f51230ea4a83b5722f1c019337ab09f7ad836b36ce934a0270ca86',
        'md5':'852fd759272db2e9be69356264b032ca'}
REUSED_SHA='ae87e789d9edcef08ac5918cb2d924e3704b5850646a170d3c8207b3cae24741'
VERSIONS={'numpy':'2.4.6','scipy':'1.17.1'}
TASK='NEURAL-DISC-20261114-VESTIBULAR-VO'

FAILURE_CODES=frozenset('''source_path_is_linked source_extent source_changed source_pin
prospective_host_numerical_version_mismatch positive_native_limits native_limits_cannot_expand_implicitly
exact_original_descriptor bounded_original_extent original_path_is_linked ordinary_original_extent
native_reader_budget native_seek_mode native_seek_extent original_truncated original_grew
complete_original_checksum MAT_v5_byte_order only_selected_MAT_v5_family original_identity_changed
explicit_source_path unknown_top_variable exact_MAT_coordinate coordinate_matches_original_orientation
exact_MAT_struct_field source_manifest_schema complete_census_source_roster complete_source_identity
bounded_census_receipt complete_census_write_cap complete_census_write bounded_memory_observation
census_sampled_RSS_limit census_memory_observation_failed bounded_worker_diagnostics census_wall_deadline
nonnegative_other_reservations fresh_operator_output preserve_global_disk_floor observed_census_zero_exit
worker_completion_join complete_source_worker_join complete_schema_extent complete_schema_output_identity
census_worker_alarm'''.split())
PRESERVED_FAILURE_CODES=frozenset({
 'complete census output budget','complete tree depth/node budget',
 'unsupported MATLAB object/function/opaque class','unsupported sparse storage format',
 'decoded-array accounting budget','invalid array dimensions','complete text metadata budget',
 'unsupported decoded value type','duplicate/reserved top variable',
 'unsupported top-level MATLAB class','top-variable coverage mismatch'})


class NativeError(ValueError):
    def __init__(self,code):
        self.code=code
        super().__init__(code)


def failure_record(error):
    code=getattr(error,'code',None)
    allowed=(type(error) is NativeError and code in FAILURE_CODES) or (
        type(error).__name__=='Refusal' and code in PRESERVED_FAILURE_CODES)
    return {'type':type(error).__name__,'code':code if allowed else None,
            'third_party_exception_prose_disclosed':False}


def need(value,code):
    if not value:
        raise NativeError(code)


def encoded(value):
    return (json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()


def pin(body):
    return {'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}


def read_source(path,expected=None,limit=100000):
    path=Path(path)
    need(not any(p.is_symlink() for p in (path,*path.parents)),'source_path_is_linked')
    with os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK),'rb') as stream:
        before=os.fstat(stream.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and 0<before.st_size<=limit,'source_extent')
        body=stream.read(before.st_size+1);after=os.fstat(stream.fileno());named=path.stat()
    keys=('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns')
    need(len(body)==before.st_size and all(getattr(before,k)==getattr(after,k)==getattr(named,k) for k in keys),'source_changed')
    need(expected is None or pin(body)['sha256']==expected,'source_pin')
    return body


def parser_module():
    body=read_source(HERE/'reused/census_worker.py',REUSED_SHA)
    module=types.ModuleType('vestibular_preserved_census_parser')
    module.__file__=str(HERE/'reused/census_worker.py')
    exec(compile(body,module.__file__,'exec'),module.__dict__)
    return module


def numerical_environment():
    import numpy as np
    import scipy
    import scipy.io as sio
    import scipy.sparse as sparse
    need(np.__version__==VERSIONS['numpy'] and scipy.__version__==VERSIONS['scipy'],
         'prospective_host_numerical_version_mismatch')
    return np,sio,sparse


@dataclass(frozen=True)
class Limits:
    read_bytes:int=3*SOURCE['bytes']+8*1024**2
    decoded_array_bytes:int=2*1024**3
    census_bytes:int=16*1024**2
    nodes:int=100000
    depth:int=64
    text_bytes:int=256*1024

    def validate(self):
        need(all(type(v) is int and v>0 for v in vars(self).values()),'positive_native_limits')
        maximum=Limits()
        need(all(getattr(self,k)<=getattr(maximum,k) for k in vars(self)),'native_limits_cannot_expand_implicitly')


class OriginalStream:
    """One regular descriptor for hashing, complete reading and final identity."""
    def __init__(self,path,descriptor,limit):
        self.path=Path(path).absolute();self.used=0;self.limit=limit
        need(set(descriptor)=={'bytes','sha256','md5'},'exact_original_descriptor')
        need(type(descriptor['bytes']) is int and 128<=descriptor['bytes']<=SOURCE['bytes'],'bounded_original_extent')
        need(not any(p.is_symlink() for p in (self.path,*self.path.parents)),'original_path_is_linked')
        self.file=os.fdopen(os.open(self.path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK),'rb')
        self.before=os.fstat(self.file.fileno());self.size=descriptor['bytes'];self.expected=descriptor
        try:
            need(stat.S_ISREG(self.before.st_mode) and self.before.st_nlink==1
                 and self.before.st_size==self.size,'ordinary_original_extent')
        except BaseException:
            self.file.close();raise

    def read(self,size=-1):
        if size is None or size<0:
            size=self.size-self.tell()
        need(type(size) is int and size>=0 and size<=self.limit-self.used,'native_reader_budget')
        body=self.file.read(size);self.used+=len(body)
        return body

    def seek(self,offset,whence=0):
        need(type(offset) is int and whence in (0,1,2),'native_seek_mode')
        target=offset if whence==0 else self.tell()+offset if whence==1 else self.size+offset
        need(0<=target<=self.size,'native_seek_extent')
        return self.file.seek(target)

    def tell(self):
        return self.file.tell()

    def authenticate(self):
        self.seek(0);sha=hashlib.sha256();md5=hashlib.md5();header=b'';count=0
        while count<self.size:
            block=self.read(min(262144,self.size-count))
            need(bool(block),'original_truncated')
            if not header:
                header=block[:128]
            count+=len(block);sha.update(block);md5.update(block)
        need(self.read(1)==b'','original_grew')
        actual={'bytes':count,'sha256':sha.hexdigest(),'md5':md5.hexdigest()}
        need(actual==self.expected,'complete_original_checksum')
        self.verify_identity()
        need(len(header)==128 and header[126:128] in (b'IM',b'MI'),'MAT_v5_byte_order')
        order='<' if header[126:128]==b'IM' else '>'
        need(struct.unpack(order+'H',header[124:126])[0]==0x0100,'only_selected_MAT_v5_family')
        self.seek(0)
        return actual

    def verify_identity(self):
        after=os.fstat(self.file.fileno());named=self.path.stat()
        keys=('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns')
        need(all(getattr(self.before,k)==getattr(after,k)==getattr(named,k) for k in keys),'original_identity_changed')

    def close(self):
        self.file.close()


@dataclass
class Document:
    original:dict
    top_variables:list
    values:dict
    census_summary:dict


def load_complete(path,descriptor,output,limits=Limits(),*,diagnostics=None):
    """Complete all variables and nested nodes; no physical roles are inferred.

    ``output`` is an operator-owned binary stream. The returned arrays and all
    census text stay private. Limits on decoded bytes are post-allocation
    accounting; a separately selected supervisor must enforce resident memory.
    The public census CLI fixes ``descriptor`` to the complete original.
    """
    limits.validate();worker=parser_module();np,sio,sparse=numerical_environment()
    for attribute,value in [('MAX_ARRAY_BYTES',limits.decoded_array_bytes),('MAX_CENSUS_BYTES',limits.census_bytes),
                            ('MAX_NODES',limits.nodes),('MAX_DEPTH',limits.depth),('MAX_TEXT_BYTES',limits.text_bytes)]:
        setattr(worker,attribute,value)
    state={} if diagnostics is None else diagnostics
    state.update(original_hash_complete=False,all_variables_loaded=False,complete_nested_traversal=False,
                 original_bytes_delivered=0,nodes=0,census_bytes=0,decoded_array_accounting_bytes=0)
    stream=None;emitter=None
    try:
        stream=OriginalStream(path,descriptor,limits.read_bytes)
        original=stream.authenticate();state['original_hash_complete']=True
        top,names,loaded=worker.read_all_variables(stream,sio)
        state['all_variables_loaded']=True
        emitter=worker.Emitter(output,np,sparse)
        emitter.emit({'schema':'vestibular_complete_host_MAT_census_v1','original':original,
                      'index_convention':'zero-based coordinates; Fortran traversal',
                      'top_variables':[{'name':name,'shape':list(shape),'class':kind} for name,shape,kind in top],
                      'biological_roles_inferred':False,'protected_output':True})
        for name in names:
            emitter.walk(loaded[name],[name],name)
        stream.verify_identity();state['complete_nested_traversal']=True
        summary={'top_variable_count':len(names),'nodes':emitter.nodes,'census_bytes':emitter.bytes,
                 'decoded_array_accounting_bytes':emitter.array_bytes,'text_metadata_bytes':emitter.text_bytes,
                 'scalar_name_matches':len(emitter.scalar_candidates),
                 'original_bytes_delivered':stream.used,'biological_membership_verified':False,
                 'physical_roles_verified':False,'new_prospective_host_route':True,
                 'historical_Docker_inventory_qualification_claimed':False}
        return Document(original,[{'name':n,'shape':list(s),'class':k} for n,s,k in top],
                        {name:loaded[name] for name in names},summary)
    finally:
        if emitter is not None:
            state.update(nodes=emitter.nodes,census_bytes=emitter.bytes,decoded_array_accounting_bytes=emitter.array_bytes)
        if stream is not None:
            state['original_bytes_delivered']=stream.used;stream.close()


def resolve(document,path):
    """Resolve an exact census path without squeezing/transposing or alias guesses."""
    import numpy as np
    need(isinstance(path,list) and path and isinstance(path[0],str),'explicit_source_path')
    need(path[0] in document.values,'unknown_top_variable')
    value=document.values[path[0]]
    for part in path[1:]:
        if isinstance(part,dict):
            need(set(part)=={'index'} and isinstance(part['index'],list),'exact_MAT_coordinate')
            index=part['index']
            need(isinstance(value,np.ndarray) and len(index)==value.ndim
                 and all(type(i) is int and 0<=i<n for i,n in zip(index,value.shape)),
                 'coordinate_matches_original_orientation')
            value=value[tuple(index)]
        else:
            need(isinstance(part,str) and isinstance(value,np.void) and value.dtype.names
                 and part in value.dtype.names,'exact_MAT_struct_field')
            value=value[part]
    return value
