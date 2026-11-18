"""Generated metadata-only checks; no authentic electrode or atlas reads.

This entrypoint reads only the byte/sha-pinned sibling coordinate_gate.py.
No affine, voxel or index numerical tests are asserted: their source binding
is unresolved. Run with the parent's admitted metadata-pool command.
"""

import builtins
import hashlib
import json
from pathlib import Path
import types
import unittest

EXPECTED_MODULE_BYTES = 7833
EXPECTED_MODULE_SHA256 = "a6a85b8fe2c5adcefd1d3e4281bd28af1d02d80c36db4342e0056d244e4e808e"
MODULE_PATH = Path(__file__).resolve().with_name("coordinate_gate.py")
with MODULE_PATH.open("rb") as handle:
    MODULE_BYTES = handle.read(EXPECTED_MODULE_BYTES + 1)
if len(MODULE_BYTES) != EXPECTED_MODULE_BYTES:
    raise RuntimeError("coordinate gate size mismatch")
if hashlib.sha256(MODULE_BYTES).hexdigest() != EXPECTED_MODULE_SHA256:
    raise RuntimeError("coordinate gate SHA256 mismatch")
gate = types.ModuleType("coordinate_gate_under_test")
gate.__file__ = str(MODULE_PATH)
exec(compile(MODULE_BYTES, str(MODULE_PATH), "exec"), gate.__dict__)


def electrode(name, x=101.125, y=-202.25, z=303.5):
    return {"name": name, "x": x, "y": y, "z": z}


