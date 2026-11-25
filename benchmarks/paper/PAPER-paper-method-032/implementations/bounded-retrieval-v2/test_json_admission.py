"""Generated CLI admission controls; no feature arrays, model or dataset reads."""
from contextlib import contextmanager, redirect_stdout
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("mindeye_json_control", HERE / "streaming.py")
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)


def reference():
    ids = [f"generated-{i}" for i in range(1000)]
    return dict(task_id=s.legacy.TASK, contract_sha256=s.CONTRACT_SHA256,
                code_revision=s.legacy.CODE_REVISION, dataset_revision=s.legacy.DATA_REVISION,
                subject=1, image_ids=ids, retrieval_pools=s.legacy.freeze_pools(ids),
                feature_space=s.FEATURE_SPACE, image_features_sha256="a" * 64,
                population_manifest_sha256="b" * 64, feature_extraction_receipt_sha256="c" * 64)


class JsonAdmission(unittest.TestCase):
    def invoke(self, candidate, ref=None):
        raw = (ref or json.dumps(reference())).encode()
        @contextmanager
        def inert_mapping(*args, **kwargs):
            yield None
        output = io.StringIO()
        with patch.object(Path, "read_bytes", return_value=raw), \
             patch.object(Path, "read_text", return_value=candidate), \
             patch.object(s, "mapped_npy", side_effect=inert_mapping) as mapped, \
             patch.object(s, "evaluate", return_value={"generated_admission": True}) as evaluated, \
             redirect_stdout(output):
            try:
                s.main(["--reference", "generated-reference.json", "--reference-sha256",
                        hashlib.sha256(raw).hexdigest(), "--candidate", "generated-candidate.json",
                        "--image-features", "unopened-image.npy", "--brain-features", "unopened-brain.npy"])
            except ValueError:
                self.assertFalse(mapped.called, "ambiguous manifests must fail before feature mapping")
                self.assertFalse(evaluated.called, "ambiguous manifests must fail before scoring")
                raise
        return evaluated.call_args.args[:2], json.loads(output.getvalue())

    def test_unique_manifest_fields_keep_literal_values(self):
        candidate = {"subject": 1, "brain_features_sha256": "d" * 64,
                     "extension": {"label": "generated", "values": [1, 0.25]}}
        (ref, admitted), result = self.invoke(json.dumps(candidate))
        self.assertEqual(reference(), ref)
        self.assertEqual(candidate, admitted)
        self.assertEqual({"generated_admission": True}, result)

    def test_conflicting_candidate_subject_is_rejected(self):
        body = '{"subject":2,"subject":1,"brain_features_sha256":"' + "d" * 64 + '"}'
        with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
            self.invoke(body)

    def test_nested_candidate_duplicate_is_rejected(self):
        body = '{"brain_features_sha256":"' + "d" * 64 + '","extension":{"arm":"data","arm":"code"}}'
        with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
            self.invoke(body)

    def test_authenticated_reference_duplicate_is_rejected(self):
        ref = json.dumps(reference()).replace('"subject": 1', '"subject": 2, "subject": 1')
        with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
            self.invoke(json.dumps({"brain_features_sha256": "d" * 64}), ref)


if __name__ == "__main__":
    unittest.main(verbosity=2)
