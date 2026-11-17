"""Operator entrypoint for the existing, complete 400-query numerical waveform pair.

Participant code runs only in the existing restricted transport. The separate
trusted grade process imports no participant source and opens private inputs
only after both closed collections and both public NPZs have been admitted.
"""
from __future__ import annotations

import argparse
import io
import json
import os
from pathlib import Path
import platform
import stat
import subprocess
import sys
import tempfile
import types

import bundle

HERE = Path(__file__).resolve().parent
CONDITIONS = ("legacy_waveform_no_tools", "matched_waveform_programme")
CASES = ("development-001", "development-002")
need, pin, encode, decode = bundle.need, bundle.pin, bundle.encoded, bundle.decode
LEGACY = {
    "PRODUCED_PROOF_REVIEW.json": {"bytes": 5759, "sha256": "4eb86a4505edfc941a269bb009f2b8ac67319287afa24f46cf5ae62cfd0b75b9"},
    "EXECUTION_SUMMARY.json": {"bytes": 4830, "sha256": "38f2b17b01e4f9016fb3242cf7c4201b3d6e492776564783bd625ba21458ecf9"},
    "run01/COMPLETE.json": {"bytes": 289037, "sha256": "0faeafa703f23b4c77afbbdf3493e606031b3d6470e762d063d5145a9c5b8d65"},
    "run01/collection/TRANSPORT_COMPLETE.json": {"bytes": 1184, "sha256": "7a71d70f9e5b6add6b0e5ad10cb3f9a9eb92649bc18503d9db8b3b48b26f44e0"},
    "run01/collection/COMPLETE.json": {"bytes": 591, "sha256": "19d69ca97f5902745fdbefa7800df8dcde7650c7f1a39c9fb626a030cc2c63e9"},
}
LEGACY_SUBMISSION = {"bytes": 80540, "sha256": "14585dd5c1db2d978513fffd79730507d498b508c65d046d5773f6c63862e673"}


def read(path, cap=1048576, expected=None):
    path = bundle.unlinked(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 < before.st_size <= cap,
             "Bounded ordinary single-link input required")
        body = stream.read(cap + 1)
        need(len(body) == before.st_size and bundle.fields(before) == bundle.fields(os.fstat(stream.fileno()))
             == bundle.fields(path.lstat()), "Input changed during capture")
    need(expected is None or pin(body) == expected, "Input identity changed")
    return body


def write(path, body):
    path = bundle.unlinked(path)
    with path.open("xb") as stream:
        stream.write(body)
        stream.flush()
        os.fsync(stream.fileno())
    path.chmod(0o400)
    return pin(body)


def module(path, body):
    name = "neural077_pair_" + pin(str(path).encode())["sha256"][:12]
    value = types.ModuleType(name)
    value.__file__ = str(path)
    sys.modules[name] = value  # dataclasses resolve their defining module.
    exec(compile(body, str(path), "exec"), value.__dict__)
    return value


def sources():
    """Capture all fixed existing dependencies before executing any of them."""
    bindings = decode(read(HERE / "SOURCE_BINDINGS.json", 16384))
    bodies = {name: read(HERE.parent / name, 65536, expected) for name, expected in bindings.items()}
    transport = module(HERE.parent / "waveform-transport-v1/transport.py", bodies["waveform-transport-v1/transport.py"])
    comparator = module(HERE.parent / "paired-condition-v1/compare.py", bodies["paired-condition-v1/compare.py"])
    return transport, comparator, bodies, bindings


def operator_identity():
    return {name: pin(read(HERE / name)) for name in ("pair.py", "bundle.py", "SOURCE_BINDINGS.json")}


def freeze(root, manifest, output):
    frozen = bundle.capture(root, decode(read(manifest, 65536)))
    write(output, encode(frozen))
    return {"status": "participant_bundle_frozen", "bundle_identity": frozen["bundle_identity"],
            "frozen_file": pin(encode(frozen)), "private_target_reads": 0}


