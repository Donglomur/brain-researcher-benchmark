"""Generated controls of the actual additive CLI; no originals or native children.

configure(legacy_root, artifact_root) precedes unittest discovery. Maintained
runner/outcome doubles below are boundary controls, not source/runtime evidence.
"""
from __future__ import annotations
import argparse
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ENTRY = None
LEGACY_ROOT = None
ARTIFACT_ROOT = None
WRITE_CAP = 1048576
READ_CAP = 8388608
RESERVED_WRITES = 0
RESERVED_READS = 0
COUNTER = 0
ACTUAL_COMPLETED_WRITES = 0


def reserve_write(size):
    global RESERVED_WRITES
    if type(size) is not int or size < 0 or RESERVED_WRITES + size > WRITE_CAP:
        raise ValueError("Generated cumulative write reservation")
    RESERVED_WRITES += size


def reserve_read(size):
    global RESERVED_READS
    if type(size) is not int or size < 0 or RESERVED_READS + size > READ_CAP:
        raise ValueError("Generated cumulative source/fixture read reservation")
    RESERVED_READS += size


def put(path, raw):
    global ACTUAL_COMPLETED_WRITES
    reserve_write(len(raw))
    with Path(path).open("xb") as stream:
        count = stream.write(raw)
        ACTUAL_COMPLETED_WRITES += count
        if count != len(raw):
            raise OSError("Partial generated fixture write")


def take(path):
    path = Path(path)
    size = path.stat().st_size
    reserve_read(size + 1)
    with path.open("rb") as stream:
        raw = stream.read(size + 1)
    if len(raw) != size:
        raise ValueError("Generated fixture changed")
    return raw


def configure(legacy_root, artifact_root):
    global ENTRY, LEGACY_ROOT, ARTIFACT_ROOT
    if ENTRY is not None:
        raise ValueError("Configure controls exactly once")
    LEGACY_ROOT = Path(legacy_root).resolve(strict=True)
    ARTIFACT_ROOT = Path(artifact_root).resolve(strict=True)
    if not LEGACY_ROOT.is_dir() or not ARTIFACT_ROOT.is_dir():
        raise ValueError("Existing explicit dependency/artifact roots required")
    source = HERE / "run.py"
    raw = take(source)
    module = types.ModuleType("_language_dual_entry_control")
    module.__file__, module.__package__ = str(source), ""
    exec(compile(raw, str(source), "exec", dont_inherit=True), module.__dict__)
    ENTRY = module


def stats():
    return {"methods": 8, "reserved_generated_postimage_bytes": RESERVED_WRITES,
            "generated_write_cap_bytes": WRITE_CAP,
            "actual_completed_fixture_and_result_write_bytes": ACTUAL_COMPLETED_WRITES,
            "reserved_named_source_fixture_read_bytes": RESERVED_READS,
            "read_cap_bytes": READ_CAP, "native_children": 0,
            "original_payload_reads": 0, "model_fits": 0,
            "maintained_runner_is_generated_dispatch_double": True,
            "positive_pair_uses_real_outcomes_and_pinned_compare": True}


def control_accounting():
    """Reservations include failed attempts; actual writes cover retained postimages."""
    return stats()


def fresh(label):
    global COUNTER
    COUNTER += 1
    root = ARTIFACT_ROOT / ("%03d-" % COUNTER + label)
    root.mkdir()
    return root


