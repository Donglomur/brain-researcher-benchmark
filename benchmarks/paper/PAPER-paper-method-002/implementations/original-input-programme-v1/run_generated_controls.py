"""Portable entry for genuine CPU/x64 BC convolution and loader controls.

The 15 scientific assertions and exact numeric comparisons are unchanged.
A bounded child retains diagnostics; --artifacts requires an absent leaf.
"""

import os
import platform
import stat
import sys
import types
from importlib import metadata

PINS = {
    "producer": (12222, "2a0890f8cfd44d54592cde0935627d2ab4c096ba0c03a7401dbfa6f4a3d9580a"),
    "composition": (10440, "f8c2296b5434ace7478fd762f7709700c867ad528818c85055a42f1655457d75"),
    "kernels": (7692, "46af417cfe92b2ffbd8fa5618c97ba5f9d6ddee93452d50aa8df7dc6e4a01517"),
    "controls": (5887, "37bddb6bfa43e13aec782582f0a4b78a083aa5e838331333959466e463715cb9"),
}

MAX_OUTPUT_BYTES = 65536

MAX_ERROR_BYTES = 4096

RAW_SCHEMA = "jaxley-new-producer-generated-differential-v1"

def require(condition, reason):
    if not condition:
        raise ValueError(reason)

def package_metadata():
    versions = {}
    for name in ("numpy", "pandas", "jax", "jaxlib", "scipy"):
        try:
            value = metadata.version(name)
        except metadata.PackageNotFoundError:
            value = None
        require(value is None or len(value) <= 256, "unbounded package version metadata")
        versions[name] = value
    return {"python": sys.version, "executable": sys.executable,
            "machine": platform.machine(), "system": platform.system(),
            "distributions": versions,
            "scope": "stdlib distribution metadata, not native/runtime qualification"}

def load_verified_modules(bodies, source_pins):
    modules = {}
    for role in PINS:
        name = "_jaxley_bc_generated_" + role + "_" + PINS[role][1][:12]
        module = types.ModuleType(name)
        module.__file__ = source_pins[role]["path"]
        # Execute the already authenticated bytes, never reopen a source path.
        # All four pinned files have definition/constant-only module scope.
        code = compile(bodies[role], module.__file__, "exec", dont_inherit=True)
        exec(code, module.__dict__)
        modules[role] = module
    return modules

def child_runtime_facts():
    """Observe the admitted control child after success; no binary body hashes.

    The frozen control configured CPU/x64 before creating any arrays. These
    observations belong to that same process, not a separate owner verifier.
    """
    import jax
    import jaxlib
    import numpy
    import pandas
    import scipy

    def file_identity(module):
        path = vars(module).get("__file__")
        result = {"module_file": path}
        if path is not None:
            try:
                current = os.stat(path)
                result.update(realpath=os.path.realpath(path), bytes=current.st_size,
                    device=current.st_dev, inode=current.st_ino,
                    mtime_ns=current.st_mtime_ns, ctime_ns=current.st_ctime_ns,
                    mode=current.st_mode, regular_file=stat.S_ISREG(current.st_mode))
            except OSError as exc:
                result["stat_error"] = bounded_error(exc)
        return result

    modules = {"jax": jax, "jaxlib": jaxlib, "numpy": numpy,
               "pandas": pandas, "scipy": scipy}
    identities = {}
    for name, module in modules.items():
        identities[name] = file_identity(module)
        identities[name]["version"] = vars(module).get("__version__")
    providers = {}
    for name, module in list(sys.modules.items()):
        if not name.startswith("jaxlib") or not isinstance(module, types.ModuleType):
            continue
        path = vars(module).get("__file__")
        if isinstance(path, str) and path.endswith((".so", ".dylib", ".pyd")):
            providers[name] = file_identity(module)
    devices = [{"id": int(device.id), "platform": device.platform,
                "device_kind": device.device_kind,
                "process_index": int(device.process_index), "description": str(device)}
               for device in jax.devices()]
    flags = {}
    for name in ("jax_enable_x64", "jax_platform_name", "jax_platforms"):
        try:
            value = getattr(jax.config, name)
        except AttributeError:
            value = jax.config.read(name)
        if name == "jax_enable_x64":
            require(type(value) is bool, "JAX x64 flag is not a boolean value")
        else:
            require(value is None or type(value) is str,
                    "JAX platform flag is not a string/null value: " + name)
        flags[name] = value
    return {"modules": identities, "default_backend": jax.default_backend(),
            "devices": devices, "jax_config": flags,
            "loaded_jaxlib_native_providers": providers,
            "native_provider_scope": "Loaded jaxlib Python-extension module paths/stat in this child only; no binary body hashes or mapped-memory attestation",
            "native_provider_available": bool(providers),
            "current_source_and_runtime_bound": False}

