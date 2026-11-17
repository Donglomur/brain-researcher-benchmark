"""Create-only operator artifacts, bounded capture and an unchanged run clock."""
import hashlib
import os
from pathlib import Path
import stat
import time
import compatibility as c

need, exact, parse, encoded, pin = c.need, c.exact, c.parse, c.encoded, c.pin
CAP = 16 * 1048576


def parent_fd(path):
    fd=os.open('/',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:
        for part in path.parent.parts[1:]:
            child=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd)
            os.close(fd);fd=child
        return fd
    except BaseException:
        os.close(fd);raise


class Budget:
    def __init__(self, limits, clock=time.monotonic):
        exact(limits, ('read_bytes', 'write_bytes', 'signal_samples', 'actions', 'seconds'))
        self.limits = dict(limits)
        for k, v in limits.items(): c.integer(v, 1)
        need(limits['seconds'] <= 86400, 'finite operator invocation interval')
        self.used = {k: 0 for k in limits if k != 'seconds'}
        self.clock, self.origin = clock, clock()
        self.end = self.origin + limits['seconds']

    def charge(self, key, n):
        c.integer(n)
        need(self.clock() < self.end, 'original invocation deadline')
        need(key in self.used and self.used[key] + n <= self.limits[key], 'prospective ' + key + ' budget')
        self.used[key] += n

    def tick(self): self.charge('read_bytes', 0)


class IO(c.FileIO):
    def __init__(self, roots, budget):
        self.roots = [c.absolute(str(p)) for p in roots]
        self.budget, self.used, self.accesses = budget, 0, []

    def charge(self, n):
        self.budget.charge('read_bytes', n)
        self.used += n

    def capture(self, desc, role, cap=CAP):
        need(Path(desc['path']).name.casefold() not in ('assessment.json','train.json','validation.json'),'protected body requires its source-owned explicit release path')
        return super().capture(desc, role, cap)

    def capture_training(self, desc, cap=CAP):
        need(Path(desc['path']).name=='TRAIN.json','only explicitly scoped original final training')
        return super().capture(desc,'authorized_current_fold_training',cap)

    def capture_assessment(self, desc, cap=CAP):
        need(Path(desc['path']).name=='assessment.json','literal separately released original assessment')
        return super().capture(desc,'post_freeze_protected_assessment',cap)

    def create(self, path, body):
        need(type(body) is bytes and 0 < len(body) <= CAP, 'bounded immutable output bytes')
        self.budget.charge('write_bytes', len(body))
        p = self.checked(path)
        need(p.parent.is_dir(), 'precreated ordinary output parent')
        directory=parent_fd(p)
        try:fd = os.open(p.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400,dir_fd=directory)
        except BaseException:os.close(directory);raise
        try:
            todo = memoryview(body)
            while todo:
                self.budget.tick()
                n = os.write(fd, todo[:65536])
                need(n > 0, 'complete create-only artifact')
                todo = todo[n:]
            os.fsync(fd)
            a=os.fstat(fd);named=p.lstat()
            need(stat.S_ISREG(a.st_mode)and a.st_nlink==1 and a.st_size==len(body)and all(getattr(a,k)==getattr(named,k)for k in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns','st_nlink')),'published bytes remain at selected ordinary path')
        except BaseException:
            os.close(directory);raise
        finally: os.close(fd)
        try: os.fsync(directory)
        finally: os.close(directory)
        return {'path': str(p), **pin(body)}

    def directory(self, path):
        p = self.checked(path)
        self.budget.tick()
        parent=parent_fd(p)
        try:
            os.mkdir(p.name,mode=0o700,dir_fd=parent)
            anchored=os.stat(p.name,dir_fd=parent,follow_symlinks=False);named=p.lstat()
            need(stat.S_ISDIR(anchored.st_mode)and all(getattr(anchored,k)==getattr(named,k)for k in ('st_dev','st_ino','st_mode')),'created directory remains in selected namespace')
            os.fsync(parent)
        finally:os.close(parent)
        return p

    def incoming(self, path, role, cap=CAP):
        p = self.checked(path)
        s = p.lstat()
        need(stat.S_ISREG(s.st_mode) and s.st_nlink == 1 and 0 < s.st_size <= cap, 'bounded unlinked worker response')
        self.charge(s.st_size + 1)
        directory=parent_fd(p)
        try:fd = os.open(p.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,dir_fd=directory)
        except BaseException:os.close(directory);raise
        try:
            a = os.fstat(fd)
            fields = ('st_dev','st_ino','st_mode','st_size','st_nlink','st_mtime_ns','st_ctime_ns')
            need(all(getattr(a,k)==getattr(s,k) for k in fields), 'same selected worker response')
            body = os.read(fd, s.st_size + 1)
            z,named=os.fstat(fd),os.stat(p.name,dir_fd=directory,follow_symlinks=False)
            need(all(getattr(named,k)==getattr(p.lstat(),k)for k in fields),'same current selected namespace')
            need(len(body)==s.st_size and all(getattr(a,k)==getattr(z,k)==getattr(named,k) for k in fields), 'stable complete response')
            self.accesses.append({'path':str(p),'role':role,'bytes':len(body)})
            return body
        finally:
            os.close(fd);os.close(directory)


def close_output(io, root, body):
    return io.create(root, encoded(body))
