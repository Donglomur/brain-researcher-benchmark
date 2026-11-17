# Preserve spike-only maintenance trials

This replacement preparation module repairs trial retention in NEURAL-041's
existing held-patient working-memory load programme. It preserves the registered
source package, original load target, patient grouping, clinical review
requirements, equal 2.5-second windows and downstream scores.

The predecessor checks LFP time coverage whenever a session contains an LFP
object. That rejects a trial even when every LFP channel is artifact-excluded
for that trial and valid spikes remain. The task explicitly retains a trial
when either prospectively eligible modality remains. This version requires the
1000-sample LFP window only when that trial actually retains LFP channels. The
2.5-second spike interval must still end no later than probe onset. Retained
LFP still passes the unchanged 400-Hz coverage and alignment checks.

For a spike-only trial, the private chronology now leaves LFP indices, alignment
and rate null; its LFP row list is empty. The epoch still has the established
shape `(0, 1000)` for absent LFP, plus the retained region-indexed spike trains.
When a globally excluded trial also has no usable modalities, its original
clinical or artifact exclusion reason is preserved. Otherwise modality-empty
trials receive the existing explicit availability reason.

## Use and integration boundary

`preparation.py` is the full replacement module, with the same `run()` signature
as its predecessor. It imports the unchanged `core.py`, `schema.py` and `nwb.py`
from `../registered-runtime/runtime/source`; their hashes and the predecessor
hash are in `SOURCE_PINS.json`. In an independently selected preparation capsule,
place the unchanged dependency directory on the Python import path and load
this file by its explicit path. The caller must still provide the complete
authenticated roster, independently produced review, identity key and native
resource allowances required by `run()`.

The registered campaign continues to select its preserved predecessor. Enrolling
this replacement requires a separately reviewed source selection and renewed
runtime/operator pins. This component does not issue a profile, acquire a
cohort, assert an eligible patient count, or relax source authentication. No
canonical task, contract, public registry or existing source pin was edited.

## Software verification

`test_preparation.py` substitutes only the native NWB interface with generated
arrays. It exercises the real preparation loop, full clinical-review schema,
44-session/36-group closure, 6,160 source-row dispositions, ZIP serialization
and authenticated epoch readback. These are invented software-control shapes,
not observed scientific cohort counts. Most generated rows are explicitly
excluded so that retained output remains small.

The controls reproduce the original failure, retain spike-only trials, reject
short retained-LFP windows, retain volts conversion and spike boundary behavior,
handle a source without LFP, reject spike intervals extending past probe, and
preserve explicit exclusion reasons. Run through the shared reviewed two-slot
test pool using an existing Python 3.11+ environment with NumPy; the test command
inside that pool is `python test_preparation.py`. No HDF5 file, native scientific
preparation, fit, model call or historical target is used. Actual test outcomes
are recorded in `VERIFICATION.json` after execution.

The unchanged predecessor epoch reader uses NumPy's private
`numpy.lib.format._read_array_header` function. The first test attempt that
executed reached seven passing controls and two readback errors because the
Homebrew installation lacked that function. All nine controls then passed in
the existing benchmark build environment, without changing the tests or reader.
The successful environment versions are recorded in `VERIFICATION.json`;
compatibility with arbitrary NumPy versions is not established.

## Scientific scope and remaining gaps

Source semantics remain those documented for DANDI
[000673/0.240118.2135](https://dandiarchive.org/dandiset/000673/0.240118.2135),
the pinned [SBCAT author revision](https://github.com/rutishauserlab/SBCAT-release-NWB/tree/a25e8cc3f61630a428f190381745257d4506f148),
and the [source paper](https://doi.org/10.1038/s41586-024-07309-z).
No external source fetch was needed for this repair; these are the inherited
documentary pins, not a fresh source requalification.

Authentic roster/clinical decisions, upstream temporal support, full source
compatibility, actual preparation, isolated execution and baseline competence
remain unqualified. Programme code does not establish direct interpretation,
typed-viewer interpretation or held-query tool-assisted investigation; those
participant deliveries remain absent. This repair establishes no decoder
performance, PAC mechanism, clinical validity or new scientific result.
