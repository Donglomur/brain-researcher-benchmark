# Findlay complete preparation source

This package provides the complete **13-table / 98-family** preparation for
`PAPER-CANDIDATE-FINDLAY-SHARP-WAVE-SLEEP`. It accepts the exact original local release or continues previously reviewed retained inputs,
computes complete family support, and writes **both** ordinary and regional
contrast reports. It does not fit models, score a participant submission, download
data, or establish a new benchmark. The full scientific endpoint remains
unqualified.

The numerical reconciler and continuation tail are unchanged from their
accepted implementations. The complete first-intake census now uses the same
ordinary policy while scanning every table, including the OFF-duration table. The ordinary report still covers all 344 measure rows,
29 contrast rows and 783 target positions, with the fixed 27-column float32/64
subtraction semantics and 13 declared exclusions. The 16 animals and 29 sessions
are distinct units. None of these counts is a new experimental result.

## What must be supplied separately

The public repository provides the complete software graph, its source manifest,
the request binder, and generated controls. It does **not** redistribute original
tables, private ledgers, identity policies, reference values or execution receipts.

An authorized operator needs:

1. The exact historical `INPUT_LEDGER.json` from an authorized benchmark
   operator. Reconstruct the other two exact inputs, `PUBLISHED_98_LEDGER.json`
   and the private identity-policy JSON, with the
   [metadata provisioning commands](metadata/README.md) using legitimate
   official source files and the publisher workbook, or obtain their accepted
   bodies from the operator. The immutable expected sizes
   and SHA256 digests are in
   [external_contract.py](../../authoring/delivery-20261105/common/remaining-builds-wave40/findlay-ordinary-contrast-integration-source-20261116-v1/external_contract.py).
   These are operator inputs, not candidate-visible materials. No alternate
   ledgers, renamed cohort, shortened scope or replacement policy are accepted.
