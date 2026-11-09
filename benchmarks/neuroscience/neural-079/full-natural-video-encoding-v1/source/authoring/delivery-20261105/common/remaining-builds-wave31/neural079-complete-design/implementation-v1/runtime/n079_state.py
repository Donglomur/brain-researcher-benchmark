"""Concrete numeric state artifacts; no pickle, executable objects or score hooks."""
import dataclasses
import hashlib
import importlib
import os
from collections.abc import Mapping
from n079_common import require, token, pin, close_all, checked_pin
from n079_arrays import MatrixWriter, preflight


class StateStore:
    def __init__(self, context, directory_fd, limits):
        self.context, self.limits = context, limits
        self.directory_fd = os.dup(directory_fd)
        self.closed = False; self.records = {}; self.np = importlib.import_module('numpy')

    def put(self, work_id, name, array, lineage):
        require(not self.closed, 'open protected state store'); token(name)
        require(isinstance(array, self.np.ndarray) and array.dtype.kind in 'fbiu' and array.ndim >= 1,
                'plain numeric state array')
        require(array.size and name not in self.records, 'nonempty unique complete numeric state')
        rows = array.shape[0]; columns = array.size // rows
        preflight(self.limits, rows, columns, 4 * array.size + getattr(self.context, 'resident_numeric_slots', 0))
        require(self.np.isfinite(array).all(), 'finite complete numeric state')
        if array.dtype.kind in 'iu':
            require(all(abs(int(v)) <= 2**53 for v in array.flat), 'exact integer state remains exactly representable in binary64')
        # Numeric computation states are exactly binary64, boolean metadata is
        # represented numerically only with its original dtype explicitly kept.
        converted = array.reshape(rows, columns).astype('float64')
        from n079_common import identity
        metadata = {'rows_pin': identity({'shape': list(array.shape), 'row_axis': 0}, self.context.encoding_limits),
                    'columns_pin': identity({'remaining_shape': list(array.shape[1:])}, self.context.encoding_limits),
                    'lineage_pin': identity(lineage, self.context.encoding_limits)}
        writer = MatrixWriter(self.context, self.directory_fd, name + '.f64', rows, columns, '<f8',
                              self.limits, work_id, metadata)
        error = None
        try:
            writer.append_columns(0, converted); result = writer.finish()
        except BaseException as exc:
            error = exc; raise
        finally:
            writer.close(error)
        result['original_shape'] = list(array.shape); result['original_dtype'] = array.dtype.str
        self.records[name] = result
        return result

    def pack(self, work_id, name, value, lineage):
        """Source-owned recursive serialization, numeric bodies as raw artifacts.

        Does not invoke arbitrary object's reducers or a candidate-supplied
        serialization function. Full metadata serialization is separately bounded.
        """
        self.context.require_effect('numeric_state', work_id)
        token(name); count = 0
        def visit(item, depth):
            nonlocal count
            count += 1
            require(count <= self.context.encoding_limits['nodes'] and depth <= self.context.encoding_limits['depth'],
                    'bounded numeric-state object graph')
            if isinstance(item, self.np.ndarray):
                key = '%s-array%d' % (name, count)
                return {'numeric_array': self.put(work_id, key, item, lineage)}
            if dataclasses.is_dataclass(item) and not isinstance(item, type):
                item = {field.name: getattr(item, field.name) for field in dataclasses.fields(item)}
            if isinstance(item, Mapping):
                require(all(type(k) is str for k in item), 'plain named state mapping')
                return {k: visit(item[k], depth + 1) for k in sorted(item)}
            if type(item) in (tuple, list):
                return [visit(x, depth + 1) for x in item]
            if type(item) in (str, int, float, bool) or item is None:
                return item
            if isinstance(item, self.np.generic):
                return visit(item.item(), depth + 1)
            raise ValueError('unsupported numeric state type')
        result = visit(value, 0)
        self.context.journal.append('numeric_state', {'name': name, 'lineage': lineage, 'state': result})
        return result

    def close(self, primary=None):
        if self.closed:
            return
        self.closed = True; fd = self.directory_fd; self.directory_fd = None
        close_all([('protected state directory', lambda: os.close(fd))], primary)


def write_state(context, work_id, name, array, lineage):
    require(type(context.state_store) is StateStore and context.state_store.context is context,
            'actual selected owned state store')
    return context.state_store.put(work_id, name, array, lineage)


def digest_record(context, work_id, arrays, lineage):
    np = importlib.import_module('numpy')
    require(type(arrays) is dict and arrays, 'actual named numeric blocks')
    result = {}
    for name, array in sorted(arrays.items()):
        token(name)
        require(isinstance(array, np.ndarray) and array.ndim >= 1 and array.size and array.dtype == np.float64,
                'finite actual binary64 digest source')
        preflight(context.numeric_limits, array.shape[0], array.size // array.shape[0], 3 * array.size + getattr(context, 'resident_numeric_slots', 0))
        require(np.isfinite(array).all(), 'finite complete numeric digest after extent admission')
        context.ledger.charge(work_id, {'logical_float_slots': 2 * array.size}, 'canonical observed numeric block digest')
        contiguous = np.ascontiguousarray(array, dtype='<f8')
        digest = hashlib.sha256(); view = memoryview(contiguous).cast('B')
        for start in range(0, len(view), 65536):
            context.tick(); digest.update(view[start:start + 65536])
        result[name] = {'dtype': '<f8', 'shape': list(array.shape), 'bytes': len(view), 'sha256': digest.hexdigest()}
    return {'arrays': result, 'lineage': lineage,
            'retention': 'actual independent metric artifacts plus source/input/state reconstruction; numerical digests are not raw retained arrays'}
