"""Owner-side static projection of the public NuCLR Bugeon split release.

No source pickle is executed and no pandas/NumPy dependency is imported. Exact
DataFrame/ndarray storage layouts are interpreted only after inert parsing.
"""
import argparse
from collections import Counter
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import zipfile

from inert_pickle import FormatError, Record, Symbol, parse, require

ARCHIVE_SHA256 = "e168d754a2a9a281e66694aaa6a5e591cf337dceac0dbf198ae432ac8fb65d81"
SOURCE_COMMIT = "0fa409b304147ace00507063d44f03155691af62"
SOURCE_URL = "https://ik.imagekit.io/7tkfmw7hc/nuclr/splits.zip"
PANEL_SUFFIX = {"transductive": "transductive", "transductive_zero_shot": "transductive_zs", "inductive_zero_shot": "inductive_zs"}
LABELS = {
    "ei": {"EC", "IN"},
    "subclass": {"Lamp5", "Pvalb", "Vip", "Sncg", "Sst"},
    "11class": {"Lamp5-Chrna7", "Lamp5-Npy", "Lamp5-Tmem182", "Pvalb-Tac1", "Pvalb-Vipr2", "Sncg-Pdzrn3", "Sncg-Vip", "Sst-Reln", "Sst-Tac1", "Vip-Cp", "Vip-Reln"},
}
UNIT = re.compile(r"(sb(?:025|026|028|030)_[0-9]{8})_u(0|[1-9][0-9]*)\Z")
DEV_SESSIONS = {"sb025_20191004", "sb026_20191011", "sb028_20191106", "sb030_20200108"}


def record(value, name):
    require(isinstance(value, Record) and value.constructor.name == name, "unexpected source storage record: " + name)
    return value


def array(value, *, ndim=1):
    """Read only the object-string ndarray encoding used by this pinned pack."""
    r = record(value, "numpy.core.multiarray._reconstruct")
    require(len(r.args) == 3 and isinstance(r.args[0], Symbol) and r.args[0].name == "numpy.ndarray" and r.args[1:] == ((0,), b"b"), "ndarray reconstruction arguments")
    state = r.state
    require(type(state) is tuple and len(state) == 5 and state[0] == 1, "ndarray storage version")
    shape, dtype, fortran, data = state[1:]
    require(type(shape) is tuple and len(shape) == ndim and all(type(n) is int and 0 < n <= 100_000 for n in shape), "ndarray dimensions")
    d = record(dtype, "numpy.dtype")
    require(d.args == ("O8", False, True) and d.state == (3, "|", None, None, None, -1, -1, 63), "only source object-string dtype supported")
    require(type(fortran) is bool and type(data) is list, "ndarray storage layout")
    extent = 1
    for n in shape: extent *= n
    require(len(data) == extent and all(type(x) is str and x for x in data), "ndarray string payload/extent")
    return list(data), shape


def index(value):
    r = record(value, "pandas.core.indexes.base._new_Index")
    require(r.state is None and len(r.args) == 2 and isinstance(r.args[0], Symbol) and r.args[0].name == "pandas.core.indexes.base.Index", "source index constructor")
    state = r.args[1]
    require(type(state) is dict and set(state) == {"data", "name"}, "source index fields")
    return array(state["data"])[0]


def label_frame(value):
    """Decode an exactly one-column, one-block source DataFrame by its axes."""
    frame = record(value, "pandas.core.frame.DataFrame")
    require(frame.args == () and type(frame.state) is dict, "source DataFrame structure")
    require(set(frame.state) == {"_mgr", "_typ", "_metadata", "attrs", "_flags"} and frame.state["_typ"] == "dataframe" and frame.state["_metadata"] == [] and frame.state["attrs"] == {} and frame.state["_flags"] == {"allows_duplicate_labels": True}, "unsupported DataFrame metadata")
    manager = record(frame.state.get("_mgr"), "pandas.core.internals.managers.BlockManager")
    require(manager.state is None and len(manager.args) == 2, "source BlockManager structure")
    blocks, axes = manager.args
    require(type(blocks) is tuple and len(blocks) == 1 and type(axes) is list and len(axes) == 2, "one-column source label frame required")
    columns, ids = index(axes[0]), index(axes[1])
    require(len(columns) == 1 and len(ids) == len(set(ids)), "label-frame column/identity mismatch")
    block = record(blocks[0], "pandas._libs.internals._unpickle_block")
    require(block.state is None and len(block.args) == 3 and block.args[2] == 2, "source label-block dimensions")
    values, shape = array(block.args[0], ndim=2)
    placement = record(block.args[1], "builtins.slice")
    require(placement.args == (0, 1, 1) and placement.state is None, "source label-block placement")
    require(shape == (1, len(ids)), "label axis/value order mismatch")
    return dict(zip(ids, values)), columns[0]


