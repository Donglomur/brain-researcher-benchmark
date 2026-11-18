"""Small generated metadata only; no data callbacks, files or production cohort."""

from copy import deepcopy
import hashlib
from pathlib import Path
import sys
import unittest


# Explicit source directory for isolated (-I) generated checks; no data path.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import access
from deps import count_packet


def cases(animals=8):
    result = []
    for index in range(animals):
        asset, animal = "asset-%s" % index, "animal-%s" % index
        result.append({
            "case_id": asset + ":0:MGv", "asset_id": asset, "animal_id": animal,
            "source_trial_row": 0, "source_trial_id": 100 + index,
            "trial_start_seconds": -5 + index, "trial_stop_seconds": -4.9999 + index,
            "region": "MGv", "source_cluster_count": index + 1,
        })
    return result


class AccessTests(unittest.TestCase):
    def test_profiles_are_fresh_and_use_selected_zero_label_validator(self):
        ids = ("direct-structured-zero-label-current-trial-v1",
               "frozen-programme-zero-label-current-trial-v1")
        for condition_id in ids:
            value = access.profile(condition_id)
            self.assertEqual(set(value), set(access.transports.PROFILE_FIELDS))
            self.assertEqual(access.validate_profile(value), value)
            value["feedback"] = "answers"
            with self.assertRaises(ValueError):
                access.validate_profile(value)
            self.assertEqual(access.profile(condition_id)["feedback"], "none")
        with self.assertRaises(ValueError):
            access.profile("trained-programme")

    def test_frozen_hash_folds_group_animals_once_without_label_release(self):
        metadata = cases()
        result = access.schedule(metadata)
        self.assertEqual(result, access.schedule(list(reversed(metadata))))
        expected_animals = sorted((row["animal_id"] for row in metadata), key=lambda animal:
                                 hashlib.sha256(("NEURAL-099|condition-b|outer-v1|" + animal).encode("utf-8")).hexdigest())
        expected_folds = {animal: index % 5 for index, animal in enumerate(expected_animals)}
        self.assertEqual(len(result), 8)
        self.assertEqual({row["animal_id"] for row in result}, set(expected_animals))
        self.assertEqual([row["outer_fold"] for row in result], sorted(row["outer_fold"] for row in result))
        for row in result:
            self.assertEqual(set(row), {"outer_fold", "animal_id", "asset_id", "source_trial_row"})
            self.assertEqual(row["outer_fold"], expected_folds[row["animal_id"]])
        for fold in range(5):
            self.assertEqual([row["animal_id"] for row in result if row["outer_fold"] == fold],
                             [animal for index, animal in enumerate(expected_animals) if index % 5 == fold])

    def test_regions_do_not_duplicate_trials_and_all_rows_stay_with_animal(self):
        metadata = cases(2)
        extra_region = deepcopy(metadata[0])
        extra_region.update(case_id="asset-0:0:MGm", region="MGm", source_cluster_count=2)
        next_rows = []
        for original in (metadata[0], extra_region):
            following = deepcopy(original)
            following.update(case_id=original["case_id"].replace(":0:", ":1:"), source_trial_row=1,
                             source_trial_id=201, trial_start_seconds=-4, trial_stop_seconds=-3.9999)
            next_rows.append(following)
        result = access.schedule(metadata + [extra_region] + next_rows)
        animal = [row for row in result if row["animal_id"] == "animal-0"]
        self.assertEqual([row["source_trial_row"] for row in animal], [0, 1])
        self.assertEqual(len({row["outer_fold"] for row in animal}), 1)
        self.assertEqual(len(result), 3)

    def test_mapping_and_chronology_fail_closed_without_value_access(self):
        same_animal = cases(2)
        same_animal[1]["animal_id"] = same_animal[0]["animal_id"]
        with self.assertRaisesRegex(ValueError, "one asset per animal"):
            access.schedule(same_animal)
        rows = cases(1)
        later = deepcopy(rows[0])
        later.update(case_id="asset-0:1:MGv", source_trial_row=1, source_trial_id=201,
                     trial_start_seconds=-6, trial_stop_seconds=-5.9999)
        with self.assertRaisesRegex(ValueError, "chronological"):
            access.schedule(rows + [later])
        with self.assertRaises(AssertionError):
            access._no_history("case", released_case_id="case")

    def test_production_is_not_qualified_by_generated_metadata_or_truthy_mode(self):
        with self.assertRaisesRegex(ValueError, "frozen source census"):
            access.schedule(cases(2), production=True)
        for value in (1, "true", None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                access.schedule(cases(2), production=value)
        self.assertEqual(access.PRODUCTION_CASE_HASH,
                         "508bdf026c6c223cc00c0a66c8ca56a6a70daed8e3acab57605e69e5c1ef4da3")

    def test_case_digest_recipe_matches_frozen_packet_normalization(self):
        metadata = cases(2)
        normalized = count_packet.validate_cases(metadata)
        self.assertEqual(access._canonical_cases(metadata), normalized)
        self.assertEqual(access._canonical_case_hash(access._canonical_cases(metadata)),
                         count_packet._case_hash(normalized))
        changed = deepcopy(metadata)
        changed[0]["source_trial_id"] += 1
        self.assertNotEqual(access._canonical_case_hash(access._canonical_cases(metadata)),
                            access._canonical_case_hash(access._canonical_cases(changed)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
