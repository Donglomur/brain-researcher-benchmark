"""Apply one explicit three-consumer Consensus held-neuron source correction.

This does not compile or execute OCaml and does not qualify Figure 2b. Original
and rendered upstream source bodies must remain in the owner's external store.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat

REVISION = "eec6021e8b9f9031eb775fc1a10a07e583cf0e29"
TASK = "PAPER-CANDIDATE-20261114-CONSENSUS"
SOURCE_LIMIT = 128 * 1024
SOURCES = {
    "fit": ("examples/fit_single_animal.ml", 40714,
            "997b7f57ebc52ee69856a627738552e315b961aeb1bd564649b621f781dc3461",
            26071, 26445, "b4bebc5e8385f4a5e4c3ad5b2002cc21a3d556a3612a60342117e8756fc1c76c"),
    "analyze": ("examples/analyze_fitted_model.ml", 34587,
                "f6cafa9e09028625318a6b3611c367d3ab14d92128e5cbb2a37aef5c111aded5",
                21961, 22335, "b4bebc5e8385f4a5e4c3ad5b2002cc21a3d556a3612a60342117e8756fc1c76c"),
    "analysis": ("lib/analysis.ml", 28994,
                 "a43794e912e7e9d8d7c574ba005e3b03c19bd57d2533694a15ed12f1e4d05f2e",
                 1738, 2106, "442762de3b80052c4157fb3b646b58f2f29c5fb3839eb29bb05866e16db9bb74"),
}

# Base.List.init's labeled interface is already used by the pinned caller.
# Explicit lists remove the first/interior/last branch discrepancy. Preserve
# the full time-row slice and exactly one target column in every consumer.
WRAPPER_BRANCH = b'''          let slice_train, slice_test =
            if Int.(n_neurons < 2 || i < 0 || i >= n_neurons)
            then invalid_arg "consensus held neuron: invalid population/index";
            let observed_indices =
              List.init Int.(n_neurons - 1) ~f:(fun j ->
                  if Int.(j < i) then j else Int.(j + 1))
            in
            [ R [ 0; -1 ]; L observed_indices ], [ R [ 0; -1 ]; I i ]
'''
ANALYSIS_BRANCH = b'''      | Some i ->
        if Int.(n_neurons < 2 || i < 0 || i >= n_neurons)
        then invalid_arg "consensus held neuron: invalid population/index";
        let observed_indices =
          List.init Int.(n_neurons - 1) ~f:(fun j ->
              if Int.(j < i) then j else Int.(j + 1))
        in
        ( [ R [ 0; -1 ]; L observed_indices ]
        , [ R [ 0; -1 ]; I i ]
        , "heldout" )
'''


def require(ok, why):
    if not ok:
        raise ValueError(why)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def descriptor(raw):
    return {"bytes": len(raw), "sha256": digest(raw)}


def render(originals):
    """Authenticate all three immutable inputs before rendering any successor."""
    require(type(originals) is dict and set(originals) == set(SOURCES), "complete three-consumer input required")
    for role, (_, size, pin, start, end, branch_pin) in SOURCES.items():
        raw = originals[role]
        require(type(raw) is bytes and len(raw) == size and digest(raw) == pin, role + ": exact original identity required")
        require(digest(raw[start:end]) == branch_pin, role + ": exact branch identity required")
    outputs, rows = {}, []
    for role, (path, _, _, start, end, _) in SOURCES.items():
        raw = originals[role]
        replacement = ANALYSIS_BRANCH if role == "analysis" else WRAPPER_BRANCH
        changed = raw[:start] + replacement + raw[end:]
        require(changed.count(b"L observed_indices") == 1, role + ": one corrected consumer required")
        require(b"L (List.concat [ [ 0; i ]; [ i + 1; -1 ] ])" not in changed, role + ": stale interior expression")
        if role != "analysis":
            # Calls and saved parameter projections both retain the same slices.
            require(changed.count(b"get_partial_prms ~slice:slice_train prms") == 2, role + ": observed parameter consumers")
            require(changed.count(b"get_partial_prms ~slice:slice_test prms") == 2, role + ": target parameter consumers")
            require(changed.count(b"~heldout:(Some i)") == 1, role + ": analysis target join")
        else:
            # simulate_laser has a separate intentional full-population slice.
            # Audit the held-neuron compute_LL consumer, not that other assay.
            scope = changed.split(b"  let compute_LL\n", 1)[1].split(b"  let compute_emp_LL ", 1)[0]
            require(scope.count(b"AD.Maths.get_fancy slice_train (G.L.extract_output (Data.o dat))") == 1,
                    "analysis: recognition observation slice")
            require(scope.count(b"AD.Maths.get_fancy slice_test (G.L.extract_output (Data.o dat))") == 1,
                    "analysis: private target slice")
        outputs[path] = changed
        rows.append({"role": role, "path": path, "original": descriptor(raw),
                     "successor": descriptor(changed), "replaced_original_span": [start, end],
                     "replacement": descriptor(replacement), "outside_span_byte_identical": True})
    return outputs, {"schema": "consensus_three_consumer_correction_v1", "task": TASK,
                     "original_revision": REVISION, "sources": rows,
                     "scope": "Corrected held-neuron information boundary at all three consumers; not historical parity.",
                     "native_compilation_or_execution": False, "scientific_qualification": False,
                     "registered_task_count_delta": 0}


def read_original(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as f:
        before = os.fstat(f.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_size <= SOURCE_LIMIT, "bounded regular original source required")
        raw = f.read(SOURCE_LIMIT + 1)
        after = os.fstat(f.fileno())
        require(len(raw) <= SOURCE_LIMIT and (before.st_size, before.st_mtime_ns, before.st_ctime_ns)
                == (after.st_size, after.st_mtime_ns, after.st_ctime_ns), "source changed or exceeded bound")
    return raw


def materialize(originals, output):
    """Write all three corrected source files only after complete authentication.

    Output must be a fresh owner-local directory. A later write failure leaves its
    partial tree as evidence; no success report is committed until all files exist.
    The caller controls external storage and redistribution, not this helper.
    """
    outputs, report = render(originals)
    output = Path(output)
    output.mkdir(mode=0o700, parents=False, exist_ok=False)
    for name, raw in outputs.items():
        path = output / name
        path.parent.mkdir(mode=0o700, exist_ok=True)
        with path.open("xb") as f:
            f.write(raw)
        path.chmod(0o600)
    with (output / "CORRECTION_REPORT.json").open("x", encoding="utf-8") as f:
        json.dump(report, f, indent=2, sort_keys=True, allow_nan=False)
        f.write("\n")
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--fit-source", required=True)
    p.add_argument("--analyze-source", required=True)
    p.add_argument("--analysis-source", required=True)
    p.add_argument("--output", required=True)
    a = p.parse_args()
    try:
        originals = {"fit": read_original(a.fit_source), "analyze": read_original(a.analyze_source),
                     "analysis": read_original(a.analysis_source)}
        report = materialize(originals, a.output)
        print(json.dumps({"status": "corrected_source_only", "sources": len(report["sources"]),
                          "scientific_qualification": False}, sort_keys=True))
    except (OSError, ValueError) as exc:
        p.exit(2, "correction refused: " + str(exc) + "\n")


if __name__ == "__main__":
    main()
