# Historical source blocker: retired rat source

This record concerns the retired source, not the active mouse methods case.
The user-approved replacement is documented in environment/SOURCE_NOTICE.md
and environment/methods.md. The old source diagnosis remains unchanged; no
claim is made that its missing independent tracking was recovered.

The exact public asset is DANDI `001754/0.260728.1352`, asset
`b8dbee0b-e84e-45f9-998d-39bee1803fc9`,
`sub-Rat1/sub-Rat1_ses-19980425T124500_behavior+ecephys.nwb`.
Published size: 8,880,640 bytes. Published SHA256:
`f35c398d7e266ed81a960e00e8fb623bc5992deaed6f70c85cee340f431b5950`.
Both match the original bytes inspected on 2026-10-01. License: CC-BY-4.0.

[Published asset metadata](https://api.dandiarchive.org/api/dandisets/001754/versions/0.260728.1352/assets/b8dbee0b-e84e-45f9-998d-39bee1803fc9/)

## Observed source facts

- The SpatialSeries describes positions sampled at spike occurrence times.
- All 191,065 position timestamps exactly match recorded spike timestamps.
  They are not the complete union: the units have 191,108 unique spike times.
- Only 22.718% of successive position intervals are 20 ms. The maximum gap is
  354.19 seconds. A median interval near 20 ms does not establish a 50 Hz clock.
- The 39 units contain 243,527 stored spikes; there is no unit-quality or
  cell-type annotation. A rate cutoff alone cannot certify pyramidal cells.
- The source is the Knierim, McNaughton & Poe spaceflight study
  ([2000, DOI 10.1038/72910](https://doi.org/10.1038/72910)), not the original
  Skaggs cohort. BL epochs are [4871,7535) and [9220,10151) seconds.
- Legacy 64-by-64 rate/occupancy maps are present, but they do not supply the
  independent time-resolved trajectory needed for this running/shuffle task.

Multiplying position-row counts by 0.02 seconds produces an ensemble-spike-
conditioned measure, not observed dwell time. Reweighting sparse rows by elapsed
time or interpolating them does not recover the missing independent behavior.
Shuffling against this same trace therefore cannot establish the advertised
finite-sample-bias correction.

NASA OSD-968 metadata describes cameras in the original experiment. Its complete
top-level inventory lists 27 files, without a separately identified continuous
tracking stream. Original FD9RAT1 ZIP (8,608,323 bytes) and processed archive
(272,289,499 bytes) remain uninspected: official download endpoints returned 403.
This is an access/provenance limit, **not evidence that tracking never existed**.

## Safe resolution

Recover independently sampled tracking with units/time alignment/provenance and
rebuild the declared estimator, or approve another public source with a complete
behavior trajectory while retaining an honestly labeled spatial-information
method case. Do not regenerate the former approximately 0.09-bit answer.

At the original quarantine, tests/reference.npz was untouched and stale and
the oracle failed before analysis. During the approved replacement, that bank
was copied and SHA-authenticated opaquely outside the task and retired from the
active verifier. The old guarded implementation remains recoverable in Git.

Local original-byte receipts (outside the task image):

- `/home/zijiaochen/projects/brain-researcher-benchmark-runs/20261001/pr147-source/source_verification.json`
- `/home/zijiaochen/projects/brain-researcher-benchmark-runs/20261001/pr147-source/nwb_structure_report.json`
- `/home/zijiaochen/projects/brain-researcher-benchmark-runs/20261001/pr147-source/nasa_metadata_inspection.json`