def _closed(collection, condition):
    need(collection["schema"] == "neural077_waveform_transport_collection_v1"
         and collection["status"] == "complete_unscored_transport_collection"
         and collection["condition"] == condition and collection["queries"] == 400
         and collection["configuration"]["sandbox"] == "macos"
         and collection["local_transcript_replayed"] is True
         and collection["private_target_reads"] == 0 and collection["scoring_performed"] is False,
         "Complete restricted homogeneous collection required")


def run_arm(delivery_root, condition, frozen_file, output, python, limits):
    """One full arm, no retry/resume; no private input argument is accepted."""
    need(condition in CONDITIONS, "Only the matched numerical waveform conditions")
    transport, _, _, bindings = sources()
    before = operator_identity()
    frozen_body = read(frozen_file)
    frozen = decode(frozen_body)
    client_body = bundle.verify(frozen)
    # Pin the actual executable while preserving the existing transport's exact
    # runtime policy. The standard library/OS are not claimed immutable here.
    executable = Path(python).resolve(strict=True)
    interpreter = pin(read(executable, 64 * 1024 * 1024))
    output = bundle.unlinked(output)
    output.mkdir(mode=0o700)
    try:
        write(output / "FROZEN.json", frozen_body)
        write(output / "CLIENT.py", client_body)
        campaign = transport.run_campaign(delivery_root, condition, output / "campaign",
                                          output / "CLIENT.py", executable, "macos", limits)
        need(campaign["successful"] == 400 and campaign["failed_or_not_started"] == 0,
             "All 400 first responses must close successfully")
        collection = transport.collect(delivery_root, condition, output / "campaign", output / "collection")
        _closed(collection, condition)
        need(collection["configuration"]["client"] == pin(client_body), "Captured participant changed")
        need(operator_identity() == before and sources()[3] == bindings
             and pin(read(executable, 64 * 1024 * 1024)) == interpreter, "Operator/runtime changed during arm")
        receipt = {"schema": "neural077_waveform_pair_arm_v1", "status": "closed_unscored_arm",
                   "condition": condition, "queries": 400, "demonstrations": 4,
                   "source": bindings, "operator": before, "bundle_identity": frozen["bundle_identity"],
                   "frozen": pin(frozen_body), "client": pin(client_body),
                   "participant_executable": {"path": str(executable), "pin": interpreter},
                   "collection": pin(read(output / "collection/TRANSPORT_COMPLETE.json", 16384)),
                   "submission": collection["submission"],
                   "all_direct_children_reaped": True, "descendant_absence_verified": False,
                   "provider_tool_policy_qualified": False, "model_performance_measured": False,
                   "private_target_reads": 0, "scoring_performed": False}
        write(output / "ARM.json", encode(receipt))
        return receipt
    except BaseException as error:
        write(output / "FAILED.json", encode({"status": "failed_unscoreable", "error_type": type(error).__name__,
                                             "retry_allowed": False, "private_target_reads": 0}))
        raise


def _arm_descriptor(path):
    path = bundle.unlinked(path)
    return {"root": str(path), "receipt": pin(read(path / "ARM.json", 65536))}


def _admit_arm(descriptor, condition, bindings, identity):
    need(set(descriptor) == {"root", "receipt"}, "Exact operator arm descriptor")
    root = bundle.unlinked(descriptor["root"])
    body = read(root / "ARM.json", 65536, descriptor["receipt"])
    receipt = decode(body)
    need(receipt["schema"] == "neural077_waveform_pair_arm_v1" and receipt["status"] == "closed_unscored_arm"
         and receipt["condition"] == condition and receipt["queries"] == 400 and receipt["demonstrations"] == 4
         and receipt["source"] == bindings and receipt["operator"] == identity
         and receipt["all_direct_children_reaped"] is True and receipt["descendant_absence_verified"] is False
         and receipt["private_target_reads"] == 0 and receipt["scoring_performed"] is False,
         "Closed operator-authenticated arm required")
    need(not (root / "FAILED.json").exists(), "Failed arm cannot be scored")
    frozen = decode(read(root / "FROZEN.json", expected=receipt["frozen"]))
    client = bundle.verify(frozen)
    need(frozen["bundle_identity"] == receipt["bundle_identity"] and pin(client) == receipt["client"],
         "Changed frozen participant bundle")
    read(root / "CLIENT.py", expected=receipt["client"])
    collection = decode(read(root / "collection/TRANSPORT_COMPLETE.json", 16384, receipt["collection"]))
    _closed(collection, condition)
    need(collection["submission"] == receipt["submission"]
         and collection["configuration"]["client"] == receipt["client"], "Collection/client binding mismatch")
    return root / "collection/submission.npz", receipt["submission"], pin(body)


