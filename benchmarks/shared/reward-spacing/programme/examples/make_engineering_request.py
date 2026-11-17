"""Create a tiny invented, no-fit request for the existing protected-order path.

This is an example input author, not an executor or authentic runtime admission.
All thirteen conditions and all named-route slots receive explicit dispositions.
"""
import argparse
import copy
from pathlib import Path
import sys
import time

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
from central.io import encode, digest, pin
from central.source import configuration, paper, neural
from central.plan import construct
from central.exposure import create
from central.comparisons import REFERENCE_FAMILIES

CONDITION = "F_X_full_permitted"
CHOSEN = CONDITION + "/appetitive/cue_time/condition/600s"


def write(path, value, raw=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(value if raw else encode(value))
    return {"path": str(path.resolve()), **pin(path)}


def invented_corpus():
    conditions = paper("pipeline").full_scope(configuration())["conditions"]
    support = {name: {"state": "source_unscorable", "reason": "Invented example only."}
               for name in conditions}
    registry = {name: {"state": "source_unavailable", "reason": "Invented example only.",
                       "animals": []} for name in conditions}
    animals = []
    for index, condition in enumerate(("60s", "60s", "600s")):
        ident = "invented-animal-" + str(index)
        alias = "invented-alias-" + str(index)
        registry[condition]["animals"].append(
            {"id": ident, "aliases": [alias], "neural_designated": True})
        session = {
            "id": "invented-session-" + str(index), "day": 1, "duration": 12.0,
            "times": [i / 4 for i in range(49)],
            "fluorescence": [i / 8 for i in range(49)], "max_gap": 0.3,
            "history": {"duration_known": True, "delivered_count_known": True,
                        "lick_history_known": True},
            "events": [
                {"id": "cue", "kind": "cue", "time": 5.0, "trial_id": "0", "delivered": None},
                {"id": "out", "kind": "outcome", "time": 6.25, "trial_id": "0", "delivered": True},
                {"id": "lick", "kind": "lick_on", "time": 6.5, "trial_id": "0", "delivered": None},
            ],
        }
        animals.append({"id": ident, "aliases": [alias], "condition": condition,
                        "sex": "unknown", "hardware": "invented", "sessions": [session]})
    return registry, {"schema": "reward_neural_operator_export_v1", "synthetic": True,
                      "source_receipts": [{"kind": "invented_formula"}],
                      "qualification": {}, "support": support, "animals": animals}


def build(directory):
    directory = Path(directory).resolve()
    if directory.exists() or not directory.parent.is_dir():
        raise ValueError("fresh example directory with existing parent required")
    directory.mkdir(mode=0o700)
    registry, corpus = invented_corpus()
    corpus_pin = write(directory / "invented-corpus.json", corpus)
    binding = {"corpus_id": "reward-spacing-10.1038-s41593-026-02206-2",
               "version": "portable-invented-example-v1", "synthetic": True,
               "asset_manifest_sha256": digest("invented formula, no acquired assets"),
               "biological_registry_sha256": digest(registry),
               "views": {"paper": digest("no paper data supplied"), "neural": corpus_pin["sha256"]}}
    setup = construct("NEURAL-045", CONDITION, registry, binding)
    jobs = {}
    for slot in setup["slots"]:
        structural = slot["applicability"].startswith("structurally_inapplicable")
        jobs[slot["id"]] = {
            "status": "structurally_inapplicable" if structural else "source_unavailable",
            "reason": "Unselected invented example slot; no scientific support claim.",
            "support_receipt_sha256": digest(["invented missing slot", slot["id"]]),
        }
    source = (PACKAGE / "examples/prior_producer.py").read_bytes()
    candidate = write(directory / "candidate.py", source, raw=True)
    reference = write(directory / "reference.py",
                      source.replace(b"[0.0] * len", b"[1.0] * len"), raw=True)
    terminal = write(directory / "interpret.py",
                     (PACKAGE / "examples/interpret_program.py").read_bytes(), raw=True)
    routine = {"kind": "python_program_v1", "source_path": terminal["path"],
               "source_sha256": terminal["sha256"],
               "input_schema": "closed_aggregate_interpretation_evidence_v1",
               "output_schema": "neural_scientific_interpretation_v1",
               "timeout_seconds": 3.0, "output_cap_bytes": 65536}
    references = {name: {"status": "required_unscorable",
                         "reason": "Original scientific reference family not supplied.",
                         "support_receipt_sha256": digest(["invented", name])}
                  for name in REFERENCE_FAMILIES}
    references["R0"] = {
        "status": "available", "program": reference, "terminal_routine": copy.deepcopy(routine),
        "actor_lineage": "invented-independent-R0", "timeout_seconds": 3.0, "output_cap_bytes": 65536,
        "registration": {
            "family": "R0", "program_sha256": reference["sha256"],
            "input_contract_sha256": digest(neural("contracts").cell(CONDITION, "NEURAL-045")["input_control_contract"]),
            "training_only": True, "selection_receipt_sha256": digest("invented no-fit selection"),
            "independent_source_receipt_sha256": digest("invented independent source"),
            "engineering_only": True,
        },
    }
    jobs[CHOSEN] = {
        "status": "available", "actor_lineage": "invented-candidate", "claim_lane": "exploratory",
        "visible_modalities": ["invented-neural"], "time_ranges": [],
        "program": candidate, "terminal_routine": routine, "corpus": corpus_pin,
        "timeout_seconds": 3.0, "output_cap_bytes": 65536, "references": references,
    }
    request = {"task": "NEURAL-045", "mode": "engineering", "registry": registry,
               "binding": binding, "jobs": jobs}
    request_pin = write(directory / "request.json", request)
    lock = pin(PACKAGE / "SOURCE_LOCK.json")
    ledger_identity = digest(["invented-example-ledger", str(directory)])
    ledger_path = directory / "exposure.json"
    create(ledger_path, ledger_identity)
    now = time.time()
    review = {
        "schema": "reward_central_execution_review_v1", "task": "NEURAL-045",
        "source": lock, "request": request_pin, "condition": CONDITION,
        "not_before": now - 1, "expires": now + 3600,
        "output": str(directory / "output"), "engineering_only": True,
        "setup_digest": digest(setup),
        "exposure_ledger": {"path": str(ledger_path), "identity": ledger_identity},
        "limits": {"wall_seconds": 60.0, "cpu_seconds": 30.0,
                   "read_bytes": 16 << 20, "write_bytes": 2 << 20,
                   "retained_bytes": 3 << 20, "files": 768,
                   "output_bytes": 65536, "candidate_seconds": 3.0},
    }
    write(directory / "review.json", review)
    result = {"source": lock, "chosen_slot": CHOSEN, "required_slots": len(jobs),
              "argv": [sys.executable, str(PACKAGE / "run.py"), "run",
                       "--task", "NEURAL-045", "--condition", CONDITION,
                       "--source-bytes", str(lock["bytes"]), "--source-sha256", lock["sha256"],
                       "--program", str(directory / "request.json"),
                       "--output", str(directory / "output"),
                       "--review", str(directory / "review.json"), "--other-reserve-bytes", "0"],
              "generated_only": True, "scientific_qualification": False,
              "external_owner_admission": False}
    write(directory / "COMMAND.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fresh_directory", type=Path)
    print(encode(build(parser.parse_args().fresh_directory)).decode(), end="")
