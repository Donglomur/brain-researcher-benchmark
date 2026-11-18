# Raw-event evidence for the fixed NEURAL-098 analysis

The existing preparation requires an actual stimulus-offset sample and an
independent raw-to-epoch join. Its preparation notes correctly refuse to guess
whether marker96 or97 means stimulus offset. The official COGITATE data-release
documentation now supplies the missing semantic distinction: MEG96 marks the
stimulus-to-blank transition;97 marks the blank-to-jitter transition. The pinned
P04 extraction source uses97 as the end of the metadata segment, which does not
make97 the stimulus offset.

`raw_event_evidence.py` is a pure, task-specific parser for one operator-supplied
P04-style event list and its raw-run clock/extent. It selects observed96 markers,
checks their durations using the existing1.01-raw-sample tolerance, and retains
all1..80 onsets, all four source categories, actual97 markers, condition markers
and response255 events. It never computes an offset from the nominal duration.
Duplicate/missing96, unknown event codes, ambiguous conditions and invalid
clocks are refused. Recording-window gaps, button exclusions and next-stimulus
intrusion remain explicit; the parser never drops a convenient trial.

Time-window comparisons use relative raw sample differences divided by the raw
sampling frequency, matching the existing binding validator. Adding fractional
boundaries to a large absolute sample origin can round them away. Independent
review identified that issue in the initial parser; the correction applies to
button membership, raw-window coverage and next-onset intrusion together.
Generated large-origin/nonintegral-clock and exact-endpoint controls cover it.

This component does not read FIF files, infer a raw clock from a resampled epoch,
fit an analysis or alter the existing33-person,42-cell/24-contrast endpoint.
It does not replace the current preparation or shared source package. Its
output is deliberately **not** a complete `neural098-event-bindings-v1` record:
`selection_index` and `epoch_event_sample` remain null, and a final stimulus
without an observed next onset keeps that value null. A nominal end time or a
sentinel must not be substituted to make the old preparation accept it.

The required remaining producer must join the complete authentic per-run event
lists and raw headers to the actual retained `epochs.selection` and
`epochs.events`, including the exact run-concatenation/resampling history. P07
concatenates event arrays and metadata separately, so source row order alone is
not an authenticated join. A complete header/event export and known marker
semantics also do not measure physical display latency or establish that a
particular recording used this scheme. No protected cohort, phase list,
recording, analysis target or native scientific pipeline was read or executed.

Generated tests exercise96-versus97, missing/duplicate96, wrong raw clocks,
half-open button boundaries, category preservation, missing final onsets,
intrusion and unsupported metadata. They establish parser behavior only.
The package remains an unadopted source component; no scientific readiness,
native neural understanding, reproduction or improvement result is claimed.

Sources observed on2026-11-18:

- [Official COGITATE event documentation](https://cogitate-consortium.github.io/cogitate-data/03_cogdataset/#stimulus-presentation-end), the M-EEG trigger scheme and raw acquisition description. This is a live documentation observation, not a pinned raw capture.
- [P04 event extraction at the retained commit](https://raw.githubusercontent.com/Cogitate-consortium/cogitate-msp1/e60764df21ab63d39ffa726a0dd38c2b6f1e3e9a/coglib/meeg/preprocessing/P04_extract_events.py), especially source lines81–101 and133–166.
- [P07 epoch construction at the same commit](https://raw.githubusercontent.com/Cogitate-consortium/cogitate-msp1/e60764df21ab63d39ffa726a0dd38c2b6f1e3e9a/coglib/meeg/preprocessing/P07_make_epochs.py), especially source lines54–133 and173–198.

Only browser-rendered source text was inspected. The expected Git blob IDs in
the existing SOURCE_ORIGINS record were not authenticated by a new raw download.
This new benchmark implementation is distributed under the repository's
applicable license; no author source file was copied into it.
