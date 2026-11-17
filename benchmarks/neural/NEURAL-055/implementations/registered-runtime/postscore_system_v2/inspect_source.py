"""Inspect the inactive current full postscore profile only; no scientific imports or dispatch."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import time

if sys.version_info < (3, 11):
    raise RuntimeError('Source inspection requires Python 3.11 or newer')

MANIFEST = {'bytes': 30217, 'sha256': 'd3ec37aeadf0cbcfd3fe74558558b8202aca8a34d22b0095df6b054b3aaba988'}
READ_LIMIT = 1111596
OUTPUT_LIMIT = 65536
SECONDS = 30
ENTRY_LIMIT = 256

def need(value, message):
    if not value:
        raise ValueError(message)

def identity(s):
    return (s.st_dev, s.st_ino, s.st_mode, s.st_nlink, s.st_size, s.st_mtime_ns, s.st_ctime_ns)

def close_owned(close, first):
    """Always attempt closure; preserve the original body and raw later error."""
    try:
        close()
    except BaseException as error:
        if first is None:
            return error
        first.__dict__.setdefault('cleanup_failures', []).append(error)
        first.add_note('Secondary close failure: ' + repr(error))
    return first

def pairs(rows):
    out = {}
    for k, v in rows:
        need(k not in out, 'duplicate source key')
        out[k] = v
    return out

class Inspection:
    def __init__(self, root):
        self.root = Path(root).absolute()
        self.deadline = time.monotonic() + SECONDS
        self.read_bytes = 0
        self.records = {}

    def tick(self):
        need(time.monotonic() < self.deadline, 'source inspection deadline')

    def capture(self, name, descriptor, mode):
        self.tick()
        p = self.root / name
        need(not any(x.is_symlink() for x in (p, *p.parents)), 'source aliases forbidden')
        s = p.lstat()
        need(stat.S_ISREG(s.st_mode) and s.st_nlink == 1, 'ordinary single-link source')
        need(stat.S_IMODE(s.st_mode) == mode, 'exact source permissions')
        n = descriptor['bytes']
        need(type(n) is int and 0 < n <= 1048576 and s.st_size == n, 'exact bounded source extent')
        need(self.read_bytes + n <= READ_LIMIT, 'source read allowance')
        self.read_bytes += n  # Reservation remains charged on failure.
        fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW)
        first = None
        raw = None
        try:
            need(identity(os.fstat(fd)) == identity(s), 'same source handle')
            chunks = []
            remaining = n
            while remaining:
                self.tick()
                chunk = os.read(fd, min(remaining, 65536))
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            raw = b''.join(chunks)
            need(identity(os.fstat(fd)) == identity(s), 'stable source handle')
        except BaseException as error:
            first = error
        finally:
            first = close_owned(lambda: os.close(fd), first)
        if first is not None:
            raise first
        need(len(raw) == n and hashlib.sha256(raw).hexdigest() == descriptor['sha256'], 'exact source body')
        need(identity(p.lstat()) == identity(s), 'stable source path')
        self.records[name] = identity(s)
        self.tick()
        return raw

    def inventory(self):
        need(not any(x.is_symlink() for x in (self.root, *self.root.parents)), 'source root aliases forbidden')
        files = set()
        directories = {}
        stack = [self.root]
        entries = 0
        while stack:
            self.tick()
            d = stack.pop()
            s = d.lstat()
            need(stat.S_ISDIR(s.st_mode), 'ordinary source directory')
            directories[str(d.relative_to(self.root))] = identity(s)
            it = os.scandir(d)
            first = None
            try:
                for entry in it:
                    entries += 1
                    need(entries <= ENTRY_LIMIT, 'finite source namespace')
                    s = entry.stat(follow_symlinks=False)
                    if stat.S_ISDIR(s.st_mode):
                        stack.append(Path(entry.path))
                    else:
                        need(stat.S_ISREG(s.st_mode) and s.st_nlink == 1, 'ordinary source namespace member')
                        files.add(str(Path(entry.path).relative_to(self.root)))
            except BaseException as error:
                first = error
            finally:
                first = close_owned(it.close, first)
            if first is not None:
                raise first
        return files, directories

    def run(self):
        raw = self.capture('SOURCE_DISCOVERY_MANIFEST.json', MANIFEST, 0o644)
        manifest = json.loads(raw, object_pairs_hook=pairs)
        need(set(manifest) == {'schema', 'files'} and manifest['schema'] == 'neural055-current-profile-discovery-source-v1', 'exact current profile source schema')
        rows = manifest['files']
        need(type(rows) is list and len(rows) == 128, 'complete current profile source support')
        names = set()
        expected_dirs = {'.'}
        for row in rows:
            need(type(row) is dict and set(row) == {'path','bytes','sha256','mode','role'}, 'closed source descriptor')
            name = row['path']
            need(type(name) is str, 'source path string')
            p = Path(name)
            need(not p.is_absolute() and '..' not in p.parts and str(p) == name and name not in names, 'canonical unique source member')
            names.add(name)
            expected_dirs.update(str(v) for v in p.parents)
        expected_files = names | {'SOURCE_DISCOVERY_MANIFEST.json', 'inspect_source.py'}
        files, directories = self.inventory()
        need(files == expected_files and set(directories) == expected_dirs, 'closed complete component namespace')
        wrapper = self.root / 'inspect_source.py'
        wrapper_stamp = identity(wrapper.lstat())
        need(stat.S_IMODE(wrapper.lstat().st_mode) == 0o644, 'ordinary installed wrapper mode')
        for row in rows:
            self.capture(row['path'], row, int(row['mode'], 8))
        for name, stamp in self.records.items():
            need(identity((self.root / name).lstat()) == stamp, 'complete source identity remained current')
        for name, stamp in directories.items():
            need(identity((self.root / name).lstat()) == stamp, 'complete directory identity remained current')
        need(identity(wrapper.lstat()) == wrapper_stamp, 'wrapper identity remained current')
        self.tick()
        return {'schema': 'neural055_current_profile_source_inspection_v1', 'task_id': 'NEURAL-055',
                'status': 'source_only', 'profile_source_files': 128, 'component_files': 130,
                'discovery_manifest': MANIFEST, 'inspection_read_bytes': self.read_bytes,
                'source_scope': {'participants':10, 'queries_per_participant':200, 'candidate_images':200,
                                 'query_repeat_mean':80, 'training_repeat_mean':4, 'cells':960, 'panels':96,
                                 'logical_phases':1920, 'reference_banks':150, 'reference_fits':8520, 'contrasts':32},
                'scope_basis': 'curated public full profile; new source identity, not measured execution',
                'scientific_qualification_gates_open':30, 'prospective_scientific_controls_unexecuted':48,
                'scientific_execution':False, 'scientific_inputs_opened':False, 'study_modules_imported':False,
                'native_qualified':False, 'scoring_authorized':False, 'submission_ready':False,
                'benchmark_count_delta':0, 'wrapper_authenticity': 'trusted installation/commit selection; not self-certified'}

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inspect', required=True, action='store_true')
    parser.parse_args(argv)
    inspector = Inspection(Path(__file__).absolute().parent)
    result = inspector.run()
    body = (json.dumps(result, sort_keys=True, allow_nan=False) + '\n').encode()
    need(len(body) <= OUTPUT_LIMIT, 'source inspection output bound')
    inspector.tick()
    written = sys.stdout.buffer.write(body)
    need(type(written) is int and written == len(body), 'complete source inspection output')
    sys.stdout.buffer.flush()
    inspector.tick()
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
