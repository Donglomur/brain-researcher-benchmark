"""Bounded private append-only originals and conservative write accounting."""
import hashlib
import json
import os
from pathlib import Path
import re
import stat

EVIDENCE_CAP = 4*1024*1024
CLEANUP_RESERVE = 512*1024
REPORT_CAP = 65536
MAX_FILES = 512


class CustodyFailure(RuntimeError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('ascii')


def binding(raw):
    return {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}


def directory_signature(path):
    s = os.lstat(path)
    if not stat.S_ISDIR(s.st_mode) or s.st_uid != os.getuid() or s.st_mode & 0o077:
        raise CustodyFailure('private owned directory required')
    return (s.st_dev,s.st_ino,s.st_mode,s.st_uid)


def sync_directory(path,expected):
    """Persist the directory entry without following a substituted link."""
    fd=None;primary=None
    try:
        fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        value=os.fstat(fd)
        if ((value.st_dev,value.st_ino,value.st_mode,value.st_uid)!=expected or
                directory_signature(path)!=expected):
            raise CustodyFailure('directory fsync identity changed')
        os.fsync(fd)
    except BaseException as error:
        primary=error
        raise
    finally:
        if fd is not None:
            closing,fd=fd,None
            try:os.close(closing)
            except BaseException as cleanup:
                if primary is not None and not isinstance(primary,Exception) and isinstance(cleanup,Exception):
                    raise primary
                raise


class EvidenceStore:
    """Serial trusted recorder; external supervisor bounds fsync/callback time.

    Each request reserves its full extent before opening. A failed write keeps
    that entire grant, including bytes with unknown syscall effects. Successful
    close/stat/fsync is required before returning a binding. No truncation,
    overwrite, retry, unlink credit, or claim of independently rehashed custody.
    """
    def __init__(self, root):
        self.root = Path(root)
        parent_identity=directory_signature(self.root.parent)
        os.mkdir(self.root,0o700)
        self.identity = directory_signature(self.root)
        sync_directory(self.root.parent,parent_identity)
        self.cleanup = False
        self.poisoned = False
        self.charged = self.confirmed = self.known_written = self.denied = 0
        self.entries = []
        self._by_hash = {}

    def __call__(self, kind, raw):
        if (type(kind) is not str or not re.fullmatch('[a-z][a-z0-9_]{0,47}',kind) or
                type(raw) is not bytes):
            raise CustodyFailure('exact bounded evidence input required')
        if self.poisoned: raise CustodyFailure('evidence store poisoned')
        if directory_signature(self.root) != self.identity:
            self.poisoned = True
            raise CustodyFailure('evidence directory changed')
        cleanup = self.cleanup or kind in ('code_call','code_close','qualification_failure')
        limit = EVIDENCE_CAP if cleanup else EVIDENCE_CAP-CLEANUP_RESERVE
        if self.charged+len(raw)>limit or len(self.entries)>=MAX_FILES:
            self.denied += len(raw)
            raise CustodyFailure('evidence write allowance exhausted')
        self.charged += len(raw)
        entry={'path':f'{len(self.entries):04d}-{kind}.bin','kind':kind,
               'binding':binding(raw),'charged_bytes':len(raw),'known_written_bytes':0,
               'status':'started','cleanup_allowance':cleanup}
        self.entries.append(entry)
        fd = None;primary=None
        try:
            fd=os.open(self.root/entry['path'],os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
            initial=os.fstat(fd)
            if not stat.S_ISREG(initial.st_mode) or initial.st_nlink!=1:
                raise CustodyFailure('exclusive regular evidence file required')
            offset=0
            while offset<len(raw):
                written=os.write(fd,memoryview(raw)[offset:offset+65536])
                if type(written) is not int or not 0<written<=min(65536,len(raw)-offset):
                    raise CustodyFailure('invalid write count')
                offset+=written;entry['known_written_bytes']+=written;self.known_written+=written
            os.fsync(fd)
            closing,fd=fd,None
            os.close(closing)  # Never retry an ambiguous interrupted close.
            final=os.lstat(self.root/entry['path'])
            if (not stat.S_ISREG(final.st_mode) or final.st_nlink!=1 or
                    (final.st_dev,final.st_ino)!=(initial.st_dev,initial.st_ino) or
                    final.st_size!=len(raw) or directory_signature(self.root)!=self.identity):
                raise CustodyFailure('closed evidence extent changed')
            sync_directory(self.root,self.identity)
            entry['status']='confirmed'
            self.confirmed+=len(raw)
            # Metadata and prefix views are bounded; large flood bodies are not copied.
            self._by_hash.setdefault(entry['binding']['sha256'],[]).append(
                (entry,raw if len(raw)<=65536 else None,raw[:4096]))
            return dict(entry['binding'])
        except BaseException as error:
            primary=error
            self.poisoned=True;entry['status']='unknown';entry['error_type']=type(error).__name__
            raise
        finally:
            if fd is not None:
                closing,fd=fd,None
                try:os.close(closing)
                except BaseException as cleanup:
                    self.poisoned=True;entry['status']='unknown'
                    entry['cleanup_error_type']=type(cleanup).__name__
                    if primary is not None and not isinstance(primary,Exception) and isinstance(cleanup,Exception):
                        raise primary
                    raise

    def lookup(self, expected, kind):
        if (type(expected) is not dict or set(expected)!={'bytes','sha256'} or
                type(expected['bytes']) is not int or type(expected['sha256']) is not str):
            raise CustodyFailure('strict original binding required')
        matches=[v for v in self._by_hash.get(expected['sha256'],())
                 if v[0]['kind']==kind and v[0]['binding']==expected and v[0]['status']=='confirmed']
        if not matches:raise CustodyFailure('original bytes not confirmed by recorder')
        return matches[-1]

    def summary(self):
        return {'cap_bytes':EVIDENCE_CAP,'cleanup_reserve_bytes':CLEANUP_RESERVE,
                'charged_cumulative_write_bytes':self.charged,
                'confirmed_cumulative_write_bytes':self.confirmed,
                'known_returned_write_bytes':self.known_written,
                'unknown_write_grant_bytes':self.charged-self.confirmed,
                'denied_before_write_bytes':self.denied,'poisoned':self.poisoned,
                'files':[dict(e,binding=dict(e['binding'])) for e in self.entries],
                'physical_io_measured':False,'independent_postexit_rehash':False}


class ReportWriter:
    """One separate final report; its own grant is reported outside its body."""
    def __init__(self, root):
        self.root=Path(root);self.identity=directory_signature(root)
        self.attempted=False;self.charged=self.confirmed=self.known_written=0
        self.receipt=None

    def write(self,value):
        if self.attempted:raise CustodyFailure('one final report attempt only')
        self.attempted=True
        raw=canonical(value)
        if len(raw)>REPORT_CAP:raise CustodyFailure('final report capacity')
        self.charged=len(raw);fd=None;primary=None
        try:
            if directory_signature(self.root)!=self.identity:raise CustodyFailure('report root changed')
            fd=os.open(self.root/'QUALIFICATION_REPORT.json',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
            s=os.fstat(fd);offset=0
            while offset<len(raw):
                n=os.write(fd,memoryview(raw)[offset:])
                if type(n) is not int or not 0<n<=len(raw)-offset:raise CustodyFailure('report write count')
                offset+=n;self.known_written+=n
            os.fsync(fd);closing,fd=fd,None;os.close(closing)
            end=os.lstat(self.root/'QUALIFICATION_REPORT.json')
            if (not stat.S_ISREG(end.st_mode) or end.st_nlink!=1 or
                    (end.st_dev,end.st_ino,end.st_size)!=(s.st_dev,s.st_ino,len(raw)) or
                    directory_signature(self.root)!=self.identity):raise CustodyFailure('report identity changed')
            sync_directory(self.root,self.identity)
            self.confirmed=len(raw);self.receipt=binding(raw)
            return dict(self.receipt)
        except BaseException as error:
            primary=error
            raise
        finally:
            if fd is not None:
                closing,fd=fd,None
                try:os.close(closing)
                except BaseException as cleanup:
                    if primary is not None and not isinstance(primary,Exception) and isinstance(cleanup,Exception):
                        raise primary
                    raise

    def summary(self):
        return {'cap_bytes':REPORT_CAP,'attempted':self.attempted,'binding':self.receipt,
                'charged_cumulative_write_bytes':self.charged,
                'confirmed_cumulative_write_bytes':self.confirmed,
                'known_returned_write_bytes':self.known_written,
                'unknown_write_grant_bytes':self.charged-self.confirmed}
