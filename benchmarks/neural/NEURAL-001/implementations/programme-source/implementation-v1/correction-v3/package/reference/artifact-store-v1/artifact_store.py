"""Bounded operator artifact storage, source-only delivery.

No filesystem or numeric work occurs on import. Caller qualification, private
namespace ownership and external process isolation remain independent gates.
A callback object or handle is NOT proof that those gates have been qualified.
"""
import ast
from dataclasses import dataclass
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import stat
import struct
from types import MappingProxyType
import uuid
import zipfile

ROLES=frozenset(('code','method','model','state','program','method_recipe','frozen_state','training_report','prediction','method_trace','submission','protected_report','uncertainty_report','current_source','action_source'))
OPERATOR_ONLY=frozenset(('protected_report','uncertainty_report'))
HEX64=re.compile(r'^[0-9a-f]{64}$')
CHUNK=65536
MAX_HEADER=4096

class ArtifactError(ValueError):
    pass

def require(condition,message):
    if not condition:raise ArtifactError(message)

def canonical_json(value,cap=None):
    # Preflight plain-object size/depth without allocating an oversized encoded
    # string. This is a logical encoded-byte bound, not Python/RSS accounting.
    def text_size(text):
        n=2
        for c in text:
            v=ord(c);n+=2 if c in ('"','\\') else (6 if v<32 or 127<=v<=65535 else (12 if v>65535 else 1))
        return n
    def measure(x,depth=0):
        require(depth<=32,'Bounded metadata nesting')
        if x is None:return 4
        if type(x) is bool:return 4 if x else 5
        if type(x) is int:
            require(x.bit_length()<=64,'Bounded metadata integer');return len(str(x))
        if type(x) is float:
            require(math.isfinite(x),'Finite metadata number');return len(json.dumps(x))
        if type(x) is str:return text_size(x)
        if type(x) in (list,tuple):
            n=2
            for i,item in enumerate(x):
                n+=int(i>0)+measure(item,depth+1)
                if cap is not None:require(n<=cap,'Metadata encoding ceiling')
            return n
        if type(x) is dict:
            n=2
            for i,(key,item) in enumerate(x.items()):
                require(type(key) is str,'Plain string metadata keys')
                n+=int(i>0)+text_size(key)+1+measure(item,depth+1)
                if cap is not None:require(n<=cap,'Metadata encoding ceiling')
            return n
        raise ArtifactError('Plain finite JSON metadata only')
    size=measure(value)
    if cap is not None:require(size<=cap,'Metadata encoding ceiling')
    try:
        body=json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode('ascii')
        if cap is not None:require(len(body)<=cap,'Actual metadata encoding ceiling')
        return body
    except (ValueError,TypeError,OverflowError) as error:raise ArtifactError('Finite plain JSON metadata required') from error


def audited(operation):
    def decorate(function):
        def call(self,*args,**kwargs):
            role=kwargs.get('role','model' if operation=='put_reference_state' else None)
            if operation=='put_bytes' and len(args)>1:role=args[1]
            if args and type(args[0]) is dict and operation in ('read_exact','qualified_path','load_reference_state'):role=args[0].get('role')
            role=role if type(role) is str and role in ROLES else 'forbidden'
            try:return function(self,*args,**kwargs)
            except BaseException as error:self._failure(operation,role,error);raise
        return call
    return decorate


def strict_json(body):
    def pairs(items):
        result={}
        for key,value in items:
            require(key not in result,'Duplicate JSON field');result[key]=value
        return result
    def bad(value):raise ArtifactError('Nonfinite JSON constant')
    try:return json.loads(body.decode('utf-8',errors='strict'),object_pairs_hook=pairs,parse_constant=bad)
    except (UnicodeError,json.JSONDecodeError) as error:raise ArtifactError('Strict UTF-8 JSON required') from error

def pin(body):
    return dict(bytes=len(body),sha256=hashlib.sha256(body).hexdigest())

def _pin_valid(value):
    return type(value) is dict and set(value)=={'bytes','sha256'} and type(value['bytes']) is int and value['bytes']>0 and type(value['sha256']) is str and HEX64.fullmatch(value['sha256']) is not None

