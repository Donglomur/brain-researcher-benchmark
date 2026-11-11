"""Own a complete future 727-file prepared-signal snapshot; no qualification.

All paths are walked through no-follow directory descriptors. Byte consistency,
read-only copies and original owner custody are checked; these observations do
not establish authentic source origin, source-to-prepared sample correspondence
or native isolation. No receipt loader creates a completed owner.
"""
import hashlib, math, os, stat, time
from pathlib import PurePosixPath
import io_contract as io
import source_evidence as evidence

IDENTITY = ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns')
DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NONBLOCK
READ_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
WRITE_FLAGS = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_NONBLOCK

def identity(value): return tuple(getattr(value,k) for k in IDENTITY)
def directory_identity(value): return value.st_dev,value.st_ino
def digest(raw): return hashlib.sha256(raw).hexdigest()
def cloned(value): return io.strict(io.encoded(value))
def absolute(value):
    io.need(type(value) is str and value.startswith('/') and value != '/' and str(PurePosixPath(value)) == value
            and all(x not in ('.','..') for x in PurePosixPath(value).parts)
            and not any(x in value for x in ('\0','\n','\r','\\')), 'canonical absolute snapshot root')
    return value
def limits(value):
    io.fields(value, ['files','file_bytes','read_bytes','write_bytes','wall_seconds','chunk_bytes'])
    io.need(all(type(value[k]) is int and value[k] > 0 for k in ('files','file_bytes','read_bytes','write_bytes','chunk_bytes')),
            'explicit positive full snapshot limits')
    io.need(value['chunk_bytes'] <= 1048576 and type(value['wall_seconds']) in (int,float)
            and math.isfinite(value['wall_seconds']) and value['wall_seconds'] > 0, 'bounded chunk and finite original deadline')
    return value

class Errors:
    def __init__(self): self.first_error=None; self.secondary_errors=[]
    def retain(self,error):
        if self.first_error is None: self.first_error=error
        elif error is not self.first_error: self.secondary_errors.append(error)
    def raise_error(self):
        if self.first_error is not None: raise self.first_error

class SnapshotBudget:
    def __init__(self,value):
        self.started_ns=time.monotonic_ns(); self.limits=limits(cloned(value))
        self.deadline_ns=self.started_ns+int(self.limits['wall_seconds']*1000000000)
        self.read_bytes=0; self.write_bytes=0; self.read_requests=0; self.write_requests=0; self.files_started=0
    def check(self): io.need(time.monotonic_ns() <= self.deadline_ns, 'same original full snapshot deadline')
    def begin_file(self):
        self.check(); self.files_started+=1
        io.need(self.files_started <= self.limits['files'], 'complete snapshot file-count limit')
    def reserve_read(self,n):
        self.check(); io.need(type(n) is int and n > 0 and self.read_bytes+n <= self.limits['read_bytes'], 'original cumulative read limit before effect')
        self.read_bytes+=n; self.read_requests+=n
    def finish_read(self,n,returned,witness):
        io.need(type(returned) is bytes and len(returned) <= n, 'bounded actual read return')
        if not witness: self.read_bytes-=n-len(returned)
        self.check()
    def reserve_write(self,n):
        self.check(); io.need(type(n) is int and n > 0 and self.write_bytes+n <= self.limits['write_bytes'], 'original cumulative write limit before effect')
        self.write_bytes+=n; self.write_requests+=n
    def finish_write(self,n,returned):
        io.need(type(returned) is int and 0 < returned <= n, 'progressing original write return')
        self.write_bytes-=n-returned; self.check()

class Descriptor(Errors):
    """One acquired descriptor occurrence, owned before open and never blindly retried."""
    def __init__(self,kind):
        super().__init__(); self.kind=kind; self.fd=None; self.opened_descriptor=None
        self.open_attempted=False; self.close_attempted=False; self.close_completed=False
    def open(self,name,flags,mode=0o600,dir_fd=None):
        io.need(not self.open_attempted, 'one original descriptor open'); self.open_attempted=True
        try:
            self.fd=os.open(name,flags,mode,dir_fd=dir_fd); self.opened_descriptor=self.fd
        except BaseException as error: self.retain(error); raise
        return self.fd
    def close(self):
        if self.fd is None or self.close_attempted: return
        self.close_attempted=True
        try: os.close(self.fd); self.close_completed=True; self.fd=None
        except BaseException as error: self.retain(error); raise

