"""Inert future Linux accounting fixture; never a Helsinki prediction program.
No data, target, model, network or file input is read. Execute only in the
separately selected unprivileged diagnostic container, never on the host.
"""
import json
import os
import time


def main():
    child = os.fork()
    if child == 0:
        try:
            memory = bytearray(8 * 1024 * 1024)
            for i in range(0, len(memory), 4096):
                memory[i] = 1
            start = time.process_time()
            value = 1
            while time.process_time() - start < 0.1:
                value = (value * 1664525 + 1013904223) & 0xffffffff
            os._exit(0 if memory[0] == 1 else 2)
        except BaseException:
            os._exit(3)
    got, status = os.waitpid(child, 0)
    if got != child or not os.WIFEXITED(status) or os.WEXITSTATUS(status) != 0:
        raise RuntimeError('diagnostic child did not exit naturally')
    print(json.dumps({'schema': 'helsinki-cgroup-lifecycle-fixture/v1',
                      'child_natural_zero': True, 'touched_bytes': 8388608},
                     sort_keys=True, separators=(',', ':')))


if __name__ == '__main__':
    main()