class EndpointGateTests(unittest.TestCase):
    def rejected(self, code, rows, pairs):
        with self.assertRaises(gate.EndpointValidationError) as caught:
            gate.validate_endpoints(rows, pairs)
        self.assertEqual(caught.exception.code, code)
        return caught.exception

    def test_author_contact_and_central_split_examples(self):
        result = gate.validate_endpoints(
            [electrode("RC-ALT2"), electrode("RC-ALT3")],
            ["RC-ALT2-RC-ALT3", "RCALT2-RCALT3"],
        )
        self.assertEqual(result["pairs"], [
            {"pair_occurrence_index": 0, "normalized_pair": "RCALT2-RCALT3", "endpoint_row_indices": [0, 1]},
            {"pair_occurrence_index": 1, "normalized_pair": "RCALT2-RCALT3", "endpoint_row_indices": [0, 1]},
        ])
        self.rejected("odd_pair_piece_count", [electrode("RC-ALT1"), electrode("RCALT2")], ["RC-ALT1-RCALT2"])

    def test_even_piece_rule_uses_equal_halves(self):
        result = gate.validate_endpoints([electrode("A-B-C"), electrode("D-E-F")], ["A-B-C-D-E-F"])
        self.assertEqual(result["pairs"][0]["normalized_pair"], "ABC-DEF")
        self.assertEqual(result["pairs"][0]["endpoint_row_indices"], [0, 1])

    def test_contact_removes_all_ascii_hyphens(self):
        result = gate.validate_endpoints([electrode("-A--1-"), electrode("B2")], ["A1-B2"])
        self.assertEqual(result["pairs"][0]["endpoint_row_indices"], [0, 1])

    def test_ambiguous_empty_pair_pieces_are_rejected(self):
        for pair in ("-A1-B2", "A1-B2-", "A1--B2", "A1---B2", "-"):
            with self.subTest(pair=pair):
                self.rejected("empty_pair_piece", [electrode("A1"), electrode("B2")], [pair])

    def test_odd_piece_and_no_separator_rejected(self):
        for pair in ("A1", "A1-B2-C3", "A-B-C-D-E"):
            with self.subTest(pair=pair):
                self.rejected("odd_pair_piece_count", [], [pair])

    def test_missing_tokens_and_empty_names(self):
        for name in ("n/a", "NaN", "N-aN"):
            with self.subTest(name=name):
                self.rejected("missing_name", [electrode(name)], [])
        for name in ("", "-", "---"):
            with self.subTest(name=name):
                self.rejected("empty_name", [electrode(name)], [])
        for pair in ("n/a", "NaN", "n/a-A1", "A1-NaN", "N-aN-B-1"):
            with self.subTest(pair=pair):
                self.rejected("missing_name", [electrode("A1"), electrode("B1")], [pair])
        self.rejected("empty_name", [], [""])

    def test_duplicate_raw_names_rejected_globally(self):
        self.rejected("duplicate_raw_name", [electrode("A1"), electrode("B2"), {"name": "UNUSED"}, {"name": "UNUSED"}], ["A1-B2"])

    def test_normalization_collisions_rejected_globally(self):
        self.rejected("normalization_collision", [electrode("A1"), electrode("B2"), {"name": "UN-USED"}, {"name": "UNUSED"}], ["A1-B2"])

    def test_missing_and_identical_endpoints_rejected(self):
        self.rejected("missing_endpoint", [electrode("A1")], ["A1-B2"])
        self.rejected("missing_endpoint", [electrode("B2")], ["A1-B2"])
        self.rejected("missing_endpoint", [], ["A1-B2"])
        self.rejected("identical_endpoints", [electrode("A1")], ["A1-A1"])
        self.rejected("identical_endpoints", [electrode("A-1")], ["A-1-A-1"])

    def test_exact_case_sensitive_names(self):
        rows = [electrode("A1"), electrode("a1"), electrode("B2")]
        result = gate.validate_endpoints(rows, ["A1-B2", "a1-B2"])
        self.assertEqual([p["endpoint_row_indices"] for p in result["pairs"]], [[0, 2], [1, 2]])
        self.rejected("missing_endpoint", rows, ["A1-b2"])

    def test_ascii_hyphen_only_and_no_whitespace_trimming(self):
        rows = [electrode("A\u20101"), electrode("B2"), electrode(" C3")]
        result = gate.validate_endpoints(rows, ["A\u20101-B2", " C3-B2"])
        self.assertEqual(result["pairs"][0]["normalized_pair"], "A\u20101-B2")
        self.rejected("missing_endpoint", rows, ["A1-B2"])
        self.rejected("missing_endpoint", rows, ["C3-B2"])

    def test_order_repetitions_reversals_and_original_indices(self):
        rows = [electrode("B2"), {"name": "UNUSED"}, electrode("A1")]
        pairs = ["A1-B2", "A1-B2", "B2-A1", "A1-B2"]
        result = gate.validate_endpoints(rows, pairs)
        self.assertEqual([p["pair_occurrence_index"] for p in result["pairs"]], [0, 1, 2, 3])
        self.assertEqual([p["normalized_pair"] for p in result["pairs"]], pairs)
        self.assertEqual([p["endpoint_row_indices"] for p in result["pairs"]], [[2, 0], [2, 0], [0, 2], [2, 0]])
        self.assertEqual(result["counts"], {"electrode_row_count": 3, "pair_occurrence_count": 4, "endpoint_occurrence_count": 8, "distinct_selected_electrode_rows": 2, "distinct_selected_coordinate_scalar_count": 6})
        self.assertEqual(pairs, ["A1-B2", "A1-B2", "B2-A1", "A1-B2"])
        self.assertEqual(rows[1], {"name": "UNUSED"})

    def test_unreferenced_coordinate_missingness_remains(self):
        rows = [{"name": "UNUSED1"}, electrode("A1"), {"name": "UNUSED2", "x": None, "y": float("nan"), "z": object()}, electrode("B2")]
        result = gate.validate_endpoints(rows, ["A1-B2"])
        self.assertEqual(result["pairs"][0]["endpoint_row_indices"], [1, 3])
        self.assertEqual(result["counts"]["electrode_row_count"], 4)

    def test_all_six_selected_coordinates_require_finiteness(self):
        for row_index in (0, 1):
            for field in ("x", "y", "z"):
                for value in (float("nan"), float("inf"), float("-inf")):
                    with self.subTest(row=row_index, field=field, value=repr(value)):
                        rows = [electrode("A1"), electrode("B2")]
                        rows[row_index][field] = value
                        error = self.rejected("coordinate_not_finite", rows, ["A1-B2"])
                        self.assertEqual(error.index, row_index)

    def test_bool_nonreal_and_missing_selected_coordinates(self):
        for value in (True, False, None, "1", complex(1, 0), object()):
            with self.subTest(value_type=type(value).__name__):
                self.rejected("coordinate_type", [electrode("A1", x=value), electrode("B2")], ["A1-B2"])
        for field in ("x", "y", "z"):
            rows = [electrode("A1"), electrode("B2")]
            del rows[1][field]
            self.rejected("missing_coordinate", rows, ["A1-B2"])

    def test_no_coordinate_coercion(self):
        class Coercible:
            def __float__(self):
                raise AssertionError("must not coerce coordinate")
        self.rejected("coordinate_type", [electrode("A1", x=Coercible()), electrode("B2")], ["A1-B2"])

    def test_integer_magnitude_bound_and_finite_builtin_numbers(self):
        largest = (1 << gate.MAX_COORDINATE_INTEGER_BITS) - 1
        result = gate.validate_endpoints([electrode("A1", x=largest, y=-largest, z=0), electrode("B2", x=1.0, y=-0.0, z=2)], ["A1-B2"])
        self.assertEqual(result["counts"]["distinct_selected_electrode_rows"], 2)
        self.rejected("coordinate_integer_too_large", [electrode("A1", x=1 << gate.MAX_COORDINATE_INTEGER_BITS), electrode("B2")], ["A1-B2"])

    def test_plain_input_types_and_required_name(self):
        self.rejected("list_type", (), [])
        self.rejected("list_type", [], ())
        self.rejected("row_type", [()], [])
        self.rejected("missing_name_field", [{}], [])
        self.rejected("text_type", [electrode(1)], [])
        self.rejected("text_type", [], [None])
        class StrChild(str):
            pass
        self.rejected("text_type", [electrode(StrChild("A1"))], [])

    def test_utf8_and_contact_name_byte_cap(self):
        first = "A" * gate.MAX_NAME_BYTES
        result = gate.validate_endpoints([electrode(first), electrode("B2")], [first + "-B2"])
        self.assertEqual(result["pairs"][0]["endpoint_row_indices"], [0, 1])
        self.rejected("text_too_large", [electrode(first + "A")], [])
        unicode_first = "\u00e9" * (gate.MAX_NAME_BYTES // 2)
        gate.validate_endpoints([electrode(unicode_first), electrode("B2")], [unicode_first + "-B2"])
        self.rejected("text_too_large", [electrode(unicode_first + "\u00e9")], [])
        self.rejected("invalid_utf8", [electrode("\ud800")], [])
        self.rejected("invalid_utf8", [], ["\ud800-B2"])

    def test_pair_byte_and_normalized_endpoint_caps(self):
        first = "A" * gate.MAX_NAME_BYTES
        second = "B" * gate.MAX_NAME_BYTES
        pair = first + "-" + second
        self.assertEqual(len(pair.encode()), gate.MAX_PAIR_BYTES)
        result = gate.validate_endpoints([electrode(first), electrode(second)], [pair])
        self.assertEqual(result["pairs"][0]["normalized_pair"], pair)
        self.rejected("text_too_large", [], [pair + "B"])
        self.rejected("text_too_large", [], [first + "A-B"])

    def test_electrode_row_cap_and_original_last_index(self):
        rows = [electrode("E" + str(i)) for i in range(gate.MAX_ELECTRODES)]
        result = gate.validate_endpoints(rows, ["E0-E" + str(gate.MAX_ELECTRODES - 1)])
        self.assertEqual(result["pairs"][0]["endpoint_row_indices"], [0, gate.MAX_ELECTRODES - 1])
        self.rejected("electrode_count_too_large", rows + [electrode("EXTRA")], [])

    def test_pair_occurrence_cap_preserves_all_repeats(self):
        rows = [electrode("A1"), electrode("B2")]
        pairs = ["A1-B2"] * gate.MAX_PAIRS
        result = gate.validate_endpoints(rows, pairs)
        self.assertEqual(len(result["pairs"]), gate.MAX_PAIRS)
        self.assertEqual(result["pairs"][-1]["pair_occurrence_index"], gate.MAX_PAIRS - 1)
        self.assertEqual(result["counts"]["endpoint_occurrence_count"], 2 * gate.MAX_PAIRS)
        self.rejected("pair_count_too_large", rows, pairs + ["A1-B2"])

    def test_whole_supplied_list_is_validated_without_filtering(self):
        error = self.rejected("missing_endpoint", [electrode("A1"), electrode("B2")], ["A1-B2", "B2-A1", "A1-MISSING"])
        self.assertEqual(error.index, 2)

    def test_empty_inputs_report_zero_support_without_readiness(self):
        result = gate.validate_endpoints([], [])
        self.assertEqual(result["pairs"], [])
        self.assertTrue(all(value == 0 for value in result["counts"].values()))
        self.assertFalse(result["participant_packet_ready"])
        result = gate.validate_endpoints([{"name": "UNUSED"}], [])
        self.assertEqual(result["counts"]["electrode_row_count"], 1)

    def test_manual_sub1_correction_is_not_applied(self):
        result = gate.validate_endpoints([electrode("LA2"), electrode("LA1")], ["LA1-LA2"])
        self.assertEqual(result["pairs"], [{"pair_occurrence_index": 0, "normalized_pair": "LA1-LA2", "endpoint_row_indices": [1, 0]}])
        self.assertNotIn("Left_Amygdala", json.dumps(result))
        self.assertFalse(result["labels_computed"])
        self.assertFalse(result["midpoint_computed"])

    def test_output_contains_only_indices_names_counts_and_false_holds(self):
        result = gate.validate_endpoints([electrode("A1"), electrode("B2")], ["A1-B2"])
        false_holds = {"coordinate_frame_verified", "index_transform_applied", "midpoint_computed", "labels_computed", "input_provenance_verified", "source_census_bound", "participant_packet_ready", "scientifically_qualified"}
        self.assertEqual(set(result), false_holds | {"endpoint_validation_only", "counts", "pairs"})
        self.assertIs(result["endpoint_validation_only"], True)
        for key in false_holds:
            self.assertIs(result[key], False)
        self.assertEqual(set(result["pairs"][0]), {"pair_occurrence_index", "normalized_pair", "endpoint_row_indices"})
        for value in ("101.125", "-202.25", "303.5", '"x"', '"y"', '"z"', '"midpoint"', '"labels"'):
            self.assertNotIn(value, json.dumps(result))
        for name in ("midpoint", "apply_affine", "voxel_index", "transform", "no_op_transform"):
            self.assertFalse(hasattr(gate, name))

    def test_gate_performs_no_file_io(self):
        original = builtins.open
        def forbidden(*args, **kwargs):
            raise AssertionError("endpoint validation must not perform file I/O")
        builtins.open = forbidden
        try:
            result = gate.validate_endpoints([electrode("A1"), electrode("B2")], ["A1-B2"])
        finally:
            builtins.open = original
        self.assertEqual(result["pairs"][0]["endpoint_row_indices"], [0, 1])


if __name__ == "__main__":
    unittest.main(verbosity=2)
