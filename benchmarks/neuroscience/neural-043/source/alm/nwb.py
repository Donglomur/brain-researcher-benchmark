"""Explicit HDF5-backed NWB reader. No guessed paths, asset discovery or downloads.

The selected public code contains no NWB field producer. A future authenticated
mapping must bind the exact datasets, object IDs, row indices, clocks, units and
preprocessing support. This reader implements that mapping, not its provenance.
"""
import hashlib
import os
import stat
from pathlib import Path
from .contracts import require, finite, scalar_text, unique, digest
from .custody import Attempt

def _walk_hard(file, path):
    import h5py
    require(path.startswith('/') and '//' not in path and '..' not in path.split('/'), 'HDF path')
    obj = file
    for part in path.strip('/').split('/'):
        require(part not in ('', '.'), 'HDF path component')
        require(isinstance(obj.get(part, getlink=True), h5py.HardLink), 'external/soft HDF link')
        obj = obj[part]
    return obj

def _dataset(file, descriptor):
    import h5py
    obj = _walk_hard(file, descriptor['path'])
    require(isinstance(obj, h5py.Dataset), 'expected dataset')
    require(not obj.is_virtual and not obj.external, 'external/virtual dataset')
    require(list(obj.shape) == descriptor['shape'], 'shape differs from mapped extent')
    require(str(obj.dtype) == descriptor['dtype'], 'dtype differs')
    require(obj.size * obj.dtype.itemsize <= descriptor['max_bytes'], 'dataset budget')
    parent = _walk_hard(file, descriptor['owner_path'])
    require(scalar_text(parent.attrs['object_id']) == descriptor['owner_object_id'], 'object identity')
    return obj

def _column(file, d):
    x = _dataset(file, d)[()]
    require(len(x.shape) == 1, 'column must be one-dimensional')
    if d['kind'] == 'text':
        return [scalar_text(v) for v in x]
    if d['kind'] == 'integer':
        require(x.dtype.kind in 'iu', 'integer column dtype')
        return [int(v) for v in x]
    require(d['kind'] in ('number','time') and x.dtype.kind in 'fiu', 'numeric column')
    values=[finite(float(v)) for v in x]
    if d['kind']=='time':
        require(d['clock_evidence'] and d['output_unit']=='seconds', 'unproven affine clock transform')
        scale=finite(d['clock_scale']);offset=finite(d['clock_offset'])
        require(scale>0,'clock scale must be positive')
        values=[v*scale+offset for v in values]
    return values

def _table(file, mapping):
    columns = {k: _column(file, v) for k, v in mapping['columns'].items()}
    require(columns and len({len(v) for v in columns.values()}) == 1, 'table alignment')
    rows = [dict(zip(columns, v)) for v in zip(*columns.values())]
    unique([r[mapping['id_column']] for r in rows], 'table row ID')
    return rows

