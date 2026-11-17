"""Compose the existing held-neuron correction with heldout cache row alignment.

Source transformation only. Keep upstream and rendered sources outside Git.
No native execution, cache loading, model run, or historical-parity claim.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path


PREDECESSOR_SHA256 = "ee98938eb64b71c37594569670da33c1c2852a7d1419a566c9f6189c4d959097"
INSERTIONS = {"fit": 28392, "analyze": 24301}
CONTEXT_SHA256 = "530aab77d29cc3df31e158dfbec4c1485b6a54221dbad380430de9328a439c5c"
FIELDS = ("ll_neuron_time", "pred_var_os", "pred_var_us", "pred_zs")
INSERTION = b"""          let ll_neuron_time = Arr.get_fancy [ L argsorted_ids ] ll_neuron_time in
          let pred_var_os = Arr.get_fancy [ L argsorted_ids ] pred_var_os in
          let pred_var_us = Arr.get_fancy [ L argsorted_ids ] pred_var_us in
          let pred_zs = Arr.get_fancy [ L argsorted_ids ] pred_zs in
"""


def load_predecessor():
    """Reuse the reviewed source authenticator and complement implementation."""
    path = Path(__file__).resolve().parent.parent / "held-neuron" / "correct_sources.py"
    raw = path.read_bytes()
    if len(raw) != 7617 or hashlib.sha256(raw).hexdigest() != PREDECESSOR_SHA256:
        raise ValueError("exact reviewed held-neuron predecessor required")
    spec = importlib.util.spec_from_file_location("consensus_held_neuron_v1", path)
    module = importlib.util.module_from_spec(spec)
    # Execute the bytes just authenticated, avoiding a second pathname read.
    exec(compile(raw, str(path), "exec"), module.__dict__)
    return module


def render(originals):
    """Return three source successors; the analysis library keeps its prior fix."""
    predecessor = load_predecessor()
    outputs, prior_report = predecessor.render(originals)
    rows = []
    for role, insertion_offset in INSERTIONS.items():
        original = originals[role]
        path, _, _, branch_start, branch_end, _ = predecessor.SOURCES[role]
        context = original[insertion_offset - 96:insertion_offset + 96]
        predecessor.require(predecessor.digest(context) == CONTEXT_SHA256,
                            role + ": exact insertion context required")
        predecessor.require(branch_end < insertion_offset, "insertion must follow held-neuron branch")
        # The predecessor has precisely one replacement before this location.
        offset = insertion_offset + len(predecessor.WRAPPER_BRANCH) - (branch_end - branch_start)
        before = outputs[path]
        predecessor.require(before[offset - 96:offset + 96] == context,
                            role + ": composed insertion context changed")
        after = before[:offset] + INSERTION + before[offset:]
        outputs[path] = after
        rows.append({"role": role, "path": path,
                     "original_insertion_offset": insertion_offset,
                     "predecessor_insertion_offset": offset,
                     "inserted": predecessor.descriptor(INSERTION),
                     "predecessor": predecessor.descriptor(before),
                     "successor": predecessor.descriptor(after),
                     "outside_insertion_byte_identical_to_predecessor": True})
    return outputs, {
        "schema": "consensus_heldout_row_alignment_v1",
        "task": predecessor.TASK,
        "original_revision": predecessor.REVISION,
        "predecessor_sha256": PREDECESSOR_SHA256,
        "predecessor_correction": prior_report,
        "row_alignment_insertions": rows,
        "unchanged_library_successor": predecessor.descriptor(outputs["lib/analysis.ml"]),
        "aligned_fields": list(FIELDS),
        "row_order": "Unchanged original descending enumeration-position permutation; not a trial-ID sort.",
        "scientific_scope": "Corrected successor source only; original Figure 2b contract unchanged.",
        "native_compilation_or_execution": False,
        "historical_parity": False,
        "scientific_qualification": False,
    }


def materialize(originals, output):
    """Authenticate and render before creating a fresh owner-only source tree."""
    outputs, report = render(originals)
    output = Path(output)
    output.mkdir(mode=0o700, parents=False, exist_ok=False)
    for name, raw in outputs.items():
        path = output / name
        path.parent.mkdir(mode=0o700, exist_ok=True)
        with path.open("xb") as handle:
            handle.write(raw)
        path.chmod(0o600)
    # A failed write may leave a partial tree; no success report precedes source.
    report_path = output / "ROW_ALIGNMENT_REPORT.json"
    with report_path.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, sort_keys=True, indent=2, allow_nan=False)
        handle.write("\n")
    report_path.chmod(0o600)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fit-source", required=True)
    parser.add_argument("--analyze-source", required=True)
    parser.add_argument("--analysis-source", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        predecessor = load_predecessor()
        originals = {role: predecessor.read_original(getattr(args, role + "_source"))
                     for role in ("fit", "analyze", "analysis")}
        report = materialize(originals, args.output)
        print(json.dumps({"status": "corrected_source_only",
                          "row_alignment_entrypoints": len(report["row_alignment_insertions"]),
                          "scientific_qualification": False}, sort_keys=True))
    except (ValueError, OSError) as exc:
        parser.exit(2, "alignment refused: " + str(exc) + "\n")


if __name__ == "__main__":
    main()
