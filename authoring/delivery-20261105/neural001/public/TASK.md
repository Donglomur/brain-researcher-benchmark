# NEURAL-001: audiobook-to-sentence envelope reconstruction

Given one participant's MEG and labeled audiobook calibration, reconstruct the
speech-envelope samples for every separate OLSA sentence interval. The complete
benchmark contains all24 MEG-SCANS participants and120 sentence trials/person,
2880 nested observations. Repeated sentences, runs and windows are not independent
people. This package currently supplies a construction recipe; neural task packets
are absent. Do not substitute one available person or synthetic data for the cohort.

The source is ds006468 snapshot1.1.1, commit5c1d52d66c6bfe4c1c908d496df8a2ecbe3fece1.
Snapshot1.1.2 changes only descriptive metadata; its data/annex entries are identical.
Both are public development data and may be exposed to models.

Each participant is an isolated invocation. Receive only that participant's
`training.npz`, `queries.npz` and public manifest row (plus these instructions).
Training contains all available whole audiobook runs at the source-defined120s
preprocessing epochs, with matched speech envelopes and run IDs. Queries contain
only306 MEG channels, opaque interval IDs, offsets and channel order. No MISC audio
channels, target waveforms, sentence/text/playlist IDs, intelligibility, SNR, event
onset table, other participant's calibration or private stage files are supplied.
All70 OLSA sentence identities and repetitions remain outside labeled training.

Use arbitrary training-only numerical methods. Select parameters and estimate
normalization using whole audiobook-run folds; keep neighboring epochs from a run
together. Refit on all permitted audiobook calibration after selection. No query
batch statistics, query-label access or post-score tuning is allowed. Candidate
process control is needed to establish access; a prediction file alone cannot.

Signals use the original author preprocessing at code commit
32bfc690e28e7591b45d96615c59b2d53b6a7165: MaxFiltered continuous MEG, original
FieldTrip0.5–4Hz FIR filtering, +3 raw1000Hz samples for measured audio latency,
and64Hz resampling. Sentence intervals include source duration plus0.5s poststimulus;
the author preprocessing permits at most one-sample length mismatch, trimming both
signals to the shorter length. Every retained sample is scored. Do not add artificial
trailing zeros or trim predictions yourself. This is retrospective interval decoding;
continuous filtering and poststimulus access are declared, not causal forecasting.
The preparer does no model fitting or final normalization. Original pooled
normalization in `training_decoding.m` is deliberately not used.

For each invocation emit `<participant>.npz` containing exactly:
- `prediction`: finite little-endian float64, shape(total_query_samples,).
- `interval_ids`: little-endian Unicode32, shape(120,), exact supplied order.
- `offsets`: little-endian int64, shape(121,), exact supplied boundaries.

Use ordinary NPY1 entries in a stored/deflated NPZ, C order, at most1048576bytes.
No missing trial, duplicate ID, additional array, link, NaN or infinite value is
valid. Whole-study scoring requires exactly24 files, sub-01.npz through sub-24.npz.
Every candidate file validates before any private target is loaded. No partial
coverage average is reported. Constant predictions remain valid and receive zero
correlation for that interval, with the convention explicitly flagged.

Primary: Spearman correlation per complete sentence (average ranks for ties),
Fisher transform each coefficient, mean equally over120 sentences within person,
then mean equally over24 people. Report raw sentence/person Spearman and Pearson
alongside the primary. This is a newly specified benchmark estimator, not the
paper's original padded/pooled reproduction. Positive and negative coefficients
remain signed. Only for finite Fisher transformation, exact±1 is bounded by
±nextafter(1,0); raw correlations remain±1. Constant private targets invalidate the
operator packet; they are never silently dropped. There is no significance threshold
or success reward. Uncertainty needs participant clustering and shared-stimulus
accounting; no naive sample-level confidence interval is supplied.

Provisional evaluation envelope, fixed before model outcomes: one Python program
≤65536bytes per invocation,1200s,4CPU,16GiB, no network; fresh state per person.
Frozen-program and case-adaptive modes receive exactly the same files and budget.
This envelope has not been measured or runtime-qualified. Later baseline studies
must include a training-only neural decoder, a no-neural audiobook prior, and a
predeclared within-run shifted-neural control under matched access. No reference
performance, SOTA claim or proof of neural understanding exists for this package.