class DirectoryChain(Errors):
    """Retain every no-follow prefix descriptor until the caller checks connection."""
    def __init__(self,owner,path):
        super().__init__(); self.owner=owner; self.path=absolute(path); self.entries=[]; self.started=False; self.closed=False
    @property
    def fd(self):
        io.need(self.entries and self.entries[-1][1].fd is not None, 'live original directory chain')
        return self.entries[-1][1].fd
    def open(self):
        io.need(not self.started, 'one original directory walk'); self.started=True
        try:
            for name in ('/',*PurePosixPath(self.path).parts[1:]):
                self.owner.budget.check(); descriptor=Descriptor('directory:'+name)
                parent=None if not self.entries else self.entries[-1][1].fd
                self.entries.append((name,descriptor,None)); fd=descriptor.open(name,DIR_FLAGS,dir_fd=parent)
                observed=os.fstat(fd); io.need(stat.S_ISDIR(observed.st_mode), 'ordinary directory prefix')
                self.entries[-1]=(name,descriptor,directory_identity(observed))
            self.connected(); return self
        except BaseException as error: self.retain(error); raise
    def connected(self):
        self.owner.budget.check()
        for i,(name,descriptor,pin) in enumerate(self.entries):
            io.need(descriptor.fd is not None and pin is not None, 'complete original directory acquisition')
            actual=os.fstat(descriptor.fd)
            entry=os.stat(name,dir_fd=None if i==0 else self.entries[i-1][1].fd,follow_symlinks=False)
            io.need(stat.S_ISDIR(actual.st_mode) and stat.S_ISDIR(entry.st_mode)
                    and directory_identity(actual)==directory_identity(entry)==pin, 'same original connected no-follow directory prefix')
        return self
    def close(self):
        for _,descriptor,_ in reversed(self.entries):
            try: descriptor.close()
            except BaseException as error: self.retain(error)
        self.closed=all(d.fd is None and d.close_completed for _,d,_ in self.entries)
        self.raise_error()

