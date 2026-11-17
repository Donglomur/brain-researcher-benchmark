"""Exact inherited opaque credential reader; proxy only, no file discovery."""
import os
import stat
import selectors
import time
from ach_resource_common import close_all as close_owned

def read_authorization_pipe(fd,origin,deadline):
    """Owned inherited pipe, bounded EOF under the original clock; no log/hash."""
    if type(fd) is not int or fd<3 or type(origin) is not int or type(deadline) is not int:
        raise ValueError('invalid opaque credential transport')
    selector=None;primary=None;parts=[];total=0
    try:
        if not origin<=time.monotonic_ns()<deadline:raise ValueError('credential transport original cutoff')
        if not stat.S_ISFIFO(os.fstat(fd).st_mode):raise ValueError('credential transport must be an inherited pipe')
        os.set_blocking(fd,False);selector=selectors.DefaultSelector();selector.register(fd,selectors.EVENT_READ)
        while True:
            now=time.monotonic_ns()
            if not origin<=now<deadline:raise ValueError('credential transport original cutoff')
            ready=selector.select(min(.1,(deadline-now)/1e9))
            if not ready:continue
            block=os.read(fd,min(4096,8193-total))
            if not block:break
            total+=len(block)
            if total>8192:raise ValueError('opaque credential transport extent')
            parts.append(block)
        if not origin<=time.monotonic_ns()<deadline or not total:raise ValueError('opaque credential transport incomplete')
        raw=b''.join(parts)
        if any(x<32 or x>126 for x in raw):raise ValueError('opaque credential encoding refused')
        return raw.decode('ascii')
    except BaseException as error:primary=error;raise
    finally:
        cleanup=[]
        if selector is not None:cleanup.append(('credential selector close',selector.close))
        cleanup.append(('owned credential pipe close',lambda:os.close(fd)))
        close_owned(cleanup,primary)