def entry_pins():
    return {name: {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
            for name in ("run.py", "outcomes.py", "contract.json")
            for raw in [take(HERE / name)]}


def envelope(root, condition, pins):
    common = root.parent
    output = root / "result"
    config = {"schema": "generated-only-provider", "mode": "generated-only",
              "condition": condition, "candidate_sha256": "2" * 64,
              "provider_source_sha256": ENTRY.LEGACY_SOURCE_PINS["provider.py"],
              "store_sha256": "1" * 64, "schedule_sha256": "3" * 64,
              "runtime": {"root": str(common / "runtime"), "manifest": str(common / "runtime.json"),
                          "manifest_sha256": "4" * 64},
              "candidate": {"root": str(root / "candidate"), "manifest": str(root / "candidate.json"),
                            "manifest_sha256": "2" * 64},
              "assistance": {"root": str(root / "assistance"), "manifest": str(root / "assistance.json"),
                             "manifest_sha256": "5" * 64},
              "bwrap": {"path": "/generated-only/bwrap", "bytes": 1, "sha256": "6" * 64, "version": "0.11.0"},
              "cgroup_parent": "/generated-only/cgroup", "python_path": "/usr/bin/python3",
              "caps": {"max_jobs": 42, "max_requests": 5685, "working_bytes": 65536}}
    p = {"schema": "language-selected-figure3b-execution-protocol/v1",
         "scope": "original_figure3b_improvement", "source_pins": dict(ENTRY.LEGACY_SOURCE_PINS),
         "store_root": str(common / "private-store"), "store_sha256": "1" * 64,
         "store_read_limit": 65536, "store_working_limit": 65536, "schedule_sha256": "3" * 64,
         "provider_config": config, "provider_admission": {"generated_stub": True},
         "output_root": str(output), "provider_evidence_root": str(root / "provider"),
         "limits": {"generated_only": 1}, "operator_joint_admission_bytes": 262144,
         "numpy_version": "generated-only-not-runtime-evidence",
         "reference_path": str(common / "private-reference.json"),
         "reference_sha256": "d822f284c2d781f920841705a63fec38d3267ee5c62e5dd5635272cf087e49c9",
         "source_support_sha256": "3d2d46bbc6534b282f97d29c51b1961c8d284cf7a9894839fb851550b7549e37"}
    return {"schema": ENTRY.SCHEMA, "scope": ENTRY.SCOPE,
            "outcomes": ["reproduction", "improvement"],
            "output_policy": "shared_frozen_candidate_predictions",
            "condition": condition, "execution_policy": "existing_native_admission_required",
            "dependency_root": str(LEGACY_ROOT), "entry_sources": copy.deepcopy(pins),
            "selected_protocol": p, "selected_protocol_sha256": ENTRY.sha(ENTRY.encoded(p)),
            "outcome_output_bytes": 65536}


def pair_fixture(label):
    root = fresh(label)
    pins = entry_pins()
    arms = {}
    for condition in ENTRY.CONDITIONS:
        folder = root / condition
        folder.mkdir()
        arms[condition] = envelope(folder, condition, pins)
    value = {"schema": ENTRY.PAIR_SCHEMA, "scope": ENTRY.SCOPE, "arms": arms,
             "execution_policy": "sequential_two_existing_runs",
             "pair_output": str(root / "PAIRED_OUTCOMES.json"), "pair_output_bytes": 65536}
    return root, value


def repin(value):
    value["selected_protocol_sha256"] = ENTRY.sha(ENTRY.encoded(value["selected_protocol"]))


class GeneratedRunner:
    """Never imports or calls a native provider, reader, original store or model."""
    def __init__(self, *, fail_condition=None, recovery_mode=None, recovery_builder=None):
        self.events = []
        self.fail_condition = fail_condition
        self.recovery_mode = recovery_mode
        self.recovery_builder = recovery_builder
        self.observed_protocols = []

    def validate_protocol(self, p):
        self.events.append(("preflight", p["provider_config"]["condition"]))
        return copy.deepcopy(p)

    def run_protocol(self, p):
        condition = p["provider_config"]["condition"]
        self.events.append(("dispatch", condition))
        self.observed_protocols.append(copy.deepcopy(p))
        if condition == self.fail_condition:
            raise ValueError("Generated explicit unqualified-provider refusal")
        root = Path(p["output_root"])
        root.mkdir()
        collection_raw = ENTRY.encoded({"generated_only": True, "condition": condition,
                                        "protocol_sha256": ENTRY.sha(ENTRY.encoded(p))})
        collection_pin = {"bytes": len(collection_raw), "sha256": ENTRY.sha(collection_raw)}
        put(root / "COLLECTION.json", collection_raw)
        value = (self.recovery_builder(condition, collection_pin["sha256"]) if self.recovery_builder else
                 {"schema": "generated-recovery-boundary-control",
                  "collection_sha256": collection_pin["sha256"], "condition_not_in_original_recovery": None})
        raw = ENTRY.encoded(value)
        if self.recovery_mode == "noncanonical":
            raw = json.dumps(value).encode()
        put(root / "RECOVERY.json", raw)
        pin = {"bytes": len(raw), "sha256": ENTRY.sha(raw)}
        if self.recovery_mode == "wrong_hash":
            pin["sha256"] = "0" * 64
        if self.recovery_mode == "too_large":
            pin["bytes"] = ENTRY.MAX_RECOVERY_BYTES + 1
        return {"scope": p["scope"], "collection": collection_pin,
                "recovery": pin, "phase_cost_bounds": {"generated_only": True},
                "scientific_qualification": False}


def complete_generated_recovery(endpoint, condition, collection_sha):
    """Synthetic42 cells through real compare; no original data/reference body."""
    selection_sha = ENTRY.sha(endpoint.encoded(endpoint.selection()))
    common = {"schema": "language-original-figure3b-scores/v1",
              "selection_sha256": selection_sha,
              "source_support_sha256": "3d2d46bbc6534b282f97d29c51b1961c8d284cf7a9894839fb851550b7549e37",
              "execution_qualified": False}
    base = 0.2 if condition == "paper_data" else 0.3
    candidate = dict(common, role="candidate", prediction_run_sha256=collection_sha,
                     scores=[{"context": context, "pearson_r": base + i / 1000.0}
                             for i, context in enumerate(endpoint.contexts())])
    reference = dict(common, role="provided_author_reference",
                     prediction_run_sha256=endpoint.PROVIDED_REFERENCE_SHA256,
                     scores=[{"context": context, "pearson_r": 0.1 + i / 1000.0}
                             for i, context in enumerate(endpoint.contexts())])
    comparison = endpoint.compare(candidate, reference)
    return {"schema": "language-selected-figure3b-recovery/v1",
            "scope": "original_figure3b_improvement", "collection_sha256": collection_sha,
            "authorities": {"jobs": 42, "requests": 5685, "read_bytes_charged": 1,
                            "exact_authority_recovered": True, "scientific_qualification": False},
            "packed": {"jobs": 42, "requests": 5685, "read_bytes": 1,
                       "all_numeric_predictions_recovered": True,
                       "protected_execution_qualified": False, "provider_journal_independently_verified": False,
                       "scientific_qualification": False, "compact_request_identity_join_verified": True,
                       "scope": "original_figure3b_improvement"},
            "result": {"candidate_scores": candidate, "paired_difference": comparison,
                       "reference_packet_sha256": ENTRY.sha(endpoint.encoded(reference)),
                       "reference_status": "provided-author-values only; same-stack baseline computation not qualified",
                       "full_224_array_reproduction_executed": False},
            "original_result_arrays": None, "protected_execution_qualified": False,
            "scientific_qualification": False}


class GeneratedOutcomes:
    """Entry boundary double; actual numerical comparison is covered separately."""
    def __init__(self):
        self.calls = []

    def compose_recovered(self, recovery, **kwargs):
        self.calls.append((copy.deepcopy(recovery), copy.deepcopy(kwargs)))
        if kwargs["recovery_sha256"] != ENTRY.sha(ENTRY.encoded(recovery)):
            raise ValueError("Wrong recovery identity at composition boundary")
        if kwargs["collection_sha256"] != recovery["collection_sha256"]:
            raise ValueError("Wrong collection identity at composition boundary")
        return {"generated_boundary_only": True, "condition": kwargs["condition"],
                "outcomes": ["reproduction", "improvement"], "scientific_qualification": False}


class Controls(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(ENTRY, "Parent must call configure(legacy_root, artifact_root)")
        original_read = ENTRY.read_pinned
        original_write = ENTRY.write_outcome

        def metered_read(path, **kwargs):
            try:
                size = Path(path).lstat().st_size
            except OSError:
                size = 0
            reserve_read(min(size, kwargs["maximum"]) + 1)
            return original_read(path, **kwargs)

        def metered_write(path, value, limit):
            global ACTUAL_COMPLETED_WRITES
            reserve_write(len(ENTRY.encoded(value)))
            existed = Path(path).exists()
            try:
                return original_write(path, value, limit)
            finally:
                if not existed and Path(path).exists():
                    ACTUAL_COMPLETED_WRITES += Path(path).stat().st_size

        self.addCleanup(patch.stopall)
        patch.object(ENTRY, "read_pinned", side_effect=metered_read).start()
        patch.object(ENTRY, "write_outcome", side_effect=metered_write).start()

    def test_01_cli_requires_explicit_native_admission_token_before_dispatch(self):
        with patch.object(ENTRY, "read_protocol", side_effect=AssertionError("protocol opened")):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                ENTRY.main(["--protocol", "/unused", "--protocol-sha256", "0" * 64])

    def test_02_actual_paired_cli_preflights_both_then_dispatches_unchanged_protocols(self):
        root, pair = pair_fixture("paired-cli")
        raw = ENTRY.encoded(pair)
        path = root / "PROTOCOL.json"
        put(path, raw)
        # Builder and both real entry compositions each authenticate one endpoint
        # source. These reads happen inside the maintained helper, so reserve
        # their exact extent+sentinel in addition to metered entry-source reads.
        reserve_read(3 * (8811 + 1))
        real_outcomes = ENTRY.load_outcomes(pair["arms"][ENTRY.CONDITIONS[0]]["entry_sources"]["outcomes.py"])
        endpoint = real_outcomes._load_endpoint(str(LEGACY_ROOT))
        runner = GeneratedRunner(recovery_builder=lambda condition, identity:
                                 complete_generated_recovery(endpoint, condition, identity))
        stdout = io.StringIO()
        with patch.object(ENTRY, "load_selected_runner", return_value=runner), \
             contextlib.redirect_stdout(stdout):
            self.assertEqual(ENTRY.main(["--protocol", str(path), "--protocol-sha256", ENTRY.sha(raw),
                "--execute-admitted-native", ENTRY.TOKEN]), 0)
        self.assertEqual(runner.events, [("preflight", c) for c in ENTRY.CONDITIONS]
                         + [("dispatch", c) for c in ENTRY.CONDITIONS])
        self.assertEqual(runner.observed_protocols, [pair["arms"][c]["selected_protocol"] for c in ENTRY.CONDITIONS])
        self.assertEqual(len(runner.observed_protocols), 2)
        result = json.loads(take(pair["pair_output"]))
        self.assertEqual(result["total_software_callbacks_for_this_shared_output_pair"], 11370)
        self.assertFalse(result["full_224_array_contract_changed"])
        self.assertFalse(result["scientific_qualification"])
        self.assertEqual(json.loads(stdout.getvalue())["conditions"], list(ENTRY.CONDITIONS))
        for c in ENTRY.CONDITIONS:
            record = json.loads(take(Path(pair["arms"][c]["selected_protocol"]["output_root"]) / "FIGURE3B_OUTCOMES.json"))
            self.assertEqual(record["maintained_store_scope"], "original_figure3b_improvement")
            self.assertEqual(record["selected_protocol_sha256"], pair["arms"][c]["selected_protocol_sha256"])
            self.assertFalse(record["protected_execution_qualification_promoted"])
            actual = record["outcomes"]
            self.assertEqual(actual["condition"], c)
            self.assertEqual(len(actual["reproduction"]["cells"]), 42)
            self.assertEqual(len(actual["improvement"]["sessions"]), 14)
            self.assertEqual(len(actual["improvement"]["participants"]), 8)
            self.assertAlmostEqual(actual["improvement"]["equal_session_paired_mean_delta"],
                                   0.1 if c == "paper_data" else 0.2)
            self.assertEqual(actual["reproduction"]["equal_session_signed_difference"],
                             actual["improvement"]["equal_session_paired_mean_delta"])
            self.assertIsNone(actual["reproduction"]["tolerance"])
            self.assertFalse(actual["scientific_qualification"])

    def test_03_mismatched_or_incomplete_pair_refuses_before_any_dispatch(self):
        _, original = pair_fixture("preflight-mismatch")
        cases = ("missing_arm", "condition", "scope", "count", "support", "schedule",
                 "source", "numpy", "caps", "candidate_context", "output_context", "protocol_hash",
                 "report_cap", "output_in_runtime", "provider_in_assistance",
                 "other_arm_assistance_in_output", "pair_output_ancestor", "output_contains_reference")
        for case in cases:
            with self.subTest(case=case):
                pair = copy.deepcopy(original)
                a, b = [pair["arms"][c] for c in ENTRY.CONDITIONS]
                p = b["selected_protocol"]
                if case == "missing_arm":
                    del pair["arms"][ENTRY.CONDITIONS[1]]
                elif case == "condition":
                    b["condition"] = ENTRY.CONDITIONS[0]
                elif case == "scope":
                    p["scope"] = "original_full_reproduction"
                elif case == "count":
                    p["provider_config"]["caps"]["max_requests"] = 5684
                elif case == "support":
                    p["source_support_sha256"] = "9" * 64
                elif case == "schedule":
                    p["schedule_sha256"] = "9" * 64
                elif case == "source":
                    p["source_pins"]["reader.py"] = "9" * 64
                elif case == "numpy":
                    p["numpy_version"] = "other"
                elif case == "caps":
                    p["provider_config"]["caps"]["working_bytes"] += 1
                elif case == "candidate_context":
                    p["provider_config"]["candidate"]["root"] = a["selected_protocol"]["provider_config"]["candidate"]["root"]
                elif case == "output_context":
                    p["output_root"] = a["selected_protocol"]["output_root"]
                elif case == "report_cap":
                    b["outcome_output_bytes"] -= 1
                elif case == "output_in_runtime":
                    p["output_root"] = p["provider_config"]["runtime"]["root"]
                elif case == "provider_in_assistance":
                    p["provider_evidence_root"] = p["provider_config"]["assistance"]["root"]
                elif case == "other_arm_assistance_in_output":
                    p["provider_config"]["assistance"]["root"] = a["selected_protocol"]["output_root"]
                elif case == "pair_output_ancestor":
                    pair["pair_output"] = str(Path(p["provider_config"]["candidate"]["root"]) / "parent.json")
                    p["provider_config"]["candidate"]["root"] = pair["pair_output"] + "/descendant"
                elif case == "output_contains_reference":
                    p["output_root"] = str(Path(p["reference_path"]).parent)
                else:
                    b["selected_protocol_sha256"] = "0" * 64
                if case != "protocol_hash":
                    repin(b)
                with patch.object(ENTRY, "load_selected_runner", side_effect=AssertionError("dispatch seam opened")):
                    with self.assertRaises((ValueError, OSError)):
                        ENTRY.run_pair(pair)

    def test_04_provider_failure_retains_first_arm_without_paired_success(self):
        for failed in ENTRY.CONDITIONS:
            root, pair = pair_fixture("refusal-" + failed)
            runner, outcomes = GeneratedRunner(fail_condition=failed), GeneratedOutcomes()
            with patch.object(ENTRY, "load_selected_runner", return_value=runner), \
                 patch.object(ENTRY, "load_outcomes", return_value=outcomes):
                with self.assertRaisesRegex(ValueError, "unqualified-provider"):
                    ENTRY.run_pair(pair)
            self.assertFalse(Path(pair["pair_output"]).exists())
            first = Path(pair["arms"][ENTRY.CONDITIONS[0]]["selected_protocol"]["output_root"]) / "FIGURE3B_OUTCOMES.json"
            self.assertEqual(first.exists(), failed == ENTRY.CONDITIONS[1])
            self.assertEqual(len(outcomes.calls), 1 if failed == ENTRY.CONDITIONS[1] else 0)

    def test_05_corrupt_or_noncanonical_recovery_never_reaches_outcome_composition(self):
        for mode in ("wrong_hash", "noncanonical", "too_large"):
            _, pair = pair_fixture("recovery-" + mode)
            runner = GeneratedRunner(recovery_mode=mode)
            with patch.object(ENTRY, "load_selected_runner", return_value=runner), \
                 patch.object(ENTRY, "load_outcomes", side_effect=AssertionError("unverified recovery composed")):
                with self.assertRaises(ValueError):
                    ENTRY.run_protocol(pair["arms"][ENTRY.CONDITIONS[0]])
            output = Path(pair["arms"][ENTRY.CONDITIONS[0]]["selected_protocol"]["output_root"])
            self.assertTrue((output / "RECOVERY.json").exists())
            self.assertFalse((output / "FIGURE3B_OUTCOMES.json").exists())

    def test_06_additive_output_cap_and_exclusive_publication_fail_closed(self):
        _, pair = pair_fixture("output-cap")
        arm = pair["arms"][ENTRY.CONDITIONS[0]]
        arm["outcome_output_bytes"] = 1
        with patch.object(ENTRY, "load_selected_runner", return_value=GeneratedRunner()), \
             patch.object(ENTRY, "load_outcomes", return_value=GeneratedOutcomes()):
            with self.assertRaisesRegex(ValueError, "before output allocation"):
                ENTRY.run_protocol(arm)
        output = Path(arm["selected_protocol"]["output_root"])
        self.assertTrue((output / "RECOVERY.json").exists())
        self.assertFalse((output / "FIGURE3B_OUTCOMES.json").exists())
        collision = output / "existing.json"
        put(collision, b"existing\n")
        with self.assertRaises(FileExistsError):
            ENTRY.write_outcome(collision, {"new": True}, 65536)
        self.assertEqual(take(collision), b"existing\n")

    def test_07_pinned_reader_and_protocol_reject_bad_extent_hash_duplicate_or_encoding(self):
        root = fresh("metadata")
        path = root / "source.py"
        raw = b"VALUE = 7\n"
        put(path, raw)
        with self.assertRaisesRegex(ValueError, "before read"):
            ENTRY.read_pinned(path, maximum=4, expected_sha256=ENTRY.sha(raw))
        with self.assertRaisesRegex(ValueError, "pinned bytes"):
            ENTRY.read_pinned(path, maximum=64, expected_sha256="0" * 64)
        self.assertEqual(ENTRY.read_pinned(path, maximum=64, expected_sha256=ENTRY.sha(raw)), raw)
        duplicate = root / "duplicate.json"
        raw = b'{"schema":"x","schema":"y"}\n'
        put(duplicate, raw)
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            ENTRY.read_protocol(duplicate, ENTRY.sha(raw))
        noncanonical = root / "noncanonical.json"
        raw = b'{"schema": "x"}'
        put(noncanonical, raw)
        with self.assertRaisesRegex(ValueError, "Canonical"):
            ENTRY.read_protocol(noncanonical, ENTRY.sha(raw))

    def test_08_verified_byte_loader_executes_saved_body_and_restores_failed_module(self):
        root = fresh("verified-loader")
        path = root / "source.py"
        raw = b"VALUE = 7\n"
        put(path, raw)
        saved = ENTRY.read_pinned(path, maximum=64, expected_sha256=ENTRY.sha(raw))
        name = "_language_generated_exact_byte_control"
        self.addCleanup(sys.modules.pop, name, None)
        module = ENTRY.module_from_bytes(name, path, saved)
        self.assertEqual(module.VALUE, 7)
        with self.assertRaisesRegex(RuntimeError, "generated"):
            ENTRY.module_from_bytes(name, path, b'raise RuntimeError("generated")\n')
        self.assertIs(sys.modules[name], module)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--legacy-root", default=str(HERE.parent))
    parser.add_argument("--artifact-root")
    args, unittest_args = parser.parse_known_args(argv)
    def run_controls(root):
        configure(args.legacy_root, root)
        program = unittest.main(module=__name__, argv=[sys.argv[0], *unittest_args], exit=False)
        print(json.dumps(stats(), sort_keys=True))
        return 0 if program.result.wasSuccessful() else 1
    if args.artifact_root is not None:
        return run_controls(args.artifact_root)
    # This default is used only by explicit standalone test execution, never by
    # import or the parent's fixed-artifact-root campaign. Deleted files remain
    # charged to the cumulative write reservation.
    with tempfile.TemporaryDirectory(prefix="language-figure3b-entry-") as root:
        return run_controls(root)


if __name__ == "__main__":
    raise SystemExit(main())
