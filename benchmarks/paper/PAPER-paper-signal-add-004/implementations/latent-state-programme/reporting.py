"""Complete bounded report persistence, primitive arrays separate from JSON."""
from pathlib import Path
from core import encoded, need
from safe_io import write_array, new_json


def write(value, root, max_bytes):
    """Fresh output only; no completion marker until every required array exists."""
    import numpy as np
    need(type(max_bytes) is int and max_bytes > 0, 'Prospective report write allocation')
    root = Path(root)
    need(not root.exists() and not root.is_symlink(), 'Fresh complete report destination')
    root.mkdir()
    written, arrays = 0, []
    def visit(x):
        nonlocal written
        if isinstance(x, np.ndarray):
            path = root / ('array_' + str(len(arrays)).zfill(6) + '.npy')
            desc = write_array(path, np.ascontiguousarray(x), max_bytes-written)
            written += desc['bytes']
            arrays.append(desc)
            return {'$array': desc}
        if isinstance(x, np.generic):
            return visit(np.asarray(x))
        if type(x) is dict:
            need(all(type(k) is str for k in x), 'String-key report metadata')
            return {k: visit(v) for k, v in x.items()}
        if type(x) in (tuple, list):
            return [visit(v) for v in x]
        need(type(x) in (str, int, float, bool, type(None)), 'No object/pickle/callable report content')
        return x
    result = visit(value)
    manifest = {'schema': 'osl_program_report_v1', 'result': result, 'arrays': arrays,
                'scientific_qualification': False}
    need(written + len(encoded(manifest)) <= max_bytes, 'Report and completion metadata within allocation')
    completion = new_json(root/'REPORT.json', manifest)
    return {'completion': completion, 'bytes_written': written+completion['bytes'],
            'arrays': len(arrays), 'scientific_qualification': False}
