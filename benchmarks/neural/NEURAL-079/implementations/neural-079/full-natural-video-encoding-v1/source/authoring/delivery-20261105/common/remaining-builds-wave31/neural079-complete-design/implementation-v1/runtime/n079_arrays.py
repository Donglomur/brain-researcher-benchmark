"""Concrete bounded binary/HDF5 I/O. No file, library or header access at import."""
import hashlib
import importlib
import math
import os
import stat
from n079_common import require, integer, fields, descriptor, checked_pin, close_all


def shape(value):
    require(type(value) is list and value and all(type(n) is int and n > 0 for n in value), 'positive complete shape')
    return tuple(value)


def matrix_descriptor(value):
    fields(value, ('object', 'shape', 'dtype', 'rows_pin', 'columns_pin', 'lineage_pin'))
    descriptor(value['object']); dims = shape(value['shape'])
    require(len(dims) == 2 and value['dtype'] in ('<f4', '<f8'), 'plain complete little-endian matrix')
    size = 4 if value['dtype'] == '<f4' else 8
    require(value['object']['bytes'] == math.prod(dims) * size, 'exact declared matrix byte extent')
    for key in ('rows_pin', 'columns_pin', 'lineage_pin'):
        checked_pin(value[key])
    return dims, size


def preflight(limits, rows, columns, slots):
    for key in ('max_rows', 'max_query_rows', 'max_columns', 'max_matrix_elements', 'max_live_float_slots'):
        integer(limits[key], 1)
    require(rows <= max(limits['max_rows'], limits['max_query_rows']) and columns <= limits['max_columns'] and
            rows * columns <= limits['max_matrix_elements'] and slots <= limits['max_live_float_slots'],
            'explicit preventive internal extent')


class MatrixReader:
    def __init__(self, context, repository, selected, limits, work_id):
        context.require_effect('array_read', work_id)
        self.context, self.repository, self.selected = context, repository, selected
        self.limits, self.work_id = limits, work_id
        self.shape, self.itemsize = matrix_descriptor(selected)
        self.fd = None; self.closed = False
        self.np = importlib.import_module('numpy')
        # MaterialRepository authenticates the full object, stable identity and
        # no-follow ancestry; no untrusted header is interpreted to size arrays.
        self.fd = repository.open(selected['object'])

    def block(self, row_indices, start, stop):
        require(not self.closed and type(row_indices) in (list, tuple) and row_indices,
                'open matrix and explicit nonempty ordered rows')
        require(len(set(row_indices)) == len(row_indices) and
                all(type(i) is int and 0 <= i < self.shape[0] for i in row_indices), 'unique admitted row positions')
        integer(start); integer(stop, 1)
        require(start < stop <= self.shape[1], 'complete bounded column interval')
        width = stop - start; count = len(row_indices)
        preflight(self.limits, count, width, 3 * count * width)
        amount = count * width * self.itemsize
        self.context.ledger.charge(self.work_id, {'data_read_bytes': amount, 'logical_float_slots': 3 * count * width},
                                   'matrix block read/conversion')
        out = self.np.empty((count, width), dtype=self.np.float64)
        for j, row in enumerate(row_indices):
            self.context.tick()
            raw = os.pread(self.fd, width * self.itemsize, (row * self.shape[1] + start) * self.itemsize)
            require(len(raw) == width * self.itemsize, 'full immutable matrix slice')
            out[j] = self.np.frombuffer(raw, dtype=self.selected['dtype'])
        require(self.np.isfinite(out).all(), 'finite matrix block')
        self.context.tick()
        return out

    def close(self, primary=None):
        if self.closed:
            return
        self.closed = True; fd, self.fd = self.fd, None
        close_all([] if fd is None else [('matrix descriptor', lambda: os.close(fd))], primary)


