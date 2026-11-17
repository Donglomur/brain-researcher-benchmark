#!/usr/bin/env python3
"""Export paired participant materials; this does not execute a solver episode.

Both conditions receive the same admitted train/validation/test inputs, permitted
validation targets, paper and task contract. Only paper_with_code receives pinned
official implementation source. No checkpoint, test target or operator prediction
is exported. Filesystem/network isolation must be supplied by a future runner.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import shutil
import tempfile

import h5py
import numpy as np


HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("_smc_delivery_scorer_contract", HERE / "scorer.py")
contract = importlib.util.module_from_spec(spec)
spec.loader.exec_module(contract)
REFERENCE_TEST = HERE / "reference_panel.json"
REFERENCE_VAL = HERE / "reference_validation_panel.json"
SOURCE_MANIFEST = HERE / "source_manifest.json"
PROTOCOL = HERE / "protocol.json"
PAPER_URL = "https://papers.neurips.cc/paper_files/paper/2024/file/209423f076b6479ab3a4f45886e30306-Paper-Conference.pdf"
PAPER_SHA256 = "85bcb5c03551717cbe5fcb9fa12aabde43dd3c181f258e5e92032ea5d7279075"
CONDITIONS = ("paper_only", "paper_with_code")
TRAIN_KEYS = {"train_spikes_heldin", "train_spikes_heldout", "train_behavior",
              "train_spikes_heldin_forward", "train_spikes_heldout_forward"}
VAL_TARGET_KEYS = {"eval_spikes_heldout", "train_behavior", "eval_behavior",
                   "eval_spikes_heldin_forward", "eval_spikes_heldout_forward",
                   "eval_cond_idx", "train_cond_idx", "psth"}
FORBIDDEN_PARTS = {".git", "__pycache__", "checkpoints", "data", "data_untracked"}
FORBIDDEN_SUFFIXES = {".pkl", ".pickle", ".pt", ".pth", ".h5", ".nwb", ".npz", ".npy",
                      ".safetensors", ".ckpt", ".pyc"}


def require(condition, message):
    contract.require(condition, message)


def safe_relative(value):
    require(isinstance(value, str), "source paths must be strings")
    path = PurePosixPath(value)
    require(value == str(path) and not path.is_absolute() and bool(path.parts)
            and all(part not in (".", "..") for part in path.parts)
            and "\\" not in value, "unsafe relative source path")
    return path


def regular_beneath(root, relative):
    relative = safe_relative(str(relative))
    root = Path(root).resolve()
    path = root
    for part in relative.parts:
        path = path / part
        require(not path.is_symlink(), "symlinks are forbidden in delivery inputs")
    require(path.is_file() and path.resolve().is_relative_to(root), "delivery input file is missing")
    return path


def no_private_paths(value):
    if isinstance(value, dict):
        for key, child in value.items():
            no_private_paths(key)
            no_private_paths(child)
    elif isinstance(value, list):
        for child in value:
            no_private_paths(child)
    elif isinstance(value, str):
        require(not value.startswith(("/", "~/", "file://"))
                and "/Users/" not in value and "/home/" not in value,
                "private absolute paths are forbidden in participant metadata")


def write_json(path, data):
    no_private_paths(data)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True, allow_nan=False) + "\n")


def copy_verified(source, destination, expected_sha256):
    shutil.copyfile(source, destination)
    require(contract.sha256(destination) == expected_sha256, "file changed during participant export")


def read_plain_dataset(group, name, shape=None):
    contract.plain_hdf5_link(group, name)
    item = group[name]
    require(isinstance(item, h5py.Dataset) and not item.is_virtual and not item.external,
            "indirect or non-dataset input is forbidden")
    require(not item.attrs, "unexpected HDF5 dataset attributes")
    if shape is not None:
        require(list(item.shape) == list(shape), "input shape differs from admitted panel: " + name)
    return item


def canonical_content_hash(item):
    digest = hashlib.sha256(json.dumps(list(item.shape), separators=(",", ":")).encode())
    for start in range(0, item.shape[0], 32):
        values = np.asarray(item[start:start + 32], dtype="<f8", order="C")
        digest.update(values.tobytes(order="C"))
    return digest.hexdigest()


def validate_input_file(path, filename, panel):
    require(contract.sha256(path) == panel["inputs_sha256"][filename], "input file hash mismatch")
    train = filename == "train_input_20ms.h5"
    keys = TRAIN_KEYS if train else {"eval_spikes_heldin"}
    with h5py.File(path, "r") as handle:
        require(set(handle) == keys and not handle.attrs, "forbidden or missing HDF5 input members")
        for name in sorted(keys):
            n = panel["n_train"] if train else panel["n_eval"]
            bins = 10 if name.endswith("_forward") else 35
            units = 2 if name == "train_behavior" else (45 if "heldout" in name else 137)
            item = read_plain_dataset(handle, name, (n, bins, units))
            require(item.dtype.kind in "fiu", "input arrays must be numeric")
            digest = canonical_content_hash(item)
            require(digest == panel["input_content_sha256"].get(filename + ":" + name),
                    "input content hash mismatch")


def validate_validation_target(path, panel):
    require(contract.sha256(path) == panel.get("validation_target_sha256"),
            "validation target has not been admitted by exact hash")
    with h5py.File(path, "r") as handle:
        require(set(handle) == {contract.DATASET} and not handle.attrs, "unexpected validation target group")
        contract.plain_hdf5_link(handle, contract.DATASET)
        group = handle[contract.DATASET]
        require(isinstance(group, h5py.Group) and set(group) == VAL_TARGET_KEYS and not group.attrs,
                "forbidden or missing validation target members")
        shapes = panel.get("validation_target_shapes", {})
        require(set(shapes) == VAL_TARGET_KEYS, "validation target shapes were not admitted")
        scientific_shapes = {
            "eval_spikes_heldout": (panel["n_eval"], 35, 45),
            "eval_spikes_heldin_forward": (panel["n_eval"], 10, 137),
            "eval_spikes_heldout_forward": (panel["n_eval"], 10, 45),
            "train_behavior": (panel["n_train"], 35, 2),
            "eval_behavior": (panel["n_eval"], 35, 2),
        }
        for name, shape in scientific_shapes.items():
            require(list(shape) == shapes[name], "validation target shape does not match original observations")
        require(len(shapes["psth"]) == 3 and 0 < shapes["psth"][0] <= 108
                and shapes["psth"][1:] == [35, 182], "invalid admitted validation PSTH shape")
        for name, shape in shapes.items():
            read_plain_dataset(group, name, shape)


def admitted_phase(prepared_root, phase):
    reference_path = REFERENCE_TEST if phase == "test" else REFERENCE_VAL
    require(reference_path.is_file(), "authentic " + phase + " reference panel is missing")
    reference = contract.read_json(reference_path)
    root = Path(prepared_root) / "mc_maze" / phase
    panel_path = regular_beneath(root, "panel.json")
    panel = contract.read_json(panel_path)
    fields = contract.PANEL_IDENTITY_FIELDS + ("inputs_sha256",)
    if phase == "val":
        fields += ("validation_target_sha256", "validation_target_shapes")
    for field in fields:
        require(field in reference and field in panel and panel[field] == reference[field],
                phase + " panel differs from the trusted native reference: " + field)
    require(panel["phase"] == phase and panel["source_commit"] == contract.AUTHOR_COMMIT,
            "phase/source provenance differs")
    for filename in ("train_input_20ms.h5", "eval_input_20ms.h5"):
        path = regular_beneath(root, filename)
        validate_input_file(path, filename, panel)
    if phase == "val":
        validate_validation_target(regular_beneath(root, "eval_target_20ms.h5"), panel)
    # An operator target in the prediction tree is a boundary violation even if
    # the explicit export allowlist would not otherwise copy it.
    require(not (Path(prepared_root) / "mc_maze" / "test" / "eval_target_20ms.h5").exists(),
            "test targets must not be staged in the participant input tree")
    return panel, root


def official_source_files(author_source, manifest_path):
    require(contract.sha256(manifest_path) == contract.sha256(SOURCE_MANIFEST),
            "source manifest differs from the package's pinned manifest")
    manifest = contract.read_json(manifest_path)
    require(manifest.get("source_commit") == contract.AUTHOR_COMMIT, "wrong official source revision")
    selected, seen = [], set()
    for row in manifest["files"]:
        if row["role"] != "source":
            continue
        relative = safe_relative(row["path"])
        require(not (set(relative.parts) & FORBIDDEN_PARTS)
                and relative.suffix.lower() not in FORBIDDEN_SUFFIXES,
                "non-code payload was labeled as official source")
        require(str(relative) not in seen, "duplicate official source path")
        seen.add(str(relative))
        path = regular_beneath(author_source, relative)
        require(path.stat().st_size == row["bytes"] and contract.sha256(path) == row["sha256"],
                "official source bytes differ from the pinned manifest")
        selected.append((path, relative, row))
    require("LICENSE" in seen and bool(selected), "official source license or source files missing")
    return selected, {key: manifest[key] for key in ("schema", "source_commit", "source_repo", "license")}


def file_inventory(root):
    rows = []
    for path in sorted(Path(root).rglob("*")):
        require(not path.is_symlink(), "delivery must not contain symlinks")
        if path.is_file():
            rows.append({"path": path.relative_to(root).as_posix(), "bytes": path.stat().st_size,
                         "sha256": contract.sha256(path)})
    return rows


def export_pair(prepared_root, author_source, paper, output, *,
                source_manifest=SOURCE_MANIFEST, protocol=PROTOCOL):
    """Export an immutable, allowlisted pair after authentic phase admission."""
    output = Path(output).resolve()
    require(not output.exists(), "paired delivery output already exists")
    require(not any((ancestor / ".git").exists() for ancestor in (output, *output.parents)),
            "authentic participant payloads must remain outside public Git worktrees")
    require(contract.sha256(protocol) == contract.sha256(PROTOCOL), "protocol differs from the frozen task protocol")
    protocol_data = contract.read_json(protocol)
    no_private_paths(protocol_data)
    paper = Path(paper)
    require(paper.is_file() and not paper.is_symlink() and 0 < paper.stat().st_size <= 4 * 1024 * 1024,
            "provide the original paper PDF, at most 4 MiB")
    with paper.open("rb") as handle:
        require(handle.read(5) == b"%PDF-", "paper must be a local PDF")
    require(contract.sha256(paper) == PAPER_SHA256, "paper differs from the pinned original publication")
    test, test_root = admitted_phase(prepared_root, "test")
    val, val_root = admitted_phase(prepared_root, "val")
    code, code_metadata = official_source_files(author_source, source_manifest)
    output.parent.mkdir(parents=True, exist_ok=True)
    input_bytes = sum(
        (root / name).stat().st_size for root, names in
        ((test_root, ("train_input_20ms.h5", "eval_input_20ms.h5")),
         (val_root, ("train_input_20ms.h5", "eval_input_20ms.h5", "eval_target_20ms.h5"))) for name in names
    )
    estimated_export_bytes = 2 * (input_bytes + paper.stat().st_size)
    estimated_export_bytes += sum(row["bytes"] for _, _, row in code) + 4 * 1024**2
    require(shutil.disk_usage(output.parent).free - estimated_export_bytes >= 60 * 1024**3,
            "export would violate the 60 GiB free-disk floor")
    task = {
        "schema": "smc_participant_task_v1", "task_id": "PAPER-SMC-RNN-2024",
        "objective": "Improve the matching original Table 2 SMC-RNN co-bps result on the complete MC_Maze 20-ms test panel; report every companion metric.",
        "metrics": protocol_data["metrics"], "allowed_observations": {
            "train": "All original training spikes and behavior, including forward bins.",
            "validation": "Original validation held-in inputs and separately labeled validation targets; permitted for selection.",
            "test": "All original test held-in spikes only; original train+validation spikes and behavior for fitting and decoder inputs.",
            "excluded": ["Original test target file", "Operator predictions", "Author checkpoints"],
        },
        "prediction_abi": {"format": "HDF5", "group": contract.DATASET,
            "required_arrays": {key: test["expected_shapes"][key] for key in sorted(contract.REQUIRED_KEYS)},
            "optional_arrays": {key: test["expected_shapes"][key] for key in sorted(contract.OPTIONAL_KEYS)},
            "values": "Finite nonnegative expected spike counts per 20-ms bin, original trial and neuron order. Original scorer clips zero rates to 1e-9.",
            "submission": "submission.h5", "freeze": "Operator freezes submission, panel and protocol hashes before accessing test targets.",
            "method_report": "Report method, arm, selection procedure, seed(s), resources and all data/source exposure. Do not include test truths."},
        "budgets": {"operator_source_qualification": protocol_data["budget"],
            "candidate_episode": None,
            "scope": "No candidate run is launched or authorized by this materials export. A runner must freeze equal candidate budgets before a paired comparison."},
        "exposure": "Original test targets became public in January 2026. Local exclusion does not make this an untouched holdout.",
        "interpretation": "Reproduction is calibration. A positive point difference alone is not an improvement finding; prespecify uncertainty and companion non-regression before candidate scoring. Exceeding SMC-RNN does not establish current SOTA.",
    }
    with tempfile.TemporaryDirectory(prefix=".smc-pair-", dir=output.parent) as temporary:
        staging = Path(temporary) / "pair"
        inventories = {}
        for condition in CONDITIONS:
            destination = staging / condition
            destination.mkdir(parents=True)
            copy_verified(paper, destination / "paper.pdf", PAPER_SHA256)
            write_json(destination / "paper.json", {"url": PAPER_URL, "sha256": contract.sha256(paper),
                       "title": "Inferring stochastic low-rank recurrent neural networks from neural data",
                       "authors": ["Matthijs Pals", "A Erdem Sagtekin", "Felix Pei", "Manuel Gloeckler", "Jakob H Macke"],
                       "publication": "NeurIPS 2024", "source_locations": ["Supplement B.5/Table 2", "Supplement D.7"]})
            copy_verified(protocol, destination / "protocol.json", contract.sha256(PROTOCOL))
            write_json(destination / "task.json", task)
            write_json(destination / "attribution.json", {
                "dataset": "Mark Churchland and Matthew Kaufman (2022), MC_Maze: macaque primary motor and dorsal premotor cortex spiking activity during delayed reaching",
                "dataset_url": "https://doi.org/10.48324/dandi.000128/0.220113.0400", "dataset_license": "CC-BY-4.0",
                "nlb_tools": "neurallatents/nlb_tools 0.0.3, MIT; source tensor recipe preserved",
                "data_transform": "20-ms binning and original train/validation/test tensors; validation targets included, test targets excluded",
            })
            for phase, panel, root in (("val", val, val_root), ("test", test, test_root)):
                target_dir = destination / "inputs" / "mc_maze" / phase
                target_dir.mkdir(parents=True)
                names = ["train_input_20ms.h5", "eval_input_20ms.h5"]
                if phase == "val":
                    names.append("eval_target_20ms.h5")
                for name in names:
                    expected_hash = panel["validation_target_sha256"] if name.startswith("eval_target_") else panel["inputs_sha256"][name]
                    copy_verified(root / name, target_dir / name, expected_hash)
                # Only authenticated scientific identity fields are participant metadata.
                public_panel = {key: panel[key] for key in contract.PANEL_IDENTITY_FIELDS}
                public_panel["inputs_sha256"] = panel["inputs_sha256"]
                if phase == "val":
                    public_panel["validation_target_sha256"] = panel["validation_target_sha256"]
                    public_panel["validation_target_shapes"] = panel["validation_target_shapes"]
                write_json(target_dir / "panel.json", public_panel)
            if condition == "paper_with_code":
                for path, relative, row in code:
                    target = destination / "official_source" / str(relative)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    copy_verified(path, target, row["sha256"])
                write_json(destination / "official_source_manifest.json",
                           {**code_metadata, "files": [row for _, _, row in code]})
            inventories[condition] = file_inventory(destination)
            write_json(destination / "delivery_manifest.json", {
                "schema": "smc_participant_delivery_v1", "condition": condition,
                "status": "participant_materials_prepared", "files": inventories[condition],
                "validation_targets": "included_identically_as_permitted_original_validation_observations",
                "boundary": "Allowlisted materials only. No execution, sandbox, network restriction, or protected-test claim follows.",
            })
        left = {row["path"]: row["sha256"] for row in inventories[CONDITIONS[0]]}
        right = {row["path"]: row["sha256"] for row in inventories[CONDITIONS[1]]}
        require(all(right.get(path) == digest for path, digest in left.items()), "paired shared files differ")
        additions = sorted(set(right) - set(left))
        require(all(path.startswith("official_source/") or path == "official_source_manifest.json" for path in additions),
                "paired conditions differ outside official code")
        pair = {"schema": "smc_paired_delivery_v1", "task_id": "PAPER-SMC-RNN-2024",
                "status": "participant_materials_prepared", "conditions": list(CONDITIONS),
                "shared_files": left, "code_condition_additions": additions,
                "condition_manifest_sha256": {condition: contract.sha256(staging / condition / "delivery_manifest.json") for condition in CONDITIONS},
                "episode_executed": False, "solver_results": None, "scientific_qualification": False}
        write_json(staging / "pair_manifest.json", pair)
        staging.rename(output)
    return pair


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("prepared-root", "author-source", "paper", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--source-manifest", type=Path, default=SOURCE_MANIFEST)
    parser.add_argument("--protocol", type=Path, default=PROTOCOL)
    args = parser.parse_args(argv)
    result = export_pair(args.prepared_root, args.author_source, args.paper, args.output,
                         source_manifest=args.source_manifest, protocol=args.protocol)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
