"""Bounded source controls only; no authentic inputs or scientific execution.

A fresh temporary directory is retained on success and on failure. Its path is
printed and recorded in PORTABILITY_RESULT.json or PORTABILITY_FAILURE.json;
the caller may remove that explicitly named owned directory after preservation.
The complete scientific ten-person input fixture is not recreated here.
"""
import argparse
import builtins
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import stat
import sys
import tempfile
import time
import tracemalloc
import types

HERE = Path(__file__).absolute().parent
TRANSFER_CAP = 18 * 1048576
RETAINED_CAP = 11 * 262144  # 2.75 MiB; parent retains the remaining 256 KiB.
LIVE_CAP = 128 * 1048576
SECONDS = 75
FORBIDDEN = frozenset(("numpy", "scipy", "torch", "torchvision", "PIL",
                       "transformers", "sklearn", "cryptography"))
TRANSFER_PARTITIONS = {
    "positive_materialization": 5 * 1048576,
    "partial_failure": 2 * 1048576,
    "source_capture_and_restore": 2 * 1048576,
    "compiler_serialization": 4 * 1048576,
    "source_auxiliary_and_streams": 3 * 1048576,
    "result_and_headroom": 2 * 1048576,
}


def require(ok, message):
    if not ok:
        raise AssertionError(message)


def descriptor(label, size=1):
    return {"path": "invented/" + label, "bytes": size, "sha256": "a" * 64,
            "mode": "0o644", "role": "invented_metadata_only"}


def campaign_spec():
    """Explicit invented operands; these are never evidence or usable assets."""
    limits = {"wall_seconds": 1000, "cpu_seconds": 1000, "read_bytes": 1048576,
              "write_bytes": 1048576, "live_bytes": 1048576, "files": 1000,
              "model_calls": 10, "stream_bytes": 1048576}
    cell = {k: limits[k] for k in ("wall_seconds", "cpu_seconds", "read_bytes",
                                   "write_bytes", "files", "model_calls", "stream_bytes")}
    services = [{"identity": "invented-" + name, "source": descriptor(name + ".py"),
                 "qualification": descriptor(name + "-qualification.json")}
                for name in ("author", "reviewer1", "reviewer2", "adjudicator")]
    interpretation = {
        "schema": "neural055-postscore-interpretation-policy-v1",
        "author": services[0], "reviewers": services[1:3], "adjudicator": services[3],
        "rubric": {"dimensions": ["estimand_and_access", "training_selection_calibration",
                                  "paired_quantitative_evidence", "control_interpretation",
                                  "uncertainty_failure_multiplicity",
                                  "reproducible_supported_limitations"],
                   "anchors": {"0": "absent_or_incorrect",
                               "1": "partly_correct_material_omission",
                               "2": "complete_and_supported"}},
        "policy": "same_current_blinded_aggregate_no_prediction_feedback_no_retry_v1",
        "clock_domain": "INVENTED_CONTROL_NO_EXECUTION", "limits": cell,
        "closure_reserve_seconds": 10, "control_directory": "invented/mailbox",
        "response_bytes": 1048576, "result_bytes": 16777216,
        "memory_bytes": 1048576, "maximum_input_tokens": 100, "maximum_output_tokens": 100,
    }
    return {
        "system": "INVENTED_SOURCE_CONTROL",
        "submission": {k: descriptor(k + ".py") for k in ("F", "I", "common_policy")},
        "limits": limits, "cell_limits": cell,
        "phase_limits": {k: 100 for k in ("fit", "infer", "reference_fit", "reference_infer",
                                          "prepare", "grade_report")},
        "native_profile": {
            "schema": "neural055-linux-cgroupfs-broker-profile-v4",
            "model_cap": 268435456, "prediction_cap": 4194304, "programme_cap": 131072,
            "sidecar_abi": "neural055-native-sidecars-v2",
            "whole_resource_scope": "original_controller_control_actor_holder_provider_transport_scoring_publication_host_daemon_memory",
            "model_providers": [], "model_token_limits": {"invented_not_a_runtime_profile": True}},
        "input_index": descriptor("INPUT_INDEX.json"),
        "input_qualification": descriptor("input-qualification.json"),
        "pre_exposure_review": descriptor("review.json"),
        "reference_qualification": {"explicit": "INVENTED_UNVERIFIED"},
        "semantic_reviews": {}, "protected_scoring_authority": descriptor("scoring-authority.json"),
        "trust": descriptor("trust.json"), "protected_panel": descriptor("panel.json"),
        "paired_schedule": {
            "committed_before_exposure": True, "qualification": descriptor("schedule-qualification.json"),
            "pairing": descriptor("pairing.json"), "schedule": descriptor("schedule.json"),
            "alignment": descriptor("alignment.json")},
        "interpretation": interpretation,
        "exposure_declaration": {"explicit": "INVENTED_UNVERIFIED"},
        "runtime_environment": {"identity": "INVENTED_NOT_QUALIFIED",
                                "qualification": descriptor("runtime-qualification.json"),
                                "feature_identity": "INVENTED_NOT_QUALIFIED"},
        "diagnostic_incomplete_scoring": False,
    }


