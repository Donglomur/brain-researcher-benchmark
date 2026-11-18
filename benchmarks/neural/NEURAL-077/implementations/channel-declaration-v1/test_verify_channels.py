"""Generated metadata controls only; no authentic EEG or channel table."""
import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("n077_channel_declaration", Path(__file__).with_name("verify_channels.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def table(units="uV"):
    rows = ["name\ttype\tunits"]
    rows.extend(f"{name}\t{'EEG' if i < 30 else 'EOG'}\t{units}" for i, name in enumerate(m.CHANNELS))
    return ("\n".join(rows) + "\n").encode()


def inventory():
    rows = []
    for i in range(1, 41):
        path = f"sub-{i:03d}/eeg/sub-{i:03d}_task-P3_channels.tsv"
        url = "https://data.nemar.org/nm000132/v1.0.0/" + path
        rows.append({"path": path, "size": 512, "checksum_algorithm": "git",
                     "checksum": m.CHANNEL_GIT_SHA1, "bytes_url": url, "url": url})
    return rows


class ChannelDeclarationTests(unittest.TestCase):
    def test_generated_declaration_is_not_device_calibration(self):
        out = m.parse_channels(table())
        self.assertEqual(len(out["channels"]), 33)
        self.assertEqual(out["declared_unit_strings"], ["uV"])
        self.assertTrue(out["unit_declaration_complete"])
        self.assertFalse(out["device_calibration_verified"])
        self.assertFalse(out["event_timing_verified"])
        self.assertIsNone(out["amplitude_scale_applied"])

    def test_unknown_and_mixed_units_are_reported_without_conversion(self):
        out = m.parse_channels(table("n/a"))
        self.assertFalse(out["unit_declaration_complete"])
        out = m.parse_channels(table().replace(b"FP1\tEEG\tuV", b"FP1\tEEG\tmV"))
        self.assertFalse(out["units_uniform"])
        self.assertEqual(out["declared_unit_strings"], ["mV", "uV"])
        self.assertIsNone(out["amplitude_scale_applied"])

    def test_whitespace_only_units_refuse_instead_of_claiming_complete(self):
        for units in (" ", "   ", "\u2003"):
            with self.subTest(units=repr(units)):
                with self.assertRaisesRegex(ValueError, "nonempty declarations"):
                    m.parse_channels(table(units))

    def test_reordered_duplicate_missing_or_wrong_role_channels_refuse(self):
        good = table().decode().splitlines()
        bad = []
        rows = good.copy(); rows[1], rows[2] = rows[2], rows[1]; bad.append(rows)
        rows = good.copy(); rows[2] = rows[1]; bad.append(rows)
        bad.append(good[:-1])
        rows = good.copy(); rows[-1] = rows[-1].replace("EOG", "EEG"); bad.append(rows)
        for rows in bad:
            with self.subTest(rows=rows[-1]):
                with self.assertRaises(ValueError):
                    m.parse_channels(("\n".join(rows) + "\n").encode())

    def test_duplicate_headers_ragged_bytes_and_empty_units_refuse(self):
        for body in [table().replace(b"name\ttype\tunits", b"name\ttype\tname"),
                     table().replace(b"FP1\tEEG\tuV", b"FP1\tEEG"),
                     table().replace(b"FP1\tEEG\tuV", b"FP1\tEEG\t"), b"\xff", b"\0"]:
            with self.subTest(body=body[:30]):
                with self.assertRaises((ValueError, UnicodeDecodeError)):
                    m.parse_channels(body)

    def test_complete_manifest_inventory_and_immutable_input(self):
        rows = inventory(); before = copy.deepcopy(rows)
        self.assertEqual(len(m.validate_inventory(rows)), 40)
        self.assertEqual(rows, before)

    def test_manifest_missing_duplicate_foreign_changed_pin_and_route_refuse(self):
        good = inventory()
        altered = []
        altered.append(good[:-1]); altered.append(good + [good[0]])
        for key, value in [("size", True), ("checksum", "0" * 40),
                           ("checksum_algorithm", "sha1"), ("bytes_url", "https://example.com/a")]:
            rows = copy.deepcopy(good); rows[0][key] = value; altered.append(rows)
        rows = copy.deepcopy(good); rows[0]["path"] = rows[0]["path"].replace("sub-001", "sub-041"); altered.append(rows)
        for rows in altered:
            with self.subTest(rows=rows[0]):
                with self.assertRaises(ValueError):
                    m.validate_inventory(rows)

    def test_no_unpinned_manifest_can_admit_generated_table(self):
        with self.assertRaisesRegex(ValueError, "Exact retained release manifest"):
            m.verify(b"[]", table())

    def test_bounded_file_reader_refuses_wrong_extent_and_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "channels.tsv"; path.write_bytes(b"abc")
            self.assertEqual(m.read_exact(path, 3), b"abc")
            with self.assertRaises(ValueError):
                m.read_exact(path, 4)
            link = Path(directory) / "link"; link.symlink_to(path)
            with self.assertRaises(ValueError):
                m.read_exact(link, 3)


if __name__ == "__main__":
    unittest.main()
