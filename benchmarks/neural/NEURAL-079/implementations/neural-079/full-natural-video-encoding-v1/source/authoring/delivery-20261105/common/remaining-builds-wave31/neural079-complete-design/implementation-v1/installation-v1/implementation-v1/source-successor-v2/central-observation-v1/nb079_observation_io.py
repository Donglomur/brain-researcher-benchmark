"""Concrete bounded ordinary read/write, original-clock ledger and Linux identity."""
import hashlib
import os
import stat
from pathlib import PurePosixPath
from nb079_observation_common import (require, fields, integer, check_pin, body_pin,
    bounded_encode, bounded_decode, collect_errors, close_all, read_fd)

DIMENSIONS=('source_read_bytes','data_read_bytes','write_bytes','log_bytes','process_starts','validation_calls','logical_float_slots')

def absolute(path):
    require(type(path) is str and path.startswith('/') and str(PurePosixPath(path))==path and
            '..' not in PurePosixPath(path).parts and '\x00' not in path,'canonical absolute path')
    return path


def descriptor(value):
    fields(value,('path','pin'),'selected ordinary descriptor');absolute(value['path']);check_pin(value['pin']);return value


def artifact(value):
    fields(value,('path','bytes','sha256'),'ordinary artifact descriptor');check_pin({k:value[k] for k in ('bytes','sha256')});return value


def signature(st):return (st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns)


def open_directory(path):
    absolute(path);fd=os.open('/',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW);first=None
    try:
        for name in PurePosixPath(path).parts[1:]:
            child=os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd)
            previous,fd=fd,child
            try:os.close(previous)
            except BaseException as error:
                held,fd=fd,None;close_all([('new directory after failed prior close',lambda:os.close(held))],error);raise
        result,fd=fd,None;return result
    except BaseException as error:first=error;raise
    finally:close_all([] if fd is None else [('directory traversal',lambda:os.close(fd))],first)


def root_shape(root):
    fields(root,('path','identity','owner_uid','mode'),'prepared root');absolute(root['path'])
    fields(root['identity'],('device','inode'),'directory identity')
    integer(root['identity']['device']);integer(root['identity']['inode'],1);integer(root['owner_uid']);integer(root['mode'])
    require(root['mode']&0o022==0,'protected root cannot be group/world writable')


def verify_root(fd,root):
    root_shape(root);st=os.fstat(fd)
    require(stat.S_ISDIR(st.st_mode) and {'device':st.st_dev,'inode':st.st_ino}==root['identity'] and
            st.st_uid==root['owner_uid'] and stat.S_IMODE(st.st_mode)==root['mode'],'actual prepared protected root')


class OrchestrationLedger:
    def __init__(self,limits,clock,maximum_attempts):
        fields(limits,DIMENSIONS,'exact central orchestration limits')
        self.limits={k:integer(v) for k,v in limits.items()};self.clock=clock
        self.maximum_attempts=integer(maximum_attempts,1);self.attempts=[]
        self.counts={k:0 for k in DIMENSIONS};self.positive={}
    def charge(self,delta,reason,phase='scientific'):
        require(type(delta) is dict and set(delta)<=set(DIMENSIONS),'existing logical dimension subset')
        row={'delta':{k:integer(v) for k,v in delta.items()},'reason':reason,'status':'attempted'}
        require(len(self.attempts)<self.maximum_attempts,'bounded central attempt roster');self.attempts.append(row)
        for k,v in row['delta'].items():self.counts[k]+=v
        try:
            self.clock.tick(phase);require(all(self.counts[k]<=self.limits[k] for k in DIMENSIONS),'central selected logical allocation exhausted')
        except BaseException:
            row['status']='refused';raise
        row['status']='charged'
    def returned(self,name,count):self.positive[name]=self.positive.get(name,0)+integer(count)
    def snapshot(self):
        return {'limits':dict(self.limits),'attempted':dict(self.counts),'positive_returns':dict(self.positive),
            'attempts':list(self.attempts),'physical_total_claim':False}


