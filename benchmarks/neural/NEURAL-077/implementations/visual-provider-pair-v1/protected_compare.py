"""Original protected loader and metrics, with explicit visual/programme conditions."""
import io
from pathlib import Path
import sys
import tempfile

def protected_compare(pair, comparator, bodies, arms, ids, locations_file, accounting, conditions):
    """No private pathname is even parsed until both captured public NPZs pass."""
    need, read, write, decode, module = pair.need, pair.read, pair.write, pair.decode, pair.module
    HERE, CASES, bundle = pair.HERE, pair.CASES, pair.bundle
    need(conditions == ("four_demo", "matched_waveform_programme"), "Exact visual/programme pair")
    import numpy as np
    validator, metrics = comparator.canonical(HERE.parent / "registered-runtime")
    snapshots = [read(path, expected=expected) for path, expected, _ in arms]
    with tempfile.TemporaryDirectory(prefix="neural077-pair-public-") as directory:
        paths = [Path(directory).resolve() / (letter + ".npz") for letter in ("a", "b")]
        for path, body in zip(paths, snapshots, strict=True):
            write(path, body)
            accounting["temporary_submission_bytes_created"] += len(body)
        for path in paths:
            validator.validate(path, ids)
        accounting["both_public_validated_before_private"] = True
        # Only the trusted operator supplies this file. Its paths must never be
        # delivered to a participant or evaluated by participant code.
        locations = decode(read(locations_file, 65536))
        need(set(locations) == {"schema", "targets", "reference_grade", "reference_commit"}
             and locations["schema"] == "neural077_pair_private_locations_v1"
             and set(locations["targets"]) == set(CASES), "Exact private operator locations")
        assets = decode(bodies["registered-runtime/assets.json"])
        # Execute unchanged author-registered lineage logic, with only its two
        # fixed container paths translated into the operator's pinned captures.
        old_modules = {name: sys.modules.get(name) for name in ("validator", "metrics")}
        old_path = list(sys.path)
        try:
            sys.modules.update(validator=validator, metrics=metrics)
            worker = module(HERE.parent / "registered-runtime/worker.py", bodies["registered-runtime/worker.py"])
        finally:
            sys.path[:] = old_path
            for name, old in old_modules.items():
                if old is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = old
        reference_paths = {"/input/reference_grade.json": locations["reference_grade"],
                           "/input/reference_commit.json": locations["reference_commit"]}
        class CapturedText:
            def __init__(self, body):
                self.body = body
            def read_text(self):
                return self.body.decode("utf-8")
        def reference_capture(path, expected, cap):
            need(path in reference_paths, "Only two fixed reference operands")
            accounting["private_reference_attempts"] += 1
            return CapturedText(read(reference_paths[path], cap, {k: expected[k] for k in ("bytes", "sha256")}))
        worker.pinned = reference_capture
        references = worker.references(assets)
        def private_loader(case):
            accounting["target_loader_attempts"] += 1
            need(case in CASES, "Fixed private case")
            expected = assets["private"]["targets"][case]
            body = read(locations["targets"][case], 100000, {k: expected[k] for k in ("bytes", "sha256")})
            with np.load(io.BytesIO(body), allow_pickle=False) as archive:
                values = {key: archive[key] for key in archive.files}
            need(set(values) == {"trial_ids", "labels", "case_id"} and str(values["case_id"]) == case
                 and np.array_equal(values["trial_ids"], ids[case]), "Exact private target/public ID join")
            return values["labels"]  # Preserve dtype for unchanged canonical validation.
        # comparator creates its own two captured temporary submissions too.
        accounting["temporary_submission_bytes_created"] += sum(map(len, snapshots))
        return comparator.compare_submissions(paths[0], paths[1], ids, private_loader, references,
                                               HERE.parent / "registered-runtime",
                                               a_pin=arms[0][1], b_pin=arms[1][1],
                                               a_condition=conditions[0], b_condition=conditions[1],
                                               a_receipt_pin=arms[0][2], b_receipt_pin=arms[1][2])