class RecordingReader:
    def __init__(self, context, repository, selected, limits, work_id):
        context.require_effect('recording_read', work_id)
        fields(selected, ('object', 'dataset', 'shape', 'dtype', 'trial_video_ids', 'trial_roster_pin',
                          'channel_pin', 'time_pin', 'schema_admission'))
        descriptor(selected['object'])
        require(selected['dataset'] == 'eeg' and selected['dtype'] == '<f4', 'source-selected EEG dataset/dtype')
        dims = shape(selected['shape'])
        require(len(dims) == 3 and dims[1:] == (127, 1800), 'full127x1800 EEG grid')
        require(type(selected['trial_video_ids']) is list and len(selected['trial_video_ids']) == dims[0] and
                all(type(i) is int and 1 <= i <= 1102 for i in selected['trial_video_ids']), 'complete trial/video join')
        for key in ('trial_roster_pin', 'channel_pin', 'time_pin', 'schema_admission'):
            checked_pin(selected[key])
        self.context, self.selected, self.limits, self.work_id = context, selected, limits, work_id
        self.fd = None; self.stream = None; self.file = None; self.closed = False
        self.np = importlib.import_module('numpy'); h5py = importlib.import_module('h5py')
        try:
            self.fd = repository.open(selected['object'])
            self.stream = os.fdopen(self.fd, 'rb', closefd=True); self.fd = None
            self.file = h5py.File(self.stream, 'r')
            node = self.file.get('eeg', getlink=True)
            require(isinstance(node, h5py.HardLink), 'no external/soft HDF5 dataset link')
            self.dataset = self.file['eeg']
            require(tuple(self.dataset.shape) == dims and self.dataset.dtype.str == '<f4', 'actual admitted HDF5 schema')
            self.shape = dims
        except BaseException as error:
            self.close(error); raise

    def block(self, start, stop):
        integer(start); integer(stop, 1)
        require(not self.closed and start < stop <= 127 * 1800, 'bounded complete EEG coordinate interval')
        first, last = start // 1800, (stop - 1) // 1800 + 1
        width = (last - first) * 1800
        preflight(self.limits, self.shape[0], width, self.shape[0] * width * 3)
        self.context.ledger.charge(self.work_id, {'data_read_bytes': self.shape[0] * width * 4,
            'logical_float_slots': self.shape[0] * width * 3}, 'HDF5 full-trial coordinate slab')
        self.context.tick()
        raw = self.dataset[:, first:last, :]
        require(raw.shape == (self.shape[0], last - first, 1800), 'complete HDF5 slab')
        result = raw.reshape(self.shape[0], width)[:, start - first * 1800:stop - first * 1800].astype('float64')
        require(self.np.isfinite(result).all(), 'finite authentic recording slab')
        self.context.tick(); return result

    def close(self, primary=None):
        if self.closed:
            return
        self.closed = True; ops = []
        for name in ('file', 'stream'):
            value = getattr(self, name, None); setattr(self, name, None)
            if value is not None:
                ops.append(('recording ' + name, value.close))
        fd, self.fd = getattr(self, 'fd', None), None
        if fd is not None:
            ops.append(('recording descriptor', lambda: os.close(fd)))
        close_all(ops, primary)


