"""Fixed tiny process-lifecycle fixture; never accepts programme code or Docker."""
import argparse
import os
import socket
import time


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--channel-fd', type=int, required=True)
    p.add_argument('--behavior', choices=('complete', 'wait'), required=True)
    a = p.parse_args()
    with socket.socket(fileno=a.channel_fd) as channel:
        channel.sendall(b'fixed-trusted-fixture:' + str(os.getpid()).encode() + b'\n')
        if a.behavior == 'wait':
            while True:
                time.sleep(.05)


if __name__ == '__main__':
    main()
