"""Trusted production-only pre-exec stop for cgroup attachment."""
import os
import signal
import sys

if __name__=='__main__':
    os.kill(os.getpid(),signal.SIGSTOP)
    os.execv(sys.argv[1],sys.argv[1:])
