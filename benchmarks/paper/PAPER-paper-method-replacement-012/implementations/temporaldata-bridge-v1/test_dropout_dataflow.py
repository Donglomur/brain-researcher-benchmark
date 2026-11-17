"""Generated source-dataflow witness only; no real torch/model/temporaldata.

Exact author UnitDropout and tokenize AST bodies are exercised with independent
NumPy arrays, forced RNG witnesses and explicit Tensor/rearrange/chain doubles.
This proves generated-object data flow, not real runtime semantics or a gain.
"""
from __future__ import annotations

import ast
from copy import deepcopy
import hashlib
from pathlib import Path
from types import SimpleNamespace
from typing import cast
import unittest
from unittest.mock import patch

import numpy as np

HERE = Path(__file__).resolve().parent
PINS = {'unit_dropout.py': 'c9b04c012fe53944b11e0aa9e3b1688ac71920827ad1b1de5e871ac889687e88',
        'nuclr_v2ga_ca2.py': '3b26a22d9ab4c08857a28c2bdf9b6c2d108b272a5c2dc3f025c7ab2fad27918d'}


class TensorDouble:
    def __init__(self, values):
        self.values = np.asarray(values)
    def to(self, dtype):
        return TensorDouble(self.values.astype(dtype))
    @property
    def T(self):
        return TensorDouble(self.values.T)
    def size(self, axis):
        return self.values.shape[axis]
    def __getitem__(self, key):
        return TensorDouble(self.values[key])


class UnitsDouble(SimpleNamespace):
    def __len__(self):
        return len(self.id)


def pinned_ast(filename):
    path = HERE / 'reference' / filename
    body = path.read_bytes()
    if hashlib.sha256(body).hexdigest() != PINS[filename]:
        raise AssertionError('source mechanism witness file differs')
    return ast.parse(body), str(path)


def source_functions():
    tree, filename = pinned_ast('unit_dropout.py')
    classes = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'UnitDropout']
    if len(classes) != 1:
        raise AssertionError('unique original transform class required')
    namespace = {'np': np, 'cast': cast, 'CalciumData': SimpleNamespace,
                 'SpikeData': SimpleNamespace, 'Data': SimpleNamespace,
                 'apply_unit_mask_': lambda *a: (_ for _ in ()).throw(AssertionError('spike path not permitted'))}
    future = ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0)
    code = ast.fix_missing_locations(ast.Module(body=[future, *classes], type_ignores=[]))
    exec(compile(code, filename, 'exec'), namespace)

    tree, filename = pinned_ast('nuclr_v2ga_ca2.py')
    models = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'NuclrV2gaCa2']
    if len(models) != 1:
        raise AssertionError('unique original calcium model class required')
    methods = [node for node in models[0].body if isinstance(node, ast.FunctionDef) and node.name == 'tokenize']
    if len(methods) != 1:
        raise AssertionError('unique original tokenize method required')
    def rearrange(values, expression, *, L, P):
        if expression != 'U (L P) -> (U L) P':
            raise AssertionError('unreviewed generated rearrange expression')
        array = values.values
        if array.ndim != 2 or array.shape[1] != L * P:
            raise AssertionError('generated patch geometry differs')
        return TensorDouble(array.reshape(array.shape[0] * L, P))
    namespace.update(torch=SimpleNamespace(from_numpy=TensorDouble, float32=np.float32),
                     rearrange=rearrange, chain=lambda tensor: np.array(tensor.values, copy=True),
                     ViewData=lambda **kwargs: SimpleNamespace(**kwargs))
    code = ast.fix_missing_locations(ast.Module(body=[future, *methods], type_ignores=[]))
    exec(compile(code, filename, 'exec'), namespace)
    return namespace['UnitDropout'], namespace['tokenize']


def view_fixture():
    raw = np.arange(40, dtype=np.float32).reshape(10, 4) + 3
    normalized = raw / np.float32(17.0)
    return SimpleNamespace(units=UnitsDouble(id=np.array(['u0', 'u1', 'u2', 'u3'])),
                           calcium_traces=SimpleNamespace(df_over_f=raw.copy(), df_over_f_norm=normalized.copy()),
                           session=SimpleNamespace(id='generated-session'))


class DropoutSourceDataflowControls(unittest.TestCase):
    def test_forced_source_dropout_changes_only_raw_and_consumes_rng(self):
        Dropout, tokenize = source_functions()
        data = view_fixture()
        original_raw = data.calcium_traces.df_over_f.copy()
        original_norm = data.calcium_traces.df_over_f_norm
        original_units = data.units
        model = SimpleNamespace(num_latents=2, patch_size=4)
        before = tokenize(model, data)
        with patch.object(np.random, 'randint', return_value=2) as randint, \
             patch.object(np.random, 'permutation', return_value=np.array([2, 0, 3, 1])) as permutation:
            changed = Dropout(min_units=2)(data)
        randint.assert_called_once_with(2, 5)
        permutation.assert_called_once_with(4)
        self.assertIs(changed, data)
        np.testing.assert_array_equal(data.calcium_traces.df_over_f, original_raw[:, [0, 2]])
        self.assertIs(data.calcium_traces.df_over_f_norm, original_norm)
        self.assertIs(data.units, original_units)
        self.assertFalse(np.shares_memory(data.calcium_traces.df_over_f, original_norm))
        after = tokenize(model, data)
        self.assertEqual(after.data['enc_input']['unit_seqlen'], 4)
        self.assertEqual(after.data['enc_input']['bins'].shape, (8, 4))
        self.assertEqual(after.data['enc_input']['bins'].dtype, np.dtype('float32'))
        np.testing.assert_array_equal(before.data['enc_input']['bins'], after.data['enc_input']['bins'])
        np.testing.assert_array_equal(before.unit_ids, after.unit_ids)
        np.testing.assert_array_equal(before.recording_ids, after.recording_ids)

    def test_generated_tokenizer_witness_detects_normalized_input_change(self):
        _, tokenize = source_functions()
        original = view_fixture()
        changed = deepcopy(original)
        changed.calcium_traces.df_over_f_norm[0, 0] += np.float32(11)
        model = SimpleNamespace(num_latents=2, patch_size=4)
        before = tokenize(model, original)
        after = tokenize(model, changed)
        np.testing.assert_array_equal(original.calcium_traces.df_over_f, changed.calcium_traces.df_over_f)
        self.assertFalse(np.array_equal(before.data['enc_input']['bins'], after.data['enc_input']['bins']))
        self.assertEqual(float(after.data['enc_input']['bins'][0, 0] - before.data['enc_input']['bins'][0, 0]), 11.0)
        np.testing.assert_array_equal(before.unit_ids, after.unit_ids)


if __name__ == '__main__':
    unittest.main(verbosity=2)
