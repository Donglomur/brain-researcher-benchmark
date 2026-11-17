# Configure the existing behavior owner

This is the existing public TMS plan/build/select interface adapted to the accepted complete behavior profile. It relocates authorized assets and host bindings without changing the scientific method, scorer, execution lifecycle, capacity guard, runtime or budgets. It does not create another task or another owner architecture.

## Prepare and review

1. Acquire the exact research assets using [the acquisition recipe](../ACQUISITION.md). Obtain the exact inherited evidence records from their custodian and keep all assets, evidence, programs and outputs outside the public source tree. `CATALOG.json` fixes their byte lengths and digests. Its blank locators and null socket identity deliberately cannot execute.
2. Copy `REQUEST.template.json` to a private path. Replace every `/OWNER` placeholder with a canonical absolute path to an ordinary single-link file or fresh output tree. Supply both candidate program commitments and the actual host Python/socket bindings. The two programs may contain the same bytes but must have distinct locators. Likewise `official_code_review` and `source_origin_asset_binding` share content commitments but require separate ordinary files: this inherited provisioner rejects locator aliasing.
3. Record the applicable existing owner authority and set `authorized_local_use` true only under that authority. This is a local-use packet; `redistribution_granted` remains false. The template starts unselected with no supplied program, source-review or runtime-admission commitment.
4. Run the source-only planner from any working directory:

```sh
python3 -I -S -B /ABSOLUTE/behavior-v1/portable/provision.py plan --request /ABSOLUTE/private-request.json
```

The default source root is the containing `behavior-v1` directory. `--source-root` can name a byte-exact relocated copy. The catalog maps all 16 logical dependencies inside that tree. Shared task/method/schema/scorer sources are reused in place; the other 12 roles are in `owner-template/`. No private source checkout is required.

The plan returns the exact rendered source-lock commitment, fresh source-review/runtime-admission templates and an unselected owner grant. Have the complete rendered source and selected runtime independently reviewed. Store the accepted records privately and fill their lengths/digests in the request. Their descriptors remain outside the runtime lock to avoid a hash cycle. Run plan on that final request before build. A JSON boolean is a trusted operator attestation, not a credential or automatic permission.

## Build and select without launching

```sh
python3 -I -S -B /ABSOLUTE/behavior-v1/portable/provision.py build --request /ABSOLUTE/private-request.json
python3 -I -S -B /ABSOLUTE/behavior-v1/portable/provision.py select --package /ABSOLUTE/private-package --grant /ABSOLUTE/private-owner-grant.json
```

`build` creates fresh private package/operation trees and an unselected manifest. It reads only source and metadata, not research data, article, official code, program or reference bodies. After the owner selects one operation, set only `owner_selected_execution` true in the exact final grant and use `select`. Selection verifies every rendered source, the grant and both new review records, writes one immutable selection, and returns the exact invocation as a JSON argv array. It never executes that array and never replaces an existing attempt or retries automatically.

Only a separately selected operator may launch that exact invocation in an admitted resource window. The existing owner first retains eight capacity probes and checks complete invented numerical conventions in the exact admitted image. It then stages the same complete paper/CSV/task/method/schema for both arms, adding precisely two official files only to B. Both closed outputs and commitments must exist before protected grading. The scorer, protected reference, host socket, operator records and other arm's output never enter participant mounts.

The inherited ceilings remain 420 active / 480 inner / 510 outer seconds, 60 seconds compatibility, 120 seconds per arm, three sequential 1-CPU/2-GiB containers, 257 MiB whole managed reads and 129 MiB retained. Host peak-process reporting is not an aggregate hard-memory guarantee. Provisioning needs a separate 12-MiB read / 6-MiB retained source-and-metadata allowance for two plan calls, build and select. No model campaign is selected.

## Source controls

```sh
python3 -I -S -B /ABSOLUTE/behavior-v1/portable/test_provision.py -v
python3 -I -S -B /ABSOLUTE/behavior-v1/portable/test_behavior_boundary.py -v
python3 -I -S -B /ABSOLUTE/behavior-v1/portable/test_construction_program.py -v
python3 -I -S -B /ABSOLUTE/behavior-v1/portable/test_public_export.py -v
```

These use invented arithmetic and mocked transport, not Docker or authentic bodies. Full fixture fingerprint checks remain version-sensitive; accepted author controls used normative CPython 3.11.6. A source-test pass does not qualify a candidate image or a new host. See [RUNTIME.md](../RUNTIME.md) for the precise deployment gap and [CONTROL_NOTES.md](CONTROL_NOTES.md) for validation scope.
