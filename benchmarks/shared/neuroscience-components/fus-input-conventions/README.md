# FUS input conventions and complete directory census

This adds executable input-construction helpers for the registered FUS direction
task. It does **not** implement a native MAT loader, establish physical acquisition
intervals or qualify the benchmark. The existing scorer and all prior results are
unchanged. The biological support remains two animals, with 49 metadata records,
48 positive records and the zero-count L-S45-R1 row.

`source_conventions.py` interprets the author-documented behavior-clock strings
and the third simulation summaryResults.txt column, acq_timestamp
(`HH:MM:SS.FFF`), as exact integer milliseconds. The first two clock columns use
`HH-MM-SS.FFF` and are refused by this helper. Missing
values stay missing, malformed values are refused, and no midnight rollover,
clock synchronization, integration duration or latency is inferred. Its signed
format applies a minus to the whole magnitude; it is an independently authored
representation, not a bitwise copy of the MATLAB parser's negative-hour edge
behavior. Native `time_acq` arrays are not decoded by these functions.

The same module maps the eight-target RT grid labels to degrees. These are labels
1, 2, 3, 4, 6, 7, 8 and 9, with 5 reserved for the center. Labels 1 and 2 also occur
in a different two-target convention. A future adapter must therefore establish
eight-target mode and join labels to actual target coordinates before using this
map. No observed target or label array was inspected here.

`census_join.py` joins **both complete archive directories** to the exact public
`ROSTER.json` and `ASSETS.json` selections. It preserves every record, every
matching filename, all other MAT names and both schema-document names. It reports
missing/ambiguous forms without selecting a convenient replacement. Files with
the same session and another run are only candidates for investigating Run99;
they do not prove constituent identity or order. Raw, motion-corrected and RT
all-trial forms stay separate. No member bytes are loaded. Both original complete
directory results must remain retained; their canonical JSON hashes accompany
the derived census. The caller must attach each transport-observed strong ETag
to its complete directory result; the join checks its syntax and preserves it.
ETag syntax and content hashing alone do not authenticate the HTTP transport.

Run the generated controls from this directory:

```sh
python3 -B -m unittest test_source_conventions test_census_join
```

The controls use invented strings, labels and directory entries. They establish
software behavior, not real trial availability, decoding performance or a new
benchmark count.

The newly authenticated sources resolve several earlier uncertainties:

- All six selected PPC loader/time-helper bodies match their exact Git blob
  identities. The one-second difference between subsequent-run image and
  behavioral offsets is now a byte-authenticated static observation. Whether
  released inputs used that branch remains unknown.
- The [paper-cited release](https://zenodo.org/records/8414598) is v0.1.0 and the
  [dataset-linked release](https://zenodo.org/records/10229710) is v0.1.1. The two
  resolved Git revisions differ only in README content. GitHub tags and the
  publisher's archive references are joined; the software ZIPs themselves were
  not downloaded or checked against their archive checksums.
- The [RT repository](https://github.com/wsgriggs2/rt_fUS_BMI) ships a simulation
  predictor with acquisition socket code removed. Its simulator consumes already
  stored `dop`, `timestamps`, `time_acq`, `state_num`, `actual_labels` and
  `memory_length`. The loader also exposes `frame_num`, `behavior`, `UF` and
  `coreParams`. This establishes consumer fields, not their original writer.
- The training extractor selects the last three timestamped frames before
  `target_acquire`, then applies a rolling-buffer transform. It does not establish
  the V3 requirement that a complete acquisition lies wholly in each trial's
  memory interval. The upstream comment describing timestamps as cells also
  differs from the loader's numerical arithmetic; native types remain unverified.
- The exact upstream archive size is 34,253,258,547 bytes. The current archive is
  56,527,114,780 bytes. Metadata alone establishes neither directory membership
  nor original trial counts.

`SOURCE_TRACE.json` pins the sources and narrows the missing writer/clock and
trial-lineage questions. `DIRECTORY_SCHEMA_OPERATION.json` binds both archive
identities, the existing ZIP64 directory parser, complete-census requirements and
finite resource bounds for the next inquiry. Its provider transport needs a
reviewed Caltech-specific adaptation: the accepted Stroop transport is pinned to
a different provider and asset. Neither this package nor an available parser
silently authorizes an acquisition.

Each distinct archive HEAD request returned a signed redirect followed by 403.
The error bodies were not read, no ZIP bytes were requested, and no retry or
strong-ETag success is claimed. A future complete directory operation must obtain
and validate an exact 206 extent and a strong ETag **before reading its first
tail body**, then bind subsequent ranges to that entity. The small ZIP suffix may
include incidental compressed member bytes, as explicitly disclosed in that
operation; no neural member may be decoded. Both schema-document names and all
native forms remain unobserved until that operation succeeds.

The outstanding native bridge still needs original physical acquisition
start/end semantics, behavior-clock synchronization, per-trial interval joins,
Run99 provenance, and successful-only versus all-attempted RT count
reconciliation. No frame duration is derived from sampling rate, and the
published average delivery latency is not used as a correction.
