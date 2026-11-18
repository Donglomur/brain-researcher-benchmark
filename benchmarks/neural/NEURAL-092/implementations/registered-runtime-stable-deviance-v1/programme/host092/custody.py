"""In-process ownership issued from acquired OS custody, never serialized."""
import os,weakref
_LIVE=weakref.WeakKeyDictionary()
def issue(host,group_fd,supervisor_pid,selection,errors):
    # Called only by the fixed trusted coordinator after the outer supervisor
    # has forked/moved it. The untrusted child never imports this package.
    from .admission import _SELECTIONS
    from .storage import decode
    captured=_SELECTIONS.get(selection)
    if captured is None or captured[0]!=supervisor_pid:raise RuntimeError('original supervisor-captured root selection, inherited only')
    profile=decode(captured[1]);expected=profile['cgroup_parent'].rstrip('/')+'/'+profile['run_id']
    actual=os.readlink('/proc/self/fd/'+str(group_fd))
    if actual!=expected or not expected.startswith('/sys/fs/cgroup/'):raise RuntimeError('original actual enclosing cgroup descriptor')
    st=os.fstat(group_fd)
    if os.getppid()!=supervisor_pid:raise RuntimeError('lost original supervisor')
    start=len(errors.events);stream=None;membership=None
    def capture_membership():
        nonlocal stream,membership
        stream=open('/proc/self/cgroup',encoding='ascii');membership=stream.read(65537)
    try:errors.call('custody_membership_read',capture_membership)
    except BaseException:pass
    finally:
        if stream is not None:errors.cleanup('custody_membership_close',stream.close)
    errors.finish(start)
    expected_membership=expected[len('/sys/fs/cgroup'):]+'/coordinator'
    if host.membership!=expected_membership or '0::'+expected_membership+'\n'!=membership:raise RuntimeError('actual coordinator cgroup membership')
    _LIVE[host]=(os.getpid(),group_fd,st.st_dev,st.st_ino,supervisor_pid)
def require(host,operation):
    record=_LIVE.get(host)
    if record is None:raise RuntimeError('no original acquired host: '+operation)
    pid,fd,dev,ino,parent=record
    if os.getpid()!=pid or os.getppid()!=parent or host.closed:raise RuntimeError('stale live host')
    st=os.fstat(fd)
    if(st.st_dev,st.st_ino)!=(dev,ino):raise RuntimeError('lost owned cgroup descriptor')
    return host
def revoke(host):_LIVE.pop(host,None)
