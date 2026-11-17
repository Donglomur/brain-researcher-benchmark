"""Original anchored workspace observations and bounded source-only readers.

No root is reconstructed from a descriptor. Each instance keeps the original
OwnedPreparationPath, original host meter and once-only descriptor custody.
"""
import os
import stat
import time
from .common import need, integer, relative, pin
from .preparation_ownership import OwnedPreparationPath
from .precommit_records import validate_type


def retained_workspace_identity(attempt):
    attempt.require_live_original()
    path = attempt.arm.workspace
    need(type(path) is OwnedPreparationPath and path.custody is attempt.pair.custody and
         path.condition == attempt.condition and path.kind == 'directory' and
         path.fd is not None and path.parents and path.identity is not None and
         not path.cleanup_attempted and not path.removal_attempted and not path.close_unknown,
         'same actual retained original workspace anchor')
    attempt.owner.host.charge('work_units', 8192)
    before = os.fstat(path.fd)
    named = os.stat(path.leaf, dir_fd=path.parents[-1], follow_symlinks=False)
    need(stat.S_ISDIR(before.st_mode) and stat.S_ISDIR(named.st_mode) and
         (before.st_dev, before.st_ino, before.st_uid) ==
         (named.st_dev, named.st_ino, named.st_uid) ==
         tuple(path.identity[k] for k in ('device', 'inode', 'uid')),
         'same original directory, parent inode and original owner')
    attempt.owner.check()
    observed = time.monotonic_ns(); integer(observed)
    need(observed < attempt.evidence_deadline_ns == attempt.owner.parent.original_deadline,
         'original H evidence interval without a new clock')
    body = dict(path.identity, mode=stat.S_IMODE(before.st_mode), observed_ns=observed)
    validate_type('OwnedPathIdentity', body)
    return body


