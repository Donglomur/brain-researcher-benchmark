"""Generated source-text controls; no author imports, tensors, or training."""
import ast
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

FILE = Path(__file__).resolve().parents[1] / "audit.py"
spec = importlib.util.spec_from_file_location("source_audit", FILE)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def cell(source):
    return {"cell_type": "code", "source": source}


def inputs():
    # These are small invented programs, not excerpts from the author files.
    notebook = {"cells": [
        {"cell_type": "markdown", "source": "Ignored even if it says trainer.train()"},
        cell("""%fake_magic never run
raise RuntimeError('source must never execute')
spikes = np.zeros((12, 3, 3 * 2 + 1))
for batch in real_dataloader.test_loader:
    unused = batch
acc_nneuron = [0, 3]
real_dataloader_fast = Simple_dataloader_from_spikes(
    [spikes], train_ratio=0.7, val_ratio=0.1, npadding=2, batch_size=4)
"""),
        cell("nrep = 5"),
        cell("""for i in range(5):
    trainer.train(include_coupling=False)
    test_loss = trainer.train(include_coupling=False, fix_latents=True)
    trainer.train(include_coupling=True)
    results[i] = test_loss
np.save('/not/opened/stale.npy', results)
"""),
        cell("""for i in range(5):
    trainer.train(include_coupling=False)
    test_loss = trainer.train(include_coupling=True)
    results[i] = test_loss
np.save('/not/opened/final.npy', results)
"""),
        cell("""def mean_sem(data):
    return data.mean(), data.std()/np.sqrt(len(data))
""")
    ]}
    loader = """raise RuntimeError('no imports')
class Simple_dataloader_from_spikes:
    def __init__(self):
        utils.set_seed(1)
        split1, split2 = int(train_ratio*self.ntrial), int((train_ratio+val_ratio)*self.ntrial)
        self.session_ids = ['0']
"""
    trainer = """raise RuntimeError('no imports')
class Trainer:
    def train(self, include_coupling=True):
        for batch in self.dataloader.train_loader:
            loss += self.get_penalty()
        for batch in self.dataloader.val_loader:
            loss += self.get_penalty()
        return best_test_loss
"""
    model = """raise RuntimeError('no imports')
def loss_function(y, eta):
    return (eta.exp() - y * eta).mean()
"""
    return notebook, loader, trainer, model


class SourceInspectionTests(unittest.TestCase):
    def test_no_execution_and_independent_count_oracle(self):
        result = audit.inspect_sources(*inputs())
        packed = result['packed_allen_route']
        self.assertEqual(packed['allocated_time_neuron_trial_shape'], [12, 3, 7])
        self.assertEqual(packed['derived_split_sizes_if_all_allocated_rows_are_valid'],
                         {'train': 4, 'validation': 1, 'test': 2})
        self.assertEqual(packed['post_padding_time_bins'], 10)
        self.assertEqual(packed['input_iterables'], ['real_dataloader.test_loader'])

    def test_stale_score_and_keyword_mismatch_have_exact_locations(self):
        rows = audit.inspect_sources(*inputs())['ablation_stages']
        self.assertEqual(rows[0]['result_basename'], 'stale.npy')
        self.assertEqual(rows[0]['saved_training_call_one_based'], 2)
        self.assertEqual(rows[0]['later_training_calls_before_save'], 1)
        self.assertEqual(rows[0]['train_calls'][1]['unsupported_keywords'], ['fix_latents'])
        self.assertEqual(rows[1]['saved_training_call_one_based'], 2)
        self.assertEqual(rows[1]['later_training_calls_before_save'], 0)

    def test_trial_order_is_not_invented(self):
        result = audit.inspect_sources(*inputs())
        self.assertEqual(result['trainer']['returns'], ['best_test_loss'])
        self.assertEqual(result['replicate_setting']['nrep'], 5)
        self.assertNotIn('trial_ids', json.dumps(result))
        self.assertEqual(result['packed_allen_route']['loader_seed_calls'], ['utils.set_seed(1)'])

    def test_changed_split_rule_rejects_unsupported_derived_counts(self):
        args = list(inputs())
        args[1] = args[1].replace('int((train_ratio+val_ratio)*self.ntrial)',
                                 'int(train_ratio*self.ntrial)+int(val_ratio*self.ntrial)')
        with self.assertRaisesRegex(audit.AuditError, 'arithmetic changed'):
            audit.inspect_sources(*args)

    def test_shape_calls_and_unbounded_arithmetic_never_execute(self):
        for expression in ("__import__('os').system('false')", "9 ** 9", "1000000000 * 2"):
            with self.subTest(expression=expression), self.assertRaises(audit.AuditError):
                audit.numeric(ast.parse(expression, mode='eval').body)

    def test_ambiguous_packing_and_dynamic_shape_reject(self):
        args = list(inputs())
        args[0]['cells'].append(args[0]['cells'][1])
        with self.assertRaisesRegex(audit.AuditError, 'packed Allen data cell'):
            audit.inspect_sources(*args)
        args = list(inputs())
        args[0]['cells'][1]['source'] = args[0]['cells'][1]['source'].replace('3 * 2 + 1', 'trial_count')
        with self.assertRaisesRegex(audit.AuditError, 'numeric source expression'):
            audit.inspect_sources(*args)

    def test_digest_binding_precedes_source_parsing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'Reproduce_figures').mkdir()
            (root / audit.SOURCE_FILES[0]).write_text('not valid JSON')
            pins = root / 'pins.json'
            pins.write_text(json.dumps({'source_commit': audit.SOURCE_COMMIT,
                                        'files': {audit.SOURCE_FILES[0]: '0' * 64}}))
            with self.assertRaisesRegex(audit.AuditError, 'digest mismatch'):
                audit.audit_directory(root, pins)

    def test_documentary_labels_preserved_without_fabricated_outputs(self):
        text = f'# Original commit {audit.SOURCE_COMMIT}; example\n# Original code cell 7\nx = 1\n# Original code cell 19\ny = 2\n'
        notebook = audit.documentary_notebook(text)
        self.assertEqual([c['source_cell_label'] for c in notebook['cells']],
                         ['cached-cell:7', 'cached-cell:19'])
        self.assertTrue(all('outputs' not in c for c in notebook['cells']))
        with self.assertRaisesRegex(audit.AuditError, 'duplicate'):
            audit.documentary_notebook(text + '# Original code cell 7\nz = 3\n')

    def test_saved_output_is_only_a_printed_historical_value(self):
        output = {'outputs':[{'text':['Data 3\t0.25000 (0.01000)\t0.3 (0.02)\t0.4 (0.03)\t0.5 (0.04)\t0.6 (0.05)\n']}]}
        result = audit.displayed_summary(output)
        self.assertEqual(result['role'], 'historical_notebook_output_not_fresh_execution')
        self.assertEqual(result['rows'][0]['values']['full_model'],
                         {'printed_mean':'0.25000','printed_parenthesized_value':'0.01000'})
        output['outputs'][0]['text'] *= 2
        with self.assertRaisesRegex(audit.AuditError, 'duplicate'):
            audit.displayed_summary(output)


if __name__ == '__main__':
    unittest.main()
