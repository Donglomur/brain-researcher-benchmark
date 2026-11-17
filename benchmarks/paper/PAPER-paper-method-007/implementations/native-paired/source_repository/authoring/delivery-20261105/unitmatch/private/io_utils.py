"""Bounded file admission and same-open private-source verification, stdlib only."""
import hashlib
import os
import stat


def signature(value):
    return (value.st_dev,value.st_ino,value.st_size,value.st_mtime_ns,value.st_ctime_ns)


def open_regular(path, limit):
    fd=os.open(path,os.O_RDONLY|os.O_NONBLOCK|os.O_NOFOLLOW)
    try:
        before=os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or not 0<=before.st_size<=limit:
            raise ValueError('bounded regular file required')
        return os.fdopen(fd,'rb'),before
    except BaseException:
        os.close(fd)
        raise


def capture(path,limit):
    file,before=open_regular(path,limit)
    with file:
        chunks=[];length=0
        while True:
            block=file.read(min(65536,limit-length+1))
            if not block:break
            length+=len(block)
            if length>limit:raise ValueError('bounded file required')
            chunks.append(block)
        if signature(before)!=signature(os.fstat(file.fileno())) or length!=before.st_size:
            raise ValueError('file changed during capture')
    raw=b''.join(chunks)
    return raw,hashlib.sha256(raw).hexdigest()


class VerifiedSource:
    def __init__(self,path,expected_sha256,limit=200_000_000):
        self.file,self.before=open_regular(path,limit)
        try:
            digest=hashlib.sha256();length=0
            while True:
                block=self.file.read(min(1024*1024,limit-length+1))
                if not block:break
                length+=len(block)
                if length>limit:raise ValueError('private source extent')
                digest.update(block)
            self.assert_stable()
            if length!=self.before.st_size or digest.hexdigest()!=expected_sha256:
                raise ValueError('private reference source pin mismatch')
            self.file.seek(0)
        except BaseException:
            self.file.close()
            raise

    def assert_stable(self):
        if signature(self.before)!=signature(os.fstat(self.file.fileno())):
            raise ValueError('private source changed after verification')

    def __enter__(self):return self

    def __exit__(self,*args):self.file.close()
