"""Generated metadata controls; no authentic recording or prepared packet reads."""
import copy
import unittest

from support import (ContractError, SOURCE, SOURCE_SPLITS, SELECTED_SPLITS,
                     SUPPORT_AXES, SUPPORT_LEVELS, validate_metadata)


def generated_metadata():
    """204 synthetic trials; three combined empty cells and more split-empty cells."""
    rows = []
    for segment in range(6):
        for slot in range(34):
            index = len(rows)
            code = slot % 8
            if segment == 0 and code == 0:
                code = 1
            if segment == 1 and code in (0, 2):
                code = 3
            if segment == 2 and slot >= 25:
                code = 0
            start = float(1000 * segment + 10 + slot * 3)
            ready, stop = start - 0.8, start + 1.0
            rows.append({"source_row": index, "trial_id": 10000 + index,
                         "source_split": "train" if slot < 25 else "val",
                         "is_eye": bool(code // 4), "theta": float(180 * ((code // 2) % 2)),
                         "is_short": bool(code % 2), "nominal_sample_interval_ms": 800.0,
                         "start_time": start - 1.0, "ready_time": ready, "set_time": start,
                         "go_time": stop, "stop_time": stop + 0.2, "observation_segment": segment,
                         "actual_sample_interval_seconds": start - ready,
                         "observed_production_interval_seconds": stop - start})
    census = []
    for index in range(1160):
        split = (rows[index]["source_split"] if index < 204 else
                 "train" if index < 802 else "val" if index < 1006 else "none")
        selected = index < 204
        census.append({"source_row": index, "trial_id": 10000 + index, "source_split": split,
                       "nominal_selected": selected,
                       "selection_reason": "nominal_800_train_val" if selected else
                       "outside_source_train_val" if split == "none" else "nominal_interval_not_800"})
    combined = [[[[0 for _ in range(2)] for _ in range(2)] for _ in range(2)] for _ in range(6)]
    for row in rows:
        combined[row["observation_segment"]][int(row["is_eye"])][int(row["theta"] == 180)][int(row["is_short"])] += 1
    zeros = [[g, e, d, p] for g in range(6) for e in range(2) for d in range(2)
             for p in range(2) if combined[g][e][d][p] == 0]
    return {"schema": "neural096_full_set_go_observations_v1", "status": "source_metadata_supported",
            "task_id": "NEURAL-096", "source": dict(SOURCE), "unit_ids": list(range(54)),
            "nlb_heldout_unit_flags": [False] * 40 + [True] * 14,
            "selected_trial_count": 204, "parent_source_split_counts": dict(SOURCE_SPLITS),
            "selected_split_counts": dict(SELECTED_SPLITS), "census": census, "trials": rows,
            "observation_segments_seconds": [[float(1000 * g), float(1000 * g + 200)] for g in range(6)],
            "representation": {"phase_bins": 20, "interval": "[native set_time, native go_time)",
                               "count_units": "spikes per source unit per phase bin",
                               "exposure_units": "seconds per phase bin", "no_fitted_basis": True,
                               "no_smoothing": True},
            "support": {"axes": list(SUPPORT_AXES), "levels": copy.deepcopy(SUPPORT_LEVELS),
                        "counts": combined, "zero_cells": zeros, "all_cells_present": not zeros}}


class SupportTests(unittest.TestCase):
    def setUp(self):
        self.metadata = generated_metadata()

    def reject(self, change, message):
        data = copy.deepcopy(self.metadata)
        change(data)
        with self.assertRaisesRegex(ContractError, message):
            validate_metadata(data)

    def test_complete_roster_and_split_specific_missingness(self):
        before = copy.deepcopy(self.metadata)
        out = validate_metadata(self.metadata)
        self.assertEqual(self.metadata, before)
        self.assertEqual(len(out["cells"]), 48)
        self.assertEqual(len(out["combined_zero_cells"]), 3)
        self.assertGreater(len(out["split_zero_cells"]), 3)
        indices = [i for cell in out["cells"] for group in ("long_trial_indices", "short_trial_indices")
                   for i in cell[group]]
        self.assertEqual(sorted(indices), list(range(204)))
        self.assertEqual(out["split_counts"][1][2][0][0], [9, 0])
        self.assertEqual(out["combined_counts"][2][0][0], [13, 3])
        missing = next(c for c in out["cells"] if c["cell_id"] == "val-segment2-eye0-direction0")
        self.assertEqual(missing["missing_priors"], ["short"])
        self.assertFalse(missing["supported"])

    def test_source_declaration_is_checked_but_not_authentication(self):
        out = validate_metadata(self.metadata)
        self.assertFalse(out["source_authenticated"])
        self.reject(lambda d: d["source"].update(sha256="0" * 64), "source identity")
        self.reject(lambda d: d.update(selected_split_counts={"train": 149, "val": 55}), "selected split")

    def test_complete_units_and_boolean_flags(self):
        self.reject(lambda d: d["unit_ids"].__setitem__(53, 0), "54 distinct")
        self.reject(lambda d: d["unit_ids"].__setitem__(0, False), "54 distinct")
        self.reject(lambda d: d["nlb_heldout_unit_flags"].__setitem__(40, 1), "held-out-unit")
        self.reject(lambda d: d["nlb_heldout_unit_flags"].__setitem__(40, False), "held-out-unit")

    def test_selected_identity_and_source_census_join(self):
        self.reject(lambda d: d["trials"][1].update(trial_id=10000), "duplicate selected")
        self.reject(lambda d: d["trials"][1].update(source_row=0), "duplicate selected")
        self.reject(lambda d: d["trials"][1].update(source_split="val"), "source census")
        self.reject(lambda d: d["trials"].pop(), "204-trial")

    def test_original_row_order_and_interval_nonoverlap(self):
        self.reject(lambda d: d["trials"].reverse(), "trial order")
        self.reject(lambda d: d["trials"][1].update(start_time=9.0, ready_time=10.0,
                    set_time=10.5, go_time=11.5, stop_time=12.0,
                    actual_sample_interval_seconds=0.5), "trial order")

    def test_native_event_and_duration_consistency(self):
        self.reject(lambda d: d["trials"][0].update(ready_time=10.0), "event order")
        self.reject(lambda d: d["trials"][0].update(set_time=float("nan")), "native event")
        self.reject(lambda d: d["trials"][0].update(actual_sample_interval_seconds=0.8), "duration declarations")
        self.reject(lambda d: d["trials"][0].update(observed_production_interval_seconds=2.0), "duration declarations")

    def test_full_interval_observation_support(self):
        self.reject(lambda d: d["trials"][0].update(observation_segment=1), "observation support")
        self.reject(lambda d: d["observation_segments_seconds"][0].__setitem__(1, 10.5), "observation support")
        self.reject(lambda d: d["observation_segments_seconds"][1].__setitem__(0, 200.0), "ordered disjoint")

    def test_cue_and_index_types(self):
        self.reject(lambda d: d["trials"][0].update(is_short=1), "flags must be boolean")
        self.reject(lambda d: d["trials"][0].update(theta=True), "direction must be")
        self.reject(lambda d: d["trials"][0].update(theta=90.0), "unknown response direction")
        self.reject(lambda d: d["trials"][0].update(nominal_sample_interval_ms=799.0), "800 ms")
        self.reject(lambda d: d["trials"][0].update(observation_segment=False), "must be an integer")

    def test_forged_complete_support_is_rejected(self):
        self.reject(lambda d: d["support"].update(all_cells_present=True), "original support")
        self.reject(lambda d: d["support"].update(zero_cells=[]), "original support")
        self.reject(lambda d: d["support"]["counts"][0][0][0].__setitem__(0, False), "original support")
        self.reject(lambda d: d["support"]["counts"][0][0][0].__setitem__(0, 1), "original support")

    def test_census_selection_and_parent_coverage(self):
        self.reject(lambda d: d["census"].pop(), "1160-row")
        self.reject(lambda d: d["census"][1].update(source_row=0), "census order")
        self.reject(lambda d: d["census"][0].update(nominal_selected=1), "flag must be boolean")
        self.reject(lambda d: d["census"][0].update(selection_reason="nominal_interval_not_800"), "selection reason")
        self.reject(lambda d: d["parent_source_split_counts"].update(train=747), "parent split")

    def test_representation_and_unknown_fields_do_not_cross_projection(self):
        self.reject(lambda d: d["representation"].update(exposure_units="milliseconds"), "representation changed")
        self.metadata["private_reference"] = "answer should not cross"
        self.metadata["trials"][0]["target_answer"] = 12
        out = validate_metadata(self.metadata)
        self.assertNotIn("private_reference", out)
        self.assertNotIn("target_answer", out["trials"][0])
        out["trials"][0]["trial_id"] = -1
        out["unit_ids"][0] = -1
        self.assertEqual(self.metadata["trials"][0]["trial_id"], 10000)
        self.assertEqual(self.metadata["unit_ids"][0], 0)


if __name__ == "__main__":
    unittest.main()
