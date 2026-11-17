"""Read the complete original C1--D1 output panel, without fitting any model.

The source filenames and shapes come from Zenodo record 20128462. This is an
operator-side calibration reader: filenames do not authenticate how scores were
produced, and this reader does not grant a candidate a scientific win.
"""
from __future__ import annotations

import hashlib
import io
from pathlib import Path

import numpy as np


SESSION_UNITS = {
    'p1_1': 33, 'p1_2': 39, 'p2_1': 19, 'p2_2': 22,
    'p3_1': 38, 'p3_2': 55, 'p4_1': 66, 'p5_1': 45,
    'p5_2': 37, 'p6_1': 17, 'p7_1': 25, 'p7_2': 22,
    'p8_1': 82, 'p8_2': 67,
}

SOURCE_FILES = {
    'population': 'C1_explained_r_normalize_mean_vicuna7b.npy',
    'unit': 'D1_explained_r_indiv_vicuna7b.npy',
    'time_shuffle': 'C1_explained_r_normalize_mean_vicuna7b_by_time_shuffle.npy',
    'random_token': 'C1_explained_r_vicuna7b_random_token_randtok.npy',
    'sentence_swap': 'C1_explained_r_normalize_mean_swap_sentence_vicuna7b.npy',
    **{f'ngram{n}': f'C2_explained_r_vicuna7b_{n}gram.npy'
       for n in (1, 3, 5, 7, 10)},
    'sem_syn': 'C3_explained_r_sem_syn_exclude_oov.npy',
    'sem_syn_shuffle': 'C3_explained_r_sem_syn_exclude_oov_shuffle.npy',
    'word2vec': 'C3_explained_r_word2vec_exclude_oov.npy',
    'word2vec_shuffle': 'C3_explained_r_word2vec_exclude_oov_shuffle.npy',
    'syn': 'C3_explained_r_syn.npy',
    'syn_shuffle': 'C3_explained_r_syn_shuffle.npy',
}


def shapes(session):
    """Literal author per-session layouts, including 1-D control arrays."""
    return {
        'population': (40, 33), 'unit': (SESSION_UNITS[session], 40, 33),
        'time_shuffle': (40, 33), 'random_token': (33,),
        'sentence_swap': (33,),
        **{f'ngram{n}': (33,) for n in (1, 3, 5, 7, 10)},
        **{f + suffix: (3, 1) for f in ('sem_syn', 'word2vec', 'syn')
           for suffix in ('', '_shuffle')},
    }


def validate_panel(panel):
    if list(panel) != list(SESSION_UNITS):
        raise ValueError('Complete original ordered fourteen-session roster required')
    for session, fields in panel.items():
        if set(fields) != set(SOURCE_FILES):
            raise ValueError(f'{session}: all sixteen original fields are required')
        for field, expected in shapes(session).items():
            array = fields[field]
            if not isinstance(array, np.ndarray) or array.shape != expected:
                raise ValueError(f'{session}/{field}: expected shape {expected}')
            if array.dtype.kind != 'f' or array.dtype.itemsize not in (4, 8):
                raise ValueError(f'{session}/{field}: float32/64 correlations required')
            if np.isinf(array).any() or np.any(np.abs(array[np.isfinite(array)]) > 1):
                raise ValueError(f'{session}/{field}: invalid correlation')
    return panel


def load_panel(result_llm_root):
    """Read all 224 files, hashing the same bytes decoded as pickle-free NPY.

    Extra unrelated author results may coexist in the root; no missing file is
    replaced by a combined array or inferred value. Undefined Pearson values
    remain NaN and are handled explicitly by downstream reductions.
    """
    root = Path(result_llm_root).resolve(strict=True)
    panel, receipts = {}, []
    for session in SESSION_UNITS:
        panel[session] = {}
        for field, filename in SOURCE_FILES.items():
            relative = Path(session) / filename
            path = root / relative
            if path.is_symlink() or not path.is_file() or path.resolve().parent != root / session:
                raise ValueError(f'{relative}: ordinary source file required')
            expected = shapes(session)[field]
            limit = int(np.prod(expected)) * 8 + 65536
            with path.open('rb') as stream:
                raw = stream.read(limit + 1)
            if len(raw) > limit:
                raise ValueError(f'{relative}: file exceeds expected geometry bound')
            stream = io.BytesIO(raw)
            version = np.lib.format.read_magic(stream)
            readers = {(1, 0): np.lib.format.read_array_header_1_0,
                       (2, 0): np.lib.format.read_array_header_2_0}
            if version not in readers:
                raise ValueError(f'{relative}: supported NPY header required')
            shape, fortran, dtype = readers[version](stream, max_header_size=65536)
            if shape != expected or dtype.kind != 'f' or dtype.itemsize not in (4, 8):
                raise ValueError(f'{relative}: wrong NPY header geometry/type')
            count = int(np.prod(expected))
            if len(raw) != stream.tell() + count * dtype.itemsize:
                raise ValueError(f'{relative}: missing or trailing bytes')
            array = np.frombuffer(raw, dtype=dtype, count=count,
                                  offset=stream.tell()).reshape(shape, order='F' if fortran else 'C')
            panel[session][field] = array
            receipts.append({'path': relative.as_posix(), 'bytes': len(raw),
                             'sha256': hashlib.sha256(raw).hexdigest()})
    validate_panel(panel)
    return panel, receipts
