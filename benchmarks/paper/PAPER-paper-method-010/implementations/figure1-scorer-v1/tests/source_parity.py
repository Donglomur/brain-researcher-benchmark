"""Differential generated controls against exact cached upstream source.

Usage: python source_parity.py /operator/cache/paper__metrics.py
Only four hash-authenticated pure metric functions are extracted by AST. No
scientific dependencies, data, fitting, generator or arbitrary module imports.
"""
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import numpy as np

PIN = "ca4f98ba2588111a3328393f7917eb91f8e45e12319acd22f308f86e01ee8673"
source = Path(sys.argv[1]).read_bytes()
if hashlib.sha256(source).hexdigest() != PIN:
    raise ValueError("expected exact pinned upstream paper/metrics.py")
selected = {"emb_to_idx", "triplet_order", "embedding_contamination", "benchmarks"}
functions = [node for node in ast.parse(source).body if isinstance(node, ast.FunctionDef) and node.name in selected]
if {node.name for node in functions} != selected:
    raise ValueError("source functions missing")
namespace = {"np": np}
exec(compile(ast.Module(body=functions, type_ignores=[]), "authenticated_metrics_functions", "exec"), namespace)
spec = importlib.util.spec_from_file_location("scorer", Path(__file__).resolve().parents[1] / "scorer.py")
scorer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scorer)

controls = []
truth = np.concatenate([k + np.linspace(.01, .99, n) for k, n in enumerate([12, 12, 12, 12, 24])])
fixtures = [truth, np.round(truth * 8) / 8]
# Keep rounded values inside their original half-open module intervals.
fixtures[1] = np.floor(truth) + np.minimum(np.round((truth % 1) * 8) / 8, .875)
# Exact shared boundaries retain source floor membership and its draw counts.
boundary_truth = truth.copy()
boundary_truth[[12, 24, 36]] = [2., 3., 4.]
fixtures.append(boundary_truth)
for fixture_id, gt in enumerate(fixtures):
    shuffle = np.random.RandomState(38).permutation(len(gt))
    gt = gt[shuffle]
    random_embedding = np.random.RandomState(59).rand(len(gt))
    embeddings = [gt[:, None], -gt, random_embedding, np.floor(random_embedding * 5)]
    for seed in (0, 74, 1029):
        np.random.seed(seed)
        reference = np.asarray(namespace["benchmarks"](gt, embeddings))
        expected_state = np.random.get_state()
        local_rng = np.random.RandomState(seed)
        actual, counts = scorer.source_benchmarks(gt, embeddings, local_rng)
        np.testing.assert_array_equal(actual, reference)
        actual_state = local_rng.get_state()
        np.testing.assert_array_equal(expected_state[1], actual_state[1])
        assert expected_state[0] == actual_state[0] and expected_state[2:] == actual_state[2:]
        assert (counts > 0).all()
        controls.append({"fixture": fixture_id, "seed": seed, "bitwise_score_equal": True, "final_rng_equal": True})
print(json.dumps({"source_sha256": PIN, "numpy": np.__version__, "controls": controls,
                  "qualification": "generated_metric_software_parity_only", "authentic_data_reads": 0,
                  "author_fits": 0}, indent=2))
