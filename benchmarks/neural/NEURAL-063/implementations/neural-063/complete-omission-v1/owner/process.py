"""Linux direct-child parent-death race closure, never a descendant boundary.

Linux PDEATHSIG follows the *creating thread*. Creation is therefore refused
outside the parent's main thread. The parent's PID is captured before fork and
passed to the child; a late getppid() is not accepted as creation authority.
The child installs SIGKILL before operational effects and immediately rechecks.
Cgroup cleanup and finite independent supervision remain separately mandatory.
"""
import ctypes
import os
import signal
import sys
import threading
from .io import ContractError


def creation_parent():
    if sys.platform != "linux" or threading.current_thread() is not threading.main_thread():
        raise ContractError("qualified Linux main-thread process creation required")
    return os.getpid()


def bind_parent_death(expected_parent):
    if sys.platform != "linux" or type(expected_parent) is not int or expected_parent <= 1:
        raise ContractError("actual precreation Linux parent identity required")
    libc = ctypes.CDLL(None, use_errno=True)
    call = libc.prctl
    call.argtypes = [ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong]
    call.restype = ctypes.c_int
    if call(1, signal.SIGKILL, 0, 0, 0) != 0:  # PR_SET_PDEATHSIG
        raise OSError(ctypes.get_errno(), "PR_SET_PDEATHSIG refused")
    if os.getppid() != expected_parent:
        os.kill(os.getpid(), signal.SIGKILL)
        raise ContractError("creating parent changed before effects")