def _stamp(st):
    return tuple(getattr(st,name) for name in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns','st_nlink','st_mode','st_uid'))

class ArtifactStore:
    """Trusted operator namespace; no target/private-key artifact roles.

    `meter(event)` must reserve each requested logical charge before returning
    True. Reservations are never refunded on failure. Observations and failures
    are separately emitted; they must not be charged a second time as reserves.
    The caller persists the audit and supervises the original clock externally.
    """
    def __init__(self, trusted_root, *, role_caps, metadata_cap, expanded_cap,
                 meter, qualify, max_audit_events):
        require(type(role_caps) is dict and role_caps and set(role_caps)<=ROLES,'Explicit ceiling for each configured safe role')
        require(all(type(n) is int and n>0 for n in role_caps.values()),'Positive role ceilings')
        require(type(metadata_cap) is int and metadata_cap>0 and type(expanded_cap) is int and expanded_cap>0,'Explicit metadata and expanded ceilings')
        require(type(max_audit_events) is int and max_audit_events>0,'Bounded complete audit capacity')
        require(callable(meter) and callable(qualify),'External budget and qualification callbacks required')
        root=Path(trusted_root)
        require(root.is_absolute() and '..' not in root.parts,'Operator-supplied canonical absolute namespace')
        self.root=root;self.role_caps=dict(role_caps);self.metadata_cap=metadata_cap;self.expanded_cap=expanded_cap
        self.meter=meter;self.qualify=qualify;self.max_audit_events=max_audit_events
        self._audit=[];self.terminal_error=None
        # Deliberately do not stat/create/open the namespace in the constructor.

    @property
    def audit(self):return tuple(MappingProxyType(dict(row)) for row in self._audit)

    def _event(self,event):
        if len(self._audit)>=self.max_audit_events:
            self.terminal_error='Artifact audit capacity exhausted; operation refused'
            raise ArtifactError(self.terminal_error)
        row=dict(event);self._audit.append(row)
        try:accepted=self.meter(MappingProxyType(row))
        except BaseException:
            self.terminal_error='External meter raised; reserved costs retained';raise
        if row['event']=='reserve':require(accepted is True,'External byte/deadline reservation refused')

    def _reserve(self,kind,count,operation,role):
        require(kind in ('read','write','expanded') and type(count) is int and count>=0,'Typed logical charge')
        self._event(dict(event='reserve',kind=kind,bytes=count,operation=operation,role=role))

    def _admit(self,role,operation,*,handle=None,audience='operator'):
        require(role in ROLES and role in self.role_caps,'Targets, private keys, unknown or unconfigured roles are forbidden')
        require(audience in ('operator','candidate'),'Explicit artifact audience')
        require(audience!='candidate' or role not in OPERATOR_ONLY,'Protected/uncertainty reports are operator-only')
        request=dict(role=role,operation=operation,audience=audience,operator_only=role in OPERATOR_ONLY,candidate_mountable=role not in OPERATOR_ONLY)
        if handle is not None:request['handle']=dict(role=handle['role'],pin=dict(handle['pin']),custody_id=handle['custody_id'])
        require(self.qualify(MappingProxyType(request)) is True,'Caller scientific/runtime qualification is absent')
        self._event(dict(event='admitted_operation',operation=operation,role=role))

    def _failure(self,operation,role,error,**details):
        row=dict(event='failure',operation=operation,role=role,error_type=type(error).__name__,**details)
        try:self._event(row)
        except BaseException:self.terminal_error=canonical_json(row).decode('ascii')

    def _root_fd(self):
        flags=os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW
        fd=os.open('/',flags)
        try:
            for part in self.root.parts[1:]:
                new=os.open(part,flags,dir_fd=fd);os.close(fd);fd=new
            st=os.fstat(fd)
            require(stat.S_ISDIR(st.st_mode) and st.st_uid==os.getuid() and not (stat.S_IMODE(st.st_mode)&0o022),'Private owner-controlled root directory required')
            return fd
        except BaseException:os.close(fd);raise

    def _directory(self,parent,name,create):
        require(name in ROLES or name in ('objects','custody'),'Derived namespace component only')
        if create:
            try:os.mkdir(name,0o700,dir_fd=parent)
            except FileExistsError:pass
        fd=os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=parent)
        st=os.fstat(fd)
        if not (stat.S_ISDIR(st.st_mode) and st.st_uid==os.getuid() and stat.S_IMODE(st.st_mode)==0o700):
            os.close(fd);raise ArtifactError('Private fixed-mode derived directory required')
        return fd

    def _read_file(self,directory,name,cap,role,operation,expected=None):
        require(type(cap) is int and cap>0,'Positive bounded read')
        fd=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=directory)
        try:
            before=os.fstat(fd)
            require(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_uid==os.getuid() and stat.S_IMODE(before.st_mode)==0o444,'Ordinary sealed owner file with one link required')
            require(0<before.st_size<=cap,'Artifact length exceeds declared read ceiling')
            if expected is not None:require(before.st_size==expected['bytes'],'Exact pinned extent')
            self._reserve('expanded',before.st_size,operation+'_buffer',role)
            chunks=[];actual=0
            while actual<before.st_size:
                requested=min(CHUNK,before.st_size-actual);self._reserve('read',requested,operation,role)
                chunk=os.read(fd,requested)
                self._event(dict(event='observed',operation=operation,role=role,bytes=len(chunk)))
                require(chunk,'Unexpected artifact EOF');chunks.append(chunk);actual+=len(chunk)
            self._reserve('read',1,operation+'_eof',role);extra=os.read(fd,1)
            require(not extra and _stamp(before)==_stamp(os.fstat(fd)),'Stable complete artifact read required')
            # Joining chunks may allocate another complete byte buffer.
            self._reserve('expanded',actual,operation+'_join',role);body=b''.join(chunks)
            if expected is not None:
                self._reserve('read',len(body),operation+'_hash',role);require(pin(body)==expected,'Artifact content identity changed')
            return body
        finally:os.close(fd)

    def _seal(self,directory,name,body,role,operation):
        """Write a unique temporary file then atomically link without overwrite.

        The final object has one link after temporary-name unlink. That brief
        two-link transition is never accepted by a reader. Failed writes are
        charged and their observed extent recorded; own temporary files are
        removed without deleting any preexisting final object.
        """
        temp='.pending-'+uuid.uuid4().hex;fd=None;written=0;linked=False
        try:
            fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=directory)
            view=memoryview(body)
            while written<len(body):
                part=view[written:written+CHUNK];self._reserve('write',len(part),operation,role)
                count=os.write(fd,part);require(count>0,'Zero-length artifact write')
                written+=count;self._event(dict(event='observed',operation=operation,role=role,bytes=count))
            os.fsync(fd);os.fchmod(fd,0o444);os.fsync(fd);os.close(fd);fd=None
            try:
                os.link(temp,name,src_dir_fd=directory,dst_dir_fd=directory,follow_symlinks=False);linked=True
            except FileExistsError:
                self._reserve('read',len(body),operation+'_dedup_body_hash',role);expected=pin(body)
                self._read_file(directory,name,len(body),role,operation+'_dedup',expected)
            os.unlink(temp,dir_fd=directory);temp=None;os.fsync(directory)
            # No read/hash claim is made merely from chmod or file naming.
        except BaseException as error:
            extent=None
            if fd is not None:
                try:extent=os.fstat(fd).st_size
                except OSError:pass
            self._failure(operation,role,error,reported_written_bytes=written,observed_partial_extent=extent,final_link_created=linked)
            raise
        finally:
            if fd is not None:os.close(fd)
            if temp is not None:
                try:os.unlink(temp,dir_fd=directory)
                except FileNotFoundError:pass

    @audited('put_bytes')
    def put_bytes(self,body,role,metadata):
        self._admit(role,'put_bytes')
        require(type(body) is bytes and 0<len(body)<=self.role_caps[role],'Bounded immutable bytes required')
        self._reserve('read',self.metadata_cap,'metadata_preflight',role);self._reserve('expanded',self.metadata_cap,'metadata_encode',role)
        metadata_bytes=canonical_json(metadata,self.metadata_cap);require(type(metadata) is dict,'Bounded plain object metadata')
        metadata=strict_json(metadata_bytes)  # freeze caller-owned containers
        self._reserve('read',len(body),'put_body_hash',role);identity=pin(body)
        record=dict(schema='neural001_artifact_custody_v1',role=role,pin=identity,metadata=metadata,policy=dict(operator_only=role in OPERATOR_ONLY,candidate_mountable=role not in OPERATOR_ONLY),nonce=uuid.uuid4().hex)
        self._reserve('expanded',self.metadata_cap+4096,'custody_encode',role)
        record_body=canonical_json(record,self.metadata_cap+4096)
        self._reserve('read',len(record_body),'custody_record_hash',role);custody_id=hashlib.sha256(record_body).hexdigest()
        root=objects=role_dir=custody=None
        try:
            root=self._root_fd();objects=self._directory(root,'objects',True);role_dir=self._directory(objects,role,True);custody=self._directory(root,'custody',True)
            self._seal(role_dir,identity['sha256']+'.blob',body,role,'put_object')
            self._seal(custody,custody_id+'.json',record_body,role,'put_custody')
            self._event(dict(event='sealed',operation='put_bytes',role=role,pin=identity,custody_id=custody_id))
            return dict(role=role,pin=identity,custody_id=custody_id)
        except BaseException as error:self._failure('put_bytes',role,error);raise
        finally:
            for fd in (custody,role_dir,objects,root):
                if fd is not None:os.close(fd)

    def _handle(self,handle):
        require(type(handle) is dict and set(handle)=={'role','pin','custody_id'},'Typed artifact handle; arbitrary paths forbidden')
        role=handle['role'];require(role in ROLES and role in self.role_caps and _pin_valid(handle['pin']),'Allowed role and exact content pin')
        require(type(handle['custody_id']) is str and HEX64.fullmatch(handle['custody_id']),'Content-addressed custody identifier')
        require(handle['pin']['bytes']<=self.role_caps[role],'Role ceiling')
        return role

    def _read_bound(self,handle,cap,*,audience='operator'):
        role=self._handle(handle);self._admit(role,'read_exact',handle=handle,audience=audience)
        require(type(cap) is int and 0<handle['pin']['bytes']<=cap<=self.role_caps[role],'Caller bounded exact read')
        root=objects=role_dir=custody=None
        try:
            root=self._root_fd();custody=self._directory(root,'custody',False)
            record_body=self._read_file(custody,handle['custody_id']+'.json',self.metadata_cap+4096,role,'read_custody')
            self._reserve('read',len(record_body),'custody_hash',role)
            require(hashlib.sha256(record_body).hexdigest()==handle['custody_id'],'Exact content-addressed custody record')
            record=strict_json(record_body)
            require(type(record) is dict and set(record)=={'schema','role','pin','metadata','policy','nonce'} and record['schema']=='neural001_artifact_custody_v1','Exact custody schema')
            require(record['role']==role and record['pin']==handle['pin'],'Custody role/content binding')
            require(record['policy']==dict(operator_only=role in OPERATOR_ONLY,candidate_mountable=role not in OPERATOR_ONLY),'Exact role audience policy binding')
            self._reserve('read',self.metadata_cap,'custody_metadata_preflight',role);self._reserve('expanded',self.metadata_cap,'custody_metadata_encode',role)
            require(type(record['metadata']) is dict and len(canonical_json(record['metadata'],self.metadata_cap))<=self.metadata_cap,'Bounded custody metadata')
            require(type(record['nonce']) is str and re.fullmatch('[0-9a-f]{32}',record['nonce']),'Custody nonce syntax')
            objects=self._directory(root,'objects',False);role_dir=self._directory(objects,role,False)
            body=self._read_file(role_dir,handle['pin']['sha256']+'.blob',cap,role,'read_object',handle['pin'])
            return body,record['metadata']
        except BaseException as error:self._failure('read_exact',role,error);raise
        finally:
            for fd in (role_dir,objects,custody,root):
                if fd is not None:os.close(fd)

    @audited('read_exact')
    def read_exact(self,handle,cap,*,audience='operator'):
        return self._read_bound(handle,cap,audience=audience)[0]

    @audited('qualified_path')
    def qualified_path(self,handle,cap,*,audience='candidate'):
        """Owner-only path after authentication; not a process-isolation proof.

        A path is inherently subject to later replacement. The external launcher
        must bind/mount the exact inode or immutable snapshot and independently
        observe it; never interpret this function as a TOCTOU-free FD transfer.
        """
        self._read_bound(handle,cap,audience=audience)
        return str(self.root/'objects'/handle['role']/(handle['pin']['sha256']+'.blob'))

    @audited('put_reference_state')
    def put_reference_state(self,metadata,arrays,*,role='model'):
        self._admit(role,'put_reference_state');require(role in ('model','state','frozen_state'),'Reference model/state role required')
        self._reserve('read',self.metadata_cap,'state_metadata_preflight',role);self._reserve('expanded',self.metadata_cap,'state_metadata_encode',role)
        metadata_body=canonical_json(metadata,self.metadata_cap);metadata=strict_json(metadata_body)
        shapes=_state_schema(metadata,self.metadata_cap)
        require(type(arrays) in (dict,MappingProxyType) and set(arrays)==set(shapes),'Exact named reference arrays')
        import numpy as np  # only after explicit caller qualification
        # Reserve complete prospective output buffers before any array encoding.
        array_total=sum(metadata['arrays'][name]['bytes'] for name in shapes)
        upper=len(metadata_body)+array_total+(MAX_HEADER+512)*(len(shapes)+1)
        require(upper<=self.expanded_cap and upper<=self.role_caps[role],'Complete state serialization ceiling; never truncate')
        self._reserve('expanded',upper*2,'state_zip_buffers',role)
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_STORED,allowZip64=False) as z:
            _zip_write(z,'metadata.json',metadata_body)
            for name,shape in shapes.items():
                array=arrays[name];row=metadata['arrays'][name]
                require(type(array) is np.ndarray and array.dtype==np.dtype('<f8') and array.shape==shape and array.flags.c_contiguous,'Exact finite C-order float64 state array')
                checks=3 if name.endswith('scale') else 2
                self._reserve('read',checks*array.nbytes,'state_array_finite_and_hash',role)
                self._reserve('expanded',(checks-1)*array.size,'state_finite_boolean_buffer',role)
                require(np.isfinite(array).all(),'Finite state array')
                if name.endswith('scale'):require(np.all(array>0),'Positive trained scale')
                require(hashlib.sha256(memoryview(array).cast('B')).hexdigest()==row['sha256'],'State array content pin')
                self._reserve('expanded',2*(array.nbytes+MAX_HEADER),'state_npy_buffer',role)
                self._reserve('read',array.nbytes,'state_array_encode',role)
                encoded=_encode_npy(array,shape)
                _zip_write(z,'arrays/'+name+'.npy',encoded)
        body=stream.getvalue();require(len(body)<=self.role_caps[role],'Actual state ZIP ceiling')
        self._reserve('read',len(metadata_body),'state_metadata_hash',role)
        return self.put_bytes(body,role,dict(format='neural001_reference_bundle_v1',metadata_sha256=hashlib.sha256(metadata_body).hexdigest(),array_count=len(shapes),expanded_array_bytes=array_total))

    @audited('load_reference_state')
    def load_reference_state(self,handle,cap):
        role=self._handle(handle);self._admit(role,'load_reference_state',handle=handle);require(role in ('model','state','frozen_state'),'Reference model/state role required')
        body,custody_metadata=self._read_bound(handle,cap)
        require(type(custody_metadata) is dict and set(custody_metadata)=={'format','metadata_sha256','array_count','expanded_array_bytes'} and custody_metadata['format']=='neural001_reference_bundle_v1','Exact bundle custody metadata')
        import numpy as np  # only after caller qualification
        self._reserve('read',min(len(body),26),'zip_preflight',role);central_size=_zip_preflight(body)
        self._reserve('read',central_size,'zip_directory_read',role);self._reserve('expanded',central_size,'zip_directory_buffer',role)
        with zipfile.ZipFile(io.BytesIO(body),'r') as z:
            rows=z.infolist();require(1<len(rows)<=16 and len({r.filename for r in rows})==len(rows),'Bounded unique bundle members')
            require(all(r.compress_type==zipfile.ZIP_STORED and not(r.flag_bits&1) and r.file_size==r.compress_size and stat.S_IFMT(r.external_attr>>16)==stat.S_IFREG for r in rows),'Stored ordinary nonencrypted members only')
            require(sum(r.file_size for r in rows)<=self.expanded_cap,'Expanded state ceiling')
            mr=[r for r in rows if r.filename=='metadata.json'];require(len(mr)==1 and 0<mr[0].file_size<=self.metadata_cap,'Bounded sole state metadata')
            self._reserve('read',mr[0].compress_size,'state_metadata_zip_read',role)
            self._reserve('expanded',mr[0].file_size,'state_metadata_expand',role);mb=z.read(mr[0])
            self._reserve('read',2*len(mb),'state_metadata_parse_and_hash',role);metadata=strict_json(mb)
            require(hashlib.sha256(mb).hexdigest()==custody_metadata['metadata_sha256'],'Exact model metadata pin')
            self._reserve('read',self.metadata_cap,'loaded_state_metadata_preflight',role);self._reserve('expanded',self.metadata_cap,'loaded_state_metadata_encode',role)
            canonical_json(metadata,self.metadata_cap)
            shapes=_state_schema(metadata,self.metadata_cap)
            require({r.filename for r in rows}=={'metadata.json'}|{'arrays/'+name+'.npy' for name in shapes},'Exact array member set')
            total=sum(metadata['arrays'][name]['bytes'] for name in shapes)
            require(custody_metadata['array_count']==len(shapes) and custody_metadata['expanded_array_bytes']==total,'Exact bundle size binding')
            arrays={}
            for name,shape in shapes.items():
                r=z.getinfo('arrays/'+name+'.npy');expected=metadata['arrays'][name]
                require(expected['bytes']+10<r.file_size<=expected['bytes']+10+MAX_HEADER,'Bounded exact NPY member extent')
                self._reserve('read',r.compress_size,'state_array_zip_read',role)
                self._reserve('expanded',r.file_size,'state_array_expand',role);encoded=z.read(r)
                array=_decode_npy(encoded,shape,np)
                checks=3 if name.endswith('scale') else 2
                self._reserve('read',checks*array.nbytes,'state_array_validate',role)
                self._reserve('expanded',(checks-1)*array.size,'state_finite_boolean_buffer',role)
                require(np.isfinite(array).all() and hashlib.sha256(memoryview(array).cast('B')).hexdigest()==expected['sha256'],'Finite exact pinned array')
                if name.endswith('scale'):require(np.all(array>0),'Positive trained scale')
                require(not array.flags.writeable,'Bytes-backed immutable decoded state')
                arrays[name]=array
        # The owner then applies reference_engine.restore_state and authentic
        # provenance/source receipts; this loader alone does not prove training.
        return metadata,MappingProxyType(arrays)


