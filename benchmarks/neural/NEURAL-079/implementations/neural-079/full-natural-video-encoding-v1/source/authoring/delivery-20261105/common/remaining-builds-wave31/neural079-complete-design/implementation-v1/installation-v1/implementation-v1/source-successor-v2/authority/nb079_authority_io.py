"""Concrete bounded authority IO. Import performs no effects or identity probes."""
import fcntl
import base64
import hashlib
import json
import os
import stat
import time
from pathlib import PurePosixPath
from nb079_launch_contract import canonical, pin, require, fields


def integer(value, minimum=0):
    require(type(value) is int and value >= minimum, 'exact finite integer required')
    return value


def check_pin(value):
    fields(value,('bytes','sha256'));integer(value['bytes'])
    require(type(value['sha256']) is str and len(value['sha256'])==64 and all(c in '0123456789abcdef' for c in value['sha256']),'exact SHA256')
    return value


def absolute(path):
    require(type(path) is str and path.startswith('/') and str(PurePosixPath(path))==path and '..' not in PurePosixPath(path).parts and '\x00' not in path,'canonical absolute path')
    return path


def relative(path):
    require(type(path) is str and path and not PurePosixPath(path).is_absolute() and str(PurePosixPath(path))==path and '..' not in PurePosixPath(path).parts and '\x00' not in path,'canonical relative path')
    return path


def descriptor(value):
    fields(value,('path','pin'));absolute(value['path']);check_pin(value['pin']);return value


def ident(fd):
    st=os.fstat(fd);return {'device':st.st_dev,'inode':st.st_ino}


def signature(st):return (st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns)


def secondary(first,error,stage):
    rows=list(getattr(first,'authority_secondary',[]));rows.append({'stage':stage,'type':type(error).__name__});first.authority_secondary=rows


def cleanup(operations,first=None):
    for stage,operation in operations:
        try:operation()
        except BaseException as error:
            if first is None:first=error
            else:secondary(first,error,stage)
    return first


def close_all(operations,first=None):
    result=cleanup(operations,first)
    if first is None and result is not None:raise result


class Clock:
    def __init__(self,selected):
        fields(selected,('origin','scientific','closeout','outer'))
        require(all(type(v) is int for v in selected.values()) and 0<=selected['origin']<selected['scientific']<selected['closeout']<selected['outer'],'original strictly ordered clock')
        self.selected=dict(selected)
    def tick(self,phase='scientific'):
        require(phase in ('scientific','closeout','outer'),'fixed original cutoff')
        now=time.monotonic_ns();require(self.selected['origin']<=now<self.selected[phase],'original cutoff, no reset');return now


class Counters:
    def __init__(self,limits,clock):
        fields(limits,('read_bytes','write_bytes','log_bytes','attempts','pending_bytes'))
        for value in limits.values():integer(value,1)
        self.limit=dict(limits);self.clock=clock;self.used={k:0 for k in limits};self.returned={'read_bytes':0,'write_bytes':0};self.records=[]
    def charge(self,values,why,phase='scientific'):
        require(type(values) is dict and set(values)<=set(self.used),'closed authority logical dimensions')
        values={k:integer(v) for k,v in values.items()};row={'delta':values,'reason':why,'status':'attempted'}
        # Full attempted counters survive limit/deadline refusal.
        self.used['attempts']+=1
        for key,value in values.items():self.used[key]+=value
        try:
            require(len(self.records)<self.limit['attempts'],'bounded attempted record retention');self.records.append(row)
            self.clock.tick(phase);require(all(self.used[k]<=self.limit[k] for k in self.used),'selected authority logical ceiling')
        except BaseException as error:row['status']='refused';error.authority_counter_prefix=self.snapshot();raise
        row['status']='reserved'
    def observed(self,direction,count):self.returned[direction]+=integer(count)
    def snapshot(self):return {'limits':self.limit,'attempted':dict(self.used),'positive_returns':dict(self.returned),'attempts':list(self.records),'physical_total_claim':False}


