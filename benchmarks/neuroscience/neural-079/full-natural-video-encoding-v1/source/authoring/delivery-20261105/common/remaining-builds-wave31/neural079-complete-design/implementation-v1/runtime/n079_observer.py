"""Independent ordinary-file/cgroup observations and the one additive ledger.

Kernel attribution, application endpoint layers and logical retention remain
different estimands. No remote or device memory is invented by this observer.
"""
import hashlib
import os
import stat
from pathlib import PurePosixPath
from ach_resource_common import close_all
from ach_resource_readers import LocalReaders, key_values, inventory
from n079_common import require, fields, integer, identity, checked_pin, descriptor
from n079_budget_service import BudgetAuthority


def open_directory(path):
    require(type(path) is str and path.startswith('/') and str(PurePosixPath(path)) == path and
            '..' not in PurePosixPath(path).parts, 'canonical selected absolute directory')
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    first = None
    try:
        for name in PurePosixPath(path).parts[1:]:
            child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            old, fd = fd, child
            try:
                os.close(old)
            except BaseException as error:
                close_all([('acquired child directory', lambda: os.close(fd))], error); fd = None; raise
        result, fd = fd, None; return result
    except BaseException as error:
        first = error; raise
    finally:
        close_all([] if fd is None else [('directory ancestry descriptor', lambda: os.close(fd))], first)


def observed_file(context, directory_fd, item, work='observer', phase='scientific'):
    descriptor(item); fd = None; parent = None; error = None
    context.ledger.charge(work, {'data_read_bytes': item['bytes'] + 1}, 'independent full immutable file join', phase)
    try:
        parent = os.dup(directory_fd)
        parts = item['path'].split('/')
        for name in parts[:-1]:
            child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
            old, parent = parent, child; os.close(old)
        fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent)
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == item['bytes'],
                'complete ordinary single-link observation')
        h = hashlib.sha256(); count = 0
        while True:
            context.tick(phase); raw = os.read(fd, min(65536, item['bytes'] - count + 1))
            if not raw:
                break
            count += len(raw); require(count <= item['bytes'], 'observed file grew'); h.update(raw)
        after = os.fstat(fd)
        signature = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        require(signature(before) == signature(after) and count == item['bytes'] and h.hexdigest() == item['sha256'],
                'fresh full observed content, including zero-byte EOF')
        return {'object': dict(item), 'identity': list(signature(after)), 'observed_ns': context.tick(phase)}
    except BaseException as exc:
        error = exc; raise
    finally:
        close_all(([] if fd is None else [('observed file close', lambda: os.close(fd))]) +
                  ([] if parent is None else [('observed parent close', lambda: os.close(parent))]), error)


