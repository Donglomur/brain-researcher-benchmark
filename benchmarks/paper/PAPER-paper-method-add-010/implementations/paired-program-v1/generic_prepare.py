"""Prepare the explicit fixed-Generic-feature classification mode.

The accepted full-category inventory is authenticated and interpreted by the
unchanged, pinned bank adapter. Only the 188 selected face/object scalars are
public. No model is fitted, raw window extracted, or scientific score computed.
Both candidate programmes freeze before any inventory, fold or reference label
is opened. The complete private reference is retained outside candidate mounts.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import math
from pathlib import Path
import secrets
import struct
import sys
import types

sys.path.insert(0, str(Path(__file__).resolve().parent))
import prepare as raw_prepare
import generic_contract as contract
from storage import (need, encoded, decoded, pin, descriptor, read, write,
                     directory, seal_public_directory)

HERE = Path(__file__).resolve().parent
ORIENTATION = ["Category_Selective", "Prefrontal_Cortex"]
REFERENCE_ARM = "author-batch-range-logistic-reference-v1"
INVENTORY_PIN = {"bytes": 3182215,
    "sha256": "80b16614e7654a4b0efaafced5abb251ab17e625f264c66c87c0c8658737fa2d"}
BANK_BINDING_PIN = {"bytes": 23524,
    "sha256": "5c91aa46ba5d984c5fd4e56fb6abe7ab1549eee8c95abb51b95b218ad356efa7"}
ADAPTER_PIN = {"bytes": 12471,
    "sha256": "7ed5df838f89a5ea8ee55842f920ea61cbdd2ceb1cbf36553a6d4d61f66d9c3d"}
REFERENCE_PIN = {"bytes": 441245,
    "sha256": "cdb07c21ba429cd0f44852e62842b95d939632a18cd9575492a7d391e1faf1ba"}
FOLDS_PIN = {"bytes": 292670,
    "sha256": "a650b9c73f756feee54ce49f4c8d903336335ce6b971affc5a3c9aaa78a05b79"}
DATA_CAP = 8192
JSON_CAP = 2 * 1024**2
FOLD_EVIDENCE = (
    "Accepted fixed Generic-feature reference folds, sealed before the first "
    "reference fit; selected CS-to-PFC orientation. This is not an assertion "
    "of exact historical fold execution."
)


def load_adapter():
    """Compile the exact reviewed source, not an unchecked installed module."""
    body = read(HERE / "generic_bank_adapter.py", ADAPTER_PIN["bytes"], ADAPTER_PIN)
    name = "_meg_fixed_generic_bank_adapter_" + ADAPTER_PIN["sha256"]
    module = types.ModuleType(name)
    module.__file__ = str(HERE / "generic_bank_adapter.py")
    # Dataclass construction resolves the module through sys.modules.
    sys.modules[name] = module
    try:
        exec(compile(body, module.__file__, "exec"), module.__dict__)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module


def source_order_hash(records):
    return hashlib.sha256(encoded([
        [r["row_key"], r["participant"], r["label"]] for r in records
    ])).hexdigest()


def validate_frozen_plan(records, roster, plan):
    """Check the accepted plan without fitting or regenerating its folds."""
    need(type(plan) is dict and plan.get("orientation") == ORIENTATION
         and plan.get("source_order_sha256") == source_order_hash(records),
         "selected plan orientation and ordered case identity")
    need(len(records) == 188 and len(roster) == len(set(roster)) == 94,
         "complete fixed-feature population")
    need(len({r["row_key"] for r in records}) == 188
         and {(r["participant"], r["label"]) for r in records}
         == {(p, label) for p in roster for label in ("face", "object")},
         "exact participant/category support")
    folds = plan.get("folds")
    need(type(folds) is list and len(folds) == 10, "exact ten-fold plan")
    all_test, seen_people, group_map, sizes = [], [], {}, []
    for number, fold in enumerate(folds):
        need(type(fold) is dict and set(fold) == {
            "fold", "train_indices", "test_indices", "train_row_keys",
            "test_row_keys", "train_participants", "test_participants"},
            "exact frozen fold fields")
        train, test = fold["train_indices"], fold["test_indices"]
        need(type(train) is list and type(test) is list and train and test
             and type(fold["fold"]) is int and fold["fold"] == number
             and all(type(i) is int for i in train + test), "fold index types")
        need(len(set(train)) == len(train) and len(set(test)) == len(test)
             and not set(train) & set(test)
             and set(train) | set(test) == set(range(188)),
             "complete disjoint train/test indices")
        train_people = {records[i]["participant"] for i in train}
        test_people = {records[i]["participant"] for i in test}
        need(not train_people & test_people
             and train_people | test_people == set(roster),
             "participant-disjoint train/test support")
        need(fold["train_participants"] == [p for p in roster if p in train_people]
             and fold["test_participants"] == [p for p in roster if p in test_people]
             and fold["train_row_keys"] == [records[i]["row_key"] for i in train]
             and fold["test_row_keys"] == [records[i]["row_key"] for i in test],
             "fold participant and row-key ledger")
        need({records[i]["label"] for i in train} == {"face", "object"}
             and {records[i]["label"] for i in test} == {"face", "object"},
             "both classes in every train and test partition")
        all_test.extend(test)
        seen_people.extend(test_people)
        sizes.append(len(test_people))
        group_map.update({p: number for p in test_people})
    need(sorted(all_test) == list(range(188))
         and len(seen_people) == len(set(seen_people)) == 94
         and sorted(sizes) == [9] * 6 + [10] * 4,
         "complete once-only held population and accepted fold sizes")
    return group_map


def bind_reference(records, roster, reference, frozen):
    """Join reference labels/folds by identities; never zip prediction order."""
    need(type(reference) is dict
         and reference.get("schema") == "meg-fresh-reference-result-v1"
         and reference.get("status") == "success"
         and reference.get("input_sha256") == INVENTORY_PIN["sha256"]
         and reference.get("primary_orientation") == ORIENTATION
         and reference.get("roster") == list(roster),
         "selected accepted reference population and source")
    need(type(frozen) is dict and set(frozen) == {"schema", "plans", "input_sha256"}
         and frozen["schema"] == "meg-frozen-before-first-fit-v1"
         and frozen["input_sha256"] == INVENTORY_PIN["sha256"],
         "accepted pre-fit fold ledger source")
    need(type(frozen["plans"]) is list and type(reference.get("plans")) is list,
         "explicit frozen and reference plans")
    plans = [p for p in frozen["plans"]
             if type(p) is dict and p.get("orientation") == ORIENTATION]
    need(len(plans) == 1, "unique selected orientation plan")
    matching = [p for p in reference["plans"]
                if type(p) is dict and p.get("orientation") == ORIENTATION]
    need(matching == plans, "reference and sealed pre-fit plan are identical")
    folds = validate_frozen_plan(records, roster, plans[0])
    need(type(reference.get("results")) is list, "explicit reference report list")
    reports = [x for x in reference["results"] if type(x) is dict
               and x.get("arm") == REFERENCE_ARM and x.get("orientation") == ORIENTATION]
    need(len(reports) == 1, "unique author batch-range reference selector")
    predictions = reports[0].get("predictions")
    need(type(predictions) is list and len(predictions) == 188,
         "complete reference predictions")
    by_key = {}
    for row in predictions:
        need(type(row) is dict and set(row) == {
            "row_key", "participant", "truth", "prediction", "p_object", "fold"},
            "exact reference prediction fields")
        key, probability = row["row_key"], row["p_object"]
        need(type(key) is str and key not in by_key
             and type(probability) in (int, float)
             and math.isfinite(probability) and 0 <= probability <= 1,
             "unique finite reference probability")
        need(row["prediction"] == ("object" if probability > 0.5 else "face"),
             "reference stored prediction matches P(object) threshold")
        by_key[key] = row
    need(set(by_key) == {r["row_key"] for r in records}, "exact reference case support")
    mapping = {}
    for row in records:
        prediction = by_key[row["row_key"]]
        need(prediction["participant"] == row["participant"]
             and prediction["truth"] == row["label"]
             and type(prediction["fold"]) is int
             and prediction["fold"] == folds[row["participant"]],
             "exact reference participant, string label and fold join")
        source = contract.source_id(row["participant"], row["label"])
        mapping[source] = {"row_key": row["row_key"], "participant": row["participant"],
                           "label": row["label"], "fold": prediction["fold"]}
    return folds, {"input_mode": contract.MODE, "truth_encoding": "face_object_strings",
                   "source_inventory_sha256": INVENTORY_PIN["sha256"], "rows": mapping}


def validate_reference(records, reference, frozen):
    """Reusable private join check; neither input needs scalar numerical values.

    The caller authenticates the reference and frozen-ledger bytes before using
    this helper. It returns the participant map and explicit source-order
    evidence, while ``bind_reference`` additionally returns the grading join.
    """
    need(type(reference) is dict and type(reference.get("roster")) is list,
         "reference roster required")
    folds, _ = bind_reference(records, tuple(reference["roster"]), reference, frozen)
    return folds, {"source_inventory_sha256": INVENTORY_PIN["sha256"],
                   "source_order_sha256": source_order_hash(records),
                   "orientation": list(ORIENTATION), "fold_evidence": FOLD_EVIDENCE}


def load_sources(inventory_path, binding_path, reference_path, folds_path):
    """Capture accepted inputs once; no raw archive or reference fitting."""
    binding = decoded(read(binding_path, BANK_BINDING_PIN["bytes"], BANK_BINDING_PIN))
    need({k: binding["inventory"][k] for k in ("bytes", "sha256")} == INVENTORY_PIN,
         "accepted inventory declaration")
    body = read(inventory_path, INVENTORY_PIN["bytes"], INVENTORY_PIN)
    adapter = load_adapter()
    bank = adapter.decode_inventory(io.BytesIO(body), binding,
                                    source_kind="qualified-original-bank")
    records = [{"row_key": row.key, "participant": row.participant,
                "label": row.label, "value": row.value}
               for row in bank.direction(ORIENTATION)]
    need(len(records) == 188 and bank.inventory_sha256 == INVENTORY_PIN["sha256"],
         "only complete selected-orientation post-QC scalars")
    reference_body = read(reference_path, REFERENCE_PIN["bytes"], REFERENCE_PIN)
    folds_body = read(folds_path, FOLDS_PIN["bytes"], FOLDS_PIN)
    folds, reference_binding = bind_reference(records, bank.roster,
        decoded(reference_body), decoded(folds_body))
    provenance = {
        "schema": "meg-generic-fixed-feature-source-qc/v1", "input_mode": contract.MODE,
        "inventory": INVENTORY_PIN, "input_binding": BANK_BINDING_PIN,
        "adapter_source": ADAPTER_PIN, "orientation": ORIENTATION,
        "author_full_category_qc_before_pair_selection": True,
        "full_category_rows_per_orientation": 376, "public_selected_rows": 188,
        "all_category_missing_values": 0, "imputation_performed": False,
        "known_category_averages_oracle_supplied": True,
        "raw_window_feature_equivalence_established": False,
        "reference_result": REFERENCE_PIN, "frozen_folds": FOLDS_PIN,
        "selected_source_order_sha256": source_order_hash(records),
        "retained_other_category_scalar_values": False,
    }
    return records, folds, reference_binding, reference_body, folds_body, provenance


def scalar_npy(values):
    """Construct the exact small NumPy-v1 little-endian float64 scalar bank."""
    need(len(values) == 188 and all(type(v) in (int, float) and math.isfinite(v)
                                  for v in values), "188 finite scalar values")
    header = b"{'descr': '<f8', 'fortran_order': False, 'shape': (188,), }"
    # The v1 header ends with a newline and the data starts on a 64-byte boundary.
    header += b" " * ((-(10 + len(header) + 1)) % 64) + b"\n"
    return b"\x93NUMPY\x01\x00" + struct.pack("<H", len(header)) + header + b"".join(
        struct.pack("<d", float(value)) for value in values)


def write_panel(root, records, folds, *, key):
    """One scalar permutation and one set of fold contexts shared by A and B."""
    panel = contract.build_panel(records, folds, key, INVENTORY_PIN)
    public = contract.ordered_public_rows(panel)
    joins = {row["id"]: source for source, row in contract.private_source_join(panel).items()}
    values = {contract.source_id(r["participant"], r["label"]): r["value"] for r in records}
    ordered = []
    for row in public:
        value = values[joins[row["id"]]]
        need(hashlib.sha256(struct.pack("<d", value)).hexdigest() == row["scalar_sha256"],
             "opaque row scalar bytes match private source join")
        ordered.append(value)
    data_root = directory(root / "data")
    data_pin = write(data_root / "FEATURES.npy", scalar_npy(ordered), DATA_CAP, public=True)
    private_pin = write(root / "PRIVATE_PANEL.json", encoded(panel), JSON_CAP)
    contexts_root = directory(root / "contexts")
    contexts = {}
    for fold in range(10):
        context = contract.public_context(panel, fold)
        target = directory(contexts_root / f"fold-{fold:02d}")
        context_pin = write(target / "CONTEXT.json", encoded(context), JSON_CAP, public=True)
        contexts[str(fold)] = {"context_sha256": context["context_sha256"],
            "mount": raw_prepare.file_mount(target / "CONTEXT.json", "input", context_pin)}
    return {"panel_sha256": panel["panel_sha256"], "private_panel": private_pin,
            "data": raw_prepare.file_mount(data_root / "FEATURES.npy", "input", data_pin),
            "contexts": contexts, "rows": 188, "query_rows": 188,
            "original_preparation": INVENTORY_PIN}


def prepare(inventory, bank_binding, reference_result, frozen_folds,
            programme_a, programme_b, paper, paper_pin, author_source, output):
    """Trusted preparation only; existing runner owns all candidate execution."""
    root = directory(output)
    try:
        programmes = raw_prepare.freeze_programmes({"A": programme_a, "B": programme_b}, root)
        paper_body = read(paper, 32 * 1024**2, descriptor(paper_pin))
        paper_root = directory(root / "paper")
        paper_file = write(paper_root / "PAPER.bin", paper_body, 32 * 1024**2, public=True)
        seal_public_directory(paper_root)
        paper_mount = raw_prepare.tree_mount(paper_root, "paper", {"PAPER.bin": paper_file})
        author = raw_prepare.author_capsule(author_source, root / "author")
        instructions = read(HERE / "GENERIC_PARTICIPANT.md", 65536)
        instructions_root = directory(root / "contract")
        instruction_pin = write(instructions_root / "GENERIC_PARTICIPANT.md", instructions, 65536, public=True)
        seal_public_directory(instructions_root)
        instruction_mount = raw_prepare.tree_mount(instructions_root, "contract",
                                                     {"GENERIC_PARTICIPANT.md": instruction_pin})
        records, folds, binding, reference_body, folds_body, qc = load_sources(
            inventory, bank_binding, reference_result, frozen_folds)
        panel = write_panel(root, records, folds, key=secrets.token_bytes(32))
        private_references = {
            "reference_result": write(root / "REFERENCE_RESULT.json", reference_body, JSON_CAP),
            "reference_folds": write(root / "FROZEN_FOLDS.json", folds_body, JSON_CAP),
            "reference_binding": write(root / "REFERENCE_BINDING.json", encoded(binding), JSON_CAP),
            "source_qc": write(root / "SOURCE_QC.json", encoded(qc), 16384),
        }
        value = {"schema": "meg-prepared-paired-campaign/v2", "input_mode": contract.MODE,
            "task_id": raw_prepare.TASK, **panel, **private_references,
            "programmes": programmes, "paper": paper_mount, "author": author,
            "contract": instruction_mount, "fold_evidence": FOLD_EVIDENCE,
            "historical_folds_authenticated": False, "source_revision": raw_prepare.AUTHOR_REVISION,
            "freeze_order": "both programmes frozen before any Generic scalar inputs or fold labels were prepared",
            "preparation_only": True, "native_phases": 0, "scientific_results": False}
        write(root / "PREPARED.json", encoded(value), JSON_CAP)
        return value
    except BaseException as error:
        write(root / "FAILED.json", encoded({"schema": "meg-generic-preparation-failure/v1",
            "input_mode": contract.MODE, "error_type": type(error).__name__,
            "partial_outputs_retained": True, "automatic_retry": False}), 8192)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("inventory", "bank-binding", "reference-result", "frozen-folds",
                 "programme-a", "programme-b", "paper", "paper-pin-json", "author-source", "output"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    result = prepare(args.inventory, args.bank_binding, args.reference_result, args.frozen_folds,
        args.programme_a, args.programme_b, args.paper, decoded(read(args.paper_pin_json, 8192)),
        args.author_source, args.output)
    print(encoded({"status": "prepared", "input_mode": contract.MODE,
                   "panel_sha256": result["panel_sha256"], "rows": 188,
                   "predictions_per_condition": 188}).decode())


if __name__ == "__main__":
    main()
