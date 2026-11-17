"""Source-owned blocked role gate; executed only by enabled OwnedProcesses.

Interpreter startup before this gate enters the selected common cgroup belongs
to the declared launcher prelude. No migration-as-universal-memory claim exists.
"""
import hashlib
import json
import os
import selectors
import stat
import sys
import time


def main(argv):
    if len(argv)<11 or argv[9]!='--':raise ValueError('exact role gate operands')
    fd,maximum=int(argv[0]),int(argv[1]);scope=argv[2];device,inode=int(argv[3]),int(argv[4])
    origin,deadline=int(argv[5]),int(argv[6]);enabled=argv[7]
    ready=int(argv[8])
    if enabled!='independently-enabled' or maximum<=0 or not origin<deadline:raise ValueError('role gate disabled')
    def tick():
        now=time.monotonic_ns()
        if not origin<=now<deadline:raise ValueError('original gate deadline')
        return now
    tick();scopefd=os.open(scope,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW);primary=None;control=None
    try:
        node=os.fstat(scopefd)
        if (node.st_dev,node.st_ino)!=(device,inode):raise ValueError('selected common scope identity')
        control=os.open('cgroup.procs',os.O_WRONLY|os.O_NOFOLLOW,dir_fd=scopefd)
        raw=str(os.getpid()).encode('ascii')
        if os.write(control,raw)!=len(raw):raise ValueError('complete owned cgroup placement')
    except BaseException as error:primary=error;raise
    finally:
        first=primary
        for child in (control,scopefd):
            if child is None:continue
            try:os.close(child)
            except BaseException as error:
                if first is None:first=error
                else:first.add_note('Secondary gate descriptor close: '+type(error).__name__)
        if primary is None and first is not None:raise first
    if not stat.S_ISFIFO(os.fstat(fd).st_mode) or not stat.S_ISFIFO(os.fstat(ready).st_mode):raise ValueError('owned inherited gate pipes')
    ready_error=None
    try:
        if os.write(ready,b'R')!=1:raise ValueError('complete post-placement readiness')
    except BaseException as error:ready_error=error;raise
    finally:
        try:os.close(ready)
        except BaseException as error:
            if ready_error is None:raise
            ready_error.add_note('Secondary readiness pipe close: '+type(error).__name__)
    selector=None;parts=[];total=0;primary=None
    try:
        selector=selectors.DefaultSelector();selector.register(fd,selectors.EVENT_READ)
        while True:
            if not selector.select((deadline-tick())/1e9):raise ValueError('release deadline')
            block=os.read(fd,min(65536,maximum+1-total))
            if not block:break
            total+=len(block)
            if total>maximum:raise ValueError('release extent')
            parts.append(block)
        raw=b''.join(parts);tick()
        receipt=json.loads(raw)
        if receipt.get('schema')!='ach_typed_role_release_v1' or receipt.get('pid')!=os.getpid():raise ValueError('same selected role release')
        descriptor=receipt['configuration_pin'];path=receipt['configuration_path']
        filefd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW);inner=None
        try:
            before=os.fstat(filefd)
            if not stat.S_ISREG(before.st_mode) or before.st_nlink!=1 or before.st_size!=descriptor['bytes'] or before.st_size>maximum:
                raise ValueError('bounded ordinary exact role configuration')
            config=bytearray()
            while len(config)<=before.st_size:
                tick();block=os.read(filefd,min(65536,before.st_size+1-len(config)))
                if not block:break
                config.extend(block)
            after=os.fstat(filefd)
            if (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns):
                raise ValueError('role configuration replaced')
            if len(config)!=descriptor['bytes'] or hashlib.sha256(config).hexdigest()!=descriptor['sha256']:raise ValueError('exact selected role configuration pin')
        except BaseException as error:inner=error;raise
        finally:
            try:os.close(filefd)
            except BaseException as error:
                if inner is None:raise
                inner.add_note('Secondary gate config close: '+type(error).__name__)
        mapping={'@ROLE_CONFIG@':path,'@ROLE_CONFIG_BYTES@':str(descriptor['bytes']),'@ROLE_CONFIG_SHA256@':descriptor['sha256']}
        command=[mapping.get(value,value) for value in argv[10:]]
        if not command:raise ValueError('selected nonempty role command')
    except BaseException as error:primary=error;raise
    finally:
        first=primary
        for close in ([selector.close] if selector is not None else [])+[lambda:os.close(fd)]:
            try:close()
            except BaseException as error:
                if first is None:first=error
                else:first.add_note('Secondary gate pipe close: '+type(error).__name__)
        if primary is None and first is not None:raise first
    tick();os.execve(command[0],command,dict(os.environ))


if __name__=='__main__':main(sys.argv[1:])
