# Frozen raster run entrypoint

This package connects the existing operator APIs into four executable commands:
prepare the complete private Reference, freeze a run plan, collect every original
case through the reviewed PNG participant transport, and separately grade the
protected complete output. The new prepare route uses the accepted exact-byte
rolling helper after the existing source census and coordinate/policy validation.
No authentic execution, acquisition, trained comparator, model client or access
admission is supplied by this source package.

The selected task is unchanged: all 79 infants, the original complete case order,
30-second causal windows with all 18 channels, one probability for the final
second, and infant-macro Brier loss against the three-expert seizure-report fraction.
The existing Reference, packet constructor, viewer, collector, transport and
evaluator are reused with exact source pins. There is no replacement scorer,
new cohort or new endpoint.

## Dependency state

`DEPENDENCIES.json` gives the exact supplemental join: the four original viewer
files selected by G1, four reviewed collector files, six final reviewed transport
files, and the unchanged existing source loader/protocol/scorer bodies. These
private source selections are **not a claim that the components are published,
installed or runtime-admitted**. The sole integrator must compose the exact files,
check current preimages and enroll the component checks on the actual target.

The collection path is entrypoint → final transport → collector → original viewer
→ original protocol. The future authentic CLI uses the existing lazy `SourceCorpus`
and its source-pinned predecessor intake; it does not use the historical controller
or historical alternative split. The separate scoring command loads the unchanged
evaluator only after complete-output admission. Test helper files are labelled
separately in the dependency map.

## External prerequisites

Before freeze/collect/score, provision a prepared current-protocol private Reference
and its case key, plus the complete authentic source in protected owner storage.
The prepare command constructs that document only from operator-provisioned full
source, a prospectively frozen preparation policy and private case key. Their
preparation, calibration, expert alignment, quality flags and lineage must already
be qualified independently. The reference hash binds those values; it does not
prove that they originated from the authenticated source. Authentic EEG, reference
and schedule admission are not supplied by generated fixtures or a shaped hash.

The participant executable/adapter, actual model/provider identity, immutable
artifacts, fresh provider context and filesystem/network containment also remain
external. The plan explicitly carries these outstanding prerequisites; it is not
an admission token or new issuer. File hashes are checked before collection and
each case, but do not lock files against mutation between checking and execution.
Use independently protected immutable deployment. Same-user filesystem/process
access and remote-provider memory are not isolated by this package.

The complete Reference is assessor-owned and contains labels. Restoring it during
collection is not a claim that the owner never accesses gold: metric execution and
score release are deferred until the separate protected grading step. Neither the
Reference, key, raw packet, complete schedule nor score report enters the participant
wire. Reports include private infant identities and must remain operator-private.

## Operator commands

Use these only after the exact operation and resources are separately admitted.
The following names stand for operator-provisioned private files and directories.

The participant specification has exactly `argv`, `artifacts`, `limits` and
`max_document_bytes`. `argv[0]` is an absolute executable path. Every absolute
argument must be listed in `artifacts` as an absolute `path` with its exact `sha256`;
the executable itself is required. Include one literal `{task_instructions}`
argument for the pinned public `PARTICIPANT.md` path. The participant adapter must
consume those instructions; passing the path does not prove model comprehension.
Arguments, artifacts, instructions, transport limits and the complete prepared
reference/schedule identities are frozen before collection.

`limits` has the existing six transport fields: `wall_seconds`, `max_actions`,
`max_action_bytes`, `max_stdout_bytes`, `max_response_bytes`, `max_wire_bytes`.
`max_document_bytes` and each CLI `--read-limit` are explicit positive bounds of at
most 1 GiB. They bound individual serialized documents or artifacts, not total
campaign work or process-tree memory. Authentic resource feasibility remains
unmeasured; a bound failure never authorizes fewer cases or signal downsampling.

```sh
python3 run.py prepare --source-root /private/helsinki-v4 --policy /private/preparation-policy.json \
  --policy-sha256 PROTECTED_POLICY_DIGEST --case-key /private/case.key \
  --read-limit 67108864 --output /private/new-reference.json

python3 run.py freeze --reference /private/reference.json --case-key /private/case.key \
  --participant-spec /private/participant.json --read-limit 67108864 --output /private/new-plan.json

python3 run.py collect --reference /private/reference.json --case-key /private/case.key \
  --plan /private/new-plan.json --plan-sha256 PROTECTED_PLAN_DIGEST --read-limit 67108864 \
  --source-root /private/helsinki-v4 --scratch-root /private/participant-scratch \
  --output /private/new-run-directory

python3 run.py score --reference /private/reference.json --case-key /private/case.key \
  --plan /private/new-plan.json --plan-sha256 PROTECTED_PLAN_DIGEST --read-limit 67108864 \
  --collection /private/new-run-directory/collection.json \
  --completion /private/new-run-directory/COMPLETED.json \
  --completion-sha256 PROTECTED_COMPLETION_DIGEST --output /private/new-score.json
```

The illustrative 64 MiB limit is not a measured authentic-corpus budget. The
operator must select admitted bounds sufficient for the complete original support.
The `freeze` command prints its canonical plan digest. `collect` returns zero only
after writing the complete collection and completion seal. In the trusted operator
environment, protect `digest(read_json(completion_path, admitted_limit))` from this
module before releasing labels to any evaluation operation. These are canonical
JSON digests, not `sha256sum` of the newline-terminated files. Do not accept an
edited document together with an untrusted newly recomputed expected digest.

