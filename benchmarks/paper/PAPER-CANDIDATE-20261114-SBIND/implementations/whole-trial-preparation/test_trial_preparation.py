"""Generated full-count indexing controls; no images, upstream modules or models."""
import copy
from collections.abc import Sequence
import hashlib
import json
import unittest
import trial_preparation as subject


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def fixture():
    census = {"schema": "sbind-complete-widefield-census-v1", "task_id": subject.TASK, "assays": []}
    split = {"schema": "sbind-prospective-whole-trial-folds-v1", "task_id": subject.TASK, "assays": []}
    for name, count in subject.COUNTS.items():
        trials = []; cursor = 0
        for i in range(count):
            length = 1 + i % 7
            trials.append({"trial_id": "invented-%s-%03d" % (name, i), "source_start": cursor, "length": length})
            cursor += length
        census["assays"].append({"assay_id": name, "source_sha256": "1" * 64,
                                 "representation_sha256": "2" * 64, "neural_shape": [1, 128, 128],
                                 "behavior_channels": ["invented-channel-a", "invented-channel-b"], "trials": trials})
        folds = []
        for fold in range(5):
            row = {"fold": fold, "train": [], "validation": [], "test": []}
            for i, trial in enumerate(trials):
                role = "test" if i % 5 == fold else "validation" if i % 5 == (fold + 1) % 5 else "train"
                row[role].append(trial["trial_id"])
            folds.append(row)
        split["assays"].append({"assay_id": name, "folds": folds})
    return census, split


def bind(census, split):
    c = encode(census); split = copy.deepcopy(split)
    split["census_sha256"] = hashlib.sha256(c).hexdigest()
    s = encode(split)
    return c, s, {"census_sha256": hashlib.sha256(c).hexdigest(), "split_sha256": hashlib.sha256(s).hexdigest()}


class InventedRows(Sequence):
    def __init__(self, length):
        self.length = length
        self.reads = []
    def __len__(self):
        return self.length
    def __getitem__(self, index):
        if not 0 <= index < self.length:
            raise IndexError(index)
        self.reads.append(index)
        return (("invented-neural-sentinel", index), ("invented-behavior-sentinel", index))


