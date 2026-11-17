"""One import-only runtime probe. Never invoke the driver CLI or open HDF5 files."""

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--driver-sha256", required=True)
    args = parser.parse_args(argv)
    path = Path(__file__).with_name("inspect_clicks.py")
    with path.open("rb") as handle:
        source = handle.read(131073)
    if len(source) > 131072 or hashlib.sha256(source).hexdigest() != args.driver_sha256:
        raise ValueError("Amended driver does not match the admitted pin")
    spec = importlib.util.spec_from_file_location("neural099_admitted_probe_driver", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load the admitted driver source")
    driver = importlib.util.module_from_spec(spec)
    # Compile the bytes just authenticated; do not reopen the path through a loader.
    exec(compile(source, str(path), "exec"), driver.__dict__)
    runtime, versions = driver.initialize_runtime()
    report = {
        "schema": "neural099-import-only-runtime-probe/v1",
        "driver_sha256": args.driver_sha256,
        "observed_versions": versions,
        "plugin_preload_environment": os.environ.get("HDF5_PLUGIN_PRELOAD"),
        "runtime_module_name": runtime.__name__,
        "driver_main_invoked": False,
        "explicit_probe_hdf5_file_open_calls": 0,
        "native_import_side_effects_instrumented": False,
        "authentic_NWB_hash_bytes": 0,
        "driver_source_hash_bytes": len(source),
        "trial_value_bytes_decoded": 0,
        "scientific_qualified": False,
        "plugin_policy_basis": "retained_official_source_and_prelaunch_environment",
        "plugin_mask_queried": False,
    }
    body = (json.dumps(report, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
    if len(body) > 65536:
        raise ValueError("Probe report exceeds its 64-KiB UTF-8 output bound")
    sys.stdout.buffer.write(body)
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