All output paths must be new. Run directories are created with mode 0700 and
documents with mode 0600. No whole packet bank is written: packets are produced
lazily in the original private Reference order and only the current packet reaches
the trusted transport. The transport sends its existing PNG/metadata schemas.

Any missing, extra, reordered, changed or failed case prevents a complete output.
The collector commits the first final answer only after its reviewed participant
lifecycle succeeds. A failed run is not resumed, silently retried or scored on a
subset. The CLI preserves `FAILED.json`; caught persistence failures remove any
success seal created by this invocation. A partial `collection.json` without a
protected successful completion seal is ineligible. The score CLI requires the
paired filenames in one directory, rejects `FAILED.json`, rechecks all reference/
schedule/output identities, and invokes the unchanged complete-support evaluator.
Filesystem crash durability and externally protected custody still need admission.

## Focused generated evidence

Eleven new maintained controls cover frozen inputs, drift before launch, original
order/completeness, lazy failure, separate protected grading, private output limits,
strict JSON and failed-write handling. One actual new process consumed the pinned
instructions and one real generated PNG through the final transport; the generated
reader then deliberately stopped, and no complete run output was returned.

Complete dispatcher/score arithmetic uses a clearly labelled in-memory metadata
executor stub on the existing 79-invented-infant/80-case fixture. It is not a new
80-case participant campaign, reference result or model performance claim. The
unchanged scorer returns the fixture's known `1/144` Brier value.

The first 11-method run passed. Independent review found that test discovery order
could populate a cached result before the evaluator-deferral spy. The corrected
method now performs fresh metadata-only collection inside the spy and passed its
single affected rerun. Original test bytes and both runs are retained. Runtime
source did not change during that correction. No old suite or 80-case process
campaign was replayed; no authentic EDF/annotation or provider was executed.

Proposed CI command after exact dependency composition:

```sh
python3 -B -m unittest discover -s benchmarks/neural/NEURAL-EXP-005/implementations/raster-run-entrypoint-v1 -p 'test_run.py' -v
```

`HELSINKI_RUN_ENTRYPOINT_SCRATCH_ROOT` optionally places generated temporary files
in an operator-selected directory; `HELSINKI_RUN_ENTRYPOINT_PROOF_PATH` optionally
writes a new bounded engineering receipt. These test options do not change the
public runtime or supply authentic inputs. No benchmark count, native-understanding
claim, access status, scientific qualification or submission readiness is promoted.

## Complete Reference preparation route

`PREPARATION_BINDINGS.json` supplements the retained dependency map with the exact
immutable rolling helper and coordinate loader. The helper is a separately
reviewed private source selection; it is not already installed or activated.
The original source adapter/protocol/helper are unchanged. The new command passes
`corpus.sources.current`, the actual module associated with the admitted reader,
so eligible sources reach the helper's rolling path. Unsupported readers retain
its unchanged generic fallback. It does not reduce the original 79-infant support,
replace source lineage, omit any payload bytes or change packet/reference hashes,
case IDs, labels, folds, order or scoring. The implementation pin for `run.py` is
new, so previously frozen run plans cannot be silently relabelled as plans for
this new implementation. Preparation implementation pins are reported separately;
they are not inserted into the frozen scientific representation or Reference.

`--policy-sha256` is the protected canonical JSON digest from `digest(policy)`, not
the hash of a newline-terminated file. The policy is the existing
`helsinki-source-preparation-policy-v1` with assessment_id, fold_seed and
prospective development_by_fold. All 82 original assets must pass existing
SourceCorpus admission. Existing current_description then checks the complete
census, exact coordinate binding and prospective policy before hashing. The
corrected three expert streams, source flags and full participant-payload hashes
remain unchanged. No key, training membership, fit recipe or authenticated source
is generated by this command.

The output is private complete Reference JSON with labels, created exclusively
at a new path with mode0600. A caught write/flush/fsync failure attempts cleanup
only when the current ordinary file has the same device/inode created by this
invocation. Preexisting or already replaced paths are not removed. Cleanup failure
preserves the original exception and produces no successful preparation receipt;
operators must treat any leftover artifact as unqualified. This assumes a trusted
private output directory and is not hostile-filesystem isolation or atomic rename.
The existing freeze/collect/score writers and commands are unchanged.

Only the five new changed-entrypoint controls were executed for this successor:

```sh
python3 -I -S -B benchmarks/neural/NEURAL-EXP-005/implementations/raster-run-entrypoint-v1/test_prepare.py
```

The generated command reached `pinned_source_rolling` and matched all54,266 bytes
of the original canonical Reference, all80 case bindings, the complete schedule
and five partitions; the unsupported reader reached `unchanged_generic` with the
same result. Generated source admission/census/description were explicit stubs;
the actual nested coordinate-binding refusal was checked separately. The full
generated Reference was captured in memory at the writer boundary. Tiny generated
files exercised persistence failures and replacement ownership. No authentic
admission or full-source preparation was performed, and no old16 helper controls
or participant campaign were replayed. This is engineering equivalence evidence,
not a speed claim or scientific result. Public composed-tree CI remains pending;
private verification used only a pinned test-side locator for the unadopted helper.