def _admit_legacy(root):
    """Reuse the independently accepted fixed-0.5 proof; never replay its campaign."""
    root = bundle.unlinked(root)
    records = {name: decode(read(root / name, 1048576, expected)) for name, expected in LEGACY.items()}
    review = records["PRODUCED_PROOF_REVIEW.json"]
    need(review["decision"] == "ACCEPT_SCOPED_AUTHENTIC_TRANSPORT_CONTROL"
         and review["counts"]["successful"] == 400 and review["counts"]["fixed_probability"] == 0.5
         and review["counts"]["failed_or_not_started"] == 0, "Accepted complete control proof required")
    collection = records["run01/collection/TRANSPORT_COMPLETE.json"]
    _closed(collection, CONDITIONS[0])
    need(collection["submission"] == LEGACY_SUBMISSION, "Legacy control identity")
    return root / "run01/collection/submission.npz", LEGACY_SUBMISSION, LEGACY["PRODUCED_PROOF_REVIEW.json"]


def public_roster(delivery_root, comparator):
    manifest_pin = {"bytes": 18502, "sha256": "edb93d2e6003e90afb54f8f62a97ceccd6088c59ba4fba1e4a2fb780c6bf9dc8"}
    manifest = decode(read(Path(delivery_root) / "public/manifest.json", 65536, manifest_pin))
    need(manifest["query_count"] == 400 and manifest["demonstration_count"] == 4
         and manifest["natural_class_prior_supplied"] is False, "Original complete packet")
    ids = manifest["development_ids"]
    return comparator.roster({case: [item for item in ids if item.startswith(case + "-")] for case in CASES})


def protected_compare(comparator, bodies, arms, ids, locations_file, accounting):
    """No private pathname is even parsed until both captured public NPZs pass."""
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
                                               a_condition=CONDITIONS[0], b_condition=CONDITIONS[1],
                                               a_receipt_pin=arms[0][2], b_receipt_pin=arms[1][2])


def grade(request_path, expected_sha):
    body = read(request_path, 65536)
    need(pin(body)["sha256"] == expected_sha, "Frozen grade request changed")
    request = decode(body)
    output = bundle.unlinked(request["output"])
    output.mkdir(mode=0o700)
    accounting = {"both_public_validated_before_private": False, "private_reference_attempts": 0,
                  "target_loader_attempts": 0, "temporary_submission_bytes_created": 0}
    try:
        _, comparator, bodies, bindings = sources()
        identity = operator_identity()
        need(request["operator"] == identity and request["source"] == bindings,
             "Frozen evaluator source changed")
        need(request["schema"] == "neural077_pair_grade_request_v1", "Exact grading request")
        a = (_admit_legacy(request["legacy_control"]) if request["legacy_control"] is not None else
             _admit_arm(request["a"], CONDITIONS[0], bindings, identity))
        b = _admit_arm(request["b"], CONDITIONS[1], bindings, identity)
        ids = public_roster(request["delivery_root"], comparator)
        result = protected_compare(comparator, bodies, (a, b), ids, request["private_locations"], accounting)
        result.update(operator_route="trusted_operator_pair_v1_not_registered_docker",
                      participant_code_executed_in_evaluator=False, model_performance_measured=False,
                      original_no_tools_control_reused=request["legacy_control"] is not None,
                      source=bindings, operator=identity, accounting=accounting,
                      evaluator_runtime={"python": platform.python_version(), "executable": sys.executable})
        write(output / "RESULT.json", encode(result))
        return result
    except BaseException as error:
        write(output / "FAILED.json", encode({"status": "unscored_failure", "error_type": type(error).__name__,
                                             "accounting": accounting, "retry_allowed": False}))
        raise


