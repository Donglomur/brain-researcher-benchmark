# HIPPOTHETA-001: fixed-channel state-conditioning method control

This task measures how a declared locomotion restriction changes the descriptive
6–10 Hz spectral maximum of one recorded channel, relative to its mixed-session
spectrum. Either ordering, equal estimates and boundary maxima are valid results.
It is an **easy method control**, not an established hard task.

## Paper relationship

[Huszár et al. (2022)](https://doi.org/10.1038/s41593-022-01138-x),
*Preconfigured dynamics in the hippocampus are guided by embryonic birthdate and
rate of neurogenesis*, supplied the original recordings. The relevant anchors are
the Methods sections **Behavior**, **State scoring**, **Theta-cycle detection**
and **Spatial ratemap analyses**, not a numerical figure target. The paper recorded
position with camera/TTL alignment and discusses behavior-dependent analyses;
it used 6–12 Hz Chebyshev filtering/Hilbert cycles on anatomically selected LFP
channels. Its spatial-rate-map velocity method uses Kalman filtering and a
1.5 cm/s cutoff. None of those is this task's Gaussian-speed >5 cm/s,
fixed-column, 4-second Welch recipe. No figure/table, birthdate effect,
connectivity result or cohort statistic is claimed to be reproduced here.

## Original-source substrate and known limitations

[DANDI 000552, published version 0.230630.2304](https://doi.org/10.48324/dandi.000552/0.230630.2304),
CC-BY-4.0, supplies exactly two assets of subject `e15-13f1`, session `220117`:
raw-ecephys NWB and behavior+ecephys NWB, together 7,108,180,912 bytes. The public
source manifest pins asset IDs, full SHA256, sizes and immutable object versions.
The image build verifies full objects; the task runs offline. No synthetic main
input, mutable draft lookup, runtime stream or reference answers are installed.

The NWB electrodes and groups have location `unknown`. Column 0 / electrode 0 /
source channel name `1` is fixed **before any signal values were inspected**,
not chosen for its theta power. It is a recorded-channel analysis, not confirmed
CA1 or laminar localization. The study's CA1 implant description does not repair
missing per-electrode metadata.

The raw file's calendar/reference date is 2011-08-18; the behavior file's is
2022-01-17. We retain that discrepancy. The paired IDs, upstream
[Buzcode clock convention](https://github.com/buzsakilab/buzcode/wiki/Data-Formatting-Standards#behavior),
converter's original behavior timestamps and matching relative epoch durations
support an **inherited common-relative-clock assumption**, not independent TTL
verification. We do not shift one series by the calendar difference. Converter
notes describe calendar bugs, but the exact executed converter commit is not
embedded in these assets. The result is conditional on this timing assumption.

## Public estimator and verifier

`instruction.md` and `/app/method_contract.json` expose the fixed channel,
physical-unit scaling, original-timestamp Gaussian smoother, gap/invalid-position
rules, central derivative, strict speed threshold, conservative sample bounds,
complete-window selection, periodic-Hann density normalization and peak rule.
Neither smoothing nor spectral windows can bridge separate valid bouts.
The same channel and spectral estimator are used for the whole recording.

Source-bound tables carry every original behavior row, valid support block,
selected bout, contributing window and both complete spectra. The verifier
checks numerical values and their aggregation, not a spectral-shape correlation,
plausible frequency range, prose phrase, favorable difference or software-version
string. Genuine independently implemented output must pass; missing, fabricated,
rescaled, misaligned and internally inconsistent output must fail. All-or-nothing
grading is disclosed; there is no promised proportional partial credit.

The mixed-session spectrum includes whatever states and artifacts were recorded.
There is no sleep-state classification, artifact-removal inference or REM claim.
A band-restricted maximum is not by itself evidence of a physiological rhythm.
The channel, clock, smoothing and threshold choices define the estimand; they do
not establish state causality or a universal hippocampal frequency.

## Validation boundary

Earlier hidden-channel/state-direction/shape-based references and author-reported
rewards are historical, not evidence for this new contract. See `REPAIR_STATUS.md`
and the external execution receipt for measured validation on the actual local
commit. Mechanics fixtures are not biological data. No Sol/frontier calibration,
remote push, merge or data/image publication is part of this repair.
