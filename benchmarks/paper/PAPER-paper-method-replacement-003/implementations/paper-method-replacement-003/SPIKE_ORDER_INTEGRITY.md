# Spike order at the original preparation boundary

`programme.preparation.load_raw_unit` now compares neighboring spike indices
directly. Its previous `np.diff(spikes) < 0` check could wrap for unsigned HDF5
integers and accept decreasing timestamps. The loader still rejects negative or
noninteger indices, preserves valid dtypes and duplicate timestamps, and keeps
the original spike-aligned QC masks. It does not sort or repair observations.

This protects the original 3D autocorrelogram input: the pinned author
[`crosscorr_vs_firing_rate`](https://github.com/m-beau/NeuroPyxels/blob/703a10fb43fc7fe0076c9c331e6b52d3195b5e60/npyx/corr.py#L796-L809)
uses the final spike to size its time axis and adjacent spikes to calculate
firing-rate intervals. A decreasing source sequence must fail preparation
instead of silently changing this classifier input. The same loader serves
mouse training and macaque transfer populations.

Run `python -B tests/spike_order_checks.py` with NumPy and h5py available.
The six generated checks exercise the actual HDF5 loader, including unsigned
decreases, signed decreases, exact valid round trips and QC alignment. They do
not call the original scientific package or compute ACGs. No authentic input
validation, numerical reproduction, complete endpoint qualification or
scientific improvement is established. Cohorts, splits, model counts and all
confidence/coverage scoring conventions are unchanged.
