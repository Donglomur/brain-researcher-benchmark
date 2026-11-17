import importlib.util
import math
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('reward_score', ROOT / 'reward_score.py')
scorer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scorer)


def logits(tokens):
    return [[1.0 if i == token else 0.0 for i in range(7)] for token in tokens]


class SourceArithmeticTests(unittest.TestCase):
    def setUp(self):
        self.symbols = list(scorer.NEAR_TRIAL + scorer.FAR_TRIAL)

    def test_literal_reward_prediction_indices_and_shift(self):
        # Near reward is symbol 14; far reward is symbol 23+19. Predict at
        # preceding input positions 13 and 41, not at reward-input positions.
        prediction = [0] * 46
        prediction[13] = prediction[41] = 6
        result = scorer.score_reward_predictions(self.symbols, logits(prediction))
        self.assertEqual((result['correct_reward_predictions'], result['eligible_reward_positions']), (2, 2))
        prediction[13], prediction[14] = 0, 6
        self.assertEqual(scorer.score_reward_predictions(self.symbols, logits(prediction))['source_score'], 0.5)

    def test_constant_reward_reaches_source_ceiling(self):
        result = scorer.score_reward_predictions(self.symbols, logits([6] * 46))
        self.assertEqual(result['source_score'], 1)
        self.assertEqual(result['diagnostics_not_source_endpoint']['false_reward_predictions'], 43)
        self.assertEqual(result['diagnostics_not_source_endpoint']['next_symbol_correct'], 2)
        self.assertEqual(result['diagnostics_not_source_endpoint']['next_symbol_positions'], 45)

    def test_terminal_row_is_retained_but_has_no_target(self):
        prediction = self.symbols[1:] + [0]
        first = scorer.score_reward_predictions(self.symbols, logits(prediction))
        prediction[-1] = 6
        second = scorer.score_reward_predictions(self.symbols, logits(prediction))
        self.assertEqual(first['source_score'], second['source_score'])
        self.assertEqual(second['diagnostics_not_source_endpoint']['false_reward_predictions'], 0)
        self.assertEqual(second['diagnostics_not_source_endpoint']['ignored_terminal_prediction'], 6)

    def test_first_argmax_tie_wins(self):
        values = logits([6] * 46)
        values[13][0] = 1
        result = scorer.score_reward_predictions(self.symbols, values)
        self.assertEqual(result['source_score'], 0.5)

    def test_mixed_trial_counts_not_token_pooled_panel(self):
        symbols = list(scorer.NEAR_TRIAL * 3 + scorer.FAR_TRIAL)
        result = scorer.score_reward_predictions(symbols, logits([6] * len(symbols)))
        self.assertEqual((result['trial_count'], result['near_trial_count'], result['far_trial_count']), (4, 3, 1))
        self.assertEqual(result['eligible_reward_positions'], 4)

    def test_original_encoding_rejects_position_unique_and_corrupted_trials(self):
        for symbols in (list(range(23)), self.symbols[:-1], [True] + self.symbols[1:],
                        self.symbols[:14] + [4] + self.symbols[15:]):
            with self.subTest(symbols=symbols[:3]):
                with self.assertRaises(ValueError):
                    scorer.score_reward_predictions(symbols, logits([6] * len(symbols)))

    def test_rejects_nonfinite_or_missing_prediction_rows(self):
        for bad in (logits([6] * 45), [[0.0] * 6] * 46,
                    [[0.0] * 6 + [math.nan]] * 46, [[0.0] * 6 + [True]] * 46):
            with self.assertRaises(ValueError):
                scorer.score_reward_predictions(self.symbols, bad)


if __name__ == '__main__':
    unittest.main()
