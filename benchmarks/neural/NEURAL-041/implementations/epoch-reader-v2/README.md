# Epoch reader using public NumPy header APIs

This replacement for NEURAL-041's `epoch_io.py` uses NumPy's documented
[`read_array_header_1_0`](https://numpy.org/doc/stable/reference/generated/numpy.lib.format.read_array_header_1_0.html)
and [`read_array_header_2_0`](https://numpy.org/doc/stable/reference/generated/numpy.lib.format.read_array_header_2_0.html).
The predecessor calls the private `_read_array_header` export, which was absent
in the Homebrew environment used by the earlier
[modality-retention controls](../modality-retention-v2/VERIFICATION.json).

The reader dispatches only after admitting NPY version 1.0 or 2.0. The existing
1,024-byte header limit, primitive dtype and allocation checks, sealed-input
authentication, five-member epoch format, 1,000-sample LFP interval, spike
boundaries and region checks remain in place. It introduces no resampling,
trial selection or numerical conversion.

`load_epoch(root, row, budget, cap, regions)` retains the original signature.
For an explicitly selected preparation or actor capsule, use this `epoch_io.py`
with the unchanged `core.py` from `../registered-runtime/runtime/source`.
[SOURCE_PINS.json](SOURCE_PINS.json) identifies that dependency and the
predecessor. The historical registered runtime and modality-retention component
still select their recorded reader. Selecting this replacement for an active
campaign requires updating that campaign's source selection and runtime pins.

## Generated controls

With an existing Python environment containing NumPy, run:

```sh
python3 -I -B test_epoch_io.py --scratch /absolute/existing/scratch-directory
```

An isolated source checkout can additionally pass `--runtime-source` with the
path to the unchanged registered source directory. The controls exercise complete
NPY 1.0/2.0 epochs, spike-only observations and existing header, dtype, extent,
spike and region restrictions. The regression restricts NumPy's exported format
surface to its public readers: the predecessor fails and the replacement reads
the same generated epoch. It does not remove internal globals used by NumPy.

All ten controls passed in the selected existing Python 3.11.6 / NumPy 1.26.3
environment. Both admitted NPY versions were tested; the unavailable private
export is modeled by the public-only proxy, not by claiming a second installed
NumPy version was tested.

These generated controls establish the selected software behavior only. They
do not establish compatibility with every NumPy release, authentic NWB
preparation, isolated participant execution, decoder accuracy or neural
interpretation. Scientific and runtime qualification remain open.
