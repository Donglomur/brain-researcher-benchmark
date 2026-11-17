"""Owner-side, source-faithful Treebank sentence-decoding reconstruction.

This executable will fit the original models if deliberately run with admitted
inputs/runtime. Construction tests mock its numerical entrypoint; no authentic
execution is implied by this file's presence. Never deliver it or the author
checkout as participant tools in the paper+data condition.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib
import importlib.metadata
import inspect
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from custody import (AUTHOR_COMMIT, TASK_ID, canonical_bytes, digest, loads, read_bounded,
                     require, verify_checkout, write_json_exclusive)
from preparation import assemble
from collect_figure4 import collect
from support_checks import SupportChecks

OVERRIDES = [
    "+exp=timed_tests", "++exp.runner.num_workers=0", "+data=decoding_base",
    "+model=classification_regression_model", "++exp.runner.name=regression_runner_test_set",
    "+task=timed_tests", "+criterion=empty_criterion", "++data.interval_duration=3.0",
    "++data.name=sentence_onset_regression", "+test=held_out_subjects",
    "++task.windows_start=-1", "++task.windows_end=1", "++task.window_duration=0.250",
    "++task.window_step=0.1",
]
PACKAGES = ("numpy", "pandas", "scipy", "h5py", "torch", "omegaconf", "hydra-core",
            "tqdm", "psutil", "tensorboardX", "torch-optimizer", "scikit-learn", "tables")


class EvidenceLog:
    """Bounded private scientific evidence; never silently truncate a record."""
    def __init__(self, path, limit):
        require(type(limit) is int and limit > 0, "positive owner-allocated evidence budget required")
        self.limit, self.bytes, self.records = limit, 0, 0
        self.handle = open(path, "xb")
        os.chmod(path, 0o600)
        self.compressed = gzip.GzipFile(fileobj=self.handle, mode="wb", mtime=0)

    def emit(self, event):
        raw = canonical_bytes(event) + b"\n"
        require(self.bytes + len(raw) <= self.limit, "scientific evidence budget exhausted; no record truncated")
        self.compressed.write(raw)
        self.compressed.flush()
        self.bytes += len(raw)
        self.records += 1

    def close(self):
        try:
            self.compressed.close()
        finally:
            self.handle.close()


def stream_identity(path, expected):
    """Authenticate owner-frozen actual input bytes, without loading into RAM."""
    path = Path(path)
    before = path.stat()
    require(path.is_file() and before.st_size == expected["bytes"], "input size differs from owner-frozen manifest")
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    after = path.stat()
    require((before.st_ino, before.st_size, before.st_mtime_ns) ==
            (after.st_ino, after.st_size, after.st_mtime_ns), "input changed while hashing")
    require(value.hexdigest() == expected["sha256"], "input hash differs from owner-frozen manifest")
    return {"bytes": after.st_size, "sha256": value.hexdigest(), "inode": after.st_ino,
            "mtime_ns": after.st_mtime_ns}


def expected_inputs(prepared):
    expected = {("data", row["relative_path"]): row for row in prepared["runtime_metadata_members"]}
    for subject in prepared["subjects"]:
        for recording in subject["recordings"]:
            expected[("data", recording["hdf5_relative_path"])] = None
            expected[("data", recording["timings_relative_path"])] = None
            movie = recording["metadata"]["filename"]
            require(isinstance(movie, str) and movie and "/" not in movie and "\\" not in movie and movie not in (".", ".."),
                    "source movie ID must be one path component")
            expected[("transcripts", f"{movie}/features.csv")] = None
    return expected


def authenticate_inputs(prepared, declaration, roots):
    require(declaration.get("schema") == "treebank-owner-frozen-inputs/v1" and
            declaration.get("task_id") == TASK_ID, "wrong owner input-manifest schema/task")
    require(isinstance(declaration.get("source_provenance"), dict) and declaration["source_provenance"],
            "owner source-provenance description required; this code does not authenticate that account")
    expected, supplied = expected_inputs(prepared), {}
    require(isinstance(declaration.get("files"), list), "complete owner input file list required")
    for row in declaration["files"]:
        require(set(row) == {"root", "relative_path", "bytes", "sha256"}, "unexpected input identity fields")
        key = (row["root"], row["relative_path"])
        require(key not in supplied and key in expected, "extra/duplicate input identity")
        require(type(row["bytes"]) is int and row["bytes"] > 0 and isinstance(row["sha256"], str) and
                len(row["sha256"]) == 64 and all(char in "0123456789abcdef" for char in row["sha256"]),
                "invalid owner input hash/size")
        if expected[key] is not None:
            require(row["bytes"] == expected[key]["bytes"] and row["sha256"] == expected[key]["sha256"],
                    "runtime metadata differs from published archive bytes")
        supplied[key] = row
    require(set(supplied) == set(expected), "full original recording/timing/transcript/metadata input support required")
    observed = {}
    for key, row in supplied.items():
        root = Path(roots[key[0]]).resolve(strict=True)
        path = (root / key[1]).resolve(strict=True)
        require(path.is_relative_to(root), "input escapes its admitted root")
        observed["/".join(key)] = stream_identity(path, row)
    return observed


def validate_config(cfg):
    expected = {"name": "sentence_onset_regression", "interval_duration": 3.0, "samp_frequency": 2048,
                "test_split": 0.2, "rereference": "None", "high_gamma": False,
                "normalization": False, "despike": False}
    for key, value in expected.items():
        require(cfg.data.get(key) == value, f"source data configuration differs: {key}")
    require(cfg.data.get("val_split", 0) == 0 and cfg.data.get("train_fewshot", None) is None,
            "full source training support required")
    require(cfg.data.get("cached_data_array", None) is None, "precomputed neural-array caches are not admitted")
    require(cfg.task.name == "classification_regression_task" and cfg.task.num_repeat == 5,
            "source classification task and five training folds required")
    for key, value in {"windows_start": -1, "windows_end": 1, "window_duration": .25, "window_step": .1}.items():
        require(cfg.task.get(key) == value, f"source window configuration differs: {key}")
    require(cfg.exp.runner.name == "regression_runner_test_set" and cfg.exp.runner.num_workers == 0,
            "original held-out linear runner required")


def compose_config(source, work, prepared_dir, data_root, transcripts_root):
    # Imports occur only during an explicit admitted native execution.
    hydra = importlib.import_module("hydra")
    OmegaConf = importlib.import_module("omegaconf").OmegaConf
    kwargs = {"config_dir": str(source / "conf")}
    if "version_base" in inspect.signature(hydra.initialize_config_dir).parameters:
        kwargs["version_base"] = None
    with hydra.initialize_config_dir(**kwargs):
        cfg = hydra.compose(config_name=None, overrides=OVERRIDES)
    replacements = {
        "test.test_split_path": source / "data/all_trials.json",
        "test.test_electrodes_path": prepared_dir, "test.out_dir": work,
        "data.saved_data_split": work / "new_split_cache",
        "data.cached_transcript_aligns": work / "new_alignment_cache",
        "data.movie_transcripts_dir": transcripts_root,
        "data.data_root": data_root, "data.raw_brain_data_dir": data_root,
    }
    for key, path in replacements.items():
        require("${" not in str(path), "filesystem paths cannot contain OmegaConf interpolation syntax")
        OmegaConf.update(cfg, key, str(path), merge=False, force_add=True)
    validate_config(cfg)
    return cfg, OmegaConf.to_container(cfg, resolve=True, throw_on_missing=False)


def original_grid(author_module, cfg):
    # Uses the same actual numpy implementation and float grid as author code.
    starts = author_module.np.arange(cfg.task.windows_start, cfg.task.windows_end, cfg.task.window_step)
    duration = int(cfg.task.window_duration * 2048)
    return [{"source_key": str(float(value)), "nominal_start": float(value),
             "nominal_start_hex": float(value).hex(),
             "requested_start_sample": int((value - cfg.task.windows_start) * 2048),
             "requested_sample_count": duration,
             "plot_center": None, "actual_slice_length": "observed_separately_at_each_source_window"}
            for value in starts]


def reject_preloaded_source_modules(file_records):
    roots = {name.split("/")[0] if "/" in name else name[:-3]
             for name in file_records if name.endswith(".py")}
    for loaded in sys.modules:
        require(not any(loaded == root or loaded.startswith(root + ".") for root in roots),
                "preloaded module would shadow original author source: " + loaded)


def run_original(author_module, cfg, prepared, observer, output):
    """The numerical calls are unchanged author run_subject_test calls."""
    data_cfg = cfg.data  # Preserve the original main's data_cfg alias behavior.
    results = {}
    with observer:
        for subject, runs in prepared["recording_inventory"].items():
            observer.subject = subject
            data_cfg.subject = subject
            result = author_module.run_subject_test(data_cfg, runs, prepared["eligibility"][subject], cfg)
            require(set(result) == set(prepared["eligibility"][subject]), "source returned incomplete contact support")
            # JSON conversion follows the original source's numeric window-key serialization.
            result = loads(canonical_bytes(result))
            results[subject] = result
            write_json_exclusive(output / f"source_scores.{subject}.json", {subject: result})
    return results


def execute(args):
    args = argparse.Namespace(**vars(args))
    for name in ("source_checkout", "labels_zip", "excluded_json", "subjects_zip", "localization_zip",
                 "prepared", "data_root", "transcripts_root", "input_manifest", "output"):
        setattr(args, name, Path(getattr(args, name)).resolve())
    source = args.source_checkout
    output = args.output.resolve()
    require(not output.is_relative_to(source), "execution output must be outside author checkout")
    output.mkdir(mode=0o700, parents=False, exist_ok=False)
    started = time.monotonic()
    provenance = {"schema": "treebank-owner-source-replay/v2", "task_id": TASK_ID,
                  "status": "started", "runtime_identity": args.runtime_identity,
                  "runtime_identity_kind": "owner_supplied_label_not_image_attestation",
                  "scientific_outcome": "unqualified", "author_commit": AUTHOR_COMMIT,
                  "author_source_policy": "no_author_file_mutation",
                  "author_checkout_postcheck": {"status": "not_performed"},
                  "metadata_reconstruction": "published_exclusion_wrapper",
                  "participant_access": "owner_reference_only_arm_isolation_not_enforced_here",
                  "python": sys.version, "executable": sys.executable, "argv": sys.argv}
    evidence = None
    previous_cwd = Path.cwd()
    previous_path = list(sys.path)
    previous_bytecode = sys.dont_write_bytecode
    primary_error = None
    try:
        require(not args.data_root.is_relative_to(source) and not args.transcripts_root.is_relative_to(source),
                "keep admitted data/transcripts outside the clean author checkout")
        prepared = assemble(source, args.labels_zip, args.excluded_json, args.subjects_zip, args.localization_zip)
        supplied_raw = read_bounded(args.prepared / "prepared.json", 16 * 1024 * 1024)
        require(loads(supplied_raw) == prepared, "prepared manifest differs from complete pinned metadata rederivation")
        supplied_eligibility = loads(read_bounded(args.prepared / "sentence_onset_regression/linear_results.json", 1024 * 1024))
        require(supplied_eligibility == prepared["eligibility"], "author eligibility interface differs from authenticated support")
        provenance["prepared_sha256"] = digest(supplied_raw)
        input_raw = read_bounded(args.input_manifest, 4 * 1024 * 1024)
        declaration = loads(input_raw)
        provenance["input_manifest_sha256"] = digest(input_raw)
        provenance["owner_input_source_account"] = declaration.get("source_provenance")
        provenance["actual_inputs"] = authenticate_inputs(prepared, declaration,
                                                          {"data": args.data_root, "transcripts": args.transcripts_root})
        provenance["input_qualification_limit"] = "Hashes bind actual bytes to owner declaration; original-release provenance needs independent admission."
        reject_preloaded_source_modules(prepared["source_file_verification"]["files"])
        sys.dont_write_bytecode = True
        from observation import SourceObserver
        sys.path.insert(0, str(source))
        os.chdir(output)
        cfg, resolved = compose_config(source, output, args.prepared.resolve(), args.data_root.resolve(), args.transcripts_root.resolve())
        reject_preloaded_source_modules(prepared["source_file_verification"]["files"])
        provenance["resolved_reconstruction_config"] = resolved
        provenance["package_versions"] = {name: importlib.metadata.version(name) for name in PACKAGES}
        module = importlib.import_module("run_time_tests")
        require(Path(module.__file__).resolve() == source / "run_time_tests.py", "wrong author entry module")
        windows = original_grid(module, cfg)
        write_json_exclusive(output / "source_windows.json", windows)
        evidence = EvidenceLog(output / "observations.jsonl.gz", args.max_evidence_bytes)
        support = SupportChecks(prepared, windows)
        def record_observation(event):
            evidence.emit(event)
            for issue in support.observe(event):
                evidence.emit(issue)
        observer = SourceObserver(source, record_observation)
        scores = run_original(module, cfg, prepared, observer, output)
        provenance["source_observation"] = observer.summary
        provenance["same_case_observation"] = support.summary()
        write_json_exclusive(output / "source_scores.json", scores)
        components = collect(prepared, scores, windows)
        components["producer_context"] = {"metadata_support": "rederived_from_pinned_metadata_and_original_inventory",
                                           "source_grid": "computed_from_actual_original_config_and_numpy",
                                           "source_score_calls": "unchanged_author_run_subject_test",
                                           "scientific_admission": "not_established_by_execution_receipt"}
        write_json_exclusive(output / "figure4_components.json", components)
        try:
            provenance["source_checkout_after"] = verify_checkout(source)
        except BaseException as error:
            provenance["author_checkout_postcheck"] = {"status": "verification_failed",
                                                        "error": type(error).__name__}
            raise
        provenance["author_checkout_postcheck"] = {"status": "passed"}
        provenance["status"] = "source_computation_and_component_collection_completed"
    except BaseException as error:
        primary_error = error
        provenance["status"] = "failed"
        provenance["failure"] = {"type": type(error).__name__, "message": str(error)[:4096]}
        raise
    finally:
        cleanup_errors = []
        if evidence is not None:
            if "support" in locals():
                provenance["same_case_observation"] = support.summary()
            if "observer" in locals():
                provenance["source_observation"] = observer.summary
            try:
                evidence.close()
            except BaseException as error:
                cleanup_errors.append({"stage": "evidence_close", "type": type(error).__name__, "message": str(error)[:4096]})
            provenance["evidence"] = {"uncompressed_bytes": evidence.bytes, "records": evidence.records,
                                      "budget_bytes": evidence.limit, "required_records_truncated": False}
        try:
            os.chdir(previous_cwd)
        except BaseException as error:
            cleanup_errors.append({"stage": "cwd_restore", "type": type(error).__name__, "message": str(error)[:4096]})
        finally:
            sys.path[:] = previous_path
            sys.dont_write_bytecode = previous_bytecode
        if cleanup_errors:
            provenance["status"] = "failed"
            provenance["cleanup_failures"] = cleanup_errors
        provenance["wall_seconds"] = time.monotonic() - started
        try:
            write_json_exclusive(output / "provenance.json", provenance)
        except BaseException as error:
            if primary_error is None:
                raise
            print("Failure provenance could not be published: " + str(error)[:1000], file=sys.stderr)
        if cleanup_errors and primary_error is None:
            raise RuntimeError("private evidence finalization failed; inspect failure provenance")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source-checkout", "labels-zip", "excluded-json", "subjects-zip", "localization-zip",
                 "prepared", "data-root", "transcripts-root", "input-manifest", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--runtime-identity", required=True)
    parser.add_argument("--max-evidence-bytes", type=int, required=True)
    args = parser.parse_args()
    require(args.runtime_identity.strip(), "owner-admitted runtime identity required")
    require(args.max_evidence_bytes > 0, "positive owner-allocated evidence budget required")
    for variable in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS",
                     "VECLIB_MAXIMUM_THREADS", "BLIS_NUM_THREADS"):
        os.environ[variable] = "1"
    execute(args)


if __name__ == "__main__":
    main()
