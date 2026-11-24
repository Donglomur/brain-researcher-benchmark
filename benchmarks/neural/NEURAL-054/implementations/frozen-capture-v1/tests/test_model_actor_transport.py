"""Generated D/R transport controls. No weights, native library, fit or data run.

Exercise the actual actor main() with explicit tokenizer/model stubs. These
controls establish message delivery and response handling, never model ability.
"""
import argparse
from contextlib import nullcontext
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


parser = argparse.ArgumentParser(add_help=False)
parser.add_argument('--actor', type=Path)
parser.add_argument('--scratch', type=Path)
options, remaining = parser.parse_known_args()
sys.argv = [sys.argv[0], *remaining]
actor_path = options.actor or (Path(__file__).resolve().parents[1] /
                              'package/programme/n054/model_actor.py')
spec = importlib.util.spec_from_file_location('n054_transport_actor', actor_path)
actor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(actor)


class ModelActorTransportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=options.scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.out = self.root / 'output'
        self.out.mkdir()
        self.labels = ['generated-label-' + str(i) for i in range(27)]
        classes = [[{'count': 3, 'mean': [str(j)] * 8, 'variance': ['1'] * 8},
                    {'count': 4, 'mean': [str(j + 1)] * 8, 'variance': ['2'] * 8}]
                   for j in range(27)]
        self.payload = {'classes': classes, 'query': ['0.5'] * 8}
        self.request = {'phase': 'diagnose', 'tools': [], 'query_id': 'opaque-generated-query',
                        'context': {'labels': self.labels, 'window': 'EARLY', 'arm': 'JOINT',
                                    'profile': 'D_PCA8_SUMMARY_V1', 'episode': 'opaque-generated-episode',
                                    'mode': 'D', 'tool': 'NONE', 'replicate': 0,
                                    'generation': 'generated-control-only'},
                        'payload': self.payload}
        self.policy = {'identity': 'generated-model-stub-only', 'seed': 0,
                       'local_model_path': 'never-opened-model-stub',
                       'D_instruction': 'Return the ordered probabilities.',
                       'R_instruction': 'Interpret the frozen report.',
                       'max_new_tokens': 20, 'qualified_context_tokens': 32}
        self.answer = json.dumps({'status': 'complete', 'probabilities': [0.5] * 27})
        self.observed = {}

    def invoke(self):
        request_path = self.root / 'request.json'
        request_path.write_text(json.dumps(self.request))
        (self.root / 'policy.json').write_text(json.dumps(self.policy))
        observed = self.observed

        class Tokenizer:
            def __call__(this, text, **kwargs):
                observed['text'] = text
                observed['tokenizer_arguments'] = kwargs
                return {'input_ids': SimpleNamespace(shape=(1, 11)), 'attention_mask': 'stub'}

            def decode(this, generated, **kwargs):
                observed['decode_arguments'] = kwargs
                return self.answer

        class Response:
            def __getitem__(this, key):
                observed['response_slice'] = (key[0], key[1].start)
                return [1, 2, 3]

        class Model:
            def eval(this):
                observed['eval'] = True

            def generate(this, **kwargs):
                observed['generate_arguments'] = kwargs
                return Response()

        def tokenizer_load(path, **kwargs):
            observed['tokenizer_load'] = (path, kwargs)
            return Tokenizer()

        def model_load(path, **kwargs):
            observed['model_load'] = (path, kwargs)
            return Model()

        stubs = {'torch': SimpleNamespace(manual_seed=lambda seed: observed.update(seed=seed),
                                         inference_mode=nullcontext),
                 'transformers': SimpleNamespace(
                     AutoTokenizer=SimpleNamespace(from_pretrained=tokenizer_load),
                     AutoModelForCausalLM=SimpleNamespace(from_pretrained=model_load))}
        argv = ['model_actor.py', '--request', str(request_path), '--output', str(self.out)]
        with patch.object(actor, '__file__', str(self.root / 'model_actor.py')), \
             patch.object(sys, 'argv', argv), patch.dict(sys.modules, stubs):
            actor.main()

    def result(self):
        return json.loads((self.out / 'result.json').read_text())

    def test_direct_model_receives_semantics_and_identical_numeric_payload(self):
        self.invoke()
        instruction, serialized = self.observed['text'].split('\n', 1)
        value = json.loads(serialized)
        self.assertEqual(instruction, self.policy['D_instruction'])
        self.assertEqual(value, {'label_order': self.labels, 'window': 'EARLY', 'arm': 'JOINT',
                                 'information_profile': 'D_PCA8_SUMMARY_V1', 'payload': self.payload})
        # No opaque identifiers or provenance metadata become extra model cues.
        self.assertNotIn('query_id', value)
        self.assertNotIn('episode', value)
        self.assertEqual(self.result(), {'status': 'complete', 'probabilities': [0.5] * 27})

    def test_label_permutation_reaches_model_without_reordering_summary_rows(self):
        self.request['context']['labels'] = list(reversed(self.labels))
        self.invoke()
        value = json.loads(self.observed['text'].split('\n', 1)[1])
        self.assertEqual(value['label_order'], list(reversed(self.labels)))
        self.assertEqual(value['payload'], self.payload)

    def test_abstention_preserves_no_numeric_output_and_original_usage(self):
        self.answer = '{"status":"abstain"}'
        self.invoke()
        self.assertEqual(self.result(), {'status': 'abstain'})
        usage = json.loads((self.out / 'usage.json').read_text())
        self.assertEqual((usage['model_calls'], usage['input_tokens'], usage['output_tokens']), (1, 11, 3))
        self.assertEqual(usage['model_identity'], self.policy['identity'])

    def test_invalid_complete_or_abstention_responses_cannot_be_written(self):
        invalid = [[], {'status': 'abstain', 'probabilities': [0.5] * 27},
                   {'status': 'complete', 'probabilities': [0.5] * 26}]
        invalid += [{'status': 'complete', 'probabilities': [value] + [0.5] * 26}
                    for value in (True, '0.5', -0.1, 1.1, float('nan'), float('inf'))]
        for response in invalid:
            with self.subTest(response=response):
                self.answer = json.dumps(response)
                with self.assertRaises(ValueError):
                    self.invoke()
                self.assertFalse((self.out / 'result.json').exists())

    def test_context_budget_counts_full_prompt_and_never_truncates(self):
        self.policy['qualified_context_tokens'] = 30
        with self.assertRaisesRegex(ValueError, 'no truncation'):
            self.invoke()
        self.assertEqual(self.observed['tokenizer_arguments'], {'return_tensors': 'pt', 'truncation': False})
        self.assertNotIn('generate_arguments', self.observed)
        self.assertFalse((self.out / 'result.json').exists())

    def test_report_transport_is_unchanged(self):
        report = {'status': 'COMPLETE_UNQUALIFIED', 'points': {'generated-effect': 0}}
        self.request = {'phase': 'interpret', 'tools': [], 'report': report}
        self.answer = '{"status":"interpreted","claims":[]}'
        self.invoke()
        self.assertEqual(self.observed['text'], self.policy['R_instruction'] + '\n' +
                         json.dumps(report, sort_keys=True, separators=(',', ':')))
        self.assertEqual(self.result(), {'status': 'interpreted', 'claims': []})

    def test_tools_rejected_before_model_load(self):
        self.request['tools'] = ['forbidden']
        with self.assertRaisesRegex(ValueError, 'No tools permitted'):
            self.invoke()
        self.assertNotIn('model_load', self.observed)

    def test_offline_model_identity_and_generation_settings_preserved(self):
        self.invoke()
        expected = (self.policy['local_model_path'], {'local_files_only': True, 'trust_remote_code': False})
        self.assertEqual(self.observed['model_load'], expected)
        self.assertEqual(self.observed['tokenizer_load'], expected)
        self.assertEqual(self.observed['generate_arguments']['max_new_tokens'], 20)
        self.assertIs(self.observed['generate_arguments']['do_sample'], False)
        self.assertEqual(self.observed['response_slice'], (0, 11))


if __name__ == '__main__':
    unittest.main(verbosity=2)
