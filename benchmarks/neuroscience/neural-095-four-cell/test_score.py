"""Small invented full-panel controls; no original data or candidate code."""
from pathlib import Path
import copy
import json
import sys
import tempfile
sys.path.insert(0, str(Path(__file__).absolute().parent))
import numpy as np
import metrics
import score


def main():
    passed = []
    ids = ['dmfc-' + str(i).zfill(6) for i in range(258)]
    condition = np.arange(258, dtype=np.int64) % 40
    context = condition // 5
    truth = 1000.0 + np.arange(258) % 13
    private = {'case_id': np.array(ids, dtype='U11'), 'tp_ms': truth,
               'condition': condition, 'context': context}
    groups = {'by_condition': condition.tolist(), 'by_context': context.tolist()}
    reference = metrics._candidate((truth + 3).tolist(), truth.tolist(), groups)
    references = {'scores': {name: copy.deepcopy(reference) for name in metrics.METHODS}}
    with tempfile.TemporaryDirectory(prefix='dmfc-public-invented-') as directory:
        root = Path(directory).resolve(); submissions = {}
        for cell in score.CELLS:
            path = root / (cell + '.npz'); submissions[cell] = path
            offset = 2 if cell.endswith('cue_only') else 1
            # Shuffled complete IDs must align correctly.
            np.savez(path, case_id=np.array(ids[::-1], dtype='U11'), prediction_ms=(truth + offset)[::-1])
        calls = []
        def labels(): calls.append('targets'); return private
        def refs(): calls.append('references'); return references
        result = score.evaluate(submissions, ids, labels, refs)
        assert calls == ['references', 'targets'] and result['private_loader_calls'] == 1
        assert all(result['modes'][m]['paired']['cue_minus_neural_mae_ms'] == 1.0 for m in score.MODES)
        assert all(result['modes'][m]['paired_arithmetic_checks'] == 50 for m in score.MODES)
        assert result['matched_method_proven'] is False and result['producer_absence_verified'] is False
        passed.append('all four invented panels align and score with one private load and50 paired checks per mode')
        original_validate = score.validator.validate
        calls.clear()
        def substitute(path, expected):
            if path != submissions[score.CELLS[-1]]:
                return original_validate(path, expected)
            saved = path.with_suffix('.saved')
            path.rename(saved)
            try:
                np.savez(path, case_id=np.array(ids, dtype='U11'), prediction_ms=np.zeros(258))
                return original_validate(path, expected)
            finally:
                path.unlink(); saved.rename(path)
        score.validator.validate = substitute
        try:
            try: score.evaluate(submissions, ids, labels, refs)
            except ValueError: pass
            else: raise AssertionError('A to B to A substitution')
        finally:
            score.validator.validate = original_validate
        assert calls == []
        passed.append('A to B to A archive substitution cannot misbind vector to restored archive hash')
        for name, altered in [('duplicate', ids[:-1] + [ids[0]]), ('NaN', ids)]:
            calls.clear(); path = submissions[score.CELLS[-1]]
            values = truth.copy()
            if name == 'NaN': values[-1] = np.nan
            np.savez(path, case_id=np.array(altered, dtype='U11'), prediction_ms=values)
            try: score.evaluate(submissions, ids, labels, refs)
            except ValueError: pass
            else: raise AssertionError(name)
            assert calls == []
            passed.append('invalid last cell ' + name + ' prevents all reference and target access')
        calls.clear()
        try: score.evaluate(dict(list(submissions.items())[:-1]), ids, labels, refs)
        except ValueError: pass
        else: raise AssertionError('missing cell')
        assert calls == []; passed.append('missing mode/view fails before private access')
        for cell,path in submissions.items():
            np.savez(path, case_id=np.array(ids, dtype='U11'), prediction_ms=-np.ones(258))
        calls.clear(); result = score.evaluate(submissions, ids, labels, refs)
        assert result['modes']['frozen_program']['arms']['cue_only']['candidate']['mae_ms'] > 1000
        assert result['modes']['frozen_program']['paired']['cue_minus_neural_mae_ms'] == 0.0
        passed.append('negative finite values preserved and zero increment valid')
        bad = dict(private, case_id=np.array(ids[::-1], dtype='U11'))
        try: score.evaluate(submissions, ids, lambda: bad, refs)
        except ValueError: pass
        else: raise AssertionError('target ID substitution')
        passed.append('target identity/order substitution rejected')
        try: score.strict_json(b'{"x":1,"x":2}')
        except ValueError: passed.append('duplicate JSON metadata rejected')
        else: raise AssertionError('duplicate JSON')
    print(json.dumps({'status': 'invented_controls_passed', 'checks': passed,
                      'numpy_version': np.__version__, 'original_data_used': False}, indent=2))


if __name__ == '__main__':
    main()
