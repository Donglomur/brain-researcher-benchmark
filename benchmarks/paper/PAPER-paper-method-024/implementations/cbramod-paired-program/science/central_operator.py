"""Inactive CBraMod operator source API; no generic candidate execution authority.

inspect/coverage/compile/lineage validate source metadata only. Explicit typed
operator methods below can later perform data/native work; they are not invoked
by inspection, and this source integration supplies no execution qualification.
Use a dedicated single-thread operator process; dependency/runtime/immutable
mount/descendant/custody qualification remains external.
"""
import argparse
from contextlib import contextmanager
import hashlib
import importlib
import importlib.abc
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import stat
import sys

TASK = 'PAPER-paper-method-024'
FREEZE = {'bytes': 19337, 'sha256': '12c55529341eac2a906a18e8136bad6463962d2d42a78efd18fb26e39359461c'}
ROLE_COUNT = 103
SOURCE_BYTES = 483831
LOCK_SHA = 'a2d9560f7f520fdd364891f07ed3144fa74de5b1ceffd0575d5813f819ecd979'
STATIC_SHA = '84365a09bcfc3f098bc52bb528e8887e61f17af0a0375c15bc1e28e805a8d968'
CONDITIONS = ('current_source_reproduction', 'matched_support_re_evaluation')
ALIASES = {'contract': 'benchmark/public/contract.py',
           'arrays': 'benchmark/private/arrays.py', 'metrics': 'benchmark/private/metrics.py',
           'io_utils': 'benchmark/private/io_utils.py', 'score': 'benchmark/private/score.py'}


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def strict(body):
    def pairs(rows):
        out = {}
        for key, value in rows:
            need(key not in out, 'duplicate JSON key')
            out[key] = value
        return out
    return json.loads(body, object_pairs_hook=pairs,
                      parse_constant=lambda _: need(False, 'nonfinite JSON'))