def bounded_encode(value,limits):
    """Conservative preventive bound before the shared canonical serializer."""
    fields(limits,('bytes','nodes','depth','string_chars'))
    for v in limits.values():integer(v,1)
    nodes=0;estimate=0
    def walk(item,depth):
        nonlocal nodes,estimate
        nodes+=1;require(nodes<=limits['nodes'] and depth<=limits['depth'],'bounded complete metadata tree')
        if type(item) is dict:
            estimate+=2+2*len(item)
            for k,v in item.items():require(type(k) is str,'string JSON keys');walk(k,depth+1);walk(v,depth+1)
        elif type(item) is list:
            estimate+=2+len(item)
            for v in item:walk(v,depth+1)
        elif type(item) is str:
            require(len(item)<=limits['string_chars'],'bounded metadata string');estimate+=2+6*len(item)
        elif type(item) in (int,bool) or item is None:
            estimate+=len(str(item))+2
        else:
            # No scientific floats or unknown objects enter issuance metadata.
            # Finite floats may exist inside original pinned configurations.
            import math
            require(type(item) is float and math.isfinite(item),'finite JSON scalar');estimate+=32
        require(estimate<=limits['bytes'],'preventive complete encoded metadata upper bound')
    walk(value,0);raw=canonical(value);require(len(raw)<=limits['bytes'],'complete shared canonical extent');return raw


def decode(raw,limits):
    require(type(raw) is bytes and len(raw)<=limits['bytes'],'bounded metadata body before decode')
    def pairs(items):
        out={}
        for k,v in items:require(k not in out,'duplicate JSON key');out[k]=v
        return out
    def reject(_):raise ValueError('nonfinite JSON constant')
    value=json.loads(raw,object_pairs_hook=pairs,parse_constant=reject)
    bounded_encode(value,limits);return value


def open_directory(path):
    absolute(path);fd=os.open('/',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW);first=None
    try:
        for name in PurePosixPath(path).parts[1:]:
            child=os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd);old,fd=fd,child
            try:os.close(old)
            except BaseException as error:close_all([('acquired directory',lambda:os.close(fd))],error);fd=None;raise
        result,fd=fd,None;return result
    except BaseException as error:first=error;raise
    finally:close_all([] if fd is None else [('traversal directory',lambda:os.close(fd))],first)


