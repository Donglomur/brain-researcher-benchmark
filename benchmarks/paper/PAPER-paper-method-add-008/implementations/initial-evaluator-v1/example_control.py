"""Write a five-unit generated engineering input, never an empirical reference."""
import argparse
import copy
import json
from pathlib import Path
from evaluator import ASSET, CONTRACT_SHA256, SOURCE_COMMIT, SORTERS, TASK_ID, canonical_digest


def control():
    units = {f"u{i}": 1 for i in range(1, 6)}
    manifest = {
        "schema_version": 1, "task_id": TASK_ID, "contract_sha256": CONTRACT_SHA256,
        "source_commit": SOURCE_COMMIT, "evidence_kind": "generated_engineering_control",
        "recording": {**ASSET, "content_sha256": "1" * 64,
                      "source_path_resolution_receipt_sha256": "2" * 64,
                      "electrical_series_path": "acquisition/ElectricalSeries",
                      "sampling_frequency_hz": 1000, "num_frames": 100,
                      "channel_ids": ["generated-channel"]},
        "curation": {"spikeinterface_version": "generated-control-no-native-runtime",
                     "bombcell_implementation_sha256": "3" * 64,
                     "unitrefine_noise_model_sha256": "4" * 64,
                     "unitrefine_sua_mua_model_sha256": "5" * 64,
                     "dependency_lock_sha256": "6" * 64, "policy_sha256": "7" * 64},
        "runs": {},
    }
    rows = [{"unit_id": f"u{i}", "bombcell_label": b, "unitrefine_label": u}
            for i, (b, u) in enumerate(zip(
                ("good", "non_soma_good", "mua", "non_soma_mua", "noise"),
                ("sua", "mua", "mua", "noise", "sua")), 1)]
    exports = {"schema_version": 1, "owner_manifest_sha256": "", "sorters": {}}
    for sorter in SORTERS:
        source_name = "tridesclous2A" if sorter == "tridesclous2" else sorter
        manifest["runs"][sorter] = {
            "source_protocol_key": source_name + "_no_motion_correction",
            "sorter_version": "generated-control-no-sorter-run",
            "effective_parameters_sha256": "8" * 64, "native_artifact_sha256": "9" * 64,
            "analyzer_preprocessing_order": ["common_reference", "bandpass_filter"] if sorter == "kilosort4" else ["bandpass_filter", "common_reference"],
            "unit_spike_counts": copy.deepcopy(units), "runtime_seconds": 1.0, "peak_memory_bytes": 1,
        }
        exports["sorters"][sorter] = {"unit_rows": copy.deepcopy(rows),
                                      "slay_merge_groups": [["u1", "u2", "u3"], ["u4", "u5"]],
                                      "native_artifact_sha256": "9" * 64}
    digest = canonical_digest(manifest)
    exports["owner_manifest_sha256"] = digest
    raster = "unit_id,sample_index,depth_um,amplitude_uv\n" + "".join(
        f"u{i},{i * 10},{i * 20},-100\n" for i in range(1, 6))
    return manifest, exports, digest, raster


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_directory", type=Path)
    args = parser.parse_args()
    args.output_directory.mkdir(exist_ok=False)
    manifest, exports, digest, raster = control()
    for name, value in (("owner-manifest.json", manifest), ("curation.json", exports)):
        (args.output_directory / name).write_text(json.dumps(value, indent=2) + "\n")
    (args.output_directory / "all-kilosort-spikes.csv").write_text(raster)
    (args.output_directory / "manifest.sha256").write_text(digest + "\n")
    print(digest)


if __name__ == "__main__":
    main()
