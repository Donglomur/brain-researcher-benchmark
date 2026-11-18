"""Minimal public decoder/entry; contains no author estimator or private store code.

The candidate implements predict(train_x, train_y, query_x, context). This module
is mounted independently of operator sources, under a declared information arm.
It is a format/transport helper, not an isolation implementation.
"""
from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import math
import struct
import sys
from pathlib import Path

import numpy as np

HEADER = struct.Struct('<8sIIQQQd16x')
MAX_ROWS, MAX_COLUMNS = 144111, 82


def need(ok, message):
    if not ok:
        raise ValueError(message)


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n').encode()


def parse(raw):
    def pairs(items):
        result = {}
        for k, v in items:
            need(k not in result, 'Duplicate JSON key')
            result[k] = v
        return result
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))


def feature(raw, rows, order):
    need(type(raw) is bytes and type(rows) is int and 2 <= rows <= MAX_ROWS
         and type(order) is bool, 'Primitive feature geometry')
    need(raw[:6] == b'\x93NUMPY' and raw[6:8] in (b'\x01\x00', b'\x02\x00'), 'Primitive NPY v1/v2 only')
    prefix = 10 if raw[6] == 1 else 12
    size = int.from_bytes(raw[8:prefix], 'little')
    need(1 <= size <= 8192 and prefix+size+rows*30*8 == len(raw), 'Exact bounded feature extent')
    header = ast.literal_eval(raw[prefix:prefix+size].decode('latin1'))
    need(type(header) is dict and set(header) == {'descr','shape','fortran_order'}
         and header['descr'] == '<f8' and type(header['shape']) is tuple
         and header['shape'] == (rows,30) and all(type(x) is int for x in header['shape'])
         and type(header['fortran_order']) is bool and header['fortran_order'] == order,
         'Exact source feature dtype/order/geometry')
    x = np.frombuffer(raw, dtype='<f8', offset=prefix+size).reshape((rows,30), order='F' if order else 'C')
    need(np.isfinite(x).all(), 'Finite source feature')
    return x


def unpack(raw, *, byte_limit, working_limit):
    need(type(byte_limit) is int and 64 <= byte_limit <= 128*1024**2
         and type(working_limit) is int and 1 <= working_limit <= 1024**3,
         'Finite decoder limits')
    need(type(raw) is bytes and 64 <= len(raw) <= byte_limit, 'Immutable bounded response bundle')
    magic, version, flags, rows, training, columns, held = HEADER.unpack_from(raw)
    need(magic == b'LCBNDL01' and version == 1 and flags == 0 and raw[48:64] == b'\0'*16,
         'Exact compact bundle header')
    need(2 <= rows <= MAX_ROWS and 1 <= training < rows and 1 <= columns <= MAX_COLUMNS
         and math.isfinite(held) and held == math.floor(held) and abs(held) < 2**53 and held < 99990,
         'Original nonempty source dimensions/held domain')
    need(len(raw) == 64+16*rows+8*training*columns, 'Exact bundle extent')
    need(8*len(raw)+128*rows+8192 <= working_limit, 'Decode workspace before NumPy')
    qid = np.frombuffer(raw, dtype='<f8', count=rows, offset=64)
    times = np.frombuffer(raw, dtype='<i8', count=rows, offset=64+8*rows)
    y = np.frombuffer(raw, dtype='<f8', count=training*columns, offset=64+16*rows).reshape(training,columns)
    need(np.isfinite(qid).all() and np.all(qid == np.floor(qid)) and np.all(np.abs(qid) < 2**53)
         and np.all(qid < 99990) and np.all(times >= 0) and np.all(times < MAX_ROWS)
         and np.all(times[1:] > times[:-1]) and np.isfinite(y).all(), 'Finite ordered original maps/Y')
    train, query = np.flatnonzero(qid != held), np.flatnonzero(qid == held)
    need(len(train) == training and len(query) == rows-training, 'Exact held equality membership')
    return rows, columns, held, qid, times, y, train, query