class Files:
    def __init__(self,counters,clock,limits):
        fields(limits,('file_bytes','block_bytes','directory_entries','path_chars','encoding'))
        for name in ('file_bytes','block_bytes','directory_entries','path_chars'):integer(limits[name],1)
        require(limits['block_bytes']<=limits['file_bytes'],'bounded actual IO chunk')
        self.counters,self.clock,self.limits=counters,clock,limits;self.encoding=limits['encoding'];self.reads=[];self.writes=[];self.publisher=None
    def read(self,item,phase='scientific',owner=None):
        descriptor(item);require(len(item['path'])<=self.limits['path_chars'],'bounded path before traversal');require(item['pin']['bytes']<=self.limits['file_bytes'],'complete selected file extent before open')
        self.counters.charge({'read_bytes':item['pin']['bytes']+1},'full pinned ordinary body and EOF',phase)
        parent=None;fd=None;first=None;raw=bytearray();record={'descriptor':item,'returned_bytes':0,'eof':False,'stable':False}
        require(len(self.reads)<self.counters.limit['attempts'],'preventive full read-record capacity');self.reads.append(record)
        try:
            parent=open_directory(str(PurePosixPath(item['path']).parent));fd=os.open(PurePosixPath(item['path']).name,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=parent)
            before=os.fstat(fd)
            require(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_size==item['pin']['bytes'],'ordinary single-link exact body')
            if owner is not None:require(before.st_uid==owner and before.st_mode&0o022==0,'independently selected protected file owner')
            while len(raw)<=before.st_size:
                self.clock.tick(phase);block=os.read(fd,min(self.limits['block_bytes'],before.st_size-len(raw)+1));self.counters.observed('read_bytes',len(block))
                if not block:record['eof']=True;break
                raw.extend(block);record['returned_bytes']=len(raw);require(len(raw)<=before.st_size,'file grew')
            require(signature(before)==signature(os.fstat(fd)) and record['eof'] and pin(bytes(raw))==item['pin'],'full stable pinned bytes and EOF')
            record.update(stable=True,identity=list(signature(before)),observed_ns=self.clock.tick(phase));return bytes(raw)
        except BaseException as error:
            record['failure_type']=type(error).__name__;error.authority_read_prefix=record;first=error;raise
        finally:close_all(([] if fd is None else [('ordinary body close',lambda:os.close(fd))])+([] if parent is None else [('ordinary parent close',lambda:os.close(parent))]),first)
    def unpinned(self,path,maximum,phase='scientific',owner=None):
        # Every absent discovery consumes the original finite attempt capacity
        # before retained metadata, traversal, stat or other namespace effects.
        absolute(path);require(len(path)<=self.limits['path_chars'],'bounded path before traversal');integer(maximum,1);require(maximum<=self.limits['file_bytes'],'bounded request maximum')
        self.counters.charge({},'bounded protected-file discovery attempt before namespace or retention',phase)
        require(len(self.reads)<self.counters.limit['attempts'],'preventive discovery record capacity')
        record={'path':path,'returned_bytes':0,'eof':False,'stable':False,'status':'attempted'};self.reads.append(record)
        parent=None;fd=None;first=None;raw=bytearray()
        try:
            parent=open_directory(str(PurePosixPath(path).parent))
            st=os.stat(PurePosixPath(path).name,dir_fd=parent,follow_symlinks=False)
            require(stat.S_ISREG(st.st_mode) and st.st_nlink==1 and st.st_size<=maximum,'complete bounded protected request')
            if owner is not None:require(st.st_uid==owner and st.st_mode&0o022==0,'selected request owner')
            self.counters.charge({'read_bytes':st.st_size+1},'full newly published protected request plus EOF',phase)
            fd=os.open(PurePosixPath(path).name,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=parent)
            require(signature(os.fstat(fd))==signature(st),'same enumerated request')
            while len(raw)<=st.st_size:
                self.clock.tick(phase);block=os.read(fd,min(self.limits['block_bytes'],st.st_size-len(raw)+1));self.counters.observed('read_bytes',len(block))
                if not block:record['eof']=True;break
                raw.extend(block);record['returned_bytes']=len(raw);require(len(raw)<=st.st_size,'request grew')
            require(record['eof'] and len(raw)==st.st_size and signature(os.fstat(fd))==signature(st),'whole stable new request and EOF')
            body=bytes(raw);item={'path':path,'pin':pin(body)}
            record.update(descriptor=item,returned_bytes=len(body),stable=True,status='complete',raw_base64=base64.b64encode(body).decode('ascii'),observed_ns=self.clock.tick(phase))
            return item,body
        except BaseException as error:
            record.update(status='absent' if isinstance(error,FileNotFoundError) else 'failed_or_unknown',failure_type=type(error).__name__,raw_prefix_base64=base64.b64encode(raw).decode('ascii'))
            error.authority_read_prefix=dict(record);first=error;raise
        finally:close_all(([] if fd is None else [('new protected request close',lambda:os.close(fd))])+([] if parent is None else [('new request parent close',lambda:os.close(parent))]),first)
    def bind_publication(self,selected):
        require(self.publisher is None,'one earlier source-admitted publication ABI')
        bounds={'maximum_source_bytes':self.limits['file_bytes'],'maximum_publication_bytes':self.limits['file_bytes'],
            'block_bytes':self.limits['block_bytes'],'maximum_publications':self.counters.limit['attempts'],
            'maximum_total_write_bytes':self.counters.limit['write_bytes'],'maximum_path_chars':self.limits['path_chars']}
        amount=selected['implementation']['pin']['bytes']+selected['libc']['pin']['bytes']+2
        require(amount-2<=bounds['maximum_source_bytes'],'whole selected publication implementation/native source extent')
        require(selected['implementation']['pin']=={'bytes':13012,'sha256':'d5126bddafeea934422c92b838553138a7db925b62b51dcb022b6774fd2c8d04'},'only exact sealed standalone publisher source')
        # Capture before executing the one fixed inert implementation under a
        # private name. Its physical path may be the parent's admitted same-body copy.
        import types,sys
        source=self.read(selected['implementation'])
        module=types.ModuleType('nb079_atomic_publication_authority');module.__file__=selected['implementation']['path']
        exec(compile(source,module.__file__,'exec'),module.__dict__)
        sys.modules[module.__name__]=module;AtomicPublication=module.AtomicPublication
        self.counters.charge({'read_bytes':amount},'whole selected atomic implementation/libc sources plus both EOF probes')
        try:self.publisher=AtomicPublication(selected,self.clock.selected,bounds,execution_enabled=True)
        except BaseException as error:
            self.counters.observed('read_bytes',getattr(error,'atomic_prefix',{}).get('returned_source_bytes',0));raise
        self.counters.observed('read_bytes',self.publisher.returned_source_bytes)
    def write(self,root,name,value,phase='scientific',log=False):
        require(self.publisher is not None,'actual earlier admitted atomic publisher before metadata effect')
        raw=bounded_encode(value,self.encoding);require(len(raw)<=self.limits['file_bytes'],'whole artifact before publication')
        delta={'write_bytes':len(raw)}
        if log:delta['log_bytes']=len(raw)
        self.counters.charge(delta,'whole atomic metadata artifact before publication',phase)
        before=self.publisher.returned_write_bytes
        try:
            result=self.publisher.publish(root,name,raw,phase);self.writes.append(result['record']);return result['descriptor']
        except BaseException as error:
            self.writes.append({'status':'failed_or_unknown','atomic_prefix':getattr(error,'atomic_prefix',self.publisher.prefix())});raise
        finally:self.counters.observed('write_bytes',self.publisher.returned_write_bytes-before)
    def directory(self,root,phase='scientific'):
        fields(root,('path','identity','owner_uid','mode'));absolute(root['path']);integer(root['owner_uid']);integer(root['mode'])
        fields(root['identity'],('device','inode'))
        for value in root['identity'].values():integer(value)
        self.counters.charge({},'bounded protected directory validation before namespace effect',phase)
        fd=open_directory(root['path']);first=None
        try:
            st=os.fstat(fd);require(ident(fd)==root['identity'] and st.st_uid==root['owner_uid'] and stat.S_IMODE(st.st_mode)==root['mode'] and root['mode']&0o022==0,'exact admitted protected directory')
            return {'path':root['path'],'identity':ident(fd),'owner_uid':st.st_uid,'mode':stat.S_IMODE(st.st_mode)}
        except BaseException as error:first=error;raise
        finally:close_all([('protected directory validation',lambda:os.close(fd))],first)


def fifo_metadata(fd,expected,clock,access):
    require(type(access) is int and access in (os.O_RDONLY,os.O_WRONLY),'exact integer OS read/write access mode, no bool')
    fields(expected,('path','identity','owner_uid','mode'));st=os.fstat(fd);flags=fcntl.fcntl(fd,fcntl.F_GETFL)
    require(stat.S_ISFIFO(st.st_mode) and {'device':st.st_dev,'inode':st.st_ino}==expected['identity'] and st.st_uid==expected['owner_uid'] and
        stat.S_IMODE(st.st_mode)==expected['mode'] and expected['mode']&0o022==0 and flags&os.O_ACCMODE==access and bool(flags&os.O_NONBLOCK),'actual selected nonblocking FIFO descriptor')
    return {'fd':fd,'device':st.st_dev,'inode':st.st_ino,'owner_uid':st.st_uid,'mode':stat.S_IMODE(st.st_mode),
        'access_mode':access,'nonblocking':True,'observed_ns':clock.tick()}