def _zip_preflight(body):
    require(len(body)>=26 and body[:4]==b'PK\x03\x04','Ordinary ZIP beginning')
    signature,disk,start_disk,on_disk,total,size,offset,comment=struct.unpack('<4s4H2LH',body[-22:])
    require(signature==b'PK\x05\x06' and disk==start_disk==comment==0,'Single-disk comment-free non-ZIP64 archive')
    require(on_disk==total and 1<total<=16 and 0<size<=65536 and offset+size==len(body)-22,'Bounded complete central directory before ZipFile construction')
    return size


def _zip_write(z,name,body):
    info=zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_STORED
    info.create_system=3;info.external_attr=(stat.S_IFREG|0o444)<<16
    z.writestr(info,body)


def _encode_npy(array,shape):
    text=repr(dict(descr='<f8',fortran_order=False,shape=shape)).encode('ascii')
    padding=(-((10+len(text)+1)%64))%64;header=text+b' '*padding+b'\n'
    require(0<len(header)<=MAX_HEADER,'Bounded NPY1 header')
    return b'\x93NUMPY\x01\x00'+len(header).to_bytes(2,'little')+header+array.tobytes(order='C')


def _decode_npy(body,shape,np):
    require(body[:8]==b'\x93NUMPY\x01\x00' and len(body)>=10,'NPY1 only')
    n=int.from_bytes(body[8:10],'little');require(0<n<=MAX_HEADER and 10+n<=len(body),'Bounded complete NPY header')
    try:header=ast.literal_eval(body[10:10+n].decode('ascii').strip())
    except (ValueError,SyntaxError,UnicodeError) as error:raise ArtifactError('Literal ASCII NPY header') from error
    require(header==dict(descr='<f8',fortran_order=False,shape=shape),'Exact dtype/shape/order, no object or pickle')
    require(len(body)==10+n+8*math.prod(shape),'Exact NPY body extent')
    return np.frombuffer(body,dtype='<f8',offset=10+n,count=math.prod(shape)).reshape(shape)


