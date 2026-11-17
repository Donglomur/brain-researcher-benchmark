# Reviewed source commits and publication

Agents create small reviewed source commits on separate local `agents/neuro/` refs. The root agent reviews each exact commit and integrates the queue serially into the checked-out `build/neuroscience-200` branch. The utility is `tools/neurobench_source_queue.py`; it never pushes, changes working-tree files, or authorizes scientific execution.

## Agent commit

Freeze a JSON allowlist containing exact repository-relative paths, byte lengths and SHA-256 hashes. The independent review must identify that exact allowlist hash and length. Use explicit owned prefixes, and `--member-key` when the proposal contains multiple supported member lists. `--include-allowlist` adds the proposal itself only when it is inside an owned prefix. Use the same choices during integration.

```sh
REPO=/absolute/path/to/neuroscience-benchmark-planning
python3.11 -I -S -B "$REPO/tools/neurobench_source_queue.py" --repo "$REPO" commit \
  --allowlist authoring/delivery-20261105/OWNED/SOURCE_PROPOSAL.json \
  --allowlist-bytes REVIEWED_BYTES --allowlist-sha256 REVIEWED_SHA256 \
  --member-key files --prefix authoring/delivery-20261105/OWNED \
  --include-allowlist --ref refs/heads/agents/neuro/UNIQUE_BATCH \
  --message 'Add reviewed source for this batch'
```

The example placeholders must be replaced with the already-reviewed values. Do not silently refresh a review pin from changed files. The returned `commit` is the exact tip for root review. By default the parent is the current HEAD captured at invocation; `--base` can name an explicitly reviewed ancestor. A unique temporary `GIT_INDEX_FILE`, Git plumbing and a new scoped ref leave shared HEAD, shared index and all working-tree bytes unchanged. Multiple agents may create these commits concurrently.

## Root integration

Root inspects the proposed source and exact tip, then runs one integration at a time. This operation requires the checked-out build branch, no active Git operation and a shared index whose tree exactly equals HEAD. Existing staged user work causes refusal; unstaged and untracked files stay byte-for-byte unchanged. `--root-integrator` is an explicit workflow acknowledgement, not an operating-system identity boundary.

```sh
python3.11 -I -S -B "$REPO/tools/neurobench_source_queue.py" --repo "$REPO" integrate \
  --allowlist authoring/delivery-20261105/OWNED/SOURCE_PROPOSAL.json \
  --allowlist-bytes REVIEWED_BYTES --allowlist-sha256 REVIEWED_SHA256 \
  --member-key files --prefix authoring/delivery-20261105/OWNED \
  --include-allowlist --ref refs/heads/agents/neuro/UNIQUE_BATCH \
  --expected-commit EXACT_REVIEWED_AGENT_COMMIT \
  --branch refs/heads/build/neuroscience-200 --root-integrator \
  --message 'Merge reviewed source batch'
```

The utility checks every changed path and blob against the frozen allowlist, requires the agent's sole parent to be an ancestor of the current build tip, applies the patch to a temporary index with three-way conflict checking, and creates a merge with the current build tip and reviewed agent tip as its two parents. It uses a prepared Git reference transaction, a compare-and-swap update and an owned shared-index lock. A conflict, changed agent tip, staged work or reference race refuses without overwriting user work. It does not check out the merged files: if the existing working tree differs from the resulting index, those differences remain visible as unstaged changes.

## Interruption and recovery

The Git reference and index are separate files. This utility does not promise a single crash-atomic filesystem transaction. Ordinary precommit errors restore the saved index; a process death can leave a durable `.git/neuro-source-queue.transaction.json` journal and owned locks. Root must inspect the outcome and use the bounded recovery operation rather than deleting stale locks blindly:

```sh
python3.11 -I -S -B "$REPO/tools/neurobench_source_queue.py" --repo "$REPO" recover --root-integrator
```

Recovery requires the recorded launcher and Git processes to be gone, the same checked-out branch, and that branch to equal the recorded old or new commit. It authenticates remaining lock ownership and index hashes before restoration. Unknown branch movement, unrelated index contents, active Git operations or incomplete journals require manual inspection; recovery refuses rather than guessing. A completed merge can report `cleanup=journal_recovery_required`, which means integration succeeded but owned metadata cleanup remains. PID reuse can conservatively block recovery. Git 2.53.0 was tested; the implementation requires prepared current-branch updates to hold `HEAD.lock` and refuses if that behavior is absent. Temporary objects from unsuccessful commits can remain unreachable until normal Git maintenance.

## Publication to the owned fork

Local build and agent history contains earlier held-out arrays and signed URLs. **Never push those local refs or their complete history.** Root publishes only content-audited source snapshots on a separate clean history rooted at the owned fork's `master`, to the owned fork's `publish/neuroscience-200` branch. This is a separate root publication procedure, not a queue feature. Do not push upstream, change a default branch, or open an upstream PR without explicit instructions.

The queue refuses known key, array, archive and database paths before reading their bodies and requires ordinary UTF-8 source files. These checks are not a universal secret detector: text and JSON can contain sensitive material. Root must audit all new source and the outgoing history before any public push. Per-turn build, execution, and pause permissions remain in the research plan and user instructions; committing source does not qualify a benchmark or authorize a model run.
