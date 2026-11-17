"""Task-local exact qualified transport and ownership-v4, shared by parent and child."""
from pathlib import Path
import os
import stat
from files import ROOT, HERE, need, read, pin, descriptor, captured_module, strict_json, current_metadata

IMPORTS = current_metadata('IMPORTS.json')
qualified = captured_module(IMPORTS['qualified_core'], 'qualified_core', register=True)
validator = captured_module(IMPORTS['trusted_controller'], 'trusted_controller', register=True)
owner = captured_module(IMPORTS['process_owner'], '_hierarchy_central_owner_v4', register=True)
need(owner.HERE == HERE / 'ownership-v4-721', 'Parent/child use identical task-local v4-721 journal identity')
BaseEngine = qualified.BaseEngine
HostBudget = qualified.HostBudget


def ordinary(source, cap, empty=False):
    p = Path(source).absolute()
    need('..' not in p.parts and all(not q.is_symlink() for q in (p, *p.parents)), 'Unlinked ordinary input')
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        a = os.fstat(fd)
        need(stat.S_ISREG(a.st_mode) and a.st_nlink == 1 and
             (0 if empty else 1) <= a.st_size <= cap, 'Bounded single-link input')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            body = stream.read(cap + 1)
        b = os.fstat(fd)
        need(len(body) == a.st_size and all(getattr(a,k) == getattr(b,k) for k in
             ('st_dev','st_ino','st_mode','st_nlink','st_size','st_mtime_ns','st_ctime_ns')), 'Stable complete captured bytes')
        return body
    finally:
        os.close(fd)


def pinned(value):
    return descriptor(value, 2000000, decode=False)
