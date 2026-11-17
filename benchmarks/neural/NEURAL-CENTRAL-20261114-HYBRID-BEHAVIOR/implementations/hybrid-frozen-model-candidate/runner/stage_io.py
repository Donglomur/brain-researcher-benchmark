"""Owned, bounded stage I/O. No work occurs on import."""
import hashlib
import json
import os
from pathlib import Path
import selectors
import stat
import subprocess
import time


def need(ok, why):
    if not ok:
        raise ValueError(why)


def packed(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()


def identity(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def ordinary(path):
    path = Path(path)
    need(path.is_absolute() and '..' not in path.parts, 'absolute ordinary path')
    for p in (path, *path.parents):
        need(not p.is_symlink(), 'no source/output symlink ancestor')
    return path


class IO:
    """Counts explicit pipeline reads/writes, not stdlib/loader/pip internal I/O.

    Complete directory sizes and installed RECORDs independently constrain
    retained results. These are not a hard filesystem quota or RSS sandbox.
    """
    def __init__(self, root, limits, deadline):
        self.root, self.limits, self.deadline = Path(root), limits, deadline
        self.read_bytes = self.write_bytes = self.metadata_bytes = 0
        self.stages = []

    def check(self):
        need(time.monotonic() < self.deadline, 'original operation deadline')

    def read_file(self, path, cap):
        self.check(); path = ordinary(path)
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, 'rb') as f:
            a = os.fstat(f.fileno())
            need(stat.S_ISREG(a.st_mode) and a.st_nlink == 1 and a.st_size <= cap,
                 'ordinary complete admitted file')
            need(self.read_bytes + a.st_size <= self.limits['explicit_local_read_bytes'],
                 'local read admission')
            body = f.read(a.st_size + 1)
            self.read_bytes += len(body)
            b = os.fstat(f.fileno())
        stamp = lambda x: (x.st_dev, x.st_ino, x.st_size, x.st_mtime_ns, x.st_ctime_ns)
        need(stamp(a) == stamp(b) and len(body) == a.st_size, 'complete stable local read')
        return body

    def write_file(self, path, body, category='metadata'):
        self.check(); path = ordinary(path)
        need(path.is_relative_to(self.root), 'write within owned output')
        need(type(body) is bytes, 'exact bytes writer')
        if category == 'metadata':
            need(len(body) <= self.limits['single_metadata_bytes'], 'single metadata cap')
            need(self.metadata_bytes + len(body) <= self.limits['metadata_total_bytes'],
                 'total metadata cap')
            self.metadata_bytes += len(body)
        need(self.write_bytes + len(body) <= self.limits['private_total_bytes'],
             'explicit write admission')
        self.write_bytes += len(body)  # reserve before dispatch; never erase failed attempt
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'wb') as f:
            need(f.write(body) == len(body), 'whole output write')
            f.flush(); os.fsync(f.fileno())
        return identity(body)

    def retained_inventory(self, approved_aliases=None):
        approved_aliases = approved_aliases or {}
        rows, total = [], 0
        for directory, dirs, files in os.walk(self.root, followlinks=False):
            for name in dirs:
                p=Path(directory)/name
                if p.is_symlink():
                    need(p.is_relative_to(self.root/'owner-runtime-controls'), 'no output directory links')
                    rows.append({'path':str(p.relative_to(self.root)),
                                 'invented_fixture_link_unfollowed':os.readlink(p),'bytes':p.lstat().st_size})
                    total+=p.lstat().st_size
            for name in files:
                p = Path(directory) / name; s = p.lstat()
                if stat.S_ISLNK(s.st_mode):
                    rel = str(p.relative_to(self.root))
                    if p.is_relative_to(self.root/'owner-runtime-controls'):
                        rows.append({'path':rel,'invented_fixture_link_unfollowed':os.readlink(p),'bytes':s.st_size})
                        total+=s.st_size
                        continue
                    need(rel in approved_aliases and os.readlink(p) == approved_aliases[rel],
                         'only exact declared venv interpreter alias links')
                    need(p.resolve().is_relative_to(self.root / 'venv'), 'venv alias contained')
                    rows.append({'path': rel, 'alias': approved_aliases[rel], 'bytes': s.st_size})
                    total += s.st_size
                    continue
                need(stat.S_ISREG(s.st_mode) and s.st_nlink == 1, 'ordinary retained output')
                total += s.st_size
                need(total <= self.limits['private_total_bytes'], 'whole retained tree cap')
                rows.append({'path': str(p.relative_to(self.root)), 'bytes': s.st_size})
        need(total <= self.limits['private_total_bytes'], 'whole retained tree including fixture links cap')
        return {'files': rows, 'bytes': total, 'hashes': 'Separate native/runtime receipts; size inventory only.'}

    def tree_size(self):
        """Whole current extent without following any fixture/runtime symlink."""
        total=0
        for directory,dirs,files in os.walk(self.root,followlinks=False):
            for name in dirs:
                p=Path(directory)/name
                if p.is_symlink():total+=p.lstat().st_size
            for name in files:
                s=(Path(directory)/name).lstat()
                need(stat.S_ISREG(s.st_mode) or stat.S_ISLNK(s.st_mode),'finite ordinary or unfollowed-link output')
                total+=s.st_size
        return total

    def final_receipt(self,path,value):
        """Admit the closure artifact itself against final whole-tree retention.

        A missing/failed final receipt and any failed postwrite check are a
        nonzero operation. A pre-write COMPLETE status is never written if the
        complete projected tree including this receipt exceeds the cap.
        """
        before=self.tree_size()
        closure={'observed_tree_before_final_receipt_bytes':before,
                 'final_receipt_bytes':0,'projected_whole_tree_bytes':before,
                 'cap_bytes':self.limits['private_total_bytes'],
                 'prewrite_complete_extent_admission':True}
        value['retention_closure']=closure
        for _ in range(12):
            body=packed(value);n=len(body)
            if closure['final_receipt_bytes']==n:break
            closure['final_receipt_bytes']=n;closure['projected_whole_tree_bytes']=before+n
        else:raise ValueError('final receipt size fixed point failed')
        need(before+len(body)<=self.limits['private_total_bytes'],'whole retention including final receipt exceeds cap')
        need(self.tree_size()==before,'tree changed during final closure admission')
        receipt=self.write_file(path,body)
        need(self.tree_size()==before+len(body),'final complete retained-tree observation differs')
        return receipt

    def run_stage(self, name, argv, cwd, env, deadline):
        """Substage shares owned worker PGID; catches failures, kills/reaps child.

        No new session/group. The external owner retains the group watchdog.
        Raised/uncaptured tails stay unknown and can never establish success.
        """
        self.check(); need(deadline <= self.deadline, 'no reset of original deadline')
        need(name.isascii() and name.replace('-', '').isalnum(), 'finite stage name')
        out = self.root / ('stage-' + name); out.mkdir(mode=0o700)
        row = {'name': name, 'argv': argv, 'attempted': True, 'status': 'FAILED',
               'returncode': None, 'streams': {}, 'errors': [], 'same_owned_process_group': True}
        self.stages.append(row)  # attempt registered before Popen
        proc = selector = None; handles = {}; pipes = []; clean = False
        cap = self.limits['streams_each_bytes']
        try:
            proc = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    start_new_session=False)
            row['pid'] = proc.pid; selector = selectors.DefaultSelector()
            for label, pipe in (('stdout', proc.stdout), ('stderr', proc.stderr)):
                handles[label] = (out / (label + '.txt')).open('xb')
                pipes.append(pipe); os.set_blocking(pipe.fileno(), False)
                row['streams'][label] = {'returned': 0, 'retained': 0, 'eof': False,
                                         'overflow': False, 'closed': False}
                selector.register(pipe, selectors.EVENT_READ, label)
            while selector.get_map() or proc.poll() is None:
                self.check(); need(time.monotonic() < deadline, 'stage original deadline')
                for key, _ in selector.select(0.1):
                    label = key.data; s = row['streams'][label]
                    data = os.read(key.fileobj.fileno(), min(65536, cap - s['returned'] + 1))
                    s['returned'] += len(data)
                    if not data:
                        s['eof'] = True; selector.unregister(key.fileobj); continue
                    need(self.write_bytes + len(data) <= self.limits['private_total_bytes'], 'stage stream retention')
                    self.write_bytes += len(data)
                    need(handles[label].write(data) == len(data), 'stage stream write')
                    s['retained'] += len(data)
                    s['overflow'] = s['returned'] > cap
                    need(not s['overflow'], 'stage stream cap including retained one-byte probe')
                if not selector.get_map() and proc.poll() is None:
                    try: proc.wait(timeout=0.1)
                    except subprocess.TimeoutExpired: pass
            row['returncode'] = proc.returncode
            need(proc.returncode == 0, 'natural zero substage required')
            clean = True
        except BaseException as error:
            row['errors'].append({'type': type(error).__name__, 'message': str(error)[:1024]})
        finally:
            if proc is not None:
                try:
                    if proc.poll() is None:
                        proc.terminate()
                        try: proc.wait(timeout=2)
                        except subprocess.TimeoutExpired: proc.kill(); proc.wait(timeout=5)
                    row['reaped'] = proc.poll() is not None
                    row['returncode'] = proc.returncode
                except BaseException as error:
                    row['errors'].append({'cleanup': type(error).__name__})
            if selector is not None: selector.close()
            for pipe in pipes: pipe.close()
            for label, f in handles.items():
                try:
                    f.flush(); os.fsync(f.fileno()); f.close()
                    row['streams'][label]['closed'] = True
                except BaseException as error:
                    row['errors'].append({'stream_close': type(error).__name__})
            row['status'] = 'COMPLETE' if clean and not row['errors'] and all(
                s['closed'] and s['eof'] and not s['overflow'] for s in row['streams'].values()) else 'FAILED'
            # If the deadline prevents receipt write, the caller sees an unknown receipt.
            self.write_file(out / 'RESULT.json', packed(row))
        need(row['status'] == 'COMPLETE', 'stage failed: ' + name)
        return row
