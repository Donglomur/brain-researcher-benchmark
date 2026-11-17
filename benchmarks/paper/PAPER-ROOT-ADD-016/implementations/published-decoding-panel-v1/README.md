# Recover the original published ECG-decoding panel

This component imports the public Figure 3C,D author-result table for the
original 20-person simultaneous Salzburg M/EEG/ECG study. It closes the missing
published-score source component identified in the current improvement contract.
It preserves 120 scores: 20 released participant identifiers, EEG and MEG, and
`ECG_components`, `ECG_not_rejected`, and `ECG_rejected` separately. It does not
reuse the historical 655-person age/slope endpoint.

The original [OSF file](https://osf.io/download/fm5t8/?revision=1),
`dec_r_ecg.csv`, is 5,222 bytes with SHA-256
`97ce1f3546cbc7cf447cdc6efa785b87037853039d0df88bc4de62d475797368`.
The fresh download matches the earlier cached OSF metadata exactly.
[Source evidence](SOURCE_RECOVERY.json) records the version, source pins,
successful and failed acquisition costs, and remaining source joins.
Raw source tables and downloaded author code are retained outside this repository.

`published_panel.py` verifies the complete source fingerprint before parsing. It
rejects incomplete or duplicate participant/condition cells, changed released
identifiers, unknown modality/ICA labels, malformed rows, and nonfinite or
out-of-range Pearson correlations. It writes all six paired participant vectors
to a new external JSON file, together with a roster fingerprint and separate
arithmetic mean and sample SD for each cell. It cannot accept an altered candidate
table under the original source identity. The means and SD describe the published
scores; they do not reproduce the original plot's confidence intervals.

Use Python 3.11 or later with only its standard library:

```sh
python3 -I -S -B published_panel.py \
  --source /external/source/dec_r_ecg.csv \
  --out /external/evidence/published-panel.json
```

The output must remain in external evidence storage because it contains the full
author score vectors. Its keys retain the source's numeric string identifiers
`0` through `19`; these are released table IDs, not authenticated recording IDs.
The program never overwrites an existing output. No dependency installation,
recording read, decoder fitting, or author-model execution is needed.

The pinned author script extracts `.r` from each backward EEG/MEG model and names
its conditions `pure`, `present`, and `removed`. Their correspondence with the
released ICA labels follows the source definitions, but the inspected script
contains no CSV exporter or recording-to-release-ID map. Consequently, this
component recovers a published result panel without claiming that the full
data-to-code chain has been reproduced.

The cached author environment explicitly names Eelbrain 0.38, MNE 1.2.0, pandas
1.4.3, and seaborn 0.11.2. These are a documented environment candidate, not a
verified final execution environment. The paper's four-fold nested temporal CV,
100-Hz sampling, -250 to 250-ms integration window, 50-ms Hamming basis,
ECG-informed ICA, and all original conditions remain the required scientific
comparison. This importer neither constructs new folds nor averages folds or
modalities into a replacement metric.

Remaining work for either original-task reproduction or improvement is to
authenticate the original recording manifest and channel order, map released IDs
to recordings, recover the temporal partitions and exclusions, establish the
preprocessing information boundary, and run a checked author decoder. Source
preprocessing writes a plain participant filename while the TRF run block reads
a filter/threshold-suffixed filename; that source path join also needs recovery.
Improvement additionally needs frozen candidate predictions and a justified
paired participant-level decision across all six cells. Public score-table
recovery alone establishes neither reproduction nor improvement. Both outcomes
are first-class, separate outcomes under the latest research scope.

The 11 task-local generated controls exercise the complete panel and meaningful
failure cases. They contain no authentic scores. Run `test_published_panel.py -v`
through the shared lightweight test pool during the parallel build. Their pass
is software evidence, separate from authentic source import and scientific
qualification. No paired participant trial or candidate/model trial was run.

Integration proposal: bind this component as published-result source recovery;
replace only the current contract's claim that the exact published score vector
is unrecovered. Retain `source_unresolved` overall, keep the anonymous-ID and
exporter join explicit, and preserve all historical association implementations.
Canonical contracts, registration, shared catalogs, and workflow enrollment are
owned by integration and were not edited here.
