"""N059 outer-owner accounting around the unchanged scientific durable I/O.

Only the owner process binds this module. Reference workers retain their original
scientific I/O in the separately declared native-managed scope. This module is
synchronous: one owner budget, one active operation, no nested managed body I/O.
"""
from pathlib import Path

from .donor.budget import Budget
from .donor.common import diagnostic_type
from .scientific import io as original
from .scientific.contracts import need, pin


_STATE = None


class _SourceState:
    def __init__(self, budget):
        self.budget = budget
        self.sequence = 0
        self.active = None
        self.records = []
        self.directories = {}
        self.original_errors = []

    def _row(self, kind, **facts):
        need(self.active is None, 'one synchronous managed scientific I/O operation')
        need(self.budget.active_cell is None, 'N059 owner I/O has no donor matched-cell limit reset')
        self.budget.admit('before N059 scientific ' + kind)
        self.sequence += 1
        row = {'operation': 'n059-scientific-io-%09d' % self.sequence,
               'kind': kind, 'status': 'admitting', 'entered_original': False,
               'settled': False, 'read_reserved_bytes': 0,
               'write_reserved_bytes': 0, 'regular_file_attempts': 0,
               'observed_successful_read_bytes': None,
               'observed_successful_write_bytes': None, **facts}
        self.records.append(row)
        self.active = row
        return row

    def _retain_error(self, row, error, *, uncertain):
        # The original object is retained before any potentially fallible formatting.
        self.original_errors.append((row['operation'], error))
        row['error_type'] = diagnostic_type(error)
        row['status'] = 'failed_after_original' if row['entered_original'] else 'admission_refused'
        if uncertain:
            self.budget.uncertain(row['operation'], 'managed_scientific_io_extent_or_custody', error,
                reason='original operation did not return complete checked evidence; full reservations retained',
                read_reserved_bytes=row['read_reserved_bytes'],
                write_reserved_bytes=row['write_reserved_bytes'])
        else:
            self.budget.admission_failures.append({'stage': row['operation'],
                'reason': 'managed scientific I/O admission/settlement boundary failed',
                'type': row['error_type']})

    def _fail(self, row, error):
        try:
            if row['entered_original'] and not row['settled'] and 'write_reservation' in row:
                # Unexpected accounting errors after the original method returns
                # must not release the operation's original safety reservation.
                # A partly charged known counter may coexist with this conservative
                # held capacity; the unknown record prevents treating it as exact.
                self.budget.reservations[row['write_reservation']] = {
                    'bytes': row['original_write_reservation_bytes'], 'files': 0}
                row['write_reserved_bytes'] = row['original_write_reservation_bytes']
                row['read_reserved_bytes'] = row['original_read_reservation_bytes']
                if 'read_limit_while_reserved' in row:
                    self.budget.limits['read_bytes'] = min(self.budget.limits['read_bytes'],
                                                         row['read_limit_while_reserved'])
            # Successful, settled I/O remains known even when the final deadline check fails.
            self._retain_error(row, error,
                uncertain=row['entered_original'] and not row['settled'])
            if row['settled']:
                row['status'] = 'complete_io_with_later_boundary_failure'
        except BaseException as secondary:
            self.budget.boundary_errors.append((row['operation'] + '-failure-custody', secondary))
            self.budget.admission_failures.append({'stage': row['operation'],
                'reason': 'failure custody also incomplete'})
        finally:
            self.active = None

    def constructor_cleanup(self, row, obj):
        """Close returned handles if only the wrapper's final boundary then fails."""
        try:
            obj.close()
            row['returned_handle_cleanup'] = 'original_close_method_returned'
        except BaseException as secondary:
            self.original_errors.append((row['operation'] + '-returned-handle-close', secondary))
            self.budget.boundary_errors.append((row['operation'] + '-returned-handle-close', secondary))
            row['returned_handle_cleanup'] = 'failed_unknown'

    def reserve_io(self, kind, *, path, write_bytes, read_bytes, create_file):
        need(type(write_bytes) is int and write_bytes >= 0
             and type(read_bytes) is int and read_bytes >= 0
             and type(create_file) is bool, 'finite managed operation extents')
        row = self._row(kind, path=str(path), original_write_reservation_bytes=write_bytes,
                        original_read_reservation_bytes=read_bytes)
        try:
            b = self.budget
            reservation = row['operation'] + '-write'
            b.reserve(reservation, write_bytes, int(create_file))
            row['write_reservation'] = reservation
            row['write_reserved_bytes'] = write_bytes
            # Reserve read capacity by narrowing the effective limit. Actual read
            # counters remain untouched until a complete original return. Original
            # immutable global_limits is never changed. No body budget operation is
            # nested in the inherited I/O methods.
            b.admit_read(read_bytes)
            old_limit = b.limits['read_bytes']
            row['read_limit_before'] = old_limit
            row['read_limit_while_reserved'] = old_limit - read_bytes
            row['read_counter_before'] = b.read_bytes
            b.limits['read_bytes'] = old_limit - read_bytes
            row['read_reserved_bytes'] = read_bytes
            if create_file:
                # Count one regular-file creation attempt before its O_CREAT call,
                # while leaving all write/live byte capacity reserved.
                b.admit_write(0, reservation=reservation)
                row['regular_file_attempts'] = 1
            b.check('after N059 scientific I/O reservation')
            return row
        except BaseException as error:
            self._fail(row, error)
            raise

    def reserve_directory(self, path):
        row = self._row('directory_create', path=str(path))
        try:
            name = row['operation'] + '-directory-inode'
            self.budget.reserve_capacity(name, 0, 1)
            row['directory_capacity'] = name
            row['directory_inode_reserved'] = 1
            self.budget.check('after N059 scientific directory reservation')
            return row
        except BaseException as error:
            self._fail(row, error)
            raise

    def begin_attach(self, path, expected):
        row = self._row('directory_attach', path=str(path))
        try:
            recorded = self.directories.get(str(path))
            need(recorded is not None and tuple(expected) == recorded['identity'],
                 'attach only this owner previously created exact directory inode')
            row['directory_capacity'] = recorded['capacity']
            row['directory_inode_reserved'] = 0
            return row
        except BaseException as error:
            self._fail(row, error)
            raise

    def enter(self, row):
        need(self.active is row and not row['entered_original'], 'one original I/O entry')
        row['entered_original'] = True
        row['status'] = 'original_in_progress'

    def directory_success(self, row, obj, *, attached=False):
        need(self.active is row and row['entered_original'], 'original directory returned')
        identity = tuple(obj.root_stamp)
        if attached:
            need(self.directories[str(obj.path)]['identity'] == identity,
                 'original attach returned exact owner inode')
        else:
            need(str(obj.path) not in self.directories, 'one original directory identity per owner path')
            self.directories[str(obj.path)] = {'identity': identity,
                'capacity': row['directory_capacity'], 'operation': row['operation']}
        obj._managed_state = self
        row['root_identity'] = list(identity)
        row['observed_successful_read_bytes'] = 0
        row['observed_successful_write_bytes'] = 0
        row['settled'] = True
        row['status'] = 'complete'
        # Directory inode capacity remains live after closing its descriptors;
        # neither class unlinks the directory, so no absence/refund is invented.
        self.budget.check('after original scientific directory custody')
        self.active = None

    def success(self, row, *, written, readback, receipt=None, created_file=False):
        need(self.active is row and row['entered_original'] and not row['settled'],
             'one original completed I/O settlement')
        need(type(written) is int and 0 <= written <= row['write_reserved_bytes']
             and type(readback) is int and 0 <= readback <= row['read_reserved_bytes'],
             'complete successful actual extents fit original reservations')
        b = self.budget
        need(b.limits['read_bytes'] == row['read_limit_while_reserved']
             and b.read_bytes == row['read_counter_before'],
             'no nested or asynchronous read-budget mutation during inherited I/O')
        reservation = b.reservations[row['write_reservation']]
        need(reservation == {'bytes': row['write_reserved_bytes'], 'files': 0},
             'unchanged owned write/live reservation and separately counted file attempt')
        # Original methods prove completed byte lengths by same-open readback and
        # custody checks. Original .written/.total are attempted extents and are
        # never treated as observed physical bytes here.
        b.written(written)
        reservation['bytes'] -= written
        row['observed_successful_write_bytes'] = written
        b.limits['read_bytes'] = row['read_limit_before']
        b.read(readback)
        row['observed_successful_read_bytes'] = readback
        del b.reservations[row['write_reservation']]
        row['released_write_reservation_slack'] = row['write_reserved_bytes'] - written
        row['released_read_reservation_slack'] = row['read_reserved_bytes'] - readback
        row['read_reserved_bytes'] = 0
        row['write_reserved_bytes'] = 0
        if created_file:
            need(row['regular_file_attempts'] == 1, 'matching original regular-file attempt')
            b.file_created()
            row['regular_file_creation_acknowledged'] = True
        row['receipt'] = receipt
        row['settled'] = True
        row['status'] = 'complete'
        b.check('after original scientific I/O complete settlement')
        self.active = None

    def snapshot(self):
        # Plain metadata only; original exception objects stay in private custody
        # and donor managed_failures rather than going through arbitrary repr/str.
        return {'schema': 'n059_owner_managed_scientific_io_v1',
                'scope': 'outer owner scientific durable file bodies and directory inode capacity',
                'records': [dict(row) for row in self.records],
                'active_operation': None if self.active is None else self.active['operation'],
                'pending_read_capacity_bytes': sum(row['read_reserved_bytes'] for row in self.records),
                'effective_read_limit': self.budget.limits['read_bytes'],
                'original_global_read_limit': self.budget.global_limits['read_bytes'],
                'confirmed_directory_count': len(self.directories),
                'directory_inode_capacity_count': sum(row.get('directory_inode_reserved', 0)
                                                       for row in self.records),
                'directory_custody': [{'path': path, 'identity': list(value['identity']),
                                      'capacity': value['capacity']} for path, value in self.directories.items()],
                'original_error_types': [{'operation': op, 'type': diagnostic_type(error)}
                                         for op, error in self.original_errors],
                'file_metadata_syscalls_and_filesystem_internal_io': 'outside managed body byte definition',
                'native_worker_io': 'separate selected native-managed scope; not intercepted here'}