def dispatch_grade(delivery_root, a, b, legacy_control, private_locations, output, timeout):
    need((a is None) != (legacy_control is None), "Select either completed A or the accepted legacy control")
    need(type(timeout) in (int, float) and 0 < timeout <= 180, "Bounded grading timeout")
    _, _, _, bindings = sources()
    identity = operator_identity()
    request = {"schema": "neural077_pair_grade_request_v1", "operator": identity, "source": bindings,
               "delivery_root": str(bundle.unlinked(delivery_root)), "a": None if a is None else _arm_descriptor(a),
               "b": _arm_descriptor(b), "legacy_control": None if legacy_control is None else str(bundle.unlinked(legacy_control)),
               "private_locations": str(Path(private_locations).absolute()),
               "output": str(bundle.unlinked(output) / "grade")}
    # Check full public closure before dispatch. The fresh evaluator repeats this
    # admission; it never trusts a producer-supplied boolean alone.
    if a is not None:
        _admit_arm(request["a"], CONDITIONS[0], bindings, identity)
    else:
        _admit_legacy(request["legacy_control"])
    _admit_arm(request["b"], CONDITIONS[1], bindings, identity)
    output = bundle.unlinked(output)
    output.mkdir(mode=0o700)
    request_pin = write(output / "REQUEST.json", encode(request))
    environment = {key: value for key, value in os.environ.items() if key in ("PATH", "LANG", "LC_ALL", "TMPDIR")}
    environment.update(PYTHONDONTWRITEBYTECODE="1", OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1")
    with (output / "evaluator.log").open("xb") as log:
        try:
            completed = subprocess.run([sys.executable, "-B", str(HERE / "pair.py"), "_grade",
                                        "--request", str(output / "REQUEST.json"), "--sha256", request_pin["sha256"]],
                                       cwd=output, env=environment, stdin=subprocess.DEVNULL, stdout=log,
                                       stderr=log, timeout=timeout, check=False, close_fds=True)
            need(completed.returncode == 0, "Protected evaluator failed; retained failure is unscoreable")
        except BaseException as error:
            write(output / "FAILED.json", encode({"status": "evaluation_dispatch_failed", "error_type": type(error).__name__,
                                                 "retry_allowed": False}))
            raise
    return {"status": "paired_evaluation_closed", "request": request_pin,
            "result": pin(read(output / "grade/RESULT.json")), "private_inputs_opened_in_dispatcher": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    f = commands.add_parser("freeze")
    for name in ("root", "manifest", "output"):
        f.add_argument("--" + name, required=True)
    r = commands.add_parser("run")
    for name in ("delivery-root", "frozen-file", "output", "python"):
        r.add_argument("--" + name, required=True)
    r.add_argument("--condition", choices=CONDITIONS, required=True)
    r.add_argument("--max-prompt-bytes", type=int, default=262144)
    r.add_argument("--wall-seconds", type=float, required=True)
    r.add_argument("--campaign-seconds", type=float, required=True)
    c = commands.add_parser("compare")
    for name in ("delivery-root", "b", "private-locations", "output"):
        c.add_argument("--" + name, required=True)
    selector = c.add_mutually_exclusive_group(required=True)
    selector.add_argument("--a")
    selector.add_argument("--legacy-control")
    c.add_argument("--timeout", type=float, default=60)
    g = commands.add_parser("_grade", help=argparse.SUPPRESS)
    g.add_argument("--request", required=True)
    g.add_argument("--sha256", required=True)
    args = vars(parser.parse_args(argv))
    action = args.pop("action")
    try:
        if action == "freeze":
            result = freeze(**args)
        elif action == "run":
            transport = sources()[0]
            args["limits"] = transport.Limits(**{name: args.pop(name) for name in
                                                ("max_prompt_bytes", "wall_seconds", "campaign_seconds")})
            result = run_arm(**args)
        elif action == "compare":
            result = dispatch_grade(**args)
        else:
            result = grade(args["request"], args["sha256"])
        print(json.dumps({"status": result["status"]}, allow_nan=False))
        return 0
    except Exception as error:
        print(json.dumps({"status": "refused", "error_type": type(error).__name__, "reason": str(error)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