class WorkspaceReader:
    """One original retained read authority, including failed opens and closes."""
    def __init__(self, capture, attempt):
        # ProgrammeCapture supplies its own exact registered owner below.
        from .programme_capture import ProgrammeCaptureHandle
        need(type(capture) is ProgrammeCaptureHandle and capture.pair.programme_capture is capture and
             capture.pair_completion.attempts.get(attempt.condition) is attempt,
             'same registered source capture and actual original arm')
        self.capture=capture; self.attempt=attempt; self.path=attempt.arm.workspace
        self.meter=attempt.owner.host; self.operations=[]; self.raw_first=None; self.raw_secondaries=[]
        self.retained_identity=retained_workspace_identity(attempt)

    def _retain(self, error, operation):
        if self.raw_first is None:self.raw_first=error
        elif error is not self.raw_first:self.raw_secondaries.append(error)
        operation['errors'].append(error)
        self.capture.retain(error, 'WorkspaceReader')

    def _begin(self, kind, name):
        operation={'kind':kind,'path':name,'fds':[],'errors':[],'read_entered':False,
                   'known_prefix':[],'unknown_extent':False,'complete':False}
        self.operations.append(operation)
        try:
            need(self.raw_first is None, 'no continuation of a failed workspace reader')
            relative(name)
            need(len(name.split('/')) <= self.capture.depth, 'original selected path depth')
            self.meter.charge('work_units',4096+len(name)*64)
            self.meter.charge('retained_bytes',4096+len(name)*4)
            retained_workspace_identity(self.attempt)
            return operation
        except BaseException as error:self._retain(error,operation);raise

    def _parents(self, operation):
        current=self.path.fd
        for part in operation['path'].split('/')[:-1]:
            self.meter.check()
            fd=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=current)
            operation['fds'].append(fd);current=fd
        return current,operation['path'].split('/')[-1]

    def _close(self, operation):
        first=None
        while operation['fds']:
            fd=operation['fds'].pop()  # relinquish before the ambiguous syscall
            try:os.close(fd)
            except BaseException as error:
                if first is None:first=error
                self._retain(error,operation)
        return first

    def read(self, name, cap, *, declared=None):
        operation=self._begin('read',name);primary=None;result=None
        try:
            integer(cap,1)
            # Maximum+EOF reservation precedes open and all actual returned bytes.
            self.meter.charge('read_bytes',cap+1)
            self.meter.charge('retained_bytes',2*(cap+1)+8192)
            self.meter.charge('work_units',4*(cap+1)+8192)
            parent,leaf=self._parents(operation)
            fd=os.open(leaf,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=parent)
            operation['fds'].append(fd)
            before=os.fstat(fd)
            need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and
                 before.st_uid==self.retained_identity['uid'] and 0<=before.st_size<=cap and
                 stat.S_IMODE(before.st_mode)<=0o777,'actual ordinary bounded same-owner source')
            before_clock=self.capture.clock()
            count=0
            while count<=before.st_size:
                self.meter.check();operation['read_entered']=True
                try:raw=os.read(fd,min(65536,before.st_size+1-count))
                except BaseException:
                    operation['unknown_extent']=True;raise
                need(type(raw) is bytes,'original byte return')
                operation['known_prefix'].append(raw);count+=len(raw)
                if not raw:break
            raw=b''.join(operation['known_prefix'])
            after=os.fstat(fd);named=os.stat(leaf,dir_fd=parent,follow_symlinks=False)
            keys=('st_dev','st_ino','st_uid','st_size','st_mode','st_mtime_ns','st_ctime_ns','st_nlink')
            need(len(raw)==before.st_size and all(getattr(before,k)==getattr(after,k)==getattr(named,k)
                 for k in keys),'complete unchanged original file with EOF and named inverse')
            raw.decode('utf8',errors='strict');need(b'\0' not in raw,'ordinary UTF8 source with no NUL')
            if declared is not None:
                need(declared['relative_path']==name and declared['mode']==stat.S_IMODE(before.st_mode) and
                     {k:declared[k] for k in ('bytes','sha256')}==pin(raw),'exact complete declared source')
            def identity(s,clock):
                return {'schema':'ci_owned_path_identity_v1','parent_handle_ordinal':self.path.anchor_handle.ordinal,
                        'relative_path':name,'device':s.st_dev,'inode':s.st_ino,'kind':'regular_file',
                        'mode':stat.S_IMODE(s.st_mode),'uid':s.st_uid,'observed_ns':clock}
            result=(raw,identity(before,before_clock),identity(after,self.capture.clock()))
        except BaseException as error:
            primary=error;self._retain(error,operation)
        close=self._close(operation)
        if primary is not None:raise primary
        if close is not None:raise close
        try:self.meter.check()
        except BaseException as error:self._retain(error,operation);raise
        operation['complete']=True
        return result

    def inventory(self, expected):
        """Complete bounded metadata census; inherited file bodies stay closed."""
        operation={'kind':'inventory','path':'','fds':[],'iterators':[],'errors':[],
                   'observed':{},'complete':False}
        self.operations.append(operation);primary=None
        try:
            need(self.raw_first is None and type(expected) is dict and
                 len(expected)<=self.capture.files,'complete predeclared finite partition')
            self.meter.charge('retained_bytes',(self.capture.files+1)*8192)
            self.meter.charge('work_units',(self.capture.files+1)*8192)
            retained_workspace_identity(self.attempt)
            pending=[('',self.path.fd)]
            while pending:
                prefix,fd=pending.pop()
                self.meter.check()
                cursor=os.scandir(fd);operation['iterators'].append(cursor)
                for entry in cursor:
                    self.meter.check()
                    name=(prefix+'/' if prefix else '')+entry.name
                    relative(name)
                    need(len(name.split('/'))<=self.capture.depth and name in expected and
                         name not in operation['observed'] and len(operation['observed'])<self.capture.files,
                         'no unlisted/duplicate/deep/over-cap workspace member')
                    original=expected[name];s=entry.stat(follow_symlinks=False)
                    directory=original['kind']=='directory'
                    need((stat.S_ISDIR(s.st_mode) if directory else stat.S_ISREG(s.st_mode)) and
                         s.st_uid==self.retained_identity['uid'] and (directory or s.st_nlink==1),
                         'same-owner ordinary partition; no alias, socket, FIFO or device')
                    if original.get('identity') is not None:
                        i=original['identity']
                        need((s.st_dev,s.st_ino,s.st_uid,stat.S_IMODE(s.st_mode))==
                             (i['device'],i['inode'],i['uid'],i['mode']),
                             'unchanged original inherited/declared object identity')
                    if original.get('bytes') is not None:
                        need(s.st_size==original['bytes'],'exact predeclared original extent')
                    operation['observed'][name]=(s.st_dev,s.st_ino,s.st_uid,s.st_mode,
                                                s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_nlink)
                    if directory:
                        child=os.open(entry.name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd)
                        operation['fds'].append(child)
                        observed=os.fstat(child)
                        need((observed.st_dev,observed.st_ino)==(s.st_dev,s.st_ino),'same directory before descent')
                        pending.append((name,child))
                operation['iterators'].remove(cursor);cursor.close()
            need(set(operation['observed'])==set(expected),'complete exact whole-workspace partition')
        except BaseException as error:primary=error;self._retain(error,operation)
        while operation['iterators']:
            cursor=operation['iterators'].pop()
            try:cursor.close()
            except BaseException as error:
                if primary is None:primary=error
                self._retain(error,operation)
        close=self._close(operation)
        if primary is not None:raise primary
        if close is not None:raise close
        try:self.meter.check()
        except BaseException as error:self._retain(error,operation);raise
        operation['complete']=True
        return dict(operation['observed'])


