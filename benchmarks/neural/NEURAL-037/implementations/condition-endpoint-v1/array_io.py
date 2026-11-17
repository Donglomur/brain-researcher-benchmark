"""Bounded exact NPY files; object reconstruction is forbidden."""
import io as streams
from pathlib import Path
import os
import delivery_io as io


def array_file(path, descriptor, np, dtype, shape):
    body = io.read(path, 80000128, {k:descriptor[k] for k in ('bytes','sha256')})
    array = np.load(streams.BytesIO(body), allow_pickle=False)
    io.need(type(array) is np.ndarray and array.dtype == np.dtype(dtype) and array.shape == tuple(shape),
            'Exact nonobject array dtype/shape')
    return array


def put_array(path, array, np):
    path=io.regular(path); output=streams.BytesIO(); np.save(output,array,allow_pickle=False); body=output.getvalue()
    io.need(len(body)<=80000128, 'Bounded prepared array')
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'wb') as stream: stream.write(body);stream.flush();os.fsync(stream.fileno())
    path.chmod(0o444)
    return io.pin(body)
