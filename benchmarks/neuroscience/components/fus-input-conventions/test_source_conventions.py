"""Generated boundary controls only; no native arrays or scientific execution."""
import unittest
from source_conventions import (
    parse_behavior_clock_ms, parse_rt_summary_clock_ms, rt_grid_label_to_degrees,
)


class ConventionControls(unittest.TestCase):
    def test_known_units(self):
        self.assertEqual(parse_behavior_clock_ms("01:02:03,004"), 3723004)
        self.assertEqual(parse_behavior_clock_ms("123:45:06,007"), 445506007)

    def test_signed_whole_magnitude(self):
        self.assertEqual(parse_behavior_clock_ms("-01:02:03,004"), -3723004)
        self.assertEqual(parse_behavior_clock_ms("-00:00:00,001"), -1)

    def test_missing_is_not_zero(self):
        for fn in (parse_behavior_clock_ms, parse_rt_summary_clock_ms):
            self.assertIsNone(fn(None))
            self.assertIsNone(fn(""))
        self.assertEqual(parse_behavior_clock_ms("00:00:00,000"), 0)

    def test_separator_is_explicit(self):
        self.assertEqual(parse_rt_summary_clock_ms("01:02:03.004"), 3723004)
        with self.assertRaises(ValueError): parse_behavior_clock_ms("01:02:03.004")
        with self.assertRaises(ValueError): parse_rt_summary_clock_ms("01:02:03,004")

    def test_first_two_summary_clock_columns_refused(self):
        for value in ("01-02-03.004", "23-59-59.999"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_rt_summary_clock_ms(value)

    def test_invalid_clock_values(self):
        for value in ("00:60:00,000", "00:00:60,000", "00:99:99,999"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_behavior_clock_ms(value)

    def test_no_implicit_coercions(self):
        for value in (False, 0, 1.2, [], {}, " 00:00:00,000", "00:00:00,000\n",
                      "+00:00:00,000", "0:00:00,000", "1000:00:00,000",
                      "00:00:00,00", "00:00:00,0000", "００:00:00,000", "00:00:00,000Z"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_behavior_clock_ms(value)

    def test_no_midnight_unwrapping(self):
        last = parse_behavior_clock_ms("23:59:59,999")
        first = parse_behavior_clock_ms("00:00:00,000")
        self.assertEqual(first-last, -86399999)

    def test_millisecond_precision(self):
        a = parse_behavior_clock_ms("999:59:59,998")
        b = parse_behavior_clock_ms("999:59:59,999")
        self.assertIs(type(b), int)
        self.assertEqual(b-a, 1)

    def test_all_eight_geometric_directions(self):
        grid_labels_counterclockwise_from_right = [6, 9, 8, 7, 4, 1, 2, 3]
        self.assertEqual([rt_grid_label_to_degrees(x) for x in grid_labels_counterclockwise_from_right],
                         [0, 45, 90, 135, 180, 225, 270, 315])

    def test_center_and_nonlabels_refused(self):
        for label in (0, 5, 10, -1, True, False, 1.0, "1", None):
            with self.subTest(label=label), self.assertRaises(ValueError):
                rt_grid_label_to_degrees(label)


if __name__ == "__main__":
    unittest.main()
