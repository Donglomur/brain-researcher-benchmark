"""Current layout does not inherit execution authority from historical locks."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("campaign_gate", ROOT / "src/neurobench/campaign_gate.py")
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)


class CampaignAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        (self.root / "benchmarks").mkdir()
        self.registry = self.root / "benchmarks/registry.json"
        self.registry.write_text(json.dumps({"kind": "neuroscience_benchmark_registry", "schema_version": 1}))

    def test_preserved_contract_does_not_authorize_current_execution(self):
        with self.assertRaisesRegex(ValueError, "Current campaign execution authority is not published"):
            gate.require_current_authority(self.root)

    def test_invented_registry_authority_cannot_enable_dispatch(self):
        self.registry.write_text(json.dumps({"kind": "neuroscience_benchmark_registry",
                                            "campaign_authority": {"approved": True}}))
        with self.assertRaisesRegex(ValueError, "unsupported current campaign authority"):
            gate.require_current_authority(self.root)

    def test_dispatch_refuses_before_request_or_scientific_input_reads(self):
        with self.assertRaisesRegex(ValueError, "Current campaign execution authority is not published"):
            gate.admit(self.root, "NEURAL-FAKE", "run", None,
                       "/does/not/exist/request.json", "a" * 64, "b" * 64)

    def test_current_dispatcher_source_chain_loads(self):
        spec = importlib.util.spec_from_file_location("current_campaign_conditions", ROOT / "src/neurobench/campaign_conditions.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        captured = module.base._campaign_module(ROOT)
        self.assertEqual(captured.CONTRACT, "benchmarks/shared/study-exposure/campaign-contract-v1")


if __name__ == "__main__":
    unittest.main()
