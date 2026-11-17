# REP012 portable paired API

This package supplies the source closure for the existing PAPER-FIND-REP-012 finite task. It preserves all 1,143 released Early-control rows and the four pooled associations: apical_local, basal_local, apical_coincident and basal_coincident. Sixteen numerical fields, 24 support fields and five cohort fields retain their existing grader and tolerances. It adds no benchmark ID and is not a new scientific result.

The paired API accepts arbitrary terminal/Python analyses in two isolated conditions. A has nine files; B has the same nine plus eight official source/support files. Both conditions receive the paper main text, processed data, complete method assumptions and identical tools. Supplementary Methods remain absent. This is explicitly method-assisted main-text reconstruction, not complete paper access or unaided recovery of the authors' methods.

## Authenticate the source

Use an ordinary unlinked source directory and Python 3.11 or later. No scientific library is imported by the host bootstrap. Obtain the exact release SHA256 of SOURCE_MANIFEST.json from the reviewed release handoff; do not silently replace it with a hash calculated from unexpected local files.

```sh
python3.11 -I -S -B /absolute/package/bootstrap.py --manifest-sha256 RELEASE_SHA256 check
```

For a literal authenticated API bootstrap, replace the two operator placeholders
below with your source directory and externally selected manifest hash:

```sh
python3.11 -I -S -B - /absolute/package RELEASE_SHA256 <<'REP012_SOURCE'
import hashlib, sys, types
from pathlib import Path
path = Path(sys.argv[1]).absolute() / 'bootstrap.py'
with path.open('rb') as stream:
    body = stream.read(7365)
if len(body) != 7364 or hashlib.sha256(body).hexdigest() != 'd880eefa6b96200b43de1744fe528090829160e5c43ca8a1bd30247dbab34128':
    raise SystemExit('Unrecognized bootstrap source')
bootstrap = types.ModuleType('rep012_authenticated_bootstrap')
bootstrap.__file__ = str(path)
exec(compile(body, str(path), 'exec'), bootstrap.__dict__)
api = bootstrap.load(sys.argv[2])
print('Authenticated paired API; no runtime or packet read')
# Supply api only to the separately admitted existing owner integration.
REP012_SOURCE
```

The check authenticates every selected source member and refuses extra files, links and changed bytes. It does not read packets, probe Docker or grant execution. Keep data, output, private reference and current operator evidence outside this source directory.

## External objects and current admission

EXTERNAL_OPERANDS.json is an inert complete operand map. Supply the exact accepted packet tree under an operator-controlled repository at:

```text
REPOSITORY/artifacts-build/rep012-matched-paper-packets-001/A/{public,task}
REPOSITORY/artifacts-build/rep012-matched-paper-packets-001/B/{public,task}
```

PACKET_BINDING.json authenticates all 26 physical files: A9 totals 425,420 bytes; B17 totals 572,721 bytes. Keep ordinary distinct single-link files at mode0444 and directories at mode0555. Original bodies are not distributed here. Provision only where you have the required local-use rights; packet copies must preserve exact content and permissions. Missing objects do not authorize a different dataset or smaller cohort. The private 1,976-byte reference is a separate operator-only object with the exact hash in EXTERNAL_OPERANDS.json. Its path must be a canonical absolute spelling without parent segments or redundant separators. Noncanonical operands are refused before loading the scorer facade; the deferred read still enforces the fixed reference hash.

This API targets the already accepted explicit shared-runtime successor, image sha256:9aaf44dc64d85d0bbb0ffdd75ff5190ad94eff91d76849d14aea859c930955ff, Linux ARM64, Python3.12.8/NumPy2.2.6/SciPy1.15.3. It has exactly two read-only, nonrecursive packet mounts and no host software bind. PUBLIC_RUNTIME_CONTRACT.json must be shown in both candidate contexts before the first interaction; it explicitly supersedes only the old runtime layout in the unchanged packet contract.

The older image385454 generic single-program route is a different historical interface. Its old controls are not qualification of this paired route. Likewise run_oracle_pair.py is a fixed-reference construction driver used by a separately pinned request; it does not measure a participant or the benefit of official code. The current package includes its unchanged bounded stage_commands helper for opaque program staging, without the original reference program or request.

Before using the API, the existing outer owner must separately admit the current host/interpreter, exact image, Docker binary/config/socket/Engine, source graph, exclusive execution window, capacity, whole resource allocation, interruption/recovery and all current closed-cost history. No live/current qualification or image distribution is supplied here. The old native request contains stale physical identities and resource bookings and must not be replayed. Configured VM memory and actual RSS are different; no historical4GiB planning allowance is a measured VM maximum.

## Existing paired API

The following is an operator integration recipe inside the already admitted bounded owner. It is not a new controller or an independently admitted command. First authenticate bootstrap.py itself through the release manifest or trusted release mechanism; then import it by its absolute source path under isolated Python and call load(RELEASE_SHA256). Importing sources launches nothing.

