"""Lazy concrete Linux x86-64 ABI calls; no library load at import."""
import ctypes
import errno
import platform
from .custody import require

class _StatFS(ctypes.Structure):
    _fields_=[("kind",ctypes.c_long),("block_size",ctypes.c_long),
              ("blocks",ctypes.c_ulong),("free_blocks",ctypes.c_ulong),
              ("available_blocks",ctypes.c_ulong),("files",ctypes.c_ulong),
              ("free_files",ctypes.c_ulong),("fsid",ctypes.c_int*2),
              ("name_length",ctypes.c_long),("fragment_size",ctypes.c_long),
              ("flags",ctypes.c_long),("spare",ctypes.c_long*4)]

def require_cgroup2(fd):
    require(platform.system()=="Linux" and platform.machine()=="x86_64",
            "selected-linux-x86-64-only")
    require(type(fd)is int and fd>=0,"native-fd")
    libc=ctypes.CDLL(None,use_errno=True)
    function=libc.fstatfs
    function.argtypes=[ctypes.c_int,ctypes.POINTER(_StatFS)]
    function.restype=ctypes.c_int
    result=_StatFS()
    if function(fd,ctypes.byref(result))!=0:
        code=ctypes.get_errno()
        raise OSError(code,"fstatfs failed")
    require(result.kind==0x63677270,"actual-cgroup-v2-filesystem")
    return result.kind
