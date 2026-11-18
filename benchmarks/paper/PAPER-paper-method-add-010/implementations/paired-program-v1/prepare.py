"""Trusted full-panel preparation after both programme closures are frozen.

No feature, classifier, prediction or scientific score is computed. Production
reads only the previously authenticated 94 prepared arrays, never the source ZIP.
"""
from __future__ import annotations

import argparse
import hashlib
import io
from pathlib import Path
import secrets
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import contract
import dependencies
from storage import (need, encoded, decoded, pin, descriptor, read, write,
                     directory, seal_public_directory)

HERE = Path(__file__).resolve().parent
TASK = "PAPER-paper-method-add-010"
PREPARED_BINDING = {"bytes": 69418,
    "sha256": "76a1d48c5bbb4f4126c9c6b4692d4a38b6cd97fa0fde3496c48281ffe3ef1e94"}
AUTHOR_REVISION = "cab648bbe2eab7093f9ab7b9a5fcddabf28e60a0"
AUTHOR_FILES = {
    "functional_connectivity_analysis/run_barycenter_pyspi_for_subject_averaged_epochs.py":
        "4a6a0b8ba1fefa22750db296dca15fabf464f61deeb6c721fc2dc7b1f83b2bdd",
    "functional_connectivity_analysis/barycenter_sq.yaml":
        "9e632969fcbf0711c4479fe9b7625b5ce5e9bd8fbd659930ac34d8838afd214a",
    "classification/fit_pyspi_classifiers.py":
        "5d84990e591d665777e90ae70a5ad1d75ba8058be559898a7b50c7a3f0855137",
    "classification/mixed_sigmoid_normalisation.py":
        "7714edb2149e597728f7d7eb23294c9758473ed1af7f45c72b6236417659127e",
    "MEG_preprocessing/combine_time_series_from_MEG.py":
        "bb25a92893f294e84294141dbdb30a89c6eb813a3409de5ee1ba53605987fe76",
    "MEG_preprocessing/extract_time_series_from_MEG.py":
        "017c29b3fdba1411b739487b7c348fb5846f767ba9708be0ef00e9008965469c",
    "requirements.txt":
        "5fadd8dd86442a6910cf525c9d54ec8520b17b79628c34c0bd309bab5006c883",
}
DATA_CAP = 13 * 1024**2
JSON_CAP = 2 * 1024**2


def file_mount(path, purpose, file_pin):
    path = Path(path).absolute()
    return {"path": str(path), "kind": "file", "purpose": purpose,
            "files": {path.name: descriptor(file_pin)}}


def tree_mount(path, purpose, files):
    return {"path": str(Path(path).absolute()), "kind": "directory", "purpose": purpose,
            "files": {name: descriptor(value) for name, value in sorted(files.items())}}


def freeze_programmes(programmes, root):
    """Both submitted sources are captured before any fold/data provider runs."""
    need(type(programmes) is dict and set(programmes) == {"A", "B"}, "both assistance programmes required")
    wrapper = read(HERE / "candidate_wrapper.py", 131072)
    captured = {role: read(programmes[role], 1048576) for role in ("A", "B")}
    need(all(captured.values()), "empty programme")
    sealed = {}
    for role in ("A", "B"):
        target = directory(root / ("program-" + role))
        files = {
            "candidate_wrapper.py": write(target / "candidate_wrapper.py", wrapper, 131072, public=True),
            "submission.py": write(target / "submission.py", captured[role], 1048576, public=True),
        }
        manifest = encoded({"schema": "meg-frozen-program/v1", "files": files})
        source_pin = write(target / "PROGRAM.json", manifest, 8192, public=True)
        files["PROGRAM.json"] = source_pin
        seal_public_directory(target)
        sealed[role] = {"source": source_pin, "mount": tree_mount(target, "program", files)}
    # This durable record precedes calls that open actual prepared data.
    write(root / "PROGRAMMES_FROZEN.json", encoded(sealed), 32768)
    return sealed


def author_capsule(source, output):
    """Copy only the seven exact published code/config/declaration files."""
    source, output = Path(source), directory(output)
    files = {}
    for relative, expected in AUTHOR_FILES.items():
        body = read(source / relative, 1048576)
        need(pin(body)["sha256"] == expected, "official source pin mismatch: " + relative)
        target = output / relative
        for parent in reversed(target.parents):
            if parent == output or output in parent.parents:
                if not parent.exists():
                    directory(parent)
        files[relative] = write(target, body, 1048576, public=True)
    seal_public_directory(output)
    return tree_mount(output, "historical_author_source", files)


def source_id(participant, category):
    return f"{participant}|{category.lower()}|Irrelevant|1000ms|on|Raw|CS-PFC|bary-sq_dtw_max"


def load_original_windows(prepared):
    """Existing reviewed loader validates the complete original preparation."""
    import numpy as np
    original = dependencies.load("inputs")
    binding, binding_pin = original.prepared_binding(prepared, with_pin=True)
    need({k: binding_pin[k] for k in ("bytes", "sha256")} == PREPARED_BINDING,
         "exact accepted full94 preparation binding required")
    records, matrices = [], {}
    for record in binding["files"]:
        values = original.load_prepared(prepared, record)
        for category in record["category_first_occurrence"]:
            rid = source_id(record["participant"], category)
            matrix = np.asarray(values[original.STIMULI.index(category)], dtype="<f8", order="C")
            need(matrix.shape == (4, 1000) and bool(np.isfinite(matrix).all()), "unchanged full regional window")
            raw = matrix.tobytes(order="C")
            records.append({"source_id": rid, "participant": record["participant"],
                "category": category.lower(), "tensor_sha256": hashlib.sha256(raw).hexdigest()})
            matrices[rid] = matrix
    final_binding = original.pin_file(Path(prepared) / "INPUT_BINDING.json", 262144)
    need({k: final_binding[k] for k in ("bytes", "sha256")} == PREPARED_BINDING,
         "preparation binding changed")
    return records, matrices, PREPARED_BINDING


