# V1 presented-sentence evaluation

This component evaluates every test sentence and ordered input keystroke in an
independently frozen panel for `PAPER-ROOT-ADD-002`. It is an offline artifact
evaluator. It neither loads recordings nor executes a decoder, and it does not
establish an authentic full-cohort reproduction.

The implemented endpoint is
`pinned-v1-presented-sentence-export`: the presented sentence stored as `true` in
the original V1 export, compared with the neural prediction. The pinned author's
online training metric uses typed targets and different accumulation; it is a
different endpoint. V2 and final language-model rescoring are excluded.

## Source identity and metric

The exact official code revision is
[`5f9889621d0df391c5aab37c996683d308e6e926`](https://github.com/facebookresearch/brain2qwerty/tree/5f9889621d0df391c5aab37c996683d308e6e926).
The data revision is
[`88f9096c6ce3a3fb17cc7b8e3131ff7f96da5684`](https://huggingface.co/datasets/bcbl190626/SpanishBCBL/tree/88f9096c6ce3a3fb17cc7b8e3131ff7f96da5684).
[source_contract.json](source_contract.json) records the canonical task digest,
selected source inventory metadata, vocabulary, known MEG aliases, recording
identity rules and primary-source fingerprints.
[PROVENANCE.json](PROVENANCE.json) records endpoint distinctions and the source
path correction: the pinned loader is `studies/spanishbcbl.py` at the repository
root, rather than the stale V1-subdirectory locator retained in the task history.

For the
[pinned export script](https://github.com/facebookresearch/brain2qwerty/blob/5f9889621d0df391c5aab37c996683d308e6e926/brain2qwerty_v1/scripts/extract_predictions.py):

- CER is unit-cost Levenshtein distance over Python string codepoints divided by
  the number of reference codepoints.
- WER is unit-cost Levenshtein distance over `reference.split()` and
  `prediction.split()`, divided by the number of reference words. Python whitespace
  splitting discards empty tokens; case and punctuation remain part of words.
- Sentence rates are averaged within biological person, then person means receive
  equal weight. These are neither pooled edit counts nor an overall sentence mean.
- CER SEM is the sample standard deviation of person means divided by the square
  root of the number of grouped people. It is not a confidence interval or a
  qualification of the uncertainty estimator.

No case folding, accent replacement, punctuation removal, whitespace rewriting,
Unicode normalization, CTC blank removal, or repeated-class collapse is added.
References must already be at the pinned callback/export stage. Reapplying the
loader's text cleanup would change some strings and is not generally idempotent.
The mathematical metric can exceed one; it is never clipped.

An empty reference has undefined CER and WER; a nonempty whitespace-only reference
has defined CER and undefined WER. Every such case remains in the result.
The complete-panel headline for an affected metric is `null`, with support flags.
`summary.source_conditional_defined_support` separately reproduces the source's
NaN-skipping aggregation, with all omitted case/person counts and its original
SEM denominator. It must not be reported as a complete-panel headline.

## Assessment and candidate boundaries

The operator supplies the panel and its expected SHA-256 from an independent,
trusted assessment freeze. A digest computed from an untrusted replacement panel
does not establish authority. The panel contains private reference text and is
not a candidate packet. Its source paths, UIDs, keystroke onsets/counts and grouping
information need a separately reviewed exposure policy before anything is released.
Supplying onset boundaries/counts is part of the source offline condition.

The canonical task has not selected an authentic transcript population. Its 472
asset records and historical 731-file repository inventory are not sentence or
person counts. This evaluator checks complete coverage relative to the supplied
frozen panel; it cannot establish that the panel contains every authentic eligible
sentence. In particular, the pinned prediction callback writes rank-zero local
state without an all-rank gather. A callback file is not a complete-population
manifest and must not define its own expected test roster.

Panel top-level fields are exact:

```text
schema: "typing-v1-panel-v1"
task_id: "PAPER-ROOT-ADD-002"
metric_route: "pinned-v1-presented-sentence-export"
source: {code_commit, data_revision}             # exact revisions above
modality: "MEG" | "EEG"                         # one modality per panel
condition: {id, access_condition, split_kind, disjoint_units,
            calibration_sentence_limit_per_person, representation}
provenance: {panel_id, eligibility_manifest_sha256,
             preprocessing_manifest_sha256, grouping_manifest_sha256,
             training_or_checkpoint_manifest_sha256}
aliases: [{participant_id, person_id}, ...]
recordings: [{path, bytes, sha256}, ...]
cases: [{case_id, participant_id, session_id, sentence_uid,
         sentence_cluster_id, trial_id, split, source_path,
         reference_text, keystroke_ids}, ...]
```

These provenance hashes bind supplied declarations; their bodies are not fetched
or scientifically verified. `recordings` identifies the primary recordings with
selected cases, not a complete raw-input dependency closure. Paths and byte sizes
must match canonical task inventory metadata. Determinable participant/session/task
contradictions are rejected using pinned loader rules and revision directory names.
FIF continuation files cannot anchor cases. Payload hashes are declared, not read
or authenticated here. Log alignment, FIF continuation custody, EEG header links,
native eligibility and trigger checks remain separate requirements.

Each `trial_id` is an integer at least two. Source sentence UIDs must bind that
trial, study, raw recording participant, session and task. The source convention
allows an integer trial prefix or its `.0` spelling. `session_id` is the decimal
session number, such as `"1"`. Those trial-prefix spellings are one source trial,
so a panel cannot include both to duplicate its metric weight or change spelling
to evade a known corrupted-trial exclusion.
Ordered `keystroke_ids` must be the nonempty source
sequence `sentence_uid + "_button_1"`, `..._button_2`, and so on. Candidates must
return exactly the expected test-case roster and ordered keystroke identities;
omissions, extras, duplicates and reordering are errors.

Known MEG aliases are `S18 → S1`, `S14 → S4`, and `S10/S21 → S5`. They are checked
before grouping and scoring. EEG aliases are explicitly supplied, not inferred
from the `_S1_` session token in filenames. No cross-modality equivalence or fixed
19-person EEG population is inferred. Raw recording participant identity remains
distinct from biological-person identity.

## Original and prospective conditions

`access_condition` is exactly `paper_and_data` or `paper_data_official_code`.
This field records a declared condition; the scorer cannot prove what information
or tools a candidate used.

The `pinned-source-sentence-clusters` split has only
`disjoint_units: ["sentence_cluster"]`, zero added calibration, and representation
`per-keystroke-classes`. The original source partitions sentence clusters; repeated
people across partitions are legitimate. The scorer checks supplied cluster
disjointness, including that identical presented text cannot be hidden behind
different cluster IDs. It does not rerun TF-IDF clustering or authenticate
paraphrase groups, split ratios, ordering or the original random seed.

`prospective-declared` is a separately named condition. It may require additional
`person` or `person_session` disjointness and may select the `transcript`
representation. The latter admits variable-length predictions and is not claimed
to be the author's one-class-per-onset output route. Both representations retain
the same literal export metric and frozen 29-character output vocabulary.

`person_session` denotes the validated source acquisition identity
`(biological person, raw recording participant, source session number)`. Session
numbers restart under aliases: `S1/session 1` and `S18/session 1` are different
source acquisitions of one person. Blocks within one raw participant/session
remain grouped. Biological equivalence across differently labeled source sessions,
especially EEG aliases, still needs independent evidence; it is not inferred here.

Case splits are `train`, `validation`, `calibration` and `test`. Calibration is
model-accessible and belongs to the training partition for disjointness checks;
its sentence count per biological person must fit the explicit frozen budget.
A person/session-disjoint condition therefore cannot calibrate on its held-out
person/session. Target-person adaptation needs a distinct future condition and
must not be called strict person-held-out evaluation.

## Candidate format and command

Candidate documents contain only:

```text
schema: "typing-v1-predictions-v1"
task_id: "PAPER-ROOT-ADD-002"
metric_route: "pinned-v1-presented-sentence-export"
representation: "per-keystroke-classes" | "transcript"
predictions: [{case_id, keystroke_ids, class_ids}, ...]
          or [{case_id, keystroke_ids, text}, ...]
```

Representations must match the frozen condition. Class IDs are integers 0–28;
booleans, fractional values and unknown classes are refused. There is one class
per supplied onset in the original representation. Transcript mode accepts an
empty prediction (all deletions) but does not permit a different output alphabet.
The original export's permissive fallback for impossible class IDs is deliberately
replaced by an explicit input-domain error. No target or grouping fields belong
in candidate output.

From the repository root, with a real externally prepared panel and independently
obtained digest:

```sh
python3 -I -S -B benchmarks/paper/PAPER-ROOT-ADD-002/implementations/v1-transcript-evaluation-v1/evaluator.py \
  --panel /operator/frozen-panel.json --panel-sha256 "$TRUSTED_PANEL_SHA256" \
  --predictions /candidate/predictions.json --output /operator/new-result.json \
  --max-json-bytes 16777216 --max-codepoints 1000000 --max-edit-cells 100000000
```

These example resource bounds are operator-selected engineering limits, not
measured native-run requirements. Budget failure refuses the complete evaluation;
no case is silently truncated. JSON reads require regular files, reject final
symlinks, and are byte bounded; duplicate keys, nonfinite constants and malformed
candidate documents are rejected. Public candidate validation happens before the
private panel file is opened. Outputs are new files and never overwrite existing
files. Parent-directory ownership and hostile concurrent mutation remain operator
responsibilities; this CLI is not a protected execution sandbox.

Exit code 0 means the declared panel was scored; 2 means invalid candidate output;
3 means an operator/source/resource failure. Errors never print target text or
private file paths. Results omit reference and predicted strings but retain
case/person IDs, per-case edit counts, denominators and all support diagnostics.
Results are operator artifacts, not automatically safe public feedback.

## Validation and remaining work

The supported runtime is Python 3.11+ with the standard library on Linux or
macOS. File admission uses POSIX regular-file and nonblocking-open semantics;
Windows compatibility is not established.

```sh
python3 -I -S -B -m unittest discover -s tests/construction -p test_typing_v1.py -v
```

Generated controls use an independently implemented full-matrix edit-distance
oracle, hand-derived alias-weighted summaries and deliberately invalid population,
grouping, vocabulary and CLI inputs. They are software checks, not authentic
recording results.

The paper's final LM-assisted headline is outside this endpoint. Original source
and paper clustering descriptions also require reconciliation before numeric
reproduction. Authentic reference text/onset alignment, selected cohort and
preprocessing, code/data rights, matched neural reference competence, exposure
policy, protected execution and complete resource qualification remain unverified.
Every successful result retains explicit false flags for those scientific claims.
The recorded code/data terms are CC BY-NC 4.0; that metadata does not certify a
particular intended use. No model, raw recording or author scientific pipeline
was run to construct this component.
