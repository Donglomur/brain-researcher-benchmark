"""Authenticate and execute the unchanged parent from exact captured bytes."""
import importlib
import importlib.util
import os
from pathlib import Path
import sys
import types
from paper_i_central_safety import need, pin, parse, descriptor, ordinary, relative, fsync_dir, cleanup

PARENT_SCHEMA = 'paper_i_executable_source_manifest_v1'
PARENT_COUNT = 38
PARENT_BYTES = 437883
PARENT_MANIFEST = {'bytes': 6012, 'sha256': '198aff81c325e3cd56414dbff3e6af5bcc1161995196abb94370340b9a3a2e12'}


def capture_parent(io, root, manifest_path, manifest_pin):
    need(manifest_pin == PARENT_MANIFEST, 'Exact accepted parent manifest')
    raw = io.read(manifest_path, descriptor(manifest_pin), 1048576)
    document = parse(raw)
    need(document.get('schema') == PARENT_SCHEMA and document.get('task') == 'PAPER-FIND-REP-014',
         'Parent manifest identity')
    rows = document['files']
    need(type(rows) is list and len(rows) == PARENT_COUNT, 'All38 unchanged runtime members')
    files, bodies = {}, {}
    root = ordinary(root)
    for row in rows:
        need(type(row) is dict and set(row) == {'path','bytes','sha256'}, 'Exact source entry')
        name = relative(row['path'])
        need(name not in files, 'Unique parent source path')
        expected = descriptor({k: row[k] for k in ('bytes','sha256')})
        need(expected['bytes'] <= 1048576, 'Bounded source file')
        files[name] = expected
        bodies[name] = io.read(root/name, expected, max(1, expected['bytes']), allow_empty=True)
    need(sum(p['bytes'] for p in files.values()) == document['bytes'] == PARENT_BYTES,
         'Exact full parent source extent')
    return {'root': root, 'manifest': dict(manifest_pin), 'manifest_raw': raw,
            'files': files, 'bodies': bodies}


def clone_parent(io, bundle, root):
    root = io.mkdir(root)
    directories = {root}
    for name, raw in sorted(bundle['bodies'].items()):
        target = root/relative(name)
        for directory in reversed(target.parent.parents):
            if directory == root or root in directory.parents:
                if directory not in directories:
                    io.mkdir(directory)
                    directories.add(directory)
        if target.parent not in directories:
            io.mkdir(target.parent)
            directories.add(target.parent)
        need(io.save(target, raw, 0o444) == bundle['files'][name], 'Exact cloned source pin')
    need(io.save(root/'EXECUTABLE_SOURCE_MANIFEST.json', bundle['manifest_raw'], 0o444) == bundle['manifest'],
         'Exact cloned manifest')
    for directory in sorted(directories, key=lambda p: len(p.parts), reverse=True):
        os.chmod(directory, 0o555)
        fsync_dir(directory)
    fsync_dir(root.parent)
    return root


def bootstrap(bundle, root):
    """Only stdlib top-level imports; no parent dependency or run yet."""
    need(pin(bundle['bodies']['supervisor.py']) == bundle['files']['supervisor.py'],
         'Executed bootstrap uses authenticated bytes')
    module = types.ModuleType('_paper_i_central_parent_bootstrap')
    module.__file__ = str(ordinary(root)/'supervisor.py')
    exec(compile(bundle['bodies']['supervisor.py'], module.__file__, 'exec', dont_inherit=True), module.__dict__)
    return module


class LoadedParent:
    def __init__(self, bundle, root):
        self.bootstrap = bootstrap(bundle, root)
        self.loader, self.roots = self.bootstrap._captured_loader(root, bundle['bodies'], bundle['files'])
        need(not any(n.split('.')[0] in self.roots for n in sys.modules), 'No ambient parent modules')
        self.context = {'loader': self.loader, 'manifest_pin': bundle['manifest'],
                        'manifest_raw': bundle['manifest_raw'], 'files': bundle['files'],
                        'bodies': bundle['bodies'], 'purpose': 'central_observer_metadata_only'}
        self.active = False
        try:
            sys.meta_path.insert(0, self.loader)
            self.active = True
            spec = self.loader.find_spec('supervisor')
            supervisor = importlib.util.module_from_spec(spec)
            supervisor._SOURCE_CONTEXT = self.context
            sys.modules['supervisor'] = supervisor
            self.loader.exec_module(supervisor)
            self.modules = {name: importlib.import_module(name) for name in
                            ('supervisor','core','planner','budget','operation')}
            self.modules.update(manifest=dict(bundle['manifest']), files=dict(bundle['files']))
            self.verify()
        except BaseException as error:
            cleanup(error, [('captured_loader.close', self.close)])
            raise

    def verify(self):
        need(self.active and self.loader in sys.meta_path, 'Captured source loader remains installed')
        return self.loader.verify()

    def close(self):
        if self.active:
            if self.loader in sys.meta_path:
                sys.meta_path.remove(self.loader)
            for name, module in list(self.loader.modules.items()):
                if sys.modules.get(name) is module:
                    sys.modules.pop(name)
            self.active = False
