"""Fixed installed HM scientific worker: no participant path or callback arguments."""
import sys
from .common import need
from .hm_whole_worker_runtime_v1 import run_fixed_hm_whole_worker_v1


def main():
    need(len(sys.argv) == 1, 'fixed HM worker entry accepts no arguments')
    return run_fixed_hm_whole_worker_v1()


if __name__ == '__main__':
    main()
