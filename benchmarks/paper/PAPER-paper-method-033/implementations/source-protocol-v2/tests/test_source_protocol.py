"""Generated software controls, with no NSD, images, targets, or models."""
import importlib.util
from pathlib import Path
import sys
import unittest
import numpy as np

SPEC = importlib.util.spec_from_file_location('source_protocol', Path(__file__).resolve().parents[1] / 'source_protocol.py')
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)
p = MODULE


def embed(*values, dtype=np.float64):
    result = np.zeros(p.SELECTION_SHAPE, dtype=dtype)
    result.flat[:len(values)] = values
    return result


class MembershipTests(unittest.TestCase):
    def inventory(self):
        # Deliberately unpadded IDs make lexicographic/numerical sorting differ.
        return [f'{key}.{ext}' for key in range(4100) for ext in p.REQUIRED_EXTENSIONS]

    def test_original_budgets_and_source_lexicographic_rule(self):
        files = self.inventory()
        memberships = p.calibration_memberships(reversed(files))
        ordered = tuple(sorted(str(i) for i in range(4100)))
        self.assertEqual(tuple(memberships), (500, 1500, 4000))
        for budget in p.BUDGETS:
            self.assertEqual(memberships[budget], ordered[:budget])
        self.assertEqual(memberships[500][:4], ('0', '1', '10', '100'))
        self.assertEqual(memberships[500], memberships[4000][:500])

    def test_inventory_integrity(self):
        files = self.inventory()
        for broken in (files[:-1], files + [files[0]], files[:3000], ['no_period'] + files,
                       ['nested/0.jpg'] + files, '0.jpg'):
            with self.subTest(type=str(broken)[:20]), self.assertRaises(p.SourceProtocolError):
                p.calibration_memberships(broken)

    def test_unknown_extensions_do_not_add_samples(self):
        files = self.inventory()
        self.assertEqual(p.calibration_memberships(files), p.calibration_memberships(files + ['extra.txt', '0.other.npy']))

    def test_source_subj_extension_cannot_silently_change_prefix(self):
        with self.assertRaises(p.SourceProtocolError):
            p.calibration_memberships(self.inventory() + ['!only_subj.subj'])

    def test_source_subj_extension_on_complete_sample_preserves_membership(self):
        files = self.inventory()
        self.assertEqual(p.calibration_memberships(files), p.calibration_memberships(files + ['0.subj']))


class SelectionTests(unittest.TestCase):
    def test_cosine_not_pearson_and_first_tie(self):
        target = embed(1, 2, 3)
        candidates = [embed(-1, -2, -3), embed(3, 2, 1), embed(1, 2, 3)]
        candidates += [embed(1, 2, 3)] * 5
        result = p.select_best_of_eight(target, iter(candidates))
        self.assertEqual(result.index, 2)
        self.assertAlmostEqual(result.cosine_similarities[0], -1)
        self.assertAlmostEqual(result.cosine_similarities[1], 10 / 14)
        self.assertAlmostEqual(result.cosine_similarities[2], 1)

    def test_offset_changes_cosine_even_when_pearson_is_same(self):
        target = np.arange(257 * 768, dtype=np.float64).reshape(p.SELECTION_SHAPE)
        candidates = [target + 1e6] + [target.copy() for _ in range(7)]
        result = p.select_best_of_eight(target, candidates)
        self.assertEqual(result.index, 1)
        self.assertLess(result.cosine_similarities[0], 0.9)

    def test_float32_matches_direct_source_algebra(self):
        target = embed(1, 4, -2, dtype=np.float32)
        candidates = [embed(i, 8-i, -i, dtype=np.float32) for i in range(8)]
        # The independent scalar cosine oracle needs no model or feature extractor.
        expected = [float((1*i + 4*(8-i) + 2*i) / np.sqrt(21*(i*i+(8-i)**2+i*i))) for i in range(8)]
        actual = p.select_best_of_eight(target, candidates)
        np.testing.assert_allclose(actual.cosine_similarities, expected, rtol=2e-6, atol=2e-7)
        self.assertEqual(actual.index, int(np.argmax(expected)))

    def test_invalid_inputs_rejected_including_unselected_candidate(self):
        target = embed(1)
        valid = [target] * 8
        bad = target.copy(); bad.flat[-1] = np.nan
        cases = [(target, valid[:7]), (target, valid + [target]), (target, valid[:7] + [bad]),
                 (embed(0), valid), (target.astype(np.int32), valid), (np.ones((768,)), valid)]
        for reference, candidates in cases:
            with self.subTest(shape=reference.shape), self.assertRaises(p.SourceProtocolError):
                p.select_best_of_eight(reference, candidates)

    def test_single_index_applied_to_all_payloads_and_returns_copies(self):
        candidates = [embed(-1)] * 5 + [embed(1)] * 3
        selection = p.select_best_of_eight(embed(1), candidates)
        payloads = {'image': np.arange(24).reshape(8, 3), 'clip': np.arange(40).reshape(8, 5)}
        chosen = p.apply_selection(selection, payloads)
        self.assertEqual(selection.index, 5)
        np.testing.assert_array_equal(chosen['image'], [15, 16, 17])
        np.testing.assert_array_equal(chosen['clip'], [25, 26, 27, 28, 29])
        chosen['image'][0] = -1
        self.assertEqual(payloads['image'][5, 0], 15)

    def test_tampered_selection_and_incomplete_payload_rejected(self):
        for selection, payload in [(p.Selection(7, (1.,) * 8), {'image': np.ones((8, 3))}),
                                   (p.Selection(0, (1.,) * 8), {'image': np.ones((7, 3))})]:
            with self.assertRaises(p.SourceProtocolError):
                p.apply_selection(selection, payload)


if __name__ == '__main__':
    unittest.main(verbosity=2)