def bounded_error(exc):
    value = (type(exc).__name__ + ": " + str(exc)).encode("utf-8", "replace")
    # Leave room for a possible replacement character at the UTF-8 boundary.
    return value[:MAX_ERROR_BYTES - 4].decode("utf-8", "replace")


HELPER_PIN = (14104, 'd44de0d61c9b8c5f1f33226fcedfec40dc66873f669ad44e8c28eb07e930b59e')
SOURCE_PINS = {'portable_consumer.py': (15008, 'e72e33d0a97648d8023e656695e0a3ce54b0e0140df2382e340e0f2534bc7c12'), 'input_binding.py': (10007, 'f4bd10b4c40cef74835001937ce3dc5cb4bd16fcc061b4138696b39827a707d9'), 'camera_centers.py': (3458, 'd6706e2ea864c9898df5491094add2852f13f544e555c4b62c6e7924f4f2d5c9'), 'bc_producer.py': (12222, '2a0890f8cfd44d54592cde0935627d2ab4c096ba0c03a7401dbfa6f4a3d9580a'), 'author_kernels.py': (7692, '46af417cfe92b2ffbd8fa5618c97ba5f9d6ddee93452d50aa8df7dc6e4a01517'), 'input_composition.py': (10440, 'f8c2296b5434ace7478fd762f7709700c867ad528818c85055a42f1655457d75'), 'generated_producer_controls.py': (5887, '37bddb6bfa43e13aec782582f0a4b78a083aa5e838331333959466e463715cb9')}
PUBLIC_NAMES = ['README.md', 'SOURCE.json', 'author_kernels.py', 'bc_producer.py', 'camera_centers.py', 'generated_boundary_controls.py', 'generated_producer_controls.py', 'input_binding.py', 'input_composition.py', 'portable_consumer.py', 'reporting_transport.py', 'run_generated_controls.py']
EXPECTED_IDS = ['actual source convolution CPU/x64', 'literal/shared source row-index and column order', 'literal/shared exact BC coordinates and one-based IDs', 'complete110BC source precision for generated fields', 'literal/shared exact numeric equality', 'sharing removes only repeated field-invariant convolution calls', 'normalization uses all110 BCs separately perfield/frame', 'source leftjoin preserves connection-row and duplicated BC order', 'all15fields use first1024 source frames in order, BC0', 'all15fields use first1024 source frames in order, BC1', 'all15fields use first1024 source frames in order, BC2', 'source image-major shape and original dtype', 'image axes/time/field repeat binding', 'loader refuses changed field support order', 'loader refuses unmatched source BC identity']


