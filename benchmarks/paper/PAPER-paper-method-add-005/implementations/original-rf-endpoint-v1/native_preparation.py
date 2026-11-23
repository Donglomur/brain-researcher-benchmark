"""Local, operator-only NetCDF bridge for the original AJILE RF endpoint.

No download, imputation, RF fitting, or historical data admission is performed.
Both output files contain protected evaluation information and stay operator-only.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

import numpy as np

_spec = importlib.util.spec_from_file_location(
    "_ajile_native_preparation", Path(__file__).with_name("preparation.py")
)
preparation = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(preparation)
endpoint = preparation.endpoint
require = endpoint.require
SCHEMA = "ajile-source-rf-native-preparation-v1"
DIMENSIONS = ("events", "channels", "time")


def prepare_netcdf(path, *, expected_sha256, participant, kind):
    """Read one admitted local source file without changing source axis semantics.

    The pinned loader applies Dataset positional indexing followed by to_array
    and squeeze. A sole variable in events/channels/time order is the supported
    case; reject other layouts rather than transposing or selecting a variable.
    Row IDs identify file bytes and original event positions, not recovered
    historical event names. The expected digest must come from the operator's
    independently admitted source inventory.
    """
    path = Path(path)
    require(path.is_file(), "local source file required")
    require(endpoint.valid_digest(expected_sha256), "expected source SHA256 required")
    require(endpoint.digest_file(path) == expected_sha256, "source SHA256 mismatch")
    import xarray as xr

    # Keep the author's open_dataset defaults, including CF decoding. Do not
    # reinterpret encoded coordinates or silently repair an unsupported schema.
    with xr.open_dataset(path) as dataset:
        require(len(dataset.data_vars) == 1, "source requires exactly one data variable")
        name = next(iter(dataset.data_vars))
        variable = dataset[name]
        require(variable.dims == DIMENSIONS, "source variable must have events/channels/time dimension order")
        require(set(dataset.sizes) == set(DIMENSIONS), "unexpected source dimensions")
        for coordinate in DIMENSIONS:
            require(coordinate in dataset.coords and dataset[coordinate].dims == (coordinate,),
                    f"explicit one-dimensional {coordinate} coordinate required")
        native = variable.values
        days = dataset.events.values
        times = dataset.time.values
        channels = dataset.channels.values
        rows = np.array([f"sha256:{expected_sha256}:event:{index}" for index in range(len(days))])
        arrays, metadata = preparation.prepare_arrays(
            native, event_days=days, times=times, channel_coordinates=channels,
            row_ids=rows, participant=participant, source_sha256=expected_sha256,
            kind=kind,
        )
        extraction = {
            "schema": SCHEMA, "variable": name, "dimension_order": list(variable.dims),
            "native_shape": list(variable.shape), "decoded_dtype": variable.dtype.str,
            "row_identity": "source SHA256 plus zero-based native event position",
            "coordinate_identities": {key: endpoint.array_digest(dataset[key].values)
                                      for key in DIMENSIONS},
            "xarray": xr.__version__, "decoder_options": "source open_dataset defaults",
            "source_bytes": path.stat().st_size,
        }
    require(endpoint.digest_file(path) == expected_sha256, "source changed during extraction")
    metadata["native_extraction"] = extraction
    return arrays, metadata


def write_bundle(output, arrays, metadata):
    """Create a new operator-only bundle; leave no partial bundle on failure."""
    output = Path(output)
    output.mkdir(mode=0o700)
    array_path, metadata_path = output / "prepared.npz", output / "preparation.json"
    try:
        # Files inherit the enclosing private directory's access boundary.
        with array_path.open("xb") as stream:
            np.savez(stream, **arrays)
        receipt = dict(metadata)
        receipt["prepared_artifact"] = {
            "path": array_path.name, "bytes": array_path.stat().st_size,
            "sha256": endpoint.digest_file(array_path),
        }
        with metadata_path.open("x") as stream:
            json.dump(receipt, stream, indent=2, allow_nan=False)
            stream.write("\n")
    except BaseException:
        for path in (array_path, metadata_path):
            path.unlink(missing_ok=True)
        output.rmdir()
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="admitted local *_ecog_data.nc")
    parser.add_argument("output", type=Path, help="new operator-only bundle directory")
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--participant", choices=endpoint.PARTICIPANTS, required=True)
    parser.add_argument("--kind", choices=("generated_control", "authentic_input"), required=True)
    args = parser.parse_args(argv)
    try:
        require(not args.output.exists(), "refusing to overwrite output bundle")
        arrays, metadata = prepare_netcdf(args.input, expected_sha256=args.expected_sha256,
                                        participant=args.participant, kind=args.kind)
        write_bundle(args.output, arrays, metadata)
    except (ValueError, KeyError, OSError, TypeError, ImportError) as error:
        parser.exit(2, f"error: {error}\n")


if __name__ == "__main__":
    main()