def operands(feature_raw, bundle_raw, descriptor_raw, *, byte_limit, working_limit):
    need(type(descriptor_raw) is bytes and 0 < len(descriptor_raw) <= 8192, 'Bounded public descriptor')
    descriptor = parse(descriptor_raw)
    need(encoded(descriptor) == descriptor_raw and type(descriptor) is dict
         and set(descriptor) == {'schema','context','features','response_maps','row_selection','prediction_shape'}
         and descriptor['schema'] == 'language-compact-selected-request/v1', 'Canonical exact descriptor')
    rows, columns, held, qid, times, y, train, query = unpack(
        bundle_raw, byte_limit=byte_limit, working_limit=working_limit)
    need(type(feature_raw) is bytes and 8*(len(bundle_raw)+len(feature_raw))+128*rows+65536 <= working_limit,
         'Joint callback workspace before feature view/copies')
    f, r, c = descriptor['features'], descriptor['response_maps'], descriptor['context']
    need(type(f) is dict and set(f) == {'sha256','bytes','format','dtype','shape','fortran_order'}
         and f['bytes'] == len(feature_raw) and f['sha256'] == hashlib.sha256(feature_raw).hexdigest()
         and f['format'] == 'npy' and f['dtype'] == '<f8' and f['shape'] == [rows,30]
         and type(f['fortran_order']) is bool, 'Authenticated one-feature assertion')
    need(r == {'schema':'language-permitted-response-maps-bundle/v1',
               'sha256':hashlib.sha256(bundle_raw).hexdigest(),'bytes':len(bundle_raw),
               'rows':rows,'training_rows':len(train),'output_columns':columns}, 'Exact response assertion')
    need(type(c) is dict and set(c) == {'session','field','family','layer','lag_index','lag_bins','held_qid'}
         and all(type(c[k]) is str and 0 < len(c[k]) <= 32 for k in ('session','field','family'))
         and all(type(c[k]) is int for k in ('layer','lag_index','lag_bins'))
         and type(c['held_qid']) is float and struct.pack('<d',c['held_qid']) == struct.pack('<d',held),
         'Bounded exact public context and held bits')
    need(descriptor['row_selection'] == 'original-order:qids!=held(train);qids==held(query)'
         and descriptor['prediction_shape'] == [len(query),columns], 'Original callback partition')
    x = feature(feature_raw,rows,f['fortran_order'])
    context = dict(c)
    context.update(train_time_indices=times[train].copy(), test_time_indices=times[query].copy(),
                   train_qid=qid[train].copy())
    return x[train].copy(), y.copy(), x[query].copy(), context


def bounded(path, cap):
    with open(path,'rb',buffering=0) as stream:
        raw = stream.read(cap+1)
    need(len(raw) <= cap, 'Input exceeds fixed bound')
    return raw


class PipeWriter:
    """Write-only NPY sink: avoid treating a pipe as a seekable real file."""
    __slots__ = ("_output",)

    def __init__(self, output):
        self._output = output

    def write(self, value):
        written = self._output.write(value)
        if type(written) is not int or written != len(value):
            raise OSError("incomplete NPY pipe write")
        return written

    def flush(self):
        return self._output.flush()


def main():
    need(len(sys.argv) == 3, 'Explicit bundle and logical work limits required')
    byte_limit, working_limit = map(int,sys.argv[1:])
    need(64 <= byte_limit <= 128*1024**2 and 1 <= working_limit <= 1024**3, 'Finite child limits')
    descriptor = bounded('/input/request.json',8192)
    feature_raw = bounded('/input/features.npy',MAX_ROWS*30*8+8192)
    bundle = bounded('/input/responses.bin',byte_limit)
    args = operands(feature_raw,bundle,descriptor,byte_limit=byte_limit,working_limit=working_limit)
    # Candidate import/call starts here; no trusted state can follow another request.
    output = PipeWriter(sys.stdout.buffer)
    sys.stdout = sys.stderr
    spec = importlib.util.spec_from_file_location('frozen_candidate','/candidate/candidate.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    prediction = module.predict(*args)
    need(type(prediction) is np.ndarray and prediction.dtype.kind == 'f'
         and prediction.dtype.itemsize in (4,8) and prediction.shape == (args[2].shape[0],args[1].shape[1])
         and np.isfinite(prediction).all(), 'Finite exact raw prediction geometry')
    np.save(output,prediction,allow_pickle=False)
    output.flush()


if __name__ == '__main__':
    main()
