"""Generated-only equivalence and refusal controls; never opens source arrays."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
KEY = b"I" * 32  # Generated fixture only, never an authentic evaluator key.


def load(name, path, pin=None):
    raw = path.read_bytes()
    if pin is not None and hashlib.sha256(raw).hexdigest() != pin:
        raise RuntimeError("reviewed source dependency differs")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    exec(compile(raw, str(path), "exec"), module.__dict__)
    return module


m = load("generated_indexed_windows", HERE / "indexed_windows.py")
core = load("generated_indexed_paired_core", HERE / "paired_windows.py",
            "00b4358cbd834f6d9a443c5c553920561301c4bfe2910075743ff92556a878be")
policy = load("generated_indexed_numeric_policy",
              HERE.parent / "source-eeg-numeric-v1/numeric_policy.py",
              "695022e90fb28deac0318b8c253bd66cc0b051155ac90746940951159b1997f5")


def clock(size, duplicates=(), first=100000):
    return m.NativeClock(first, size, first+4*(size-1)-4*len(duplicates),
                         duplicates, {"duplicate_timestamp": 1} if duplicates else {})


def event(model, row, target=3, reasons=None):
    return {"schema": "dosei_private_annotation_event_v1", "visibility": "evaluator_private",
            "source_event_id": f"recording:41/row:{row}", "recording_id": "41",
            "source_row": row, "recognized_time_ms": model.time(row),
            "condition": core.CONDITION, "marker_kind": "moaas_assessment_marker",
            "moaas_grouped_ordinal": target, "biological_person_id": None,
            "assessment_onset_verified": False, "unresolved_reason_codes": reasons or []}


def native_rows(model):
    values = [policy.parse_sample(v) for v in
              ("1.0", "", "NaN", "300", "187.5", "-187.5", "1e-999", "-0.0", "bad", "1e999")]
    for i in range(model.row_count):
        left, right = values[i % len(values)], values[(i+3) % len(values)]
        yield (i, model.time(i), left[0], right[0], left[1], right[1])


class IndexedWindows(unittest.TestCase):
    def index(self, model, row, target=3, reasons=None):
        return m.make_case_index(model, event(model, row, target, reasons), secret=KEY, core=core)

    def project(self, index, rows, **kw):
        return m.project_window(index, rows, secret=kw.get("secret", KEY), core=core, policy=policy)

    def compare(self, model, marker, target=3, reasons=None):
        rows = list(native_rows(model))
        e = event(model, marker, target, reasons)
        index = m.make_case_index(model, e, secret=KEY, core=core)
        builder = core.PairedWindowBuilder("41", KEY, policy)
        streaming = None
        for row in rows:
            result = builder.consume(row, e if row[0] == marker else None)
            if result is not None:
                streaming = result
        selected = rows[index["start_row"]:index["end_row_exclusive"]]
        packet = self.project(index, iter(selected))
        self.assertEqual(packet, streaming[0])
        self.assertEqual(index["evaluator"], streaming[1])
        self.assertEqual(packet["case_id"], core.opaque_case_id(KEY, "41", marker))
        self.assertEqual(set(packet), core.PUBLIC_FIELDS)
        self.assertLess(len(json.dumps(index)), 2048)
        return index, packet, rows

    def test_full_window_and_later_shift_equivalent_to_complete_stream(self):
        for marker in (7500, 7550):
            with self.subTest(marker=marker):
                index, packet, _ = self.compare(clock(7602), marker)
                self.assertEqual(packet["coverage"]["row_count"], 7500)
                self.assertTrue(packet["coverage"]["full_interval_recorded"])
                self.assertEqual(packet["relative_time_ms"], list(range(-30000, 0, 4)))
                self.assertEqual(index["start_row"], marker-7500)

    def test_short_empty_all_blank_and_ambiguous_retained(self):
        self.compare(clock(6), 0)
        self.compare(clock(6, (1,)), 1)
        index, packet, rows = self.compare(clock(6), 3, target=None, reasons=["ambiguous"])
        self.assertEqual(packet["coverage"]["source_prefix_missing_ms"], 29988)
        blank, flag = policy.parse_sample("")
        selected = [(r[0], r[1], blank, blank, flag, flag) for r in rows[:3]]
        result = self.project(index, selected)
        self.assertEqual(result["values_uv"], [[None, None]]*3)
        self.assertEqual(result["observation_mask"], [[False, False]]*3)
        self.assertIsNone(index["evaluator"]["moaas_grouped_ordinal"])

    def test_duplicate_at_left_inclusive_and_marker_exclusive_boundaries(self):
        index, packet, _ = self.compare(clock(7600, (3,)), 7503)
        self.assertEqual(index["start_row"], 2)
        self.assertEqual(packet["relative_time_ms"][:2], [-30000, -30000])
        self.assertEqual(packet["coverage"]["row_count"], 7501)
        index, packet, _ = self.compare(clock(7600, (7501,)), 7501)
        self.assertEqual(index["end_row_exclusive"], 7500)
        self.assertEqual(packet["coverage"]["row_count"], 7500)
        self.assertNotIn(0, packet["relative_time_ms"])

    def test_clock_binary_search_matches_bruteforce_and_rejects_other_anomalies(self):
        for dup in ((), (1,), (4,), (24,)):
            model = clock(25, dup, first=0)
            expected = [model.time(i) for i in range(25)]
            for boundary in range(-5, 105):
                self.assertEqual(model.lower_bound(boundary),
                                 next((i for i,t in enumerate(expected) if t >= boundary), 25))
            roundtrip = m.NativeClock.from_binding(model.binding())
            self.assertEqual([roundtrip.time(i) for i in range(25)], expected)
        for args in (
            (0, 5, 16, (), {"backward_timestamp": 1}),
            (0, 5, 16, (), {"duplicate_timestamp": 0}),
            (0, 5, 12, (2,), {"duplicate_timestamp": True}),
            (0, 5, 16, (2,), {"duplicate_timestamp": 1}),
            (0, 5, 8, (1, 2), {"duplicate_timestamp": 2}),
            (0, 5, 12, (0,), {"duplicate_timestamp": 1}),
            (0, 5, 12, (True,), {"duplicate_timestamp": 1}),
            (False, 5, 16, (), {}),
            (0, True, 0, (), {}),
            (0, 0, 0, (), {}),
            (2**63-1, 2, 2**63+3, (), {}),
        ):
            with self.subTest(args=args), self.assertRaises(m.IndexRefusal):
                m.NativeClock(*args)
        issues = {"duplicate_timestamp": 1}
        immutable = m.NativeClock(0, 5, 12, (2,), issues)
        issues["new_problem"] = 5
        self.assertEqual(immutable.binding()["issue_counts"], {"duplicate_timestamp": 1})

    def test_private_targets_and_future_values_never_enter_public_packet(self):
        model = clock(10)
        rows = list(native_rows(model))
        packets = []
        for target in (1, 5, None):
            index = self.index(model, 3, target, ["evaluator-only-reason"])
            public = self.project(index, rows[:3])
            packets.append(public)
            encoded = json.dumps(public, allow_nan=False)
            for name in ("recording_id", "source_row", "marker_time_ms", "moaas_grouped",
                         "source_event_id", "evaluator-only-reason", "clock", "split"):
                self.assertNotIn(name, encoded)
        self.assertEqual(packets[0], packets[1])
        self.assertEqual(packets[1], packets[2])
        class WindowOnly:
            def __init__(self): self.calls = 0
            def __iter__(self): return self
            def __next__(self):
                self.calls += 1
                if self.calls <= 3: return rows[self.calls-1]
                raise StopIteration
        stream = WindowOnly()
        self.assertEqual(self.project(self.index(model, 3), stream), packets[0])
        self.assertEqual(stream.calls, 4)  # one EOF probe, no marker/future payload
        with self.assertRaises(m.IndexRefusal):
            self.project(self.index(model, 3), rows[:3], secret=b"X" * 32)
        first, second = self.index(model, 1), self.index(model, 2)
        self.assertNotEqual(first["case_id"], second["case_id"])

    def test_missing_extra_reordered_or_wrong_clock_rows_refuse(self):
        index, _, rows = self.compare(clock(8), 4)
        selected = rows[:4]
        bad_cases = [
            selected[:-1],
            selected+[object()],  # rejects without inspecting a future object
            [selected[1], selected[0], *selected[2:]],
            [selected[0], (1, selected[1][1]+4, *selected[1][2:]), *selected[2:]],
            [(True, selected[0][1], *selected[0][2:]), *selected[1:]],
            [list(selected[0]), *selected[1:]],
        ]
        for rows_bad in bad_cases:
            with self.subTest(count=len(rows_bad)), self.assertRaises(m.IndexRefusal):
                self.project(index, rows_bad)
        empty = self.index(clock(2), 0)
        with self.assertRaises(m.IndexRefusal):
            self.project(empty, [object()])

    def test_quality_and_value_validated_through_existing_observe(self):
        index = self.index(clock(2), 1)
        for value, quality in ((300.0, 0), (300.0, policy.BLANK), (1.0, policy.EXACT_ENDPOINT),
                               (2.0, policy.NONZERO_UNDERFLOW), (0.0, True), (0.0, 128)):
            with self.subTest(value=value, quality=quality), self.assertRaises(core.PacketRefusal):
                self.project(index, [(0, 100000, value, 1.0, quality, 0)])
        packet = self.project(index, [(0, 100000, 187.5, 300.0, policy.EXACT_ENDPOINT, policy.OUT_OF_RANGE)])
        self.assertEqual(packet["values_uv"], [[187.5, None]])
        self.assertEqual(packet["source_endpoint_mask"], [[True, False]])

    def test_private_index_and_event_envelopes_recompute_fail_closed(self):
        model = clock(10)
        index = self.index(model, 3)
        for mutate in (
            lambda d: d.update(start_row=True),
            lambda d: d.update(end_row_exclusive=4),
            lambda d: d["coverage"].update(row_count=True),
            lambda d: d["evaluator"].update(marker_time_ms=100000),
            lambda d: d["evaluator"].update(source_row=True),
            lambda d: d["evaluator"].update(moaas_grouped_ordinal=True),
            lambda d: d["evaluator"].update(biological_person_id="invented"),
            lambda d: d.update(case_id="0"*64),
            lambda d: d["clock"].update(last_time_ms=100000),
            lambda d: d.update(unexpected="not admitted"),
        ):
            bad = copy.deepcopy(index); mutate(bad)
            with self.assertRaises((m.IndexRefusal, core.PacketRefusal)):
                self.project(bad, [])
        for changes in ({"recognized_time_ms":100000}, {"source_row":True},
                        {"recording_id":"041"}, {"assessment_onset_verified":True},
                        {"unresolved_reason_codes":"not-list"}, {"source_event_id":"wrong"}):
            e = event(model, 3); e.update(changes)
            with self.assertRaises((m.IndexRefusal, core.PacketRefusal)):
                m.make_case_index(model, e, secret=KEY, core=core)
        e = event(model, 3); e["marker_kind"] = "soc_transition_marker"
        self.assertIsNone(m.make_case_index(model, e, secret=KEY, core=core))


if __name__ == "__main__":
    unittest.main()