2. For a **fresh first intake**, the exact 3,015,691-byte original release archive
   from the [frozen data DOI](https://doi.gin.g-node.org/10.12751/g-node.xzmv31/).
   The worker checks its fixed SHA256 before copying or extraction, validates all
   17 members and 13 footers, then constructs new complete receipts. No earlier
   failed run, old output root, HTTP receipt or cleanup graph is required.
   For **continuation only**, provide the already reviewed retained-input manifest
   (`findlay-census-continuation-inputs/v1`) and **all** files it pins: original
   archive, all 17 extracted members, the 13 complete table reports and their
   group parts, prior request/source-lock/HTTP/integrity/outcome receipts, and the
   independent review. The continuation checks the recorded prior refusal and
   closure; it does not fabricate an acquisition history. Arbitrary Parquet files
   cannot replace continuation provenance. The new first-intake path instead
   authenticates the complete original archive; it does not fabricate old receipts.
3. A concrete compatible runtime and its inventory. The inherited verifier
   requires CPython **3.11.6**, PyArrow **24.0.0**, and a complete pinned NumPy
   installation. It records the actual NumPy version and all selected package
   bodies. OS/system libraries and CPython base/stdlib remain trusted. Runtime
   availability and execution on another machine require separate verification.
4. A selected public source-adoption commit containing this software. Supply its
   actual 40-character commit, never private repository ancestry. The owner
   compares every selected software body with that commit before dispatch.

Keep the three private metadata files, original archive or prior material, and runtime inventory
outside the public checkout. The retained original root can be elsewhere on the
host; it must be canonical, unlinked and disjoint from new output. Do not rewrite
old receipt paths to pretend a copied archive has the same provenance. A moved
prior dataset requires a separately reviewed provenance migration.

The three metadata bodies remain external. Two now have deterministic exporters
that reproduce their exact existing bytes; one historical audit ledger remains
operator-supplied. [PROVISIONING.md](PROVISIONING.md) gives the original-data and
metadata prerequisites. The first-intake source works with those inputs without
our historical attempt. Source publication alone does not distribute a
data-complete benchmark.

## Bind and invoke the existing owner

From the public repository root, use an already provisioned compatible Python.
The runtime preparation command is an explicit separate operation: it inventories
software; the binder does not run it automatically.

```sh
FINDLAY_OWNER=authoring/delivery-20261105/common/remaining-builds-wave40/findlay-complete-census-continuation-source-20261115-v1/owner

python3 -I -B "$FINDLAY_OWNER/runtime_manifest.py" \
  --site-packages /absolute/runtime/site-packages \
  --output /absolute/private/runtime.json \
  --receipt /absolute/private/runtime-preparation.json
```

For a fresh first intake, select the original release, existing fixed private
grading metadata, and a fresh private binding directory. The
`artifacts-build` parent must already exist in the checkout. Use actual absolute
paths and the actual public commit in place of the illustrative arguments:

```sh
python3 -I -B components/findlay-complete-preparation/bind_request.py \
  --commit ACTUAL_PUBLIC_COMMIT \
  --input-ledger /absolute/private/INPUT_LEDGER.json \
  --published-families /absolute/private/PUBLISHED_98_LEDGER.json \
  --private-policy /absolute/private/PRIVATE_IDENTITY_POLICY.json \
  --original-archive /absolute/private/10.12751_g-node.xzmv31.zip \
  --runtime-manifest /absolute/private/runtime.json \
  --operation-output /absolute/public-checkout/artifacts-build/findlay-new-operation \
  --write-dir /absolute/private/fresh-binding-directory
```

For continuation, use `--prior-attempt /absolute/private/retained-inputs.json`
instead of `--original-archive`; the two arguments are mutually exclusive.

The binder authenticates all selected software and three external metadata
bodies, checks their full-scope schema and cohort joins, and writes a new
`source-lock.json` and `request.json`. Its stdout gives both exact SHA256
digests. It does not inspect arrays, start a worker, grant execution authority,
or qualify science. For a fresh archive it checks the ordinary file extent and
binds the fixed expected digest; the worker performs the complete body hash.
It refuses invented metadata and incomplete/changed inputs; exact metadata
reconstructed by the reviewed exporters is accepted under the same fixed pins.

Only after selecting the actual operation and its resources, invoke the existing
owner with those exact paths and emitted digests:

```sh
python3 -I -B "$FINDLAY_OWNER/run.py" \
  --request /absolute/private/fresh-binding-directory/request.json \
  --request-sha256 ACTUAL_EMITTED_REQUEST_SHA256 \
  --source-lock /absolute/private/fresh-binding-directory/source-lock.json \
  --source-lock-sha256 ACTUAL_EMITTED_SOURCE_LOCK_SHA256
```

The source graph contains 14 Python members. Only those software members must
exist in the selected Git commit. The three fixed private metadata bodies are
separately authenticated at owner and worker admission; they are never required
in Git. Absolute paths appear only in newly created private bindings and outputs.

The unchanged durable V4 process owner manages dispatch, deadlines and cleanup.
Its prospective envelope remains 180 seconds work plus 60 seconds recovery,
512 MiB planned host memory, 192 MiB runtime admission, 32 MiB application reads
and 40 MiB whole-operation retention. RSS is sampled, not a hard aggregate limit.
The request binder and runtime inventory are separate operations. POSIX and
macOS-style process-inspection assumptions remain inherited; source relocation
tests on Linux do not establish native execution compatibility there.

## Complete outputs and scientific limits

The owner retains refusal evidence and partial output. A successful preparation
status is `COMPLETE_INTAKE_CENSUS_WITH_GATES`; it still has
`scientific_qualification: false`. The fresh route constructs all 13 original table reports; continuation retains
and checks the existing 13 reports. Both account for all 98 family supports, the ordinary
`condition-reconstruction.private.json`, and the separate regional
`multicortical_condition-reconstruction.private.json`. These outputs contain
operator-only numerical/identity material and must stay outside candidate access.

Ordinary agreement on authentic inputs is not yet established by this public
source change. Regional iEta lineage and definitions, gamma/ripple model
semantics, complete cohort joins, 98-family numerical references and participant
evaluation remain unresolved. The finite Figure 2 result does not replace the
full contract. Processed exposed inputs do not establish raw-signal,
prospective-forecast, unseen-population, full-paper, LLM or SOTA results.

## Generated source controls

These commands use the standard library only. They do not need private assets,
NumPy, PyArrow, a runtime inventory or a native run:

```sh
python3 -I -S -B components/findlay-complete-preparation/test_portable.py
python3 -I -S -B components/findlay-complete-preparation/test_fresh_intake.py
python3 -I -S -B authoring/delivery-20261105/common/remaining-builds-wave40/findlay-ordinary-contrast-integration-source-20261116-v1/test_integration.py
```

The controls cover relocation to a path containing spaces, complete software
pins, metadata scope/identity barriers, invalid-input refusal before output,
and unchanged full ordinary reconciliation/both-report routing. All numerical
fixtures and test identities are **invented**. The 98-family composition fixture
tests routing and complete accounting, not biological eligibility. Shape-only
fixture validation is explicitly distinct from fixed-digest production
admission; every generated metadata body is rejected by production admission.
The fresh tests use a complete classic ZIP containing invented payloads, real
extraction/integrity code and explicitly mocked native/census seams. A separate
composition control uses all 13 tables and 98 invented family slots with the
actual ordinary reconciler. The production contract rejects every invented
archive. No native decoder, original dataset, actual historical receipt chain
or model is validated by CI.

Our software is distributed under [MIT](LICENSE). Original data, paper, upstream
analysis code and private metadata are not included; their separate permissions
and access requirements are unchanged. See [NOTICE.md](NOTICE.md).

