"""One complete2054 generated transport panel; real projection tested separately.

The projection seam emits job metadata only, never an authentic response. All
2054 durable submissions use typed failures, keeping storage finite while testing
the actual original-coordinate sequence, commitment and complete-store plumbing.
"""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


delivery = load("temporal_generated_delivery", HERE / "delivery.py")
fixtures = load("temporal_generated_protocol_fixture", HERE / "test_protocol.py")
collector = load("temporal_generated_delivery_collector", HERE / "submissions.py")
WRITTEN_BYTES = 0


class MetadataProjection:
    """Explicit generated-only seam; real metadata and immutable protocol remain."""
    def __init__(self, protocol):
        self.protocol = protocol
        self.observed = []
        self.target_calls = 0

    def __getattr__(self, key):
        return getattr(self.protocol, key)

    def project_job(self, _input_root, job_id):
        info = self.protocol.job_info(job_id)
        self.observed.append(job_id)
        return {"generated_metadata_seam": True, "job": info["job"]}

    def targets(self, *_args):
        self.target_calls += 1
        raise AssertionError("all-failure transport control must not read any target")


class DeliveryControls(unittest.TestCase):
    def test_complete_cv_then_full_commitment_and_tamper_refusal(self):
        global WRITTEN_BYTES
        source = fixtures.p.Source(fixtures.SOURCE_DIRECTORY)
        _rows, _raw, _vars, manifest, plans = fixtures.generated(source)
        plan = plans["named_response_columns"]
        protocol = fixtures.p.Protocol(plan, plan["plan_sha256"], manifest,
                                       "b" * 64, "paper_data_author_code", source)
        seam = MetadataProjection(protocol)
        failure = {"type": "candidate_declined", "message": "generated transport control"}
        with tempfile.TemporaryDirectory(prefix="generated-delivery-", dir=HERE) as temporary:
            parent = Path(temporary).resolve()
            session = delivery.DeliverySession(seam, parent / "run")
            with self.assertRaisesRegex(ValueError, "observation must precede"):
                session.submit(failure=failure)
            with self.assertRaisesRegex(ValueError, "all 2054"):
                session.seal()
            for i in range(2054):
                observation = session.observe("NO_AUTHENTIC_INPUT")
                self.assertTrue(observation["generated_metadata_seam"])
                self.assertEqual(observation["job"]["mode"], "cv" if i < 1896 else "full")
                if i == 0:
                    with self.assertRaisesRegex(ValueError, "commit the current"):
                        session.observe("NO_AUTHENTIC_INPUT")
                    with self.assertRaisesRegex(ValueError, "prediction row support"):
                        session.submit(predictions=[[0.0] * 819])
                    self.assertEqual(session.committed_jobs, 0)
                if i < 1896:
                    self.assertFalse((session.directory / "CV_FREEZE.json").exists())
                else:
                    cv = json.loads((session.directory / "CV_FREEZE.json").read_text())
                    self.assertEqual(cv["count"], 1896)
                    self.assertEqual([x["job_id"] for x in cv["records"]], seam.observed[:1896])
                session.submit(failure=failure)
            self.assertTrue(session.complete)
            self.assertEqual(session.committed_jobs, 2054)
            with self.assertRaisesRegex(ValueError, "already complete"):
                session.observe("NO_AUTHENTIC_INPUT")
            # A same-extent rewrite after full-data delivery cannot alter the
            # earlier cryptographic CV commitment and pass the final seal.
            first_cv = session.predictions_directory / session._pins[0]["path"]
            original = first_cv.read_bytes()
            changed = original.replace(b"generated transport control", b"generated transport contr0l")
            self.assertNotEqual(changed, original)
            first_cv.chmod(0o600)
            first_cv.write_bytes(changed); WRITTEN_BYTES += len(changed)
            with self.assertRaisesRegex(ValueError, "committed record bytes changed"):
                session.seal()
            self.assertFalse((session.predictions_directory / "MANIFEST.json").exists())
            first_cv.write_bytes(original); WRITTEN_BYTES += len(original)
            first_cv.chmod(0o444)
            result = session.seal()
            receipt = json.loads((session.directory / "DELIVERY_RECEIPT.json").read_text())
            self.assertEqual(receipt["cv_jobs_committed_before_full_observations"], 1896)
            self.assertEqual(receipt["full_jobs_committed"], 158)
            self.assertFalse(receipt["runtime_isolation_qualified"])
            self.assertFalse(receipt["scientific_qualification"])
            with self.assertRaisesRegex(ValueError, "all 2054"):
                session.seal()
            score = collector.evaluate(session.predictions_directory, seam,
                                       result["submission"]["sha256"], "NO_AUTHENTIC_INPUT", 19)
            self.assertEqual(seam.target_calls, 0)
            self.assertEqual(len(score["failures"]), 2054)
            self.assertTrue(all(x["status"] == "undefined_incomplete_or_nonfinite"
                                for x in score["figure3_regional_cv"]))
            with self.assertRaises(FileExistsError):
                delivery.DeliverySession(seam, parent / "run")
            WRITTEN_BYTES += sum(p.stat().st_size for p in parent.rglob("*") if p.is_file())
            self.assertLess(WRITTEN_BYTES, 5 * 1024 * 1024)


if __name__ == "__main__":
    try:
        unittest.main(verbosity=2)
    finally:
        print("CUMULATIVE_GENERATED_FILE_WRITES_BYTES=%d" % WRITTEN_BYTES)
