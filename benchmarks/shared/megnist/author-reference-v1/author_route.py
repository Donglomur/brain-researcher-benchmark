"""MegNIST author-method fitting without test-label or test-score access.

This external adapter is construction evidence, not permission to run authentic
data. Its functions are usable on generated fixtures; the separate preflight
must establish the complete original input/panel scope before any later run.
The exact upstream module is retained unchanged under its MIT license.
"""
from __future__ import annotations

from collections.abc import Mapping
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
from types import ModuleType
from typing import Any


AUTHOR_SHA256 = "f377af312dd066691e5f046b5ead51c5f77745ffbd908850cc49a5d95061ab18"
LICENSE_SHA256 = "23514a4ae3e85260e2e49e8ce6528e274139f6a55762cd573afb0669af9b5e8c"
AUTHOR_PATH = (Path(__file__).resolve().parent /
               "author-source/run_hyperparameter_search.py")
LICENSE_PATH = AUTHOR_PATH.with_name("LICENSE")
NORMALIZATION_METHOD = "author-sequential-welford-population-v1"
_AUTHOR_MODULE: ModuleType | None = None


def file_sha256(path: str | Path) -> str:
    """Hash file bytes without importing/executing a source or array object."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sha(value: str, name: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError(f"{name} must be an explicit lowercase SHA-256")
    return value


def _verified_file(path: str | Path, expected_sha256: str, name: str) -> Path:
    expected_sha256 = _sha(expected_sha256, name)
    result = Path(path).resolve(strict=True)
    if not result.is_file() or file_sha256(result) != expected_sha256:
        raise ValueError(f"{name} content identity mismatch")
    return result


def load_author_source() -> ModuleType:
    """Import only the fixed reviewed trainer, without invoking its main().

    Calling this imports installed scientific packages. Do so only inside the
    approved generated-control pool or a separately authorized execution.
    Hashes are checked on every call, including after the module was imported.
    """
    global _AUTHOR_MODULE
    _verified_file(AUTHOR_PATH, AUTHOR_SHA256, "author source")
    _verified_file(LICENSE_PATH, LICENSE_SHA256, "author license")
    if _AUTHOR_MODULE is None:
        name = "_megnist_reviewed_author_f377af312dd0"
        spec = importlib.util.spec_from_file_location(name, AUTHOR_PATH)
        if spec is None or spec.loader is None:
            raise RuntimeError("Cannot load the pinned author source")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        try:
            spec.loader.exec_module(module)
        except BaseException:
            sys.modules.pop(name, None)
            raise
        _AUTHOR_MODULE = module
    return _AUTHOR_MODULE


def _labeled_shape(author: ModuleType, path: Path) -> tuple[int, tuple[int, ...]]:
    with author.h5py.File(path, "r") as handle:
        if "data" not in handle or "labels" not in handle:
            raise ValueError("Training/validation input needs data and labels")
        shape = tuple(handle["data"].shape)
        if len(shape) < 2 or shape[0] < 1 or any(x < 1 for x in shape[1:]):
            raise ValueError("Input data must have nonempty rows and features")
        labels = handle["labels"]
        if tuple(labels.shape) != (shape[0],):
            raise ValueError("Label cardinality/shape does not match input rows")
        if not author.np.issubdtype(labels.dtype, author.np.integer):
            raise ValueError("Labels must use an integer dtype")
        values = labels[:]
        if author.np.any(values < 0) or author.np.any(values >= 10):
            raise ValueError("Labels must be original digit classes 0 through 9")
    return shape[0], shape[1:]


def _array_spec(array: Any) -> dict[str, Any]:
    return {"dtype": array.dtype.str, "shape": list(array.shape),
            "sha256": hashlib.sha256(array.tobytes(order="C")).hexdigest()}


def _normalization_provenance(author: ModuleType, mean: Any, std: Any,
                              train_sha256: str, rows: int,
                              sample_shape: tuple[int, ...]) -> dict[str, Any]:
    return {
        "schema": "megnist-training-normalization/v1",
        "source_sha256": AUTHOR_SHA256,
        "train_sha256": train_sha256,
        "training_rows": rows,
        "sample_shape": list(sample_shape),
        "flattened_features": int(author.np.prod(sample_shape)),
        "method": NORMALIZATION_METHOD,
        "statistics_batch_size": 1000,
        "mean": _array_spec(mean),
        "std": _array_spec(std),
    }


def _validated_normalization(author: ModuleType, normalization: dict[str, Any],
                             train_sha256: str, rows: int,
                             sample_shape: tuple[int, ...]) -> dict[str, Any]:
    if not isinstance(normalization, dict):
        raise ValueError("Normalization must contain arrays and provenance")
    features = int(author.np.prod(sample_shape))
    arrays = {}
    for name in ("mean", "std"):
        value = normalization.get(name)
        if not isinstance(value, author.np.ndarray):
            raise ValueError(f"Normalization {name} must be a numeric array")
        if value.dtype != author.np.dtype("float64") or value.shape != (features,):
            raise ValueError(f"Normalization {name} has incorrect shape/dtype")
        if not author.np.isfinite(value).all():
            raise ValueError(f"Normalization {name} contains nonfinite values")
        if name == "std" and author.np.any(value <= 0):
            raise ValueError("Normalization standard deviations must be positive")
        arrays[name] = author.np.array(value, copy=True, order="C")
    expected = _normalization_provenance(
        author, arrays["mean"], arrays["std"], train_sha256, rows, sample_shape)
    if normalization.get("provenance") != expected:
        raise ValueError("Normalization source/training/array provenance mismatch")
    for value in arrays.values():
        value.flags.writeable = False
    return {**arrays, "provenance": expected, "cache": normalization.get("cache")}


def normalization_for_training(
    train_path: str | Path, *, expected_train_sha256: str,
    cache_path: str | Path | None = None,
    expected_cache_provenance_sha256: str | None = None,
) -> dict[str, Any]:
    """Use exact author training-only Welford, or an explicitly pinned cache.

    A cache is numeric NPZ (mean/std only) plus ``<cache_path>.json``. Existing
    caches require the caller's independently trusted SHA of that JSON sidecar;
    the sidecar in turn binds NPZ bytes, source, actual training bytes and arrays.
    This verifies declared identities, not receipt provenance or runtime isolation.
    The function never reads a test file or runs a model.
    """
    author = load_author_source()
    train = _verified_file(train_path, expected_train_sha256, "training input")
    rows, sample_shape = _labeled_shape(author, train)
    cache = Path(cache_path).resolve() if cache_path is not None else None
    sidecar = Path(str(cache) + ".json") if cache is not None else None

    if cache is not None and (cache.exists() or sidecar.exists()):
        if not cache.is_file() or not sidecar.is_file():
            raise ValueError("Incomplete normalization cache pair")
        if expected_cache_provenance_sha256 is None:
            raise ValueError("Existing cache requires a trusted provenance SHA-256")
        _verified_file(sidecar, expected_cache_provenance_sha256, "cache provenance")
        record = json.loads(sidecar.read_text(encoding="utf-8"))
        if set(record) != {"schema", "cache_sha256", "provenance"} or record["schema"] != "megnist-normalization-cache/v1":
            raise ValueError("Unexpected normalization cache record")
        _verified_file(cache, record["cache_sha256"], "normalization cache")
        with author.np.load(cache, allow_pickle=False) as stored:
            if set(stored.files) != {"mean", "std"}:
                raise ValueError("Normalization cache must contain only mean/std")
            result = {"mean": stored["mean"], "std": stored["std"],
                      "provenance": record["provenance"]}
        result["cache"] = {
            "data_path": str(cache), "provenance_path": str(sidecar),
            "data_sha256": record["cache_sha256"],
            "provenance_sha256": expected_cache_provenance_sha256,
        }
        result = _validated_normalization(author, result, expected_train_sha256,
                                           rows, sample_shape)
        _verified_file(train, expected_train_sha256, "training input after cache use")
        return result

    if expected_cache_provenance_sha256 is not None:
        raise ValueError("Expected cache provenance was supplied but cache is absent")

    # Call the exact reviewed operation, including source row order, float64
    # accumulators, population denominator, and zero-std replacement.
    mean, std = author.compute_dataset_statistics(train, batch_size=1000)
    _verified_file(train, expected_train_sha256, "training input after statistics")
    result = {"mean": mean, "std": std,
              "provenance": _normalization_provenance(
                  author, mean, std, expected_train_sha256, rows, sample_shape),
              "cache": None}
    result = _validated_normalization(author, result, expected_train_sha256,
                                       rows, sample_shape)
    if cache is not None:
        cache.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive creation preserves failed/incomplete writes for diagnosis.
        with cache.open("xb") as handle:
            author.np.savez_compressed(handle, mean=result["mean"], std=result["std"])
        record = {"schema": "megnist-normalization-cache/v1",
                  "cache_sha256": file_sha256(cache),
                  "provenance": result["provenance"]}
        with sidecar.open("x", encoding="utf-8") as handle:
            json.dump(record, handle, sort_keys=True, indent=2)
            handle.write("\n")
        result["cache"] = {
            "data_path": str(cache), "provenance_path": str(sidecar),
            "data_sha256": record["cache_sha256"],
            "provenance_sha256": file_sha256(sidecar),
        }
    return result


def model_state_sha256(model: Any) -> str:
    """Digest named numeric parameter/buffer tensors without loading author code.

    This is a tensor-state identity, not authentication of model code, arbitrary
    Python attributes, architecture/configuration, or isolation. Callers must
    bind those separately. Unsupported/non-numeric state is rejected, never
    skipped. The same helper is used by fitting and private inference.
    """
    if not callable(getattr(model, "state_dict", None)):
        raise ValueError("Model needs an explicit numeric state_dict interface")
    state = model.state_dict()
    if not isinstance(state, Mapping) or any(not isinstance(name, str) for name in state):
        raise ValueError("Model state must map string names to numeric tensors")
    digest = hashlib.sha256()
    for name, tensor in sorted(state.items()):
        try:
            value = tensor.detach().cpu().contiguous().numpy()
        except (AttributeError, TypeError, RuntimeError, NotImplementedError) as exc:
            raise ValueError(f"Unsupported model state tensor: {name}") from exc
        if value.dtype.kind not in "biufc" or value.dtype.hasobject:
            raise ValueError(f"Non-numeric model state tensor: {name}")
        header = json.dumps({"name": name, "dtype": value.dtype.str,
                             "shape": list(value.shape)}, sort_keys=True,
                            separators=(",", ":")).encode("utf-8")
        digest.update(len(header).to_bytes(8, "big"))
        digest.update(header)
        digest.update(value.tobytes(order="C"))
    return digest.hexdigest()


def fit_reference_run(
    train_path: str | Path, val_path: str | Path, *,
    expected_train_sha256: str, expected_val_sha256: str,
    normalization: dict[str, Any], hidden_size: int, seed: int,
    device: str = "cpu", batch_size: int = 32, max_epochs: int = 200,
    learning_rate: float = 1e-3, patience: int = 20, num_workers: int = 0,
) -> dict[str, Any]:
    """Fit one source-method run using training and validation files only.

    This primitive intentionally permits tiny generated fixtures. It does NOT
    assert the full reference shape, 70-cell scope or scientific qualification;
    those are separately checked before any later authorized authentic run.
    Returned model state is frozen for inference but remains a mutable Python
    object: the private prediction owner must recheck ``model_state_sha256``.
    """
    author = load_author_source()
    for name, value, lower in (("hidden_size", hidden_size, 1), ("seed", seed, 0),
                               ("batch_size", batch_size, 1), ("max_epochs", max_epochs, 1),
                               ("patience", patience, 1), ("num_workers", num_workers, 0)):
        if isinstance(value, bool) or not isinstance(value, int) or value < lower:
            raise ValueError(f"Invalid {name}")
    if isinstance(learning_rate, bool) or not isinstance(learning_rate, (int, float)) or not author.np.isfinite(learning_rate) or learning_rate <= 0:
        raise ValueError("learning_rate must be positive and finite")
    if author.torch.get_default_dtype() != author.torch.float32:
        raise ValueError("Source fitting requires ordinary float32 Torch default dtype")
    if str(author.torch.get_default_device()) != "cpu":
        raise ValueError("Source initialization requires ordinary CPU default device")

    train = _verified_file(train_path, expected_train_sha256, "training input")
    val = _verified_file(val_path, expected_val_sha256, "validation input")
    if train == val:
        raise ValueError("Training and validation paths must be distinct")
    rows, sample_shape = _labeled_shape(author, train)
    val_rows, val_shape = _labeled_shape(author, val)
    if val_shape != sample_shape:
        raise ValueError("Training/validation sample shapes differ")
    normalized = _validated_normalization(author, normalization,
                                           expected_train_sha256, rows, sample_shape)

    # Preserve source make_loaders' first reset, exact dataset class, loader
    # kwargs/order and train worker_init_fn. No explicit DataLoader generator.
    # The unused test Dataset/loader is deliberately not created or accessed.
    author.set_all_seeds(seed)
    train_dataset = author.HDF5Dataset(train, normalized["mean"], normalized["std"])
    val_dataset = author.HDF5Dataset(val, normalized["mean"], normalized["std"])
    common = {"batch_size": batch_size, "num_workers": num_workers,
              "pin_memory": author.torch.cuda.is_available()}
    train_loader = author.DataLoader(train_dataset, shuffle=True,
                                    worker_init_fn=author.worker_init_fn, **common)
    val_loader = author.DataLoader(val_dataset, shuffle=False, **common)
    input_size = int(author.np.prod(train_dataset.data_shape))

    # Preserve source run_once's second reset immediately before model init.
    author.set_all_seeds(seed)
    torch_device = author.torch.device(device)
    model = author.SimpleMLP(input_size, hidden_size, num_classes=10).to(torch_device)
    trained = author.train_model(model, train_loader, val_loader, torch_device,
                                 max_epochs=max_epochs, learning_rate=learning_rate,
                                 patience=patience)
    _verified_file(train, expected_train_sha256, "training input after fitting")
    _verified_file(val, expected_val_sha256, "validation input after fitting")
    trained_model = trained["model"]
    trained_model.eval()
    trained_model.requires_grad_(False)
    digest = model_state_sha256(trained_model)
    metadata = {
        "source_sha256": AUTHOR_SHA256,
        "train_sha256": expected_train_sha256,
        "val_sha256": expected_val_sha256,
        "training_rows": rows, "validation_rows": val_rows,
        "sample_shape": list(sample_shape), "input_size": input_size,
        "hidden_size": hidden_size, "seed": seed,
        "batch_size": batch_size, "max_epochs": max_epochs,
        "learning_rate": learning_rate, "patience": patience,
        "num_workers": num_workers, "device": str(torch_device),
        "torch_version": author.torch.__version__,
        "numpy_version": author.np.__version__,
        "h5py_version": author.h5py.__version__,
        "historical_runtime_lock_authenticated": False,
        "best_val_acc": trained["best_val_acc"],
        "best_epoch": trained["best_epoch"],
        "train_accs": list(trained["train_accs"]),
        "val_accs": list(trained["val_accs"]),
        "model_state_sha256": digest,
        "no_test_evaluation_path_executed": True,
        "input_roles_require_preflight": True,
        "test_result_emitted": False,
        "complete_reference_scope_validated": False,
        "scientific_qualification": False,
        "adapter_delta": "No unused test loader or post-fit test iteration. Subsequent source runs reset seeds; whole-process post-fit RNG equivalence is not claimed. Inference export precedes model disposal and checks this state digest.",
    }
    return {"model": trained_model, "normalization": normalized, "metadata": metadata}


def run_reference_panel(
    input_manifest_path: str | Path, *, candidate_root: str | Path,
    private_join_path: str | Path, expected_private_join_sha256: str,
    output_root: str | Path, device: str = "cpu",
    normalization_cache_path: str | Path | None = None,
    expected_cache_provenance_sha256: str | None = None,
) -> dict[str, Any]:
    """Run the complete 70-cell author reference in an operator-private context.

    INVOKING THIS FUNCTION PERFORMS AUTHENTIC TRAINING AND TEST EVALUATION.
    Source recovery and construction approval do not authorize such a call.
    It requires separate execution authorization, a measured resource plan and
    a trusted operator environment. During construction only dependencies may
    be mocked to exercise the 70-cell control flow; no authentic file is read.

    The original input manifest and private target identity are fixed below.
    No reduced grid or training-profile override is accepted. Candidate
    improvement is a separate route and is NOT constrained to this grid.
    Output permissions/path checks do not qualify actual runtime isolation.
    The optional 71st representative-checkpoint refit is deliberately absent.
    """
    # Lazy imports avoid a fit/prediction cycle and keep import-time behavior
    # free of source loading, input access and execution.
    import gc
    import math
    import os
    import preflight
    import prediction_interface
    import evaluate_private
    import summarize_reference as reference_summary

    accepted_manifest_sha256 = "ec53db9a60779e01ee05496833418355151781afff7b02f9db20a879029ace02"
    accepted_join_sha256 = "98b85d94724611df9e79b821bf0fadc1a8af54b239c4db70de180307a5bddf36"
    widths = (32, 64, 128, 256, 512, 1024, 2048)
    seeds = tuple(range(42, 52))
    if expected_private_join_sha256 != accepted_join_sha256:
        raise ValueError("Full reference requires the accepted original private test join")
    candidate = Path(candidate_root).resolve(strict=True)
    if not candidate.is_dir():
        raise ValueError("candidate_root must be an explicit existing directory")
    declared_output = Path(output_root)
    if declared_output.exists() or declared_output.is_symlink():
        raise FileExistsError("Reference output_root must be new; no partial-run reuse")
    output = declared_output.resolve()
    if not output.parent.is_dir():
        raise ValueError("Create the trusted private parent directory separately")
    join = Path(private_join_path).resolve(strict=True)
    preflight.check_path_separation(candidate, output)
    preflight.check_path_separation(candidate, join.parent)
    source_check = preflight.verify_source_identity(AUTHOR_PATH, AUTHOR_SHA256)
    inputs = preflight.validate_input_manifest(
        input_manifest_path, profile="reference",
        expected_sha256=accepted_manifest_sha256, root=candidate,
        inspect_files=True, feature_shape=(306, 250))
    if (inputs.get("manifest_sha256") != accepted_manifest_sha256
            or inputs.get("feature_shape") != [306, 250]
            or not inputs.get("file_identities_verified")
            or not inputs.get("header_shapes_verified")):
        raise ValueError("Reference input preflight did not verify the original support")
    splits = inputs["splits"]
    for split, rows in (("train", 10000), ("val", 1000), ("test", 1000)):
        if splits[split]["rows"] != rows:
            raise ValueError("Reference split cardinality changed")
    join = _verified_file(join, accepted_join_sha256, "original private test join")

    # Private POSIX permissions are a local precaution, not proof of an
    # enforced candidate/operator boundary (same-user access remains possible).
    output.mkdir(mode=0o700)
    output.chmod(0o700)
    if output.stat().st_mode & 0o077:
        raise ValueError("Reference output directory must be owner-only")

    def write_private_json(path: Path, value: dict[str, Any]) -> None:
        encoded = (json.dumps(value, sort_keys=True, indent=2,
                              allow_nan=False) + "\n").encode("utf-8")
        if len(encoded) > 1024 * 1024:
            raise ValueError("Reference JSON artifact exceeds the bounded metadata size")
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded)

    def identity(path: Path, role: str) -> dict[str, Any]:
        return {"role": role, "path": str(path), "bytes": path.stat().st_size,
                "sha256": file_sha256(path)}

    limits = {"visibility": "trusted_operator_and_evaluator_private",
              "scientific_qualification": False, "runtime_isolation_qualified": False,
              "reproduction_status": "unknown", "improvement_status": "unknown",
              "optional_71st_checkpoint_refit_performed": False,
              "candidate_grid_required": False}
    started = {"scope": "complete_original_70_cell_reference_only",
               "manifest_sha256": accepted_manifest_sha256,
               "private_join_sha256": accepted_join_sha256,
               "source_sha256": AUTHOR_SHA256, "widths": list(widths),
               "seeds": list(seeds), "source_profile": {
                   "batch_size": 32, "max_epochs": 200, "learning_rate": 1e-3,
                   "patience": 20, "num_workers": 0, "device": device},
               **limits}
    write_private_json(output / "RUN_STARTED.json", started)
    artifacts = [identity(output / "RUN_STARTED.json", "private_run_start")]
    records: list[dict[str, Any]] = []
    current_cell = None
    try:
        cache = (Path(normalization_cache_path).resolve()
                 if normalization_cache_path is not None
                 else output / "training_standardisation.npz")
        normalization = normalization_for_training(
            splits["train"]["path"],
            expected_train_sha256=splits["train"]["sha256"], cache_path=cache,
            expected_cache_provenance_sha256=expected_cache_provenance_sha256)
        if normalization.get("cache") is None:
            raise ValueError("Panel normalization must have a bound cache artifact")
        cache_record = normalization["cache"]
        for field, digest_key, role in (
                ("data_path", "data_sha256", "training_normalization_arrays"),
                ("provenance_path", "provenance_sha256", "training_normalization_provenance")):
            path = _verified_file(cache_record[field], cache_record[digest_key], role)
            artifacts.append(identity(path, role))

        author = load_author_source()
        for width in widths:
            for seed in seeds:
                current_cell = {"hidden_size": width, "seed": seed}
                cell = output / f"width_{width}_seed_{seed}"
                cell.mkdir(mode=0o700)
                fitted = payload = scored = None
                try:
                    fitted = fit_reference_run(
                        splits["train"]["path"], splits["val"]["path"],
                        expected_train_sha256=splits["train"]["sha256"],
                        expected_val_sha256=splits["val"]["sha256"],
                        normalization=normalization, hidden_size=width, seed=seed,
                        device=device, batch_size=32, max_epochs=200,
                        learning_rate=1e-3, patience=20, num_workers=0)
                    fit_metadata = fitted["metadata"]
                    for key, expected in (
                            ("hidden_size", width), ("seed", seed),
                            ("source_sha256", AUTHOR_SHA256),
                            ("train_sha256", splits["train"]["sha256"]),
                            ("val_sha256", splits["val"]["sha256"])):
                        if fit_metadata.get(key) != expected:
                            raise ValueError(f"Fit metadata changed reference {key}")
                    if fitted["normalization"]["provenance"] != normalization["provenance"]:
                        raise ValueError("Fit changed the single training normalization")
                    frozen_state = _sha(fit_metadata["model_state_sha256"], "fitted model state")
                    if model_state_sha256(fitted["model"]) != frozen_state:
                        raise ValueError("Fitted model changed before private prediction")
                    test = _verified_file(splits["test"]["path"],
                                          splits["test"]["sha256"], "test features before prediction")
                    payload = prediction_interface.predict_h5(
                        fitted["model"], test,
                        fitted["normalization"]["mean"], fitted["normalization"]["std"],
                        expected_model_state_sha256=frozen_state,
                        batch_size=32, device=device, expected_rows=1000,
                        expected_shape=(306, 250))
                    _verified_file(test, splits["test"]["sha256"], "test features after prediction")
                    if payload["model_state_sha256"] != frozen_state:
                        raise ValueError("Prediction export changed the fitted state identity")
                    prediction_path = cell / "predictions.h5"
                    prediction_interface.write_predictions(prediction_path, payload)
                    prediction_path.chmod(0o600)
                    _verified_file(join, accepted_join_sha256, "private test join before scoring")
                    scored = evaluate_private.evaluate_files(
                        prediction_path, join, expected_rows=1000)
                    _verified_file(join, accepted_join_sha256, "private test join after scoring")
                    if (scored["num_cases"] != 1000
                            or isinstance(scored["correct_count"], bool)
                            or not isinstance(scored["correct_count"], int)
                            or not 0 <= scored["correct_count"] <= 1000
                            or scored["accuracy_percent"] != 100.0 * scored["correct_count"] / 1000):
                        raise ValueError("Private score does not preserve complete-case source accuracy")
                    val_acc = fit_metadata["best_val_acc"]
                    if isinstance(val_acc, bool) or not math.isfinite(val_acc) or not 0 <= val_acc <= 100:
                        raise ValueError("Invalid reference validation accuracy")
                    prediction_identity = identity(prediction_path, "private_per_case_predictions")
                    run_record = {"hidden_size": width, "seed": seed,
                                  "val_acc": val_acc, "test_acc": scored["accuracy_percent"],
                                  "num_cases": 1000, "correct_count": scored["correct_count"],
                                  "model_state_sha256": frozen_state,
                                  "prediction_artifact": prediction_identity,
                                  **limits}
                    metadata_path = cell / "fit_and_private_score.json"
                    write_private_json(metadata_path, {
                        "record": run_record, "fit_metadata": fit_metadata,
                        "normalization_provenance": normalization["provenance"],
                        "manifest_sha256": accepted_manifest_sha256,
                        "private_join_sha256": accepted_join_sha256,
                        "test_feature_sha256": splits["test"]["sha256"],
                        "per_case_derivation": "Retained predictions plus the exact private join independently determine all case-level correctness; no targets are written into candidate inputs.",
                        **limits})
                    run_record["metadata_artifact"] = identity(metadata_path, "private_fit_and_score_metadata")
                    artifacts.extend((prediction_identity, run_record["metadata_artifact"]))
                    records.append(run_record)
                finally:
                    # No model is retained in records or artifact metadata.
                    # Each next fit again performs the original seed resets.
                    fitted = payload = scored = None
                    gc.collect()
                    if author.torch.cuda.is_available():
                        author.torch.cuda.empty_cache()

        summary = reference_summary.summarize_reference(records)
        if len(records) != 70 or summary.get("scope") != "complete_original_reference_baseline_grid":
            raise ValueError("No complete reference summary was produced")
        _verified_file(join, accepted_join_sha256, "private test join at panel completion")
        complete_path = output / "COMPLETE_REFERENCE_PANEL.json"
        write_private_json(complete_path, {
            "records": records, "summary": summary,
            "normalization_provenance": normalization["provenance"],
            "source_identity": source_check, "input_preflight": inputs,
            "private_join_sha256": accepted_join_sha256,
            "execution_completed_cells": 70, **limits})
        artifacts.append(identity(complete_path, "complete_private_reference_panel"))
        return {"records": records, "summary": summary, "artifacts": artifacts,
                "normalization_provenance": normalization["provenance"],
                "output_root": str(output), "execution_completed_cells": 70, **limits}
    except BaseException as exc:
        # Preserve partial artifacts without creating a complete summary or
        # claiming partial scientific success. Reuse/resume requires new review.
        write_private_json(output / "RUN_FAILED.json", {
            "completed_cells": len(records), "failed_cell": current_cell,
            "error_type": type(exc).__name__, "error": str(exc)[:4096],
            "complete_reference_panel": False, **limits})
        raise


if __name__ == "__main__":
    raise SystemExit("Library only: no automatic authentic training, downloads or test evaluation.")