def load_recording(root, asset, mapping, budget):
    """Future authorized native caller; hashes opened bytes before NWB decoding.

    File object and HDF object each acquired into the same raw-error owner. The
    OS view must be an isolated immutable input mount; symlink components refused.
    """
    def operation(owner):
        import h5py
        import numpy as np
        p = Path(root).absolute()
        for part in Path(asset['path']).parts:
            p = p / part
            require(not p.is_symlink(), 'symlink source component')
        f = owner.own(open(p, 'rb', buffering=0), lambda: None)
        owner.resources[-1][1] = f.close
        st = os.fstat(f.fileno())
        require(stat.S_ISREG(st.st_mode) and st.st_size == asset['bytes'], 'file extent/type')
        require(st.st_size <= budget['file_bytes'], 'file exceeds admitted budget')
        h = hashlib.sha256()
        while True:
            b = f.read(1024 * 1024)
            if not b:
                break
            h.update(b)
        require(h.hexdigest() == asset['sha256'], 'source bytes differ')
        f.seek(0)
        nwb = h5py.File(f, 'r')
        owner.own(nwb, nwb.close)
        require(str(nwb.attrs['nwb_version']).startswith('2.'), 'NWB version')
        require(mapping['asset_sha256'] == asset['sha256'], 'mapping/source binding')
        require(mapping['digest']==digest({k:v for k,v in mapping.items() if k!='digest'}), 'mapping digest')
        require(mapping['source_unit'] == 'seconds' and mapping['distance_unit'] == 'micrometers', 'units')
        require(mapping['clock_evidence'] and mapping['roi_identity_evidence'], 'missing identity/clock evidence')
        require(scalar_text(_walk_hard(nwb, mapping['mouse_path'])[()]) == asset['mouse'], 'mouse differs')
        require(scalar_text(_walk_hard(nwb, mapping['session_path'])[()]) == asset['session'], 'session differs')
        result = {'mouse': asset['mouse'], 'session': asset['session'],
                  'asset_sha256': asset['sha256'], 'planes': [],
                  'trials': _table(nwb, mapping['trials']),
                  'stimuli': _table(nwb, mapping['stimuli']) if 'stimuli' in mapping else [],
                  'cell_links': mapping['cell_links'], 'targets': mapping['targets'],
                  'epoch_bounds': mapping['epoch_bounds'],
                  'grid': mapping['grid'], 'mapping_digest': mapping['digest']}
        total = 0
        for m in mapping['planes']:
            require(m['axis_order'] == ['time', 'roi'], 'unsupported/inferred neural axes')
            require(m['processing_support_evidence'], 'calcium causal support unverified')
            require(m['roi_qc_basis']=='segmentation_only' and m['roi_qc_evidence'], 'outcome-dependent ROI selection')
            rois = _table(nwb, m['roi_table'])
            region=_dataset(nwb,m['region_indices'])
            require(m['region_indices']['owner_path']==m['data']['owner_path'], 'ROI region not owned by response series')
            require('table' in region.attrs, 'DynamicTableRegion table reference missing')
            referred=nwb[region.attrs['table']]
            require(scalar_text(referred.attrs['object_id'])==m['roi_table']['object_id'], 'ROI table reference differs')
            indexes = _column(nwb, m['region_indices'])
            require(all(0 <= i < len(rois) for i in indexes), 'ROI region index')
            unique(indexes, 'ROI region index')
            selected_rois = [rois[i] for i in indexes]
            data = _dataset(nwb, m['data'])
            require(scalar_text(data.attrs['unit'])==m['source_data_unit'], 'neural source unit differs')
            require(float(data.attrs.get('conversion',1.0))==m['conversion'] and
                    float(data.attrs.get('offset',0.0))==m['offset'], 'neural scaling differs from source')
            require(len(data.shape) == 2 and data.shape[1] == len(indexes), 'ROI/data axis mismatch')
            total += data.size * data.dtype.itemsize
            require(total <= budget['array_bytes'], 'whole recording array budget')
            values = np.asarray(data[()], dtype='float64')
            require(np.isfinite(values).all(), 'nonfinite neural input')
            require(m['unit'] == 'dff' and m['conversion'] > 0, 'unsupported neural scaling')
            values = values * finite(m['conversion']) + finite(m['offset'])
            clocks = {k: np.asarray(_column(nwb, m[k]), dtype=float) for k in
                      ('exposure_start', 'exposure_end', 'support_start', 'support_end')}
            require(all(v.shape == (data.shape[0],) for v in clocks.values()), 'clock row mismatch')
            require(np.all(clocks['exposure_end'] >= clocks['exposure_start']), 'negative exposure')
            require(np.all(np.diff(clocks['exposure_start']) > 0), 'nonincreasing clock')
            require(np.all(clocks['support_start'] <= clocks['exposure_start']) and
                    np.all(clocks['support_end'] >= clocks['exposure_end']), 'support misses exposure')
            artifact = np.asarray(_column(nwb, m['artifact']), dtype=int)
            require(artifact.shape == (data.shape[0],) and set(artifact.tolist()) <= {0, 1}, 'artifact mask')
            movement = np.asarray(_column(nwb, m['movement']), dtype=float)
            require(movement.shape == artifact.shape and np.isfinite(movement).all(), 'frame movement clock')
            result['planes'].append({'id': m['plane_id'], 'epoch': m['epoch'],
                                     'roi': selected_rois, 'values': values,
                                     'artifact': artifact, 'movement': movement, **clocks})
        after = os.fstat(f.fileno())
        require((st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns) ==
                (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), 'source changed during read')
        return result
    attempt = Attempt()
    return attempt.run(operation)
