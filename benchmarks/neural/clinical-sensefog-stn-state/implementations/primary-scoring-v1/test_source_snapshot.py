"""Generated dependency-byte controls; no clinical data or participant runs."""
import hashlib
import math
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch


HERE = Path(__file__).resolve().parent


def load_source(path, name):
    module = types.ModuleType(name)
    module.__file__ = str(path)
    exec(compile(path.read_bytes(), str(path), "exec"), module.__dict__)
    return module


class SourceSnapshotControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixtures = load_source(HERE / "test_score.py", "_sensefog_generated_fixtures")
        cls.score_source = (HERE / "sensefog_score.py").read_bytes()
        cls.mapper_source = (HERE.parent / "recording-lag-controls" / "sensefog_pairing.py").read_bytes()

    def prepare(self, directory):
        root = Path(directory)
        scorer = root / "primary-scoring-v1" / "sensefog_score.py"
        mapper = root / "recording-lag-controls" / "sensefog_pairing.py"
        scorer.parent.mkdir()
        mapper.parent.mkdir()
        scorer.write_bytes(self.score_source)
        mapper.write_bytes(self.mapper_source)
        return scorer, mapper

    def test_authenticated_mapper_bytes_are_executed_after_path_replacement(self):
        with tempfile.TemporaryDirectory() as temporary:
            scorer, mapper = self.prepare(temporary)
            read_bytes = Path.read_bytes
            replaced = []

            def replace_after_read(path):
                raw = read_bytes(path)
                if path == mapper and not replaced:
                    replacement = mapper.with_suffix(".replacement")
                    replacement.write_bytes(raw + b"\nraise RuntimeError('unverified mapper executed')\n")
                    replacement.replace(mapper)
                    replaced.append(True)
                return raw

            with patch.object(Path, "read_bytes", replace_after_read):
                module = load_source(scorer, "_sensefog_snapshot_race")
            self.assertEqual(replaced, [True])
            self.assertEqual(module.MAPPER_SHA256, hashlib.sha256(self.mapper_source).hexdigest())
            self.assertNotEqual(hashlib.sha256(mapper.read_bytes()).hexdigest(), module.MAPPER_SHA256)
            report = module.score(*self.fixtures.fixture(), max_cases=200)
            self.assertEqual(report["original_case_count"], 130)
            self.assertAlmostEqual(report["primary"]["score"], (-math.log(.1) - 11 * math.log(.9)) / 12)

    def test_changed_bytes_before_authentication_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            scorer, mapper = self.prepare(temporary)
            mapper.write_bytes(self.mapper_source + b"\n# changed before authentication\n")
            with self.assertRaisesRegex(ValueError, "mapper source changed"):
                load_source(scorer, "_sensefog_bad_mapper")

    def test_stable_source_keeps_complete_primary_and_paired_results(self):
        with tempfile.TemporaryDirectory() as temporary:
            scorer, _ = self.prepare(temporary)
            module = load_source(scorer, "_sensefog_stable_mapper")
            documents = self.fixtures.fixture()
            paired = self.fixtures.paired_fixture(*documents)
            observed = module.score(*documents, max_cases=200, paired_predictions=paired)
            reference = self.fixtures.mod.score(*documents, max_cases=200, paired_predictions=paired)
            self.assertEqual(observed, reference)
            self.assertEqual(len(observed["primary"]["participant_folds"]), 12)
            self.assertEqual(len(observed["paired_diagnostics"]["transforms"]), 20)
            self.assertEqual(observed["original_case_count"], 130)


if __name__ == "__main__":
    unittest.main(verbosity=2)
