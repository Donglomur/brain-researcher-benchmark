# Current-checkout source preparation

Use this additive preparer before the unchanged NEURAL081 source constructor.
The original release names 105 files in their historical repository locations.
After the repository reorganization, 102 exact bodies are at new locations and
three campaign helpers have changed. Passing the current checkout directly to
the old constructor therefore fails; this guide supplies the current two-step
route.

`prepare_sources.py` resolves only the fixed [SOURCE_MAP.json](SOURCE_MAP.json).
Its 102 relocated bodies must match the original release hashes. The three
[historical helpers](historical-tools/) are exact public bodies from commit
`eb485f29c88057864caeba1282ab38ee8218f6a9`, an ancestor of the public audit base
`68a9ae5c9bd927949fee99b1add5793f7e7d88b0`. Their original paths, Git blob IDs,
lengths and SHA-256 identities are recorded in the map. They are copied as source;
the preparer never invokes a campaign or substitutes current campaign code.

All original constructor, release, fragment and historical manifest files are
unchanged. The new map and preparer have their own
[current source descriptor](../../../../../../integrity/current-closures/relocation-neural081/SOURCE_PINS.json).
The preparer authenticates the released constructor bytes and reuses its bounded
file capture and publication functions. It compiles those verified bytes directly,
without loading cached bytecode, and does not call its scientific or metadata
operation entrypoints.

## 1. Prepare the exact prerequisite tree

From the repository root, choose a fresh absolute destination outside the checkout.
Its parent must already exist, with ordinary-directory custody. The preparer
refuses symlinks, hardlinked source files, missing or changed bodies, overlapping
roots, and an existing destination. It checks all 105 sources before creating
the destination and checks them again as they are copied.

```sh
PKG="$PWD/benchmarks/neural/NEURAL-081/implementations/neural-081/portable-v1"
PREPARED_SOURCE=/ABSOLUTE/fresh-neural081-prerequisites
PREPARATION_DEADLINE=$(python3 -I -S -c 'import time; print(time.monotonic() + 60)')
python3 -I -S -B "$PKG/source-resolution/prepare_sources.py" \
  --public-root "$PWD" --destination "$PREPARED_SOURCE" \
  --read-cap 16777216 --write-cap 4194304 --live-cap 16777216 \
  --deadline "$PREPARATION_DEADLINE"
```

Replace `/ABSOLUTE/...` before use. These example bounds cover this fixed public
source closure; they are not scientific-run budgets. The 105 required bodies total
1,970,112 bytes. Logical read accounting includes the preparer entry, authenticated
constructor bootstrap, map and release metadata, source preflight, copies and
published readbacks. Logical writes include the copied bodies and receipt, plus a
conservative 65,536-byte reservation for the terminal report. Managed buffer
accounting follows the released helpers; it is not an OS RSS, filesystem quota or
CPU limit. The deadline is a future absolute value of the host monotonic clock.

The prepared tree contains the 105 exact historical paths and a separate
`SOURCE_RESOLUTION.json` receipt. Require successful process exit and the matching
receipt; a partial directory or a receipt alone is not completed execution.
An interrupted or refused copy can leave its owned prefix. Do not reuse that
directory as a new preparation destination or silently delete evidence of failure.
No source archive or dataset is downloaded, and no profile, neural input, secret,
protected target or model is read by this operation.

## 2. Run the unchanged source constructor

Select an independently configured profile using [OPERATOR_RECORDS.md](../OPERATOR_RECORDS.md).
For source construction, its three late evidence slots may explicitly state
`{"disposition":"not_supplied"}`. This does not qualify an environment or study.
Choose an instance root distinct from the checkout and prepared source tree.

```sh
CONSTRUCTION_DEADLINE=$(python3 -I -S -c 'import time; print(time.monotonic() + 60)')
python3 -I -S -B "$PKG/release/neural081_instance.py" build \
  --release "$PKG/release/PORTABLE_RELEASE.json" \
  --release-bytes 54631 \
  --release-sha256 d6d3406ba2e0fce136fbe7d71bf76fd311915324eb031493a2d963184f2ae2ca \
  --public-root "$PREPARED_SOURCE" --root /ABSOLUTE/fresh-neural081-instance \
  --profile /ABSOLUTE/operator/profile.json \
  --profile-bytes EXACT_PROFILE_BYTES --profile-sha256 EXACT_PROFILE_SHA256 \
  --read-cap 33554432 --write-cap 33554432 --live-cap 33554432 \
  --deadline "$CONSTRUCTION_DEADLINE"
```

Replace the profile placeholders with the exact byte count and SHA-256 of the
actual file. This second operation has its own separately charged budgets. It
copies all 105 original bodies under the instance's `origin/`, installs the same
66 active source/context bodies, and creates the six instance-specific metadata
bodies for the 72-member source closure. All active source bytes and scientific
gates remain those of the unchanged release. The instance's installed source
closure does not depend on retaining the prepared tree after successful copying;
keep its preparation receipt as provenance under the operator's retention policy.

Subsequent metadata stages use the installed constructor as described in
[STAGES.md](../STAGES.md). Actual qualification, authentic inputs, numerical and
physical environments, protected custody and independent approval remain external
requirements. Neither preparation nor construction runs a model, executes a
scientific operation, creates passing qualification, or establishes paper results.

## Generated controls and rights

From the repository root:

```sh
python3 -I -S -B -m unittest discover -s tests/benchmarks \
  -p 'test_neural081_relocation.py' -v
```

The tests use public source and an invented profile with no supplied evidence.
They check exact preparation, the unchanged constructor, relocation, refusal and
continued lack of qualification. They do not validate authentic neuroscience data.

Repository-authored additions and the recovered public helpers retain the
[repository MIT license](../../../../../../../LICENSE). Existing source and
third-party attribution are preserved; see [RIGHTS.md](../RIGHTS.md). No private
authoring history or private operational receipts are included in this adapter.