```python
api = bootstrap.load(RELEASE_SHA256)
c = api.controller

# Read both externally committed program bodies before either candidate session.
# Each descriptor is an exact {"bytes": ..., "sha256": ...} operator selection.
programs = {
    arm: c.captured(program_paths[arm], 262144, program_pins[arm])
    for arm in ("A", "B")
}
pair = c.PairController(
    repository, api.packet_binding, fresh_output_root,
    admitted_docker_binary, private_docker_config, admitted_docker_socket, fresh_nonce
)
pair.budget.write(
    pair.root / "PROGRAM_SOURCE_BINDINGS.json",
    c.encode({"programs": program_pins, "role": "arbitrary committed submitted programs"})
)
try:
    for arm in ("A", "B"):
        condition = pair.begin(arm)
        # Give condition.runtime_invocation to this arm's fresh candidate context.
        pair.budget.write(condition.folder / "RUNTIME_INVOCATION.json",
                          c.encode(condition.runtime_invocation))
        for command in api.staging.stage_commands(programs[arm], c.PYTHON):
            response = condition.call("terminal", command)
            c.need(response["returncode"] == 0, "program staging completed")
        response = condition.call("python", "/scratch/run_oracle.py")
        c.need(response["returncode"] == 0, "submitted program completed")
        condition.freeze()
    barrier = pair.finish()
except BaseException as error:
    for condition in pair.conditions.values():
        if not condition.closed and condition.cid is not None:
            condition.failure("participant integration", error)
    raise
```

The staging filenames retain the existing helper's oracle.py/run_oracle.py names; the bytes are the selected arbitrary program, not an implied oracle. The program interface is --input /public --output /output/result.json. Both programs must be committed before either runs. A program is never imported on the host. Interactive users may instead call condition.call("terminal", command) or condition.call("python", "/scratch/script.py") through the same existing API. Trusted usage_tokens accounting remains the owner's responsibility; no model adapter, provider, token-billing guarantee or model authorization is supplied.

Never give a candidate the repository, other arm, source package, output evidence, Docker socket or private reference. Candidate contexts must also be independent outside the container; isolated mounts alone do not prevent an external model context from retaining another arm's information.

Condition.freeze captures bounded opaque result bytes and closes its resources. PairController.finish requires both successfully frozen closed conditions and joins watchdogs before publishing PAIR_BARRIER.json. It is valid for a candidate to return a weak/discrepant result; no reference-program parity is required. A missing result or failed/unknown cleanup is not successful science. Preserve every failure and partial; recover only exact owned resources using the existing selected outer owner, with no automatic retry.

## Validate and score after complete closure

The external owner must establish both arms' closed receipts, exact owned-container absence, reaped CLI/driver groups, captured output hashes and PAIR_BARRIER.json before private grading or feedback. The controller's barrier is not an independent whole-host absence measurement. The accepted fixed-oracle operation demonstrates the sequencing to reuse, but its exact request and competence expectation are not generic participant authority.

First validate both captured submissions without private data:

```sh
python3.11 -I -S -B /absolute/package/bootstrap.py --manifest-sha256 RELEASE_SHA256 validate --submission /owner/pair/A/submission.json
python3.11 -I -S -B /absolute/package/bootstrap.py --manifest-sha256 RELEASE_SHA256 validate --submission /owner/pair/B/submission.json
```

Only after both arm sessions and driver groups have closed, the already admitted owner invokes the unchanged scalar artifact scorer separately for each arm. Each scorer retains its30-second alarm and exact private-reference hash; use fresh output paths:

```sh
python3.11 -I -S -B /absolute/package/bootstrap.py --manifest-sha256 RELEASE_SHA256 score --submission /owner/pair/A/submission.json --reference /private/private_expected.json --output /owner/grades/A.json
python3.11 -I -S -B /absolute/package/bootstrap.py --manifest-sha256 RELEASE_SHA256 score --submission /owner/pair/B/submission.json --reference /private/private_expected.json --output /owner/grades/B.json
```

These CLI modes are artifact operations, not a lifecycle or proof that a program ran. The source-loading time precedes the original scalar alarm and belongs inside the separately bounded whole owner. An invalid or unsupported artifact receives its existing classification; a failed/private-reference problem is an operator error. Retain each grade's16/24/5 denominators, all four endpoint records, status, full_reconstruction and continuous score. Do not require full reconstruction merely to admit a valid participant output. The primary score is numeric_score times endpoint_support_score times cohort_score; stronger p values earn no extra credit.

## Preserved limits

Nominal pooled-spine p values do not establish mouse-level inference. Caption-p discrepancies, deposit-version equivalence, missing supplementary Methods, prior answer exposure, source-defined eligibility and the broader compartment/intervention claims remain explicit. Correct scalar outputs alone do not prove fresh computation, data use, code-access benefit, protected improvement, SOTA, a complete paper investigation or submission readiness. Historical baseline and cost records remain external evidence with their original contexts, not new observations.

Only generated relocation/admission checks are selected for this source package. Runtime/whole-owner qualification and authentic paired execution remain external and unqualified by this delivery.
