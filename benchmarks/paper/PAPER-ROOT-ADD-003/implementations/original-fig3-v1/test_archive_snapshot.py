"""Generated archive controls; original OSF bytes and responses are never read."""
import csv
import hashlib
import importlib.util
import io
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location("fig3_archive_control", Path(__file__).with_name("endpoint.py"))
e = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = e
spec.loader.exec_module(e)


def generated_archive(response):
    csv_text = io.StringIO(newline="")
    writer = csv.DictWriter(csv_text, fieldnames=e.SOURCE_COLUMNS)
    writer.writeheader()
    for participant in e.PARTICIPANTS:
        for item in e.ITEMS:
            condition = "B" if item <= 1000 else "D" if item <= 1250 else "S"
            row = dict.fromkeys(e.SOURCE_COLUMNS, "")
            row.update(target_UID=str(participant), roi=e.ROI, item_id=str(item),
                       sentence=f"generated sentence {item}", cond=condition,
                       cond_approach="B" if condition == "B" else condition + "_search",
                       response_target=str(response), response_target_non_norm="1", encoding_model_pred=str(item))
            writer.writerow(row)
    csv_body = csv_text.getvalue().encode()
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        member = tarfile.TarInfo(e.MEMBER)
        member.size = len(csv_body)
        archive.addfile(member, io.BytesIO(csv_body))
    return buffer.getvalue(), len(csv_body)


class ArchiveSnapshotControls(unittest.TestCase):
    def test_inplace_rewrite_cannot_relabel_decoded_responses(self):
        original, member_size = generated_archive(1)
        replacement, _ = generated_archive(2)
        original_open = tarfile.open
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "generated.tar.gz"
            path.write_bytes(original)
            rewrites = []

            def rewrite_before_decode(*args, **kwargs):
                # The source archive is modified after authentication but before
                # tar decoding. An open filesystem descriptor is still mutable.
                path.write_bytes(replacement)
                rewrites.append(True)
                return original_open(*args, **kwargs)

            with patch.object(e, "ARCHIVE_BYTES", len(original)), \
                    patch.object(e, "ARCHIVE_SHA256", hashlib.sha256(original).hexdigest()), \
                    patch.object(e, "MEMBER_BYTES", member_size), \
                    patch.object(e.tarfile, "open", side_effect=rewrite_before_decode):
                panel = e.load_original_archive(path)
            self.assertEqual(rewrites, [True])
            self.assertEqual(len(panel.normalized), 3)
            self.assertTrue(all(len(row) == 1500 for row in panel.normalized))
            self.assertTrue(all(value == 1. for row in panel.normalized for value in row))

    def test_unchanged_complete_generated_archive_is_preserved(self):
        original, member_size = generated_archive(1)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "generated.tar.gz"
            path.write_bytes(original)
            with patch.object(e, "ARCHIVE_BYTES", len(original)), \
                    patch.object(e, "ARCHIVE_SHA256", hashlib.sha256(original).hexdigest()), \
                    patch.object(e, "MEMBER_BYTES", member_size):
                panel = e.load_original_archive(path)
        self.assertEqual(panel.conditions.count("B"), 1000)
        self.assertEqual(panel.conditions.count("D"), 250)
        self.assertEqual(panel.conditions.count("S"), 250)
        self.assertEqual(panel.source_predictions, tuple(float(i) for i in range(1, 1501)))
        self.assertTrue(all(value == 1. for row in panel.normalized for value in row))

    def test_extra_archive_byte_rejected_before_decode(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "too_long.tar"
            path.write_bytes(b"12345")
            with patch.object(e, "ARCHIVE_BYTES", 4), \
                    patch.object(e.tarfile, "open", side_effect=AssertionError("decode must not occur")), \
                    self.assertRaisesRegex(e.InvalidPanel, "length"):
                e.load_original_archive(path)


if __name__ == "__main__":
    unittest.main()