def _reporter():
    # Authenticate the one adjacent stdlib helper before executing its bytes.
    import hashlib
    import os
    import stat
    import types
    root = os.path.dirname(os.path.abspath(__file__))
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    directory = os.open('/', flags)
    fd = None
    try:
        for part in root.split('/')[1:]:
            if part in ('', '.', '..'):
                raise ValueError('noncanonical source root')
            child = os.open(part, flags, dir_fd=directory)
            os.close(directory)
            directory = child
        fd = os.open('reporting_transport.py', os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size != HELPER_PIN[0]:
            raise ValueError('helper mode/link/extent')
        chunks, total = [], 0
        while total <= HELPER_PIN[0]:
            part = os.read(fd, min(8192, HELPER_PIN[0] + 1 - total))
            if not part:
                break
            chunks.append(part)
            total += len(part)
        body = b''.join(chunks)
        identity = lambda value: (value.st_dev, value.st_ino, value.st_mode, value.st_nlink, value.st_size, value.st_mtime_ns, value.st_ctime_ns)
        if identity(before) != identity(os.fstat(fd)) or len(body) != HELPER_PIN[0] or hashlib.sha256(body).hexdigest() != HELPER_PIN[1]:
            raise ValueError('helper byte identity')
    finally:
        if fd is not None:
            os.close(fd)
        os.close(directory)
    module = types.ModuleType('_jaxley_input_reporting_transport')
    module.__file__ = os.path.join(root, 'reporting_transport.py')
    exec(compile(body, module.__file__, 'exec', dont_inherit=True), module.__dict__)
    return module, root


def _authenticated_sources(reporting, root):
    import os
    directory = reporting._directory(root)
    try:
        reporting.require(sorted(os.listdir(directory)) == PUBLIC_NAMES, 'exact owned source namespace')
    finally:
        os.close(directory)
    # All seven unchanged source/control modules are authenticated before any
    # scientific import; execution consumes these held bytes, never a reopen.
    return {name: reporting.read_source(root, name, size, digest)
            for name, (size, digest) in SOURCE_PINS.items()}


def main(argv=None):
    import argparse
    import os
    import sys
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--artifacts', help='one entirely absent artifact directory')
    mode.add_argument('--worker-report-fd', type=int, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    reporting, root = _reporter()
    if args.worker_report_fd is not None:
        # Internal transport endpoint always invokes this suite's real function.
        # It accepts no replacement source, command, roster or fixture selector.
        return _worker(reporting, root, args.worker_report_fd)
    command = [sys.executable, '-I', '-B', os.path.join(root, os.path.basename(__file__))]
    return reporting.transport(command, args.artifacts, EXPECTED_IDS)


def _worker(reporting, root, report_fd):
    entry = {'schema': 'jaxley-generated-control-cli-entry-v1', 'source_pins': {},
             'runtime_metadata': None, 'child_runtime': None, 'scientific_call_started': False,
             'resource_authority': False, 'original_inputs': False, 'model_fits': False,
             'old_control_replay': False, 'installs_or_backend_substitution': False}
    function = None
    try:
        held = _authenticated_sources(reporting, root)
        roles = {'producer': 'bc_producer.py', 'composition': 'input_composition.py',
                 'kernels': 'author_kernels.py', 'controls': 'generated_producer_controls.py'}
        bodies = {role: held[name] for role, name in roles.items()}
        entry['source_pins'] = {role: {'path': os.path.join(root, name), 'bytes': PINS[role][0],
                                      'sha256': PINS[role][1]} for role, name in roles.items()}
        entry['runtime_metadata'] = package_metadata()
        missing = [name for name, value in entry['runtime_metadata']['distributions'].items() if value is None]
        require(not missing, 'missing required control dependencies:' + ','.join(missing))
        modules = load_verified_modules(bodies, entry['source_pins'])
        function = modules['controls'].run_generated_differential
        entry['scientific_call_started'] = True
        raw = function(modules['producer'], modules['composition'], modules['kernels'].make_author_kernels)
        require(type(raw) is dict and raw.get('schema') == RAW_SCHEMA, 'unexpected scientific schema')
        require(raw.get('status') == 'PASS' and raw.get('exact_numeric_equal') is True
                and raw.get('checks') == EXPECTED_IDS, 'complete unchanged numerical result required')
        require(raw.get('current_source_and_runtime_bound') is False, 'scientific result cannot grant admission')
        entry['child_runtime'] = child_runtime_facts()
        result = {'status': 'PASS', 'controls': raw['checks'], 'scientific_result': raw, 'entry': entry}
        reporting._encode(result, reporting.MAX_RESULT_BYTES)
        code = 0
    except Exception as exc:
        result = {'status': 'FAIL', 'controls': [], 'error': reporting.bounded_error(exc), 'entry': entry,
                  **reporting.trace_observations(exc, function)}
        code = 1
    reporting.write_worker_report(report_fd, result)
    return code


if __name__ == '__main__':
    raise SystemExit(main())