class FileSnapshotOwner(Errors):
    """Original source, copy and readback descriptors retained before all effects."""
    def __init__(self,collection,row):
        super().__init__(); self.collection=collection; self.row=cloned(row); self.row_raw=io.encoded(self.row)
        self.source=Descriptor('prepared-source'); self.output=Descriptor('new-snapshot'); self.readback=Descriptor('snapshot-readback')
        self.started=False; self.complete=False; self.before=None; self.after=None; self.snapshot_identity=None
        self.created_identity=None; self.copied_bytes=0; self.readback_bytes=0; self.source_sha256=None; self.readback_sha256=None
        self.active_call=None; self.last_call=None; self.read_calls=0; self.write_calls=0
    def read(self,descriptor,n,phase,witness=False):
        budget=self.collection.budget; self.active_call={'phase':phase,'operation':'read','requested':n,'returned':None,'witness':witness}
        budget.reserve_read(n)
        try:
            raw=os.read(descriptor.fd,n); self.active_call['returned']=len(raw)
            budget.finish_read(n,raw,witness); self.read_calls+=1
            self.last_call=self.active_call; self.active_call=None; return raw
        except BaseException as error: self.active_call['error']=error; raise
    def write(self,raw):
        offset=0; budget=self.collection.budget
        while offset<len(raw):
            count=len(raw)-offset; self.active_call={'phase':'copy','operation':'write','requested':count,'returned':None}
            budget.reserve_write(count)
            try:
                written=os.write(self.output.fd,raw[offset:]); self.active_call['returned']=written
                budget.finish_write(count,written); self.write_calls+=1; offset+=written; self.copied_bytes+=written
                self.last_call=self.active_call; self.active_call=None
            except BaseException as error: self.active_call['error']=error; raise
    def require_file(self,fd,expected_size):
        s=os.fstat(fd)
        io.need(stat.S_ISREG(s.st_mode) and s.st_nlink==1 and s.st_size==expected_size, 'exact ordinary single-link file extent')
        return s
    def run(self,source_directory,destination_directory):
        io.need(not self.started,'one original file-copy occurrence'); self.started=True
        c=self.collection; budget=c.budget; row=self.row; filename=row['file'].split('/')[1]
        try:
            budget.begin_file(); source_directory.connected()
            self.source.open(filename,READ_FLAGS,dir_fd=source_directory.fd); self.before=self.require_file(self.source.fd,row['bytes'])
            c.admit_source_inode(self.before,row['recording_id'])
            self.output.open(filename,WRITE_FLAGS,dir_fd=destination_directory)
            initial=self.require_file(self.output.fd,0); self.created_identity=directory_identity(initial)
            hasher=hashlib.sha256(); total=0
            while total<row['bytes']:
                raw=self.read(self.source,min(budget.limits['chunk_bytes'],row['bytes']-total),'source')
                io.need(raw,'no early original EOF'); total+=len(raw); hasher.update(raw); self.write(raw)
            io.need(self.read(self.source,1,'source',True)==b'','original source EOF witness')
            self.after=self.require_file(self.source.fd,row['bytes']); source_directory.connected()
            self.source_sha256=hasher.hexdigest()
            io.need(identity(self.before)==identity(self.after) and self.source_sha256==row['sha256'] and self.copied_bytes==row['bytes'], 'same complete source snapshot bytes')
            current=self.require_file(self.output.fd,row['bytes']); io.need(directory_identity(current)==self.created_identity,'same exclusively created output')
            os.fchmod(self.output.fd,0o444)
            self.output.close(); self.source.close(); budget.check()
            self.readback.open(filename,READ_FLAGS,dir_fd=destination_directory)
            start=self.require_file(self.readback.fd,row['bytes'])
            io.need(directory_identity(start)==self.created_identity and stat.S_IMODE(start.st_mode)==0o444,'same read-only original output inode')
            hasher=hashlib.sha256()
            while self.readback_bytes<row['bytes']:
                raw=self.read(self.readback,min(budget.limits['chunk_bytes'],row['bytes']-self.readback_bytes),'readback')
                io.need(raw,'no early snapshot EOF'); self.readback_bytes+=len(raw); hasher.update(raw)
            io.need(self.read(self.readback,1,'readback',True)==b'','snapshot EOF witness')
            end=self.require_file(self.readback.fd,row['bytes']); self.readback_sha256=hasher.hexdigest()
            io.need(identity(start)==identity(end) and self.readback_sha256==row['sha256'],'complete unchanged snapshot readback')
            linked=os.stat(filename,dir_fd=destination_directory,follow_symlinks=False)
            io.need(identity(linked)==identity(end) and stat.S_ISREG(linked.st_mode) and linked.st_nlink==1,'output pathname remains same original inode')
            self.snapshot_identity=identity(end)
        except BaseException as error:self.retain(error)
        finally:
            for descriptor in (self.readback,self.output,self.source):
                try: descriptor.close()
                except BaseException as error:self.retain(error)
        if self.first_error is None:
            try:
                budget.check(); io.need(all(x.close_completed and x.fd is None for x in(self.source,self.output,self.readback)),'all original file closes succeeded')
                self.complete=True
            except BaseException as error:self.retain(error)
        self.raise_error(); return self