def run(root):
    begin = time.monotonic()
    tracemalloc.start()
    checks = []
    originals = {}
    inserted = []
    old_import = builtins.__import__
    old_alarm = signal.getsignal(signal.SIGALRM)
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(
        TimeoutError("portable source control deadline")))
    signal.setitimer(signal.ITIMER_REAL, SECONDS)
    helper = None
    worker = None
    compiler_encoded = 0
    auxiliary = None
    source_capture = 0
    restored_bytes = 0
    partial = None

    def check(label, ok):
        require(ok, label)
        checks.append(label)

    def refuse(label, function, types_=(ValueError, FileNotFoundError)):
        try:
            function()
        except types_ as error:
            checks.append(label)
            originals[label] = {"type": type(error).__name__, "message": str(error)[:1024]}
            return error
        raise AssertionError("did not refuse: " + label)

    def guard_import(name, *args, **kwargs):
        if name.split(".")[0] in FORBIDDEN:
            raise AssertionError("scientific import forbidden in source controls: " + name)
        return old_import(name, *args, **kwargs)

    def load(name, path, row=None):
        require(name not in sys.modules, "test does not replace an existing module")
        if row is None:
            raw = path.read_bytes()
            require(0 < len(raw) <= 262144, "bounded selected helper")
        else:
            raw, _ = helper.read_body(path, row, 0o644, auxiliary)
        mod = types.ModuleType(name)
        mod.__file__ = str(path)
        sys.modules[name] = mod
        inserted.append(name)
        exec(compile(raw, str(path), "exec"), mod.__dict__)
        return mod

    try:
        require(sum(TRANSFER_PARTITIONS.values()) == TRANSFER_CAP,
                "prospective transfer partitions")
        # This test and the helper are selected executable code. Their authenticity
        # is not inferred from their own manifest. A full 3 MiB auxiliary reserve
        # includes their loading and all bounded child-stream reservations below.
        helper = load("_neural055_public_source_entry", HERE / "source_entry.py")
        auxiliary = helper.Ledger()
        rows = helper.selected_rows()
        by_name = {r["path"]: r for r in rows}
        check("exact 88-body transport", len(rows) == 88)
        worker = helper.Materializer()
        result = worker.run(str(root / "materialized"))
        originals["actual_materializer_and_inspector"] = result
        check("actual inspector source-only natural zero",
              result["inspector_original"]["returncode"] == 0
              and result["inspection"]["status"] == "source_only")
        check("materialization reservation within selected share",
              worker.ledger.read_bytes + worker.ledger.write_bytes
              <= TRANSFER_PARTITIONS["positive_materialization"])
        materialized = root / "materialized"
        check("all runtime modes preserved", all(
            stat.S_IMODE((materialized / r["path"]).lstat().st_mode)
            == int(r["runtime_mode"], 8) for r in rows))
        refuse("existing output refused", lambda: helper.Materializer().run(str(materialized)))
        first = rows[0]
        bad = dict(first, sha256="0" * 64)
        refuse("actual source body wrong digest refused",
               lambda: helper.read_body(HERE / first["path"], bad, 0o644, auxiliary))

        # Tiny filesystem controls: ordinary marker bytes, never scientific payloads.
        raw = b"invented-source-control\n"
        tiny = root / "tiny.txt"
        tiny.write_bytes(raw)
        os.chmod(tiny, 0o644)
        pin = {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
        link = root / "tiny-link"
        link.symlink_to(tiny)
        refuse("source symlink refused", lambda: helper.read_body(link, pin, 0o644, auxiliary))
        hard = root / "tiny-hardlink"
        os.link(tiny, hard)
        refuse("source hardlink refused", lambda: helper.read_body(hard, pin, 0o644, auxiliary))
        # Keep both links as retained negative evidence; do not modify the checkout.
        modefile = root / "readonly-marker.txt"
        modefile.write_bytes(raw)
        os.chmod(modefile, 0o444)
        refuse("wrong transport mode refused",
               lambda: helper.read_body(modefile, pin, 0o644, auxiliary))

        # Two tiny dual-failure controls exercise the actual cleanup boundaries.
        # Real descriptors/iterators are closed before the wrapper raises again.
        dual_file = root / "dual-failure-marker.txt"
        dual_file.write_bytes(raw)
        os.chmod(dual_file, 0o644)
        real_os = helper.os

        class ReadAndCloseFault:
            def __init__(self):
                self.closed = []
            def __getattr__(self, name):
                return getattr(real_os, name)
            def read(self, fd, limit):
                real_os.read(fd, limit)
                raise OSError("INVENTED_PRIMARY_READ_FAILURE")
            def close(self, fd):
                real_os.close(fd)
                self.closed.append(fd)
                raise OSError("INVENTED_SECONDARY_HANDLE_CLOSE_FAILURE")

        handle_fault = ReadAndCloseFault()
        helper.os = handle_fault
        try:
            error = refuse("source read plus close keeps primary",
                           lambda: helper.read_body(dual_file, pin, 0o644, auxiliary), (OSError,))
        finally:
            helper.os = real_os
        check("read primary and secondary original retained",
              str(error) == "INVENTED_PRIMARY_READ_FAILURE"
              and len(error.cleanup_failures) == 1
              and str(error.cleanup_failures[0]) == "INVENTED_SECONDARY_HANDLE_CLOSE_FAILURE"
              and any("Secondary source-handle close failure" in n for n in error.__notes__))
        require(len(handle_fault.closed) == 1, "one real handle close")
        try:
            real_os.fstat(handle_fault.closed[0])
        except OSError as closed_error:
            check("actual negative source handle is closed", closed_error.errno == 9)
        else:
            raise AssertionError("dual-failure source descriptor leaked")
        originals["source read plus close keeps primary"]["secondary"] = {
            "type": type(error.cleanup_failures[0]).__name__,
            "message": str(error.cleanup_failures[0]), "notes": error.__notes__}

        class IteratorAndCloseFault:
            def __init__(self, iterator):
                self.iterator = iterator
                self.closed = False
            def __iter__(self):
                return self
            def __next__(self):
                next(self.iterator)
                raise OSError("INVENTED_PRIMARY_LISTING_FAILURE")
            def close(self):
                self.iterator.close()
                self.closed = True
                raise OSError("INVENTED_SECONDARY_ITERATOR_CLOSE_FAILURE")

        class ScandirFault:
            stream = None
            def __getattr__(self, name):
                return getattr(real_os, name)
            def scandir(self, directory):
                self.stream = IteratorAndCloseFault(real_os.scandir(directory))
                return self.stream

        listing_fault = ScandirFault()
        helper.os = listing_fault
        try:
            error = refuse("source listing plus close keeps primary",
                           lambda: helper.namespace(materialized, rows, auxiliary), (OSError,))
        finally:
            helper.os = real_os
        check("listing primary and secondary original retained",
              str(error) == "INVENTED_PRIMARY_LISTING_FAILURE"
              and len(error.cleanup_failures) == 1
              and str(error.cleanup_failures[0]) == "INVENTED_SECONDARY_ITERATOR_CLOSE_FAILURE"
              and any("Secondary source-iterator close failure" in n for n in error.__notes__))
        check("actual negative directory iterator is closed",
              listing_fault.stream.closed and next(listing_fault.stream.iterator, None) is None)
        originals["source listing plus close keeps primary"]["secondary"] = {
            "type": type(error.cleanup_failures[0]).__name__,
            "message": str(error.cleanup_failures[0]), "notes": error.__notes__}

        class InterruptedCopy(helper.Materializer):
            def write_body(self, path, row, raw):
                if len(self.copied) == 1:
                    raise OSError("INVENTED_SECOND_COPY_FAILURE")
                return super().write_body(path, row, raw)

        partial = InterruptedCopy()
        first_error = refuse("partial copy preserves first error",
                             lambda: partial.run(str(root / "partial-materialization")),
                             (OSError,))
        check("partial original state retained", str(first_error) == "INVENTED_SECOND_COPY_FAILURE"
              and partial.created and len(partial.copied) == 1 and partial.stage == "copy"
              and (root / "partial-materialization" / partial.copied[0]).is_file())
        check("failed copy never reaches inspector", partial.inspector_original is None)
        check("partial reservation within selected share",
              partial.ledger.read_bytes + partial.ledger.write_bytes
              <= TRANSFER_PARTITIONS["partial_failure"])

        builtins.__import__ = guard_import
        op = materialized / "operator_completion"
        closure = load("source_closure", op / "source_closure.py",
                       by_name["operator_completion/source_closure.py"])
        context, source_capture = closure.capture_runtime(
            materialized / "complete_study", closure.MANIFEST, 1048576)
        check("real curated capture is complete", len(context["source_bodies"]) == 78)
        refuse("real capture rejects wrong manifest",
               lambda: closure.capture_runtime(materialized / "complete_study",
                                                dict(closure.MANIFEST, sha256="0" * 64), 1048576))
        support = closure.RuntimeSupport(context)
        try:
            check("actual six metadata support modules loaded",
                  set(support.modules) == set(closure.RuntimeSupport.NAMES))
        finally:
            support.close()
        prep = load("preparation", op / "preparation.py",
                    by_name["operator_completion/preparation.py"])
        limits = {"wall_seconds": 25, "cpu_seconds": 25, "read_bytes": 1048576,
                  "write_bytes": 524288, "live_bytes": 16777216, "files": 128,
                  "model_calls": 1, "stream_bytes": 131072}
        session = prep.Session(context, materialized / "complete_study", root,
                               root / "restoration", str(Path(sys.executable).resolve()),
                               limits, time.monotonic(), time.process_time(), stream_cap=65536)
        def no_scientific_dispatch(*_args, **_kwargs):
            raise AssertionError("scientific dispatch forbidden in source-only controls")
        session.dispatch = no_scientific_dispatch
        try:
            restored = session.restore()
            selected = closure.preparation_bodies(context)
            for name, raw in selected.items():
                p = restored / name
                selected_pin = {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
                observed, _ = helper.read_body(p, selected_pin, 0o444, auxiliary)
                check("actual retained preparation body " + name, observed == raw)
                restored_bytes += len(raw)
            check("restored readonly directories",
                  all(stat.S_IMODE(p.lstat().st_mode) == 0o555
                      for p in (restored, restored / "private", restored / "private/preparation",
                                restored / "public")))
            check("actual restoration no scientific dispatch", session.operations == [])
            originals["restoration"] = {"roles": session.restored, "operations": session.operations,
                                        "source_identity": context["identity"]}
        finally:
            session.support.close()
        check("capture and restore fit selected share",
              source_capture + 2 * restored_bytes + len(prep.LAUNCHER) + 32768
              <= TRANSFER_PARTITIONS["source_capture_and_restore"])

        plans = load("plans", op / "plans.py", by_name["operator_completion/plans.py"])
        original_encode = plans.encode_plan
        def counted_encode(value):
            nonlocal compiler_encoded
            raw = original_encode(value)
            compiler_encoded += len(raw)
            require(compiler_encoded <= TRANSFER_PARTITIONS["compiler_serialization"],
                    "compiler virtual serialization allowance")
            return raw
        plans.encode_plan = counted_encode
        old_module = plans._Metadata.module
        def counted_module(self, name):
            nonlocal compiler_encoded
            value = old_module(self, name)
            if name == "common" and not getattr(value, "_counted_portability", False):
                original = value.encoded
                def encoded(obj):
                    nonlocal compiler_encoded
                    raw = original(obj)
                    compiler_encoded += len(raw)
                    require(compiler_encoded <= TRANSFER_PARTITIONS["compiler_serialization"],
                            "original metadata serialization allowance")
                    return raw
                value.encoded = encoded
                value._counted_portability = True
            return value
        plans._Metadata.module = counted_module
        current = load("plans_v2", op / "plans_v2.py", by_name["operator_completion/plans_v2.py"])
        spec = campaign_spec()
        plan = current.build_campaign_plan(spec, context)
        raw_plan = current.encode_plan(plan)
        cells = plan["cells"]
        check("full 960-cell domain", len(cells) == 960
              and len({tuple(sorted(c.items())) for c in cells}) == 960)
        check("600 candidate and 360 reference cells",
              sum(c["mode"] in ("F", "I") for c in cells) == 600
              and sum(c["mode"] == "REFERENCE" for c in cells) == 360)
        check("all ten people and five arms",
              {c["outer_person"] for c in cells} == {"sub-%02d" % i for i in range(1, 11)}
              and {c["arm"] for c in cells}
              == {"FULL", "IMAGE_ONLY", "PRE_ONLY", "POST_ONLY", "ALIGN_SHUFFLE"})
        check("both modes tools and all three seeds",
              {(c["mode"], c["tool_setting"], c["seed"]) for c in cells
               if c["mode"] != "REFERENCE"}
              == {(m, t, s) for m in ("F", "I") for t in ("T0", "T1")
                  for s in (55055, 55056, 55057)})
        check("full scientific dimensions unchanged", plan["dimensions"] == plans.DIMENSIONS)
        check("cell envelope and closed target barrier",
              plan["policy"]["cell_limits"] == spec["cell_limits"]
              and plan["policy"]["target_access"] == "after_all960_safe_original_dispositions")
        check("explicit external operands remain invented and unchanged",
              all(plan[k] == spec[k] for k in (
                  "submission", "input_index", "input_qualification", "pre_exposure_review",
                  "reference_qualification", "semantic_reviews", "protected_scoring_authority",
                  "trust", "protected_panel", "paired_schedule", "interpretation",
                  "exposure_declaration")))
        check("four source policy joins", plan["resource_policy"] == plan["policy"]["resource_policy"]
              == plan["native_profile"]["resource_policy"] == plan["runtime_environment"]["resource_policy"])
        incomplete = dict(spec)
        del incomplete["input_index"]
        refuse("actual compiler requires external input operand",
               lambda: current.build_campaign_plan(incomplete, context))
        bad_context = dict(context, identity="0" * 64)
        refuse("actual compiler rejects wrong source identity",
               lambda: current.build_campaign_plan(spec, bad_context))
        originals["compiler"] = {"cells": len(cells), "plan_bytes": len(raw_plan),
                                 "plan_sha256": hashlib.sha256(raw_plan).hexdigest(),
                                 "encoded_bytes": compiler_encoded, "executed_cells": 0}
        # Real operator request reading fails before source capture or any dispatch.
        missing = helper.bounded_child(
            [sys.executable, "-I", "-S", "-B", str(op / "operator_entry.py"),
             "--request", str(root / "ABSENT_EXTERNAL_REQUEST.json"),
             "--request-bytes", "1", "--request-sha256", "a" * 64], auxiliary, 10)
        originals["actual_missing_external_request"] = missing
        check("actual missing external request refusal",
              missing["returncode"] != 0 and "FileNotFoundError" in missing["stderr"]
              and not (root / "ABSENT_EXTERNAL_REQUEST.json").exists())
        check("no scientific dependencies imported", not FORBIDDEN.intersection(sys.modules))
        check("auxiliary reads fit selected share",
              auxiliary.read_bytes + auxiliary.write_bytes + 262144
              <= TRANSFER_PARTITIONS["source_auxiliary_and_streams"])
        helper.unchanged(HERE, worker.files, worker.directories)
        check("Git checkout selected bodies and modes unchanged", True)
        peak = tracemalloc.get_traced_memory()[1]
        check("known traced live allocation bounded", peak <= LIVE_CAP)
        # Only this owned test tree is inventoried; there are no authentic aliases.
        retained = 0
        entries = 0
        stack = [root]
        while stack:
            folder = stack.pop()
            for p in folder.iterdir():
                entries += 1
                require(entries <= 512, "bounded owned control namespace")
                s = p.lstat()
                if stat.S_ISDIR(s.st_mode):
                    stack.append(p)
                elif stat.S_ISREG(s.st_mode):
                    retained += s.st_size
                else:
                    require(stat.S_ISLNK(s.st_mode) and p == link,
                            "only the exact invented negative alias")
        check("retained source controls within allowance", retained + 65536 <= RETAINED_CAP)
        return {"schema": "neural055_public_portability_controls_v1", "status": "passed",
                "checks": checks, "check_count": len(checks), "originals": originals,
                "owned_control_root": str(root), "retained_control_bytes_before_result": retained,
                "logical_transfer_prospective_partitions": TRANSFER_PARTITIONS,
                "logical_transfer_prospective_total": TRANSFER_CAP,
                "compiler_serialized_bytes": compiler_encoded, "capture_reserved_bytes": source_capture,
                "known_traced_peak_bytes": peak, "known_live_cap": LIVE_CAP,
                "elapsed_seconds": time.monotonic() - begin,
                "scientific_or_native_execution": False, "authentic_inputs_opened": False,
                "scientific_qualification": False, "benchmark_count_delta": 0,
                "measurement_limit": "explicit source/copy/serialization bounds; standard interpreter/library and OS I/O are not physical-I/O measurements"}
    except BaseException as exc:
        failure = {"schema": "neural055_public_portability_failure_v1", "status": "failed",
                   "checks_completed": checks, "first_error_type": type(exc).__name__,
                   "first_error": str(exc)[:2048], "originals": originals,
                   "owned_control_root": str(root), "partial_state_retained": True,
                   "scientific_or_native_execution": False}
        raw = (json.dumps(failure, sort_keys=True, indent=2) + "\n").encode()
        require(len(raw) <= 65536, "bounded source failure record")
        with (root / "PORTABILITY_FAILURE.json").open("xb") as f:
            f.write(raw)
        print(json.dumps({"status": "failed", "owned_control_root": str(root)}), file=sys.stderr)
        raise
    finally:
        builtins.__import__ = old_import
        for name in reversed(inserted):
            sys.modules.pop(name, None)
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old_alarm)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    p.add_argument("--output", help="Explicit fresh absolute owned control directory")
    args = p.parse_args(argv)
    if args.output is None:
        # resolve only the newly returned system temporary directory, not inputs.
        root = Path(tempfile.mkdtemp(prefix="neural055-source-controls-")).resolve()
    else:
        root = Path(args.output)
        require(root.is_absolute() and str(root) == args.output and ".." not in root.parts
                and not any(v.is_symlink() for v in (root, *root.parents)),
                "canonical absolute owned control output")
        require(not os.path.lexists(root) and root.parent.is_dir(), "fresh control output")
        root.mkdir(mode=0o700)
    require(root.stat().st_uid == os.getuid(), "operator-owned control output")
    os.chmod(root, 0o700)
    result = run(root)
    raw = (json.dumps(result, sort_keys=True, indent=2) + "\n").encode()
    require(len(raw) <= 65536, "bounded source control result")
    with (root / "PORTABILITY_RESULT.json").open("xb") as f:
        f.write(raw)
    print(json.dumps({"status": result["status"], "check_count": result["check_count"],
                      "owned_control_root": str(root), "result_sha256": hashlib.sha256(raw).hexdigest(),
                      "scientific_execution": False}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

