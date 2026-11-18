"""Generated metadata controls; no neural arrays, prediction or fitting."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import census

CATALOGUE = Path(os.environ.get("N074_CATALOGUE_PATH", str(
    HERE.parent / "agent-operator/source/n074/catalogue.py")))
PEOPLE, ENDPOINTS = census.read_catalogue(CATALOGUE.read_bytes())


def record(person, endpoint, image_id, direction="ffx", session="ses-01", valid=False, run_id=None):
    _, source_task, contrast = endpoint
    task = census.TASK_TO_API[source_task]
    return {
        "id": image_id, "collection_id": 6618, "subject_id": person, "task": task,
        "name": f"{person}_{session}_task-{task}_{direction}_" +
                (f"run-{run_id}_" if run_id is not None else "") + contrast,
        "map_type": "Z map", "analysis_level": "single-subject", "modality": "fMRI-BOLD",
        "data_origin": "volume", "is_thresholded": False, "number_of_subjects": 1,
        "is_valid": valid, "file_size": 3000000,
    }


def rows():
    return [record(person, endpoint, 1000 + 51 * p + e)
            for p, person in enumerate(PEOPLE) for e, endpoint in enumerate(ENDPOINTS)]


def run(items):
    return census.census(((0, i, row) for i, row in enumerate(items)), PEOPLE, ENDPOINTS, len(items))


class CensusControls(unittest.TestCase):
    def test_full_roster_keeps_unqualified_invalid_metadata_candidates(self):
        result = run(rows())
        self.assertEqual(result["declared_cases"], 663)
        self.assertEqual(result["counts"], {"one_metadata_ffx_candidate": 663})
        self.assertEqual(len(result["cells"]), 663)
        self.assertFalse(result["cells"][0][3][0][3])
        self.assertFalse(result["content_sha256s_verified"])
        self.assertFalse(result["readiness_promoted"])

    def test_missing_and_repeated_session_never_shrink_or_choose_panel(self):
        items = rows()[1:]
        items.append(record(PEOPLE[0], ENDPOINTS[1], 999999, session="ses-99"))
        result = run(items)
        self.assertEqual(result["counts"], {"no_ffx_candidate": 1,
                         "multiple_metadata_ffx_candidates": 1, "one_metadata_ffx_candidate": 661})
        self.assertEqual(result["cells"][0][3], [])
        self.assertEqual(len(result["cells"][1][3]), 2)
        self.assertEqual(result["declared_cases"], 663)

    def test_ap_pa_are_separate_and_pairing_is_session_specific(self):
        items = rows()
        items.extend([record(PEOPLE[0], ENDPOINTS[0], 5000, "dir-ap"),
                      record(PEOPLE[0], ENDPOINTS[0], 5001, "dir-pa", "ses-99")])
        result = run(items)
        first = result["cells"][0]
        self.assertEqual(first[2], "one_metadata_ffx_candidate")
        self.assertEqual(first[4:], [1, 1])
        self.assertEqual(first[3][0][-2:], [1, 0])
        self.assertEqual(result["ffx_metadata_candidates"], 663)

    def test_unparsed_relevant_row_and_metadata_identity_conflict_fail_closed(self):
        for change in ({"name": "unrecognized"}, {"subject_id": PEOPLE[1]},
                       {"task": "archi_spatial"}, {"collection_id": 1},
                       {"map_type": "T map"}, {"is_thresholded": True},
                       {"number_of_subjects": 2}):
            with self.subTest(change=change):
                items = rows()
                items[0] = dict(items[0], **change)
                with self.assertRaises(census.CensusError):
                    run(items)

    def test_duplicate_image_and_incomplete_source_snapshot_rejected(self):
        items = rows()
        items[1] = dict(items[1], id=items[0]["id"])
        with self.assertRaises(census.CensusError):
            run(items)
        with self.assertRaises(census.CensusError):
            census.census(((0, i, row) for i, row in enumerate(rows()[:-1])), PEOPLE, ENDPOINTS, 663)

    def test_alias_and_catalogue_cannot_silently_change_population(self):
        changed = ENDPOINTS[:-1] + ((ENDPOINTS[-1][0], "unrecognized_task", ENDPOINTS[-1][2]),)
        with self.assertRaises(census.CensusError):
            census.census((), PEOPLE, changed, 1)
        with self.assertRaises(census.CensusError):
            census.census((), PEOPLE[:-1], ENDPOINTS, 1)
        with self.assertRaises(census.CensusError):
            census.read_catalogue(b"DECLARED_PEOPLE = ('sub-01',)\n")

    def test_snapshot_pin_and_duplicate_json_key_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "metadata.json"
            body = b'{"a":1}'
            path.write_bytes(body)
            digest = hashlib.sha256(body).hexdigest()
            self.assertEqual(census.read_pinned(path, len(body), digest, 1024), body)
            for extent, pin in ((len(body) + 1, digest), (len(body), "0" * 64)):
                with self.assertRaises(census.CensusError):
                    census.read_pinned(path, extent, pin, 1024)
            link = Path(directory) / "link.json"
            link.symlink_to(path)
            with self.assertRaises(census.CensusError):
                census.read_pinned(link, len(body), digest, 1024)
        with self.assertRaises(census.CensusError):
            census.decode(b'{"a":1,"a":2}')

    def test_explicit_run_identity_keeps_rsvp_matches_and_ambiguity(self):
        endpoint = next(e for e in ENDPOINTS if e[1] == "RSVPLanguage")
        e_index = ENDPOINTS.index(endpoint)
        items = rows()
        items[e_index] = record(PEOPLE[0], endpoint, 1000 + e_index, run_id="03")
        items.append(record(PEOPLE[0], endpoint, 6000, run_id="04"))
        result = run(items)
        cell = result["cells"][e_index]
        self.assertEqual(cell[2], "multiple_metadata_ffx_candidates")
        self.assertEqual([c[2] for c in cell[3]], ["03", "04"])
        self.assertEqual(result["declared_cases"], 663)
        self.assertEqual(result["counts"]["one_metadata_ffx_candidate"], 662)
        self.assertFalse(cell[3][0][3])

    def test_pairing_does_not_cross_runs_or_sessions(self):
        endpoint = next(e for e in ENDPOINTS if e[1] == "RSVPLanguage")
        e_index = ENDPOINTS.index(endpoint)
        items = rows()
        items[e_index] = record(PEOPLE[0], endpoint, 1000 + e_index, run_id="03")
        items.extend([record(PEOPLE[0], endpoint, 6100, "dir-ap", run_id="03"),
                      record(PEOPLE[0], endpoint, 6101, "dir-pa", run_id="04"),
                      record(PEOPLE[0], endpoint, 6102, "dir-pa", "ses-99", run_id="03")])
        cell = run(items)["cells"][e_index]
        self.assertEqual(cell[4:], [1, 2])
        self.assertEqual(cell[3][0][-2:], [1, 0])

    def test_malformed_run_tag_cannot_become_false_absence(self):
        items = rows()
        items[0] = dict(items[0], name=items[0]["name"].replace("_ffx_", "_ffx_run-bad_"))
        with self.assertRaises(census.CensusError):
            run(items)


if __name__ == "__main__":
    unittest.main(verbosity=1)