def write_panel(root, records, matrices, source_binding, folds, *, key):
    """Create one anonymous bank shared by all twenty isolated programme phases."""
    import numpy as np
    panel = contract.build_panel(records, folds, key, source_binding)
    public = contract.ordered_public_windows(panel)
    joins = {row["id"]: source for source, row in contract.private_source_join(panel).items()}
    need(set(matrices) == {r["source_id"] for r in records}, "complete exact matrix membership")
    bank = np.empty((376, 4, 1000), dtype="<f8")
    for index, row in enumerate(public):
        matrix = np.asarray(matrices[joins[row["id"]]], dtype="<f8", order="C")
        need(matrix.shape == (4, 1000) and bool(np.isfinite(matrix).all()), "finite original window geometry")
        need(hashlib.sha256(matrix.tobytes(order="C")).hexdigest() == row["tensor_sha256"],
             "opaque window identity does not match the original matrix")
        bank[index] = matrix
    stream = io.BytesIO()
    np.save(stream, bank, allow_pickle=False)
    data_root = directory(root / "data")
    data_pin = write(data_root / "WINDOWS.npy", stream.getvalue(), DATA_CAP, public=True)
    private_pin = write(root / "PRIVATE_PANEL.json", encoded(panel), JSON_CAP)
    contexts_root = directory(root / "contexts")
    contexts = {}
    for fold in range(10):
        context = contract.public_context(panel, fold)
        target = directory(contexts_root / f"fold-{fold:02d}")
        context_pin = write(target / "CONTEXT.json", encoded(context), JSON_CAP, public=True)
        contexts[str(fold)] = {"context_sha256": context["context_sha256"],
            "mount": file_mount(target / "CONTEXT.json", "input", context_pin)}
    return {"panel_sha256": panel["panel_sha256"], "private_panel": private_pin,
            "data": file_mount(data_root / "WINDOWS.npy", "input", data_pin),
            "contexts": contexts, "rows": 376, "query_rows": 188,
            "original_preparation": source_binding}


def prepare(prepared, folds_path, programme_a, programme_b, paper, paper_pin,
            author_source, output):
    """Production source path; no native execution is started here."""
    root = directory(output)
    try:
        programs = freeze_programmes({"A": programme_a, "B": programme_b}, root)
        paper_body = read(paper, 32 * 1024**2, descriptor(paper_pin))
        paper_root = directory(root / "paper")
        paper_file = write(paper_root / "PAPER.bin", paper_body, 32 * 1024**2, public=True)
        seal_public_directory(paper_root)
        paper_mount = tree_mount(paper_root, "paper", {"PAPER.bin": paper_file})
        author = author_capsule(author_source, root / "author")
        instructions = read(HERE / "PARTICIPANT.md", 65536)
        instructions_root = directory(root / "contract")
        instruction_pin = write(instructions_root / "PARTICIPANT.md", instructions, 65536, public=True)
        seal_public_directory(instructions_root)
        instruction_mount = tree_mount(instructions_root, "contract", {"PARTICIPANT.md": instruction_pin})
        fold_document = decoded(read(folds_path, 131072))
        need(type(fold_document) is dict and set(fold_document) == {"folds", "evidence"}
             and type(fold_document["evidence"]) is str and 0 < len(fold_document["evidence"]) <= 4096,
             "explicit complete externally selected fold map and evidence required")
        records, matrices, source_binding = load_original_windows(prepared)
        panel = write_panel(root, records, matrices, source_binding, fold_document["folds"], key=secrets.token_bytes(32))
        value = {"schema": "meg-prepared-paired-campaign/v1", "task_id": TASK,
            **panel, "programmes": programs, "paper": paper_mount, "author": author,
            "contract": instruction_mount, "fold_evidence": fold_document["evidence"],
            "historical_folds_authenticated": False, "source_revision": AUTHOR_REVISION,
            "freeze_order": "both programmes frozen before any original windows or fold labels were prepared",
            "preparation_only": True, "native_phases": 0, "scientific_results": False}
        write(root / "PREPARED.json", encoded(value), JSON_CAP)
        return value
    except BaseException as error:
        write(root / "FAILED.json", encoded({"schema": "meg-paired-preparation-failure/v1",
            "error_type": type(error).__name__, "partial_outputs_retained": True,
            "automatic_retry": False}), 8192)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("prepared", "folds", "programme-a", "programme-b", "paper", "paper-pin-json", "author-source", "output"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    value = prepare(args.prepared, args.folds, args.programme_a, args.programme_b,
                    args.paper, decoded(read(args.paper_pin_json, 8192)), args.author_source, args.output)
    print(encoded({"status": "prepared", "panel_sha256": value["panel_sha256"],
                   "windows": value["rows"], "queries_per_condition": value["query_rows"]}).decode())


if __name__ == "__main__":
    main()