def id_list(value):
    ids, _ = array(value)
    require(len(ids) == len(set(ids)) and all(UNIT.fullmatch(x) for x in ids), "duplicate or malformed source unit IDs")
    return ids


def project(raw, label_level, panel):
    require(label_level in LABELS and panel in PANEL_SUFFIX, "unknown original panel")
    root = parse(raw)
    require(type(root) is dict and set(root) == {"label_map", "splits"}, "source split root fields")
    labels, column = label_frame(root["label_map"])
    require(set(labels.values()) == LABELS[label_level], "source label family mismatch; no guessed encoding")
    require(all(UNIT.fullmatch(x) for x in labels), "label-map source identity syntax")
    metadata = []
    for uid in labels:
        match = UNIT.fullmatch(uid)
        session = match.group(1)
        metadata.append({"id": uid, "session_id": session, "subject_id": session.split("_")[0], "source_neuron_index": int(match.group(2))})
    source_splits = root["splits"]
    if type(source_splits) is dict: source_splits = [source_splits]
    require(type(source_splits) is list and source_splits, "source split collection")
    splits = []
    for n, source in enumerate(source_splits):
        require(type(source) is dict and set(source) in ({"train", "val", "test"}, {"train", "train_cv", "test"}, {"train_cv", "test"}), "source split fields")
        split = {"id": f"source-{n}"}
        for key, value in source.items():
            if key == "train_cv":
                require(type(value) is list and value, "source train_cv collection")
                folds = []
                for fold in value:
                    require(type(fold) is dict and set(fold) == {"train", "val"}, "source CV fields")
                    folds.append({k: id_list(v) for k,v in fold.items()})
                split[key] = folds
            else: split[key] = id_list(value)
        # The source's omitted outer train means the complete label-map complement.
        # Keep omission in the projection; do not generate or reorder a new split.
        coverage = set(split["test"])
        coverage.update(split.get("train", set(labels)-coverage))
        coverage.update(split.get("val", []))
        omitted = set(labels) - coverage
        require(coverage <= set(labels), "source split contains unknown labeled units")
        require(all(UNIT.fullmatch(uid).group(1) in DEV_SESSIONS for uid in omitted), "source split omits nondevelopment labeled units; exclusion provenance unresolved")
        if omitted:
            split["excluded"] = {uid: "Author split omits source development session " + UNIT.fullmatch(uid).group(1) for uid in labels if uid in omitted}
        splits.append(split)
    result = {"schema": "nuclr_bugeon_source_projection_v2", "source_commit": SOURCE_COMMIT,
              "source_member_sha256": hashlib.sha256(raw).hexdigest(),
              "source_member": f"splits/bugeon/{label_level}_{PANEL_SUFFIX[panel]}.pkl",
              "label_level": label_level, "panel": panel, "source_label_column": column,
              "label_map": labels, "metadata": metadata, "splits": splits}
    return result


def validate_topology(projection):
    """Reuse the existing complete cohort validator with inert dummy embeddings.

    This performs validation only: no fit, scaling, inference or metric is called.
    The dummy matrix never leaves this function and is not an observation.
    """
    module = _evaluator()
    packet = _validation_packet(projection, module=module)
    packet["checkpoints"] = [{"id": "validation-only", "epoch": 0, "ids": list(projection["label_map"]), "embeddings": [[0] for _ in projection["label_map"]]}]
    module.validate_packet(packet)


def topology_audit(projection):
    """Report source incompatibility without repairing or discarding source IDs."""
    try:
        validate_topology(projection)
        error = None
    except ValueError as exc:
        # Retain only the existing validator's explicit contract errors.
        if type(exc).__name__ != "ContractError": raise
        error = str(exc)
    rows = []
    universe = set(projection["label_map"])
    def by_subject(ids):
        return dict(sorted(Counter(uid.split("_")[0] for uid in ids).items()))
    for split in projection["splits"]:
        test = set(split["test"])
        train = set(split.get("train", universe-test))
        cv = []
        for fold in split.get("train_cv", []):
            fit, val = set(fold["train"]), set(fold["val"])
            cv.append({"train_subjects": by_subject(fit), "validation_subjects": by_subject(val),
                       "train_test_overlap": len(fit & test), "validation_test_overlap": len(val & test),
                       "train_validation_overlap": len(fit & val),
                       "cv_ids_outside_outer_train": len((fit | val) - train),
                       "cv_ids_outside_outer_train_by_subject": by_subject((fit | val)-train),
                       "outer_train_ids_missing_from_cv": len(train-(fit | val))})
        rows.append({"test_subjects": by_subject(test), "outer_train_subjects": by_subject(train),
                     "outer_train_test_overlap": len(train & test), "cv": cv,
                     "excluded_development_units": len(split.get("excluded", {}))})
    return {"matches_registered_topology": error is None, "validation_error": error, "folds": rows}