class SignalSnapshotOwner(Errors):
    def __init__(self,selection_raw,prepared_roots,destination,selected_limits):
        super().__init__(); self.budget=SnapshotBudget(selected_limits)
        io.need(type(selection_raw)is bytes,'original source evidence selection bytes')
        self.selection_raw=selection_raw; self.selection=evidence.validate_selection(io.strict(selection_raw)); self.selection_canonical=io.encoded(self.selection)
        io.need(selection_raw==self.selection_canonical,'canonical original snapshot evidence selection')
        io.fields(prepared_roots,('CHB','Siena')); self.prepared_roots={k:absolute(v)for k,v in prepared_roots.items()}
        self.roots_raw=io.encoded(self.prepared_roots); self.destination=absolute(destination); self.destination_raw=self.destination
        for root in self.prepared_roots.values():
            io.need(self.destination!=root and not self.destination.startswith(root+'/') and not root.startswith(self.destination+'/'),'disjoint original prepared and fresh output roots')
        self.limits_raw=io.encoded(self.budget.limits)
        records={r['recording_id']:r for r in self.selection['records']}; assets={a['asset_id']:a for a in self.selection['assets']}; self.rows=[]
        for row in self.selection['panel']['records']:
            rid=row['recording_id']; a=assets[records[rid]['prepared_asset']]; signal=row['signal']
            io.need(a['path']==signal['file']=='signals/'+rid+'.h5' and a['bytes']==signal['bytes'] and a['sha256']==signal['sha256'],'exact planned prepared signal inverse')
            self.rows.append({'recording_id':rid,'cohort':row['cohort'],'file':signal['file'],'bytes':signal['bytes'],'sha256':signal['sha256']})
        io.need(len(self.rows)==727 and len({r['recording_id']for r in self.rows})==727 and
                sum(r['cohort']=='CHB'for r in self.rows)==686 and sum(r['cohort']=='Siena'for r in self.rows)==41,'complete original727 snapshot roster')
        self.rows_raw=io.encoded(self.rows); self.total_bytes=sum(r['bytes']for r in self.rows); self.planned_read_bytes=2*(self.total_bytes+len(self.rows))
        lim=self.budget.limits
        io.need(len(self.rows)<=lim['files'] and all(0<r['bytes']<=lim['file_bytes']for r in self.rows)
                and self.planned_read_bytes<=lim['read_bytes'] and self.total_bytes<=lim['write_bytes'],'whole source/copy/readback/EOF demands admitted before effects')
        self.original_owner=self; self.started=False; self.complete=False; self.file_owners=[]; self.directory_owners=[]; self.created_directories=[]
        self.destination_descriptor=Descriptor('fresh-root'); self.signals_descriptor=Descriptor('fresh-signals')
        self.destination_identity=None; self.signals_identity=None; self.source_inodes={}; self.verification_owners=[]
        self.budget.check()
    def selection_intact(self,selection_raw=None):
        self.budget.check()
        io.need(selection_raw is None or selection_raw==self.selection_raw,'same original source selection for unified root')
        io.need(io.encoded(self.selection)==self.selection_canonical==self.selection_raw and io.encoded(self.rows)==self.rows_raw
                and io.encoded(self.prepared_roots)==self.roots_raw and self.destination==self.destination_raw
                and io.encoded(self.budget.limits)==self.limits_raw,'unchanged original snapshot plan/roots/limits')
    def chain(self,path,verification=False):
        item=DirectoryChain(self,path)
        (self.verification_owners if verification else self.directory_owners).append(item)
        return item.open()
    def admit_source_inode(self,value,rid):
        key=directory_identity(value)
        io.need(key not in self.source_inodes,'no repeated original prepared inode or hardlink shortcut')
        self.source_inodes[key]=rid
    def connected_destination(self,parent):
        parent.connected(); name=PurePosixPath(self.destination).name
        actual=os.stat(name,dir_fd=parent.fd,follow_symlinks=False); opened=os.fstat(self.destination_descriptor.fd)
        io.need(stat.S_ISDIR(actual.st_mode)and directory_identity(actual)==directory_identity(opened)==self.destination_identity,'same original fresh root at selected absolute path')
        actual=os.stat('signals',dir_fd=self.destination_descriptor.fd,follow_symlinks=False);opened=os.fstat(self.signals_descriptor.fd)
        io.need(stat.S_ISDIR(actual.st_mode)and directory_identity(actual)==directory_identity(opened)==self.signals_identity,'same original signals directory')
    def run(self):
        io.need(not self.started,'one original whole snapshot'); self.started=True
        try:
            self.selection_intact(); source={c:self.chain(p+'/signals')for c,p in self.prepared_roots.items()}
            target=PurePosixPath(self.destination); parent_path=str(target.parent)
            io.need(parent_path!='/','selected private output parent below filesystem root')
            parent=self.chain(parent_path); parent.connected()
            # mkdir is exclusive. No pre-existing destination is adopted.
            self.created_directories.append({'parent':parent,'name':target.name,'attempted':True,'created':False})
            os.mkdir(target.name,0o700,dir_fd=parent.fd); self.created_directories[-1]['created']=True
            self.destination_descriptor.open(target.name,DIR_FLAGS,dir_fd=parent.fd); root=os.fstat(self.destination_descriptor.fd)
            io.need(stat.S_ISDIR(root.st_mode),'new snapshot root is ordinary directory');self.destination_identity=directory_identity(root)
            self.created_directories.append({'parent':self.destination_descriptor,'name':'signals','attempted':True,'created':False})
            os.mkdir('signals',0o700,dir_fd=self.destination_descriptor.fd);self.created_directories[-1]['created']=True
            self.signals_descriptor.open('signals',DIR_FLAGS,dir_fd=self.destination_descriptor.fd);s=os.fstat(self.signals_descriptor.fd)
            io.need(stat.S_ISDIR(s.st_mode),'new signal root is ordinary directory');self.signals_identity=directory_identity(s)
            for row in self.rows:
                self.selection_intact(); self.connected_destination(parent)
                file_owner=FileSnapshotOwner(self,row); self.file_owners.append(file_owner)
                result=file_owner.run(source[row['cohort']],self.signals_descriptor.fd)
                io.need(result is file_owner and file_owner.complete,'same complete original file owner')
            self.selection_intact(); self.connected_destination(parent)
            io.need(len(self.file_owners)==727 and all(x.complete and x.first_error is None for x in self.file_owners),'all727 successful original copies')
            io.need(set(os.listdir(self.signals_descriptor.fd))=={r['file'].split('/')[1]for r in self.rows}
                    and os.listdir(self.destination_descriptor.fd)==['signals'],'exact whole fresh output membership')
            io.need(self.budget.read_bytes==self.planned_read_bytes and self.budget.write_bytes==self.total_bytes,'complete original logical IO support')
            os.fchmod(self.signals_descriptor.fd,0o555);os.fchmod(self.destination_descriptor.fd,0o555)
            for item in self.directory_owners:item.connected()
        except BaseException as error:self.retain(error)
        finally:
            for descriptor in(self.signals_descriptor,self.destination_descriptor):
                try:descriptor.close()
                except BaseException as error:self.retain(error)
            for item in reversed(self.directory_owners):
                try:item.close()
                except BaseException as error:self.retain(error)
        if self.first_error is None:
            try:
                self.selection_intact();io.need(all(x.closed for x in self.directory_owners)and self.destination_descriptor.close_completed and self.signals_descriptor.close_completed,'complete original directory close custody')
                self.complete=True
            except BaseException as error:self.retain(error)
        self.raise_error();return self
    def require_complete(self,selection_raw):
        io.need(type(self)is SignalSnapshotOwner and self.original_owner is self and self.complete and self.first_error is None,'original completed snapshot owner, not a receipt')
        chain=None
        try:
            self.selection_intact(selection_raw)
            io.need(len(self.file_owners)==len(self.rows)==727 and len(self.source_inodes)==727
                    and self.budget.files_started==727 and self.budget.read_bytes==self.planned_read_bytes
                    and self.budget.write_bytes==self.total_bytes, 'same original complete acquisition and IO membership')
            io.need(all(x.closed for x in self.directory_owners)
                    and self.destination_descriptor.close_completed and self.destination_descriptor.fd is None
                    and self.signals_descriptor.close_completed and self.signals_descriptor.fd is None,
                    'all original snapshot directory closes retained before handoff')
            chain=DirectoryChain(self,self.destination+'/signals');self.verification_owners.append(chain);chain.open()
            io.need(directory_identity(os.fstat(chain.fd))==self.signals_identity and stat.S_IMODE(os.fstat(chain.fd).st_mode)==0o555,'same read-only original signals root')
            io.need(directory_identity(os.fstat(chain.entries[-2][1].fd))==self.destination_identity and stat.S_IMODE(os.fstat(chain.entries[-2][1].fd).st_mode)==0o555,'same read-only original unified root')
            io.need(set(os.listdir(chain.fd))=={r['file'].split('/')[1]for r in self.rows}
                    and os.listdir(chain.entries[-2][1].fd)==['signals'],'full original snapshot membership before handoff')
            for row,owner in zip(self.rows,self.file_owners):
                self.budget.check();io.need(type(owner)is FileSnapshotOwner and owner.collection is self and owner.complete and owner.first_error is None
                    and owner.row_raw==io.encoded(row)==io.encoded(owner.row)
                    and all(x.close_completed and x.fd is None for x in(owner.source,owner.output,owner.readback)),
                    'same complete original file occurrence and closes')
                current=os.stat(row['file'].split('/')[1],dir_fd=chain.fd,follow_symlinks=False)
                io.need(stat.S_ISREG(current.st_mode)and current.st_nlink==1 and stat.S_IMODE(current.st_mode)==0o444 and identity(current)==owner.snapshot_identity,'same original read-only snapshot extent and identity')
            chain.connected();self.selection_intact()
        except BaseException as error:self.complete=False;self.retain(error)
        finally:
            if chain is not None:
                try:chain.close()
                except BaseException as error:self.complete=False;self.retain(error)
        self.raise_error();return self.destination
