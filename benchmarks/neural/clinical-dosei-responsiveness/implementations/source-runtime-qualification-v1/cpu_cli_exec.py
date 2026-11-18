"""Fixed Docker CLI CPU guard; exec preserves the owned PID/session and pipes."""
import os
import resource
import signal
import sys

DOCKER = '/usr/local/Cellar/docker/29.4.0/bin/docker'
SOFT_CPU_SECONDS = 2
HARD_CPU_SECONDS = 3


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if not (len(args) >= 2 and args[0] == '--' and args[1] == DOCKER
            and len(args) <= 128 and all(type(x) is str and '\x00' not in x and
            0 < len(x.encode('utf-8')) <= 4096 for x in args)):
        raise ValueError('fixed bounded Docker CLI command required')
    signal.signal(signal.SIGXCPU, signal.SIG_DFL)
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_CPU, (SOFT_CPU_SECONDS, HARD_CPU_SECONDS))
    os.execv(DOCKER, args[1:])
    raise RuntimeError('exec unexpectedly returned')


if __name__ == '__main__':
    main()
