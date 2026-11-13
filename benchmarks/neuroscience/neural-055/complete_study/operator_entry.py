"""Inspect the inactive exact S8 source only; no scientific imports or dispatch."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import time

MANIFEST = {'bytes': 16641, 'sha256': '1e3ec2628854c3038cc446a74e0bb29e786649ae2d84dbc17f69334529185bf9'}
README = {'bytes': 5908, 'sha256': 'bf201e2e233dfa28d1af487aac957e847e4a50f537f7f7cb25e8e00f40ae26aa'}
READ_LIMIT = 576685
OUTPUT_LIMIT = 65536
SECONDS = 30
ENTRY_LIMIT = 256

def need(value, message):
    if not value:
        raise ValueError(message)

def identity(s):
    return (s.st_dev, s.st_ino, s.st_mode, s.st_nlink, s.st_size, s.st_mtime_ns, s.st_ctime_ns)

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
        with os.fdopen(fd, 'rb') as f:
            need(identity(os.fstat(f.fileno())) == identity(s), 'same source handle')
            raw = f.read(n)
            need(identity(os.fstat(f.fileno())) == identity(s), 'stable source handle')
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
            with os.scandir(d) as it:
                for entry in it:
                    entries += 1
                    need(entries <= ENTRY_LIMIT, 'finite source namespace')
                    s = entry.stat(follow_symlinks=False)
                    if stat.S_ISDIR(s.st_mode):
                        stack.append(Path(entry.path))
                    else:
                        need(stat.S_ISREG(s.st_mode) and s.st_nlink == 1, 'ordinary source namespace member')
                        files.add(str(Path(entry.path).relative_to(self.root)))
        return files, directories

    def run(self):
        raw = self.capture('RUNTIME_SOURCE_MANIFEST.json', MANIFEST, 0o644)
        manifest = json.loads(raw, object_pairs_hook=pairs)
        need(set(manifest) == {'schema', 'files'} and manifest['schema'] == 'neural055-complete-runtime-source-v1', 'exact S8 source schema')
        rows = manifest['files']
        need(type(rows) is list and len(rows) == 78, 'complete S8 source support')
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
        expected_files = names | {'RUNTIME_SOURCE_MANIFEST.json', 'README.md', 'operator_entry.py'}
        files, directories = self.inventory()
        need(files == expected_files and set(directories) == expected_dirs, 'closed complete component namespace')
        wrapper = self.root / 'operator_entry.py'
        wrapper_stamp = identity(wrapper.lstat())
        need(stat.S_IMODE(wrapper.lstat().st_mode) == 0o644, 'ordinary installed wrapper mode')
        for row in rows:
            self.capture(row['path'], row, int(row['mode'], 8))
        self.capture('README.md', README, 0o644)
        for name, stamp in self.records.items():
            need(identity((self.root / name).lstat()) == stamp, 'complete source identity remained current')
        for name, stamp in directories.items():
            need(identity((self.root / name).lstat()) == stamp, 'complete directory identity remained current')
        need(identity(wrapper.lstat()) == wrapper_stamp, 'wrapper identity remained current')
        self.tick()
        return {'schema': 'neural055_complete_s8_source_inspection_v1', 'task_id': 'NEURAL-055',
                'status': 'source_only', 'original_source_files': 79, 'component_files': 81,
                'runtime_manifest': MANIFEST, 'inspection_read_bytes': self.read_bytes,
                'source_scope': {'participants':10, 'queries_per_participant':200, 'candidate_images':200,
                                 'query_repeat_mean':80, 'training_repeat_mean':4, 'cells':960, 'panels':96,
                                 'logical_phases':1920, 'reference_banks':150, 'reference_fits':8520, 'contrasts':32},
                'scope_basis': 'curated public S8 source; unchanged scientific code; not measured execution',
                'scientific_qualification_gates_open':30, 'prospective_scientific_controls_unexecuted':48,
                'scientific_execution':False, 'scientific_inputs_opened':False, 'study_modules_imported':False,
                'native_qualified':False, 'scoring_authorized':False, 'submission_ready':False,
                'benchmark_count_delta':0, 'wrapper_authenticity': 'trusted public commit/materializer selection; not self-certified'}

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inspect', required=True, action='store_true')
    parser.parse_args(argv)
    inspector = Inspection(Path(__file__).absolute().parent)
    result = inspector.run()
    body = (json.dumps(result, sort_keys=True, allow_nan=False) + '\n').encode()
    need(len(body) <= OUTPUT_LIMIT, 'source inspection output bound')
    inspector.tick()
    sys.stdout.buffer.write(body)
    sys.stdout.buffer.flush()
    inspector.tick()
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
