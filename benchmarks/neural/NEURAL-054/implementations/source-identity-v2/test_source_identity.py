"""Generated metadata controls only; no authentic source, labels or native arrays."""
from collections import Counter
from contextlib import contextmanager
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import adapter
from source_identity import IdentityError, PEOPLE, validate_roster


def generated_roster():
    rows = []
    for person in PEOPLE:
        epoch = 0
        for session in range(1, 13):
            for concept in range(1, 1855):
                image = (session - 1) * 1854 + concept
                rows.append({"person": person, "epoch_index": epoch,
                             "session": session, "run": (concept - 1) % 10 + 1,
                             "trial_type": "exp", "image": image, "concept": concept,
                             "image_path": f"generated-only/image-{image}.jpg"})
                epoch += 1
        for kind in ("repeat", "catch"):
            for index in range(2400):
                rows.append({"person": person, "epoch_index": epoch,
                             "session": index % 12 + 1, "run": index % 10 + 1,
                             "trial_type": kind})
                epoch += 1
    return rows


@contextmanager
def changed(rows, edits):
    old = {index: rows[index] for index in edits}
    try:
        for index, fields in edits.items():
            rows[index] = {**rows[index], **fields}
        yield rows
    finally:
        for index, row in old.items():
            rows[index] = row


def predecessor_marginal_checks(rows):
    """The exact experimental invariants used by the preserved issuer's join."""
    experimental = [row for row in rows if row["trial_type"] == "exp"]
    assert len(experimental) == len({(row["person"], row["image"])
                                     for row in experimental}) == 88992
    for person in PEOPLE:
        selected = [row for row in experimental if row["person"] == person]
        assert Counter(row["concept"] for row in selected) == Counter(
            {concept: 12 for concept in range(1, 1855)})
        assert Counter((row["session"], row["concept"]) for row in selected) == Counter(
            {(session, concept): 1 for session in range(1, 13)
             for concept in range(1, 1855)})


class SharedImageIdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = generated_roster()
        cls.order = list(range(1, 22249))
        cls.images = [{"image": image, "image_path": f"generated-only/image-{image}.jpg"}
                      for image in cls.order]

    def test_complete_panel_and_order_invariance(self):
        result = validate_roster(self.rows, image_order=self.order, images=self.images)
        self.assertEqual(result["experimental_rows"], 88992)
        reordered = validate_roster(list(reversed(self.rows)), image_order=list(reversed(self.order)))
        self.assertEqual(result, reordered)

    def test_concept_swap_passes_old_marginals_but_breaks_shared_target_join(self):
        with changed(self.rows, {27048: {"concept": 2}, 27049: {"concept": 1}}) as rows:
            predecessor_marginal_checks(rows)
            with self.assertRaisesRegex(IdentityError, "inconsistent concept"):
                validate_roster(rows)

    def test_person_specific_image_replacement_keeps_old_counts(self):
        with changed(self.rows, {27048: {"image": 999999,
                                       "image_path": "generated-only/replaced.jpg"}}) as rows:
            predecessor_marginal_checks(rows)
            with self.assertRaisesRegex(IdentityError, "exact 22248 source images"):
                validate_roster(rows)

    def test_same_image_id_with_different_source_path(self):
        with changed(self.rows, {27048: {"image_path": "generated-only/different.jpg"}}) as rows:
            with self.assertRaisesRegex(IdentityError, "inconsistent concept or source path"):
                validate_roster(rows)

    def test_duplicate_physical_path_with_distinct_image_ids(self):
        edits = {offset + 1: {"image_path": self.rows[0]["image_path"]}
                 for offset in (0, 27048, 54096, 81144)}
        with changed(self.rows, edits) as rows:
            with self.assertRaisesRegex(IdentityError, "multiple image IDs"):
                validate_roster(rows)

    def test_extra_duplicate_visual_row_defeats_old_dictionary_count(self):
        order = self.order + [1]
        self.assertEqual(len({image: index for index, image in enumerate(order)}), 22248)
        with self.assertRaisesRegex(IdentityError, "visual row order"):
            validate_roster(self.rows, image_order=order)

    def test_visual_missing_and_wrong_image(self):
        for order in (self.order[:-1], self.order[:-1] + [999999]):
            with self.subTest(rows=len(order)):
                with self.assertRaisesRegex(IdentityError, "visual row order"):
                    validate_roster(self.rows, image_order=order)

    def test_extraction_manifest_must_match_identity_and_coverage(self):
        for images in (self.images[:-1] + [self.images[0]],
                       [{**self.images[0], "image_path": "generated-only/wrong.jpg"}] + self.images[1:]):
            with self.assertRaises(IdentityError):
                validate_roster(self.rows, images=images)

    def test_source_epoch_and_integer_identity_are_not_coerced(self):
        for edit in ({"epoch_index": 1}, {"image": True}, {"concept": 1.0}):
            with changed(self.rows, {0: edit}) as rows:
                with self.assertRaises(IdentityError):
                    validate_roster(rows)

    def test_predecessor_pins_bind_real_metadata_only_modules(self):
        self.assertTrue(callable(adapter._module("preparation").extract))
        self.assertTrue(callable(adapter._module("views").FeatureIssuer))

    def test_wrong_authority_fails_before_roster_read(self):
        admission = {"domain": "wrong", "execution_selection": "selected"}
        with patch.object(adapter, "_roster") as read:
            with self.assertRaises(IdentityError):
                adapter.feature_issuer(admission, "unused", b"", "selected")
            read.assert_not_called()

    def test_both_adapters_refuse_bad_join_before_native_dispatch(self):
        admission = {"images": self.images, "image_order": self.order}
        with changed(self.rows, {27048: {"concept": 2}, 27049: {"concept": 1}}) as rows:
            with patch.object(adapter, "_roster", return_value=rows), \
                 patch.object(adapter, "_authorize"), patch.object(adapter, "_module") as dispatch:
                with self.assertRaises(IdentityError):
                    adapter.extract(admission, "unused", "unused", "unused", "selected")
                with self.assertRaises(IdentityError):
                    adapter.feature_issuer(admission, "unused", b"", "selected")
                dispatch.assert_not_called()

    def test_valid_adapters_forward_original_arguments_and_return(self):
        admission = {"images": self.images, "image_order": self.order}
        calls = []
        def forward(*args):
            calls.append(args)
            return "unchanged-predecessor-result"
        module = SimpleNamespace(extract=forward, FeatureIssuer=forward)
        with patch.object(adapter, "_roster", return_value=self.rows), \
             patch.object(adapter, "_authorize"), patch.object(adapter, "_module", return_value=module):
            self.assertEqual(adapter.extract(admission, "source", "images", "out", "selected"),
                             "unchanged-predecessor-result")
            self.assertEqual(calls[-1], (admission, "source", "images", "out", "selected"))
            self.assertEqual(adapter.feature_issuer(admission, "root", b"secret", "selected"),
                             "unchanged-predecessor-result")
            self.assertEqual(calls[-1], (admission, "root", b"secret", "selected"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
