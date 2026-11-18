"""Regression coverage for the reviewed iSTTC source-policy prose correction.

The published iSTTC metadata subgraph is the fixture. Its predecessor and scope
bytes are authenticated; the real context, byte-pin reader and unavailable-outcome
validators run. Global endpoint-authority coverage is a separate integration check.
No scientific source executes.
"""
import copy
from functools import lru_cache
import importlib.util
import hashlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
TASK = "PAPER-paper-method-add-004"
HOME = "benchmarks/paper/" + TASK
PROVENANCE = HOME + "/docs/provenance/empirical-qc-source-resolution.v1.json"
OLD_LIMIT = ("The authentic empirical unit/mouse/area roster and original trial-window draws remain unmaterialized; "
             "paper amplitude cutoff 0.01 and retained loader policy 0.1 are unreconciled.")
EXPECTED_LIMIT = ("The original empirical unit/session/mouse/area roster, interval coordinates and trial-window draws remain unmaterialized. "
    "Existing pinned author source documents staged QC: the broader loader amplitude cutoff 0.1 is followed by an eight-area filter "
    "using amplitude_cutoff < 0.01, isi_violations < 0.5 and presence_ratio > 0.9. This resolves the unexplained 0.1-versus-0.01 contrast "
    "at source-policy level only. Paper inclusive boundaries versus source strict boundaries, the saved presence-ratio minimum 0.95 "
    "and exact historical AllenSDK filtering, authentic 5775-unit/26-mouse membership, complete fit failures and panel-specific masks remain unresolved.")
EXPECTED_SECONDARY = ("The original 5775-unit/26-mouse empirical cohort, mouse/session identities, intervals, historical trial draws and "
    "panel masks remain unresolved. The pinned downstream <0.01 amplitude filter explains the loader 0.1 threshold; exact boundary "
    "and historical presence/AllenSDK selection still require qualification.")

@lru_cache(maxsize=64)
def source_bytes(relative):
    return (ROOT / relative).read_bytes()

def framework(name):
    path = ROOT / "src/neurobench" / (name + ".py")
    spec = importlib.util.spec_from_file_location("_isttc_public_" + name, path)
    module = importlib.util.module_from_spec(spec)
    exec(compile(source_bytes("src/neurobench/" + name + ".py"), str(path), "exec"), module.__dict__)
    return module

binding = framework("paper_outcomes_binding")
checker = framework("repository_checks")

class MetadataBytes:
    """In-memory byte transport; production metadata_pin authenticates each read."""
    def __init__(self):
        self.overrides = {}
        self.requested = []

    def document(self, relative):
        self.requested.append(relative)
        raw = self.overrides[relative] if relative in self.overrides else source_bytes(relative)
        if raw is None:
            raise FileNotFoundError(relative)
        return binding.engine().loads_contract(raw.decode("utf-8")), {
            "path": relative, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}

def changed_leaves(left, right, prefix=""):
    if left == right:
        return set()
    if type(left) is dict and type(right) is dict and set(left) == set(right):
        return set().union(*(changed_leaves(left[k], right[k], prefix + "/" + k) for k in left))
    if type(left) is list and type(right) is list and len(left) == len(right):
        return set().union(*(changed_leaves(a, b, prefix + "/" + str(i)) for i, (a, b) in enumerate(zip(left, right))))
    return {prefix}

class IsttcQcSourceResolutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Reuse the published lineage/contract fixture with the production
        # metadata reader. Do not fabricate a permissive validation stub.
        cls.registry = json.loads(source_bytes(binding.REGISTRY))
        cls.row = next(row for row in cls.registry["tasks"] if row["id"] == TASK)

    def setUp(self):
        self.reader = MetadataBytes()
        self.read_pin = lambda pin, label: checker.metadata_pin(self.reader, pin, pin["path"], label)
        # Authenticate the same immutable predecessor registry and selected
        # scope records consumed by coverage, but limit this unit fixture to
        # iSTTC context. Global endpoint selections must be composed separately.
        declared = self.registry["paper_outcomes"]
        snapshot = self.read_pin(declared["pre_outcomes_registry"], "Pre-outcomes registry")
        self.previous = binding.PreviousRows((row["id"], row) for row in snapshot["tasks"])
        scope = self.read_pin(declared["scope_decisions"], "Current scope authority")
        self.previous.scope_decisions = binding.scope_decisions(scope)
        self.previous.scope_pin = copy.deepcopy(declared["scope_decisions"])
        self.entry = self.previous.scope_decisions["entries"][TASK]
        self.task = self.read_pin(self.row["specification"], "Current iSTTC task")
        self.history = self.read_pin(self.row["paper_outcomes"]["previous_specification"], "Preserved iSTTC task")
        self.improvement = self.read_pin(self.row["specification_revision"]["improvement_contract"], "Preserved improvement")

    def context(self):
        return binding.context(self.row, self.task, self.previous, self.read_pin,
                               improvement_contract=self.improvement)

    def test_selected_projection_changes_exact_five_fields_and_preserves_history(self):
        historical = copy.deepcopy(self.history)
        improvement = copy.deepcopy(self.improvement)
        old_entry = copy.deepcopy(self.entry)
        del old_entry["source_policy_resolution"]
        old_entry["remaining_source_limits"][0] = OLD_LIMIT
        before = binding.project_task(self.history, self.previous[TASK], self.improvement, old_entry,
                                      reproduction_version="paper-reproduction/v2")
        after = binding.project_task(self.history, self.previous[TASK], self.improvement, self.entry,
                                     reproduction_version="paper-reproduction/v2")
        self.assertEqual(after, self.task)
        self.assertEqual(changed_leaves(before, after), {
            "/episode/primary_source_limits/0", "/blocking_issues/primary_source_limits/0",
            "/holds/primary_source_limits/0", "/blocking_issues/retained_secondary_improvement/2",
            "/next_implementation_action/retained_secondary_improvement/action"})
        self.assertEqual(after["blocking_issues"]["primary_source_limits"][0], EXPECTED_LIMIT)
        self.assertEqual(after["blocking_issues"]["retained_secondary_improvement"][2], EXPECTED_SECONDARY)
        self.assertEqual(set(before), set(after))
        self.assertEqual(self.history, historical)
        self.assertEqual(self.improvement, improvement)
        self.assertEqual(before["holds"]["preserved_predecessor_limits"], after["holds"]["preserved_predecessor_limits"])
        self.assertEqual(before["admission"], after["admission"])

    def test_context_authenticates_exact_provenance_and_keeps_outcomes_unknown(self):
        authority = self.entry["source_policy_resolution"]
        self.assertEqual(authority, {"resolution_id": "isttc-staged-qc-prose-v1",
                                   "provenance": binding.pin(PROVENANCE, source_bytes(PROVENANCE))})
        bound = self.context()
        self.assertIn(PROVENANCE, self.reader.requested)
        self.assertIn(PROVENANCE, bound["members"])
        self.assertEqual(bound["availability"], "unavailable")
        self.assertEqual(bound["reproduction_contract"]["eligibility"], "source_unresolved")
        self.assertTrue(all(cell["scientific_outcome"] == "unknown" for cell in bound["summary"]["cells"]))

    def test_wrong_authority_pin_extra_key_and_primary_text_are_rejected(self):
        for kind in ("resolution_id", "pin", "extra", "primary"):
            with self.subTest(kind=kind):
                scope = copy.deepcopy(self.previous.scope_decisions)
                entry = scope["entries"][TASK]
                if kind == "resolution_id": entry["source_policy_resolution"]["resolution_id"] = "unreviewed"
                elif kind == "pin": entry["source_policy_resolution"]["provenance"]["sha256"] = "0" * 64
                elif kind == "extra": entry["source_policy_resolution"]["ready"] = True
                else: entry["remaining_source_limits"][0] = "All source uncertainties resolved"
                with self.assertRaisesRegex(ValueError, "Unreviewed iSTTC source-policy resolution"):
                    binding.scope_decisions(scope)

    def test_wrong_task_and_incompatible_scope_route_are_rejected(self):
        entry = copy.deepcopy(self.entry)
        entry["task_id"] = "PAPER-UNREVIEWED-QC"
        with self.assertRaisesRegex(ValueError, "Unreviewed iSTTC source-policy resolution"):
            binding._isttc_qc_resolution(entry)
        scope = copy.deepcopy(self.previous.scope_decisions)
        entry = scope["entries"].pop(TASK)
        scope.setdefault("same_primary_corrections", {})[TASK] = entry
        self.assertTrue(binding.SCOPE_IDS <= set(scope["entries"]))
        with self.assertRaisesRegex(ValueError, "requires the unavailable scope route"):
            binding.scope_decisions(scope)

    def test_both_stale_expected_instructions_are_rejected(self):
        for field in ("blocker", "action"):
            with self.subTest(field=field):
                previous = copy.deepcopy(self.history)
                if field == "blocker": previous["blocking_issues"][2] += " stale"
                else: previous["next_implementation_action"]["action"] += " stale"
                with self.assertRaisesRegex(ValueError, "instruction preimage changed"):
                    binding.project_task(previous, self.previous[TASK], self.improvement, self.entry,
                                         reproduction_version="paper-reproduction/v2")

    def test_missing_provenance_fails_in_real_context(self):
        self.reader.overrides[PROVENANCE] = None
        with self.assertRaisesRegex(FileNotFoundError, "empirical-qc-source-resolution"):
            self.context()

    def test_altered_provenance_fails_production_byte_pin_reader(self):
        self.reader.overrides[PROVENANCE] = source_bytes(PROVENANCE) + b" "
        with self.assertRaisesRegex(ValueError, "iSTTC staged QC source-policy provenance pin mismatch"):
            self.context()

    def test_published_reproduction_and_provenance_keep_source_uncertainties_unresolved(self):
        bound = self.context()
        reproduction = bound["reproduction_contract"]
        text = reproduction["same_task"]["cohort"]["description"]
        self.assertIn("paper inclusive versus source strict boundaries, saved presence minimum0.95 and historical AllenSDK filtering remain unresolved", text)
        self.assertNotIn("remain qualified", text)
        self.assertIn("not a locally authenticated notebook body", text)
        self.assertIn("Counts are source design statements,not authenticated current identities", text)
        raw = source_bytes(HOME + "/reproduction.v2.json")
        role = json.loads(source_bytes(HOME + "/docs/provenance/reproduction.pre-scope.role.json"))
        self.assertEqual(role["active_contract"]["sha256"], binding.pin("ignored", raw)["sha256"])
        self.assertEqual(role["active_contract"]["bytes"], len(raw))
        self.assertEqual(role["active_contract"]["canonical_digest"], binding.engine(reproduction).contract_digest(reproduction))
        provenance = self.read_pin(self.entry["source_policy_resolution"]["provenance"], "QC provenance")
        self.assertFalse(provenance["readiness_promotion"])
        self.assertEqual(provenance["failed_local_capture"]["body_bytes"], 0)
        self.assertFalse(provenance["failed_local_capture"]["retry_performed"])

if __name__ == "__main__":
    unittest.main()