def bind(budget):
    """Bind once, before constructing any owner scientific directory or journal."""
    global _STATE
    need(_STATE is None and type(budget) is Budget, 'one exact original owner Budget lifetime')
    need(budget.active_cell is None, 'owner budget is not a donor matched-cell scope')
    budget.admit('bind N059 owner scientific I/O')
    _STATE = _SourceState(budget)
    return _STATE


def state():
    need(_STATE is not None, 'owner scientific I/O budget bound before effects')
    return _STATE


class OwnedDirectory(original.OwnedDirectory):
    def __init__(self, path, max_bytes):
        owner = state()
        selected_path = Path(path).absolute()
        row = owner.reserve_directory(selected_path)
        returned = False
        try:
            owner.enter(row)
            super().__init__(path, max_bytes)
            returned = True
            owner.directory_success(row, self)
        except BaseException as error:
            owner._fail(row, error)
            if returned:
                owner.constructor_cleanup(row, self)
            raise

    @classmethod
    def attach(cls, path, max_bytes, expected):
        owner = state()
        selected_path = Path(path).absolute()
        row = owner.begin_attach(selected_path, expected)
        obj = None
        try:
            owner.enter(row)
            obj = super().attach(path, max_bytes, expected)
            owner.directory_success(row, obj, attached=True)
            return obj
        except BaseException as error:
            owner._fail(row, error)
            if obj is not None:
                owner.constructor_cleanup(row, obj)
            raise

    def write(self, name, body):
        need(type(body) is bytes, 'exact managed owned body')
        owner = self._managed_state
        need(owner is state(), 'same bound owner scientific directory')
        n = len(body)
        row = owner.reserve_io('owned_write', path=self.path / name,
                               write_bytes=n, read_bytes=n + 1, create_file=True)
        before_read = self.readback_bytes
        try:
            owner.enter(row)
            result = super().write(name, body)
            observed = self.readback_bytes - before_read
            need(result == pin(body) and observed == n, 'complete exact original owned-write return')
            owner.success(row, written=n, readback=observed, receipt=result, created_file=True)
            return result
        except BaseException as error:
            owner._fail(row, error)
            raise

    def read_exact(self, name, expected):
        need(type(expected) is dict and set(expected) == {'bytes', 'sha256'}
             and type(expected['bytes']) is int and expected['bytes'] >= 0,
             'finite exact managed owned-body descriptor')
        owner = self._managed_state
        need(owner is state(), 'same bound owner scientific directory')
        row = owner.reserve_io('owned_read_exact', path=self.path / name,
                               write_bytes=0, read_bytes=expected['bytes'] + 1, create_file=False)
        before_read = self.readback_bytes
        try:
            owner.enter(row)
            result = super().read_exact(name, expected)
            observed = self.readback_bytes - before_read
            need(type(result) is bytes and len(result) == expected['bytes']
                 and observed == len(result), 'complete exact original owned-read return')
            owner.success(row, written=0, readback=observed, receipt=pin(result))
            return result
        except BaseException as error:
            owner._fail(row, error)
            raise