def capture_source_file(capture, condition, ordinal, raw, declared, before, after):
    """One new H file with exact mode, fsync, close and whole readback."""
    p=capture.publisher;name='programme_'+condition+'_'+str(ordinal)+'.txt'
    record={'name':name,'fds':[],'raw_first':None,'raw_secondaries':[],
            'write_entered':False,'known_written':0,'unknown_write':False,
            'descriptor':None,'identity':None,'complete':False}
    need((condition,ordinal) not in capture.file_attempts,'one captured source file attempt')
    capture.file_attempts[(condition,ordinal)]=record
    record['parent_ordinal']=len(capture.parent_handles)
    capture.parent_handles.append(record)
    primary=None;result=None
    def own(error):
        if record['raw_first'] is None:record['raw_first']=error
        elif error is not record['raw_first']:record['raw_secondaries'].append(error)
        capture.retain(error,'capture_source_file')
    try:
        need(type(raw) is bytes and len(raw)<=capture.source_cap,'complete original source in same cap')
        key=(str(p.outputs.root),name)
        need(key not in p.parent.canonical_publications and
             len(p.parent.canonical_publications)<p.maximum_members,'original global publication count')
        p.parent.canonical_publications[key]=record
        p.meter.charge('write_bytes',len(raw));p.meter.charge('retained_bytes',2*len(raw)+8192)
        p.meter.charge('work_units',4*len(raw)+8192)
        parents,leaf=p.outputs._parent(name);record['fds'].extend(parents)
        fd=os.open(leaf,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=parents[-1])
        record['fds'].append(fd)
        while record['known_written']<len(raw):
            p.meter.check();record['write_entered']=True
            record['unknown_write']=True
            amount=os.write(fd,raw[record['known_written']:])
            need(type(amount) is int and 0<amount<=len(raw)-record['known_written'],'actual bounded write prefix')
            record['known_written']+=amount
            record['unknown_write']=False
        mode=0o400|(declared['mode']&0o100)
        p.meter.check();os.fsync(fd);os.fchmod(fd,mode)
        original=os.fstat(fd);named=os.stat(leaf,dir_fd=parents[-1],follow_symlinks=False)
        need(stat.S_ISREG(original.st_mode) and original.st_nlink==1 and
             (original.st_dev,original.st_ino,original.st_uid,original.st_size,stat.S_IMODE(original.st_mode))==
             (named.st_dev,named.st_ino,named.st_uid,len(raw),mode), 'actual immutable H-created source identity')
        expected={'path':name,**pin(raw)};record['descriptor']=expected
        actual=p.outputs.read(expected,capture.source_cap)
        need(actual==raw,'full actual fsync/write/readback inverse before source admission')
        identity={'schema':'ci_owned_path_identity_v1','parent_handle_ordinal':record['parent_ordinal'],
                  'relative_path':name,'device':original.st_dev,'inode':original.st_ino,
                  'kind':'regular_file','mode':mode,'uid':original.st_uid,'observed_ns':capture.clock()}
        record['identity']=identity
        result={'schema':'ci_captured_programme_file_v1','ordinal':ordinal,'declared':declared,
                'before':before,'after':after,'captured':expected,'captured_identity':identity,'captured_mode':mode}
        validate_type('CapturedProgrammeFile',result)
    except BaseException as error:primary=error;own(error)
    while record['fds']:
        fd=record['fds'].pop()
        try:os.close(fd)
        except BaseException as error:
            if primary is None:primary=error
            own(error)
    if primary is not None:raise primary
    try:p.meter.check()
    except BaseException as error:own(error);raise
    record['complete']=True
    return result

