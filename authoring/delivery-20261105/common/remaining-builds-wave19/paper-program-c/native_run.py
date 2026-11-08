"""Future B/operator original-method invocation in an already audited image.

No author implementation is made available to A by this adapter. Preparation,
dependency/image construction and scientific execution require separate actual
authorization; calling this module's functions is not that authorization.
"""
import hashlib
import os
import random
import runpy
import sys
from pathlib import Path
from core import BRANCHES, REVISION, need
from safe_io import capture, strict


def run(job, context, script, script_pin, wrapper_pin, workspace, capture_directory,
        exposure, capture_bytes):
    need(job['phase'] == 'native' and job['role'] in ('B', 'reference'),
         'Historical source is B/operator only; A runs its own independent program')
    need(exposure['role'] == job['role'] and exposure['image_digest'] and
         exposure['inventory_sha256'], 'Separately audited actual full image/source exposure')
    need(context['revision'] == REVISION and context['branch'] == job['branch']
         and job['branch'] in BRANCHES and context['attempt_id'] == job['id'],
         'Exact original source/branch/attempt context')
    script = Path(script).absolute()
    capture(script, 1_000_000, script_pin)
    # The image already contains the reviewed instrumented wrapper. No package
    # installation, source tree copying, path-only swap or runtime monkeypatch.
    import numpy as np
    import tensorflow as tf
    from osl_dynamics.config_api import wrappers
    capture(wrappers.__file__, 1_000_000, wrapper_pin)
    need(tf.__version__ == '2.9.1', 'Exact declared native TensorFlow recipe')
    from native.sink import CaptureSink, DirectoryStore, install_sink
    from native.contract import validate_context
    validate_context(context)
    sink = CaptureSink(DirectoryStore(capture_directory, capture_bytes), context)
    install_sink(sink)
    random.seed(job['seed'])
    np.random.seed(job['seed'])
    tf.keras.utils.set_random_seed(job['seed'])
    old_argv, old_cwd = sys.argv[:], Path.cwd()
    try:
        os.chdir(workspace)
        sys.argv = [str(script)]
        if job['branch'] != 'ctf_static':
            sys.argv.append(str(10*job['fit_set']+job['attempt']))
        runpy.run_path(str(script), run_name='__main__')
        return sink.finish()
    finally:
        sys.argv[:] = old_argv
        os.chdir(old_cwd)
    # The external executor still supplies actual natural exit and resource
    # closure; a completed sink alone is never an execution attestation.