class Journal(original.Journal):
    def __init__(self, directory, name, max_bytes):
        need(type(directory) is OwnedDirectory and directory._managed_state is state(),
             'owner journal uses the exact managed directory')
        owner = directory._managed_state
        row = owner.reserve_io('journal_create', path=directory.path / name,
                               write_bytes=0, read_bytes=0, create_file=True)
        returned = False
        try:
            owner.enter(row)
            super().__init__(directory, name, max_bytes)
            returned = True
            self._managed_state = owner
            self._managed_confirmed_bytes = 0
            owner.success(row, written=0, readback=0, created_file=True)
        except BaseException as error:
            owner._fail(row, error)
            if returned:
                owner.constructor_cleanup(row, self)
            raise

    def append(self, body):
        need(type(body) is bytes and body.endswith(b'\n'), 'whole managed journal record')
        owner = self._managed_state
        need(owner is state(), 'same bound owner journal')
        need(self.total == self._managed_confirmed_bytes, 'original journal has no unsettled prior append')
        n = len(body)
        row = owner.reserve_io('journal_append', path=self.directory.path / self.name,
                               write_bytes=n, read_bytes=n, create_file=False)
        before_read = self.directory.readback_bytes
        try:
            owner.enter(row)
            # This inherited method updates directory.written itself. It does not
            # call directory.write, so exactly one global wrapper settles this append.
            result = super().append(body)
            observed = self.directory.readback_bytes - before_read
            need(result == pin(body) and observed == n
                 and self.total == self._managed_confirmed_bytes + n,
                 'complete exact original journal-append return')
            owner.success(row, written=n, readback=observed, receipt=result)
            self._managed_confirmed_bytes += n
            return result
        except BaseException as error:
            owner._fail(row, error)
            raise

    def seal(self):
        owner = self._managed_state
        need(owner is state(), 'same bound owner journal')
        need(self.total == self._managed_confirmed_bytes, 'complete original prior append accounting before seal')
        row = owner.reserve_io('journal_seal', path=self.directory.path / self.name,
                               write_bytes=0, read_bytes=self._managed_confirmed_bytes, create_file=False)
        before_read = self.directory.readback_bytes
        try:
            owner.enter(row)
            result = super().seal()
            observed = self.directory.readback_bytes - before_read
            need(result['bytes'] == self._managed_confirmed_bytes and observed == self._managed_confirmed_bytes,
                 'complete original journal-seal body reread')
            owner.success(row, written=0, readback=observed, receipt=result)
            return result
        except BaseException as error:
            owner._fail(row, error)
            raise
