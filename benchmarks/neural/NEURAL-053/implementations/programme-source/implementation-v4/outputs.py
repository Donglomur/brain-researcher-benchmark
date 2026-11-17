"""Operator-only source-bound stores/loaders joining actual study stages."""
from pathlib import Path
from cohort import ARMS, require
from io_support import object_digest
from storage import write_json_fresh, read_array_exact, read_json_exact
from grading import required_case_keys
from packets import prediction_case_files


def reference_sink(root, budget):
    root = Path(root)
    require(root.is_dir() and not root.is_symlink(), "Admitted operator reference directory")

    def store(case, result):
        label = f"reference-f{case['fold_ordinal']}-{case['arm']}"
        folder = root / label
        folder.mkdir()
        plans = {family: write_json_fresh(folder / (family + '.json'), graph, budget)
                 for family, graph in result["plans"].items()}
        evidence = {k: v for k, v in result.items() if k != "plans"}
        evidence_pin = write_json_fresh(folder / 'training_selection.json', evidence, budget)
        manifest = {"case": case, "fits": 244, "plans": plans, "training_selection": evidence_pin,
                    "primary_family": result["primary_family"],
                    "source_method_or_scientific_admission": False}
        manifest_pin = write_json_fresh(folder / 'manifest.json', manifest, budget)
        return {**manifest, "artifact_manifest_sha256": manifest_pin["sha256"], "manifest": manifest_pin}
    return store


def candidate_sink(root, budget):
    root = Path(root)
    require(root.is_dir() and not root.is_symlink(), "Admitted operator candidate directory")

    def store(case, authored, phase_events):
        from method.plan import load_plan
        key = [case["mode"], case["replication"], case["fold_ordinal"], case["arm"]]
        folder = root / object_digest(key)
        folder.mkdir()
        graph = authored["plan"]
        parsed = load_plan(graph)
        plan_pin = write_json_fresh(folder / 'plan.json', graph, budget)
        lineage = {k: v for k, v in authored.items() if k != "plan"}
        lineage["phase_events"] = list(phase_events)
        evidence_pin = write_json_fresh(folder / 'training_lineage.json', lineage, budget)
        manifest = {"context_key": key, "plan": plan_pin, "plan_sha256": parsed.digest,
                    "training_lineage": evidence_pin, "method_admission": "required_before_query"}
        manifest_pin = write_json_fresh(folder / 'manifest.json', manifest, budget)
        return {**manifest, "manifest": manifest_pin}
    return store


def query_descriptors(case_files, budget):
    result = {}
    for key in required_case_keys():
        pin = prediction_case_files(case_files, key)["query_descriptor"]
        result[key] = read_json_exact(pin["path"], pin, budget)
    return result


def prediction_record_loader(completed, descriptors, reference_selection, budget):
    """Loader returns readonly mapped exact outputs, not unconstrained submissions.

    Its execution receipts must separately join an approved observer registry in
    the grader. Candidate-written completion flags do not become approvals here.
    """
    require(set(completed) == set(required_case_keys()), "All160 completed prediction artifacts")
    from selection import ReferenceSelection
    require(type(reference_selection) is ReferenceSelection, "Derived immutable training selection")

    def load():
        records = {}
        for key in required_case_keys():
            output, descriptor = completed[key], descriptors[key]
            require(output["execution_receipt"]["reference_selection_digest"] == reference_selection.digest,
                    "Observed prediction bound the approved pre-query primary choice")
            pin = output["probability_artifact"]
            matrix = read_array_exact(pin["path"], pin, (3708, 1854), budget)
            records[key] = {"context_key": list(key), "probabilities": matrix,
                            "query_ids": descriptor["query_ids"], "classes": descriptor["classes"],
                            "query_descriptor_digest": object_digest(descriptor),
                            "reference_selection_digest": output["execution_receipt"]["reference_selection_digest"],
                            "method_admission_digest": output["method_gate"]["receipt_sha256"],
                            "execution_receipt": output["execution_receipt"]}
        return records
    return load