class MatrixWriter:
    def __init__(self, context, directory_fd, filename, rows, columns, dtype, limits, work_id, lineage):
        context.require_effect('array_write', work_id)
        require(type(filename) is str and filename not in ('', '.', '..') and '/' not in filename and '\\' not in filename,
                'one output filename')
        integer(rows, 1); integer(columns, 1); require(dtype in ('<f4', '<f8'), 'explicit storage dtype')
        self.context, self.work_id, self.limits = context, work_id, limits
        self.rows, self.columns, self.dtype = rows, columns, dtype
        self.itemsize = 4 if dtype == '<f4' else 8; self.bytes = rows * columns * self.itemsize
        self.lineage, self.filename = lineage, filename
        self.fd = None; self.parent = None; self.next_column = 0; self.closed = False
        self.quantization = {'nonzero_to_zero': 0, 'subnormal_output': 0, 'maximum_abs_value_rounded_to_zero': 0.0}
        self.np = importlib.import_module('numpy')
        context.reserve_storage(self.bytes, work_id)
        context.ledger.charge(work_id, {'write_bytes': self.bytes}, 'complete output logical extent before create')
        try:
            self.parent = os.dup(directory_fd)
            self.fd = os.open(filename, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=self.parent)
            os.ftruncate(self.fd, self.bytes)
            self.inode = (os.fstat(self.fd).st_dev, os.fstat(self.fd).st_ino)
        except BaseException as error:
            self.close(error); raise

    def append_columns(self, start, array):
        require(not self.closed and start == self.next_column and type(start) is int, 'consecutive full column writes')
        require(isinstance(array, self.np.ndarray) and array.ndim == 2 and array.shape[0] == self.rows,
                'complete all-row column block')
        width = array.shape[1]
        require(width > 0 and start + width <= self.columns, 'complete bounded block')
        preflight(self.limits, self.rows, width, 3 * self.rows * width)
        require(self.np.isfinite(array).all(), 'finite predictions/targets before canonical storage')
        stored = array.astype(self.dtype)
        require(self.np.isfinite(stored).all(), 'finite once-rounded canonical values')
        if self.dtype == '<f4':
            # Ordinary IEEE nearest-even finite underflow is disclosed, not
            # confused with a destroyed binary64 arithmetic denominator.
            zeros = (array != 0) & (stored == 0)
            self.quantization['nonzero_to_zero'] += int(self.np.count_nonzero(zeros))
            self.quantization['subnormal_output'] += int(self.np.count_nonzero((stored != 0) & (self.np.abs(stored) < self.np.finfo('float32').tiny)))
            if self.np.any(zeros):
                self.quantization['maximum_abs_value_rounded_to_zero'] = max(
                    self.quantization['maximum_abs_value_rounded_to_zero'], float(self.np.max(self.np.abs(array[zeros]))))
        for row in range(self.rows):
            self.context.tick(); raw = stored[row].tobytes(order='C'); position = (row * self.columns + start) * self.itemsize
            done = 0
            while done < len(raw):
                self.context.tick(); count = os.pwrite(self.fd, raw[done:], position + done)
                require(count > 0, 'complete array write'); done += count
        self.next_column += width

    def finish(self):
        require(not self.closed and self.next_column == self.columns, 'all coordinate columns written once')
        self.context.tick(); os.fsync(self.fd); os.fsync(self.parent)
        self.context.ledger.charge(self.work_id, {'data_read_bytes': self.bytes + 1}, 'full completed output identity and EOF')
        before = os.fstat(self.fd)
        digest = hashlib.sha256(); offset = 0
        while offset < self.bytes:
            self.context.tick(); raw = os.pread(self.fd, min(65536, self.bytes - offset), offset)
            require(raw, 'complete output identity read'); digest.update(raw); offset += len(raw)
        require(os.pread(self.fd, 1, self.bytes) == b'', 'exact completed output EOF')
        status = os.fstat(self.fd)
        require((before.st_mtime_ns, before.st_ctime_ns, before.st_size) == (status.st_mtime_ns, status.st_ctime_ns, status.st_size), 'stable complete output during identity read')
        require((status.st_dev, status.st_ino) == self.inode and status.st_size == self.bytes and
                stat.S_ISREG(status.st_mode) and status.st_nlink == 1, 'stable single-link complete output')
        record = {'object': {'path': self.filename, 'bytes': self.bytes, 'sha256': digest.hexdigest()},
                  'shape': [self.rows, self.columns], 'dtype': self.dtype, **self.lineage}
        matrix_descriptor(record)
        if self.dtype == '<f4':
            self.context.journal.append('canonical_f32_quantization', {'object': record['object'], 'diagnostics': self.quantization})
        self.close(); self.context.tick(); return record

    def close(self, primary=None):
        if self.closed:
            return
        self.closed = True; ops = []
        for name in ('fd', 'parent'):
            fd = getattr(self, name, None); setattr(self, name, None)
            if fd is not None:
                ops.append(('array writer ' + name, lambda fd=fd: os.close(fd)))
        close_all(ops, primary)


class RowFeatureWriter(MatrixWriter):
    """Full row-major feature output without concatenating all1102 rows."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.current_row = 0; self.current_column = 0

    def append_feature(self, row, start, values):
        require(not self.closed and row == self.current_row and start == self.current_column,
                'consecutive feature row/layer coverage')
        require(isinstance(values, self.np.ndarray) and values.ndim == 1, 'flat actual graph output')
        width = len(values)
        require(width > 0 and start + width <= self.columns and row < self.rows, 'bounded row-major feature extent')
        preflight(self.limits, 1, width, 3 * width)
        require(self.np.isfinite(values).all(), 'finite raw features')
        require(values.dtype.str == self.dtype, 'native feature dtype stored without an additional quantization policy')
        stored = values.astype(self.dtype)
        require(self.np.isfinite(stored).all(), 'finite exact feature storage')
        if self.dtype == '<f4':
            self.quantization['subnormal_output'] += int(self.np.count_nonzero((stored != 0) & (self.np.abs(stored) < self.np.finfo('float32').tiny)))
        raw = stored.tobytes(order='C')
        position = (row * self.columns + start) * self.itemsize; done = 0
        while done < len(raw):
            self.context.tick(); count = os.pwrite(self.fd, raw[done:], position + done)
            require(count > 0, 'complete row-major feature write'); done += count
        self.current_column += width
        if self.current_column == self.columns:
            self.current_row += 1; self.current_column = 0
        if self.current_row == self.rows:
            self.next_column = self.columns

    def append_columns(self, start, array):
        raise ValueError('row-major feature writer requires append_feature')
