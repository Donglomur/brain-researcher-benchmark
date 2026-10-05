# Private artifact provisioning — PR #175

This is a code/public-metadata publication of the existing repair
`047572a947fd401373bddd7f6ec0537d917b86aa`. The rebuilt source-derived answer bank is deliberately absent
from this tree and from its newly published commit ancestry. Earlier public
history may contain an obsolete bank; it is not valid for this repaired verifier.
This revision is **not standalone runnable** and is not a new scientific result.

## Exact private inputs

`PRIVATE_ARTIFACTS.json` is the machine-readable identity manifest.

| Task-relative path | Bytes | SHA256 |
| --- | ---: | --- |
| `tests/reference.npz` | 16196995 | `49e416e3f36eecd2cbcc9e85489fd8198327b96ff2d6c62f550380e5b6bb90f3` |

## Evaluator/operator procedure

1. Obtain the approved frozen bytes through the private evaluation-artifact
   channel. Do not regenerate, substitute an old public bank, or relax checks.
2. Before grading, provision `tests/reference.npz` at this exact task-relative
   path, in the private verifier bundle. Harbor must expose it only at
   `/tests/reference.npz` during verification, after the coding agent has stopped.
   Never put the bank in the agent image, instruction, public commit, or agent
   mount. Use a private staging copy if the runner transports the tests directory.
3. Run `python3 tests/private_reference.py` in that private staging copy. The
   evaluator repeats the exact size/SHA256 check before running scientific tests;
   direct pytest collection of `tests/test_outputs.py` also fails closed.
4. Missing or mismatched provisioning exits as `PROVISIONING_ERROR` before any
   scoring code. The preflight does not write, delete, or overwrite reward files.
   Treat this as infrastructure failure, never as an LLM failure. Use a fresh
   trial/log directory and inspect the process exit status, not stale rewards.

The scientific instruction, oracle, tolerances, and repaired verifier equations
are unchanged by packaging. The original tested repair and historical reward
artifacts remain untouched. Local packaging checks cover correct/missing/stale
private bytes and source projection identity; they are **not** a fresh container
oracle run or evidence of scientific adequacy or model difficulty.

The exact paths are git-ignored only to reduce accidental additions; this is not
an access-control mechanism. Do not force-add these private inputs. Publicly
licensed agent inputs already present in the approved repair retain their source
manifests and attribution; "code-only" does not mean that public metadata vanish.