class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.census, self.split = fixture()
        self.calls = []; self.sources = []
    def loader(self, assay):
        self.calls.append(assay.assay_id)
        rows = InventedRows(assay.total_frames); self.sources.append(rows)
        return subject.SourceRows(assay.source_sha256, assay.representation_sha256,
                                  subject.SHAPE, assay.channels, rows)
    def prepare(self, name="WFCI1", fold=0):
        c, s, pins = bind(self.census, self.split)
        return subject.prepare_fold(c, s, **pins, assay_id=name, fold=fold, source_loader=self.loader)
    def refuse(self):
        with self.assertRaises(subject.AdmissionError): self.prepare()
        self.assertEqual(self.calls, [])

    def test_all_660_trials_all_folds_preserve_order_support_values_and_resets(self):
        for declared in self.census["assays"]:
            name = declared["assay_id"]; all_ids = {t["trial_id"] for t in declared["trials"]}
            held = []
            for fold in range(5):
                views = self.prepare(name, fold)
                self.assertEqual(self.sources[-1].reads, [])
                partition = []
                for role, view in views.items():
                    frames = list(view); ids = {x.trial_id for x in frames}
                    partition.append(ids)
                    if role == "test": held.extend(ids)
                    expected = [t for t in declared["trials"] if t["trial_id"] in ids]
                    source_indices = [i for t in expected for i in range(t["source_start"], t["source_start"] + t["length"])]
                    self.assertEqual([x.source_index for x in frames], source_indices)
                    self.assertEqual([x.neural[1] for x in frames], source_indices)
                    self.assertEqual([x.behavior[1] for x in frames], source_indices)
                    self.assertEqual(list(view.reset_mask()), [int(not x.reset) for x in frames])
                    self.assertEqual(sum(x.reset for x in frames), len(ids))
                    self.assertEqual([x.trial_offset for x in frames], [i for t in expected for i in range(t["length"])])
                self.assertEqual(set.union(*partition), all_ids)
                self.assertTrue(all(not partition[i] & partition[j] for i in range(3) for j in range(i)))
            self.assertCountEqual(held, all_ids)
        self.assertEqual(len(self.calls), 10)

    def test_role_listing_order_does_not_reorder_time(self):
        before = self.prepare()
        for a in self.split["assays"]:
            for f in a["folds"]:
                for role in ("train", "validation", "test"): f[role].reverse()
        after = self.prepare()
        for role in before:
            self.assertEqual([x.source_index for x in before[role]], [x.source_index for x in after[role]])

    def test_missing_duplicate_unknown_overlapping_or_empty_trials_refuse_before_loader(self):
        original = copy.deepcopy(self.split)
        changes = [lambda f: f["train"].pop(), lambda f: f["train"].append(f["train"][0]),
                   lambda f: f["train"].append("unknown"), lambda f: f["validation"].append(f["train"][0]),
                   lambda f: f.update(validation=[])]
        for change in changes:
            self.split = copy.deepcopy(original); change(self.split["assays"][0]["folds"][0]); self.refuse()

    def test_bad_lengths_census_support_and_source_gaps_refuse(self):
        original = copy.deepcopy(self.census)
        for length in (0, -1, True, 1.0):
            self.census = copy.deepcopy(original); self.census["assays"][0]["trials"][0]["length"] = length; self.refuse()
        self.census = copy.deepcopy(original); self.census["assays"][1]["trials"].pop(); self.refuse()
        self.census = copy.deepcopy(original); self.census["assays"][0]["trials"][1]["source_start"] += 1; self.refuse()
        self.census = copy.deepcopy(original); self.census["assays"][0]["trials"][1]["trial_id"] = self.census["assays"][0]["trials"][0]["trial_id"]; self.refuse()

    def test_full_fold_grid_and_once_test_coverage_required(self):
        self.split["assays"][1]["folds"].pop(); self.refuse()
        self.census, self.split = fixture()
        self.split["assays"][0]["folds"][1] = copy.deepcopy(self.split["assays"][0]["folds"][0])
        self.split["assays"][0]["folds"][1]["fold"] = 1
        self.refuse()

    def test_hash_cross_binding_and_duplicate_json_rejected_before_loader(self):
        c, s, pins = bind(self.census, self.split)
        for raw_c, raw_s, expected in [(c+b" ", s, pins), (c, s+b" ", pins)]:
            with self.assertRaises(subject.AdmissionError):
                subject.prepare_fold(raw_c, raw_s, **expected, assay_id="WFCI1", fold=0, source_loader=self.loader)
        j = json.loads(s); j["census_sha256"] = "0"*64; bad = encode(j)
        with self.assertRaises(subject.AdmissionError): subject.compile_protocol(c, bad, census_sha256=pins["census_sha256"], split_sha256=hashlib.sha256(bad).hexdigest())
        raw = b'{"schema":1,"schema":2}'
        with self.assertRaises(subject.AdmissionError): subject.compile_protocol(raw, s, census_sha256=hashlib.sha256(raw).hexdigest(), split_sha256=pins["split_sha256"])
        self.assertEqual(self.calls, [])

    def test_loaded_extent_and_identity_refused_before_any_frame_read(self):
        c, s, pins = bind(self.census, self.split)
        for mode in ("extent", "source", "representation", "shape", "channel"):
            rows = InventedRows(1)
            def bad(assay):
                rows.length = assay.total_frames - (mode == "extent")
                return subject.SourceRows("3"*64 if mode == "source" else assay.source_sha256,
                    "3"*64 if mode == "representation" else assay.representation_sha256,
                    (128, 128) if mode == "shape" else subject.SHAPE,
                    ("omitted-channel",) if mode == "channel" else assay.channels, rows)
            with self.assertRaises(subject.AdmissionError):
                subject.prepare_fold(c, s, **pins, assay_id="WFCI1", fold=0, source_loader=bad)
            self.assertEqual(rows.reads, [])

    def test_fixed_170_trials_remain_whole_and_mask_each_trial_start(self):
        for a in self.census["assays"]:
            for i, trial in enumerate(a["trials"]): trial.update(source_start=i*170, length=170)
        views = self.prepare()
        for view in views.values():
            self.assertEqual([i for i, x in enumerate(view.reset_mask()) if x == 0], list(range(0, len(view), 170)))
            self.assertTrue(all(s.length == 170 for s in view.spans))
        self.assertEqual(self.sources[-1].reads, [])

    def test_lazy_index_boundaries_and_invalid_row(self):
        view = self.prepare()["test"]
        self.assertEqual(view[-1].source_index, view[len(view)-1].source_index)
        for index in (len(view), -len(view)-1):
            with self.assertRaises(IndexError): view[index]
        for index in (True, slice(None)):
            with self.assertRaises(TypeError): view[index]
        bad = subject.TrialView([(1,)], (subject.Span("invented", 0, 1, 0),))
        with self.assertRaises(subject.AdmissionError): bad[0]


if __name__ == "__main__":
    unittest.main(verbosity=2)
