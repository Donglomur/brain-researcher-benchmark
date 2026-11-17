"""Owned producer artifacts and exact bounded product-index publication."""
import hashlib
import os
import stat
from n079_common import require, descriptor, pin, canonical, close_all


class ProducedRepository:
    """Source-owned closed outputs within one trusted producer, not public custody."""
    def __init__(self, context, original, directory_fd, work_id):
        self.context, self.original, self.work_id = context, original, work_id
        self.fd = os.dup(directory_fd); self.objects = {}; self.closed = False

    def register(self, value):
        descriptor(value); require('/' not in value['path'] and value['path'] not in self.objects, 'fresh owned output leaf')
        self.objects[value['path']] = dict(value)
        return value

    def open(self, value):
        descriptor(value)
        if value['path'] not in self.objects:
            return self.original.open(value)
        require(value == self.objects[value['path']] and not self.closed, 'same exact source-owned output')
        self.context.ledger.charge(self.work_id, {'data_read_bytes': value['bytes'] + 1}, 'full own closed output identity')
        fd = os.open(value['path'], os.O_RDONLY | os.O_NOFOLLOW, dir_fd=self.fd); error = None
        try:
            before = os.fstat(fd)
            require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == value['bytes'], 'complete ordinary owned output')
            h = hashlib.sha256(); total = 0
            while True:
                self.context.tick(); block = os.read(fd, min(65536, value['bytes'] - total + 1))
                if not block:
                    break
                total += len(block); require(total <= value['bytes'], 'owned output stable extent'); h.update(block)
            after = os.fstat(fd)
            require(total == value['bytes'] and h.hexdigest() == value['sha256'] and
                    (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
                    (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns), 'actual owned output body unchanged')
            os.lseek(fd, 0, os.SEEK_SET); result, fd = fd, None; return result
        except BaseException as exc:
            error = exc; raise
        finally:
            close_all([] if fd is None else [('owned output read descriptor', lambda: os.close(fd))], error)

    def close(self, primary=None):
        if self.closed:
            return
        self.closed = True; fd, self.fd = self.fd, None
        close_all([('own product directory', lambda: os.close(fd))], primary)


def write_index(context, directory_fd, value, work_id, name='RESULT_INDEX.json'):
    require('/' not in name and name not in ('', '.', '..'), 'one actual index leaf')
    raw = canonical(value, context.encoding_limits)
    context.reserve_storage(len(raw), work_id)
    context.ledger.charge(work_id, {'write_bytes': len(raw)}, 'full bounded product index before creation')
    context.tick(); fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400, dir_fd=directory_fd)
    error = None
    try:
        done = 0
        while done < len(raw):
            context.tick(); n = os.write(fd, raw[done:]); require(n > 0, 'complete producer index'); done += n
        os.fsync(fd); os.fsync(directory_fd); context.tick()
        return {'path': name, **pin(raw)}
    except BaseException as exc:
        error = exc; raise
    finally:
        close_all([('product index descriptor', lambda: os.close(fd))], error)


def read_index(context, repository, selected, work_id, phase='scientific'):
    descriptor(selected); require(selected['bytes'] <= context.encoding_limits['bytes'], 'bounded selected metadata extent')
    context.ledger.charge(work_id, {'source_read_bytes': selected['bytes'] + 1}, 'full input-index decode')
    fd = repository.open(selected); error = None
    try:
        chunks = []; total = 0
        while True:
            context.tick(phase); block = os.read(fd, min(65536, selected['bytes'] - total + 1))
            if not block:
                break
            chunks.append(block); total += len(block); require(total <= selected['bytes'], 'exact metadata extent')
        raw = b''.join(chunks)
        require(pin(raw) == {k: selected[k] for k in ('bytes', 'sha256')}, 'full metadata identity')
        from ach_resource_common import bounded_decode
        return bounded_decode(raw, context.encoding_limits)
    except BaseException as exc:
        error = exc; raise
    finally:
        close_all([('input-index descriptor', lambda: os.close(fd))], error)
