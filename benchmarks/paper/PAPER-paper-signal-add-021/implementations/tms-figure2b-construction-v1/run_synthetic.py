"""Fixed Linux runtime observation plus the unchanged invented-only146-control harness."""
from pathlib import Path
import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import runpy
import sys


def require(ok, why):
    if not ok:
        raise RuntimeError(why)


def module_pin(module, prefix):
    path = Path(module.__file__).resolve(strict=True)
    require(prefix in path.parents and path.is_file(), "dependency outside selected fresh venv")
    before = path.stat()
    require(before.st_nlink == 1 and before.st_size <= 1048576, "bounded dependency initializer")
    body = path.read_bytes()
    after = path.stat()
    require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
            (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), "dependency changed")
    return {"path": str(path), "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--runtime-output", required=True, type=Path)
    args = parser.parse_args()
    source = Path(__file__).resolve(strict=True).parent
    root = source.parent
    suffix = root.name.removeprefix("tms-figure2b-controls-")
    require(root.parent == Path("/tmp") and suffix != root.name and
            all(x.isdigit() for x in suffix.split("-")) and len(suffix.split("-")) == 2,
            "fixed owned CI root")
    require(args.out == root / "inner/attempt/fixtures" and
            args.runtime_output == root / "inner/attempt/RUNTIME.json", "fixed output locations")
    prefix = Path(sys.prefix).resolve(strict=True)
    require(prefix == Path("/tmp") / ("tms-runtime-" + suffix) and
            sys.prefix != sys.base_prefix, "fresh selected virtual environment")
    require(sys.platform == "linux" and platform.machine() == "x86_64" and
            sys.version_info[:3] == (3, 11, 18) and sys.flags.isolated and
            sys.dont_write_bytecode, "exact isolated Linux interpreter")
    require(os.getuid() == os.getgid() == 65534, "fixed unprivileged worker")
    require(os.environ.get("OPENBLAS_NUM_THREADS") == os.environ.get("OMP_NUM_THREADS") == "1",
            "explicit single-thread native dependency policy")
    import numpy
    import h5py
    require(numpy.__version__ == "2.4.6" and h5py.__version__ == "3.16.0", "exact selected dependency versions")
    report = {"schema": "tms-linux-synthetic-runtime-v1", "python_version": platform.python_version(),
        "machine": platform.machine(), "python_executable": sys.executable,
        "base_prefix": sys.base_prefix, "venv_prefix": str(prefix),
        "numpy_version": numpy.__version__, "h5py_version": h5py.__version__,
        "hdf5_version_observed": h5py.version.hdf5_version,
        "pip_version_observed": importlib.metadata.version("pip"),
        "numpy_initializer": module_pin(numpy, prefix), "h5py_initializer": module_pin(h5py, prefix),
        "requirements_sha256": hashlib.sha256((source / "requirements-ci.lock").read_bytes()).hexdigest(),
        "full_native_dependency_closure": False, "native_matlab_parity": False,
        "scientifically_qualified": False, "primary_inputs": 0}
    with args.runtime_output.open("x") as stream:
        json.dump(report, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    harness = source / "test_source_positions.py"
    require(hashlib.sha256(harness.read_bytes()).hexdigest() ==
            "171aa67796415154d388a926360614cb1b8c8359a1ae53c60f93650b6ce1ab82", "unchanged146-control harness")
    sys.argv = [str(harness), "--out", str(args.out)]
    runpy.run_path(str(harness), run_name="__main__")


if __name__ == "__main__":
    main()
