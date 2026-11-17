"""Generated independent graph enumeration and boundary controls, no original data."""
import importlib.util
import itertools
import json
import math
from pathlib import Path
import random
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("motifs", Path(__file__).with_name("motifs.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def brute(n, labels):
    edges = dict(zip(itertools.combinations(range(n), 2), labels))
    result = {m.key(t): 0 for t in itertools.combinations_with_replacement((-1, 0, 1), 3)}
    for a, b, c in itertools.combinations(range(n), 3):
        result[m.key(tuple(sorted((edges[a,b], edges[a,c], edges[b,c]))))] += 1
    return result


def inputs():
    cases = [{"case_id": "g1", "animal_id": "generated_mouse", "session_id": "generated_session",
              "projection": "ACC", "outcome": "correct", "task_variable": "choice",
              "neuron_ids": ["a", "b", "c", "d"], "classification_provenance": "generated_only"}]
    manifest = {"schema": "npvc-motif-input-v1", "task_id": m.TASK, "cases": cases,
                "shuffle_ids": ["s0", "s1"], "two_pool_models": [{"model_id": "uniform", "n": 4, "p": 0.5, "delta1": 0, "delta2": 0}]}
    records = [{"case_id": "g1", "kind": "observed", "labels": [1, 1, 0, 1, 0, 1]},
               {"case_id": "g1", "kind": "shuffle", "shuffle_id": "s0", "permutation": list(range(6))},
               {"case_id": "g1", "kind": "shuffle", "shuffle_id": "s1", "permutation": list(reversed(range(6)))}]
    return manifest, records


class Controls(unittest.TestCase):
    def test_all_729_four_node_signed_graphs(self):
        for labels in itertools.product((-1, 0, 1), repeat=6):
            got = m.graph(4, list(labels))
            self.assertEqual(got["counts"], brute(4, labels))
            self.assertEqual(sum(got["counts"].values()), 4)

    def test_mixed_larger_graphs_and_relabeling(self):
        rng = random.Random(73)
        for n in range(5, 13):
            labels = [rng.choice((-1, 0, 1)) for _ in range(math.comb(n, 2))]
            got = m.graph(n, labels)
            self.assertEqual(got["counts"], brute(n, labels))
            edges = dict(zip(itertools.combinations(range(n), 2), labels))
            order = list(range(n)); rng.shuffle(order)
            permuted = [edges[tuple(sorted((order[i], order[j])))] for i,j in itertools.combinations(range(n),2)]
            self.assertEqual(got, m.graph(n, permuted))

    def test_published_clustering_not_standard_transitivity(self):
        # Triangle plus one tail: one closed and two open unordered triples.
        got = m.graph(4, [1, 1, 0, 1, 0, 1])["clustering"]["IE"]
        self.assertEqual((got["closed"], got["open"]), (1, 2))
        self.assertAlmostEqual(got["coefficient"], 1/3)
        self.assertNotEqual(got["coefficient"], 3/5)

    def test_independent_edges_remain_in_denominator_and_undefined_cc(self):
        got = m.graph(4, [0]*6)
        self.assertEqual(got["counts"]["0,0,0"], 4)
        self.assertEqual(got["independent_edge_triplets"], 4)
        for sign in ("IL", "IE"):
            self.assertIsNone(got["clustering"][sign]["coefficient"])
        self.assertEqual(sum(got["probabilities"].values()), 1)

    def test_fixed_count_null_against_all_unique_edge_permutations(self):
        labels = [-1, -1, 0, 0, 1, 1]
        permutations = set(itertools.permutations(labels))
        expected = m.graph(4, labels)["uniform_fixed_count_shuffle_expected_probabilities"]
        brute_means = {k: 0 for k in expected}
        for p in permutations:
            for k,v in brute(4, p).items():
                brute_means[k] += v / 4 / len(permutations)
        for k in expected:
            self.assertAlmostEqual(expected[k], brute_means[k], places=14)
        # Finite-edge inventory cannot produce +++ when there are only two +.
        self.assertEqual(expected["+,+,+"], 0)

    def test_two_pool_against_all_64_bernoulli_graphs(self):
        n, p, d1, d2 = 4, 0.5, 0.2, -0.1
        result = m.two_pool(n,p,d1,d2)
        edge_p = [result["p1"], result["between_pool_p"], result["between_pool_p"],
                  result["between_pool_p"], result["between_pool_p"], result["p2"]]
        expected = [0.0]*4
        for bits in itertools.product((0,1), repeat=6):
            probability = math.prod(v if b else 1-v for b,v in zip(bits,edge_p))
            labels = [1 if b else -1 for b in bits]
            counts = brute(4, labels)
            for k,name in enumerate(result["order"]):
                expected[k] += probability*counts[name]/4
        for a,b in zip(result["probabilities"],expected):
            self.assertAlmostEqual(a,b,places=14)
        self.assertAlmostEqual(sum(result["probabilities"]), 1)
        self.assertAlmostEqual((result["p1"]+result["p2"]+4*result["between_pool_p"])/6,p)

    def test_two_pool_boundary_uniform_and_exchange(self):
        for p in (0, 0.3, 1):
            result = m.two_pool(8,p,0,0)
            for v in result["relative_to_homogeneous_Bernoulli"]:
                self.assertAlmostEqual(v,0,places=14)
        for a,b in zip(m.two_pool(6,0.5,0.1,-0.2)["probabilities"],m.two_pool(6,0.5,-0.2,0.1)["probabilities"]):
            self.assertAlmostEqual(a,b,places=14)
        for args in ((5,.5,0,0),(4,.5,1,0),(4,float('nan'),0,0),(4,10**1000,0,0),(4,.9,-.9,-.9)):
            with self.assertRaises(m.Invalid):m.two_pool(*args)

    def test_complete_case_and_null_closure(self):
        manifest, rows = inputs()
        output = m.evaluate(manifest, rows)
        self.assertTrue(output["complete_relative_to_supplied_manifest"])
        self.assertFalse(output["authentic_population_verified"])
        self.assertIsNone(output["bootstrap_confidence_intervals"])
        self.assertIsNone(output["numerical_pass"])
        self.assertEqual(len(output["cases"][0]["shuffles"]),2)
        for broken in (rows[:-1],rows+[rows[0]],list(reversed(rows))):
            with self.assertRaises(m.Invalid):m.evaluate(manifest,broken)
        for perm in ([0]*6,[True,1,2,3,4,5],[0,1,2,3,4,6],list(range(5))):
            with self.assertRaises(m.Invalid):m.shuffled_labels(rows[0]["labels"],perm)

    def test_difference_and_undefined_null_not_omitted(self):
        manifest,rows = inputs()
        output = m.evaluate(manifest,rows)
        for s in output["cases"][0]["shuffles"]:
            a=output["cases"][0]["observed"]["clustering"]["IE"]["coefficient"]
            b=s["graph"]["clustering"]["IE"]["coefficient"]
            self.assertEqual(s["relative"]["clustering"]["IE"]["difference"],a-b)
        rows[0]["labels"]=[1,0,0,0,0,0]
        output=m.evaluate(manifest,rows)
        got=output["cases"][0]["mean_relative"]["clustering"]["IE"]
        self.assertIsNone(got["difference"])
        self.assertEqual(got["undefined_shuffles"],2)

    def test_json_full_io_and_fresh_destination(self):
        manifest,rows=inputs()
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);a=p/'manifest.json';b=p/'records.jsonl';o=p/'output.json'
            a.write_text(json.dumps(manifest));b.write_text(''.join(json.dumps(x)+'\n' for x in rows))
            m.run(a,b,o);got=json.loads(o.read_text())
            self.assertEqual(got["input_custody"]["records_bytes"],b.stat().st_size)
            with self.assertRaises(m.Invalid):m.run(a,b,o)
        for text in ('{"x":0,"x":1}', '{"x":NaN}'):
            with self.assertRaises(m.Invalid):m.decode(text)


if __name__ == '__main__':
    unittest.main(verbosity=2)
