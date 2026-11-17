"""Generated fixtures only. No authentic files, arrays, or network are opened.

Run from this directory with Python unittest discovery. The parent owns the
shared test-pool invocation. These checks exercise metadata joins and semantics,
not physiological scoring or source authenticity of the real dataset.
"""

from copy import deepcopy
import hashlib
import unittest

from support import (MGN_001421_METADATA_PROFILE, SupportError,
                     build_support, decode_pinned_json)


DIGEST = "a" * 64


def fixture():
    assets = []
    records = []
    specifications = [
        ("asset-a", "mouse-a", 3, [(7, "MGv", "good"), (8, "MGv", "mua"),
                                   (9, " ", "mua")]),
        # Repeated unit 7 across assets is legitimate, and a repeated source
        # subject is retained rather than being treated as a second animal.
        ("asset-b", "mouse-a", 4, [(7, "SG", "mua"), (12, " ", "good")]),
    ]
    for aid, subject, trials, assignments in specifications:
        asset = {"asset_id": aid, "subject_id": subject,
                 "path": subject + "/" + aid + ".nwb", "bytes": 100,
                 "sha256": "b" * 64}
        assets.append(asset)
        regions = {}
        quality = {}
        units = []
        for uid, region, label in assignments:
            units.append({"unit_id": uid, "electrode_row": 0,
                          "location_literal": region, "quality_literal": label})
            regions[region] = regions.get(region, 0) + 1
            quality[label] = quality.get(label, 0) + 1
        records.append({
            **{k: asset[k] for k in ("asset_id", "path", "bytes", "sha256")},
            "nwb_version": "2.7.0", "obs_intervals_present": False,
            "response_array_values_opened": False,
            "identity": {"general/subject/subject_id": subject,
                         "session_start_time": "2021-01-01T12:00:00-05:00",
                         "timestamps_reference_time": ["2021-01-01T12:00:00-05:00"]},
            "declared_unit_count": len(units), "unit_assignments": units,
            "source_anatomy_unit_counts": regions, "source_quality_unit_counts": quality,
            "coordinate_support": {axis: {"shape": [2]} for axis in ("x", "y", "z")},
            "schema": {**{"intervals/trials/" + k: {"shape": [trials]}
                          for k in ("id", "start_time", "stop_time")},
                       "units/spike_times_index": {"shape": [len(units)]}},
        })
    return ({"source_manifest_sha256": DIGEST, "source_files": 2,
             "source_bytes": 200, "response_array_values_opened": False,
             "scientific_qualified": False, "records": records}, {"assets": assets})


def prepare(census=None, sources=None, profile=None):
    if census is None:
        census, sources = fixture()
    return build_support(census, sources, source_manifest_sha256=DIGEST,
                         qualification_profile=profile)


