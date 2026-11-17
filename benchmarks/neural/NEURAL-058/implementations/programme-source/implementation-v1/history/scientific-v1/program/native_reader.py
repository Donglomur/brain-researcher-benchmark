"""Operator-only literal-source-equivalent C=1 projection; never mounted to agents.

Imports numerical/HDF dependencies only inside selected preparation. Original
brainsets are never deserialized by candidate code. Full native parity is an
independent qualification, not established by this source implementation.
"""
import hashlib
import os
import stat
from contextlib import contextmanager
from core import need, integer, finite, stamp, parent_chain, close_preserving, cleanup_preserving


def versions(expected):
    import importlib.metadata
    for name, version in expected.items():
        actual = importlib.metadata.version(name)
        need(actual == version, 'exact selected native distribution: '+name)


def hdf_headers(file, limits, budget):
    """Traverse metadata first; reject executable/foreign links and bound extents.

    Variable UTF8 strings are permitted only as bounded native metadata under
    the enclosing hard-memory qualification; their heap expansion is not
    inferred from HDF storage size. No object/reference arrays reach exports.
    """
    import h5py
    seen = set(); total = 0; objects = 0; variable_strings = 0
    def walk(group):
        nonlocal total, objects, variable_strings
        budget.tick()
        address = h5py.h5o.get_info(group.id).addr
        need(address not in seen, 'no HDF hard-link cycles/aliases'); seen.add(address)
        for name in group:
            budget.tick(); objects += 1
            need(objects <= limits['hdf_objects'], 'complete HDF object cap')
            need(type(name) is str and name not in ('','.', '..') and '/' not in name, 'HDF member name')
            need(type(group.get(name, getlink=True)) is h5py.HardLink, 'no soft/external HDF links')
            obj = group[name]
            if isinstance(obj, h5py.Group):
                if 'object' in obj.attrs:
                    need(obj.attrs['object'] in ('Data','ArrayDict','Interval','RegularTimeSeries','IrregularTimeSeries'), 'fixed Data class dispatcher')
                walk(obj); continue
            need(isinstance(obj, h5py.Dataset) and not obj.is_virtual, 'ordinary HDF dataset')
            shape = obj.shape; need(shape is not None and len(shape) <= 8, 'bounded HDF rank')
            count = 1
            for n in shape:
                need(type(n) is int and n >= 0, 'HDF ordinary shape'); count *= n
                need(count <= limits['array_elements'], 'HDF preallocation element cap')
            dtype = obj.dtype
            need(dtype.fields is None and h5py.check_dtype(ref=dtype) is None, 'no compound/reference datasets')
            if dtype.hasobject:
                text = h5py.check_string_dtype(dtype)
                need(text is not None and text.encoding in ('utf-8','ascii'), 'only variable string metadata')
                variable_strings += count
                need(variable_strings <= limits['variable_strings'], 'bounded string cardinality with external memory enforcement')
                extent = count * limits['max_string_bytes']
            else:
                need(dtype.kind in 'fiubSU', 'primitive HDF datatype')
                extent = count * dtype.itemsize
            total += extent; need(total <= limits['expanded_original_bytes'], 'complete original expanded reservation')
    walk(file)
    budget.reserve_read(total)
    return {'declared_expanded_reservation': total, 'objects': objects,
            'variable_string_elements': variable_strings,
            'physical_io_and_native_heap_requires_external_qualification': True}


@contextmanager
def original(path, expected, limits, budget):
    """Same-open full hash before and after native projection; no unpickling."""
    from core import descriptor
    expected = descriptor(expected); need(expected['bytes'] <= limits['original_raw_bytes'], 'original raw bound')
    path = parent_chain(path); budget.reserve_read(expected['bytes']+1)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    stream = None; file = None
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_mode & 0o222 == 0
             and before.st_size == expected['bytes'], 'sealed ordinary original')
        def digest():
            os.lseek(fd, 0, os.SEEK_SET); h = hashlib.sha256(); left = expected['bytes']
            while left:
                budget.tick(); raw = os.read(fd, min(left, 1 << 20)); need(raw, 'short original')
                h.update(raw); left -= len(raw)
            need(not os.read(fd, 1) and h.hexdigest() == expected['sha256'], 'exact complete original content')
            need(stamp(os.fstat(fd)) == stamp(before) == stamp(os.lstat(path)), 'original descriptor and path custody')
        digest(); os.lseek(fd, 0, os.SEEK_SET)
        # closefd=False leaves the independently retained descriptor available
        # for the final hash and ensures every close is independently attempted.
        stream = os.fdopen(fd, 'rb', closefd=False)
        import h5py
        file = h5py.File(stream, 'r')
        accounting = hdf_headers(file, limits, budget)
        from torch_brain.data import Data
        data = Data.from_hdf5(file, lazy=False)
        budget.tick()
        yield data, accounting
        budget.reserve_read(expected['bytes']+1); digest(); budget.tick()
    finally:
        failures = []
        import sys
        primary = sys.exception()
        for resource in (file, stream):
            if resource is not None:
                try: resource.close()
                except BaseException as error: failures.append(error)
        try: os.close(fd)
        except BaseException as error: failures.append(error)
        if failures:
            raise BaseExceptionGroup('original operation/independent cleanup', ([primary] if primary else [])+failures)


def primitive(value, kind, shape=None):
    import numpy as np
    x = np.asarray(value)
    need(x.dtype.kind in kind and not x.dtype.hasobject, 'native primitive array')
    if shape is not None: need(x.shape == tuple(shape), 'complete native shape')
    if x.dtype.kind == 'f': need(bool(np.isfinite(x).all()), 'finite original primitive')
    return x