def _state_schema(metadata,cap):
    keys={'schema','family','person_id','run_ids','epoch_ids','lengths','channel_kinds','config','report','arrays'}
    require(type(metadata) is dict and set(metadata)==keys and metadata['schema']=='neural001_reference_state_v1','Exact bounded reference-state metadata')
    family=metadata['family'];config=metadata['config'];require(type(config) is list,'Plain config list')
    require(type(metadata['person_id']) is str and 0<len(metadata['person_id'])<=128,'Opaque participant string')
    runs=metadata['run_ids'];ids=metadata['epoch_ids'];lengths=metadata['lengths'];kinds=metadata['channel_kinds']
    require(type(runs) is list and len(runs) in (2,4) and all(type(x) is str and 0<len(x)<=128 for x in runs) and len(set(runs))==len(runs),'Complete unique run metadata')
    require(type(ids) is list and 0<len(ids)<=10000 and all(type(x) is str and 0<len(x)<=128 for x in ids) and len(set(ids))==len(ids),'Complete unique epoch metadata')
    require(type(lengths) is list and len(lengths)==len(ids) and all(type(n) is int and n>=4 for n in lengths) and sum(lengths)<=250000,'Exact admitted training support metadata')
    require(type(kinds) is list and len(kinds)==306 and kinds.count('mag')==102 and kinds.count('grad')==204,'Full sensor metadata')
    report=metadata['report'];require(type(report) is dict,'Plain training report')
    er=report.get('training_epoch_runs');require(type(er) is list and len(er)==len(ids) and all(type(x) is str for x in er) and set(er)==set(runs),'Complete epoch/run provenance')
    shapes={'target_mean':()}
    if family=='R0':
        require(config==[] and report.get('ridge_attempts')==0 and report.get('pca_attempts')==0,'Prior reference provenance')
    elif family=='R1':
        require(config in [[x] for x in (1e-6,1e-4,1e-2,1.,1e2,1e4,1e6)] and report.get('ridge_attempts')==7*len(runs)+1 and report.get('pca_attempts')==0,'Complete ridge reference provenance')
        shapes.update(target_scale=(),kind_mean=(2,),kind_scale=(2,),beta=(5203,))
    elif family=='R2':
        require(len(config)==3 and type(config[0]) is int and config[0] in (32,64) and config[1] in (.5,1.,2.) and config[2] in (.001,.1,10.,1000.) and report.get('ridge_attempts')==24*len(runs)+1 and report.get('pca_attempts')==2*len(runs)+1,'Complete nonlinear reference provenance')
        k=config[0];shapes.update(target_scale=(),channel_mean=(306,),channel_scale=(306,),pca_center=(306,),pca_vectors=(306,k),pca_scale=(k,),rff_g=(17*k,512),rff_phase=(512,),beta=(513,))
    else:raise ArtifactError('Unknown reference family')
    rows=metadata['arrays'];require(type(rows) is dict and set(rows)==set(shapes),'Exact reference array declarations')
    for name,shape in shapes.items():
        row=rows[name];require(type(row) is dict and set(row)=={'shape','dtype','bytes','sha256'} and row['shape']==list(shape) and row['dtype']=='<f8' and type(row['bytes']) is int and row['bytes']==8*math.prod(shape) and type(row['sha256']) is str and HEX64.fullmatch(row['sha256']),'Exact fixed-shape array declaration')
    return shapes