def capture(path, cap, expected=None):
    path = Path(path).absolute()
    need('..' not in path.parts and not any(p.is_symlink() for p in (path, *path.parents)),
         'ordinary source/metadata ancestry')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        a = os.fstat(fd)
        need(stat.S_ISREG(a.st_mode) and a.st_nlink == 1 and 0 <= a.st_size <= cap,
             'bounded ordinary source/metadata file')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            body = stream.read(cap + 1)
        z, linked = os.fstat(fd), path.lstat()
        attrs = ('st_dev', 'st_ino', 'st_mode', 'st_nlink', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
        need(len(body) == a.st_size and all(getattr(a, k) == getattr(z, k) == getattr(linked, k)
                                          for k in attrs), 'stable complete source/metadata')
    finally:
        os.close(fd)
    if expected is not None:
        need(len(body) == expected['bytes'] and hashlib.sha256(body).hexdigest() == expected['sha256'],
             'source/metadata identity')
    return body


def selected(name):
    return name in ALIASES or any(name == prefix or name.startswith(prefix + '.')
                                 for prefix in ('benchmark', 'preprocessing_current'))


class CapturedFinder(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def __init__(self, root, bodies):
        self.rows = {}
        for relative, body in bodies.items():
            relative = relative.removeprefix('runtime/source/')
            path = PurePosixPath(relative)
            if path.suffix != '.py' or path.parts[0] not in ('benchmark', 'preprocessing_current'):
                continue
            package = path.name == '__init__.py'
            name = '.'.join(path.parts[:-1] if package else (*path.parts[:-1], path.stem))
            self.rows[name] = (body, str(root / relative), package)
        for alias, relative in ALIASES.items():
            self.rows[alias] = (bodies['runtime/source/' + relative], str(root / relative), False)
        for name in list(self.rows):
            parts = name.split('.')
            for n in range(1, len(parts)):
                package = '.'.join(parts[:n])
                self.rows.setdefault(package, (b'', str(root.joinpath(*parts[:n]) / '__init__.py'), True))

    def find_spec(self, fullname, path=None, target=None):
        if not selected(fullname):
            return None
        need(fullname in self.rows, 'unselected operator source module: ' + fullname)
        _, origin, package = self.rows[fullname]
        return importlib.util.spec_from_loader(fullname, self, origin=origin, is_package=package)

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        body, origin, package = self.rows[module.__name__]
        module.__file__ = origin
        if package:
            module.__path__ = [str(Path(origin).parent)]
        exec(compile(body, origin, 'exec', dont_inherit=True), module.__dict__)


class HostRuntime:
    """Typed source operator. Authentication is not scientific or data authority."""
    def __init__(self, root=None):
        self.root = Path(root if root is not None else Path(__file__).parent).absolute()
        self.source = self.root / 'runtime/source'
        self._active = False

    def verify_source(self):
        freeze = strict(capture(self.root / 'SOURCE_FREEZE.json', 65536, FREEZE))
        rows = freeze['roles']
        need(freeze['schema'] == 'cbramod_central_source_freeze_v1' and freeze['task_id'] == TASK
             and freeze['role_count'] == len(rows) == ROLE_COUNT
             and freeze['bytes'] == SOURCE_BYTES and freeze['all_inherited_bodies_unchanged'] is True,
             'complete selected source freeze')
        names = [r['path'] for r in rows]
        need(len(set(names)) == ROLE_COUNT and sum(r['bytes'] for r in rows) == SOURCE_BYTES,
             'exact selected source census')
        bodies = {}
        for row in rows:
            path = PurePosixPath(row['path'])
            need(path.as_posix() == row['path'] and not path.is_absolute() and '..' not in path.parts
                 and path.parts[:2] == ('runtime', 'source'), 'canonical mapped source path')
            bodies[row['path']] = capture(self.root / row['path'], 1048576, row)
        names = {PurePosixPath(n).relative_to('runtime/source') for n in names}
        directories = {PurePosixPath('.')}
        for name in names:
            directories.update(name.parents)
        for relative in directories:
            expected = {p.relative_to(relative).parts[0] for p in names if p.is_relative_to(relative)}
            entries = list((self.source / relative).iterdir())
            need(all(not p.is_symlink() for p in entries) and {p.name for p in entries} == expected,
                 'exact selected source tree without extra cache/body')
        return freeze, bodies

    @contextmanager
    def modules(self):
        # Scoped verified-source imports prevent disk .pyc and cached foreign
        # selected modules from bypassing the body pins. Not thread-safe by design.
        need(not self._active and not any(selected(n) for n in sys.modules),
             'dedicated operator process: fresh selected namespace required')
        _, bodies = self.verify_source()
        finder = CapturedFinder(self.source, bodies)
        old_path = sys.path[:]
        self._active = True
        sys.meta_path.insert(0, finder)
        try:
            yield bodies
        finally:
            sys.meta_path.remove(finder)
            for name in tuple(sys.modules):
                if selected(name):
                    del sys.modules[name]
            sys.path[:] = old_path
            self._active = False

    def _call(self, module, function, *args, **kwargs):
        with self.modules():
            return getattr(importlib.import_module(module), function)(*args, **kwargs)

    def inspect(self):
        with self.modules() as bodies:
            campaign = importlib.import_module('benchmark.native.campaign')
            panel = strict(bodies['runtime/source/benchmark/public/PANEL.json'])
            reports = [campaign.coverage(panel, purpose, reference)
                       for purpose, reference in (('reproduction', False), ('improvement', False), ('improvement', True))]
            return {'schema': 'cbramod_central_inspection_v1', 'id': TASK,
                    'status': 'source_only_inactive', 'source_roles': ROLE_COUNT,
                    'official_text_roles': 65, 'native_locked_roles': 59,
                    'primary_datasets': [d['id'] for d in panel['primary_downstream_datasets']],
                    'additional_source_dataset': 'BCIC-IV-2a',
                    'campaigns': [{'purpose': r['purpose'], 'reference': r['reference'],
                                   'required': r['required'], 'source_routed': r['source_routed'],
                                   'source_complete': r['source_complete']} for r in reports],
                    'evaluation_conditions': list(CONDITIONS),
                    'historical_published_scores': 'context_only_not_comparable_fixed_references',
                    'information_arms': ['paper_and_data', 'paper_data_official_code'],
                    'run': None, 'score': None, 'program_execution': None,
                    'admission': {k: False for k in ('runnable', 'source_complete', 'research_qualified',
                                                    'submission_ready', 'full_contract_complete')},
                    'scientific_payload_opened': False}

    def campaign_coverage(self, purpose='reproduction', reference=False):
        with self.modules() as bodies:
            panel = strict(bodies['runtime/source/benchmark/public/PANEL.json'])
            return importlib.import_module('benchmark.native.campaign').coverage(panel, purpose, reference)

    def bind_campaign(self, plans, purpose='reproduction', reference=False):
        with self.modules() as bodies:
            panel = strict(bodies['runtime/source/benchmark/public/PANEL.json'])
            return importlib.import_module('benchmark.native.campaign').bind_campaign(panel, plans, purpose, reference)

    def compile_producer(self, dataset_id, stage, bindings):
        return self._call('preprocessing_current.producer', 'compile_producer', dataset_id, stage, bindings, self.source / 'official')

    def stage_producer(self, plan, work_dir):
        return self._call('preprocessing_current.producer', 'stage_producer', plan, work_dir)

    def dispatch_producer(self, staged, python_executable, timeout_seconds, maximum_log_bytes, execution):
        return self._call('preprocessing_current.producer', 'dispatch', staged, python_executable,
                          timeout_seconds, maximum_log_bytes, execution)

    def row_lineage(self, dataset_id, split, source_keys, group_by_key):
        return self._call('preprocessing_current.observations', 'row_lineage', dataset_id, split, source_keys, group_by_key)

    def training_descriptor(self, lineage, prepared_root, inputs_root):
        return self._call('preprocessing_current.observations', 'training_descriptor', lineage, prepared_root,
                          'b9e961003214326972c567eff390e75b0287e32a', LOCK_SHA, inputs_root)

    def query_descriptor(self, observations, canonical_dataset_query, full_query_sha256, relative_owner):
        return self._call('benchmark.native.observations_bridge', 'query_descriptor', observations,
                          canonical_dataset_query, full_query_sha256, relative_owner)

    def export_observations(self, dataset_id, split, dataset, prepared_root, group_by_key, output_dir,
                            maximum_sample_bytes, maximum_total_bytes, maximum_metadata_bytes, execution):
        return self._call('preprocessing_current.observations', 'export_observations', dataset_id, split,
                          dataset, prepared_root, group_by_key, output_dir, maximum_sample_bytes,
                          maximum_total_bytes, maximum_metadata_bytes, execution)

    def validate_native_plan(self, plan):
        need(plan.get('official_source_sha256') == LOCK_SHA, 'selected native source lock')
        return self._call('benchmark.native.policy', 'validate_plan', plan)

    def dispatch_native(self, plan_path, expected_sha, inputs_root, output_root, log_path,
                        maximum_log_bytes, python_executable=sys.executable):
        body = capture(plan_path, 16 * 1048576)
        need(hashlib.sha256(body).hexdigest() == expected_sha, 'native plan identity')
        plan = strict(body)
        self.validate_native_plan(plan)
        return self._call('benchmark.native.dispatch', 'dispatch', plan_path, expected_sha,
                          self.source / 'official', inputs_root, output_root, log_path,
                          maximum_log_bytes, python_executable)

    def stage_view(self, view, output, cap=5000000):
        return self._call('benchmark.private.stage_view', 'stage', self.source, view, output, STATIC_SHA, cap)

    @staticmethod
    def _condition(condition, purpose):
        need(condition in CONDITIONS, 'explicit current-source or matched-support evaluation condition')
        need(purpose in ('reproduction', 'improvement'), 'declared artifact purpose')
        need(purpose != 'improvement' or condition == 'matched_support_re_evaluation',
             'improvement requires matched-support re-evaluation; historical copied scores are context only')

    def publish_targets(self, plan, plan_sha, source_root, output, cap, evaluation_condition):
        self._condition(evaluation_condition, plan['query']['purpose'])
        with self.modules() as bodies:
            panel = strict(bodies['runtime/source/benchmark/public/PANEL.json'])
            result = importlib.import_module('benchmark.private.prepare').publish(plan, plan_sha, source_root, output, panel, cap)
            return {'evaluation_condition': evaluation_condition, 'result': result,
                    'reference_comparability_verified': False, 'historical_superiority_claim': False}

    def grade_artifacts(self, candidate, query, artifact_root, load_private, evaluation_condition):
        self._condition(evaluation_condition, query['purpose'])
        with self.modules() as bodies:
            panel = strict(bodies['runtime/source/benchmark/public/PANEL.json'])
            result = importlib.import_module('benchmark.private.score').grade(candidate, query, panel, artifact_root, load_private)
            return {'evaluation_condition': evaluation_condition, 'result': result,
                    'reference_comparability_verified': False, 'historical_superiority_claim': False,
                    'note': 'Legacy query condition labels are not evidence of paper split parity or fair baselines.'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('inspect', 'coverage'))
    parser.add_argument('--purpose', choices=('reproduction', 'improvement'), default='reproduction')
    parser.add_argument('--reference', action='store_true')
    args = parser.parse_args(argv)
    host = HostRuntime()
    result = host.inspect() if args.operation == 'inspect' else host.campaign_coverage(args.purpose, args.reference)
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
