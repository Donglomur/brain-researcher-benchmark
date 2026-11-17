"""Exact seven-symbol source reward score; no model or panel qualification.

Derived from OSM_Paper_Figures c1d1788, Vanilla_RNN_Sigmoid cell 0.
The source names this accuracy but computes recall at next-symbol reward
positions. False positives do not change its value. See README.md.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


NEAR_TRIAL = (1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 1, 1, 1, 4, 6, 1, 1, 1, 5, 5, 1, 1, 0)
FAR_TRIAL = (1, 1, 1, 1, 1, 1, 3, 3, 3, 3, 1, 1, 1, 4, 4, 1, 1, 1, 5, 6, 1, 1, 0)
TRIAL_LENGTH = 23
REWARD_SYMBOL = 6
SYMBOL_COUNT = 7


def score_reward_predictions(test_symbols: list[int], logits: list[list[float]]) -> dict:
    """Score source-shaped predictions on complete original 23-symbol trials.

    Logit row t predicts test_symbols[t+1]. Source inference supplies one row
    for every input, including the last input without a known next target.
    The final prediction cannot match any eligible reward position. This
    function retains that row and reports its exclusion explicitly.

    Trial count, model state, model fitting and simulation census are the
    caller's obligations. This arithmetic kernel does not validate them.
    """
    if not isinstance(test_symbols, list) or not test_symbols:
        raise ValueError('test_symbols must be a nonempty list')
    if any(type(symbol) is not int or not 0 <= symbol < SYMBOL_COUNT for symbol in test_symbols):
        raise ValueError('original task symbols must be integers 0 through 6')
    if len(test_symbols) % TRIAL_LENGTH:
        raise ValueError('test_symbols must contain complete 23-symbol trials')
    kinds = []
    for start in range(0, len(test_symbols), TRIAL_LENGTH):
        trial = tuple(test_symbols[start:start + TRIAL_LENGTH])
        if trial not in (NEAR_TRIAL, FAR_TRIAL):
            raise ValueError('trial does not match original seven-symbol 2ACDC encoding')
        kinds.append('near' if trial == NEAR_TRIAL else 'far')
    if not isinstance(logits, list) or len(logits) != len(test_symbols):
        raise ValueError('source inference requires one logit row per input symbol')
    predictions = []
    for row in logits:
        if (not isinstance(row, list) or len(row) != SYMBOL_COUNT
                or any(type(value) not in (int, float)
                       or (type(value) is float and not math.isfinite(value)) for value in row)):
            raise ValueError('each logit row must contain seven finite numbers')
        # Python's max returns the first maximum, matching source argmax.
        predictions.append(max(range(SYMBOL_COUNT), key=row.__getitem__))

    targets = test_symbols[1:]
    actual_reward = {i for i, symbol in enumerate(targets) if symbol == REWARD_SYMBOL}
    predicted_reward = {i for i, symbol in enumerate(predictions) if symbol == REWARD_SYMBOL}
    hits = len(actual_reward & predicted_reward)
    eligible_predictions = predictions[:-1]
    false_positives = sum(p == REWARD_SYMBOL and y != REWARD_SYMBOL
                          for p, y in zip(eligible_predictions, targets))
    # Complete literal source trials contain one reward each, so nonzero.
    return {
        'metric': 'source_reward_recall_named_accuracy',
        'correct_reward_predictions': hits,
        'eligible_reward_positions': len(actual_reward),
        'source_score': hits / len(actual_reward),
        'trial_count': len(kinds),
        'near_trial_count': kinds.count('near'),
        'far_trial_count': kinds.count('far'),
        'diagnostics_not_source_endpoint': {
            'false_reward_predictions': false_positives,
            'nonreward_target_positions': len(targets) - len(actual_reward),
            'next_symbol_correct': sum(p == y for p, y in zip(eligible_predictions, targets)),
            'next_symbol_positions': len(targets),
            'ignored_terminal_prediction': predictions[-1],
        },
    }


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key: ' + key)
        result[key] = value
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path, help='JSON with test_symbols and logits')
    parser.add_argument('output', type=Path, help='new JSON report; never overwritten')
    args = parser.parse_args()
    payload = json.loads(args.input.read_text(), object_pairs_hook=_unique_object,
                         parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    if not isinstance(payload, dict) or set(payload) != {'test_symbols', 'logits'}:
        raise ValueError('input must contain exactly test_symbols and logits')
    result = score_reward_predictions(payload['test_symbols'], payload['logits'])
    with args.output.open('x') as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
        handle.write('\n')


if __name__ == '__main__':
    main()