def intervals(value):
    import numpy as np
    a = primitive(value.start, 'fi'); b = primitive(value.end, 'fi', a.shape)
    need(a.ndim == 1 and bool(np.all(b > a)) and bool(np.all(a[1:] >= b[:-1])),
         'complete finite sorted disjoint nonpoint interval support')
    return a, b


def anatomy(data, limits):
    import numpy as np
    units = data.units; n = len(units)
    need(0 < n <= limits['units'], 'complete all-unit support')
    raw_locations = np.asarray(units.location,dtype='<f8')
    need(raw_locations.shape == (n,3) and not bool(np.isinf(raw_locations).any()), 'full anatomy; missing coordinates explicitly retained')
    missing = np.isnan(raw_locations)
    locations = np.where(missing,0.,raw_locations)
    regions = []
    for value in units.region_beryl:
        if isinstance(value, bytes): value = value.decode('utf-8')
        if value is None or isinstance(value,float) and np.isnan(value): value = '<MISSING>'
        need(isinstance(value,str) and 0 < len(value.encode()) <= limits['max_string_bytes'], 'bounded original region metadata')
        regions.append(str(value))
    need(len(regions) == n, 'one region per original unit')
    return locations, missing, regions


def task_context(data, trial_id):
    import numpy as np
    indices = primitive(data.trials.trial_index, 'iu')
    match = np.flatnonzero(indices == trial_id); need(len(match) == 1, 'unique original trial row')
    i = int(match[0])
    # Only exogenously assigned task covariates; no choice/RT/outcome fields.
    keys = ('stimulus_side','stimulus_contrast','block_prior')
    result=[]
    for name in keys:
        values=np.asarray(getattr(data.trials,name)); need(values.dtype.kind in 'fiu', 'primitive assigned context')
        value=float(values[i]); need(not np.isinf(value), 'no infinite context')
        result.append(None if np.isnan(value) else value)
    return result


def iter_windows(data, role, limits, budget):
    """Concrete full original intersection/TrialSampler and trailing readout.

    role is source/evaluation. Source train and val intervals are both retained
    as a labeled source corpus; source-animal CV is applied later. Evaluation
    uses only original test intervals. No other evaluation wheel is exported.
    """
    import numpy as np
    from torch_brain.samplers import TrialSampler
    need(role in ('source','evaluation'), 'original corpus role')
    A0 = finite(float(data.absolute_start))
    move = data.task_aligned_intervals.movement_window
    ma, mb = intervals(move); mids = primitive(move.trial_index, 'iu', ma.shape)
    intervals(data.task_aligned_intervals.domain); intervals(data.wheel.domain)
    splits = ('pretrain_train_domain','pretrain_val_domain') if role == 'source' else ('ts1_test_domain',)
    locations, location_missing, regions = anatomy(data, limits)
    seen_windows = 0
    for split in splits:
        domain = getattr(data, split); intervals(domain)
        support = data.task_aligned_intervals.domain & domain & move & data.wheel.domain
        intervals(support)
        sampler = TrialSampler(sampling_intervals={'fixed': support}, shuffle=False)
        for index in sampler:
            budget.tick(); seen_windows += 1
            need(seen_windows <= limits['windows'], 'full window bound; no truncation')
            a, b = float(index.start), float(index.end)
            match = np.flatnonzero((ma <= a) & (mb >= b))
            need(len(match) == 1 and b>a, 'unique full original movement interval')
            k = int(match[0]); m = float(ma[k]); trial = int(mids[k])
            need(float(mb[k]) == m+1.0, 'original one-second movement-window construction')
            sample = data.slice(a, b)
            end = float(sample.domain.end[-1]); q = end-1.0
            target = sample.slice(q, end) if q > 1e-6 else sample
            times = primitive(target.wheel.timestamps, 'f').astype('<f8')
            velocity = primitive(target.wheel.wheel_vel, 'f').reshape(-1)
            speed = primitive(target.wheel.wheel_speed, 'f').reshape(-1)
            need(0 < len(times) <= limits['timestamps'] and velocity.shape == speed.shape == times.shape,
                 'all original target positions, no empty or reshaped support')
            need(bool(np.all(np.diff(times) > 0)) and bool(np.array_equal(speed, np.abs(velocity))), 'signed/absolute original readout join')
            physical_times = float(target.absolute_start) + times
            onset = A0+m
            relative_times = physical_times-onset
            need(bool(np.all((physical_times >= A0+a) & (physical_times < A0+b))), 'native grid belongs to original emitted support')
            # Spikes are sliced only to the original emitted interval. Target
            # extraction does not add any earlier context to the neural view.
            spike_times = primitive(sample.spikes.timestamps, 'f').astype('<f8') + float(sample.absolute_start)-onset
            unit_index = primitive(sample.spikes.unit_index, 'iu').astype('<i8')
            need(spike_times.shape == unit_index.shape and len(spike_times) <= limits['spikes'], 'complete spike-axis bound')
            need(bool(np.all((unit_index >= 0) & (unit_index < len(regions)))), 'original full unit indices')
            need(bool(np.all((spike_times >= a-m) & (spike_times < b-m))), 'no extra neural history')
            sa, sb = intervals(sample.spikes.domain)
            neural_domain = np.column_stack((sa,sb)).astype('<f8') + float(sample.absolute_start)-onset
            yield {'source_split': split, 'source_trial': trial, 'source_onset': m,
                   'A0': A0, 'native_target_origin': float(target.absolute_start),
                   'support': np.array([a-m,b-m], dtype='<f8'), 'times': relative_times,
                   'velocity': velocity, 'speed': speed,
                   'spike_times': spike_times, 'spike_units': unit_index,
                   'neural_domain': neural_domain, 'locations': locations,
                   'location_missing': location_missing, 'regions': regions, 'context': task_context(data, trial)}
    need(seen_windows > 0, 'required original session has no emitted windows')