class ProtectedIO:
    def __init__(self,clock,ledger,limits,encoding,owner_uid):
        self.clock,self.ledger,self.limits,self.encoding,self.owner_uid=clock,ledger,limits,encoding,owner_uid
        self.observations=[]
    def _open(self,path):
        absolute(path);parent=open_directory(str(PurePosixPath(path).parent));fd=None;first=None
        try:fd=os.open(PurePosixPath(path).name,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=parent)
        except BaseException as error:first=error
        first=collect_errors([('ordinary parent',lambda:os.close(parent))],first)
        if first is not None:
            close_all([] if fd is None else [('ordinary file after acquisition/parent failure',lambda:os.close(fd))],first)
            raise first
        return fd
    def capture(self,item,phase='scientific',kind='source',keep=True,maximum=None,owner_uid=None):
        descriptor(item);maximum=self.limits['metadata_bytes'] if maximum is None else integer(maximum)
        require(item['pin']['bytes']<=maximum,'complete selected file extent before open')
        if keep:require(4*item['pin']['bytes']<=self.limits['live_buffer_bytes'],'complete JSON/capture live payload bound before read')
        require(len(self.observations)<self.limits['maximum_files'],'finite complete capture roster before read')
        expected_owner=self.owner_uid if owner_uid is None else integer(owner_uid)
        dimension='source_read_bytes' if kind=='source' else 'data_read_bytes'
        self.ledger.charge({dimension:item['pin']['bytes']+1},'complete selected '+kind+' capture before read',phase)
        started=self.clock.tick(phase);fd=self._open(item['path']);first=None;h=hashlib.sha256();size=0;pieces=[]
        try:
            before=os.fstat(fd)
            require(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_uid==expected_owner and
                not(stat.S_IMODE(before.st_mode)&0o022) and before.st_size==item['pin']['bytes'],'ordinary immutable source-owned complete file')
            while True:
                self.clock.tick(phase);block=os.read(fd,min(self.limits['block_bytes'],item['pin']['bytes']-size+1))
                self.ledger.returned(dimension,len(block))
                if not block:break
                size+=len(block);h.update(block);require(size<=item['pin']['bytes'],'readback grew beyond selected extent')
                if keep:pieces.append(block)
            require(size==item['pin']['bytes'] and h.hexdigest()==item['pin']['sha256'] and signature(before)==signature(os.fstat(fd)),
                'complete stable independently hashed source/output')
            self.observations.append({'descriptor':item,'kind':kind,'started_ns':started,'finished_ns':self.clock.tick(phase),'bytes':size})
            require(len(self.observations)<=self.limits['maximum_files'],'finite selected complete readback roster')
            return b''.join(pieces) if keep else {'path':item['path'],**item['pin']}
        except BaseException as error:
            first=error;error.nb079_read_prefix={'descriptor':item,'bytes':size,'partial_sha256':h.hexdigest(),'kind':kind};raise
        finally:close_all([('ordinary capture fd',lambda:os.close(fd))],first)
    def json(self,item,phase='scientific',owner_uid=None):
        return bounded_decode(self.capture(item,phase,owner_uid=owner_uid),self.encoding)
    def write(self,root_fd,name,raw,phase='outer',log=False):
        require(type(raw) is bytes and '/' not in name and name not in ('','.','..'),'one exact owned publication leaf')
        require(len(raw)<=self.limits['publication_bytes'],'complete output bound before file creation')
        delta={'write_bytes':len(raw)}
        if log:delta['log_bytes']=len(raw)
        self.ledger.charge(delta,'complete bounded central publication before write',phase)
        fd=None;first=None;done=0;h=hashlib.sha256()
        try:
            fd=os.open(name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o400,dir_fd=root_fd)
            while done<len(raw):
                self.clock.tick(phase);n=os.write(fd,memoryview(raw)[done:]);require(type(n) is int and 0<n<=len(raw)-done,'positive complete publication write')
                h.update(memoryview(raw)[done:done+n]);done+=n;self.ledger.returned('write_bytes',n)
            os.fsync(fd);os.fsync(root_fd);self.clock.tick(phase)
            return {'path':name,**body_pin(raw)}
        except BaseException as error:
            first=error;error.nb079_publication_prefix={'path':name,'bytes':done,'sha256':h.hexdigest(),'durable':False};raise
        finally:close_all([] if fd is None else [('publication descriptor',lambda:os.close(fd))],first)


