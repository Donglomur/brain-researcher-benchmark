# Public-input fixed-delay-warp reference

`reference_program.py` fills the missing participant-side executable for the
registered fixed-delay-warp comparator. It reads only the admitted public
one-second calibration and validation trajectories and emits a complete
`neural029-predictions-v1` submission through the existing frozen-program ABI.
The existing preparation's private baseline arrays remain unchanged.

For each pair and registered cell, the program averages **every** public source
trial with equal trial weight, then evaluates that mean at `g(t) = t/2` for
`0 <= t < 2` and `g(t) = t - 1` for `2 <= t <= 3`, using linear interpolation on
the exact 61-point source grid. It repeats the resulting trajectory for every
declared target trial. At `t = 2`, both branches select source time `1`.
There is no fitted warp, target adaptation, trial filtering, behavior input,
or cohort reduction. Calibration and validation are combined only because this
fixed method makes no selection and the registered contract permits final
refitting on all public one-second trials.

This one file can be supplied as the executor's frozen `program`; it has no
sibling imports and accepts exactly the existing required arguments:

```sh
/ADMITTED/venv/bin/python -I -B reference_program.py \
  --input /input --output /output/submission.json
```

Python 3.11/3.12 and the already selected NumPy 2.2.6 are required. The program
does not install dependencies or create a native image. It requires an admitted
public packet at `/input/public/MANIFEST.json` and its hash-bound source NPZ
files; private files are not needed or opened. File paths, complete opaque
axes, source split, hashes, numeric NPY geometry, finite values and all pair
records are checked. It streams the repeated output within the existing
100,000,000-byte submission limit. A missing or malformed late pair, numeric
failure or exceeded limit removes staging and publishes no partial submission.
An existing destination is never overwritten.

The program's input manifest and container/environment must still be frozen by
the existing executor. A successful local call is not a sandbox qualification.
The reference does not call the operator grader, read target traces, select a
method using target errors, or change the mouse-macro pooled-training-scale
NRMSE. The executor continues to close candidate resources before target access.

`test_reference.py` exercises generated three-pair/two-mouse data, varying source
trial counts and cell counts, an independent half-tick interpolation oracle,
actual inherited submission validation and scoring, isolated single-file ABI,
public-only reads, malformed identities, late nonfinite data, extra NPZ members,
oversized NPY headers, and complete-output failure. These are software controls;
their invented arrays are not a smaller benchmark cohort or neural evidence.
Run them only through the shared lightweight test pool in this construction.

The complete original `mainData1.mat` and `mainData2.mat` cohort, biological mouse
and registration identities, native clocks, whole-packet capacity, protected
native execution and independent empirical comparator qualification remain
unverified. No authentic preparation, model trial, new score, direct observation,
typed-viewer or case-adaptive tool-assisted condition is established here.
This directory adds one frozen-program reference component, not a new task or
a ready benchmark. All predecessor source, canonical task and contracts remain
unchanged. Source and contract pins are in `SOURCE_PINS.json`.
