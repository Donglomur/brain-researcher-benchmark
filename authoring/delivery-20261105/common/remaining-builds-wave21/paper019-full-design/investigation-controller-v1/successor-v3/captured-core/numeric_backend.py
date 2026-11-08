"""Load the exact reviewed numeric helper bytes, without bytecode caches.

This source identity check is not an interpreter/import/custody qualification.
The separately qualified outer launcher must account its source I/O and startup.
"""
import hashlib
import os
from pathlib import Path
import stat
import types

EXPECTED_BYTES = 24405
EXPECTED_SHA256 = '61715146ac2f01042d1b526896f7133604246f4951ff467c36f2735530ed5892'
path = Path(__file__).absolute().parent/'reference-math/core.py'
fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
try:
    before = os.fstat(fd)
    if not stat.S_ISREG(before.st_mode) or before.st_size != EXPECTED_BYTES:
        raise ValueError('exact numeric source extent')
    raw = b''
    while len(raw) < EXPECTED_BYTES+1:
        piece = os.read(fd, EXPECTED_BYTES+1-len(raw))
        if not piece:
            break
        raw += piece
    after = os.fstat(fd)
    if (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns) != (
        after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns):
        raise ValueError('numeric source changed')
    if len(raw) != EXPECTED_BYTES or hashlib.sha256(raw).hexdigest() != EXPECTED_SHA256:
        raise ValueError('exact numeric source hash')
finally:
    os.close(fd)
module = types.ModuleType('ach_frozen_numeric')
module.__file__ = str(path)
exec(compile(raw,str(path),'exec',dont_inherit=True),module.__dict__)
for name in ('group_weights','weighted_moments','fit_standardizer','transform_standardizer',
             'epoch_features','build_variant','fit_head','predict_head','settings','select_setting',
             'resource_plan','validation_loss','positive_distance_median','NumericFailure'):
    globals()[name] = getattr(module,name)
del module, raw
