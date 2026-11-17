"""Generated source-format controls; no empirical data or fitted model runs."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from scipy.io import loadmat, savemat

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent / "initial-evaluator-v1"))
import source_adapter as adapter
import evaluator as historical


def source_struct(traces):
    voltage = np.empty(len(traces), dtype=object)
    voltage[:] = traces
    return {
        "Trial_MembranePotential": voltage,
        "Trial_MembranePotential_SamplingRate": np.full(len(traces), 20000),
        "Trial_Type": np.array(["Spont"] * len(traces), dtype=object),
        "Cell_Type": np.array(["PV"] * len(traces), dtype=object),
        "Mouse_Name": np.array(["generated-mouse"] * len(traces), dtype=object),
        "Cell_Counter": np.ones(len(traces)),
    }


class SourceAdapterTests(unittest.TestCase):
    def test_source_volts_reproduce_crossings_in_millivolts(self):
        voltage = np.full(1000, -.060)
        voltage[200:202] = [.010, -.020]
        voltage[400] = -.030
        data = source_struct([voltage, voltage.copy()])
        old = historical.decode_pala(data)
        with self.assertRaisesRegex(historical.ContractError, "begins above"):
            historical.spike_indices(old[0].voltage_mv)
        actual = adapter.decode_pala_volts(data)
        self.assertEqual(actual[0].voltage_mv[0], -60)
        self.assertEqual(actual[0].voltage_mv[200], 10)
        np.testing.assert_array_equal(historical.spike_indices(actual[0].voltage_mv), [200, 400])
        clean, times = historical.remove_spikes(actual[0].voltage_mv)
        np.testing.assert_array_equal(times, [200, 400])
        np.testing.assert_allclose(clean, -60)
        self.assertEqual(voltage[200], .010)
        self.assertFalse(actual[0].voltage_mv.flags.writeable)

    def test_real_mat_serialization_preserves_source_rows_and_trace_lengths(self):
        data = source_struct([np.array([[-.065, -.030, .015]]),
                              np.array([[-.052], [-.040], [.020], [-.060]])])
        data["Mouse_Name"] = np.array(["mouse-B", "mouse-A"], dtype=object)
        data["Cell_Counter"] = np.array([3, 2])
        data["Cell_Type"] = np.array(["Sst", "PV"], dtype=object)
        data["Trial_Type"] = np.array(["uEPSP", "Spont"], dtype=object)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "generated-source-volts.mat"
            savemat(path, {"data": data}, long_field_names=True)
            loaded = loadmat(path, simplify_cells=True)
            actual = adapter.decode_pala_volts(loaded["data"])
        self.assertEqual([t.trial_id for t in actual], ["pala-row-000001", "pala-row-000002"])
        self.assertEqual([t.cell_id for t in actual], ["mouse-B_3", "mouse-A_2"])
        self.assertEqual([t.cell_type for t in actual], ["Sst", "PV"])
        self.assertEqual([t.trial_type for t in actual], ["uEPSP", "Spont"])
        np.testing.assert_allclose(actual[0].voltage_mv, [-65, -30, 15])
        np.testing.assert_allclose(actual[1].voltage_mv, [-52, -40, 20, -60])

    def test_preserves_20khz_sample_index_and_no_amplitude_inference(self):
        data = source_struct([np.array([-.060, -.031, -.029, -.060])])
        trial = adapter.decode_pala_volts(data)[0]
        self.assertEqual(trial.sampling_hz, 20000)
        np.testing.assert_array_equal(historical.spike_indices(trial.voltage_mv), [2])
        self.assertEqual(2 / trial.sampling_hz, .0001)
        # Explicit volts are converted even for small signals; no amplitude heuristic.
        small = adapter.decode_pala_volts(source_struct([np.array([1e-6, -2e-6])]))[0]
        np.testing.assert_allclose(small.voltage_mv, [.001, -.002])

    def test_generated_cohort_rate_uses_source_volts_correctly(self):
        # 400 spikes / 20 seconds = exactly 20 Hz, ten separate source trials.
        voltage = np.full(400000, -.060)
        voltage[500::1000] = .010
        source = source_struct([voltage] * 10)
        trials = adapter.decode_pala_volts(source)
        eligible, ledger = historical.audit_population(trials)
        self.assertEqual(list(eligible), ["generated-mouse_1"])
        self.assertEqual(ledger[0]["mean_rate_hz"], 20)
        self.assertEqual(len(ledger[0]["candidate_trial_ids"]), 10)
        # No inferred authentic eight-neuron/five-mouse mapping is asserted.
        self.assertEqual([len(t.voltage_mv) for t in trials], [400000] * 10)

    def test_non_source_payload_rejected_before_mat_decode(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "data.mat"
            path.write_bytes(b"generated control, not authentic data")
            with patch.object(adapter, "loadmat") as reader:
                with self.assertRaisesRegex(adapter.SourceContractError, "MD5"):
                    adapter.load_pala(path)
                reader.assert_not_called()

    def test_rejects_nonfinite_complex_and_ambiguous_trace_shapes(self):
        invalid = [np.array([-.06, np.nan]), np.array([-.06, np.inf]),
                   np.array([1j, 2j]), np.ones((2, 2)), np.array([-.06]),
                   np.array(["-.06", "-.05"]), np.array([1e308, -1e308])]
        for trace in invalid:
            with self.subTest(trace=repr(trace)):
                with self.assertRaises(adapter.SourceContractError):
                    adapter.decode_pala_volts(source_struct([trace]))

    def test_missing_alignment_and_biological_identity_refused(self):
        original = source_struct([np.array([-.06, -.05])] * 2)
        for field, values in (
            ("Mouse_Name", ["", "mouse"]), ("Mouse_Name", [None, "mouse"]),
            ("Cell_Counter", [1.5, 1]), ("Cell_Counter", [True, False]),
            ("Trial_MembranePotential_SamplingRate", [1000, 20000]),
            ("Trial_Type", ["Spont"]),
        ):
            with self.subTest(field=field, values=values):
                data = dict(original)
                data[field] = values
                with self.assertRaises(adapter.SourceContractError):
                    adapter.decode_pala_volts(data)
        data = dict(original)
        del data["Cell_Type"]
        with self.assertRaises(adapter.SourceContractError):
            adapter.decode_pala_volts(data)


if __name__ == "__main__":
    unittest.main()