class SupportTests(unittest.TestCase):
    def test_ragged_clusters_and_denominator_audit(self):
        result = prepare()
        first, second = result["assets"]
        self.assertEqual(first["regions"], [{"region": "MGv", "cluster_ids": [7, 8],
                         "cluster_count": 2, "quality_counts": {"good": 1, "mua": 1}}])
        self.assertEqual(second["regions"][0]["cluster_ids"], [7])
        self.assertEqual(second["regions"][0]["region"], "SG")
        self.assertIn("SG", first["unsupported_named_regions"])
        self.assertIn("MGv", second["unsupported_named_regions"])
        self.assertEqual(first["unassigned_cluster_ids"], [9])
        self.assertEqual(second["unassigned_cluster_ids"], [12])
        self.assertEqual(result["summary"]["eligible_cluster_count"], 3)
        self.assertEqual(result["summary"]["unassigned_cluster_count"], 2)
        self.assertEqual(result["summary"]["nonempty_region_cell_count"], 2)

    def test_rows_and_identity_stay_declared_metadata(self):
        result = prepare()
        self.assertEqual([a["source_trial_rows"] for a in result["assets"]], [3, 4])
        self.assertEqual(result["summary"]["source_trial_rows"], 7)
        self.assertEqual(result["summary"]["source_file_count"], 2)
        self.assertEqual(result["summary"]["source_subject_count"], 1)
        self.assertTrue(all(a["animal_id"] is None for a in result["assets"]))
        self.assertTrue(all(not value for value in result["qualification"].values()))
        for asset in result["assets"]:
            self.assertNotIn("recording_end", asset["clock"])
            self.assertNotIn("trial_ids", asset)
            self.assertFalse(asset["clock"]["actual_event_times_authenticated"])

    def test_order_independence_and_no_input_mutation(self):
        census, sources = fixture()
        original = deepcopy((census, sources))
        expected = prepare(census, sources)
        self.assertEqual((census, sources), original)
        census["records"].reverse()
        sources["assets"].reverse()
        for record in census["records"]:
            record["unit_assignments"].reverse()
        self.assertEqual(prepare(census, sources), expected)

    def test_full_metadata_profile_enforced(self):
        census, sources = fixture()
        profile = {"source_manifest_sha256": DIGEST, **prepare()["summary"]}
        result = prepare(census, sources, profile)
        self.assertTrue(result["qualification"]["metadata_profile_matched"])
        self.assertFalse(result["qualification"]["ready_for_scoring"])
        profile["eligible_cluster_count"] = 4
        with self.assertRaises(SupportError):
            prepare(census, sources, profile)
        with self.assertRaises(SupportError):
            prepare(census, sources, MGN_001421_METADATA_PROFILE)

    def test_missing_duplicate_and_mismatched_source_assets_rejected(self):
        for mutation in (
            lambda c, s: c["records"].pop(),
            lambda c, s: c["records"].__setitem__(1, deepcopy(c["records"][0])),
            lambda c, s: s["assets"][1].__setitem__("asset_id", "asset-a"),
            lambda c, s: c["records"][0].__setitem__("sha256", "c" * 64),
            lambda c, s: c.__setitem__("source_manifest_sha256", "c" * 64),
            lambda c, s: c.__setitem__("source_bytes", 201),
        ):
            with self.subTest(mutation=mutation):
                census, sources = fixture()
                mutation(census, sources)
                with self.assertRaises(SupportError):
                    prepare(census, sources)

    def test_inconsistent_rows_or_clocks_rejected(self):
        for mutation in (
            lambda r: r["schema"]["intervals/trials/id"].__setitem__("shape", [2]),
            lambda r: r["schema"]["intervals/trials/start_time"].__setitem__("shape", [True]),
            lambda r: r["schema"]["intervals/trials/stop_time"].__setitem__("shape", [3, 1]),
            lambda r: r["identity"].__setitem__("timestamps_reference_time", ["other"]),
            lambda r: r.__setitem__("obs_intervals_present", True),
        ):
            with self.subTest(mutation=mutation):
                census, sources = fixture()
                mutation(census["records"][0])
                with self.assertRaises(SupportError):
                    prepare(census, sources)

    def test_cluster_assignment_and_category_errors_rejected(self):
        for mutation in (
            lambda r: r["unit_assignments"][1].__setitem__("unit_id", 7),
            lambda r: r["unit_assignments"][0].__setitem__("unit_id", True),
            lambda r: r["unit_assignments"][0].__setitem__("electrode_row", 2),
            lambda r: r["unit_assignments"][0].__setitem__("location_literal", "MGN"),
            lambda r: r["unit_assignments"][0].__setitem__("location_literal", "MGv "),
            lambda r: r["unit_assignments"][0].__setitem__("quality_literal", "noise"),
            lambda r: r["source_anatomy_unit_counts"].__setitem__("MGv", 3),
            lambda r: r["source_quality_unit_counts"].__setitem__("good", True),
        ):
            with self.subTest(mutation=mutation):
                census, sources = fixture()
                mutation(census["records"][0])
                with self.assertRaises(SupportError):
                    prepare(census, sources)

    def test_absent_named_support_is_not_zero_response(self):
        census, sources = fixture()
        record = census["records"][0]
        for unit in record["unit_assignments"]:
            unit["location_literal"] = " "
        record["source_anatomy_unit_counts"] = {" ": 3}
        with self.assertRaisesRegex(SupportError, "no named source support"):
            prepare(census, sources)

    def test_pinned_json_rejects_corruption_duplicates_and_nonfinite(self):
        raw = b'{"valid": 1}'
        digest = hashlib.sha256(raw).hexdigest()
        self.assertEqual(decode_pinned_json(raw, digest), {"valid": 1})
        with self.assertRaises(SupportError):
            decode_pinned_json(raw + b" ", digest)
        with self.assertRaises(SupportError):
            decode_pinned_json(raw, digest, max_bytes=3)
        for malformed in (b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":1e999}', b'[]', b'\xff'):
            with self.subTest(raw=malformed):
                with self.assertRaises(SupportError):
                    decode_pinned_json(malformed, hashlib.sha256(malformed).hexdigest())


if __name__ == "__main__":
    unittest.main()
