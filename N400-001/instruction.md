# Target-word N400 amplitude in a fixed ERP CORE subset

Estimate the signed unrelated-minus-related target-word ERP amplitude at CPz,
300–500 ms, separately for subjects 1–12 and then average equally across subjects.

## Scientific scope

[ERP CORE (Kappenman et al., 2021)](https://doi.org/10.1016/j.neuroimage.2020.117465),
Figure 2 and Tables 1–2, motivates the contrast, CPz site and measurement window.
The published N400 characterization used 39 participants, ICA, artifact rejection,
and correctness/reaction-time exclusions. This task instead uses a fixed 12-person
subset, a specified FIR filter, and no such exclusions. It is an original-data
method control, **not a reproduction of the published cleaned amplitude**. Do not
infer a population effect, a precise onset, or artifact-free physiology from it.

## Offline data and public method

Original `<subject>_N400_shifted_ds.set` / `.fdt` pairs are in
`/app/data/erpcore_n400`. `data_manifest.json` identifies each OSF version-1 source
and its size, SHA256 and MD5. Verify these identities; no downloads or substitutes
are needed. The files already include the original stimulus-delay correction and
256 Hz downsampling. Do not apply either operation again.

`/app/method_contract.json` is the complete public numerical and output contract.
Follow that contract; equivalent numerical implementations are welcome. The
following points summarize its important choices:

- Retain every original event in a source ledger. Related **targets** are 211/212;
  unrelated targets are 221/222. Codes 111/112/121/122 are primes, and 201/202 are
  responses, not target stimuli. Correctness and reaction time do not select trials.
- Use CPz referenced to `(P9 + P10)/2`. Only these three channels are needed for
  this readout; identically filtering all EEG channels gives the same result.
- Use the explicit float64, zero-phase, 0.1–30 Hz Hamming FIR defined in the
  contract. Its 8,449 coefficients and segment-edge padding are public, including
  the construction formula. One centered FIR pass is not `filtfilt`. Do not add
  ICA, notch filtering, interpolation, clipping or amplitude-based rejection.
- Respect original discontinuities: independently filter each continuous segment
  and exclude target epochs crossing a segment boundary. A boundary's duration
  describes removed historical data, not an extra current interval to discard.
  Keep structural exclusions and their reasons in the trial ledger.
- Convert the original 1-based event latency to the nearest zero-based sample,
  ties to even. Do not silently merge target events with the same rounded sample.
  The nominal −200..800 ms epoch comprises offsets −51..205 inclusive at 256 Hz.
  Baseline offsets are −51..0; measurement offsets are 77..128, both inclusive.
  These correspond to actual epoch endpoints −199.21875/800.78125 ms and
  measurement endpoints 300.78125/500 ms.
- Subtract each trial's baseline mean, average trials equally within condition,
  and subtract related from unrelated. Preserve the sign. Average the 12 subject
  differences equally, not by trial count; do not force negative values.

## Required outputs

Write these eight files to `${OUTPUT_DIR}` (default `/app/output`). Exact columns,
null conventions, JSON fields and numerical tolerances are in the public contract.

| File | Required evidence |
| --- | --- |
| `source_events.csv` | Every source event, original index/type/latency/duration, role, sample and eligibility |
| `segments.csv` | Source segment bounds and actual filter padding |
| `trial_measurements.csv` | Every candidate target, retained/dropped status, baseline and signed window measurements |
| `curves.csv` | All 257 samples of each subject's related, unrelated and difference curves |
| `per_subject.csv` | Exact subject coverage, candidate/retained/dropped counts and signed condition/difference amplitudes |
| `n400.json` | Equal-subject headline, source support, contrast and measurement definition |
| `run_metadata.json` | Source hashes, public contract and observed source structure, software provenance |
| `findings.md` | A concise numerical summary and the interpretation limits of this adaptation |

Use the EEGLAB FDT microvolt storage convention; these headers contain no explicit
voltage-unit annotation. If a reader converts to volts, convert back once when
reporting. Missing measurements on structurally dropped trials are
blank, not zero, NaN or infinity. Every participant must retain at least one trial
in each target condition. Missing sources, unsupported structure, nonfinite signal
values or ambiguous target identity must fail explicitly, not yield fabricated
measurements. On failure write `status: failed_precondition` and a nonempty reason
in `run_metadata.json` and `n400.json`, plus a short `findings.md`, then exit nonzero.

The verifier checks original-source identity, all event/trial/curve/subject
measurements and their aggregation. There is no required sign, effect size,
prime-null result or pooled-halving relationship, and no prose keyword gate.
A prime-plus-target sensitivity analysis is optional and ungraded. Software
version strings are provenance, not a requirement to use one implementation.
Scoring is binary: all required checks pass for reward 1; otherwise reward 0.

## Attribution and access scope

Credit Emily Kappenman, Steven Luck and the ERP CORE contributors. The OSF N400
node currently reports CC-BY 4.0; the pinned author repository's `License.txt`
states CC-BY-SA 4.0. Both scoped notices are recorded in the source manifest; this
task does not claim that either supersedes the other or clear public redistribution.
