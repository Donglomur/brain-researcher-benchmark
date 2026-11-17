"""Bounded byte-stream staging; no array readers and no whole-file buffers."""
import hashlib
import os
import stat
from core import need
from safe_io import child, sync_parent


def copy_file(source,target,expected,budget,chunk_bytes=1048576):
    need(type(chunk_bytes) is int and 0<chunk_bytes<=1048576,'Bounded fixed staging buffer')
    source,target=os.fspath(source),os.fspath(target)
    budget.read(expected['bytes']);budget.write(expected['bytes'])
    src=dst=None;created=False;created_identity=None;primary=None;cleanup=[];total=0;h=hashlib.sha256()
    try:
        src=os.open(source,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC|os.O_NONBLOCK)
        before=os.fstat(src);need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_size==expected['bytes'],'Ordinary exact source member')
        dst=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o400);created=True
        owned=os.fstat(dst);created_identity=(owned.st_dev,owned.st_ino)
        while total<expected['bytes']:
            budget.tick();raw=os.read(src,min(chunk_bytes,expected['bytes']-total))
            need(raw,'Full source body required');total+=len(raw);budget.file_reads+=len(raw);h.update(raw)
            offset=0
            while offset<len(raw):
                n=os.write(dst,raw[offset:]);need(n>0,'Complete staging write');offset+=n;budget.file_writes+=n
        after=os.fstat(src)
        need((before.st_dev,before.st_ino,before.st_mode,before.st_nlink,before.st_size,before.st_mtime_ns,before.st_ctime_ns)==(after.st_dev,after.st_ino,after.st_mode,after.st_nlink,after.st_size,after.st_mtime_ns,after.st_ctime_ns),'Stable source identity throughout capture')
        need(h.hexdigest()==expected['sha256'],'Exact full source digest')
        os.fchmod(dst,0o444);os.fsync(dst)
    except BaseException as exc:primary=exc
    finally:
        for fd in (src,dst):
            if fd is not None:
                try:os.close(fd)
                except BaseException as exc:cleanup.append(exc)
    if primary is None and not cleanup:
        try:sync_parent(target)
        except BaseException as exc:cleanup.append(exc)
    if primary is not None or cleanup:
        if created:
            try:
                current=os.lstat(target)
                need(created_identity is not None and stat.S_ISREG(current.st_mode) and (current.st_dev,current.st_ino)==created_identity,'Cleanup refused foreign or unproven staging inode')
                os.unlink(target)
            except BaseException as exc:cleanup.append(exc)
            try:sync_parent(target)
            except BaseException as exc:cleanup.append(exc)
        if primary is not None:
            if cleanup:raise RuntimeError('Staging primary failure: '+repr(primary)+'; cleanup failures: '+repr(cleanup)) from primary
            raise primary
        raise RuntimeError('Staging close/durability failure: '+repr(cleanup)) from cleanup[0]
    budget.tick();return dict(expected)
