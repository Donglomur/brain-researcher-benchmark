# Original material identity audit and content joins

This source component advances the original NEURAL-085 recorded NR-versus-TSR
condition task. It authenticates all fourteen original ZuCo2 material files,
retains every source record, and supplies an exact ordered join for a future
complete source-content census. It does not change the task, metric, cohort,
held-person/held-item split, historical source, or registered scoring bridge.

The earlier material loader discarded the first three records of each block
before its exact-text census. That disposition was explicitly pending a MAT
content join. Here, those 42 records remain visible. `legacy_prefix` describes
that earlier positional rule; it is **not** an independently established
practice label.

## Source evidence and interpretation

`pinned_materials.json` records the size, SHA-256, OSF URL and original version
of every file. These identities were checked against the retained original
OSF materials listing and all fourteen cached bodies. No new download was
made. The source is [original ZuCo 2.0](https://osf.io/2urht/), distinct from
the later ZuCo benchmark archive; the source paper is
[Hollenstein et al. (2020)](https://aclanthology.org/2020.lrec-1.18/).

The authenticated files contain 781 material records: 370 NR and 411 TSR.
Using the predecessor's permissive Python CSV interpretation gives:

| Material scope | Shared exact texts | NR shared occurrences | TSR shared occurrences |
| --- | ---: | ---: | ---: |
| Every original material row | 61 | 63 | 64 |
| After the legacy three-per-block removal | 56 | 58 | 58 |

The all-material NR occurrence count happens to equal the paper's reported
63 duplicates. This is a numerical correspondence, **not a reconciliation of
the paper's 63 obligations**, a count of distinct paired items, or evidence
that any prefix was recorded. The recorded matched item set J remains
unqualified.

The source includes quotation syntax that a strict CSV reader rejects.
Therefore the audit preserves both the legacy permissive CSV interpretation
and an explicitly literal source-line interpretation. The latter splits the
two initial source identifiers and final annotation from the sentence, keeping
sentence quotes and embedded semicolons. It is a syntax diagnostic, not a
claim about the presentation application's parser. Both interpretations are
reported; neither is automatically promoted to the recorded text. The literal
interpretation yields 38 shared exact all-material texts and 33 after the
legacy prefix removal, showing why syntax must be resolved by original
recording content rather than selected to obtain a desired count.

Exact identity uses the contract's NFKC normalization and whitespace collapse.
Case and punctuation are retained. Conservative case/punctuation groups are
reported separately and never define J. Repeated source records keep separate
identities. Source text, parsed fields and per-record IDs stay in the private
operator output, outside the repository.

## Operator use

Use the existing environment; only Python's standard library is required.
During the parallel construction wave, run every invocation through the
shared test pool under its resource policy.

```sh
python -I -B materials_join.py \
  --source /operator/original-material-cache \
  --output /operator/fresh-material-audit
```

The output directory must be fresh and outside the repository. The command
authenticates all fourteen files before writing `material_rows.json` and
`material_audit.json`; it does not open physiological recordings. The public
audit contains counts and source hashes, while the rows contain original
stimuli and must remain operator-owned.

An independently prepared content-only metadata census may be supplied with
`--presentation-content`. Its schema is:

```json
{
  "schema": "zuco2-presentation-content-v1",
  "containers": [
    {
      "person": "YAC",
      "condition": "NR",
      "source_bytes": 123,
      "source_sha256": "64 lowercase hexadecimal characters",
      "presentations": [{"source_index": 0, "text": "original content"}]
    }
  ]
}
```

The abbreviated example is not admissible data. Actual input must contain all
36 containers for the original 18 people, all 349 NR and 390 TSR presentations
per person, and ordered complete zero-based source indices. Extra fields,
missing/duplicate containers and cross-person text disagreements are refused.

Each condition's ordered material sequence is joined to the ordered recording
content through exact subsequence alignment. A unique join returns original
source-record IDs and every unobserved material row. Zero or multiple possible
joins return explicit dispositions without a guessed identity. Identical
repeats are separate positions: a first-match heuristic is not used. Both
quote interpretations are evaluated separately.

Content joins carry the metadata file hash and supplied original container
pins. They cannot verify the upstream MAT extraction's custody by themselves.
Neither a unique join nor the computed observed shared set automatically
qualifies the primary endpoint or reconciles the paper's duplicate obligations.

## Validation and remaining limits

`test_materials_join.py` uses generated fixtures. It checks all 781 records,
prefix preservation, quote sensitivity, authentication failures, missing pins,
symlink refusal, exact normalization, 945 independent exhaustive alignment
comparisons, and the complete generated 36-container/13,302-presentation
metadata join. It also rejects incomplete cohorts, duplicate containers,
cross-person disagreements and unexpected label fields.

The authenticated run reads public stimulus metadata only. No EEG/gaze array,
historical solver target, private answer, candidate prediction or model is
used. Full original MAT/event joins, exact representation units and native
operators, split/campaign qualification, the paper's 63-obligation provenance,
and fixed-reference execution remain unresolved. Native/direct interpretation,
typed-viewer delivery, adaptive investigation and frozen-program performance
remain separate outcomes; this preparation component establishes none of
those performance results. Fixed chronology still prevents a causal
reading-demand interpretation.