class LinuxIdentity:
    def __init__(self,clock,ledger,maximum):self.clock,self.ledger,self.maximum=clock,ledger,integer(maximum,1)
    def proc(self,path,phase):
        self.ledger.charge({'source_read_bytes':self.maximum+1},'bounded actual Linux identity read before effect',phase)
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW);first=None
        try:
            raw=read_fd(fd,self.maximum,self.clock,phase);self.ledger.returned('source_read_bytes',len(raw));return raw
        except BaseException as error:first=error;raise
        finally:close_all([('Linux identity descriptor',lambda:os.close(fd))],first)
    def observe(self,pid,phase='scientific'):
        integer(pid,1);self.clock.tick(phase)
        raw=self.proc('/proc/%d/stat'%pid,phase);tail=raw[raw.rfind(b')')+2:].split()
        require(len(tail)>=20 and tail[19].isdigit(),'actual proc start ticks');start=int(tail[19])
        rows=dict(line.split(':',1) for line in self.proc('/proc/%d/status'%pid,phase).decode('ascii').splitlines() if ':' in line)
        uid=[int(x) for x in rows['Uid'].split()];gid=[int(x) for x in rows['Gid'].split()]
        require(len(uid)==len(gid)==4,'actual process credential quadruples')
        exe=os.stat('/proc/%d/exe'%pid);namespaces={}
        for name in ('mnt','pid','user','net','ipc','uts','cgroup'):
            st=os.stat('/proc/%d/ns/%s'%(pid,name));namespaces[name]=[st.st_dev,st.st_ino]
        result={'pid':pid,'uid':uid[1],'gid':gid[1],'start_ticks':start,
            'boot_id':self.proc('/proc/sys/kernel/random/boot_id',phase).decode('ascii').strip(),
            'executable':{'device':exe.st_dev,'inode':exe.st_ino},'namespaces':namespaces,
            'cgroup':self.proc('/proc/%d/cgroup'%pid,phase).decode('ascii')}
        again=self.proc('/proc/%d/stat'%pid,phase)
        require(int(again[again.rfind(b')')+2:].split()[19])==start,'same original PID/start throughout identity')
        return result
    def argv_environment(self,pid,argv,environment,phase='scientific'):
        actual=self.proc('/proc/%d/cmdline'%pid,phase)
        require(actual==b'\x00'.join(x.encode() for x in argv)+b'\x00','literal actual original OS argv')
        raw=self.proc('/proc/%d/environ'%pid,phase)
        parts=raw.split(b'\x00');require(parts[-1:]==[b''],'complete actual environment delimiters')
        entries=[p.split(b'=',1) for p in parts[:-1]]
        require(all(len(p)==2 for p in entries) and len(entries)==len({p[0] for p in entries}),'exact unique environment names')
        require({k.decode():v.decode() for k,v in entries}==environment,'actual exact admitted clean environment')
        return {'argv_pin':body_pin(actual),'environment_observed_equal':True}


def read_terminal(io,item,schema,owner_uid,phase='outer'):
    """Hash a full stream and parse its sole last typed frame with bounded lines."""
    descriptor(item);require(item['pin']['bytes']<=io.limits['stream_bytes'],'selected full stream before read')
    require(4*(io.limits['block_bytes']+io.limits['metadata_bytes'])<=io.limits['live_buffer_bytes'],
            'stream block plus whole terminal frame before allocation')
    io.ledger.charge({'data_read_bytes':item['pin']['bytes']+1},'complete stream terminal audit before read',phase)
    fd=io._open(item['path']);first=None;total=0;h=hashlib.sha256();line=bytearray();line_number=0;found=[]
    try:
        before=os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_uid==owner_uid and
                not(stat.S_IMODE(before.st_mode)&0o022) and before.st_size==item['pin']['bytes'],'actual ordinary exact full stream')
        while True:
            io.clock.tick(phase);raw=os.read(fd,min(io.limits['block_bytes'],item['pin']['bytes']-total+1))
            io.ledger.returned('data_read_bytes',len(raw))
            if not raw:break
            total+=len(raw);h.update(raw);require(total<=item['pin']['bytes'],'stream extent stable')
            for byte in raw:
                require(len(line)<io.limits['metadata_bytes'],'every stdout line within selected whole-frame cap')
                line.append(byte)
                if byte==10:
                    try:value=bounded_decode(bytes(line[:-1]),io.encoding)
                    except (ValueError,UnicodeError):value=None
                    if type(value) is dict and value.get('schema')==schema:
                        found.append((line_number,value));require(len(found)<=1,'no duplicate source terminal')
                    line_number+=1;line.clear()
        require(total==item['pin']['bytes'] and h.hexdigest()==item['pin']['sha256'] and signature(before)==signature(os.fstat(fd)),
                'full stable observed terminal stream hash')
        require(not line and len(found)==1 and found[0][0]==line_number-1,'one exact final complete newline-delimited terminal')
        return found[0][1]
    except BaseException as error:first=error;error.nb079_terminal_prefix={'bytes':total,'sha256':h.hexdigest(),'complete_lines':line_number};raise
    finally:close_all([('terminal stream descriptor',lambda:os.close(fd))],first)