class ObserverService:
    def __init__(self, context, selected, endpoints):
        fields(selected, ('allocation', 'participants', 'reader_admission', 'baseline', 'baseline_admission',
                          'job_roots', 'output_file_limit', 'output_byte_limit', 'output_entry_limit', 'output_depth_limit'))
        require(integer(selected['output_entry_limit'], 1) >= integer(selected['output_file_limit'], 1) and
                integer(selected['output_depth_limit'], 1) <= 256, 'finite complete namespace traversal extents')
        checked_pin(selected['baseline_admission'])
        # The baseline is observed AFTER base deployment custody and BEFORE
        # population. Its detached admission is bound by the actual outer
        # release/gate/configuration chain, not recursively inside base custody.
        # bind_baseline below validates original clock/scope/raw observations.
        require(type(selected['baseline']) is dict, 'actual retained pre-population baseline record')
        self.context, self.selected, self.endpoints = context, selected, endpoints
        self.budget = BudgetAuthority(context, selected['allocation'], selected['participants'])
        context.require_effect('resource_read', 'observer')
        self.reader = None; self.jobs = {}; self.cost_prefixes = {}; self.closed = False
        try:
            self.reader = LocalReaders(selected['reader_admission'], context.profile, context.clock)
            self.reader.bind_baseline(selected['baseline'])
        except BaseException as error:
            self.close(error); raise

    def job(self, item):
        fields(item, ('job', 'stage_token', 'binding', 'process', 'cgroup', 'cgroup_identity', 'output',
                      'output_identity', 'observation', 'observation_identity', 'inventory', 'streams', 'result'))
        require(item['job'] not in self.jobs, 'one independent final observation per actual job')
        require(item['output'] == self.selected['job_roots']['output'] + '/' + item['job'] and
                item['cgroup'] == self.selected['job_roots']['cgroup'] + '/' + item['job'] and
                item['observation'] == self.selected['job_roots']['observation'] + '/_observation_' + item['job'],
                'actual source-owned context paths under admitted roots')
        result = item['result']
        require(result['natural_exit'] is True and result['exit_code'] == 0 and result['stream_eof'] is True and
                result['forced_stop'] is False and self.context.clock.origin <= result['finished_ns'] < self.context.clock.scientific,
                'trusted supervisor actual wait/EOF before original scientific cutoff')
        require(len(item['inventory']) <= integer(self.selected['output_file_limit'], 1) and
                sum(x['bytes'] for x in item['inventory']) <= integer(self.selected['output_byte_limit'], 1),
                'complete selected independent observation extents')
        require(sorted(x['path'] for x in item['streams']) == ['stderr.log', 'stdout.log'], 'both complete process streams')
        fds = []; error = None; record = {'request': item, 'files': [], 'streams': []}
        try:
            for name in ('cgroup', 'output', 'observation'):
                fd = open_directory(item[name]); fds.append((name, fd))
                st = os.fstat(fd)
                require([st.st_dev, st.st_ino] == item[name + '_identity'], 'same independently observed directory')
            cg, output, streams = [fd for _, fd in fds]
            def quiescent():
                self.context.ledger.charge('observer', {'source_read_bytes': self.context.profile['reader_limits']['file_bytes']},
                                          'actual cgroup events observation bound')
                fd = os.open('cgroup.events', os.O_RDONLY | os.O_NOFOLLOW, dir_fd=cg); first = None
                try:
                    from ach_resource_common import read_fd
                    raw = read_fd(fd, self.context.profile['reader_limits']['file_bytes'], self.context.clock, 'scientific')
                    require(key_values(raw).get('populated') == 0, 'all actual job descendants gone')
                    return raw.decode('ascii')
                except BaseException as exc:
                    first = exc; raise
                finally:
                    close_all([('job events descriptor', lambda: os.close(fd))], first)
            record['events_before'] = quiescent()
            require(len({x['path'] for x in item['inventory']}) == len(item['inventory']), 'unique complete output roster')
            # Enumerate every ordinary output name independently. Hashing only
            # a producer-chosen subset cannot establish a complete inventory.
            actual_names = []; entry_count = 0
            def names(fd, prefix='', depth=0):
                nonlocal entry_count
                require(depth <= self.selected['output_depth_limit'], 'selected complete namespace depth')
                iterator = os.scandir(fd); first = None
                try:
                    for entry in iterator:
                        self.context.tick(); entry_count += 1
                        require(entry_count <= self.selected['output_entry_limit'], 'selected whole namespace entries including directories')
                        st = entry.stat(follow_symlinks=False)
                        require(stat.S_ISDIR(st.st_mode) or stat.S_ISREG(st.st_mode), 'ordinary output tree only')
                        if stat.S_ISDIR(st.st_mode):
                            child = os.open(entry.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                            err = None
                            try:
                                names(child, prefix + entry.name + '/', depth + 1)
                            except BaseException as exc:
                                err = exc; raise
                            finally:
                                close_all([('output subdirectory', lambda: os.close(child))], err)
                        else:
                            actual_names.append(prefix + entry.name)
                            require(len(actual_names) <= self.selected['output_file_limit'], 'complete inventory entry bound')
                except BaseException as exc:
                    first = exc; raise
                finally:
                    close_all([('output directory iterator', iterator.close)], first)
            names(output)
            require(sorted(actual_names) == sorted(x['path'] for x in item['inventory']), 'independent whole output membership')
            record['files'] = [observed_file(self.context, output, x) for x in item['inventory']]
            record['streams'] = [observed_file(self.context, streams, x) for x in item['streams']]
            record['events_after'] = quiescent()
            record['common_scope'] = self.reader.snapshot('scientific')
            record['evidence'] = identity(record, self.context.encoding_limits)
            self.context.journal.append('independent_actual_job', record)
            self.jobs[item['job']] = record
            return record
        except BaseException as exc:
            error = exc; exc.n079_prefix = record; raise
        finally:
            close_all([(name + ' observed directory', lambda fd=fd: os.close(fd)) for name, fd in reversed(fds)], error)

    def handle(self, operation, payload, actual_peer):
        if operation == 'job_observation':
            expected = self.context.admission['selection']['peers']['issuer']
            require(all(actual_peer[k] == expected[k] for k in ('pid', 'uid', 'gid')), 'issuer requests independent observations')
            return self.job(payload)
        if operation == 'bundle_budget_prefix':
            expected = self.context.admission['selection']['peers']['controller']
            require(all(actual_peer[k] == expected[k] for k in ('pid', 'uid', 'gid')), 'actual controller requests own pre-report budget record')
            fields(payload, ('bundle_id',))
            from n079_plan import bundles
            candidates = {b['id']: b for b in bundles()}; require(payload['bundle_id'] in candidates, 'one complete selected bundle')
            bundle = candidates[payload['bundle_id']]
            works = ['policy/' + bundle['policy_id'], 'training/' + bundle['id']] + [
                'query/%s/%d' % (bundle['id'], q) for q in bundle['query_ids']]
            ledger = self.budget.ledger
            record = {'schema': 'n079_observed_bundle_cost_prefix_v1', 'bundle_id': bundle['id'],
                'source_pin': self.context.source_pin, 'study_pin': self.context.effect_admission['study_pin'],
                'allocation_pin': self.context.effect_admission['allocation_pin'], 'work_ids': works,
                'local_attempted': {k: dict(ledger.local[k]) for k in works}, 'ledger_attempt_count': len(ledger.attempts),
                'observed_ns': self.context.tick(), 'future_report_included': False,
                'meaning': 'central attempted reservations; policy row is shared across signals, not a new per-bundle cost',
                'actual_billing_and_remote_resources': 'unknown_without_independent_external_evidence'}
            evidence = identity(record, self.context.encoding_limits)
            self.context.journal.append('observed_bundle_cost_prefix', {'record': record, 'evidence': evidence})
            self.cost_prefixes[evidence['sha256']] = record
            return {'record': record, 'evidence': evidence}
        if operation == 'retained_bundle_budget_prefix':
            expected = self.context.admission['selection']['peers']['issuer']
            require(all(actual_peer[k] == expected[k] for k in ('pid', 'uid', 'gid')), 'issuer-only actual cost-prefix join')
            fields(payload, ('evidence',)); checked_pin(payload['evidence'])
            record = self.cost_prefixes[payload['evidence']['sha256']]
            require(identity(record, self.context.encoding_limits) == payload['evidence'], 'same retained actual observer prefix')
            return {'record': record, 'evidence': payload['evidence']}
        if operation == 'snapshot':
            require(payload == {}, 'no caller-selected hidden resource scope')
            return {'kernel': self.reader.snapshot('scientific'), 'budget': self.budget.ledger.snapshot(),
                    'jobs': sorted(self.jobs), 'endpoints': self.endpoints.snapshot()}
        raise ValueError('unselected observer operation')

    def close(self, primary=None):
        if self.closed:
            return
        self.closed = True
        close_all([] if self.reader is None else [('local measurement reader', lambda: self.reader.close(primary))], primary)
