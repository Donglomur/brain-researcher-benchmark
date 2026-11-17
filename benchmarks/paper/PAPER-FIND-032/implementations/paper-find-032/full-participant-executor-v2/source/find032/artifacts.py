"""Actual bounded file transport and protected numerical collection definitions."""
import io
import json
from .core import Custody, Refusal, encode_json, read_exact, write_exact, relative_name
from .products import ProductKey, validate_matrix, require_complete_products, require_endpoint_products


def product_name(key):
    return relative_name('__'.join((key.participant, key.stimulus, key.pipeline,
                                   key.condition, key.score)) + '.npz')


def save_product(root_fd, key, array, axes, budget, custody, *, member_bytes):
    import numpy as np
    validate_matrix(array, *axes, confusion=key.score == 'confusion')
    if type(member_bytes) is not int or member_bytes <= 0:
        raise Refusal('explicit member output cap')
    # Numerical buffer/native peak is not qualified by the logical byte cap.
    local = Custody(custody)
    stream = io.BytesIO()
    with local.attempt('product serialize'):
        try:
            np.savez(stream, value=array, train_times=axes[0], test_times=axes[1])
            data = stream.getvalue()
            if len(data) > member_bytes:
                raise Refusal('serialized output exceeds preselected member cap')
            row = write_exact(root_fd, product_name(key), data, budget, local)
        except BaseException as error:
            if local.first is None:
                local.catch('product serialization/write', error)
        finally:
            local.close('product buffer close', stream.close)
        local.raise_first()
    return {'key': [key.participant, key.stimulus, key.pipeline, key.condition, key.score], **row}


def load_product(root_fd, row, budget, custody, *, member_bytes):
    import numpy as np
    if set(row) != {'key', 'name', 'bytes', 'sha256'} or len(row['key']) != 5:
        raise Refusal('exact product row required')
    key = ProductKey(*row['key'])
    if row['name'] != product_name(key) or type(row['bytes']) is not int or not 0 < row['bytes'] <= member_bytes:
        raise Refusal('product key/path/size mismatch')
    raw, captured = read_exact(root_fd, row['name'], row['bytes'], row['sha256'], budget, custody)
    local = Custody(custody)
    stream = io.BytesIO(raw)
    archive = directory = None
    with local.attempt('product decode'):
        try:
            # ZIP members are checked before NumPy allocation. This is a logical
            # bound, not a measured decompression/native-memory qualification.
            import zipfile
            directory = zipfile.ZipFile(stream)
            if len(directory.namelist()) != 3 or set(directory.namelist()) != {'value.npy', 'train_times.npy', 'test_times.npy'}:
                raise Refusal('exact NPZ members required')
            if sum(x.file_size for x in directory.infolist()) > member_bytes:
                raise Refusal('expanded NPZ extent exceeds cap')
            stream.seek(0)
            archive = np.load(stream, allow_pickle=False)
            axes = (archive['train_times'], archive['test_times'])
            value = archive['value']
            validate_matrix(value, *axes, confusion=key.score == 'confusion')
        except BaseException as error:
            if local.first is None:
                local.catch('product decode body', error)
        finally:
            if archive is not None:
                local.close('NPZ close', archive.close)
            if directory is not None:
                local.close('ZIP directory close', directory.close)
            local.close('product input buffer close', stream.close)
        local.raise_first()
    return key, value, axes, captured


def collect(root_fd, rows, budget, custody, *, member_bytes, endpoint='complete'):
    """Rows describe expected bytes; actual capture is always parent performed.

    A row does not attest the producer, execution, access arm, or native cost.
    Qualified execution/source binding is a separate still-open prerequisite.
    """
    keys = [ProductKey(*row['key']) for row in rows]
    if len(keys) != len(set(keys)):
        raise Refusal('duplicate product occurrence')
    require_endpoint_products(dict.fromkeys(keys), endpoint)
    products, captures, axes = {}, {}, None
    for row in rows:
        key, value, current, captured = load_product(root_fd, row, budget, custody, member_bytes=member_bytes)
        if axes is not None:
            import numpy as np
            if any(not np.array_equal(a, b) for a, b in zip(axes, current)):
                raise Refusal('collection actual time axes mismatch')
        axes = current
        products[key] = value
        captures[key] = captured
    return products, axes, captures


def numerical_agreement(candidate, reference, *, absolute_tolerance, endpoint='complete'):
    """Protected agreement diagnostic, not a qualified binary reward or truth oracle."""
    import numpy as np
    if type(absolute_tolerance) not in (int, float) or not np.isfinite(absolute_tolerance) or absolute_tolerance < 0:
        raise Refusal('preselected finite tolerance required')
    require_endpoint_products(candidate, endpoint); require_endpoint_products(reference, endpoint)
    rows = []
    for key in sorted(reference):
        a, b = candidate[key], reference[key]
        if a.shape != b.shape or not np.isfinite(a).all() or not np.isfinite(b).all():
            raise Refusal('complete finite candidate/reference join required')
        delta = float(np.max(np.abs(a-b)))
        rows.append({'key': [key.participant, key.stimulus, key.pipeline, key.condition, key.score],
                     'maximum_absolute_error': delta, 'within_tolerance': delta <= absolute_tolerance})
    return {'diagnostic_only': True, 'qualified_reward': None, 'all_cells_present': True, 'endpoint': endpoint,
            'tolerance': absolute_tolerance, 'products': rows,
            'scientific_conclusion': 'not inferred from significance or numerical agreement'}


def save_group(root_fd, group, budget, custody, *, member_bytes):
    import numpy as np
    rows = []
    def save(name, arrays):
        local = Custody(custody)
        stream = io.BytesIO()
        with local.attempt('group serialization'):
            try:
                np.savez(stream, **arrays)
                raw = stream.getvalue()
                if len(raw) > member_bytes:
                    raise Refusal('group member exceeds preselected cap')
                row = write_exact(root_fd, name, raw, budget, local)
            except BaseException as error:
                if local.first is None:
                    local.catch('group serialization/write', error)
            finally:
                local.close('group buffer close', stream.close)
            local.raise_first()
        rows.append(row)
    for index, (name, values) in enumerate(group.family.items()):
        if name in group.structural:
            # Preserve actual subject differences without manufacturing t/p/nulls.
            save('group_comparison_' + str(index).zfill(3) + '.npz',
                 {'subject_values': values, 'train_times': group.axes[0], 'test_times': group.axes[1]})
            continue
        c = group.clusters[name]
        masks = np.stack(c['clusters']) if c['clusters'] else np.empty((0, *values.shape[1:]), dtype=bool)
        save('group_comparison_' + str(index).zfill(3) + '.npz',
             {'subject_values': values, 't': c['t'], 'cluster_masks': masks,
              'cluster_p': c['p'], 'null_max': c['null_max'],
              'train_times': group.axes[0], 'test_times': group.axes[1]})
    for index, (name, values) in enumerate(group.bayes.items()):
        save('group_BF10_' + str(index) + '.npz',
             {'BF10': values, 'train_times': group.axes[0], 'test_times': group.axes[1]})
    save('group_oof_confusion.npz', {'value': group.confusion,
         'train_times': group.axes[0], 'test_times': group.axes[1]})
    rows.append(write_exact(root_fd, 'GROUP_INDEX.json', encode_json({
        'comparisons': tuple(group.family), 'BF10_names': tuple(group.bayes),
        'policy': group.policy, 'unavailable': group.unavailable,
        'structural_controls': group.structural, 'products': rows}), budget, custody))
    return rows