def _evaluator():
    path = Path(__file__).resolve().parents[1] / "initial-evaluator-v1" / "evaluator.py"
    spec = importlib.util.spec_from_file_location("nuclr_initial_readout", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _validation_packet(projection, *, module=None):
    """Ephemeral structural control for v1; never exported or passed to evaluate.

    Zero digests refer to synthetic validator scaffolding, not acquired data.
    Metadata identities here are parsed from split IDs, not a fluorescence join.
    """
    module = module or _evaluator()
    panel, level = projection["panel"], projection["label_level"]
    return {"schema_version": 1, "task_id": module.TASK_ID, "source_commit": SOURCE_COMMIT,
            "input_role": "generated_engineering_control", "panel": panel, "label_level": level,
            "context_variant": "population_context", "class_balance": "resample",
            "source_session_manifest": sorted(module.SOURCE_SESSIONS),
            "representation_training_sessions": sorted(module.SOURCE_SESSIONS - module.SB028_SESSIONS if panel == "inductive_zero_shot" else module.SOURCE_SESSIONS),
            "label_vocabulary": sorted(LABELS[level]), "source_label_mapping": {x:x for x in sorted(LABELS[level])},
            "label_map": copy.deepcopy(projection["label_map"]), "metadata": copy.deepcopy(projection["metadata"]),
            "splits": copy.deepcopy(projection["splits"]),
            "provenance": {"split_sha256": projection["source_member_sha256"], "metadata_sha256": "0"*64, "data_receipt_sha256": "0"*64,
                           "split_member": Path(projection["source_member"]).name, "split_release": "december_2025_current", "split_release_detail": "Current author archive, Last-Modified 2025-12-14; conference equivalence unresolved"}}


def summary(projection):
    rows = projection["metadata"]
    return {k: projection[k] for k in ("source_member", "source_member_sha256", "label_level", "panel", "source_label_column")} | {
        "labeled_units": len(rows), "label_counts": dict(sorted(Counter(projection["label_map"].values()).items())),
        "topology_audit": topology_audit(projection),
        "sessions": dict(sorted(Counter(r["session_id"] for r in rows).items())),
        "folds": [{"test": len(s["test"]), "train": len(s.get("train", set(projection["label_map"])-set(s["test"]))),
                   "validation": len(s["val"]) if "val" in s else None,
                   "cv": [{"train": len(f["train"]), "val": len(f["val"])} for f in s.get("train_cv", [])]} for s in projection["splits"]]}


def read_archive(path):
    path = Path(path)
    with path.open("rb") as handle:
        raw = handle.read(8_725_950)
    require(len(raw) == 8_725_949 and hashlib.sha256(raw).hexdigest() == ARCHIVE_SHA256, "exact acquired archive pin mismatch")
    result = []
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names = archive.namelist()
        for level in LABELS:
            for panel, suffix in PANEL_SUFFIX.items():
                name = f"splits/bugeon/{level}_{suffix}.pkl"
                require(names.count(name) == 1, "missing or duplicate original panel member")
                info = archive.getinfo(name)
                require(0 < info.file_size <= 2_000_000, "source member size bound")
                projection = project(archive.read(info), level, panel)
                projection["source_archive_sha256"] = ARCHIVE_SHA256
                projection["topology_audit"] = topology_audit(projection)
                result.append(projection)
    return result


def select_readout_panel(projections, label_level, panel):
    """Select a complete panel only after the unchanged topology check passes.

    This rejects the current EI inductive source artifact. It neither repairs CV
    memberships nor certifies paper-era identity, metadata joins or a native run.
    """
    matches = [p for p in projections if p["label_level"] == label_level and p["panel"] == panel]
    require(len(matches) == 1, "unique complete original panel required")
    validate_topology(matches[0])
    result = copy.deepcopy(matches[0])
    result["required_readout_class_balance"] = "resample"
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--owner-output", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    args = parser.parse_args()
    projections = read_archive(args.archive)
    args.owner_output.mkdir(parents=True, exist_ok=True)
    for projection in projections:
        name = Path(projection["source_member"]).stem+".json"
        (args.owner_output/name).write_text(json.dumps(projection, indent=2, allow_nan=False)+"\n")
    document = {"source_archive_sha256": ARCHIVE_SHA256, "source_url": SOURCE_URL,
                "release": "2025-12-14 current public release", "panels": [summary(p) for p in projections],
                "qualification": "split source recovery only; no native reproduction or improvement result"}
    args.summary.write_text(json.dumps(document, indent=2, allow_nan=False)+"\n")


if __name__ == "__main__":
    main()
