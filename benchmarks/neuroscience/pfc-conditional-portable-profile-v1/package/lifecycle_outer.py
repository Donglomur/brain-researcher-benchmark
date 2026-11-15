"""Accepted outer receipt and process-absence functions, with no old diagnostic entrypoint."""
import time,hashlib,json,os,stat
from pathlib import Path
START=time.monotonic()
RETENTION_CAP=1048576
STREAM_CAP=262144
ROOT=END=None

def need(ok, why):
    if not ok:
        raise RuntimeError(why)


def retained():
    total = 0
    for path in ROOT.iterdir():
        st = path.lstat(); need(stat.S_ISREG(st.st_mode) and st.st_nlink == 1, 'flat ordinary caller evidence')
        total += st.st_size
    return total


def save(name, value):
    body = value if isinstance(value, bytes) else (json.dumps(value, sort_keys=True, allow_nan=False)+'\n').encode()
    need(name == Path(name).name and 0 < len(name) < 128 and len(body) <= STREAM_CAP,
         'finite outer original evidence')
    need(time.monotonic() < END and retained()+len(body) <= RETENTION_CAP,
         'original outer retention/horizon before publication')
    fd = os.open(ROOT/name, os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW, 0o400)
    try:
        offset = 0
        while offset < len(body):
            need(time.monotonic() < END, 'original caller publication horizon')
            size = os.write(fd, body[offset:]); need(size > 0, 'complete original publication'); offset += size
        os.fsync(fd)
    finally:
        os.close(fd)
    return {'path': str(ROOT/name), 'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def group_absent(pid):
    try:
        os.killpg(pid, 0)
    except ProcessLookupError:
        return True
    return False

