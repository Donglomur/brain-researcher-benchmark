# Complete fly-group split compiler

This operator component turns the existing complete native descriptor map and
a separately reviewed biological-identity resolution into outer and inner
leave-one-fly-out partitions. Each genotype has its own folds. Every trial,
ROI and eventual episode from the same fly must inherit that fly's partition,
including files from different pulse, plume or control conditions.

The component closes a software gap between the 42-file inventory and the
registered grouped-evaluation design. **It does not resolve the biological
identities.** No authentic identity map is distributed or fabricated here,
and no actual split compilation, target production, model run, neural result
or benchmark readiness is claimed.

## Required operator operands

`--base-plan` is the complete descriptor map already required by the adjacent
`native-inspection` package: 3,419,523 bytes, SHA-256
`7eb06156b8ce98b9bb00f078ef64e8b57e99c5e1e234dc4c7222372a4d40b10c`.
The CLI authenticates this fixed identity before parsing. It never opens the
789 MB imaging archive, calibration recordings or numerical signal arrays.

`--identity-resolution` is an evaluator-private JSON document, authenticated
against an externally supplied SHA-256 digest. Its exact top-level fields are:

```json
{
  "schema": "fly-odor-identity-resolution/v1",
  "task_id": "NEURAL-SCOPE-20261114-FLY-ODOR-MEMORY",
  "base_plan_sha256": "7eb06156b8ce98b9bb00f078ef64e8b57e99c5e1e234dc4c7222372a4d40b10c",
  "identity_status": "reviewed_resolved",
  "identity_review_sha256": "<digest of independent identity review>",
  "files": [],
  "record_50_51_resolution": {
    "decision": "same_animal",
    "evidence_sha256": "<digest of the source-backed record-label resolution>",
    "record_50_members": [],
    "record_51_members": []
  }
}
```

The empty arrays and placeholder hashes illustrate the fields only; this is
not a valid or selected resolution. `files` must contain exactly one assignment
for every native archive member, with these exact fields:

- `archive_member_id` and `official_lookup_index`, joined to the descriptor;
- `source_population_label`, exactly preserving the source descriptor label;
- `fly_id`, the reviewed biological animal identity across all its files;
- `genotype`, either `VT062617` or `52G12`;
- `identity_evidence_sha256`, identifying evidence for the assignment.

The two record-label member arrays are nonempty, duplicate-free lists of
registered native members. They must each refer to one animal. The decision
may be `same_animal` or `different_animals` and must agree with the assignments.
Source record labels 50 and 51 are **not** interpreted as lookup-table indices.
Their relationship to native members is an explicit reviewed join. The two
arrays can overlap only consistently with a same-animal decision. No guess is
made from file names, integer labels or a desired fly count.

A digest establishes byte identity, not the correctness, independence or
chronology of an identity review. The operator must inspect the referenced
evidence and freeze the resolution before outcome-dependent selection. The
program validates declared relationships; it cannot authenticate biological
identity from a user-entered claim or arbitrary hash.

## What the compiler checks and emits

The descriptor must contain exactly 42 unique members and 1,345 trials, with
each file's full zero-based contiguous native trial order. The assignment
must cover that exact set. Unknown/duplicate members, unresolved identities,
source-label mismatches, one animal spanning genotypes or inconsistent
population-to-genotype mappings refuse the entire compilation. There must
be at least three reviewed flies per genotype to support a nonempty training
set in every inner validation fold. This is a construction requirement, not
a claim about the authentic resolved number of flies.

For each fly in each genotype, the outer test fold contains all its files;
outer training contains every other fly of the same genotype. Each outer
training fly then serves once as inner validation, with the remaining flies
as inner training. The outer test fly never enters inner selection. The two
genotypes are never pooled. No condition, episode, quality, future-reencounter
label or neural/behavioral value participates in partitioning.

The output preserves a complete file census with each file's trial interval
`[0, trial_count)`. No trial is excluded by this component. The eventual target
producer must bind every eligible and ineligible episode to its original
member and trial, preserve the full census, and inherit these partitions.
Creating correct file groups does not establish event eligibility, target
coverage, exact physical odor offsets or candidate-input isolation.

```sh
python3.11 -I -S -B compile_splits.py \
  --base-plan /private/complete-descriptor.json \
  --identity-resolution /private/reviewed-identities.json \
  --identity-resolution-sha256 FROZEN_IDENTITY_SHA256 \
  --output /private/new-grouped-splits.json
```

Only regular non-symlink inputs are accepted. JSON duplicate keys, nonfinite
constants, excessive input/output sizes and stale identities are rejected.
The result is created exclusively with mode 0600. No existing output is
overwritten. An I/O failure can leave a partial file; preserve the nonzero exit
status and do not use file existence as proof of completion. This is trusted
operator preparation, not same-user or operating-system isolation.

The parsed `compile_splits()` function assumes its caller has authenticated
both operands. Generated tests exercise that function with invented metadata.
They do not prove that generated records are the authentic descriptor map;
the production CLI separately refuses invented descriptor bytes.

## Checks and source lineage

Python 3.11 and its standard library suffice. The maintained test command is:

```sh
python3.11 -I -S -B test_compile_splits.py
```

The generated controls check complete outer/inner group support, permutation
invariance, explicit alias handling, incomplete file/trial rejection, identity
join failures, cross-genotype leakage rejection, insufficient-group refusal,
strict metadata input boundaries and private immutable output. They do not
read authentic arrays, run scientific models or measure participant ability.

The registered `task.json` and `understanding.v1.json` specify fly grouping,
separate genotypes and training-only model selection. Existing
`native-inspection/runtime/inspector/optional_inputs.py` binds the complete
descriptor and its 42-file/1,345-trial support. Its consumer and independent
auditor preserve `archive_member_id`, `official_lookup_index`,
`population_label`, `trial_count` and `trial_index_zero_based` as used here.
This package does not change those producers or the adjacent point scorer.
`SOURCE_MANIFEST.json` pins the exact source contracts inspected for this work.

The official [Zenodo release](https://zenodo.org/records/20053990) was visible
during construction and still lists the imaging, PID, readme and confocal
objects. That metadata is not an identity-resolution map. Attempts to inspect
the publisher page, PMC article and pinned GitHub tree were blocked by their
respective access/front-end responses; no new source facts were inferred
from those failed reads. The retained task's primary-source review is reused,
not represented as newly authenticated paper/code bodies.

Physical odor calibration, heading/speed units, animal identity evidence,
episode extraction, all-condition eligibility, competent reference models,
normalization sensitivity and paired animal-level inference remain separate
gates. Released all-trial fluorescence normalization still makes the endpoint
conditional and retrospective. Successful metadata compilation cannot turn
it into prospective causal forecasting or native neural understanding.
